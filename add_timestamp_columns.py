#!/usr/bin/env python3
"""
Script de migration pour ajouter les colonnes created_at et updated_at à la table invitations
"""

import sqlite3
from datetime import datetime
from pathlib import Path

# Chemin vers la base de données
DB_PATH = Path(__file__).parent / "papcse.db"

# Si pas trouvée, chercher dans le répertoire courant
if not DB_PATH.exists():
    DB_PATH = Path("papcse.db")

# Si toujours pas trouvée, chercher dans app/
if not DB_PATH.exists():
    DB_PATH = Path(__file__).parent / "app" / "papcse.db"

print(f"📊 Migration de la base de données: {DB_PATH}")
print("=" * 60)

if not DB_PATH.exists():
    print(f"❌ Erreur: La base de données {DB_PATH} n'existe pas")
    exit(1)

# Connexion à la base de données
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

try:
    # Vérifier si les colonnes existent déjà
    cursor.execute("PRAGMA table_info(invitations)")
    columns = [row[1] for row in cursor.fetchall()]

    print(f"\n✅ Colonnes actuelles dans 'invitations': {len(columns)} colonnes")

    has_created_at = 'created_at' in columns
    has_updated_at = 'updated_at' in columns

    if has_created_at and has_updated_at:
        print("\n✅ Les colonnes created_at et updated_at existent déjà!")
        print("   Aucune migration nécessaire.")
    else:
        print("\n📝 Colonnes manquantes détectées:")
        if not has_created_at:
            print("   ⚠️  created_at - À créer")
        if not has_updated_at:
            print("   ⚠️  updated_at - À créer")

        # Ajouter created_at si manquante
        if not has_created_at:
            print("\n🔧 Ajout de la colonne 'created_at'...")
            cursor.execute("""
                ALTER TABLE invitations
                ADD COLUMN created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            """)
            print("   ✅ Colonne 'created_at' ajoutée avec succès")

        # Ajouter updated_at si manquante
        if not has_updated_at:
            print("\n🔧 Ajout de la colonne 'updated_at'...")
            cursor.execute("""
                ALTER TABLE invitations
                ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            """)
            print("   ✅ Colonne 'updated_at' ajoutée avec succès")

        # Créer un index sur created_at pour améliorer les performances
        if not has_created_at:
            print("\n🔧 Création de l'index sur 'created_at'...")
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_invitations_created_at
                ON invitations(created_at)
            """)
            print("   ✅ Index créé avec succès")

        # Commiter les changements
        conn.commit()
        print("\n✅ Migration terminée avec succès!")

        # Vérifier le résultat
        cursor.execute("SELECT COUNT(*) FROM invitations")
        count = cursor.fetchone()[0]
        print(f"\n📊 Statistiques:")
        print(f"   • Nombre total d'invitations: {count}")
        print(f"   • Colonnes ajoutées: created_at, updated_at")
        print(f"   • Index créé: idx_invitations_created_at")

except sqlite3.Error as e:
    print(f"\n❌ Erreur lors de la migration: {e}")
    conn.rollback()
    exit(1)

finally:
    conn.close()
    print("\n" + "=" * 60)
    print("✅ Connexion fermée")

print("\n🎉 Base de données mise à jour avec succès!")
print("   Vous pouvez maintenant redémarrer l'application.")
