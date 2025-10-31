#!/usr/bin/env python3
"""
Script de diagnostic pour comprendre pourquoi certaines colonnes
ne s'affichent pas après l'import.

Ce script affiche :
1. Les dernières invitations importées
2. Le contenu du champ 'raw' (toutes les colonnes de l'Excel)
3. Les colonnes structurées effectivement remplies
4. Les noms de colonnes de votre Excel qui N'ONT PAS été reconnus

Usage:
    python scripts/diagnose_import.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.models import Invitation
from app.config import DATABASE_URL

print("=" * 80)
print("🔍 DIAGNOSTIC DES COLONNES INVITATIONS")
print("=" * 80)

engine = create_engine(DATABASE_URL)
session = Session(bind=engine)

# Récupérer les 5 dernières invitations (les plus récentes importées)
invitations = session.query(Invitation).order_by(Invitation.id.desc()).limit(5).all()

if not invitations:
    print("❌ Aucune invitation trouvée dans la base !")
    sys.exit(1)

print(f"\n📊 Analyse des {len(invitations)} dernières invitations importées\n")
print("=" * 80)

for i, inv in enumerate(invitations, 1):
    print(f"\n{'='*80}")
    print(f"INVITATION #{i} - SIRET: {inv.siret}")
    print(f"{'='*80}")

    # Afficher les colonnes structurées
    print("\n✅ COLONNES STRUCTURÉES (ce qui devrait s'afficher) :")
    print(f"  • Denomination        : {inv.denomination or '❌ VIDE'}")
    print(f"  • Enseigne            : {inv.enseigne or '❌ VIDE'}")
    print(f"  • Adresse             : {inv.adresse or '❌ VIDE'}")
    print(f"  • Commune (Ville)     : {inv.commune or '❌ VIDE'}")
    print(f"  • Code postal         : {inv.code_postal or '❌ VIDE'}")
    print(f"  • Activité principale : {inv.activite_principale or '❌ VIDE'}")
    print(f"  • Libellé activité    : {inv.libelle_activite or '❌ VIDE'}")
    print(f"  • Effectifs label     : {inv.effectifs_label or '❌ VIDE'}")
    print(f"  • Tranche effectifs   : {inv.tranche_effectifs or '❌ VIDE'}")
    print(f"  • Catégorie entreprise: {inv.categorie_entreprise or '❌ VIDE'}")
    print(f"  • Est actif           : {inv.est_actif if inv.est_actif is not None else '❌ VIDE'}")
    print(f"  • Est siège           : {inv.est_siege if inv.est_siege is not None else '❌ VIDE'}")
    print(f"  • Source              : {inv.source or '❌ VIDE'}")
    print(f"  • Date invitation     : {inv.date_invit or '❌ VIDE'}")

    # Afficher le contenu de raw
    print("\n📋 CONTENU DU CHAMP 'raw' (colonnes de votre Excel) :")
    if inv.raw:
        print(f"  Nombre de colonnes trouvées : {len(inv.raw)}")
        print(f"\n  Détail des colonnes :")
        for key, value in inv.raw.items():
            # Tronquer les valeurs longues
            display_value = str(value)[:50] + "..." if len(str(value)) > 50 else str(value)
            print(f"    • {key:30s} = {display_value}")
    else:
        print("  ❌ VIDE (aucune colonne trouvée dans l'Excel)")

    # Vérifier quelles colonnes auraient dû être mappées
    if inv.raw:
        print("\n🔍 ANALYSE DES COLONNES NON RECONNUES :")

        # Colonnes attendues pour chaque champ
        mapping = {
            "Denomination (Raison sociale)": ["denomination", "denomination_usuelle", "raison_sociale", "raison_sociale_etablissement", "nom_raison_sociale", "rs", "nom"],
            "Enseigne": ["enseigne", "enseigne_commerciale", "enseigne_commerciale"],
            "Adresse": ["adresse_complete", "adresse", "adresse_ligne_1", "adresse_ligne1", "adresse1", "adresse_postale", "ligne_4", "ligne4", "libelle_voie"],
            "Code postal": ["code_postal", "code_postal_etablissement", "cp"],
            "Ville": ["commune", "ville", "localite", "libelle_commune_etablissement", "adresse_ville"],
            "Activité": ["activite_principale", "code_naf", "naf", "code_ape", "ape"],
            "Libellé activité": ["libelle_activite", "libelle_naf", "activite", "activite_principale_libelle"],
            "Effectifs": ["effectifs", "effectif", "effectifs_salaries", "effectifs_categorie"],
            "Tranche effectifs": ["tranche_effectifs", "tranche_effectif", "tranche_effectifs_salaries", "tranche_effectif_salarie"],
            "Catégorie": ["categorie_entreprise", "categorie", "taille_entreprise", "taille"],
        }

        # Colonnes dans raw non utilisées
        raw_keys = set(inv.raw.keys())
        recognized_keys = set()

        for field_name, expected_keys in mapping.items():
            found = False
            for key in expected_keys:
                if key in raw_keys:
                    recognized_keys.add(key)
                    found = True
                    break

            if not found:
                # Chercher des colonnes similaires dans raw
                similar = [k for k in raw_keys if any(exp in k or k in exp for exp in expected_keys)]
                if similar:
                    print(f"\n  ⚠️  {field_name} est VIDE mais j'ai trouvé : {similar}")
                    print(f"      Colonnes attendues : {', '.join(expected_keys[:3])}...")

        # Colonnes non reconnues du tout
        unrecognized = raw_keys - recognized_keys - {'siret', 'date', 'date_pap', 'date_invitation', 'source', 'origine', 'canal'}
        if unrecognized:
            print(f"\n  ℹ️  Colonnes dans votre Excel NON UTILISÉES :")
            for key in sorted(unrecognized):
                print(f"      • {key} = {inv.raw[key][:50] if len(str(inv.raw[key])) > 50 else inv.raw[key]}")

print("\n" + "=" * 80)
print("📝 RÉSUMÉ ET RECOMMANDATIONS")
print("=" * 80)

# Compter les colonnes vides globalement
total_invitations = len(invitations)
stats = {
    "denomination_vide": sum(1 for inv in invitations if not inv.denomination),
    "enseigne_vide": sum(1 for inv in invitations if not inv.enseigne),
    "adresse_vide": sum(1 for inv in invitations if not inv.adresse),
    "commune_vide": sum(1 for inv in invitations if not inv.commune),
    "code_postal_vide": sum(1 for inv in invitations if not inv.code_postal),
}

print(f"\nSur les {total_invitations} dernières invitations :")
print(f"  • Raison sociale vide : {stats['denomination_vide']}/{total_invitations}")
print(f"  • Enseigne vide       : {stats['enseigne_vide']}/{total_invitations}")
print(f"  • Adresse vide        : {stats['adresse_vide']}/{total_invitations}")
print(f"  • Ville vide          : {stats['commune_vide']}/{total_invitations}")
print(f"  • Code postal vide    : {stats['code_postal_vide']}/{total_invitations}")

print("\n💡 SOLUTIONS :")

if invitations[0].raw:
    print("\n1. Vérifier les noms de colonnes de votre Excel")
    print("   → Voir ci-dessus les colonnes NON RECONNUES")
    print("   → Renommer les colonnes dans Excel pour correspondre aux noms attendus")
    print("")
    print("2. Réimporter le fichier Excel après avoir renommé les colonnes")
    print("   → Aller sur /admin")
    print("   → Section 'Importer Invitations PAP'")
    print("")
    print("3. OU utiliser la migration pour remplir depuis raw")
    print("   → railway run python scripts/migrate_and_fix_invitations.py")
else:
    print("\n❌ PROBLÈME : Le champ 'raw' est vide !")
    print("   Cela signifie que TOUTES les colonnes de votre Excel sont vides ou NULL")
    print("   → Vérifier que votre fichier Excel contient bien des données")
    print("   → Réimporter un fichier Excel avec des données")

print("\n" + "=" * 80)
print("✅ Diagnostic terminé")
print("=" * 80)

session.close()
