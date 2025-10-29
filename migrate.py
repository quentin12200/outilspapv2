#!/usr/bin/env python3
"""Script de migration automatique vers la version 2.0."""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
BACKUP_DIR = ROOT / f"backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

FILES_TO_BACKUP = [
    ROOT / "app" / "main.py",
    ROOT / "app" / "etl.py",
    ROOT / "app" / "routers" / "api.py",
    ROOT / "app" / "templates" / "base.html",
    ROOT / "app" / "templates" / "index.html",
    ROOT / ".env.example",
    ROOT / "requirements.txt",
]


def backup_files() -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    for src in FILES_TO_BACKUP:
        if src.exists():
            dest = BACKUP_DIR / src.relative_to(ROOT)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            print(f"Sauvegarde : {src} -> {dest}")


def create_directories() -> None:
    for path in (ROOT / "app" / "core", ROOT / "tests", ROOT / "logs"):
        path.mkdir(parents=True, exist_ok=True)
        print(f"Dossier vérifié : {path}")


def ensure_env_file() -> None:
    example = ROOT / ".env.example"
    target = ROOT / ".env"
    if example.exists() and not target.exists():
        shutil.copy2(example, target)
        print("Fichier .env créé à partir de .env.example")


def main() -> None:
    backup_files()
    create_directories()
    ensure_env_file()
    print("Migration préparatoire terminée. Vérifiez la documentation pour les étapes suivantes.")


if __name__ == "__main__":
    main()
