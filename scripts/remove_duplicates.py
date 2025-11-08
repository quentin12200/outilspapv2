#!/usr/bin/env python3
"""
Script pour supprimer les doublons d'invitations.
Garde seulement l'invitation la plus récente pour chaque SIRET.

Usage:
    python scripts/remove_duplicates.py
    python scripts/remove_duplicates.py --by-date  # Garde la date la plus récente
    python scripts/remove_duplicates.py --by-id    # Garde l'ID le plus élevé (défaut)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session
from app.models import Invitation
from app.config import DATABASE_URL

print("\n" + "="*80)
print("🧹 SUPPRESSION DES DOUBLONS D'INVITATIONS")
print("="*80 + "\n")

# Vérifier les arguments
by_date = "--by-date" in sys.argv
by_id = "--by-id" in sys.argv or not by_date  # Par défaut

if by_date:
    print("📅 Mode : Garder l'invitation avec la date la plus RÉCENTE pour chaque SIRET")
else:
    print("🆔 Mode : Garder l'invitation avec l'ID le plus ÉLEVÉ pour chaque SIRET")
    print("   (l'ID le plus élevé = la dernière importée)")

engine = create_engine(DATABASE_URL)
session = Session(bind=engine)

# Statistiques avant
total_before = session.query(Invitation).count()
unique_sirets = session.query(func.count(func.distinct(Invitation.siret))).scalar()
duplicates = total_before - unique_sirets

print(f"\n📊 État actuel :")
print(f"  • Total invitations : {total_before}")
print(f"  • SIRET uniques     : {unique_sirets}")
print(f"  • Doublons          : {duplicates}")

if duplicates == 0:
    print("\n✅ Aucun doublon à supprimer !")
    session.close()
    sys.exit(0)

print(f"\n⚠️  Je vais supprimer {duplicates} doublons...")
input("\n⏸️  Appuyez sur ENTRÉE pour continuer (ou Ctrl+C pour annuler)...")

# Trouver les IDs à GARDER
print("\n🔍 Recherche des invitations à conserver...")

if by_date:
    # Garder l'invitation avec la date la plus récente pour chaque SIRET
    # Subquery pour trouver la date max par SIRET
    subq = session.query(
        Invitation.siret,
        func.max(Invitation.date_invit).label('max_date')
    ).group_by(Invitation.siret).subquery()

    # Trouver les IDs à garder
    ids_to_keep = session.query(Invitation.id).join(
        subq,
        (Invitation.siret == subq.c.siret) & (Invitation.date_invit == subq.c.max_date)
    ).all()

else:  # by_id
    # Garder l'invitation avec l'ID le plus élevé pour chaque SIRET
    # Subquery pour trouver l'ID max par SIRET
    subq = session.query(
        Invitation.siret,
        func.max(Invitation.id).label('max_id')
    ).group_by(Invitation.siret).subquery()

    # Trouver les IDs à garder
    ids_to_keep = session.query(Invitation.id).join(
        subq,
        Invitation.id == subq.c.max_id
    ).all()

# Convertir en set pour recherche rapide
ids_to_keep_set = {id_tuple[0] for id_tuple in ids_to_keep}

print(f"✅ {len(ids_to_keep_set)} invitations seront conservées")
print(f"❌ {total_before - len(ids_to_keep_set)} invitations seront supprimées")

# Supprimer les doublons
print("\n🗑️  Suppression en cours...")

deleted = session.query(Invitation).filter(
    ~Invitation.id.in_(ids_to_keep_set)
).delete(synchronize_session=False)

session.commit()

print(f"✅ {deleted} doublons supprimés")

# Statistiques après
total_after = session.query(Invitation).count()
unique_sirets_after = session.query(func.count(func.distinct(Invitation.siret))).scalar()

print(f"\n📊 État après nettoyage :")
print(f"  • Total invitations : {total_after}")
print(f"  • SIRET uniques     : {unique_sirets_after}")
print(f"  • Doublons restants : {total_after - unique_sirets_after}")

# Vérification
if total_after - unique_sirets_after > 0:
    print("\n⚠️  ATTENTION : Il reste des doublons !")
    print("   Cela peut arriver si plusieurs invitations ont la même date/ID max.")
    print("   Relancez le script pour les supprimer.")
else:
    print("\n✅ Parfait ! Plus aucun doublon.")

print("\n" + "="*80)
print("✅ Nettoyage terminé")
print("="*80)
print("\n💡 Prochaines étapes :")
print("  1. Vérifier sur /invitations que tout est correct")
print("  2. Ne plus réimporter le même fichier plusieurs fois")
print("  3. Pour ajouter de nouvelles invitations, importer seulement les nouvelles lignes")
print("\n")

session.close()
