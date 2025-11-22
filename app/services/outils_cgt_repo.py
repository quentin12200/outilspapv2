"""Helpers to mirror the outilsCGT repository locally for offline access."""

from __future__ import annotations

import datetime
import shutil
import tempfile
from pathlib import Path
from typing import Dict

import subprocess

REPO_GIT_URL = "https://github.com/quentin12200/outilsCGT.git"
DEST_DIR = Path(__file__).resolve().parent.parent / "static" / "outils-cgt"
ZIP_CACHE_PATH = Path(__file__).resolve().parent.parent / "static" / "outils-cgt.zip"
HEAVY_DIRS = ["node_modules", "venv", ".venv"]
SPARSE_PATHS = [
    "frontend",
    "README.md",
    "DemarcheMain.js",
    "DemarcheRevendicativePage.js",
    "scripts",
]


def sync_outils_cgt_repo(force: bool = False) -> Dict[str, object]:
    """Download and extract the outilsCGT repository into ``static/outils-cgt``.

    Returns a dict with ``ok`` boolean, ``files`` count, ``updated_at`` UTC datetime,
    and optional ``error`` message.
    """

    if DEST_DIR.exists() and not force:
        return {
            "ok": True,
            "files": sum(1 for _ in DEST_DIR.rglob("*")),
            "updated_at": datetime.datetime.utcfromtimestamp(DEST_DIR.stat().st_mtime),
            "path": DEST_DIR,
            "zip_path": ZIP_CACHE_PATH if ZIP_CACHE_PATH.exists() else None,
            "from_cache": True,
        }

    tmpdir = Path(tempfile.mkdtemp(prefix="outils-cgt-"))
    repo_dir = tmpdir / "repo"

    try:
        subprocess.run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "--filter=blob:none",
                "--no-checkout",
                REPO_GIT_URL,
                str(repo_dir),
            ],
            check=True,
            timeout=120,
        )

        subprocess.run(
            ["git", "-C", str(repo_dir), "sparse-checkout", "init", "--cone"],
            check=True,
            timeout=60,
        )

        subprocess.run(
            ["git", "-C", str(repo_dir), "sparse-checkout", "set", *SPARSE_PATHS],
            check=True,
            timeout=60,
        )

        subprocess.run(
            ["git", "-C", str(repo_dir), "checkout"],
            check=True,
            timeout=120,
        )

        if DEST_DIR.exists():
            shutil.rmtree(DEST_DIR)
        shutil.copytree(repo_dir, DEST_DIR, ignore=shutil.ignore_patterns(".git"))

        for dirname in HEAVY_DIRS:
            bulky_path = DEST_DIR / dirname
            if bulky_path.exists():
                shutil.rmtree(bulky_path, ignore_errors=True)

        ZIP_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        shutil.make_archive(str(ZIP_CACHE_PATH.with_suffix("")), "zip", DEST_DIR)

        file_count = sum(1 for _ in DEST_DIR.rglob("*"))
        return {
            "ok": True,
            "files": file_count,
            "updated_at": datetime.datetime.utcnow(),
            "path": DEST_DIR,
            "zip_path": ZIP_CACHE_PATH,
            "from_cache": False,
        }
    except Exception as exc:  # noqa: BLE001 - surface any sync failure as message
        return {"ok": False, "error": str(exc)}
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def outils_cgt_readme_excerpt(lines: int = 40) -> str:
    """Return the first ``lines`` lines of the mirrored README if present."""

    readme_path = DEST_DIR / "README.md"
    if not readme_path.exists():
        return ""

    content_lines = readme_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    return "\n".join(content_lines[:lines])
