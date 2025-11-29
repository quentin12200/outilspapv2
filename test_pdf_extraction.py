#!/usr/bin/env python3
"""
Script de test pour l'extraction PDF PAP
Permet de tester l'extraction sans utiliser l'API web
"""

import sys
from pypdf import PdfReader
from pathlib import Path


def test_pdf_extraction(pdf_path: str):
    """
    Teste l'extraction de texte depuis un PDF PAP

    Args:
        pdf_path: Chemin vers le fichier PDF
    """
    print(f"🔍 Test d'extraction PDF: {pdf_path}")
    print("=" * 60)

    if not Path(pdf_path).exists():
        print(f"❌ Erreur: Le fichier {pdf_path} n'existe pas")
        return False

    try:
        # 1. Extraire le texte
        print("\n1️⃣ Extraction du texte...")
        reader = PdfReader(pdf_path)
        pdf_text = ""

        for i, page in enumerate(reader.pages, 1):
            page_text = page.extract_text()
            pdf_text += page_text + "\n"
            print(f"   Page {i}: {len(page_text)} caractères extraits")

        print(f"\n   ✅ Total: {len(pdf_text)} caractères extraits depuis {len(reader.pages)} page(s)")

        # 2. Afficher un extrait
        print("\n2️⃣ Extrait du contenu (500 premiers caractères):")
        print("-" * 60)
        print(pdf_text[:500])
        print("-" * 60)

        # 3. Rechercher les patterns PAP typiques
        print("\n3️⃣ Analyse des patterns PAP:")

        # SIRET (14 chiffres)
        import re
        siret_pattern = r'\b\d{14}\b'
        sirets = re.findall(siret_pattern, pdf_text)
        if sirets:
            print(f"   ✅ SIRET trouvé(s): {sirets[:5]}{'...' if len(sirets) > 5 else ''}")
        else:
            print("   ⚠️  Aucun SIRET (14 chiffres) détecté")

        # Dates (format français)
        date_pattern = r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b'
        dates = re.findall(date_pattern, pdf_text)
        if dates:
            print(f"   ✅ Date(s) trouvée(s): {dates[:5]}{'...' if len(dates) > 5 else ''}")
        else:
            print("   ⚠️  Aucune date détectée")

        # Mots-clés PAP
        keywords = ['PAP', 'protocole', 'accord', 'élection', 'CSE', 'comité']
        found_keywords = [kw for kw in keywords if kw.lower() in pdf_text.lower()]
        if found_keywords:
            print(f"   ✅ Mots-clés PAP trouvés: {', '.join(found_keywords)}")
        else:
            print("   ⚠️  Aucun mot-clé PAP typique trouvé")

        # 4. Statistiques
        print("\n4️⃣ Statistiques:")
        print(f"   • Nombre de lignes: {len(pdf_text.splitlines())}")
        print(f"   • Nombre de mots: {len(pdf_text.split())}")
        print(f"   • Taille en octets: {len(pdf_text.encode('utf-8'))}")

        # 5. Verdict
        print("\n" + "=" * 60)
        if len(pdf_text.strip()) > 100 and (sirets or dates):
            print("✅ PDF lisible avec des données extractibles détectées")
            print("   Le document semble compatible avec l'import PAP automatique")
            return True
        elif len(pdf_text.strip()) > 100:
            print("⚠️  PDF lisible mais peu de données structurées détectées")
            print("   L'extraction ChatGPT sera nécessaire pour structurer les données")
            return True
        else:
            print("❌ PDF non lisible ou vide")
            print("   Le PDF pourrait être une image scannée (nécessite OCR)")
            return False

    except Exception as e:
        print(f"\n❌ Erreur lors de l'extraction: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_pdf_extraction.py <chemin_vers_pdf>")
        print("\nExemple:")
        print("  python test_pdf_extraction.py /chemin/vers/pap.pdf")
        sys.exit(1)

    pdf_path = sys.argv[1]
    success = test_pdf_extraction(pdf_path)
    sys.exit(0 if success else 1)
