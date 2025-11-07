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
from .rate_limiter import sirene_rate_limiter

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
    Récupère l'IDCC d'un SIRET via l'API Siret2IDCC de manière SYNCHRONE.

    Note: L'API Sirene de l'INSEE NE CONTIENT PAS les IDCC !
    Les IDCC proviennent des déclarations DSN, pas du registre Sirene.

    Utilise l'API Siret2IDCC : https://siret2idcc.fabrique.social.gouv.fr/api/v2/{siret}

    Returns:
        - {"idcc": "XXXX", "success": True} si IDCC trouvé
        - {"idcc": None, "success": True} si API OK mais pas d'IDCC
        - None si erreur API ou SIRET invalide
    """
    SIRET2IDCC_API_BASE = "https://siret2idcc.fabrique.social.gouv.fr/api/v2"

    # Nettoyer le SIRET
    siret_clean = siret.strip().replace(" ", "")
    if len(siret_clean) != 14 or not siret_clean.isdigit():
        logger.warning(f"SIRET invalide: {siret}")
        return None

    url = f"{SIRET2IDCC_API_BASE}/{siret_clean}"

    # Retry avec backoff pour gérer les 429
    import time
    max_retries = 3
    retry_delay = 2  # secondes

    for attempt in range(max_retries):
        try:
            # Respecter le rate limit
            sirene_rate_limiter.wait_if_needed()

            logger.error(f"Calling API Siret2IDCC for SIRET {siret_clean} (attempt {attempt + 1}/{max_retries})...")
            with httpx.Client(timeout=10.0) as client:
                response = client.get(url, headers={"Accept": "application/json"})
                logger.error(f"API Response for {siret_clean}: status={response.status_code}")

                if response.status_code == 200:
                    data = response.json()

                    # La réponse est un tableau avec un objet contenant le SIRET et ses conventions
                    # [{"siret": "...", "conventions": [...]}]
                    if data and len(data) > 0:
                        siret_data = data[0]
                        conventions = siret_data.get("conventions", [])

                        # Chercher une convention active
                        for conv in conventions:
                            if conv.get("active", False) and conv.get("nature") == "IDCC":
                                idcc = conv.get("num")
                                idcc_url = conv.get("url")
                                if idcc:
                                    logger.error(f"IDCC found for {siret_clean}: {idcc} - URL: {idcc_url}")
                                    return {"idcc": idcc, "idcc_url": idcc_url, "success": True}

                        # Pas de convention active trouvée
                        logger.error(f"No active IDCC for {siret_clean} (API OK, but no IDCC in database)")
                        return {"idcc": None, "success": True}
                    else:
                        logger.error(f"Empty response for {siret_clean}")
                        return {"idcc": None, "success": True}

                elif response.status_code == 404:
                    logger.error(f"SIRET non trouvé dans Siret2IDCC: {siret_clean}")
                    # 404 n'est pas une erreur critique - l'entreprise peut simplement ne pas avoir d'IDCC
                    return {"idcc": None, "success": True}

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
                    logger.error(f"Erreur API Siret2IDCC ({response.status_code})")
                    return None

        except httpx.TimeoutException:
            logger.error(f"Timeout lors de la requête SIRET {siret_clean}")
            return None
        except Exception as e:
            logger.error(f"Erreur lors de l'appel API Siret2IDCC: {e}")
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
            logger.error(f"Starting enrichment process with rate limit: {sirene_rate_limiter.max_requests} req/{sirene_rate_limiter.time_window}s")
            logger.error(f"Estimated time: ~{(total * 2.5):.0f} seconds ({(total * 2.5 / 60):.1f} minutes)")

            if total == 0:
                logger.error("No invitations to enrich. Task completed.")
                task_tracker.complete_task(task_id, {"total": 0, "message": "No invitations to process"})
                return

            for i, invitation in enumerate(invitations):
                try:
                    # Récupérer les données depuis l'API SIRENE (version synchrone)
                    data = _get_siret_sync(invitation.siret)

                    if data and data.get("success"):
                        # API a répondu avec succès
                        idcc_value = data.get("idcc")
                        idcc_url_value = data.get("idcc_url")

                        # Marquer la date d'enrichissement dans tous les cas
                        invitation.date_enrichissement = datetime.now()

                        if idcc_value:
                            # IDCC trouvé : on le met à jour
                            invitation.idcc = idcc_value
                            invitation.idcc_url = idcc_url_value
                            enrichis += 1
                            # Récupérer aussi la dénomination pour un log plus lisible
                            denom = invitation.denomination or invitation.siret
                            logger.error(f"✓ [{i+1}/{total}] SIRET {invitation.siret} ({denom[:40]}...) → IDCC: {idcc_value} | URL: {idcc_url_value}")
                        else:
                            # API OK mais pas d'IDCC : on marque quand même l'enrichissement
                            # pour éviter de réessayer indéfiniment
                            denom = invitation.denomination or invitation.siret
                            logger.error(f"○ [{i+1}/{total}] SIRET {invitation.siret} ({denom[:40]}...) → Pas d'IDCC dans la base Sirene")

                        # Commit tous les 10 pour un affichage plus rapide des données dans l'interface
                        if (i + 1) % 10 == 0:
                            session.commit()
                            progress_pct = ((i + 1) / total * 100)
                            logger.error(f"Progress: {i + 1}/{total} ({progress_pct:.1f}%) - {enrichis} IDCC found - Data committed and visible in database")
                    else:
                        # Erreur API (404, timeout, etc.)
                        erreurs += 1
                        denom = invitation.denomination or invitation.siret
                        logger.error(f"✗ [{i+1}/{total}] SIRET {invitation.siret} ({denom[:40]}...) → Erreur API ou SIRET non trouvé")

                except Exception as e:
                    denom = invitation.denomination or invitation.siret
                    logger.error(f"✗ [{i+1}/{total}] SIRET {invitation.siret} ({denom[:40]}...) → Exception: {e}")
                    erreurs += 1
                    continue

            # Commit final
            session.commit()

            # Calculer le nombre de SIRETs traités avec succès (avec ou sans IDCC)
            traites_avec_succes = total - erreurs

            result = {
                "total": total,
                "traites_avec_succes": traites_avec_succes,
                "idcc_trouves": enrichis,
                "sans_idcc": traites_avec_succes - enrichis,
                "erreurs": erreurs
            }
            task_tracker.complete_task(task_id, result)
            logger.error(f"enrichir_invitations_idcc completed: {enrichis} IDCC trouvés / {traites_avec_succes} traités avec succès / {erreurs} erreurs / {total} total")

        finally:
            session.close()
    except Exception as e:
        error_msg = f"Error in enrichir_invitations_idcc: {str(e)}"
        logger.exception(error_msg)
        task_tracker.fail_task(task_id, error_msg)
