#!/usr/bin/env python3
"""
Test rapide pour vérifier que l'API Siret2IDCC renvoie bien les URLs Legifrance
"""
import sys
import os

# Ajouter le répertoire parent au path pour importer les modules de l'app
sys.path.insert(0, os.path.dirname(__file__))

from app.background_tasks import _get_siret_sync

# SIRETs de test qui devraient avoir un IDCC
test_sirets = [
    ("55210055400175", "Peugeot SA (Métallurgie)"),
    ("75330823807996", "ACTION (Commerce)"),
    ("54204452401063", "NATIXIS (Banque)"),
    ("82161143100015", "Exemple de la doc (Bureaux d'études)"),
]

print("\n" + "=" * 80)
print("TEST RÉCUPÉRATION URL IDCC VIA API SIRET2IDCC")
print("=" * 80 + "\n")

for siret, description in test_sirets:
    print(f"\n📋 Test: {description}")
    print(f"   SIRET: {siret}")
    print("-" * 80)

    result = _get_siret_sync(siret)

    if result:
        if result.get("success"):
            idcc = result.get("idcc")
            idcc_url = result.get("idcc_url")

            if idcc:
                print(f"   ✅ IDCC trouvé: {idcc}")
                print(f"   🔗 URL Legifrance: {idcc_url}")

                if idcc_url and idcc_url.startswith("https://www.legifrance.gouv.fr"):
                    print(f"   ✓ Format URL valide")
                elif idcc_url:
                    print(f"   ⚠️ URL présente mais format inattendu")
                else:
                    print(f"   ⚠️ Aucune URL retournée")
            else:
                print(f"   ○ Pas d'IDCC trouvé (normal pour certaines entreprises)")
        else:
            print(f"   ✗ Erreur API")
    else:
        print(f"   ✗ Aucun résultat retourné")

print("\n" + "=" * 80)
print("FIN DU TEST")
print("=" * 80 + "\n")
