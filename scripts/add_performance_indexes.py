#!/usr/bin/env python3
"""
Script pour ajouter les index de performance sur les tables principales.

DESCRIPTION:
    Ajoute les index manquants pour optimiser les requêtes fréquentes,
    notamment pour build_siret_summary() et les endpoints API.

USAGE:
    python scripts/add_performance_indexes.py

TABLES AFFECTÉES:
    - Tous_PV (PVEvent)
    - invitations (Invitation)
    - siret_summary (SiretSummary)
    - audit_logs (AuditLog)
    - background_tasks (BackgroundTask)

NOTES:
    - Les index sont créés avec IF NOT EXISTS pour éviter les doublons
    - L'exécution peut prendre plusieurs minutes sur de grosses bases
    - Aucun impact sur les données existantes

AUTEUR:
    Généré automatiquement lors de l'optimisation des performances

DATE:
    2025-01-08
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import engine, SessionLocal
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def add_indexes():
    """Ajoute les index de performance"""
    logger.info("🔍 Ajout des index de performance...")
    logger.info("=" * 70)

    # Liste des index à créer
    indexes = {
        "PVEvent (Tous_PV)": [
            "CREATE INDEX IF NOT EXISTS idx_pv_siret ON Tous_PV(siret)",
            "CREATE INDEX IF NOT EXISTS idx_pv_cycle ON Tous_PV(Cycle)",
            "CREATE INDEX IF NOT EXISTS idx_pv_date ON Tous_PV(date_scrutin)",
            "CREATE INDEX IF NOT EXISTS idx_pv_siret_cycle ON Tous_PV(siret, Cycle)",
        ],
        "Invitation": [
            "CREATE INDEX IF NOT EXISTS idx_invitation_siret ON invitations(siret)",
            "CREATE INDEX IF NOT EXISTS idx_invitation_date ON invitations(date_invit)",
            "CREATE INDEX IF NOT EXISTS idx_invitation_siret_date ON invitations(siret, date_invit)",
            "CREATE INDEX IF NOT EXISTS idx_invitation_enrichment ON invitations(date_enrichissement)",
        ],
        "SiretSummary": [
            "CREATE INDEX IF NOT EXISTS idx_summary_siret ON siret_summary(siret)",
            "CREATE INDEX IF NOT EXISTS idx_summary_statut ON siret_summary(statut_pap)",
            "CREATE INDEX IF NOT EXISTS idx_summary_cgt ON siret_summary(cgt_implantee)",
            "CREATE INDEX IF NOT EXISTS idx_summary_date_pv ON siret_summary(date_pv_max)",
        ],
        "AuditLog": [
            "CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_logs(user_identifier)",
            "CREATE INDEX IF NOT EXISTS idx_audit_resource ON audit_logs(resource_type)",
            "CREATE INDEX IF NOT EXISTS idx_audit_success ON audit_logs(success)",
        ],
        "BackgroundTask": [
            "CREATE INDEX IF NOT EXISTS idx_task_status ON background_tasks(status)",
            "CREATE INDEX IF NOT EXISTS idx_task_started ON background_tasks(started_at)",
            "CREATE INDEX IF NOT EXISTS idx_task_completed ON background_tasks(completed_at)",
        ],
    }

    db = SessionLocal()
    try:
        total_created = 0
        total_skipped = 0

        for table, index_sqls in indexes.items():
            logger.info(f"\n📋 Table: {table}")
            logger.info("-" * 70)

            for sql in index_sqls:
                try:
                    # Extraire le nom de l'index
                    index_name = sql.split("IF NOT EXISTS ")[1].split(" ON ")[0]

                    logger.info(f"  • Création de l'index {index_name}...")
                    db.execute(text(sql))
                    db.commit()
                    logger.info(f"    ✅ Index {index_name} créé")
                    total_created += 1

                except Exception as e:
                    if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                        logger.info(f"    ⏭️  Index {index_name} existe déjà")
                        total_skipped += 1
                    else:
                        logger.error(f"    ❌ Erreur lors de la création de {index_name}: {e}")

        logger.info("\n" + "=" * 70)
        logger.info(f"✅ Indexation terminée!")
        logger.info(f"📊 Index créés: {total_created}")
        logger.info(f"📊 Index déjà existants: {total_skipped}")

        # Analyser les tables pour mettre à jour les statistiques
        logger.info("\n🔍 Analyse des tables pour mettre à jour les statistiques...")
        try:
            # SQLite ANALYZE
            db.execute(text("ANALYZE"))
            db.commit()
            logger.info("✅ Statistiques mises à jour")
        except Exception as e:
            logger.warning(f"⚠️  Impossible d'analyser les tables: {e}")

        return True

    except Exception as e:
        logger.error(f"\n❌ Erreur lors de l'indexation: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return False

    finally:
        db.close()


if __name__ == "__main__":
    success = add_indexes()
    sys.exit(0 if success else 1)
