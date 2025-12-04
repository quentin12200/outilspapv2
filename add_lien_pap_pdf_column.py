"""
Migration: Ajout des colonnes lien_pap_pdf et date_courrier à la table invitations

- lien_pap_pdf: Lien permanent vers le PDF scanné du PAP
- date_courrier: Date du courrier d'invitation (distincte de date_invit pour éviter confusion)

Usage:
    python add_lien_pap_pdf_column.py
"""

import sqlite3
import os
from datetime import datetime

# Chemin vers la base de données
DB_PATH = os.getenv("DATABASE_URL", "sqlite:///./papcse.db").replace("sqlite:///", "")

def add_lien_pap_pdf_column():
    """Ajoute les colonnes lien_pap_pdf et date_courrier à la table invitations si elles n'existent pas"""

    print(f"📊 Migration: Ajout des colonnes lien_pap_pdf et date_courrier")
    print(f"   Base de données: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        print(f"❌ Erreur: Base de données introuvable: {DB_PATH}")
        return False

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Vérifier quelles colonnes existent déjà
        cursor.execute("PRAGMA table_info(invitations)")
        existing_columns = [row[1] for row in cursor.fetchall()]

        columns_to_add = []
        if 'lien_pap_pdf' not in existing_columns:
            columns_to_add.append(('lien_pap_pdf', 'TEXT'))
        else:
            print("✅ La colonne lien_pap_pdf existe déjà")

        if 'date_courrier' not in existing_columns:
            columns_to_add.append(('date_courrier', 'DATE'))
        else:
            print("✅ La colonne date_courrier existe déjà")

        if not columns_to_add:
            print("✅ Toutes les colonnes existent déjà")
            conn.close()
            return True

        # Ajouter les colonnes manquantes
        for col_name, col_type in columns_to_add:
            print(f"➕ Ajout de la colonne {col_name}...")
            cursor.execute(f"""
                ALTER TABLE invitations
                ADD COLUMN {col_name} {col_type}
            """)

        conn.commit()

        # Vérifier que les colonnes ont bien été ajoutées
        cursor.execute("PRAGMA table_info(invitations)")
        final_columns = [row[1] for row in cursor.fetchall()]

        all_added = True
        for col_name, _ in columns_to_add:
            if col_name in final_columns:
                print(f"✅ Colonne {col_name} ajoutée avec succès")
            else:
                print(f"❌ Erreur: La colonne {col_name} n'a pas été ajoutée")
                all_added = False

        if all_added:
            # Compter le nombre d'invitations
            cursor.execute("SELECT COUNT(*) FROM invitations")
            count = cursor.fetchone()[0]
            print(f"   {count} invitations dans la table")

        conn.close()
        return all_added

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
