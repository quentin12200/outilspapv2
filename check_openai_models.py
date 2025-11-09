#!/usr/bin/env python3
"""
Script pour vérifier quels modèles OpenAI sont accessibles avec votre clé API.
"""

import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

def check_available_models():
    """Vérifie quels modèles GPT-4 sont disponibles."""
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        print("❌ OPENAI_API_KEY non trouvée dans .env")
        return

    print(f"🔑 Clé API trouvée: {api_key[:20]}...")
    print("\n" + "="*60)
    print("Vérification des modèles GPT-4 disponibles...")
    print("="*60 + "\n")

    client = OpenAI(api_key=api_key)

    # Liste des modèles GPT-4o à tester
    models_to_test = [
        "gpt-4o",
        "gpt-4o-2024-11-20",
        "gpt-4o-2024-08-06",
        "gpt-4o-2024-05-13",
        "gpt-4o-mini",
        "gpt-4o-mini-2024-07-18",
        "gpt-4-turbo",
        "gpt-4-turbo-2024-04-09",
    ]

    available_models = []
    unavailable_models = []

    for model in models_to_test:
        try:
            # Essayer un appel minimal pour vérifier l'accès
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5
            )
            available_models.append(model)
            print(f"✅ {model:30} - DISPONIBLE")
        except Exception as e:
            error_msg = str(e)
            unavailable_models.append((model, error_msg))
            if "does not have access" in error_msg or "model_not_found" in error_msg:
                print(f"❌ {model:30} - NON ACCESSIBLE (pas dans votre plan)")
            else:
                print(f"⚠️  {model:30} - ERREUR: {error_msg[:50]}")

    print("\n" + "="*60)
    print("RÉSUMÉ")
    print("="*60)
    print(f"\n✅ Modèles disponibles ({len(available_models)}):")
    for model in available_models:
        print(f"   - {model}")

    if unavailable_models:
        print(f"\n❌ Modèles non disponibles ({len(unavailable_models)}):")
        for model, _ in unavailable_models:
            print(f"   - {model}")

    # Recommandation
    print("\n" + "="*60)
    print("RECOMMANDATION")
    print("="*60)

    if available_models:
        recommended = available_models[0]
        print(f"\n💡 Modèle recommandé pour votre configuration: {recommended}")
        print(f"\nPour l'utiliser, ajoutez ceci dans votre fichier .env :")
        print(f"\n   OPENAI_MODEL={recommended}")

        # Tarifs approximatifs
        costs = {
            "gpt-4o": "$0.0025/1K input tokens, $0.01/1K output tokens",
            "gpt-4o-mini": "$0.00015/1K input tokens, $0.0006/1K output tokens",
            "gpt-4-turbo": "$0.01/1K input tokens, $0.03/1K output tokens",
        }

        for model_name, cost in costs.items():
            if any(model_name in m for m in available_models):
                print(f"\n💰 Tarif {model_name}: {cost}")
    else:
        print("\n⚠️  Aucun modèle GPT-4 accessible avec cette clé API.")
        print("Vérifiez :")
        print("  1. Que vous avez des crédits sur votre compte OpenAI")
        print("  2. Que votre clé API est valide")
        print("  3. Que vous avez activé les modèles dans votre projet OpenAI")

if __name__ == "__main__":
    check_available_models()
