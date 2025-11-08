#!/usr/bin/env python3
"""
Script RAPIDE pour voir les noms de colonnes dans votre base de données.
Affiche les 3 premières invitations et TOUS les noms de colonnes Excel.

Usage:
    python scripts/quick_check_columns.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.models import Invitation
from app.config import DATABASE_URL

print("\n" + "="*80)
print("📋 NOMS DES COLONNES DANS VOTRE FICHIER EXCEL")
print("="*80 + "\n")

engine = create_engine(DATABASE_URL)
session = Session(bind=engine)

# Récupérer les 3 dernières invitations
invitations = session.query(Invitation).order_by(Invitation.id.desc()).limit(3).all()

if not invitations:
    print("❌ Aucune invitation trouvée !")
    sys.exit(1)

print(f"📊 Analyse des {len(invitations)} dernières invitations\n")

for i, inv in enumerate(invitations, 1):
    print(f"\n{'─'*80}")
    print(f"INVITATION #{i} - SIRET: {inv.siret}")
    print(f"{'─'*80}")

    if inv.raw:
        print(f"\n✅ Colonnes dans votre Excel ({len(inv.raw)} colonnes) :")

        # Afficher toutes les colonnes avec leurs valeurs
        for key in sorted(inv.raw.keys()):
            value = inv.raw[key]
            # Tronquer si trop long
            if value and len(str(value)) > 60:
                display = str(value)[:60] + "..."
            else:
                display = value or "(vide)"

            print(f"  • {key:30s} → {display}")
    else:
        print("\n❌ Aucune colonne 'raw' (Excel vide ?)")

    # Afficher ce qui a été reconnu
    print(f"\n📝 Ce qui a été reconnu par le système :")
    print(f"  • Raison sociale : {inv.denomination or '❌ NON'}")
    print(f"  • Adresse        : {inv.adresse or '❌ NON'}")
    print(f"  • Ville          : {inv.commune or '❌ NON'}")
    print(f"  • Code postal    : {inv.code_postal or '❌ NON'}")
    print(f"  • Effectifs      : {inv.effectifs_label or '❌ NON'}")
    print(f"  • Enseigne       : {inv.enseigne or '❌ NON'}")

print("\n" + "="*80)
print("💡 INSTRUCTIONS")
print("="*80)
print("\n1. Regardez les noms de colonnes ci-dessus")
print("2. Comparez avec ce que le système a reconnu")
print("3. Envoyez-moi les noms EXACTS des colonnes qui manquent")
print("\nPar exemple :")
print('  - Si vous voyez "adresse_complete" → OK, déjà supporté')
print('  - Si vous voyez "adresse_etablissement" → Pas supporté, envoyez-moi ce nom')
print('  - Si vous voyez "effectif_salarie" → Pas supporté, envoyez-moi ce nom')
print("\n")

session.close()
