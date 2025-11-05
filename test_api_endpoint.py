#!/usr/bin/env python
"""Script de test pour l'endpoint /api/stats/enriched"""

import sys
import os

# Ajoute le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db import SessionLocal
from app.routers.api import enriched_kpi_stats

def test_endpoint():
    """Teste l'endpoint directement sans serveur HTTP"""
    print("=" * 60)
    print("Test de l'endpoint /api/stats/enriched")
    print("=" * 60)

    # Crée une session de base de données
    db = SessionLocal()

    try:
        print("\n🔄 Appel de l'endpoint...")
        result = enriched_kpi_stats(db)

        print("\n✅ Résultat:")
        print("-" * 60)
        for key, value in result.items():
            print(f"{key:30s} = {value}")
        print("-" * 60)

        # Vérifie que toutes les clés attendues sont présentes
        expected_keys = [
            'total_invitations',
            'audience_threshold',
            'pap_pv_overlap_percent',
            'cgt_implanted_count',
            'cgt_implanted_percent',
            'elections_next_30_days'
        ]

        missing_keys = set(expected_keys) - set(result.keys())
        if missing_keys:
            print(f"\n⚠️  Clés manquantes: {missing_keys}")
        else:
            print("\n✅ Toutes les clés attendues sont présentes")

        # Affiche un résumé
        print("\n📊 Résumé:")
        print(f"  - Invitations PAP: {result['total_invitations']}")
        print(f"  - Seuil audience: {result['audience_threshold']}")
        print(f"  - Couverture PAP↔PV: {result['pap_pv_overlap_percent']}%")
        print(f"  - CGT implantée: {result['cgt_implanted_count']} ({result['cgt_implanted_percent']}%)")
        print(f"  - Élections 30j: {result['elections_next_30_days']}")

        if result['total_invitations'] == 0:
            print("\n⚠️  ATTENTION: Aucune invitation dans la base de données")
            print("   Les indicateurs afficheront tous 0 sur la page d'accueil")

        return True

    except Exception as e:
        print(f"\n❌ ERREUR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = test_endpoint()
    sys.exit(0 if success else 1)
