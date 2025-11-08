#!/usr/bin/env python3
"""
Script pour diagnostiquer les doublons dans les invitations.

Usage:
    python scripts/check_duplicates.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session
from app.models import Invitation
from app.config import DATABASE_URL
from collections import Counter

print("\n" + "="*80)
print("🔍 DIAGNOSTIC DES DOUBLONS DANS LES INVITATIONS")
print("="*80 + "\n")

engine = create_engine(DATABASE_URL)
session = Session(bind=engine)

# Compter le total
total = session.query(Invitation).count()
print(f"📊 Total d'invitations dans la base : {total}")

# Compter les SIRET uniques
unique_sirets = session.query(func.count(func.distinct(Invitation.siret))).scalar()
print(f"🔢 Nombre de SIRET uniques : {unique_sirets}")

# Calculer le nombre de doublons
duplicates = total - unique_sirets
print(f"⚠️  Nombre de doublons : {duplicates}")

if duplicates > 0:
    print(f"\n❌ ATTENTION : Vous avez {duplicates} doublons !")
    print(f"   Vous avez importé {total} lignes au total")
    print(f"   Mais seulement {unique_sirets} SIRET différents")
    print(f"   → Les données ont été importées {total // unique_sirets if unique_sirets > 0 else 0} fois en moyenne")

# Compter par source
print(f"\n📋 Répartition par source :")
sources = session.query(
    Invitation.source,
    func.count(Invitation.id)
).group_by(Invitation.source).all()

for source, count in sources:
    print(f"  • {source or 'Sans source':30s} : {count:5d} invitations")

# Trouver les SIRET avec le plus de doublons
print(f"\n🔍 Top 10 des SIRET avec le plus de doublons :")
duplicated_sirets = session.query(
    Invitation.siret,
    func.count(Invitation.id).label('count')
).group_by(Invitation.siret).having(func.count(Invitation.id) > 1).order_by(func.count(Invitation.id).desc()).limit(10).all()

if duplicated_sirets:
    for siret, count in duplicated_sirets:
        print(f"  • SIRET {siret} : {count} fois")

        # Montrer les dates d'import
        dates = session.query(Invitation.date_invit).filter(Invitation.siret == siret).all()
        dates_str = ", ".join([str(d[0]) for d in dates[:3]])
        if len(dates) > 3:
            dates_str += f" ... (+{len(dates)-3})"
        print(f"    Dates : {dates_str}")
else:
    print("  ✅ Aucun doublon trouvé")

# Compter par date d'import (ID proche = import en même temps)
print(f"\n📅 Répartition approximative par import :")
print("    (basé sur les ranges d'IDs)")

# Récupérer min et max ID
min_id = session.query(func.min(Invitation.id)).scalar() or 0
max_id = session.query(func.max(Invitation.id)).scalar() or 0

# Diviser en tranches de ~1000
chunk_size = 1000
current_id = min_id
import_num = 1

while current_id <= max_id:
    next_id = current_id + chunk_size
    count_in_range = session.query(Invitation).filter(
        Invitation.id >= current_id,
        Invitation.id < next_id
    ).count()

    if count_in_range > 0:
        # Récupérer une invitation de cette tranche pour voir la date
        sample = session.query(Invitation).filter(
            Invitation.id >= current_id,
            Invitation.id < next_id
        ).first()

        print(f"  Import #{import_num} (IDs {current_id}-{next_id-1}) : {count_in_range} invitations")
        if sample:
            print(f"    Exemple : SIRET {sample.siret}, Date: {sample.date_invit}, Source: {sample.source}")

        import_num += 1

    current_id = next_id

print("\n" + "="*80)
print("💡 SOLUTIONS")
print("="*80)

if duplicates > 0:
    print("\n❌ Vous avez des doublons. Voici comment les supprimer :\n")

    print("Option 1 : TOUT SUPPRIMER et réimporter proprement")
    print("-" * 80)
    print("railway run python")
    print(">>> from app.db import SessionLocal")
    print(">>> from app.models import Invitation")
    print(">>> session = SessionLocal()")
    print(">>> session.query(Invitation).delete()")
    print(f">>> # Cela va supprimer {total} invitations")
    print(">>> session.commit()")
    print(">>> exit()")
    print("\nPuis réimporter votre fichier Excel UNE SEULE FOIS sur /admin\n")

    print("Option 2 : Garder seulement les plus récentes (par ID)")
    print("-" * 80)
    print("railway run python scripts/remove_duplicates.py")
    print(f"# Cela gardera {unique_sirets} invitations (les plus récentes)")
    print(f"# Et supprimera {duplicates} doublons\n")

    print("Option 3 : Garder seulement les plus récentes (par date)")
    print("-" * 80)
    print("railway run python scripts/remove_duplicates.py --by-date")
    print("# Garde l'invitation avec la date la plus récente pour chaque SIRET\n")

else:
    print("\n✅ Pas de doublons ! Votre base est propre.")
    print(f"   Vous avez {total} invitations uniques.")

print("\n" + "="*80)
print("✅ Diagnostic terminé")
print("="*80 + "\n")

session.close()
