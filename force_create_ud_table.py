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
        from app.migrations import create_tableaux_bord_ud_table_if_needed

        # Exécuter la migration
        create_tableaux_bord_ud_table_if_needed()

        logger.info("✅ Migration terminée avec succès!")
        logger.info("📝 La table tableaux_bord_ud a été créée ou vérifiée.")
        logger.info("🔄 Vous pouvez maintenant réessayer l'import des contacts UD.")

        return 0

    except Exception as e:
        logger.error(f"❌ Erreur lors de la migration: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1

if __name__ == "__main__":
    sys.exit(main())
