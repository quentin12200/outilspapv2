#!/usr/bin/env python3
"""
Script pour créer les tables manquantes dans la base de données
Usage: python create_missing_tables.py
"""

import sys
import os

# Ajouter le répertoire parent au path pour importer les modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db import engine, Base
from app.models import PasswordResetToken, EmailLog

def create_tables():
    """Crée toutes les tables manquantes dans la base de données"""
    print("🔧 Création des tables manquantes...")

    try:
        # Créer toutes les tables définies dans Base.metadata
        Base.metadata.create_all(bind=engine)
        print("✅ Tables créées avec succès !")

        # Vérifier les tables créées
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        print(f"\n📊 Tables présentes dans la base de données ({len(tables)}):")
        for table in sorted(tables):
            print(f"   - {table}")

        # Vérifier spécifiquement les nouvelles tables
        if 'password_reset_tokens' in tables:
            print("\n✅ Table 'password_reset_tokens' créée")
        else:
            print("\n⚠️  Table 'password_reset_tokens' manquante")

        if 'email_logs' in tables:
            print("✅ Table 'email_logs' créée")
        else:
            print("⚠️  Table 'email_logs' manquante")

    except Exception as e:
        print(f"\n❌ Erreur lors de la création des tables: {e}")
        sys.exit(1)

if __name__ == "__main__":
    create_tables()
