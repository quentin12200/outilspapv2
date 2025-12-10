#!/usr/bin/env python3
"""
Script pour forcer la création de la table tableaux_bord_ud
sans avoir à redémarrer l'application.

Usage:
    python force_create_ud_table.py
"""

import sys
import logging

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Exécute la migration pour créer la table tableaux_bord_ud"""
    try:
        logger.info("🚀 Démarrage de la migration forcée...")

        # Import des modules nécessaires
        from app.db import engine
        from app.migrations import create_tableaux_bord_ud_table_if_needed, create_pap_documents_table_if_needed

        # Exécuter les migrations
        create_tableaux_bord_ud_table_if_needed()
        create_pap_documents_table_if_needed()

        logger.info("✅ Migrations terminées avec succès!")
        logger.info("📝 Les tables tableaux_bord_ud et pap_documents ont été créées ou vérifiées.")
        logger.info("🔄 Vous pouvez maintenant utiliser les fonctionnalités UD et portails PAP.")

        return 0

    except Exception as e:
        logger.error(f"❌ Erreur lors de la migration: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1

if __name__ == "__main__":
    sys.exit(main())
