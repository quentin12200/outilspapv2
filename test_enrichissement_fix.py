#!/usr/bin/env python3
"""
Script de test pour vérifier que l'enrichissement IDCC fonctionne correctement.
Teste les différents cas :
- SIRET avec IDCC
- SIRET sans IDCC (mais valide)
- SIRET invalide
"""

import sys
import os

# Pour pouvoir importer les modules de l'app
sys.path.insert(0, os.path.dirname(__file__))

from app.background_tasks import _get_siret_sync


def test_enrichissement():
    print("=" * 70)
    print("TEST DE L'ENRICHISSEMENT IDCC")
    print("=" * 70)

    # Test 1 : SIRET avec IDCC connu (PEUGEOT)
    print("\n📋 Test 1 : SIRET avec IDCC")
    print("-" * 70)
    siret_avec_idcc = "55210055400175"  # Peugeot SA
    print(f"Testing SIRET: {siret_avec_idcc}")
    result = _get_siret_sync(siret_avec_idcc)
    if result:
        print(f"✓ Result: {result}")
        if result.get("success") and result.get("idcc"):
            print(f"✅ SUCCESS: IDCC trouvé = {result.get('idcc')}")
        elif result.get("success") and not result.get("idcc"):
            print("✅ SUCCESS: API OK mais pas d'IDCC")
        else:
            print("❌ FAIL: Format de réponse incorrect")
    else:
        print("❌ FAIL: Aucun résultat")

    # Test 2 : SIRET probablement sans IDCC (petit commerce)
    print("\n📋 Test 2 : SIRET sans IDCC (mais valide)")
    print("-" * 70)
    siret_sans_idcc = "83272932600017"  # Un petit commerce sans IDCC
    print(f"Testing SIRET: {siret_sans_idcc}")
    result = _get_siret_sync(siret_sans_idcc)
    if result:
        print(f"✓ Result: {result}")
        if result.get("success"):
            if result.get("idcc"):
                print(f"✅ SUCCESS: IDCC trouvé = {result.get('idcc')}")
            else:
                print("✅ SUCCESS: API OK mais pas d'IDCC (comportement attendu)")
        else:
            print("❌ FAIL: Format de réponse incorrect")
    else:
        print("⚠️  WARNING: Aucun résultat (peut-être SIRET inexistant)")

    # Test 3 : SIRET invalide
    print("\n📋 Test 3 : SIRET invalide")
    print("-" * 70)
    siret_invalide = "00000000000000"
    print(f"Testing SIRET: {siret_invalide}")
    result = _get_siret_sync(siret_invalide)
    if result is None:
        print("✅ SUCCESS: None retourné pour SIRET invalide (comportement attendu)")
    else:
        print(f"❌ FAIL: Devrait retourner None, mais a retourné: {result}")

    print("\n" + "=" * 70)
    print("RÉSUMÉ")
    print("=" * 70)
    print("""
✅ Corrections appliquées :
   1. _get_siret_sync() retourne désormais {"idcc": None, "success": True}
      pour les cas où l'API répond OK mais sans IDCC

   2. run_enrichir_invitations_idcc() marque maintenant date_enrichissement
      même si l'IDCC n'est pas trouvé

   3. Les statistiques distinguent :
      - IDCC trouvés
      - Traités avec succès mais sans IDCC
      - Erreurs

🔑 Bénéfices :
   - Évite de réessayer indéfiniment les mêmes SIRETs sans IDCC
   - Meilleure visibilité sur les résultats d'enrichissement
   - Logs plus clairs pour le débogage
""")


if __name__ == "__main__":
    test_enrichissement()
