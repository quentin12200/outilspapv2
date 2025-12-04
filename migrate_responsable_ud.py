#!/usr/bin/env python3
"""
Script de migration pour ajouter la colonne responsable_ud
à la table tableaux_bord_ud
"""

import sqlite3
import os
import sys

def migrate():
    # Chemin vers la base de données
    DB_PATH = os.getenv("DATABASE_URL", "sqlite:///./papcse.db").replace("sqlite:///", "")

    if not os.path.exists(DB_PATH):
        print(f"❌ Base de données introuvable: {DB_PATH}")
        sys.exit(1)

    print(f"📂 Base de données: {DB_PATH}")

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Vérifier si la colonne existe déjà
        cursor.execute("PRAGMA table_info(tableaux_bord_ud)")
        existing_columns = [row[1] for row in cursor.fetchall()]

        if 'responsable_ud' in existing_columns:
            print("✅ La colonne responsable_ud existe déjà !")
            cursor.execute("SELECT COUNT(*) FROM tableaux_bord_ud")
            count = cursor.fetchone()[0]
            print(f"📊 {count} tableaux UD dans la base")
            conn.close()
            return

        # Ajouter la colonne
        print("➕ Ajout de la colonne responsable_ud...")
        cursor.execute("ALTER TABLE tableaux_bord_ud ADD COLUMN responsable_ud VARCHAR(255)")
        conn.commit()

        # Vérifier
        cursor.execute("PRAGMA table_info(tableaux_bord_ud)")
        final_columns = [row[1] for row in cursor.fetchall()]

        if 'responsable_ud' not in final_columns:
            print("❌ Erreur: La colonne n'a pas été ajoutée")
            sys.exit(1)

        cursor.execute("SELECT COUNT(*) FROM tableaux_bord_ud")
        count = cursor.fetchone()[0]

        conn.close()

        print("✅ Migration réussie !")
        print(f"📊 {count} tableaux UD dans la base")
        print("\n🎯 Vous pouvez maintenant:")
        print("   1. Retourner sur /admin")
        print("   2. Rafraîchir la page (F5)")
        print("   3. Cliquer sur 'Importer depuis JSON'")

    except Exception as e:
        print(f"❌ Erreur: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("🔧 Migration de la colonne responsable_ud")
    print("=" * 50)
    migrate()
