"""
Gestionnaire de tâches de fond pour les opérations lourdes
"""
from datetime import datetime
from enum import Enum
from typing import Optional
import logging

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


async def run_enrichir_invitations_idcc():
    """
    Fonction à exécuter en arrière-plan pour enrichir les invitations avec IDCC via l'API SIRENE.
    """
    from .models import Invitation
    from .database import SessionLocal
    from .services.sirene_api import enrichir_siret, SireneAPIError
    from datetime import datetime

    task_id = "enrichir_invitations_idcc"
    task_tracker.start_task(task_id, "Enrichissement des IDCC manquants via API SIRENE")

    try:
        session = SessionLocal()
        try:
            logger.info("Starting enrichir_invitations_idcc in background...")

            # Récupérer toutes les invitations sans IDCC
            invitations = session.query(Invitation).filter(
                (Invitation.idcc.is_(None)) | (Invitation.idcc == "")
            ).all()

            total = len(invitations)
            enrichis = 0
            erreurs = 0

            logger.info(f"Found {total} invitations without IDCC")

            for i, invitation in enumerate(invitations):
                try:
                    # Récupérer les données depuis l'API SIRENE
                    data = await enrichir_siret(invitation.siret)

                    if data and data.get("idcc"):
                        # Mettre à jour l'IDCC
                        invitation.idcc = data.get("idcc")
                        invitation.date_enrichissement = datetime.now()
                        enrichis += 1

                        # Commit tous les 50 pour éviter de perdre tout en cas d'erreur
                        if (i + 1) % 50 == 0:
                            session.commit()
                            logger.info(f"Progress: {i + 1}/{total} processed ({enrichis} enriched)")
                    else:
                        erreurs += 1

                except (SireneAPIError, Exception) as e:
                    logger.warning(f"Error enriching SIRET {invitation.siret}: {e}")
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
            logger.info(f"enrichir_invitations_idcc completed: {enrichis}/{total} enriched, {erreurs} errors")

        finally:
            session.close()
    except Exception as e:
        error_msg = f"Error in enrichir_invitations_idcc: {str(e)}"
        logger.exception(error_msg)
        task_tracker.fail_task(task_id, error_msg)
