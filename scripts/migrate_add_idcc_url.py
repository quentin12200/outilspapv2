"""
Script de migration pour ajouter la colonne idcc_url (URL Legifrance)
à la table invitations.

Usage:
    python scripts/migrate_add_idcc_url.py
"""

import sqlite3
import os
import sys

# Chemin vers la base de données
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "pap.db")

# Colonne à ajouter
COLUMN_NAME = "idcc_url"
COLUMN_TYPE = "TEXT"


def column_exists(cursor, table_name, column_name):
    """Vérifie si une colonne existe dans une table"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns


def main():
    if not os.path.exists(DB_PATH):
        print(f"❌ Base de données non trouvée : {DB_PATH}")
        print("   La base sera créée automatiquement au premier démarrage de l'application.")
        return

    print(f"📦 Connexion à la base de données : {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("\n🔍 Vérification de la colonne idcc_url...")

    if column_exists(cursor, "invitations", COLUMN_NAME):
        print(f"  ✓ Colonne '{COLUMN_NAME}' existe déjà")
        print("\n✓ Aucune migration nécessaire.")
    else:
        try:
            cursor.execute(f"ALTER TABLE invitations ADD COLUMN {COLUMN_NAME} {COLUMN_TYPE}")
            conn.commit()
            print(f"  ✅ Colonne '{COLUMN_NAME}' ajoutée ({COLUMN_TYPE})")
            print("\n🎉 Migration réussie !")
            print(f"\n💡 La colonne '{COLUMN_NAME}' est maintenant disponible.")
            print("   Elle sera remplie lors du prochain enrichissement IDCC.")
        except sqlite3.OperationalError as e:
            print(f"  ❌ Erreur lors de l'ajout de '{COLUMN_NAME}': {e}")
            conn.close()
            sys.exit(1)

    conn.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ ERREUR : {e}")
        sys.exit(1)
