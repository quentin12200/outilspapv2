#!/usr/bin/env python3
"""
Script pour vérifier les tables disponibles dans la base de données.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, inspect

# Connexion à la base de données
db_path = Path(__file__).parent.parent / "papcse.db"
engine = create_engine(f'sqlite:///{db_path}')

# Inspecter les tables
inspector = inspect(engine)
tables = inspector.get_table_names()

print("=" * 80)
print("TABLES DISPONIBLES DANS LA BASE DE DONNÉES")
print("=" * 80)
print()

if not tables:
    print("❌ Aucune table trouvée dans la base de données")
else:
    print(f"✓ {len(tables)} table(s) trouvée(s):")
    print()
    for table in sorted(tables):
        print(f"  • {table}")

        # Afficher les colonnes de chaque table
        columns = inspector.get_columns(table)
        if columns:
            print("    Colonnes:")
            for col in columns[:10]:  # Limiter à 10 colonnes
                print(f"      - {col['name']} ({col['type']})")
            if len(columns) > 10:
                print(f"      ... et {len(columns) - 10} autres colonnes")
        print()
