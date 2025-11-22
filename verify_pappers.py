import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from app.services.sirene_api import enrichir_siret, rechercher_siret

async def main():
    print("--- Test Pappers API Integration ---")
    
    # Test 1: Enrichissement SIRET (Carrefour Siege)
    siret_test = "65201405100732"
    print(f"\n1. Testing enrichir_siret({siret_test})...")
    result = await enrichir_siret(siret_test)
    
    if result:
        print("   [SUCCESS] Data found:")
        print(f"   Name: {result.get('denomination')}")
        print(f"   Source: {result.get('source', 'Unknown')}")
        if result.get('source') == 'Pappers':
            print("   [VERIFIED] Data came from Pappers!")
        else:
            print("   [WARNING] Data came from fallback (Sirene) or source not set.")
    else:
        print("   [FAILURE] No data found.")

    # Test 2: Recherche (Carrefour)
    query = "Carrefour"
    print(f"\n2. Testing rechercher_siret('{query}')...")
    results = await rechercher_siret(query, limit=3)
    
    if results:
        print(f"   [SUCCESS] Found {len(results)} results.")
        first = results[0]
        print(f"   First result: {first.get('denomination')} ({first.get('siret')})")
        print(f"   Source: {first.get('source', 'Unknown')}")
        if first.get('source') == 'Pappers':
            print("   [VERIFIED] Search results came from Pappers!")
    else:
        print("   [FAILURE] No results found.")

if __name__ == "__main__":
    asyncio.run(main())
