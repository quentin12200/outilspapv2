from dotenv import load_dotenv
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import tempfile
from typing import Iterable, Optional
import urllib.error
import urllib.parse
import urllib.request

from sqlalchemy.engine.url import make_url

load_dotenv()

logger = logging.getLogger("papcse.config")

BASE_DIR = Path(__file__).resolve().parent.parent


def _extract_release_url(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    lowered = candidate.lower()
    if lowered.startswith("http://") or lowered.startswith("https://"):
        return candidate
    return None


db_url_env = os.getenv("DB_URL")
release_url_override = _extract_release_url(db_url_env)
if release_url_override and not os.getenv("DATABASE_RELEASE_URL"):
    os.environ.setdefault("DATABASE_RELEASE_URL", release_url_override)


def _coalesce_database_url() -> str:
    candidates = [os.getenv("DATABASE_URL")]
    if db_url_env and not release_url_override:
        candidates.append(db_url_env)
    candidates.extend(
        [
            os.getenv("SQLALCHEMY_DATABASE_URL"),
            os.getenv("RAILWAY_DATABASE_URL"),
        ]
    )

    for candidate in candidates:
        if not candidate:
            continue
        stripped = candidate.strip()
        if stripped:
            return stripped

    default_sqlite_path = BASE_DIR / "papcse.db"
    return f"sqlite:///{default_sqlite_path}"


DATABASE_URL = _coalesce_database_url()

url = make_url(DATABASE_URL)
IS_SQLITE = url.get_backend_name() == "sqlite"


def _iter_release_urls(
    asset_hint: Optional[str],
    alt_names: Iterable[str],
) -> Iterable[tuple[str, str]]:
    """Yield pairs of (download_url, asset_name) for SQLite releases."""

    direct_url = os.getenv("DATABASE_RELEASE_URL")
    if direct_url:
        parsed_name = Path(urllib.parse.urlparse(direct_url).path).name
        yield direct_url, parsed_name or (asset_hint or "")

    release_repo = os.getenv("DATABASE_RELEASE_REPO", "quentin12200/PV-retenus-branche-interpro-Audience-et-SVE")
    release_api = os.getenv(
        "DATABASE_RELEASE_API",
        f"https://api.github.com/repos/{release_repo}/releases/latest",
    )

    try:
        request = urllib.request.Request(
            release_api,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "papcse-sqlite-loader",
            },
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except Exception as exc:  # pragma: no cover - réseau
        logger.warning("Impossible de récupérer la release GitHub %s: %s", release_api, exc)
        return

    assets = payload.get("assets") or []
    normalized_hint = asset_hint.lower() if asset_hint else None
    normalized_alt = {str(name).lower() for name in alt_names if name}

    for asset in assets:
        name = asset.get("name") or ""
        download_url = asset.get("browser_download_url")
        if not download_url:
            continue
        lower_name = name.lower()
        if normalized_hint and lower_name != normalized_hint:
            continue
        if not normalized_hint:
            if lower_name not in normalized_alt and not lower_name.endswith((".db", ".sqlite", ".sqlite3", ".zip")):
                continue
        yield download_url, name


def _normalise_checksum(raw: Optional[str]) -> Optional[str]:
    """Return a normalized hexadecimal SHA-256 digest."""

    if not raw:
        return None

    value = raw.strip()
    if not value:
        return None

    lower_value = value.lower()
    if ":" in lower_value:
        prefix, digest = lower_value.split(":", 1)
        if prefix and prefix != "sha256":
            logger.warning(
                "Type de checksum %s non géré, seule sha256 est supportée", prefix
            )
            return None
        value = digest.strip()
    else:
        value = lower_value

    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        logger.warning("Checksum SHA-256 invalide: %s", raw)
        return None

    return value


def _compute_sha256(path: Path) -> Optional[str]:
    try:
        hasher = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except OSError as exc:
        logger.warning("Impossible de calculer le SHA-256 de %s: %s", path, exc)
        return None


def _check_sqlite_checksum(path: Path, expected: str) -> bool:
    digest = _compute_sha256(path)
    if not digest:
        return False
    if digest.lower() != expected:
        logger.error(
            "La base %s ne correspond pas au SHA-256 attendu (%s ≠ %s)",
            path,
            digest,
            expected,
        )
        return False
    return True


EXPECTED_SQLITE_SHA256 = _normalise_checksum(
    os.getenv("DATABASE_RELEASE_SHA256")
    or os.getenv("DATABASE_RELEASE_CHECKSUM")
    or os.getenv("DB_SHA256")
    or os.getenv("DB_CHECKSUM")
)


def _download_sqlite_from_release(
    target: Path, alt_names: Iterable[str], expected_checksum: Optional[str]
) -> bool:
    if os.getenv("DATABASE_RELEASE_SKIP"):
        return False

    asset_hint = os.getenv("DATABASE_RELEASE_ASSET")
    alt_list = [str(name) for name in alt_names if name]
    alt_lower = {name.lower() for name in alt_list}

    for url_candidate, asset_name in _iter_release_urls(asset_hint, alt_list):
        tmp_name: Optional[Path] = None
        try:
            request = urllib.request.Request(
                url_candidate,
                headers={"User-Agent": "papcse-sqlite-loader", "Accept": "application/octet-stream"},
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                with tempfile.NamedTemporaryFile("wb", delete=False) as tmp_file:
                    shutil.copyfileobj(response, tmp_file)
                    tmp_name = Path(tmp_file.name)
        except urllib.error.HTTPError as exc:  # pragma: no cover - réseau
            logger.warning("Téléchargement impossible depuis %s: %s", url_candidate, exc)
            if tmp_name and tmp_name.exists():
                tmp_name.unlink()
            continue
        except Exception as exc:  # pragma: no cover - réseau
            logger.warning("Erreur réseau en téléchargeant %s: %s", url_candidate, exc)
            if tmp_name and tmp_name.exists():
                tmp_name.unlink()
            continue

        try:
            suffix = (asset_name or "").lower()
            if suffix.endswith(".zip"):
                import zipfile

                with zipfile.ZipFile(tmp_name) as archive:
                    members = archive.namelist()
                    chosen = None
                    normalized_hint = asset_hint.lower() if asset_hint else None
                    for member in members:
                        short = Path(member).name
                        lower_short = short.lower()
                        if normalized_hint and lower_short != normalized_hint:
                            continue
                        if (not normalized_hint) and (
                            lower_short not in alt_lower
                            and not lower_short.endswith((".db", ".sqlite", ".sqlite3"))
                        ):
                            continue
                        chosen = member
                        break
                    if not chosen:
                        raise ValueError("Aucun fichier SQLite trouvé dans l'archive de release")
                    with archive.open(chosen) as source, open(target, "wb") as dest:
                        shutil.copyfileobj(source, dest)
            else:
                with tmp_name.open("rb") as source, open(target, "wb") as dest:
                    shutil.copyfileobj(source, dest)

            if expected_checksum and not _check_sqlite_checksum(target, expected_checksum):
                try:
                    target.unlink(missing_ok=True)  # type: ignore[attr-defined]
                except TypeError:
                    if target.exists():
                        target.unlink()
                logger.warning(
                    "Checksum incorrect pour l'asset de release %s, tentative suivante",
                    asset_name or url_candidate,
                )
                continue

            logger.info(
                "Base SQLite téléchargée depuis la release (%s)",
                asset_name or url_candidate,
            )
            return True
        except Exception as exc:  # pragma: no cover - réseau
            logger.warning("Impossible d'utiliser l'asset de release %s: %s", asset_name, exc)
        finally:
            if tmp_name:
                try:
                    tmp_name.unlink(missing_ok=True)  # type: ignore[attr-defined]
                except TypeError:
                    if tmp_name.exists():
                        tmp_name.unlink()

    return False


if IS_SQLITE:
    raw_path = url.database or ""
    candidates = []

    def add_candidate(path_like):
        if not path_like:
            return
        path_obj = Path(path_like).expanduser()
        candidates.append(path_obj)

    def add_directory(dir_like):
        if not dir_like:
            return
        dir_path = Path(dir_like).expanduser()
        directories.append(dir_path)

    search_name = "papcse.db"
    directories = []

    env_hint_dirs = []
    hints_env = os.getenv("DATABASE_SEARCH_PATHS")
    if hints_env:
        env_hint_dirs.extend(Path(p.strip()) for p in hints_env.split(os.pathsep) if p.strip())

    extra_env = {
        "DATABASE_PATH": os.getenv("DATABASE_PATH"),
        "DATABASE_FILE": os.getenv("DATABASE_FILE"),
    }
    for value in extra_env.values():
        if value:
            add_candidate(value)

    env_directories = {
        "DATABASE_DIR": os.getenv("DATABASE_DIR"),
        "RAILWAY_VOLUME_PATH": os.getenv("RAILWAY_VOLUME_PATH"),
    }
    for value in env_directories.values():
        if value:
            env_hint_dirs.append(Path(value))

    if raw_path:
        raw_candidate = Path(raw_path)
        if raw_candidate.name:
            search_name = raw_candidate.name
        if raw_candidate.is_absolute():
            add_candidate(raw_candidate)
            add_directory(raw_candidate.parent)
        else:
            # Préserver le comportement historique : d'abord le chemin tel quel
            add_candidate(raw_candidate)
            add_directory(raw_candidate.parent)
            add_candidate((BASE_DIR / raw_candidate).resolve())
            add_candidate((BASE_DIR / raw_candidate.name).resolve())
            add_directory((BASE_DIR / raw_candidate).resolve().parent)
            add_directory((BASE_DIR / raw_candidate.name).resolve().parent)
            cwd = Path.cwd()
            add_candidate((cwd / raw_candidate).resolve())
            add_candidate((cwd / raw_candidate.name).resolve())
            add_directory((cwd / raw_candidate).resolve().parent)
            add_directory((cwd / raw_candidate.name).resolve().parent)
    else:
        default_candidate = BASE_DIR / search_name
        add_candidate(default_candidate)
        add_directory(default_candidate.parent)

    # Ajouter quelques emplacements communs rencontrés sur les déploiements existants
    common_roots = [
        BASE_DIR,
        BASE_DIR / "app",
        BASE_DIR / "data",
        BASE_DIR.parent,
        BASE_DIR.parent / "data",
        Path.cwd(),
        Path.cwd() / "app",
        Path.cwd() / "data",
        Path("/app"),
        Path("/app/data"),
        Path("/data"),
    ]

    directories.extend(common_roots)
    directories.extend(env_hint_dirs)

    base_stem = Path(search_name).stem or search_name
    alt_names = {
        search_name,
        "papcse.db",
        "papcse.sqlite",
        "papcse.sqlite3",
    }
    if base_stem:
        alt_names.add(base_stem)
        alt_names.add(f"{base_stem}.db")
        alt_names.add(f"{base_stem}.sqlite")
        alt_names.add(f"{base_stem}.sqlite3")

    for directory in directories:
        if not directory:
            continue
        dir_path = Path(directory).expanduser()
        for name in alt_names:
            if not name:
                continue
            add_candidate(dir_path / name)
        if dir_path.exists() and base_stem:
            for pattern in [
                f"*{base_stem}*.db",
                f"*{base_stem}*.sqlite",
                f"*{base_stem}*.sqlite3",
            ]:
                for match in dir_path.glob(pattern):
                    if match.is_file():
                        add_candidate(match)

    # Éliminer les doublons tout en conservant l'ordre d'évaluation
    seen = set()
    ordered_candidates = []
    for candidate in candidates:
        if not candidate:
            continue
        try:
            key = candidate.resolve()
        except FileNotFoundError:
            key = candidate
        if key in seen:
            continue
        ordered_candidates.append(candidate)
        seen.add(key)

    if not ordered_candidates:
        ordered_candidates.append(BASE_DIR / "papcse.db")

    resolved_path = next((c for c in ordered_candidates if c.exists()), ordered_candidates[0])
    resolved_path = resolved_path.expanduser()
    if resolved_path.is_dir():
        resolved_path = resolved_path / "papcse.db"
    if not resolved_path.is_absolute():
        resolved_path = (BASE_DIR / resolved_path).resolve()

    def ensure_parent(path: Path) -> tuple[Path, bool]:
        """Ensure the directory for *path* exists and is writable.

        Returns a tuple ``(final_path, writable)`` where ``final_path`` may be
        updated to fall back to the project directory when the requested
        location cannot be created because of permissions (e.g. read-only
        filesystems in production deployments).
        """

        def fallback_path(original: Path) -> tuple[Path, bool]:
            """Return a writable fallback within the project when possible."""

            fallback = (BASE_DIR / search_name).resolve()
            if fallback == original:
                return original, False
            fallback_parent = fallback.parent
            if not fallback_parent.exists():
                try:
                    fallback_parent.mkdir(parents=True, exist_ok=True)
                except Exception as exc:  # pragma: no cover - dépend du FS
                    logger.warning(
                        "Impossible de préparer le dossier de secours %s: %s",
                        fallback_parent,
                        exc,
                    )
                    return original, False
            if not os.access(fallback_parent, os.W_OK):
                return original, False
            logger.info(
                "Répertoire %s en lecture seule, repli sur %s",
                original.parent,
                fallback,
            )
            return fallback, True

        candidate = path
        parent = candidate.parent
        if parent.exists():
            if os.access(parent, os.W_OK):
                return candidate, True
            logger.warning(
                "Le répertoire %s n'est pas inscriptible pour la base SQLite",
                parent,
            )
            return fallback_path(candidate)
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            logger.warning(
                "Impossible de créer le dossier %s, utilisation du répertoire local",
                parent,
            )
            return fallback_path(candidate)
        except OSError as exc:
            logger.warning("Erreur en créant le dossier %s: %s", parent, exc)
            return fallback_path(candidate)
        else:
            return candidate, True

    resolved_path, can_write = ensure_parent(resolved_path)

    if resolved_path.exists() and EXPECTED_SQLITE_SHA256:
        if not _check_sqlite_checksum(resolved_path, EXPECTED_SQLITE_SHA256):
            if can_write:
                logger.warning(
                    "Téléchargement de la base depuis la release pour rétablir le checksum attendu"
                )
                if not _download_sqlite_from_release(
                    resolved_path, alt_names, EXPECTED_SQLITE_SHA256
                ):
                    logger.error(
                        "Impossible de récupérer une base SQLite correspondant au SHA-256 attendu"
                    )
            else:
                logger.error(
                    "Base SQLite invalide et répertoire non inscriptible: %s", resolved_path
                )
    elif not resolved_path.exists():
        if can_write:
            if not _download_sqlite_from_release(
                resolved_path, alt_names, EXPECTED_SQLITE_SHA256
            ) and EXPECTED_SQLITE_SHA256:
                logger.error(
                    "Aucun téléchargement de base SQLite ne correspond au SHA-256 attendu"
                )
        else:
            logger.error(
                "Impossible de créer la base SQLite dans un répertoire non inscriptible: %s",
                resolved_path.parent,
            )

    url = url.set(database=str(resolved_path))
    DATABASE_URL = str(url)
