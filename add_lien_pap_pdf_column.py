"""
Migration: Ajout de la colonne lien_pap_pdf à la table invitations

Cette colonne stockera le lien permanent vers le PDF scanné du PAP
pour chaque invitation.

Usage:
    python add_lien_pap_pdf_column.py
"""

import sqlite3
import os
from datetime import datetime

# Chemin vers la base de données
DB_PATH = os.getenv("DATABASE_URL", "sqlite:///./papcse.db").replace("sqlite:///", "")

def add_lien_pap_pdf_column():
    """Ajoute la colonne lien_pap_pdf à la table invitations si elle n'existe pas"""

    print(f"📊 Migration: Ajout de la colonne lien_pap_pdf")
    print(f"   Base de données: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        print(f"❌ Erreur: Base de données introuvable: {DB_PATH}")
        return False

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Vérifier si la colonne existe déjà
        cursor.execute("PRAGMA table_info(invitations)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'lien_pap_pdf' in columns:
            print("✅ La colonne lien_pap_pdf existe déjà")
            conn.close()
            return True

        # Ajouter la colonne
        print("➕ Ajout de la colonne lien_pap_pdf...")
        cursor.execute("""
            ALTER TABLE invitations
            ADD COLUMN lien_pap_pdf TEXT
        """)

        conn.commit()

        # Vérifier que la colonne a bien été ajoutée
        cursor.execute("PRAGMA table_info(invitations)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'lien_pap_pdf' in columns:
            print("✅ Colonne lien_pap_pdf ajoutée avec succès")

            # Compter le nombre d'invitations
            cursor.execute("SELECT COUNT(*) FROM invitations")
            count = cursor.fetchone()[0]
            print(f"   {count} invitations dans la table")

            conn.close()
            return True
        else:
            print("❌ Erreur: La colonne n'a pas été ajoutée")
            conn.close()
            return False

    except Exception as e:
        print(f"❌ Erreur lors de la migration: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Migration: Ajout colonne lien_pap_pdf")
    print("=" * 60)
    print()

    success = add_lien_pap_pdf_column()

    print()
    if success:
        print("✅ Migration terminée avec succès")
    else:
        print("❌ Migration échouée")
    print("=" * 60)
