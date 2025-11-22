"""
Script de migration pour ajouter les colonnes de géolocalisation (latitude, longitude)
à la table invitations.

Usage:
    python scripts/migrate_add_geolocation.py
"""

import sqlite3
import os
import sys

# Chemin vers la base de données
# Utilise la variable d'environnement DATABASE_URL ou le chemin par défaut
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./papcse.db")

# Extraire le chemin du fichier SQLite depuis l'URL
if DATABASE_URL.startswith("sqlite:///"):
    DB_PATH = DATABASE_URL.replace("sqlite:///", "")
    # Gérer les chemins relatifs
    if DB_PATH.startswith("./"):
        DB_PATH = os.path.join(os.path.dirname(__file__), "..", DB_PATH[2:])
else:
    # Pour PostgreSQL ou autre, utiliser une approche différente
    print("⚠️ Ce script ne fonctionne qu'avec SQLite")
    print("   Pour PostgreSQL, utilisez Alembic ou un outil de migration approprié")
    sys.exit(1)

# Colonnes à ajouter avec leur type SQL
COLUMNS_TO_ADD = [
    ("latitude", "FLOAT"),
    ("longitude", "FLOAT"),
]


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

    added_columns = []
    skipped_columns = []

    print("\n🔍 Vérification des colonnes de géolocalisation...")

    for column_name, column_type in COLUMNS_TO_ADD:
        if column_exists(cursor, "invitations", column_name):
            print(f"  ✓ Colonne '{column_name}' existe déjà")
            skipped_columns.append(column_name)
        else:
            try:
                cursor.execute(f"ALTER TABLE invitations ADD COLUMN {column_name} {column_type}")
                print(f"  ✅ Colonne '{column_name}' ajoutée ({column_type})")
                added_columns.append(column_name)
            except sqlite3.OperationalError as e:
                print(f"  ❌ Erreur lors de l'ajout de '{column_name}': {e}")

    conn.commit()
    conn.close()

    print("\n" + "=" * 60)
    print("📊 RÉSUMÉ DE LA MIGRATION")
    print("=" * 60)
    print(f"✅ Colonnes ajoutées     : {len(added_columns)}")
    print(f"⏭️  Colonnes déjà présentes : {len(skipped_columns)}")
    print(f"📝 Total vérifié         : {len(COLUMNS_TO_ADD)}")

    if added_columns:
        print("\n🎉 Migration réussie ! Les colonnes suivantes ont été ajoutées :")
        for col in added_columns:
            print(f"   • {col}")
    else:
        print("\n✓ Aucune migration nécessaire, toutes les colonnes existent déjà.")

    print("\n💡 Les colonnes de géolocalisation sont maintenant disponibles pour la cartographie.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ ERREUR : {e}")
        sys.exit(1)
