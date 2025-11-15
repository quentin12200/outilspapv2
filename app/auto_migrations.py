"""
Migration automatique pour ajouter les champs d'authentification par email.
Ce script s'exécute automatiquement au démarrage de l'application.
"""

import logging
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def check_column_exists(session: Session, table_name: str, column_name: str) -> bool:
    """Vérifie si une colonne existe dans une table."""
    try:
        inspector = inspect(session.bind)
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception as e:
        logger.error(f"Erreur lors de la vérification de la colonne {column_name}: {e}")
        return False


def migrate_add_email_fields(session: Session) -> bool:
    """
    Ajoute les champs d'authentification par email à la table users si nécessaire.

    Returns:
        bool: True si la migration a été appliquée, False si déjà à jour
    """
    try:
        # Vérifier si les colonnes existent déjà
        if check_column_exists(session, 'users', 'email_verified'):
            logger.info("✅ Les colonnes d'authentification email existent déjà")
            return False

        logger.info("🔄 Application de la migration email...")

        # Liste des colonnes à ajouter
        columns_to_add = [
            ("email_verified", "BOOLEAN DEFAULT 0 NOT NULL"),
            ("validation_token", "VARCHAR(255)"),
            ("validation_token_expiry", "DATETIME"),
            ("reset_token", "VARCHAR(255)"),
            ("reset_token_expiry", "DATETIME")
        ]

        # Ajouter chaque colonne
        for col_name, col_type in columns_to_add:
            try:
                session.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}"))
                logger.info(f"  ✅ Colonne '{col_name}' ajoutée")
            except Exception as e:
                if "duplicate column name" in str(e).lower():
                    logger.info(f"  ⏭️  Colonne '{col_name}' existe déjà")
                else:
                    logger.error(f"  ❌ Erreur lors de l'ajout de '{col_name}': {e}")
                    raise

        # Créer les index
        indexes = [
            ("idx_users_validation_token", "users", "validation_token"),
            ("idx_users_reset_token", "users", "reset_token")
        ]

        for idx_name, table, column in indexes:
            try:
                session.execute(text(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table}({column})"))
                logger.info(f"  ✅ Index '{idx_name}' créé")
            except Exception as e:
                logger.warning(f"  ⚠️  Erreur lors de la création de l'index '{idx_name}': {e}")

        session.commit()
        logger.info("✅ Migration email appliquée avec succès !")

        return True

    except Exception as e:
        session.rollback()
        logger.error(f"❌ Erreur lors de la migration : {str(e)}")
        raise


def run_auto_migrations(session: Session):
    """
    Exécute toutes les migrations automatiques nécessaires.

    Cette fonction est appelée au démarrage de l'application.
    """
    try:
        logger.info("🔍 Vérification des migrations nécessaires...")

        # Migration : Ajout des champs email
        migrate_add_email_fields(session)

        logger.info("✅ Toutes les migrations sont à jour")

    except Exception as e:
        logger.error(f"❌ Erreur critique lors des migrations automatiques : {str(e)}")
        # Ne pas faire planter l'application, mais loguer l'erreur
        pass
