"""
Gestionnaire de tâches de fond pour les opérations lourdes
"""
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
import logging
import httpx
import os
import uuid

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskTracker:
    """
    Tracker simple pour suivre l'état des tâches en arrière-plan.
    En production, utiliser Redis ou une vraie queue comme Celery.
    """
    def __init__(self):
        self._tasks = {}

    def start_task(self, task_id: str, description: str = None):
        """Marque une tâche comme démarrée"""
        self._tasks[task_id] = {
            "status": TaskStatus.RUNNING,
            "description": description,
            "started_at": datetime.now(),
            "completed_at": None,
            "result": None,
            "error": None,
        }
        logger.info(f"Task {task_id} started: {description}")

    def complete_task(self, task_id: str, result=None):
        """Marque une tâche comme terminée avec succès"""
        if task_id in self._tasks:
            self._tasks[task_id].update({
                "status": TaskStatus.COMPLETED,
                "completed_at": datetime.now(),
                "result": result,
            })
            logger.info(f"Task {task_id} completed successfully")

    def fail_task(self, task_id: str, error: str):
        """Marque une tâche comme échouée"""
        if task_id in self._tasks:
            self._tasks[task_id].update({
                "status": TaskStatus.FAILED,
                "completed_at": datetime.now(),
                "error": error,
            })
            logger.error(f"Task {task_id} failed: {error}")

    def get_task_status(self, task_id: str) -> Optional[dict]:
        """Récupère le statut d'une tâche"""
        return self._tasks.get(task_id)

    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """Nettoie les anciennes tâches terminées"""
        now = datetime.now()
        to_remove = []
        for task_id, task_data in self._tasks.items():
            if task_data["completed_at"]:
                age = (now - task_data["completed_at"]).total_seconds() / 3600
                if age > max_age_hours:
                    to_remove.append(task_id)

        for task_id in to_remove:
            del self._tasks[task_id]

        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old tasks")


# Instance globale du tracker (en production, utiliser Redis)
task_tracker = TaskTracker()


def run_build_siret_summary(session_factory):
    """
    Fonction à exécuter en arrière-plan pour reconstruire le résumé SIRET.
    Utilise une session dédiée pour éviter les conflits.
    """
    from . import etl

    task_id = "build_siret_summary"
    task_tracker.start_task(task_id, "Reconstruction de la table siret_summary")

    try:
        # Créer une nouvelle session pour cette tâche
        session = session_factory()
        try:
            logger.info("Starting build_siret_summary in background...")
            rows_generated = etl.build_siret_summary(session)
            task_tracker.complete_task(task_id, {"rows": rows_generated})
            logger.info(f"build_siret_summary completed: {rows_generated} rows generated")
        finally:
            session.close()
    except Exception as e:
        error_msg = f"Error in build_siret_summary: {str(e)}"
        logger.exception(error_msg)
        task_tracker.fail_task(task_id, error_msg)


def _get_siret_sync(siret: str) -> Optional[Dict[str, Any]]:
    """
    Récupère les informations d'un SIRET via l'API SIRENE de manière SYNCHRONE.
    Version simplifiée pour les tâches de fond.
    """
    SIRENE_API_BASE = "https://api.insee.fr/api-sirene/3.11"

    # Configuration de l'authentification (API Sirene 3.11)
    api_key = (os.getenv("SIRENE_API_KEY") or os.getenv("API_SIRENE_KEY") or "").strip()

    headers = {"Accept": "application/json"}
    if api_key:
        # API Sirene 3.11 : utiliser X-INSEE-Api-Key-Integration
        headers["X-INSEE-Api-Key-Integration"] = api_key
        logger.error(f"[SIRENE AUTH] Using API key: {api_key[:8]}...{api_key[-4:]} (length: {len(api_key)})")
        logger.error(f"[SIRENE AUTH] Header name: X-INSEE-Api-Key-Integration")
    else:
        logger.error("[SIRENE AUTH] ⚠️ NO API KEY FOUND - Using public access (limited rate)")

    # Nettoyer le SIRET
    siret_clean = siret.strip().replace(" ", "")
    if len(siret_clean) != 14 or not siret_clean.isdigit():
        logger.warning(f"SIRET invalide: {siret}")
        return None

    url = f"{SIRENE_API_BASE}/siret/{siret_clean}"

    # Retry avec backoff pour gérer les 429
    import time
    max_retries = 3
    retry_delay = 2  # secondes

    for attempt in range(max_retries):
        try:
            logger.error(f"Calling API SIRENE for SIRET {siret_clean} (attempt {attempt + 1}/{max_retries})...")
            with httpx.Client(timeout=10.0) as client:
                response = client.get(url, headers=headers)
                logger.error(f"API Response for {siret_clean}: status={response.status_code}")

                if response.status_code == 200:
                    data = response.json()
                    etablissement = data.get("etablissement", {})
                    unite_legale = etablissement.get("uniteLegale", {})

                    # Extraire l'IDCC
                    idcc = unite_legale.get("identifiantConventionCollectiveRenseignee")

                    if idcc:
                        logger.error(f"IDCC found for {siret_clean}: {idcc}")
                        return {"idcc": idcc}
                    else:
                        logger.error(f"No IDCC for {siret_clean}")
                        return None

                elif response.status_code == 404:
                    logger.error(f"SIRET non trouvé: {siret_clean}")
                    return None

                elif response.status_code == 429:
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                        logger.warning(f"Rate limit atteint (429). Retry dans {wait_time}s...")
                        time.sleep(wait_time)
                        continue  # Retry
                    else:
                        logger.error("Rate limit atteint - Nombre max de retries atteint")
                        return None

                else:
                    logger.error(f"Erreur API Sirene ({response.status_code})")
                    return None

        except httpx.TimeoutException:
            logger.error(f"Timeout lors de la requête SIRET {siret_clean}")
            return None
        except Exception as e:
            logger.error(f"Erreur lors de l'appel API SIRENE: {e}")
            return None

    return None  # Si toutes les tentatives échouent


def run_enrichir_invitations_idcc():
    """
    Fonction à exécuter en arrière-plan pour enrichir les invitations avec IDCC via l'API SIRENE.
    """
    import sys
    try:
        # Écrire directement dans stderr ET logger
        msg = "=" * 80 + "\nrun_enrichir_invitations_idcc() CALLED\n" + "=" * 80
        print(msg, file=sys.stderr, flush=True)
        logger.error(msg)  # Utiliser ERROR pour être sûr que ça s'affiche

        from .models import Invitation
        from .db import SessionLocal

        task_id = "enrichir_invitations_idcc"
        logger.error(f"Creating task tracker for {task_id}")
        task_tracker.start_task(task_id, "Enrichissement des IDCC manquants via API SIRENE")
        logger.error(f"Task tracker started for {task_id}")
    except Exception as e:
        error_msg = f"CRITICAL ERROR AT START: {type(e).__name__}: {str(e)}"
        print(error_msg, file=sys.stderr, flush=True)
        logger.error(error_msg)
        import traceback
        traceback.print_exc(file=sys.stderr)
        raise

    try:
        session = SessionLocal()
        try:
            logger.error("Starting enrichir_invitations_idcc in background...")

            # Récupérer toutes les invitations sans IDCC
            invitations = session.query(Invitation).filter(
                (Invitation.idcc.is_(None)) | (Invitation.idcc == "")
            ).all()

            total = len(invitations)
            enrichis = 0
            erreurs = 0

            logger.error(f"Found {total} invitations without IDCC")

            for i, invitation in enumerate(invitations):
                try:
                    # Récupérer les données depuis l'API SIRENE (version synchrone)
                    data = _get_siret_sync(invitation.siret)

                    if data and data.get("idcc"):
                        # Mettre à jour l'IDCC
                        invitation.idcc = data.get("idcc")
                        invitation.date_enrichissement = datetime.now()
                        enrichis += 1

                        # Commit tous les 50 pour éviter de perdre tout en cas d'erreur
                        if (i + 1) % 50 == 0:
                            session.commit()
                            logger.error(f"Progress: {i + 1}/{total} processed ({enrichis} enriched)")
                    else:
                        erreurs += 1

                except Exception as e:
                    logger.error(f"Error enriching SIRET {invitation.siret}: {e}")
                    erreurs += 1
                    continue

            # Commit final
            session.commit()

            result = {
                "total": total,
                "enrichis": enrichis,
                "erreurs": erreurs
            }
            task_tracker.complete_task(task_id, result)
            logger.error(f"enrichir_invitations_idcc completed: {enrichis}/{total} enriched, {erreurs} errors")

        finally:
            session.close()
    except Exception as e:
        error_msg = f"Error in enrichir_invitations_idcc: {str(e)}"
        logger.exception(error_msg)
        task_tracker.fail_task(task_id, error_msg)
