#!/usr/bin/env python3
"""
Script pour télécharger automatiquement papcse.db depuis la release GitHub.
"""
import os
import sys
import requests
from pathlib import Path

# Configuration
GITHUB_REPO = "quentin12200/outilspapv2"
RELEASE_TAG = "v1.0.0"
DB_FILENAME = "papcse.db"
DB_URL = f"https://github.com/{GITHUB_REPO}/releases/download/{RELEASE_TAG}/{DB_FILENAME}"

# Chemin vers le fichier de base de données
PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / DB_FILENAME


def download_database(force=False):
    """
    Télécharge la base de données depuis GitHub Release.

    Args:
        force (bool): Si True, re-télécharge même si le fichier existe déjà

    Returns:
        bool: True si téléchargement réussi, False sinon
    """
    # Vérifier si le fichier existe déjà
    if DB_PATH.exists() and not force:
        file_size = DB_PATH.stat().st_size / (1024 * 1024)  # Taille en Mo
        print(f"✓ Base de données déjà présente : {DB_PATH} ({file_size:.1f} Mo)")
        return True

    if force and DB_PATH.exists():
        print(f"⚠ Re-téléchargement forcé de la base de données...")
    else:
        print(f"⚠ Base de données non trouvée, téléchargement depuis GitHub...")

    print(f"📥 URL: {DB_URL}")
    print(f"📁 Destination: {DB_PATH}")

    try:
        # Téléchargement avec barre de progression
        response = requests.get(DB_URL, stream=True, timeout=60)
        response.raise_for_status()

        # Récupérer la taille totale
        total_size = int(response.headers.get('content-length', 0))
        total_mb = total_size / (1024 * 1024)

        print(f"📦 Taille du fichier: {total_mb:.1f} Mo")
        print("⏳ Téléchargement en cours...")

        # Télécharger par chunks avec progression
        downloaded = 0
        chunk_size = 8192

        with open(DB_PATH, 'wb') as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)

                    # Afficher la progression tous les 5%
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        if int(progress) % 10 == 0:
                            downloaded_mb = downloaded / (1024 * 1024)
                            print(f"  {progress:.0f}% - {downloaded_mb:.1f} Mo / {total_mb:.1f} Mo")

        final_size = DB_PATH.stat().st_size / (1024 * 1024)
        print(f"✅ Téléchargement terminé ! ({final_size:.1f} Mo)")
        print(f"✓ Base de données sauvegardée : {DB_PATH}")

        return True

    except requests.exceptions.RequestException as e:
        print(f"❌ Erreur lors du téléchargement : {e}", file=sys.stderr)

        # Si le fichier partiel existe, le supprimer
        if DB_PATH.exists():
            DB_PATH.unlink()
            print(f"🗑️ Fichier partiel supprimé")

        return False

    except Exception as e:
        print(f"❌ Erreur inattendue : {e}", file=sys.stderr)
        return False


def check_database():
    """
    Vérifie si la base de données existe et est valide.

    Returns:
        bool: True si la base existe et semble valide, False sinon
    """
    if not DB_PATH.exists():
        return False

    # Vérifier que le fichier n'est pas vide
    if DB_PATH.stat().st_size < 1000:  # Moins de 1 Ko = probablement invalide
        print(f"⚠ Le fichier existe mais semble invalide (taille < 1 Ko)")
        return False

    # Vérifier que c'est bien un fichier SQLite
    try:
        with open(DB_PATH, 'rb') as f:
            header = f.read(16)
            if not header.startswith(b'SQLite format 3'):
                print(f"⚠ Le fichier n'est pas une base SQLite valide")
                return False
    except Exception as e:
        print(f"⚠ Erreur lors de la vérification : {e}")
        return False

    return True


def main():
    """
    Point d'entrée principal du script.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Télécharge papcse.db depuis GitHub Release"
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help="Force le re-téléchargement même si le fichier existe"
    )
    parser.add_argument(
        '--check',
        action='store_true',
        help="Vérifie seulement si la base existe (ne télécharge pas)"
    )

    args = parser.parse_args()

    if args.check:
        # Mode vérification seulement
        if check_database():
            print("✅ Base de données présente et valide")
            sys.exit(0)
        else:
            print("❌ Base de données manquante ou invalide")
            sys.exit(1)

    # Télécharger la base
    success = download_database(force=args.force)

    if success:
        print("\n" + "="*60)
        print("✅ Base de données prête à l'emploi !")
        print("="*60)
        sys.exit(0)
    else:
        print("\n" + "="*60)
        print("❌ Échec du téléchargement de la base de données")
        print("="*60)
        sys.exit(1)


if __name__ == "__main__":
    main()
