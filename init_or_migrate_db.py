#!/usr/bin/env python3
"""
Script pour initialiser ou migrer la base de données
- Si la DB n'existe pas: crée toutes les tables avec les bonnes colonnes
- Si la DB existe: ajoute les colonnes manquantes (migration)
"""

import sys
from pathlib import Path

# Ajouter le répertoire parent au path pour importer app
sys.path.insert(0, str(Path(__file__).parent))

from app.db import engine, Base
from app.models import Invitation
import sqlite3
from sqlalchemy import inspect

print("🚀 Initialisation/Migration de la base de données")
print("=" * 60)

# Récupérer le chemin de la base de données depuis l'engine
db_url = str(engine.url)
if db_url.startswith("sqlite:///"):
    db_path = db_url.replace("sqlite:///", "")
    if db_path.startswith("./"):
        db_path = db_path[2:]
    print(f"📍 Base de données: {db_path}")
else:
    print(f"📍 Base de données: {db_url}")

# Vérifier si la base existe
db_file = Path(db_path) if db_url.startswith("sqlite:///") else None
db_exists = db_file.exists() if db_file else True

if not db_exists:
    print("\n✨ Nouvelle base de données - Création de toutes les tables...")
    # Créer toutes les tables
    Base.metadata.create_all(bind=engine)
    print("✅ Toutes les tables ont été créées avec succès!")
else:
    print("\n📊 Base de données existante - Vérification des colonnes...")

    # Utiliser l'inspecteur SQLAlchemy
    inspector = inspect(engine)

    # Vérifier la table invitations
    if 'invitations' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('invitations')]
        print(f"   Colonnes actuelles: {len(columns)}")

        has_created_at = 'created_at' in columns
        has_updated_at = 'updated_at' in columns

        if has_created_at and has_updated_at:
            print("   ✅ created_at: OK")
            print("   ✅ updated_at: OK")
            print("\n✅ Aucune migration nécessaire - Base de données à jour!")
        else:
            print("\n⚠️  Colonnes manquantes détectées:")
            if not has_created_at:
                print("   ❌ created_at: MANQUANTE")
            if not has_updated_at:
                print("   ❌ updated_at: MANQUANTE")

            print("\n🔧 Migration en cours...")

            # Connexion directe SQLite pour les ALTER TABLE
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            try:
                if not has_created_at:
                    print("   Ajout de created_at...")
                    cursor.execute("""
                        ALTER TABLE invitations
                        ADD COLUMN created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                    """)

                if not has_updated_at:
                    print("   Ajout de updated_at...")
                    cursor.execute("""
                        ALTER TABLE invitations
                        ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    """)

                # Créer l'index
                if not has_created_at:
                    print("   Création de l'index idx_invitations_created_at...")
                    cursor.execute("""
                        CREATE INDEX IF NOT EXISTS idx_invitations_created_at
                        ON invitations(created_at)
                    """)

                conn.commit()
                print("\n✅ Migration terminée avec succès!")

            except sqlite3.Error as e:
                print(f"\n❌ Erreur lors de la migration: {e}")
                conn.rollback()
                sys.exit(1)
            finally:
                conn.close()
    else:
        print("\n⚠️  Table 'invitations' non trouvée - Création de toutes les tables...")
        Base.metadata.create_all(bind=engine)
        print("✅ Toutes les tables ont été créées avec succès!")

# Vérification finale
print("\n" + "=" * 60)
print("🔍 Vérification finale...")
inspector = inspect(engine)

if 'invitations' in inspector.get_table_names():
    columns = [col['name'] for col in inspector.get_columns('invitations')]
    print(f"✅ Table 'invitations': {len(columns)} colonnes")

    # Afficher les colonnes importantes
    important_cols = ['id', 'siret', 'created_at', 'updated_at']
    for col in important_cols:
        status = "✅" if col in columns else "❌"
        print(f"   {status} {col}")

print("\n" + "=" * 60)
print("🎉 Base de données prête à l'emploi!")
print("\n💡 Vous pouvez maintenant démarrer l'application:")
print("   uvicorn app.main:app --reload")
