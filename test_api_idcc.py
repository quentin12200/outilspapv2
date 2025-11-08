#!/usr/bin/env python3
"""
Test rapide pour vérifier si l'API Sirene renvoie bien des IDCC
"""
import httpx
import os
import json
from dotenv import load_dotenv

load_dotenv()

# Configuration
SIRENE_API_BASE = "https://api.insee.fr/api-sirene/3.11"
api_key = (os.getenv("SIRENE_API_KEY") or os.getenv("API_SIRENE_KEY") or "").strip()

headers = {"Accept": "application/json"}
if api_key:
    headers["X-INSEE-Api-Key-Integration"] = api_key
    print(f"✓ API Key: {api_key[:8]}...{api_key[-4:]}")
else:
    print("⚠️ NO API KEY")

# Test avec des SIRETs qui devraient avoir un IDCC
test_sirets = [
    ("55210055400175", "Peugeot SA (devrait avoir IDCC)"),
    ("83272932600017", "Petit commerce (probablement sans IDCC)"),
    ("52448206400028", "Premier SIRET du log (Carrefour Market)"),
]

print("\n" + "=" * 80)
print("TEST DE L'EXTRACTION IDCC")
print("=" * 80 + "\n")

for siret, description in test_sirets:
    print(f"\n📋 Test: {description}")
    print(f"   SIRET: {siret}")
    print("-" * 80)

    url = f"{SIRENE_API_BASE}/siret/{siret}"

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, headers=headers)

            print(f"   Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()

                # Structure de la réponse
                etablissement = data.get("etablissement", {})
                unite_legale = etablissement.get("uniteLegale", {})

                # Extraction IDCC (comme dans le code actuel)
                idcc = unite_legale.get("identifiantConventionCollectiveRenseignee")

                print(f"\n   📊 Données extraites:")
                print(f"      - IDCC trouvé: {idcc if idcc else 'Non'}")

                # Afficher tous les champs de uniteLegale qui contiennent "convention" ou "idcc" (case-insensitive)
                print(f"\n   🔍 Champs relatifs à IDCC/Convention dans uniteLegale:")
                for key, value in unite_legale.items():
                    if "convention" in key.lower() or "idcc" in key.lower() or "collective" in key.lower():
                        print(f"      - {key}: {value}")

                # Afficher la structure complète pour debug
                if not idcc:
                    print(f"\n   📄 Structure complète uniteLegale:")
                    print(f"      Clés disponibles: {list(unite_legale.keys())}")

            else:
                print(f"   ✗ Erreur: {response.status_code}")

    except Exception as e:
        print(f"   ✗ Exception: {e}")

print("\n" + "=" * 80)
print("FIN DU TEST")
print("=" * 80)
