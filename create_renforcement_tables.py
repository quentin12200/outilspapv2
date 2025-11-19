#!/usr/bin/env python3
"""
Script pour créer les tables de renforcement syndical (cartographie et rétro-planning)
Usage: python create_renforcement_tables.py
"""

import sys
import os

# Ajouter le répertoire parent au path pour importer les modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db import engine, Base
from app.models import Cartographie, ServiceCartographie, Retroplanning, PhaseRetroplanning

def create_tables():
    """Crée les tables de renforcement syndical dans la base de données"""
    print("🔧 Création des tables de renforcement syndical...")

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
        expected_tables = [
            'cartographies',
            'services_cartographie',
            'retroplannings',
            'phases_retroplanning'
        ]

        print("\n🔍 Vérification des tables de renforcement:")
        for table_name in expected_tables:
            if table_name in tables:
                print(f"✅ Table '{table_name}' créée")
            else:
                print(f"⚠️  Table '{table_name}' manquante")

    except Exception as e:
        print(f"\n❌ Erreur lors de la création des tables: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    create_tables()
