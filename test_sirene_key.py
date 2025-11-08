#!/usr/bin/env python3
"""
Script de test pour vérifier l'authentification API Sirene.
Usage: python test_sirene_key.py
"""

import os
import httpx
import sys

def test_sirene_api():
    # Récupérer la clé API
    api_key = os.getenv("SIRENE_API_KEY") or os.getenv("API_SIRENE_KEY")

    print("=" * 70)
    print("TEST API SIRENE - AUTHENTIFICATION")
    print("=" * 70)

    if not api_key:
        print("❌ ERREUR : Aucune clé API trouvée")
        print("   Variables cherchées : SIRENE_API_KEY, API_SIRENE_KEY")
        print("\n💡 Définissez la variable :")
        print("   export SIRENE_API_KEY='votre-clé-ici'")
        return False

    print(f"✓ Clé API trouvée : {api_key[:8]}...{api_key[-4:]} (longueur: {len(api_key)})")

    # Test 1 : Format de la clé
    print("\n--- Test 1 : Format de la clé ---")
    if len(api_key) == 36 and api_key.count('-') == 4:
        print("✓ Format UUID valide")
    else:
        print(f"⚠️  Format inhabituel (attendu: UUID avec 4 tirets, longueur 36)")

    # Test 2 : Appel API avec la clé
    print("\n--- Test 2 : Appel API Sirene ---")
    url = "https://api.insee.fr/api-sirene/3.11/siren/552100554"
    headers = {
        "X-INSEE-Api-Key-Integration": api_key,
        "Accept": "application/json"
    }

    print(f"URL      : {url}")
    print(f"Header   : X-INSEE-Api-Key-Integration")
    print(f"Clé      : {api_key[:8]}...{api_key[-4:]}")

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, headers=headers)

            print(f"\nStatut HTTP : {response.status_code}")

            if response.status_code == 200:
                print("✅ SUCCÈS : L'API répond correctement")
                data = response.json()
                if "header" in data:
                    print(f"   Statut API : {data['header'].get('statut')}")
                if "uniteLegale" in data:
                    print(f"   Raison sociale : {data['uniteLegale'].get('denominationUniteLegale')}")
                return True

            elif response.status_code == 401:
                print("❌ ERREUR 401 : Authentification refusée")
                print("   → La clé API est invalide ou expirée")
                print("   → Vérifiez la clé sur https://portail-api.insee.fr/")

            elif response.status_code == 403:
                print("❌ ERREUR 403 : Accès interdit")
                print("   → La clé n'a pas accès à l'API Sirene")
                print("   → Vérifiez les permissions sur le portail INSEE")

            elif response.status_code == 429:
                print("⚠️  ERREUR 429 : Trop de requêtes")
                print("   → Rate limit atteint")
                print("   → Si vous utilisez une clé payante, elle n'est peut-être pas reconnue")

            else:
                print(f"⚠️  Erreur inattendue : {response.status_code}")

            print(f"\nRéponse brute (200 premiers caractères) :")
            print(response.text[:200])

    except Exception as e:
        print(f"❌ EXCEPTION : {e}")
        return False

    return False

if __name__ == "__main__":
    print("\n💡 Ce script teste si votre clé API Sirene fonctionne correctement\n")
    success = test_sirene_api()
    print("\n" + "=" * 70)
    if success:
        print("✅ RÉSULTAT : Clé API fonctionnelle")
        sys.exit(0)
    else:
        print("❌ RÉSULTAT : Problème d'authentification détecté")
        print("\n📋 Actions recommandées :")
        print("1. Vérifiez que la clé est active sur https://portail-api.insee.fr/")
        print("2. Vérifiez que l'API 'Sirene' est bien souscrite")
        print("3. Essayez de régénérer la clé si nécessaire")
        sys.exit(1)
