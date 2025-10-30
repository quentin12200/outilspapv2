# app/migrations.py
"""
Migrations automatiques pour ajouter les colonnes Sirene si elles n'existent pas.
Ce script s'exécute au démarrage de l'application.
"""

import logging
from sqlalchemy import text, inspect
from .db import engine

logger = logging.getLogger(__name__)

# Colonnes Sirene à ajouter à la table invitations
SIRENE_COLUMNS = [
    ("denomination", "TEXT"),
    ("enseigne", "TEXT"),
    ("adresse", "TEXT"),
    ("code_postal", "VARCHAR(10)"),
    ("commune", "TEXT"),
    ("activite_principale", "VARCHAR(10)"),
    ("libelle_activite", "TEXT"),
    ("tranche_effectifs", "VARCHAR(5)"),
    ("effectifs_label", "TEXT"),
    ("est_siege", "BOOLEAN"),
    ("est_actif", "BOOLEAN"),
    ("categorie_entreprise", "VARCHAR(10)"),
    ("date_enrichissement", "DATETIME"),
]


def column_exists(table_name: str, column_name: str) -> bool:
    """Vérifie si une colonne existe dans une table."""
    inspector = inspect(engine)

    # Vérifie si la table existe
    if table_name not in inspector.get_table_names():
        return False

    # Récupère les colonnes de la table
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def add_sirene_columns_if_needed():
    """
    Ajoute les colonnes Sirene à la table invitations si elles n'existent pas.
    Cette migration est idempotente (peut être exécutée plusieurs fois sans problème).
    """
    logger.info("🔍 Vérification des colonnes Sirene dans la table invitations...")

    # Vérifie si la table invitations existe
    inspector = inspect(engine)
    if "invitations" not in inspector.get_table_names():
        logger.info("⚠️  Table invitations n'existe pas encore, elle sera créée par SQLAlchemy")
        return

    columns_added = []
    columns_already_exist = []

    with engine.connect() as conn:
        for column_name, column_type in SIRENE_COLUMNS:
            if not column_exists("invitations", column_name):
                # Ajoute la colonne
                try:
                    sql = text(f"ALTER TABLE invitations ADD COLUMN {column_name} {column_type}")
                    conn.execute(sql)
                    conn.commit()
                    columns_added.append(column_name)
                    logger.info(f"  ✅ Colonne ajoutée: {column_name} ({column_type})")
                except Exception as e:
                    logger.error(f"  ❌ Erreur lors de l'ajout de {column_name}: {e}")
            else:
                columns_already_exist.append(column_name)

    # Résumé
    if columns_added:
        logger.info(f"✅ Migration terminée: {len(columns_added)} colonnes Sirene ajoutées")
    else:
        logger.info(f"✅ Toutes les colonnes Sirene existent déjà ({len(columns_already_exist)}/13)")


def run_migrations():
    """Point d'entrée pour exécuter toutes les migrations."""
    try:
        add_sirene_columns_if_needed()
    except Exception as e:
        logger.error(f"❌ Erreur lors des migrations: {e}")
        # Ne pas lever l'exception pour ne pas bloquer le démarrage
        # L'application peut démarrer même si les migrations échouent
