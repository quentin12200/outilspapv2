#!/usr/bin/env python3
"""
Script de diagnostic et migration pour remplir les colonnes invitations.

Ce script :
1. Diagnostique l'état actuel de la table invitations
2. Remplit les colonnes structurées depuis le champ raw
3. Si raw est NULL, tente d'utiliser d'autres sources
4. Affiche un rapport détaillé

Usage:
    python scripts/migrate_and_fix_invitations.py

    # Ou depuis le répertoire racine :
    python -m scripts.migrate_and_fix_invitations
"""

import sys
import os

# Ajouter le répertoire parent au path pour importer app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unicodedata
import re
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session
from app.models import Invitation
from app.config import DATABASE_URL

print("=" * 80)
print("📊 DIAGNOSTIC ET MIGRATION - TABLE INVITATIONS")
print("=" * 80)
print(f"\n🔗 Connexion à la base : {DATABASE_URL}\n")

# Créer la connexion
engine = create_engine(DATABASE_URL)
session = Session(bind=engine)

# ============================================================================
# ÉTAPE 1 : DIAGNOSTIC
# ============================================================================

print("🔍 ÉTAPE 1 : DIAGNOSTIC DE LA TABLE INVITATIONS")
print("-" * 80)

# Vérifier que la table existe
inspector = inspect(engine)
if "invitations" not in inspector.get_table_names():
    print("❌ ERREUR : La table 'invitations' n'existe pas !")
    sys.exit(1)

# Récupérer toutes les invitations
total = session.query(Invitation).count()
print(f"📋 Total d'invitations dans la table : {total}")

if total == 0:
    print("⚠️  Aucune invitation dans la table. Rien à migrer.")
    sys.exit(0)

# Compter les invitations avec colonnes NULL
stats = {
    "denomination_null": session.query(Invitation).filter(Invitation.denomination.is_(None)).count(),
    "enseigne_null": session.query(Invitation).filter(Invitation.enseigne.is_(None)).count(),
    "adresse_null": session.query(Invitation).filter(Invitation.adresse.is_(None)).count(),
    "commune_null": session.query(Invitation).filter(Invitation.commune.is_(None)).count(),
    "code_postal_null": session.query(Invitation).filter(Invitation.code_postal.is_(None)).count(),
    "activite_principale_null": session.query(Invitation).filter(Invitation.activite_principale.is_(None)).count(),
    "raw_null": session.query(Invitation).filter(Invitation.raw.is_(None)).count(),
    "raw_not_null": session.query(Invitation).filter(Invitation.raw.isnot(None)).count(),
}

print("\n📊 État des colonnes :")
print(f"  • Denomination NULL     : {stats['denomination_null']}/{total} ({stats['denomination_null']*100//total if total > 0 else 0}%)")
print(f"  • Enseigne NULL         : {stats['enseigne_null']}/{total} ({stats['enseigne_null']*100//total if total > 0 else 0}%)")
print(f"  • Adresse NULL          : {stats['adresse_null']}/{total} ({stats['adresse_null']*100//total if total > 0 else 0}%)")
print(f"  • Commune NULL          : {stats['commune_null']}/{total} ({stats['commune_null']*100//total if total > 0 else 0}%)")
print(f"  • Code postal NULL      : {stats['code_postal_null']}/{total} ({stats['code_postal_null']*100//total if total > 0 else 0}%)")
print(f"  • Activité NULL         : {stats['activite_principale_null']}/{total} ({stats['activite_principale_null']*100//total if total > 0 else 0}%)")
print(f"  • Champ raw NULL        : {stats['raw_null']}/{total} ({stats['raw_null']*100//total if total > 0 else 0}%)")
print(f"  • Champ raw NON-NULL    : {stats['raw_not_null']}/{total} ({stats['raw_not_null']*100//total if total > 0 else 0}%)")

# Afficher quelques exemples de données raw
print("\n🔎 Échantillon de données raw (5 premières invitations avec raw non-null) :")
sample_with_raw = session.query(Invitation).filter(Invitation.raw.isnot(None)).limit(5).all()
if sample_with_raw:
    for i, inv in enumerate(sample_with_raw, 1):
        print(f"\n  Invitation #{i} (SIRET: {inv.siret}):")
        if inv.raw:
            raw_keys = list(inv.raw.keys())[:10]  # Première 10 clés
            print(f"    Clés dans raw: {', '.join(raw_keys)}")
            if len(inv.raw) > 10:
                print(f"    ... et {len(inv.raw) - 10} autres clés")
        else:
            print("    raw est vide")
else:
    print("  Aucune invitation avec raw non-null")

# ============================================================================
# ÉTAPE 2 : FONCTIONS DE MIGRATION
# ============================================================================

def _normalize_raw_key(key: str) -> str:
    """Normalise une clé de dictionnaire raw pour la recherche."""
    key = unicodedata.normalize("NFKD", str(key))
    key = "".join(ch for ch in key if not unicodedata.combining(ch))
    key = key.lower()
    key = re.sub(r"[^a-z0-9]+", "_", key)
    return key.strip("_")


def _pick_from_raw(raw_dict: dict, *keys: str) -> str | None:
    """Récupère la première valeur non-None depuis raw_dict pour les clés données."""
    if not raw_dict:
        return None
    for key in keys:
        norm = _normalize_raw_key(key)
        if norm and norm in raw_dict:
            value = raw_dict[norm]
            if value is not None and str(value).strip() and str(value).strip().lower() not in ("nan", "none", "null", ""):
                return str(value).strip()
    return None


def _pick_bool_from_raw(raw_dict: dict, *keys: str) -> bool | None:
    """Récupère une valeur booléenne depuis raw_dict."""
    value = _pick_from_raw(raw_dict, *keys)
    if value is None:
        return None
    lowered = str(value).strip().lower()
    if lowered in {"1", "oui", "o", "yes", "y", "true"}:
        return True
    if lowered in {"0", "non", "n", "no", "false"}:
        return False
    return None


# ============================================================================
# ÉTAPE 3 : MIGRATION
# ============================================================================

print("\n" + "=" * 80)
print("🚀 ÉTAPE 2 : MIGRATION DES DONNÉES")
print("-" * 80)

# Récupérer toutes les invitations
invitations = session.query(Invitation).all()

updated_count = 0
skipped_no_raw = 0
skipped_already_filled = 0

for inv in invitations:
    raw = inv.raw or {}
    updated = False

    # Si raw est vide et toutes les colonnes sont déjà NULL, on ne peut rien faire
    if not raw and not inv.denomination and not inv.enseigne:
        skipped_no_raw += 1
        continue

    # Si toutes les colonnes importantes sont déjà remplies, on skip
    if inv.denomination and inv.commune and inv.code_postal:
        skipped_already_filled += 1
        continue

    # Denomination
    if not inv.denomination:
        inv.denomination = _pick_from_raw(
            raw,
            "denomination", "denomination_usuelle", "raison_sociale", "raison sociale",
            "raison_sociale_etablissement", "nom_raison_sociale", "rs", "nom"
        )
        if inv.denomination:
            updated = True

    # Enseigne
    if not inv.enseigne:
        inv.enseigne = _pick_from_raw(raw, "enseigne", "enseigne_commerciale", "enseigne commerciale")
        if inv.enseigne:
            updated = True

    # Adresse
    if not inv.adresse:
        inv.adresse = _pick_from_raw(
            raw,
            "adresse_complete", "adresse", "adresse_ligne_1", "adresse_ligne1", "adresse_ligne 1",
            "adresse1", "adresse_postale", "ligne_4", "ligne4", "libelle_voie", "libelle_voie_etablissement"
        )
        if inv.adresse:
            updated = True

    # Code postal
    if not inv.code_postal:
        inv.code_postal = _pick_from_raw(
            raw, "code_postal", "code postal", "cp", "code_postal_etablissement"
        )
        if inv.code_postal:
            updated = True

    # Commune
    if not inv.commune:
        inv.commune = _pick_from_raw(
            raw, "commune", "ville", "localite", "adresse_ville", "libelle_commune_etablissement"
        )
        if inv.commune:
            updated = True

    # Activité principale
    if not inv.activite_principale:
        inv.activite_principale = _pick_from_raw(
            raw, "activite_principale", "code_naf", "naf", "code_ape", "ape"
        )
        if inv.activite_principale:
            updated = True

    # Libellé activité
    if not inv.libelle_activite:
        inv.libelle_activite = _pick_from_raw(
            raw, "libelle_activite", "libelle activité", "libelle_naf", "activite",
            "activite_principale_libelle"
        )
        if inv.libelle_activite:
            updated = True

    # Tranche effectifs
    if not inv.tranche_effectifs:
        inv.tranche_effectifs = _pick_from_raw(
            raw, "tranche_effectifs", "tranche_effectif", "tranche_effectifs_salaries",
            "tranche_effectif_salarie"
        )
        if inv.tranche_effectifs:
            updated = True

    # Effectifs label
    if not inv.effectifs_label:
        inv.effectifs_label = _pick_from_raw(
            raw, "effectifs", "effectif", "effectifs_salaries", "effectifs salaries",
            "effectifs categorie"
        )
        if inv.effectifs_label:
            updated = True

    # Catégorie entreprise
    if not inv.categorie_entreprise:
        inv.categorie_entreprise = _pick_from_raw(
            raw, "categorie_entreprise", "categorie", "taille_entreprise", "taille"
        )
        if inv.categorie_entreprise:
            updated = True

    # Est actif
    if inv.est_actif is None:
        inv.est_actif = _pick_bool_from_raw(raw, "est_actif", "actif", "etat_etablissement", "etat")
        if inv.est_actif is not None:
            updated = True

    # Est siège
    if inv.est_siege is None:
        inv.est_siege = _pick_bool_from_raw(raw, "est_siege", "siege", "siege_social")
        if inv.est_siege is not None:
            updated = True

    if updated:
        updated_count += 1

# Commit
try:
    session.commit()
    print(f"✅ Migration réussie !")
    print(f"   • Invitations mises à jour    : {updated_count}")
    print(f"   • Invitations sans données raw : {skipped_no_raw}")
    print(f"   • Invitations déjà remplies    : {skipped_already_filled}")
    print(f"   • Total traité                 : {updated_count + skipped_no_raw + skipped_already_filled}/{total}")
except Exception as e:
    session.rollback()
    print(f"❌ ERREUR lors de la migration : {e}")
    sys.exit(1)
finally:
    session.close()

# ============================================================================
# ÉTAPE 4 : VÉRIFICATION POST-MIGRATION
# ============================================================================

print("\n" + "=" * 80)
print("🔍 ÉTAPE 3 : VÉRIFICATION POST-MIGRATION")
print("-" * 80)

# Nouvelle session pour vérifier
session = Session(bind=engine)

# Re-compter les NULL
new_stats = {
    "denomination_null": session.query(Invitation).filter(Invitation.denomination.is_(None)).count(),
    "enseigne_null": session.query(Invitation).filter(Invitation.enseigne.is_(None)).count(),
    "adresse_null": session.query(Invitation).filter(Invitation.adresse.is_(None)).count(),
    "commune_null": session.query(Invitation).filter(Invitation.commune.is_(None)).count(),
    "code_postal_null": session.query(Invitation).filter(Invitation.code_postal.is_(None)).count(),
}

print("\n📊 État des colonnes APRÈS migration :")
print(f"  • Denomination NULL : {new_stats['denomination_null']}/{total} ({new_stats['denomination_null']*100//total if total > 0 else 0}%)")
print(f"  • Enseigne NULL     : {new_stats['enseigne_null']}/{total} ({new_stats['enseigne_null']*100//total if total > 0 else 0}%)")
print(f"  • Adresse NULL      : {new_stats['adresse_null']}/{total} ({new_stats['adresse_null']*100//total if total > 0 else 0}%)")
print(f"  • Commune NULL      : {new_stats['commune_null']}/{total} ({new_stats['commune_null']*100//total if total > 0 else 0}%)")
print(f"  • Code postal NULL  : {new_stats['code_postal_null']}/{total} ({new_stats['code_postal_null']*100//total if total > 0 else 0}%)")

# Afficher quelques exemples APRÈS migration
print("\n✨ Échantillon APRÈS migration (5 premières invitations) :")
sample_after = session.query(Invitation).limit(5).all()
for i, inv in enumerate(sample_after, 1):
    print(f"\n  Invitation #{i} (SIRET: {inv.siret}):")
    print(f"    Denomination    : {inv.denomination or '(vide)'}")
    print(f"    Enseigne        : {inv.enseigne or '(vide)'}")
    print(f"    Adresse         : {inv.adresse or '(vide)'}")
    print(f"    Commune         : {inv.commune or '(vide)'}")
    print(f"    Code postal     : {inv.code_postal or '(vide)'}")

session.close()

print("\n" + "=" * 80)
print("✅ MIGRATION TERMINÉE")
print("=" * 80)
