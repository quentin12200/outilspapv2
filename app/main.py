# app/main.py

import os
import glob
import hashlib
import urllib.request
import logging
import math
import re
import secrets
import shutil
import unicodedata
import tempfile
import calendar
from types import SimpleNamespace
from urllib.parse import urlparse, urlencode
from fastapi import FastAPI, Request, Depends, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, FileResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_, update
from sqlalchemy.orm import Session
from typing import Any, Mapping, Iterator, Sequence, Optional
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from io import BytesIO

# --- Imports bas niveau (engine/Base) d'abord ---
from .db import get_session, Base, engine, SessionLocal
from datetime import date, datetime, timedelta

from .models import (
    Invitation,
    SiretSummary,
    PVEvent,
    Cartographie,
    ServiceCartographie,
    Retroplanning,
    PhaseRetroplanning
)
from .services.calcul_elus_cse import (
    calculer_nombre_elus_cse,
    repartir_sieges_quotient_puis_plus_forte_moyenne,
    repartir_sieges_quotient_seul,
    calculer_elus_cse_complet,
    ORGANISATIONS_LABELS
)
from .auth import ADMIN_API_KEY
from .user_auth import (
    hash_password,
    verify_password,
    validate_email,
    validate_password_strength,
    authenticate_user,
    get_client_ip,
    create_user_session_token,
    get_current_user_or_none,
    get_current_user,
    require_admin_user,
    is_admin_user,
    is_public_route,
    USER_SESSION_COOKIE_NAME,
    USER_SESSION_MAX_AGE,
    UserAuthException
)
from .models import User, PasswordResetToken, DataExportRequest
import uuid
from .services.export_service import generate_calendrier_excel
from .services.email_service import get_resend_service

# =========================================================
# Bootstrap DB (AVANT d'importer les routers)
# =========================================================

DB_URL = os.getenv("DB_URL", "").strip()                # URL de l'asset Release GitHub
DB_SHA256 = os.getenv("DB_SHA256", "").lower().strip()  # Empreinte optionnelle
DB_GH_TOKEN = os.getenv("DB_GH_TOKEN", "").strip() or None  # Token si repo privé
DB_FAIL_ON_HASH_MISMATCH = os.getenv("DB_FAIL_ON_HASH_MISMATCH", "").strip().lower()

INVITATIONS_URL = os.getenv("INVITATIONS_URL", "").strip()
INVITATIONS_SHA256 = os.getenv("INVITATIONS_SHA256", "").lower().strip()
INVITATIONS_GH_TOKEN = os.getenv("INVITATIONS_GH_TOKEN", "").strip() or DB_GH_TOKEN
INVITATIONS_FAIL_ON_HASH_MISMATCH = os.getenv("INVITATIONS_FAIL_ON_HASH_MISMATCH", "").strip().lower()
INVITATIONS_AUTO_IMPORT = os.getenv("INVITATIONS_AUTO_IMPORT", "false").strip().lower() in {"1", "true", "yes", "on"}

_DEFAULT_KIT_PDF_GITHUB = (
    "https://github.com/quentin12200/outilspapv2/releases/download/v1.0.0/Kit.renforcement.compile.30.06.2025.pour.impression.pdf"
)
_DEFAULT_KIT_PDF_ONEDRIVE = (
    "https://1drv.ms/f/c/7bb16296eeed7fa3/Eh42VXPwAUpAlwK_jNGlf2sBAbKGzOahFc2AGh9OR1VbuA?e=yFBDHw"
)

# Restaurer GitHub comme source principale (fonctionnait avant)
KIT_PDF_URL = os.getenv("KIT_PDF_URL", _DEFAULT_KIT_PDF_GITHUB).strip()
KIT_PDF_FILENAME = os.getenv(
    "KIT_PDF_FILENAME",
    "Kit.renforcement.compile.30.06.2025.pour.impression.pdf",
).strip()
KIT_PDF_URLS = os.getenv("KIT_PDF_URLS", "").strip()
KIT_PDF_URL_FALLBACKS = os.getenv("KIT_PDF_URL_FALLBACKS", _DEFAULT_KIT_PDF_ONEDRIVE).strip()
KIT_PDF_LOCAL_PATH = os.getenv("KIT_PDF_LOCAL_PATH", "").strip()
KIT_PDF_LOCAL_PATHS = os.getenv("KIT_PDF_LOCAL_PATHS", "").strip()

_DEFAULT_DATA_DIR = os.path.join(os.getcwd(), "app", "data")

# Chemin par défaut du PDF dans app/data/kit/ si pas de chemin configuré
_DEFAULT_KIT_LOCAL_PATH = os.path.join(os.getcwd(), "app", "data", "kit", "Kit.renforcement.compile.30.06.2025.pour.impression.pdf")
if not KIT_PDF_LOCAL_PATH and os.path.exists(_DEFAULT_KIT_LOCAL_PATH):
    KIT_PDF_LOCAL_PATH = _DEFAULT_KIT_LOCAL_PATH
    logger.info(f"Utilisation du PDF local par défaut: {_DEFAULT_KIT_LOCAL_PATH}")

_DEFAULT_KIT_CACHE_DIR = os.path.join(os.getcwd(), "app", "data", "kit")
KIT_PDF_CACHE_ENABLED = os.getenv("KIT_PDF_CACHE_ENABLED", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
KIT_PDF_AUTO_WARM = os.getenv("KIT_PDF_AUTO_WARM", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
KIT_PDF_CACHE_DIR = os.getenv("KIT_PDF_CACHE_DIR", _DEFAULT_KIT_CACHE_DIR).strip() or _DEFAULT_KIT_CACHE_DIR
if KIT_PDF_CACHE_ENABLED:
    KIT_PDF_CACHE_PATH = os.path.join(
        KIT_PDF_CACHE_DIR,
        KIT_PDF_FILENAME or "Kit-renforcement.pdf",
    )
else:
    KIT_PDF_CACHE_PATH = ""


def _infer_invitation_urls() -> list[str]:
    """Tente de déduire les URLs possibles des invitations à partir de `DB_URL`.

    Pour éviter de devoir re-téléverser le fichier à chaque déploiement, on part
    du principe que le fichier SQLite et le fichier Excel des invitations sont
    hébergés sur la même release GitHub. Plusieurs noms courants sont testés :

    - même nom que la base mais avec une extension `.xlsx` / `.csv`
    - suffixe `-invitations` ajouté au nom du fichier
    """

    urls: list[str] = []

    if INVITATIONS_URL or not DB_URL:
        return urls  # La configuration explicite reste prioritaire

    parsed = urlparse(DB_URL)
    if parsed.scheme not in {"http", "https"}:
        return urls

    path = parsed.path or ""
    directory, filename = os.path.split(path)
    if not filename:
        return urls

    stem, ext = os.path.splitext(filename)
    if not stem:
        return urls

    candidates = []
    for candidate_ext in (".xlsx", ".csv"):
        candidates.append(os.path.join(directory, f"{stem}{candidate_ext}"))
        candidates.append(os.path.join(directory, f"{stem}-invitations{candidate_ext}"))

    for candidate in candidates:
        inferred = parsed._replace(path=candidate).geturl()
        if inferred != DB_URL and inferred not in urls:
            urls.append(inferred)

    return urls


INVITATIONS_INFERRED_URLS = _infer_invitation_urls()
INVITATIONS_EFFECTIVE_URL: str | None = None


def _is_truthy(value: str) -> bool:
    return value in {"1", "true", "yes", "on"}


def _safe_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _split_url_list(raw: str) -> list[str]:
    if not raw:
        return []
    parts = re.split(r"[\s,]+", raw)
    return [part.strip() for part in parts if part.strip()]


def _split_path_list(raw: str) -> list[str]:
    if not raw:
        return []
    parts = re.split(r"[\s,;]+", raw)
    return [part.strip() for part in parts if part.strip()]


KIT_PDF_EXPECTED_SIZE_MB = _safe_int(os.getenv("KIT_PDF_EXPECTED_SIZE_MB"), 115)
KIT_PDF_MIN_SIZE_MB = _safe_int(
    os.getenv("KIT_PDF_MIN_SIZE_MB"),
    max(80, KIT_PDF_EXPECTED_SIZE_MB - 5),
)
KIT_PDF_MIN_SIZE_BYTES = max(1, KIT_PDF_MIN_SIZE_MB) * 1024 * 1024


def _build_local_kit_candidates() -> list[str]:
    hints: list[str] = []

    if KIT_PDF_CACHE_ENABLED and KIT_PDF_CACHE_PATH:
        hints.append(KIT_PDF_CACHE_PATH)

    for raw in (KIT_PDF_LOCAL_PATH, KIT_PDF_LOCAL_PATHS):
        for entry in _split_path_list(raw):
            hints.append(entry)

    if KIT_PDF_FILENAME:
        hints.append(os.path.join(_DEFAULT_DATA_DIR, KIT_PDF_FILENAME))
        hints.append(os.path.join(_DEFAULT_DATA_DIR, "kit", KIT_PDF_FILENAME))

    hints.append(os.path.join(_DEFAULT_DATA_DIR, "kit", "Kit.renforcement.compile.30.06.2025.pour.impression.pdf"))
    hints.append(os.path.join(_DEFAULT_DATA_DIR, "Kit.renforcement.compile.30.06.2025.pour.impression.pdf"))

    normalized: list[str] = []
    seen: set[str] = set()
    for hint in hints:
        if not hint:
            continue
        abs_path = os.path.abspath(os.path.expanduser(hint))
        if abs_path not in seen:
            normalized.append(abs_path)
            seen.add(abs_path)
    return normalized


KIT_PDF_LOCAL_HINTS = _build_local_kit_candidates()
KIT_PDF_LOCAL_GLOBS = []


def _kit_candidate_is_valid(path: str | None) -> bool:
    if not path:
        return False
    try:
        if not os.path.exists(path):
            return False
        size = os.path.getsize(path)
    except OSError:
        return False

    if size < KIT_PDF_MIN_SIZE_BYTES:
        logger.debug(
            "Fichier PDF ignoré (%s): taille %s < seuil %s",
            path,
            size,
            KIT_PDF_MIN_SIZE_BYTES,
        )
        return False

    return True


def _is_valid_kit_size(path: str | None) -> bool:
    if not path:
        return False
    try:
        return os.path.getsize(path) >= KIT_PDF_MIN_SIZE_BYTES
    except OSError:
        return False


def _find_local_kit_pdf() -> str | None:
    """Retourne le chemin d'un PDF déjà présent dans app/data (ou via les hints)."""

    for candidate in KIT_PDF_LOCAL_HINTS:
        if _kit_candidate_is_valid(candidate):
            return os.path.abspath(candidate)

    for pattern in KIT_PDF_LOCAL_GLOBS:
        for match in sorted(glob.glob(pattern)):
            if _kit_candidate_is_valid(match):
                return os.path.abspath(match)

    return None


def _kit_pdf_cache_ready() -> bool:
    if not KIT_PDF_CACHE_ENABLED or not KIT_PDF_CACHE_PATH:
        return False
    try:
        return _is_valid_kit_size(KIT_PDF_CACHE_PATH)
    except OSError:
        return False


def _ensure_kit_pdf_cached(force_refresh: bool = False) -> str | None:
    if not KIT_PDF_CACHE_ENABLED or not KIT_PDF_CACHE_PATH:
        local_path = _find_local_kit_pdf()
        return local_path

    if _kit_pdf_cache_ready() and not force_refresh:
        if _is_valid_kit_size(KIT_PDF_CACHE_PATH):
            return KIT_PDF_CACHE_PATH
        try:
            os.remove(KIT_PDF_CACHE_PATH)
        except OSError:
            pass

    local_source = _find_local_kit_pdf()
    if local_source:
        os.makedirs(os.path.dirname(KIT_PDF_CACHE_PATH), exist_ok=True)
        if os.path.abspath(local_source) != os.path.abspath(KIT_PDF_CACHE_PATH):
            shutil.copy2(local_source, KIT_PDF_CACHE_PATH)
            logger.info(
                "Kit renforcement copié depuis %s vers %s",
                local_source,
                KIT_PDF_CACHE_PATH,
            )
        else:
            logger.info("Kit renforcement déjà présent dans %s", KIT_PDF_CACHE_PATH)
        if _is_valid_kit_size(KIT_PDF_CACHE_PATH):
            return KIT_PDF_CACHE_PATH
        logger.warning(
            "Le PDF local %s est trop léger (< %s Mo), suppression et téléchargement depuis la release",
            KIT_PDF_CACHE_PATH,
            KIT_PDF_MIN_SIZE_MB,
        )
        try:
            os.remove(KIT_PDF_CACHE_PATH)
        except OSError:
            pass

    if not KIT_PDF_URL_CANDIDATES:
        return KIT_PDF_CACHE_PATH if _kit_pdf_cache_ready() else None

    os.makedirs(os.path.dirname(KIT_PDF_CACHE_PATH), exist_ok=True)

    last_error: Exception | None = None
    for candidate in KIT_PDF_URL_CANDIDATES:
        tmp_path: str | None = None
        try:
            logger.info("Téléchargement du kit de renforcement via %s", candidate)
            # Utiliser le token GitHub si l'URL est sur github.com
            token = DB_GH_TOKEN if "github.com" in candidate else None
            tmp_path = _download_to_temp(candidate, token=token, timeout=KIT_PDF_TIMEOUT)
            with open(tmp_path, "rb") as handle:
                header = handle.read(5)
                if not header.startswith(b"%PDF-"):
                    raise ValueError("La ressource récupérée n'est pas un PDF valide")
            os.replace(tmp_path, KIT_PDF_CACHE_PATH)
            tmp_path = None
            if not _is_valid_kit_size(KIT_PDF_CACHE_PATH):
                raise ValueError(
                    f"Document téléchargé trop léger (< {KIT_PDF_MIN_SIZE_MB} Mo)"
                )
            logger.info("Kit renforcement mis en cache (%s)", KIT_PDF_CACHE_PATH)
            return KIT_PDF_CACHE_PATH
        except Exception as exc:  # pragma: no cover - dépend du réseau
            last_error = exc
            logger.warning("Échec du téléchargement du kit via %s: %s", candidate, exc)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    if last_error:
        logger.error("Impossible de mettre en cache le kit PDF: %s", last_error)
    return None


def _build_kit_url_candidates() -> list[str]:
    ordered_sources = [KIT_PDF_URL, KIT_PDF_URLS, KIT_PDF_URL_FALLBACKS]
    urls: list[str] = []
    seen: set[str] = set()
    for source in ordered_sources:
        for candidate in _split_url_list(source):
            if candidate not in seen:
                urls.append(candidate)
                seen.add(candidate)
    return urls


KIT_PDF_URL_CANDIDATES = _build_kit_url_candidates()
KIT_PDF_TIMEOUT = _safe_int(os.getenv("KIT_PDF_TIMEOUT"), 60)


def _kit_pdf_status() -> dict[str, bool]:
    """Expose l'état actuel du kit PDF pour l'interface (inline vs streaming)."""

    inline_ready = False

    if KIT_PDF_CACHE_ENABLED:
        if _kit_pdf_cache_ready():
            inline_ready = True
        else:
            inline_ready = _find_local_kit_pdf() is not None
    else:
        inline_ready = _find_local_kit_pdf() is not None

    download_ready = inline_ready or bool(KIT_PDF_URL_CANDIDATES)

    return {
        "inline_ready": inline_ready,
        "download_ready": download_ready,
        "remote_only": download_ready and not inline_ready,
    }

_HASH_CACHE: dict[str, tuple[float, int, str]] = {}


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _cached_sha256(path: str) -> str:
    """Calcule (ou retrouve) le hash SHA256 d'un fichier en mettant en cache l'empreinte."""

    try:
        stat_result = os.stat(path)
    except OSError:
        return ""

    cached = _HASH_CACHE.get(path)
    signature = (stat_result.st_mtime, stat_result.st_size)
    if cached and cached[0] == signature[0] and cached[1] == signature[1]:
        return cached[2]

    digest = _sha256_file(path).lower()
    _HASH_CACHE[path] = (signature[0], signature[1], digest)
    return digest

def _sqlite_path_from_engine() -> str | None:
    try:
        if engine.url.get_backend_name() == "sqlite":
            db_path = engine.url.database
            if db_path and db_path != ":memory:":
                return db_path
    except Exception:
        pass
    return None

def _download(
    url: str,
    dest: str,
    token: str | None = None,
    *,
    timeout: int | float | None = None,
) -> None:
    headers = {"Accept": "application/octet-stream"}
    if token:
        headers["Authorization"] = f"token {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp, open(dest, "wb") as f:
        f.write(resp.read())

logger = logging.getLogger(__name__)


def _download_to_temp(
    url: str,
    token: str | None = None,
    *,
    timeout: int | float | None = None,
) -> str:
    """Télécharge un fichier distant vers un fichier temporaire et retourne son chemin."""
    suffix = os.path.splitext(urlparse(url).path)[1]
    fd, tmp_path = tempfile.mkstemp(prefix="papcse-asset-", suffix=suffix or "")
    os.close(fd)
    try:
        _download(url, tmp_path, token=token, timeout=timeout)
        return tmp_path
    except Exception:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise


def _log_or_raise_hash_mismatch(label: str, expected: str, got: str, downloaded: bool, fail_flag: str) -> None:
    message = (
        f"SHA256 mismatch for {label}:\n"
        f"  got:  {got}\n"
        f"  want: {expected}"
    )
    if downloaded and _is_truthy(fail_flag):
        raise RuntimeError(message)

    level = logging.ERROR if downloaded else logging.WARNING
    logger.log(level, "%s -- continuing.", message)


def _stream_remote_asset(
    url_or_urls: str | Sequence[str], *, accept: str = "application/octet-stream"
) -> tuple[Iterator[bytes], int | None]:
    """Retourne un itérateur streaming + longueur depuis une ou plusieurs URLs distantes."""

    if isinstance(url_or_urls, str):
        candidates = [url_or_urls]
    else:
        candidates = list(url_or_urls)

    candidates = [candidate for candidate in candidates if candidate]
    if not candidates:
        raise HTTPException(status_code=404, detail="Aucune ressource distante configurée")

    last_error: Exception | None = None
    headers = {
        "Accept": accept,
        "User-Agent": "PAPCSE/1.0 (+https://outilspap.cgt.fr)",
    }

    response = None
    for candidate in candidates:
        request = urllib.request.Request(candidate, headers=headers)
        try:
            response = urllib.request.urlopen(request, timeout=KIT_PDF_TIMEOUT)
            logger.info("Kit PDF récupéré via %s", candidate)
            break
        except Exception as exc:  # pragma: no cover - dépend du réseau
            last_error = exc
            logger.warning("Échec du chargement %s: %s", candidate, exc)
            continue
    else:
        raise HTTPException(
            status_code=502,
            detail="Impossible de récupérer le document distant",
        ) from last_error

    assert response is not None  # pour les analyseurs statiques

    def iterator(resp=response) -> Iterator[bytes]:
        with resp:
            while True:
                chunk = resp.read(1024 * 64)
                if not chunk:
                    break
                yield chunk

    content_length = response.headers.get("Content-Length")
    try:
        length_value = int(content_length) if content_length else None
    except (TypeError, ValueError):
        length_value = None

    return iterator, length_value


def ensure_sqlite_asset() -> None:
    """
    Garantit que le fichier SQLite existe au chemin visé par l'engine:
    - crée le dossier parent
    - télécharge depuis DB_URL si absent
    - vérifie SHA256 si fourni
    """
    db_path = _sqlite_path_from_engine()
    if not db_path:
        return

    parent = os.path.dirname(db_path) or "."
    os.makedirs(parent, exist_ok=True)

    downloaded = False
    if DB_URL and not os.path.exists(db_path):
        _download(DB_URL, db_path, token=DB_GH_TOKEN)
        downloaded = True

    if DB_SHA256 and os.path.exists(db_path):
        digest = _sha256_file(db_path).lower()
        if digest != DB_SHA256:
            _log_or_raise_hash_mismatch(
                f"DB file at {db_path}",
                DB_SHA256,
                digest,
                downloaded,
                DB_FAIL_ON_HASH_MISMATCH,
            )


def _auto_seed_invitations(session: Session) -> None:
    """Importe automatiquement les invitations depuis une release si la table est vide."""
    global INVITATIONS_EFFECTIVE_URL

    if not INVITATIONS_AUTO_IMPORT:
        logger.info("Automatic invitation import is disabled (INVITATIONS_AUTO_IMPORT=false)")
        return

    candidates: list[tuple[str, str, str]] = []
    if INVITATIONS_URL:
        candidates.append(("configuration", INVITATIONS_URL, INVITATIONS_SHA256))
    for inferred in INVITATIONS_INFERRED_URLS:
        candidates.append(("déduction", inferred, ""))

    if not candidates:
        return

    existing = session.query(func.count(Invitation.id)).scalar() or 0
    if existing > 0:
        logger.info(
            "Skipping automatic invitation import: table already contains %s rows.",
            existing,
        )
        return

    last_error: Exception | None = None
    for origin, url, expected_sha in candidates:
        tmp_path: str | None = None
        try:
            logger.info("Trying automatic invitation import (%s): %s", origin, url)
            tmp_path = _download_to_temp(url, token=INVITATIONS_GH_TOKEN)
            if expected_sha:
                digest = _sha256_file(tmp_path).lower()
                if digest != expected_sha:
                    _log_or_raise_hash_mismatch(
                        "invitations seed",
                        expected_sha,
                        digest,
                        True,
                        INVITATIONS_FAIL_ON_HASH_MISMATCH,
                    )

            from . import etl  # Import tardif pour éviter les références circulaires

            inserted = etl.ingest_invit_excel(session, tmp_path)
            INVITATIONS_EFFECTIVE_URL = url
            logger.info(
                "Automatically imported %s invitations from %s.",
                inserted,
                url,
            )
            return
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code == 404:
                logger.info("Automatic invitation import: file not found at %s (404)", url)
            else:
                logger.exception("Automatic invitation import failed with %s", url)
        except Exception as exc:
            last_error = exc
            logger.exception("Automatic invitation import failed with %s", url)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    if last_error:
        if isinstance(last_error, urllib.error.HTTPError) and last_error.code == 404:
            logger.info(
                "No invitation files found at inferred URLs; proceeding without automatic seeding. "
                "This is normal if invitations are manually uploaded."
            )
        else:
            logger.warning(
                "Automatic invitation import failed for all candidates; proceeding without seeding: %s",
                last_error,
            )

# Télécharge/ prépare le fichier AVANT d’importer les routers
ensure_sqlite_asset()

# =========================================================
# App & Routers
# =========================================================

# ⚠️ Import des routers APRÈS ensure_sqlite_asset()
from .routers import api  # noqa: E402
from .routers import api_invitations_stats  # noqa: E402
from .routers import api_geo_stats  # noqa: E402
from .routers import api_idcc_enrichment  # noqa: E402
from .routers import api_document_extraction  # noqa: E402
from .routers import api_chatbot  # noqa: E402
from .routers import api_email  # noqa: E402

app = FastAPI(title="PAP/CSE · Tableau de bord")

# Gestionnaire d'exceptions pour l'authentification utilisateur
@app.exception_handler(UserAuthException)
async def user_auth_exception_handler(request: Request, exc: UserAuthException):
    """Redirige vers la page de login utilisateur quand l'authentification échoue"""
    return RedirectResponse(url=exc.redirect_url, status_code=303)


# Middleware pour vérifier l'authentification utilisateur
@app.middleware("http")
async def authentication_middleware(request: Request, call_next):
    """
    Middleware pour protéger les routes et rediriger les utilisateurs non connectés.
    Les routes publiques (signup, login, static, etc.) ne sont pas protégées.
    """
    path = request.url.path

    # Vérifier si la route est publique
    if is_public_route(path):
        response = await call_next(request)
        return response

    # Pour les routes protégées, vérifier l'authentification
    session_token = request.cookies.get(USER_SESSION_COOKIE_NAME)

    if not session_token:
        # Pas de session, rediriger vers login
        return RedirectResponse(url="/login", status_code=303)

    # Vérifier que le token est valide
    from .user_auth import verify_user_session_token
    session_data = verify_user_session_token(session_token)

    if not session_data:
        # Token invalide ou expiré, rediriger vers login
        return RedirectResponse(url="/login", status_code=303)

    # Vérifier que l'utilisateur existe et est approuvé
    db = SessionLocal()
    try:
        user = db.query(User).filter(
            User.id == session_data["user_id"],
            User.is_approved == True,
            User.is_active == True
        ).first()

        if not user:
            # Utilisateur non trouvé, pas approuvé, ou inactif
            return RedirectResponse(url="/login", status_code=303)

        # Utilisateur authentifié, continuer
        response = await call_next(request)
        return response
    finally:
        db.close()

# Activer l'audit logging middleware
from .audit import create_audit_middleware
app.middleware("http")(create_audit_middleware())

app.include_router(api.router)
app.include_router(api_invitations_stats.router)
app.include_router(api_geo_stats.router)
app.include_router(api_idcc_enrichment.router)
app.include_router(api_document_extraction.router)
app.include_router(api_chatbot.router)
app.include_router(api_email.router)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# Ajouter un filtre Jinja2 personnalisé pour nettoyer les valeurs "nan"
def clean_nan_filter(value):
    """Filtre Jinja2 pour convertir 'nan' en None ou valeur par défaut."""
    if value is None:
        return None
    if isinstance(value, str):
        # Vérifier si la valeur est "nan" (insensible à la casse)
        if value.strip().lower() in {'nan', 'none', 'null'}:
            return None
    return value

templates.env.filters["clean_nan"] = clean_nan_filter


# Ajouter une fonction globale pour récupérer l'utilisateur connecté dans les templates
def get_current_user_from_request(request):
    """Fonction globale Jinja2 pour récupérer l'utilisateur connecté"""
    return getattr(request.state, "current_user", None)


templates.env.globals["get_current_user"] = get_current_user_from_request


# Ajouter un context processor pour injecter l'utilisateur connecté dans tous les templates
@app.middleware("http")
async def add_user_to_context(request: Request, call_next):
    """
    Middleware pour ajouter l'utilisateur connecté au contexte de tous les templates.
    """
    # Essayer de récupérer l'utilisateur connecté
    db = SessionLocal()
    try:
        current_user = get_current_user_or_none(request, db)
        # Stocker l'utilisateur dans request.state pour qu'il soit accessible
        request.state.current_user = current_user
    except Exception:
        request.state.current_user = None
    finally:
        db.close()

    response = await call_next(request)
    return response


def _check_and_fix_schema():
    """Vérifie que le schéma de siret_summary est à jour et le recrée si nécessaire."""
    logger.info("🔍 [STARTUP] Checking siret_summary schema...")

    from sqlalchemy import inspect, text

    try:
        logger.debug("Creating database inspector...")
        inspector = inspect(engine)

        logger.debug("Checking if siret_summary table exists...")
        if not inspector.has_table('siret_summary'):
            logger.info("✓ Table siret_summary does not exist yet, will be created by create_all")
            return

        logger.debug("Getting existing columns from siret_summary...")
        existing_columns = {col['name'] for col in inspector.get_columns('siret_summary')}
        logger.debug(f"Found {len(existing_columns)} existing columns")

        logger.debug("Getting required columns from model...")
        required_columns = {col.name for col in SiretSummary.__table__.columns}
        logger.debug(f"Need {len(required_columns)} required columns")

        missing = required_columns - existing_columns
        if not missing:
            logger.info("✓ siret_summary schema is up to date")
            return

        # Schema mismatch - on doit recréer la table
        logger.warning(f"⚠️  Schema mismatch: siret_summary is missing {len(missing)} columns: {', '.join(sorted(missing)[:10])}")
        logger.info("🔧 Dropping and recreating siret_summary table...")

        # Utiliser une connexion raw pour le DROP
        logger.debug("Executing DROP TABLE...")
        with engine.connect() as conn:
            conn.execute(text("DROP TABLE IF EXISTS siret_summary"))
            conn.commit()

        logger.info("✓ Old table dropped, will be recreated by create_all")
    except Exception as e:
        logger.exception(f"❌ ERROR in _check_and_fix_schema: {e}")
        raise

@app.on_event("startup")
def on_startup():
    # Vérifier et corriger le schéma de siret_summary AVANT create_all
    # pour éviter que create_all ne "verrouille" l'ancien schéma
    _check_and_fix_schema()

    # Création des tables après que le fichier .db soit prêt
    Base.metadata.create_all(bind=engine)

    # Exécute les migrations pour ajouter les colonnes Sirene si nécessaire
    from .migrations import run_migrations
    run_migrations()

    # Si le résumé SIRET est vide, le reconstruire automatiquement (ou non selon config)
    # afin que le tableau de bord ne s'affiche pas avec des compteurs à zéro lors du
    # premier démarrage (base préremplie).
    try:
        with SessionLocal() as session:
            _auto_seed_invitations(session)
            total_summary = session.query(func.count(SiretSummary.siret)).scalar() or 0

            if total_summary == 0:
                from .config import AUTO_BUILD_SUMMARY_ON_STARTUP

                if AUTO_BUILD_SUMMARY_ON_STARTUP:
                    # Mode synchrone : reconstruction immédiate au démarrage (peut causer timeout)
                    from . import etl
                    generated = etl.build_siret_summary(session)
                    logger.info("Siret summary rebuilt at startup (%s rows)", generated)
                else:
                    # Mode recommandé : log seulement, l'admin doit lancer manuellement via API
                    logger.warning(
                        "⚠️  siret_summary table is empty. "
                        "Please trigger rebuild manually via POST /api/build/summary"
                    )
    except Exception:  # pragma: no cover - protection démarrage
        logger.exception("Unable to rebuild siret_summary at startup")

    # Créer le compte super admin si il n'existe pas
    _ensure_super_admin_exists()


def _ensure_super_admin_exists():
    """
    Crée automatiquement le compte super admin au démarrage si il n'existe pas.

    L'email du super admin est défini par SUPER_ADMIN_EMAIL (défaut: leyrat.quentin@gmail.com).
    Le mot de passe initial est défini par SUPER_ADMIN_PASSWORD (défaut: généré aléatoirement).
    """
    super_admin_email = os.getenv("SUPER_ADMIN_EMAIL", "leyrat.quentin@gmail.com")
    super_admin_password = os.getenv("SUPER_ADMIN_PASSWORD")

    try:
        with SessionLocal() as session:
            # Vérifier si le super admin existe déjà
            existing_admin = session.query(User).filter(User.email == super_admin_email).first()

            if existing_admin:
                # Le super admin existe déjà
                # S'assurer qu'il a bien le role admin et qu'il est approuvé
                updated = False

                if existing_admin.role != "admin" or not existing_admin.is_approved or not existing_admin.is_active:
                    existing_admin.role = "admin"
                    existing_admin.is_approved = True
                    existing_admin.is_active = True
                    updated = True
                    logger.info(f"✅ Super admin {super_admin_email} - role et statut mis à jour")

                # Mettre à jour le mot de passe si SUPER_ADMIN_PASSWORD est défini
                if super_admin_password:
                    existing_admin.hashed_password = hash_password(super_admin_password)
                    updated = True
                    logger.info(f"✅ Super admin {super_admin_email} - mot de passe mis à jour depuis SUPER_ADMIN_PASSWORD")

                if updated:
                    session.commit()
                    logger.info(f"🔄 Super admin {super_admin_email} mis à jour avec succès")
                else:
                    logger.info(f"✅ Super admin {super_admin_email} existe déjà et est à jour")

                return

            # Générer un mot de passe aléatoire si non fourni
            if not super_admin_password:
                import string
                import random
                # Générer un mot de passe sécurisé de 16 caractères
                chars = string.ascii_letters + string.digits + "!@#$%^&*"
                super_admin_password = ''.join(random.choice(chars) for _ in range(16))
                logger.warning(
                    f"⚠️  Mot de passe super admin généré automatiquement: {super_admin_password}\n"
                    f"    Définissez SUPER_ADMIN_PASSWORD dans les variables d'environnement pour un mot de passe personnalisé."
                )

            # Créer le super admin
            super_admin = User(
                email=super_admin_email,
                hashed_password=hash_password(super_admin_password),
                first_name="Quentin",
                last_name="Leyrat",
                phone=None,
                organization="CGT",
                fd=None,
                ud=None,
                region=None,
                responsibility="Super Administrateur",
                registration_reason="Compte super admin créé automatiquement",
                registration_ip="127.0.0.1",
                is_approved=True,  # Automatiquement approuvé
                is_active=True,
                role="admin"  # Role admin
            )

            session.add(super_admin)
            session.commit()

            logger.info(f"🎉 Super admin créé avec succès : {super_admin_email}")
            if not os.getenv("SUPER_ADMIN_PASSWORD"):
                logger.warning(f"    Mot de passe: {super_admin_password}")
                logger.warning(f"    ⚠️  IMPORTANT : Changez ce mot de passe après la première connexion !")

    except Exception as e:
        logger.exception(f"❌ Erreur lors de la création du super admin: {e}")


@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/presentation", response_class=HTMLResponse)
def presentation(request: Request, db: Session = Depends(get_session)):
    total_sirets = db.query(func.count(SiretSummary.siret)).scalar() or 0
    invitations_total = db.query(func.count(Invitation.id)).scalar() or 0
    pap_sirets = (
        db.query(func.count(func.distinct(Invitation.siret)))
        .filter(Invitation.siret.isnot(None))
        .scalar()
        or 0
    )
    c4_carence = (
        db.query(func.count(SiretSummary.siret))
        .filter(SiretSummary.carence_c4.is_(True))
        .scalar()
        or 0
    )

    capability_cards = [
        {
            "title": "Cartographier les priorités",
            "description": "Visualisez les établissements à fort enjeu et leurs invitations PAP pour planifier les relances.",
            "icon": "fa-bullseye",
        },
        {
            "title": "Coordonner les équipes",
            "description": "Partagez une base commune entre confédération, fédérations et UD pour suivre l’avancement.",
            "icon": "fa-people-arrows",
        },
        {
            "title": "Mesurer l’impact",
            "description": "Reliez chaque invitation aux PV C5 afin de suivre les voix CGT et les carences évitées.",
            "icon": "fa-chart-line",
        },
    ]

    journey_steps = [
        {
            "title": "Réception du PAP",
            "description": "L’invitation est enregistrée avec sa date, son UD et ses contacts référents.",
            "icon": "fa-envelope-open-text",
            "focus": "Point de départ",
        },
        {
            "title": "Mobilisation et ciblage",
            "description": "Les équipes croisent invitations et historiques C3/C4 pour prioriser les actions.",
            "icon": "fa-users-gear",
            "focus": "Organisation",
        },
        {
            "title": "Scrutin C5",
            "description": "Les PV sont collectés, les voix CGT intégrées et les carences signalées.",
            "icon": "fa-file-circle-check",
            "focus": "Résultat",
        },
        {
            "title": "Bilan et relance",
            "description": "Les indicateurs alimentent les bilans confédéraux et préparent la vague suivante.",
            "icon": "fa-arrows-rotate",
            "focus": "Boucle continue",
        },
    ]

    module_links = [
        {
            "title": "Tableau de bord",
            "description": "Indicateurs clés, audiences et focus ≥ 1 000 inscrit·es.",
            "icon": "fa-gauge-high",
            "href": "/",
        },
        {
            "title": "Invitations PAP",
            "description": "Recherche, filtres UD/FD et suivi des dates C5.",
            "icon": "fa-envelope-circle-check",
            "href": "/invitations",
        },
        {
            "title": "Calendrier C5",
            "description": "Projection des scrutins ≥ 1 000 inscrit·es pour anticiper le terrain.",
            "icon": "fa-calendar-days",
            "href": "/calendrier",
        },
        {
            "title": "Recherche SIRET",
            "description": "Interrogation Sirene et fiche détaillée des établissements.",
            "icon": "fa-magnifying-glass",
            "href": "/recherche-siret",
        },
        {
            "title": "Mes ciblages",
            "description": "Imports C3/C4 pour croiser les audiences et préparer les campagnes.",
            "icon": "fa-layer-group",
            "href": "/ciblage",
        },
    ]

    resource_links = [
        {
            "title": "Importer les invitations PAP",
            "icon": "fa-upload",
            "href": "/admin#invitations",
            "description": "Pas-à-pas pour charger ou mettre à jour vos fichiers PAP C5.",
        },
        {
            "title": "Recalculer le résumé SIRET",
            "icon": "fa-rotate",
            "href": "/admin#resume",
            "description": "Relancer la consolidation des données C3/C4 après import.",
        },
        {
            "title": "Configurer Railway",
            "icon": "fa-rocket",
            "href": "/admin#configuration",
            "description": "Variables d’environnement et téléchargement automatique de la base.",
        },
        {
            "title": "Kit ressources C5",
            "icon": "fa-cloud-arrow-down",
            "href": "https://cloud.cgt.fr/public.php/dav/files/jXycqmjkMpYbwXr/?accept=zip",
            "description": "Accéder au dossier partagé (outils, supports et documents de campagne).",
        },
    ]

    faq_entries = [
        {
            "question": "Comment savoir si une invitation est bien reliée à un PV C5 ?",
            "answer": "La fiche SIRET affiche la chronologie PAP → PV avec les dates importées. Vous pouvez aussi utiliser le tri 'PV reçu' dans la page invitations.",
        },
        {
            "question": "Peut-on importer plusieurs fichiers PAP ?",
            "answer": "Oui. Chaque import ajoute ou met à jour les invitations existantes en se basant sur le couple SIRET + date PAP.",
        },
        {
            "question": "Que faire si un SIRET manque d’informations ?",
            "answer": "Lancez une recherche Sirene depuis la fiche SIRET ou utilisez l’onglet 'Recherche SIRET' pour enrichir automatiquement l’établissement.",
        },
    ]

    return templates.TemplateResponse(
        "presentation.html",
        {
            "request": request,
            "total_sirets": total_sirets,
            "invitations_total": invitations_total,
            "pap_sirets": pap_sirets,
            "c4_carence": c4_carence,
            "capability_cards": capability_cards,
            "journey_steps": journey_steps,
            "module_links": module_links,
            "resource_links": resource_links,
            "faq_entries": faq_entries,
        },
    )


@app.get("/guide-exploitation", response_class=HTMLResponse)
def guide_exploitation(request: Request, db: Session = Depends(get_session)):
    """Page de synthèse interactive du guide d'exploitation IA."""

    # Tracker l'activité si l'utilisateur est connecté
    user = get_current_user_or_none(request, db)
    if user:
        from .activity_tracker import track_guide_view
        track_guide_view(db, user)

    if KIT_PDF_CACHE_ENABLED and KIT_PDF_AUTO_WARM:
        _ensure_kit_pdf_cached()

    kit_status = _kit_pdf_status()
    kit_pdf_endpoint = request.app.url_path_for("kit_pdf_document")

    return templates.TemplateResponse(
        "guide_exploitation.html",
        {
            "request": request,
            "kit_pdf_available": kit_status["download_ready"],
            "kit_pdf_inline_ready": kit_status["inline_ready"],
            "kit_pdf_remote_only": kit_status["remote_only"],
            "kit_filename": KIT_PDF_FILENAME or "Kit-renforcement.pdf",
            "kit_pdf_endpoint": kit_pdf_endpoint,
            "kit_pdf_expected_size_mb": KIT_PDF_EXPECTED_SIZE_MB,
        },
    )


@app.get("/kit-election", response_class=HTMLResponse)
def kit_election_page(request: Request):
    """Page du kit élection avec tous les documents disponibles"""
    import os
    from pathlib import Path

    data_dir = Path("app/data")

    # Scanner tous les dossiers et fichiers
    kit_structure = {}
    special_files = []

    # Fichiers spéciaux à la racine
    for item in data_dir.iterdir():
        if item.is_file() and item.suffix.lower() in ['.pdf', '.docx', '.pptx']:
            special_files.append({
                "name": item.name,
                "path": str(item.relative_to("app")),
                "size": item.stat().st_size,
                "type": item.suffix[1:].upper()
            })

    # Dossiers numérotés
    for folder in sorted(data_dir.iterdir()):
        if folder.is_dir():
            folder_name = folder.name
            files_list = []

            # Scanner récursivement
            for root, dirs, files in os.walk(folder):
                for file in files:
                    file_path = Path(root) / file
                    if file_path.suffix.lower() in ['.pdf', '.docx', '.pptx', '.txt']:
                        rel_path = file_path.relative_to(folder)
                        files_list.append({
                            "name": file,
                            "path": str(file_path.relative_to("app")),
                            "rel_path": str(rel_path),
                            "size": file_path.stat().st_size,
                            "type": file_path.suffix[1:].upper()
                        })

            if files_list:
                kit_structure[folder_name] = {
                    "name": folder_name,
                    "files": sorted(files_list, key=lambda x: x["name"])
                }

    return templates.TemplateResponse(
        "kit_election.html",
        {
            "request": request,
            "kit_structure": dict(sorted(kit_structure.items())),
            "special_files": sorted(special_files, key=lambda x: x["name"]),
        },
    )


@app.get("/kit-election/file/{file_path:path}")
async def kit_election_file(file_path: str):
    """Servir un fichier du kit élection"""
    from pathlib import Path
    import mimetypes
    from urllib.parse import unquote

    # Décoder l'URL (espaces et caractères spéciaux)
    file_path = unquote(file_path)

    # Sécurité : vérifier que le chemin est dans app/data
    full_path = Path("app") / file_path

    # Normaliser le chemin et vérifier qu'il est dans app/data
    try:
        full_path = full_path.resolve()
        base_path = Path("app/data").resolve()

        if not str(full_path).startswith(str(base_path)):
            raise HTTPException(status_code=403, detail="Accès refusé")

        if not full_path.exists():
            raise HTTPException(status_code=404, detail="Fichier non trouvé")
    except Exception as e:
        raise HTTPException(status_code=404, detail="Fichier non trouvé")

    # Déterminer le type MIME
    mime_type, _ = mimetypes.guess_type(str(full_path))
    if mime_type is None:
        mime_type = "application/octet-stream"

    return FileResponse(
        path=str(full_path),
        media_type=mime_type,
        filename=full_path.name
    )


# =========================================================
# Routes pour la Cartographie d'Entreprise
# =========================================================

@app.get("/cartographie-entreprise", response_class=HTMLResponse)
def cartographie_entreprise(
    request: Request,
    user: User | None = Depends(get_current_user_or_none),
    db: Session = Depends(get_session)
):
    """Outil de cartographie d'entreprise par services"""

    # Tracker l'activité si l'utilisateur est connecté
    if user:
        from .activity_tracker import track_activity
        track_activity(db, user, "cartographie_view", resource_name="Cartographie d'entreprise")

    return templates.TemplateResponse(
        "cartographie_entreprise.html",
        {
            "request": request,
            "user": user,
        },
    )


_KIT_PDF_PLACEHOLDER_HTML = """<!doctype html><html lang=\"fr\"><head><meta charset=\"utf-8\"><title>Kit renforcement</title><style>body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f8fafc;margin:0;color:#0f172a;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:2rem;} .card{background:#fff;border-radius:1.5rem;box-shadow:0 25px 45px rgba(15,23,42,.12);padding:2.75rem;max-width:520px;text-align:center;} h1{font-size:1.5rem;margin-bottom:0.75rem;} p{font-size:1rem;line-height:1.6;color:#475569;} </style></head><body><div class=\"card\"><h1>Document en cours de préparation</h1><p>Le serveur n'a pas encore pu récupérer le kit PDF. Rechargez cette page dans quelques instants ou utilisez le bouton de téléchargement lorsqu'il s'active.</p></div></body></html>"""
@app.post("/api/cartographie")
async def create_cartographie(
    request: Request,
    nom_entreprise: str | None = Form(None),
    siret: str | None = Form(None),
    services: str | None = Form(None),  # JSON string
    user: User | None = Depends(get_current_user_or_none),
    db: Session = Depends(get_session),
):
    """Créer une nouvelle cartographie d'entreprise"""
    import json

    try:
        payload: dict[str, Any] = {}
        content_type = (request.headers.get("content-type") or "").lower()

        if "application/json" in content_type:
            payload = await request.json()
            nom_entreprise = payload.get("nom_entreprise", nom_entreprise)
            siret = payload.get("siret", siret)
            services = payload.get("services", services)

        if not nom_entreprise or not str(nom_entreprise).strip():
            raise HTTPException(status_code=400, detail="Le nom de l'entreprise est requis")

        raw_services = services
        if raw_services is None:
            raw_services = payload.get("services") if payload else None

        if raw_services is None:
            raise HTTPException(status_code=400, detail="Aucun service fourni")

        if isinstance(raw_services, str):
            services_data = json.loads(raw_services)
        else:
            services_data = raw_services

        if not isinstance(services_data, list) or not services_data:
            raise HTTPException(status_code=400, detail="Format de services invalide")

        # Calculer les totaux
        total_salaries = 0
        total_syndiques = 0

        for service in services_data:
            salaries = max(int(service.get('salaries', 0) or 0), 0)
            syndiques = max(min(int(service.get('syndiques', 0) or 0), salaries), 0)
            total_salaries += salaries
            total_syndiques += syndiques

        taux = (total_syndiques / total_salaries * 100) if total_salaries > 0 else 0

        # Créer la cartographie
        carto = Cartographie(
            siret=siret if siret and str(siret).strip() else None,
            nom_entreprise=str(nom_entreprise).strip(),
            created_by=user.id if user else None,
            total_salaries=total_salaries,
            total_syndiques=total_syndiques,
            taux_syndicalisation=taux,
        )
        db.add(carto)
        db.flush()  # Pour obtenir l'ID

        # Créer les services
        for idx, service_data in enumerate(services_data):
            salaries = max(int(service_data.get('salaries', 0) or 0), 0)
            syndiques = max(min(int(service_data.get('syndiques', 0) or 0), salaries), 0)
            service_taux = (syndiques / salaries * 100) if salaries > 0 else 0

            service = ServiceCartographie(
                cartographie_id=carto.id,
                nom_service=service_data.get('nom', ''),
                nombre_salaries=salaries,
                nombre_syndiques=syndiques,
                taux_syndicalisation=service_taux,
                ordre=idx,
            )
            db.add(service)

        db.commit()

        return {"success": True, "id": carto.id}

    except Exception as e:
        db.rollback()
        logger.error(f"Erreur lors de la création de la cartographie: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/cartographies")
def list_cartographies(
    user: User | None = Depends(get_current_user_or_none),
    db: Session = Depends(get_session),
):
    """Lister les cartographies de l'utilisateur"""
    query = db.query(Cartographie).filter(Cartographie.is_archived == False)

    if user:
        query = query.filter(Cartographie.created_by == user.id)

    cartographies = query.order_by(Cartographie.created_at.desc()).limit(50).all()

    result = []
    for c in cartographies:
        # Charger les services associés
        services = db.query(ServiceCartographie).filter(
            ServiceCartographie.cartographie_id == c.id
        ).order_by(ServiceCartographie.ordre).all()

        result.append({
            "id": c.id,
            "nom_entreprise": c.nom_entreprise,
            "siret": c.siret,
            "total_salaries": c.total_salaries,
            "total_syndiques": c.total_syndiques,
            "taux_syndicalisation": c.taux_syndicalisation,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "services_count": len(services),
            "services": [
                {
                    "nom": s.nom_service,
                    "salaries": s.nombre_salaries,
                    "syndiques": s.nombre_syndiques,
                }
                for s in services
            ]
        })

    return {"cartographies": result}


@app.get("/api/cartographie/fd-inscrits")
def cartographie_fd_inscrits(db: Session = Depends(get_session)):
    """Répartition nationale des inscrit·es par fédération (FD)."""

    fd_rows = (
        db.query(
            func.coalesce(SiretSummary.fd_c4, SiretSummary.fd_c3, "").label("fd"),
            func.coalesce(SiretSummary.dep, "").label("dep"),
            func.sum(
                func.coalesce(
                    SiretSummary.inscrits_c4,
                    SiretSummary.inscrits_c3,
                    SiretSummary.effectif_siret,
                    0,
                )
            ).label("total_inscrits"),
            func.count(SiretSummary.siret).label("sirets"),
        )
        .group_by("fd", "dep")
        .all()
    )

    payload: dict[str, dict[str, Any]] = {}

    for row in fd_rows:
        fd_label = (row.fd or "").strip()
        if not fd_label:
            fd_label = "FD non renseignée"

        total_inscrits = int(row.total_inscrits or 0)
        if total_inscrits <= 0:
            continue

        dep_code = (row.dep or "00").strip() or "00"
        if dep_code.isdigit() and len(dep_code) == 1:
            dep_code = dep_code.zfill(2)

        entry = payload.setdefault(
            fd_label,
            {
                "fd": fd_label,
                "total_inscrits": 0,
                "sirets": 0,
                "departements": [],
            },
        )
        entry["total_inscrits"] += total_inscrits
        entry["sirets"] += int(row.sirets or 0)
        entry["departements"].append(
            {
                "dep": dep_code,
                "total_inscrits": total_inscrits,
                "sirets": int(row.sirets or 0),
            }
        )

    fd_stats = list(payload.values())
    fd_stats.sort(key=lambda item: item["total_inscrits"], reverse=True)

    for entry in fd_stats:
        entry["departements"].sort(
            key=lambda item: (-item["total_inscrits"], item["dep"])
        )

    total_inscrits = sum(entry["total_inscrits"] for entry in fd_stats)
    total_sirets = sum(entry["sirets"] for entry in fd_stats)

    return {
        "fd_stats": fd_stats,
        "totals": {
            "total_inscrits": total_inscrits,
            "total_sirets": total_sirets,
            "fd_count": len(fd_stats),
        },
        "last_generated_at": datetime.utcnow().isoformat() + "Z",
    }


# =========================================================
# Routes pour le Rétro-planning
# =========================================================

@app.get("/retroplanning", response_class=HTMLResponse)
def retroplanning_page(
    request: Request,
    user: User | None = Depends(get_current_user_or_none),
    db: Session = Depends(get_session)
):
    """Outil de rétro-planning pour les campagnes syndicales"""

    # Tracker l'activité si l'utilisateur est connecté
    if user:
        from .activity_tracker import track_activity
        track_activity(db, user, "retroplanning_view", resource_name="Rétro-planning")

    return templates.TemplateResponse(
        "retroplanning.html",
        {
            "request": request,
            "user": user,
        },
    )


@app.post("/api/retroplanning")
async def create_retroplanning(
    request: Request,
    titre: str | None = Form(None),
    date_evenement: str | None = Form(None),
    type_campagne: str | None = Form(None),
    entreprise: str | None = Form(None),
    siret: str | None = Form(None),
    description: str | None = Form(None),
    phases: str | None = Form(None),  # JSON string
    user: User | None = Depends(get_current_user_or_none),
    db: Session = Depends(get_session),
):
    """Créer un nouveau rétro-planning"""
    import json

    try:
        payload: dict[str, Any] = {}
        content_type = (request.headers.get("content-type") or "").lower()

        if "application/json" in content_type:
            payload = await request.json()
            titre = payload.get("titre", titre)
            date_evenement = payload.get("date_evenement", date_evenement)
            type_campagne = payload.get("type_campagne", type_campagne)
            entreprise = payload.get("entreprise", entreprise)
            siret = payload.get("siret", siret)
            description = payload.get("description", description)
            phases = payload.get("phases", phases)

        if not titre or not str(titre).strip():
            raise HTTPException(status_code=400, detail="Le titre est requis")

        if not date_evenement:
            raise HTTPException(status_code=400, detail="La date de l'événement est requise")

        if not type_campagne:
            raise HTTPException(status_code=400, detail="Le type de campagne est requis")

        raw_phases = phases
        if raw_phases is None:
            raw_phases = payload.get("phases") if payload else None

        if raw_phases is None:
            raise HTTPException(status_code=400, detail="Aucune phase fournie")

        if isinstance(raw_phases, str):
            phases_data = json.loads(raw_phases)
        else:
            phases_data = raw_phases

        if not isinstance(phases_data, list) or not phases_data:
            raise HTTPException(status_code=400, detail="Format de phases invalide")

        # Parser la date
        from datetime import datetime
        date_j = datetime.strptime(str(date_evenement), '%Y-%m-%d').date()

        # Créer le rétro-planning
        retro = Retroplanning(
            titre=str(titre).strip(),
            date_evenement=date_j,
            type_campagne=str(type_campagne).strip(),
            entreprise=entreprise if entreprise and entreprise.strip() else None,
            siret=siret if siret and siret.strip() else None,
            description=description if description and description.strip() else None,
            created_by=user.id if user else None,
        )
        db.add(retro)
        db.flush()  # Pour obtenir l'ID

        # Créer les phases
        for idx, phase_data in enumerate(phases_data):
            # Calculer les dates
            date_debut_str = phase_data.get('dateDebut')
            date_debut = datetime.strptime(date_debut_str, '%Y-%m-%d').date() if date_debut_str else None

            duree = phase_data.get('duree', 0)
            date_fin = None
            if date_debut:
                from datetime import timedelta
                date_fin = date_debut + timedelta(days=duree)

            phase = PhaseRetroplanning(
                retroplanning_id=retro.id,
                titre=phase_data.get('titre', ''),
                description=phase_data.get('description', ''),
                jours_avant_j=phase_data.get('joursAvantJ', 0),
                date_debut=date_debut,
                date_fin=date_fin,
                statut=phase_data.get('statut', 'a_venir'),
                ordre=idx,
            )
            db.add(phase)

        db.commit()

        return {"success": True, "id": retro.id}

    except Exception as e:
        db.rollback()
        logger.error(f"Erreur lors de la création du rétro-planning: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/retroplannings")
def list_retroplannings(
    user: User | None = Depends(get_current_user_or_none),
    db: Session = Depends(get_session),
):
    """Lister les rétro-plannings de l'utilisateur"""
    query = db.query(Retroplanning).filter(Retroplanning.is_archived == False)

    if user:
        query = query.filter(Retroplanning.created_by == user.id)

    retroplannings = query.order_by(Retroplanning.date_evenement.desc()).limit(50).all()

    return {
        "retroplannings": [
            {
                "id": r.id,
                "titre": r.titre,
                "date_evenement": r.date_evenement.isoformat() if r.date_evenement else None,
                "type_campagne": r.type_campagne,
                "entreprise": r.entreprise,
                "siret": r.siret,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in retroplannings
        ]
    }


_KIT_PDF_PLACEHOLDER_HTML = """<!doctype html><html lang=\"fr\"><head><meta charset=\"utf-8\"><title>Kit renforcement</title><style>body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f8fafc;margin:0;color:#0f172a;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:2rem;} .card{background:#fff;border-radius:1.5rem;box-shadow:0 25px 45px rgba(15,23,42,.12);padding:2.75rem;max-width:520px;text-align:center;} h1{font-size:1.5rem;margin-bottom:0.75rem;} p{font-size:1rem;line-height:1.6;color:#475569;} </style></head><body><div class=\"card\"><h1>Document en cours de préparation</h1><p>Le serveur n'a pas encore pu récupérer le kit PDF. Rechargez cette page dans quelques instants ou utilisez le bouton de téléchargement lorsqu'il s'active.</p></div></body></html>"""


@app.get("/kit-renforcement/document", name="kit_pdf_document")
def kit_pdf_document(download: bool = False):
    """Diffuse le PDF du kit de renforcement via le même domaine (embed + téléchargement)."""

    disposition = "attachment" if download else "inline"
    filename = KIT_PDF_FILENAME or "Kit-renforcement.pdf"

    cached_path = _ensure_kit_pdf_cached()
    if cached_path:
        response = FileResponse(
            cached_path,
            media_type="application/pdf",
            filename=filename,
        )
        response.headers["Content-Disposition"] = f'{disposition}; filename="{filename}"'
        response.headers["Cache-Control"] = "public, max-age=86400"
        return response

    try:
        iterator_factory, content_length = _stream_remote_asset(
            KIT_PDF_URL_CANDIDATES, accept="application/pdf"
        )
    except HTTPException as exc:
        logger.warning("Kit PDF indisponible: %s", exc)
        if download:
            raise
        return HTMLResponse(_KIT_PDF_PLACEHOLDER_HTML, status_code=200)

    response = StreamingResponse(iterator_factory(), media_type="application/pdf")
    response.headers["Content-Disposition"] = f'{disposition}; filename="{filename}"'
    response.headers["Cache-Control"] = "public, max-age=86400"
    if content_length is not None:
        if content_length < KIT_PDF_MIN_SIZE_BYTES:
            raise HTTPException(
                status_code=502,
                detail="Document distant trop léger pour la diffusion",
            )
        response.headers["Content-Length"] = str(content_length)

    return response


# Mapping des numéros de documents vers les fichiers PDF individuels
_KIT_INDIVIDUAL_DOCS = {
    "2": "09_202506_Kit_Renforcement-Doc_2.pdf",
    "6": "21_202506_Kit_Renforcement-Doc_6.pdf",
    "7B": "27_202506_Kit_Renforcement-Doc_7B.pdf",
    "8B": "32_202506_Kit_Renforcement-Doc_8B.pdf",
    "8C": "31_202506_Kit_Renforcement-Doc_8C.pdf",
}


@app.get("/kit-renforcement/doc/{doc_id}", name="kit_individual_doc")
def kit_individual_doc(doc_id: str, download: bool = False):
    """
    Diffuse un document individuel du kit de renforcement.
    doc_id peut être: 2, 6, 7B, 8B, 8C
    """
    # Normaliser l'ID du document (majuscules)
    doc_id_normalized = doc_id.upper()

    # Vérifier si le document existe
    if doc_id_normalized not in _KIT_INDIVIDUAL_DOCS:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} non trouvé")

    # Récupérer le nom du fichier
    filename = _KIT_INDIVIDUAL_DOCS[doc_id_normalized]
    file_path = os.path.join(_DEFAULT_DATA_DIR, filename)

    # Vérifier si le fichier existe
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=404,
            detail=f"Fichier {filename} non trouvé sur le serveur"
        )

    # Définir le type de disposition (inline pour afficher, attachment pour télécharger)
    disposition = "attachment" if download else "inline"

    # Créer la réponse avec le fichier PDF
    response = FileResponse(
        file_path,
        media_type="application/pdf",
        filename=filename,
    )
    response.headers["Content-Disposition"] = f'{disposition}; filename="{filename}"'
    response.headers["Cache-Control"] = "public, max-age=86400"

    return response


@app.get("/stats", response_class=HTMLResponse)
def stats(request: Request, db: Session = Depends(get_session)):
    """Page dédiée aux visualisations statistiques du tableau de bord."""

    # Tracker l'activité si l'utilisateur est connecté
    user = get_current_user_or_none(request, db)
    if user:
        from .activity_tracker import track_stats_view
        track_stats_view(db, user)

    return templates.TemplateResponse(
        "stats.html",
        {
            "request": request,
        },
    )


@app.get("/test-kpi", response_class=HTMLResponse)
def test_kpi(request: Request):
    """Page de test pour l'endpoint /api/stats/enriched"""
    return templates.TemplateResponse("test_kpi.html", {"request": request})


@app.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_session)):
    """
    Page d'accueil publique - Plateforme interne
    """
    recent_activities = []
    current_user = get_current_user(request, db)

    if current_user:
        # Récupérer les activités récentes de l'utilisateur
        from .models import UserActivity, Cartographie, Retroplanning
        from datetime import datetime, timedelta

        activities = db.query(UserActivity).filter(
            UserActivity.user_id == current_user.id
        ).order_by(
            UserActivity.accessed_at.desc()
        ).limit(6).all()

        # Formatter les activités pour l'affichage
        for activity in activities:
            # Calculer le temps écoulé
            now = datetime.now()
            delta = now - activity.accessed_at

            if delta.days > 0:
                time_ago = f"Il y a {delta.days} jour{'s' if delta.days > 1 else ''}"
            elif delta.seconds >= 3600:
                hours = delta.seconds // 3600
                time_ago = f"Il y a {hours}h"
            elif delta.seconds >= 60:
                minutes = delta.seconds // 60
                time_ago = f"Il y a {minutes}min"
            else:
                time_ago = "À l'instant"

            # Déterminer l'icône, la couleur et l'URL en fonction du type
            activity_config = {
                "cartographie_view": {
                    "icon": "fas fa-building",
                    "icon_bg": "bg-orange-50",
                    "icon_color": "text-orange-600",
                    "title": activity.resource_name or "Cartographie",
                    "subtitle": "Cartographie entreprise",
                    "url": f"/cartographie-entreprise?id={activity.resource_id}" if activity.resource_id else "/cartographie-entreprise"
                },
                "retroplanning_view": {
                    "icon": "fas fa-calendar-check",
                    "icon_bg": "bg-teal-50",
                    "icon_color": "text-teal-600",
                    "title": activity.resource_name or "Rétroplanning",
                    "subtitle": "Planification campagne",
                    "url": f"/retroplanning?id={activity.resource_id}" if activity.resource_id else "/retroplanning"
                },
                "stats_view": {
                    "icon": "fas fa-chart-line",
                    "icon_bg": "bg-indigo-50",
                    "icon_color": "text-indigo-600",
                    "title": "Statistiques",
                    "subtitle": "Tableau de bord",
                    "url": "/stats"
                },
                "invitations_view": {
                    "icon": "fas fa-envelope-open-text",
                    "icon_bg": "bg-rose-50",
                    "icon_color": "text-rose-600",
                    "title": "Invitations PAP",
                    "subtitle": "Cycle 5",
                    "url": "/invitations"
                },
                "ciblage_view": {
                    "icon": "fas fa-crosshairs",
                    "icon_bg": "bg-sky-50",
                    "icon_color": "text-sky-600",
                    "title": "Ciblage",
                    "subtitle": "Établissements prioritaires",
                    "url": "/ciblage"
                },
                "guide_view": {
                    "icon": "fas fa-book-open",
                    "icon_bg": "bg-purple-50",
                    "icon_color": "text-purple-600",
                    "title": "Guide d'exploitation",
                    "subtitle": "Kit de renforcement",
                    "url": "/guide-exploitation"
                }
            }

            config = activity_config.get(activity.activity_type, {
                "icon": "fas fa-file",
                "icon_bg": "bg-gray-50",
                "icon_color": "text-gray-600",
                "title": activity.resource_name or "Document",
                "subtitle": activity.activity_type,
                "url": "/"
            })

            recent_activities.append({
                **config,
                "time_ago": time_ago
            })

    return templates.TemplateResponse("index.html", {
        "request": request,
        "recent_activities": recent_activities
    })




def _parse_date(value: str | None) -> date | None:
    if not value:
        return None

    cleaned = value.strip()
    if not cleaned:
        return None

    formats = (
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y/%m/%d",
        "%d.%m.%Y",
    )

    for fmt in formats:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue

    # Tentative ISO 8601 générique (permet 2025-03-01T00:00:00)
    try:
        return datetime.fromisoformat(cleaned).date()
    except ValueError:
        return None


def _is_missing_date_value(value: Any) -> bool:
    if value is None:
        return True

    # pandas NaT objects expose .isnat
    if hasattr(value, "isnat"):
        try:
            if bool(value.isnat):
                return True
        except Exception:
            pass

    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return True
        lowered = cleaned.lower()
        if lowered in {"nan", "nat", "none", "null"}:
            return True
        if lowered.startswith("0000-00-00"):
            return True

    return False


def _coerce_date_value(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if hasattr(value, "to_pydatetime"):
        try:
            converted = value.to_pydatetime()
            if isinstance(converted, datetime):
                return converted.date()
        except Exception:
            pass
    if isinstance(value, str):
        parsed = _parse_date(value)
        if parsed:
            return parsed
    return None


def _first_non_empty(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _infer_dep_from_cp(cp: str | None) -> str | None:
    if not cp:
        return None

    digits = "".join(ch for ch in str(cp) if ch.isdigit())
    if not digits:
        return None

    if digits.startswith(("97", "98")) and len(digits) >= 3:
        return digits[:3]

    if digits.startswith("20"):
        if len(digits) >= 3:
            third = digits[2]
            if third in {"0", "1", "2", "3", "4", "5"}:
                return "2A"
            return "2B"
        return "2A"

    if len(digits) >= 2:
        return digits[:2]

    return None


def _resolve_ud_label(row: SiretSummary) -> str | None:
    direct_ud = _first_non_empty(getattr(row, "ud_c4", None), getattr(row, "ud_c3", None))
    if direct_ud:
        return direct_ud

    dep_value = _first_non_empty(getattr(row, "dep", None))
    if dep_value:
        return f"UD {dep_value}"

    cp_value = _first_non_empty(getattr(row, "cp", None))
    inferred = _infer_dep_from_cp(cp_value)
    if inferred:
        return f"UD {inferred}"

    return None


def _format_date_label(date_value: date | None, raw_value: Any) -> str | None:
    if date_value is not None:
        return date_value.strftime("%d/%m/%Y")
    if raw_value is None:
        return None
    text = str(raw_value).strip()
    if not text:
        return None
    lowered = text.lower()
    if lowered in {"nan", "nat", "none", "null"}:
        return None
    return text


def _date_display_and_sort(value: Any) -> tuple[str | None, str]:
    """Return a French-formatted label and ISO sort key for a date-like value."""

    parsed = _coerce_date_value(value)
    if parsed is not None:
        return parsed.strftime("%d/%m/%Y"), parsed.isoformat()

    if value is None:
        return None, ""

    text = str(value).strip()
    if not text:
        return None, ""

    return text, text


def _to_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(" ", "").replace(",", ".")
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _cycle_priority(cycle_str: str) -> int:
    """
    Retourne la priorité d'un cycle pour la déduplication par SIRET.
    C4 (cycle actuel) a la priorité la plus élevée.

    Returns:
        3 pour C4 (priorité max)
        2 pour C5
        1 pour C3
        0 pour autres/inconnu
    """
    if cycle_str == "C4":
        return 3
    elif cycle_str == "C5":
        return 2
    elif cycle_str == "C3":
        return 1
    else:
        return 0


@app.get("/calendrier", response_class=HTMLResponse)
def calendrier_elections(
    request: Request,
    min_effectif: int = 1000,
    q: str = "",
    cycle: str = "",
    institution: str = "",
    fd: str = "",
    idcc: str = "",
    ud: str = "",
    region: str = "",
    year: str = "",
    page: int = 1,
    per_page: int = 50,
    db: Session = Depends(get_session),
):
    today = date.today()

    stmt = (
        db.query(
            PVEvent.siret,
            PVEvent.raison_sociale,
            PVEvent.ud,
            PVEvent.region,
            PVEvent.effectif_siret,
            PVEvent.inscrits,
            PVEvent.cycle,
            PVEvent.date_prochain_scrutin,
            PVEvent.date_pv,
            PVEvent.institution,
            PVEvent.fd,
            PVEvent.idcc,
            PVEvent.sve,
            PVEvent.tx_participation_pv,
            PVEvent.votants,
            PVEvent.nb_college_siret,
            PVEvent.cgt_voix,
            PVEvent.cfdt_voix,
            PVEvent.fo_voix,
            PVEvent.cftc_voix,
            PVEvent.cgc_voix,
            PVEvent.unsa_voix,
            PVEvent.sud_voix,
            PVEvent.autre_voix,
        )
        .filter(PVEvent.date_prochain_scrutin.isnot(None))
    )

    search_term = q.strip().lower()
    cycle_filter = cycle.strip()
    institution_filter = institution.strip()
    fd_filter = fd.strip()
    idcc_filter = idcc.strip()
    ud_filter = ud.strip()
    region_filter = region.strip()
    year_filter = year.strip()

    options = {
        "cycles": set(),
        "institutions": set(),
        "fds": set(),
        "idccs": set(),
        "uds": set(),
        "regions": set(),
        "years": set(),
    }

    per_siret: dict[str, dict[str, Any]] = {}
    for row in stmt:
        parsed_date = _parse_date(row.date_prochain_scrutin)
        if not parsed_date or parsed_date < today:
            continue

        if row.cycle:
            options["cycles"].add(row.cycle)
        if row.institution:
            options["institutions"].add(row.institution)
        if row.fd:
            options["fds"].add(row.fd)
        if row.idcc:
            options["idccs"].add(str(row.idcc))
        if row.ud:
            options["uds"].add(row.ud)
        if row.region:
            options["regions"].add(row.region)
        if parsed_date:
            options["years"].add(str(parsed_date.year))

        # Pour le filtre et l'affichage : utiliser effectif_siret ou inscrits
        effectif_value = _to_number(row.effectif_siret)
        if effectif_value is None:
            effectif_value = _to_number(row.inscrits)

        # Pour le calcul CSE : TOUJOURS utiliser inscrits (effectif du collège)
        effectif_college = _to_number(row.inscrits)

        if min_effectif and (effectif_value is None or effectif_value < min_effectif):
            continue

        if cycle_filter and (row.cycle or "") != cycle_filter:
            continue
        if institution_filter and (row.institution or "") != institution_filter:
            continue
        if fd_filter and (row.fd or "") != fd_filter:
            continue
        if idcc_filter and (str(row.idcc or "")) != idcc_filter:
            continue
        if ud_filter and (row.ud or "") != ud_filter:
            continue
        if region_filter and (row.region or "") != region_filter:
            continue
        if year_filter and str(parsed_date.year) != year_filter:
            continue

        if search_term:
            siret_value = str(row.siret or "")
            raison = (row.raison_sociale or "").lower()
            if search_term not in siret_value.lower() and search_term not in raison:
                continue

        # ÉTAPE 1 : Calculer pour CHAQUE collège/PV (ne pas dédupliquer encore)
        # On va créer une entrée par collège, puis agréger par SIRET après

        sve_value = _to_number(getattr(row, "sve", None))
        participation_value = _to_number(getattr(row, "tx_participation_pv", None))

        # Si tx_participation_pv est vide, calculer à partir de votants/inscrits
        if participation_value is None:
            votants_value = _to_number(getattr(row, "votants", None))
            inscrits_value = _to_number(row.inscrits)
            if votants_value is not None and inscrits_value is not None and inscrits_value > 0:
                participation_value = (votants_value / inscrits_value) * 100

        nb_college_value = _to_number(getattr(row, "nb_college_siret", None))

        # Calculer les voix par organisation pour ce collège
        voix_par_orga = {}
        for attr, label in PV_ORGANISATION_FIELDS:
            votes_value = _to_number(getattr(row, attr, None))
            if votes_value and votes_value > 0:
                voix_par_orga[label] = votes_value

        # Calculer les élus CSE pour ce collège (uniquement C4, plafonné à 35 sièges pour 10 000+)
        # IMPORTANT: Utiliser l'effectif DU COLLÈGE (inscrits), PAS l'effectif total entreprise (effectif_siret)
        elus_par_orga = {}
        nb_sieges_cse = None

        if row.cycle == "C4" and effectif_college and effectif_college > 0 and voix_par_orga:
            calcul_elus = calculer_elus_cse_complet(
                int(effectif_college),  # Effectif du collège (inscrits) - JAMAIS effectif_siret !
                {label: int(v) for label, v in voix_par_orga.items()}
            )
            nb_sieges_cse = calcul_elus["nb_sieges_total"]
            elus_par_orga = calcul_elus["elus_par_orga"]

        # Créer une clé unique par collège pour garder tous les collèges
        # On va agréger par SIRET après
        college_key = f"{row.siret or 'pv'}_{row.cycle or 'na'}_{id(row)}"

        # Récupérer aussi votants et inscrits pour l'agrégation de la participation
        votants_college = _to_number(getattr(row, "votants", None)) or 0
        inscrits_college = _to_number(row.inscrits) or 0

        per_siret[college_key] = {
            "siret": row.siret,
            "raison_sociale": row.raison_sociale,
            "ud": row.ud,
            "region": row.region,
            "effectif": int(effectif_value) if effectif_value is not None else None,
            "cycle": row.cycle,
            "date": parsed_date,
            "date_pv": _parse_date(row.date_pv),
            "institution": row.institution,
            "fd": row.fd,
            "idcc": row.idcc,
            "nb_college": int(nb_college_value) if nb_college_value is not None else None,
            # Données à agréger
            "sve": sve_value or 0,
            "votants": votants_college,
            "inscrits": inscrits_college,
            "participation": participation_value,
            "voix_par_orga": voix_par_orga,
            "elus_par_orga": elus_par_orga,
            "nb_sieges_cse": nb_sieges_cse or 0,
        }

    # ÉTAPE 2 & 3 : Agréger par SIRET (additionner tous les collèges d'un même SIRET)
    from collections import defaultdict

    siret_aggregated = {}
    for college_data in per_siret.values():
        siret = college_data["siret"]

        if siret not in siret_aggregated:
            # Première fois qu'on voit ce SIRET : initialiser
            siret_aggregated[siret] = {
                "siret": siret,
                "raison_sociale": college_data["raison_sociale"],
                "ud": college_data["ud"],
                "region": college_data["region"],
                "effectif": college_data["effectif"],
                "cycle": college_data["cycle"],  # On garde le cycle du premier collège vu
                "date": college_data["date"],
                "date_display": college_data["date"].strftime("%d/%m/%Y"),
                "date_pv": college_data["date_pv"],
                "institution": college_data["institution"],
                "fd": college_data["fd"],
                "idcc": college_data["idcc"],
                # Champs à sommer
                "sve": 0,
                "votants": 0,
                "inscrits": 0,
                "nb_sieges_cse": 0,
                "nb_college": college_data["nb_college"],
                "voix_par_orga": defaultdict(float),
                "elus_par_orga": defaultdict(int),
                # DEBUG: garder le détail des collèges pour affichage
                "colleges_details": [],
            }

        # Vérifier le quorum du collège AVANT d'agréger ses votes
        # Le quorum est atteint si : SVE >= (inscrits / 2) + 1
        # Si le quorum n'est pas atteint, ce collège n'a pas d'élus et ses voix ne comptent pas
        college_inscrits = college_data["inscrits"]
        college_sve = college_data["sve"]
        quorum_atteint = False

        if college_inscrits > 0:
            quorum_requis = (college_inscrits / 2) + 1
            quorum_atteint = college_sve >= quorum_requis

        # Additionner les valeurs de ce collège aux totaux du SIRET
        # UNIQUEMENT si le quorum est atteint
        if quorum_atteint:
            siret_aggregated[siret]["sve"] += college_data["sve"]
            siret_aggregated[siret]["votants"] += college_data["votants"]
            siret_aggregated[siret]["inscrits"] += college_data["inscrits"]
            # NOTE: Ne pas sommer nb_sieges_cse des collèges !
            # Le nombre de sièges sera recalculé au niveau SIRET selon l'effectif total

            for orga, voix in college_data["voix_par_orga"].items():
                siret_aggregated[siret]["voix_par_orga"][orga] += voix

        # NOTE: Ne pas sommer les élus des collèges !
        # Les élus seront calculés une seule fois au niveau SIRET
        # après agrégation de tous les votes.

        # DEBUG: ajouter les détails de ce collège
        siret_aggregated[siret]["colleges_details"].append({
            "effectif": college_data["effectif"],
            "cycle": college_data["cycle"],
            "sve": college_data["sve"],
            "nb_sieges": college_data["nb_sieges_cse"],
            "voix_par_orga": dict(college_data["voix_par_orga"]),
            "elus_par_orga": dict(college_data["elus_par_orga"]),
        })

    # Calculer les élus au niveau SIRET en utilisant les votes agrégés
    # + Plafonner à 35 sièges maximum si nécessaire
    for siret, data in siret_aggregated.items():
        # Calculer le nombre de sièges au niveau SIRET en fonction de l'effectif total
        effectif = data.get("effectif", 0)
        nb_sieges = calculer_nombre_elus_cse(effectif) if effectif > 0 else 0

        # Plafonner à 35 sièges si nécessaire
        if nb_sieges > 35:
            nb_sieges = 35

        # Mettre à jour le nombre de sièges dans les données
        data["nb_sieges_cse"] = nb_sieges

        # Récupérer les voix agrégées
        voix_siret = {orga: int(v) for orga, v in data["voix_par_orga"].items() if v > 0}

        # Calculer la répartition des élus au niveau SIRET avec les votes agrégés
        # Utiliser la méthode QUOTIENT SEUL (plus conservatrice et réaliste)
        # au lieu de "moyenne haute" qui suppose des listes complètes
        if voix_siret and nb_sieges > 0:
            elus_recalcules = repartir_sieges_quotient_seul(voix_siret, nb_sieges)
            data["elus_par_orga"] = defaultdict(int, elus_recalcules)
        else:
            data["elus_par_orga"] = defaultdict(int)

    # Formater les données agrégées pour l'affichage
    elections_list = []
    for siret_data in siret_aggregated.values():
        # Convertir voix_par_orga en all_orgs pour l'affichage
        sve_total = siret_data["sve"]
        all_orgs = []
        orgs_data = {}  # Dictionnaire pour accès direct par code organisation

        for orga, voix in siret_data["voix_par_orga"].items():
            if voix > 0:
                percent = (voix / sve_total * 100) if sve_total > 0 else None
                org_info = {
                    "label": orga,
                    "votes": voix,
                    "votes_display": _format_int_fr(voix),
                    "percent": percent,
                    "percent_display": _format_percent_fr(percent) if percent is not None else None,
                }
                all_orgs.append(org_info)

                # Mapping des noms vers les codes (pour compatibilité avec le template)
                code_map = {
                    "CGT": "cgt_voix",
                    "CFDT": "cfdt_voix",
                    "FO": "fo_voix",
                    "CFTC": "cftc_voix",
                    "CGC": "cgc_voix",
                    "UNSA": "unsa_voix",
                    "SUD": "sud_voix",
                    "Autre": "autre_voix",
                }
                if orga in code_map:
                    orgs_data[code_map[orga]] = org_info

        # Calculer participation au niveau SIRET à partir des totaux agrégés
        participation_siret = None
        if siret_data["inscrits"] > 0 and siret_data["votants"] > 0:
            participation_siret = (siret_data["votants"] / siret_data["inscrits"]) * 100

        elections_list.append({
            "siret": siret_data["siret"],
            "raison_sociale": siret_data["raison_sociale"],
            "ud": siret_data["ud"],
            "region": siret_data["region"],
            "effectif": siret_data["effectif"],
            "effectif_display": _format_int_fr(siret_data["effectif"]) if siret_data["effectif"] else None,
            "cycle": siret_data["cycle"],
            "date": siret_data["date"],
            "date_display": siret_data["date_display"],
            "date_pv": siret_data["date_pv"],
            "institution": siret_data["institution"],
            "fd": siret_data["fd"],
            "idcc": siret_data["idcc"],
            "sve": siret_data["sve"],
            "sve_display": _format_int_fr(siret_data["sve"]),
            "participation": participation_siret,
            "participation_display": _format_percent_fr(participation_siret) if participation_siret is not None else "—",
            "nb_college": siret_data["nb_college"],
            "nb_college_display": _format_int_fr(siret_data["nb_college"]) if siret_data["nb_college"] else None,
            "all_orgs": sorted(all_orgs, key=lambda x: x["votes"], reverse=True),
            "orgs_data": orgs_data,  # Dictionnaire pour accès direct par code
            "nb_sieges_cse": siret_data["nb_sieges_cse"] if siret_data["nb_sieges_cse"] > 0 else None,
            "elus_par_orga": dict(siret_data["elus_par_orga"]),
            # DEBUG: détail des collèges
            "colleges_details": siret_data["colleges_details"],
        })

    elections_list = sorted(elections_list, key=lambda item: item["date"])

    # Pagination
    total_elections = len(elections_list)

    # Valider et limiter per_page
    per_page = max(10, min(per_page, 500))  # Entre 10 et 500 lignes
    page = max(1, page)  # Au moins page 1

    # Calculer le nombre total de pages
    import math
    total_pages = math.ceil(total_elections / per_page) if total_elections > 0 else 1

    # Ajuster la page si elle dépasse le total
    if page > total_pages:
        page = total_pages

    # Calculer l'offset et extraire la page demandée
    offset = (page - 1) * per_page
    elections_page = elections_list[offset:offset + per_page]

    return templates.TemplateResponse(
        "calendrier.html",
        {
            "request": request,
            "elections": elections_page,
            "next_election": elections_list[0] if elections_list else None,
            "filters": {
                "min_effectif": min_effectif,
                "q": q,
                "cycle": cycle_filter,
                "institution": institution_filter,
                "fd": fd_filter,
                "idcc": idcc_filter,
                "ud": ud_filter,
                "region": region_filter,
                "year": year_filter,
            },
            "options": {
                "cycles": sorted(options["cycles"]),
                "institutions": sorted(options["institutions"]),
                "fds": sorted(options["fds"]),
                "idccs": sorted(options["idccs"]),
                "uds": sorted(options["uds"]),
                "regions": sorted(options["regions"]),
                "years": sorted(options["years"], reverse=True),
            },
            "total_elections": total_elections,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
        },
    )


@app.get("/calendrier/export")
def calendrier_export(
    request: Request,
    min_effectif: int = 1000,
    q: str = "",
    cycle: str = "",
    institution: str = "",
    fd: str = "",
    idcc: str = "",
    ud: str = "",
    region: str = "",
    year: str = "",
    db: Session = Depends(get_session),
    current_user = Depends(get_current_user)
):
    """
    Export Excel de la sélection filtrée du calendrier +1000.
    Réservé aux administrateurs.
    """
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux administrateurs. Veuillez utiliser la fonction 'Demander l'export'.")

    filters = {
        "min_effectif": min_effectif,
        "q": q,
        "cycle": cycle,
        "institution": institution,
        "fd": fd,
        "idcc": idcc,
        "ud": ud,
        "region": region,
        "year": year,
    }

    excel_buffer = generate_calendrier_excel(db, filters)
    filename = f"calendrier_elections_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

    return StreamingResponse(
        excel_buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.post("/calendrier/export/request")
async def calendrier_export_request(
    request: Request,
    min_effectif: int = Form(1000),
    q: str = Form(""),
    cycle: str = Form(""),
    institution: str = Form(""),
    fd: str = Form(""),
    idcc: str = Form(""),
    ud: str = Form(""),
    region: str = Form(""),
    year: str = Form(""),
    db: Session = Depends(get_session),
    current_user = Depends(get_current_user),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Créer une demande d'export de données.
    Envoie un email aux administrateurs pour validation.
    """
    # Créer le token unique
    token = str(uuid.uuid4())
    
    filters = {
        "min_effectif": min_effectif,
        "q": q,
        "cycle": cycle,
        "institution": institution,
        "fd": fd,
        "idcc": idcc,
        "ud": ud,
        "region": region,
        "year": year,
    }
    
    # Créer la demande en base
    export_request = DataExportRequest(
        user_id=current_user.id,
        token=token,
        status="PENDING",
        filters=filters,
        created_at=datetime.now()
    )
    db.add(export_request)
    db.commit()
    
    # Envoyer email aux admins
    admins = db.query(User).filter(User.role == "admin", User.is_active == True).all()
    admin_emails = [admin.email for admin in admins]
    
    if admin_emails:
        base_url = str(request.base_url).rstrip("/")
        approve_link = f"{base_url}/admin/exports/{token}/approve"
        reject_link = f"{base_url}/admin/exports/{token}/reject"
        
        # Rendu du template email
        html_content = templates.get_template("emails/export_request_admin.html").render(
            user=current_user,
            request_date=datetime.now().strftime("%d/%m/%Y à %H:%M"),
            filters=filters,
            approve_link=approve_link,
            reject_link=reject_link
        )
        
        email_service = get_resend_service()
        for admin_email in admin_emails:
            background_tasks.add_task(
                email_service.send_email,
                to=admin_email,
                subject=f"Demande d'export - {current_user.full_name}",
                html=html_content
            )
            
    return {"success": True, "message": "Votre demande a été envoyée aux administrateurs."}


@app.get("/admin/exports/{token}/{action}")
async def admin_export_action(
    token: str,
    action: str,
    request: Request,
    db: Session = Depends(get_session),
    current_user = Depends(require_admin_user),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Valider ou refuser une demande d'export.
    """
    export_request = db.query(DataExportRequest).filter(DataExportRequest.token == token).first()
    
    if not export_request:
        raise HTTPException(status_code=404, detail="Demande introuvable")
        
    if export_request.status != "PENDING":
        return HTMLResponse(f"<h1>Cette demande a déjà été traitée ({export_request.status}).</h1>")
        
    requester = db.query(User).filter(User.id == export_request.user_id).first()
    if not requester:
        raise HTTPException(status_code=404, detail="Utilisateur demandeur introuvable")
        
    if action == "approve":
        export_request.status = "APPROVED"
        export_request.processed_at = datetime.now()
        # Expire dans 24h
        export_request.expires_at = datetime.now() + timedelta(hours=24)
        db.commit()
        
        # Envoyer email au demandeur
        base_url = str(request.base_url).rstrip("/")
        download_link = f"{base_url}/calendrier/export/download/{token}"
        
        # Rendu du template email
        html_content = templates.get_template("emails/export_approved_user.html").render(
            user=requester,
            download_link=download_link
        )
        
        email_service = get_resend_service()
        background_tasks.add_task(
            email_service.send_email,
            to=requester.email,
            subject="Votre export est prêt",
            html=html_content
        )
        
        return HTMLResponse("<h1>Demande approuvée avec succès. L'utilisateur a été notifié.</h1>")
        
    elif action == "reject":
        export_request.status = "REJECTED"
        export_request.processed_at = datetime.now()
        db.commit()
        
        return HTMLResponse("<h1>Demande refusée.</h1>")
        
    else:
        raise HTTPException(status_code=400, detail="Action invalide")


@app.get("/calendrier/export/download/{token}")
def calendrier_export_download(
    token: str,
    db: Session = Depends(get_session)
):
    """
    Télécharger un export approuvé.
    """
    export_request = db.query(DataExportRequest).filter(DataExportRequest.token == token).first()
    
    if not export_request:
        raise HTTPException(status_code=404, detail="Lien invalide")
        
    if export_request.status != "APPROVED":
        raise HTTPException(status_code=403, detail="Cet export n'est pas validé")
        
    if export_request.expires_at and datetime.now() > export_request.expires_at:
        raise HTTPException(status_code=403, detail="Ce lien a expiré")
        
    filters = export_request.filters or {}
    
    excel_buffer = generate_calendrier_excel(db, filters)
    filename = f"calendrier_elections_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

    return StreamingResponse(
        excel_buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.get("/invitations", response_class=HTMLResponse)
def invitations(
    request: Request,
    q: str = "",
    source: str = "",
    est_actif: str = "",
    est_siege: str = "",
    ud: str = "",
    fd: str = "",
    departement: str = "",
    statut: str = "",
    page: int = 1,
    per_page: int = 50,
    db: Session = Depends(get_session),
):
    # Tracker l'activité si l'utilisateur est connecté
    user = get_current_user_or_none(request, db)
    if user:
        from .activity_tracker import track_invitations_view
        filters = {k: v for k, v in {
            "q": q, "source": source, "est_actif": est_actif,
            "est_siege": est_siege, "ud": ud, "fd": fd,
            "departement": departement, "statut": statut
        }.items() if v}
        track_invitations_view(db, user, filters if filters else None)

    qs = db.query(Invitation)

    if q:
        like = f"%{q}%"
        qs = qs.filter(
            (Invitation.siret.like(like))
            | (Invitation.denomination.ilike(like))
            | (Invitation.commune.ilike(like))
        )

    if source:
        qs = qs.filter(Invitation.source == source)

    if est_actif:
        if est_actif == "oui":
            qs = qs.filter(Invitation.est_actif.is_(True))
        elif est_actif == "non":
            qs = qs.filter(Invitation.est_actif.is_(False))

    if est_siege:
        if est_siege == "oui":
            qs = qs.filter(Invitation.est_siege.is_(True))
        elif est_siege == "non":
            qs = qs.filter(Invitation.est_siege.is_(False))

    # Nouveaux filtres
    if ud:
        qs = qs.filter(Invitation.ud == ud)

    if fd:
        qs = qs.filter(Invitation.fd == fd)

    if departement:
        qs = qs.filter(Invitation.code_postal.like(f"{departement}%"))

    # Filtre par statut (basé sur l'existence d'un PV C5)
    today = date.today()

    # On appliquera le filtre après avoir récupéré les invitations
    # car on doit joindre avec la table PV

    invitations = (
        qs.order_by(Invitation.date_invit.desc().nullslast(), Invitation.id.desc()).all()
    )

    def normalize_siret(value: Any | None) -> str | None:
        """Retourne une version canonique (14 chiffres) du SIRET lorsque possible."""

        if value is None:
            return None

        if isinstance(value, (bytes, bytearray)):
            text = value.decode("utf-8", "ignore")
        else:
            text = str(value)

        if not text:
            return None

        stripped = text.strip()
        if not stripped:
            return None

        digits_only = "".join(ch for ch in stripped if ch.isdigit())
        if len(digits_only) == 14:
            return digits_only

        if len(stripped) == 14 and stripped.isdigit():
            return stripped

        # Conserver la meilleure tentative pour ne pas perdre l'information
        return digits_only or stripped or None

    # Récupérer tous les SIRET qui ont un PV C5 pour calculer le statut
    sirets_with_pv_c5 = {
        normalized
        for (raw_siret,) in (
            db.query(PVEvent.siret)
            .filter(PVEvent.cycle == "C5")
            .distinct()
            .all()
        )
        if (normalized := normalize_siret(raw_siret))
    }

    # Dictionnaire SIRET -> date PV C5 pour affichage
    pv_c5_dates = {}
    for row in db.query(PVEvent.siret, PVEvent.date_pv).filter(PVEvent.cycle == "C5").all():
        siret_norm = normalize_siret(row[0])
        if siret_norm and row[1]:
            pv_c5_dates[siret_norm] = row[1]

    # Dictionnaire SIRET -> effectif (depuis les PV)
    # Priorité : effectif_siret > inscrits
    effectifs_pv = {}
    for row in db.query(PVEvent.siret, PVEvent.effectif_siret, PVEvent.inscrits).all():
        siret_norm = normalize_siret(row[0])
        if siret_norm:
            # Utiliser effectif_siret en priorité, sinon inscrits
            effectif = row[1] if row[1] and row[1] > 0 else (row[2] if row[2] and row[2] > 0 else None)
            if effectif:
                # Garder le plus grand effectif si plusieurs PV pour le même SIRET
                if siret_norm not in effectifs_pv or effectif > effectifs_pv[siret_norm]:
                    effectifs_pv[siret_norm] = int(effectif)

    # DEBUG: Effectifs côté invitations PAP
    pap_sirets = {
        normalized
        for inv in invitations
        if (normalized := normalize_siret(inv.siret))
    }
    logger.debug(f"Invitations PAP chargées: {len(invitations)}")
    logger.debug(f"Invitations PAP avec SIRET: {len(pap_sirets)}")

    # Récupérer tous les SIRET qui ont un PV C3 ou C4 (reconduction)
    # DEBUG: Voir tous les cycles distincts dans la base
    all_cycles = db.query(PVEvent.cycle).distinct().all()
    logger.debug(f"Tous les cycles dans la base: {[c[0] for c in all_cycles if c[0]]}")

    sirets_with_previous_pv = {
        normalized
        for (raw_siret,) in (
            db.query(PVEvent.siret)
            .filter(or_(PVEvent.cycle == "C3", PVEvent.cycle == "C4"))
            .distinct()
            .all()
        )
        if (normalized := normalize_siret(raw_siret))
    }
    logger.debug(f"Nombre de SIRETs avec PV C3/C4: {len(sirets_with_previous_pv)}")
    logger.debug(
        f"Invitations PAP avec PV C3/C4: {len(pap_sirets & sirets_with_previous_pv)}"
    )
    logger.debug(
        f"Invitations PAP avec PV C5: {len(pap_sirets & sirets_with_pv_c5)}"
    )
    logger.debug(
        f"Invitations PAP candidates Reconduction (C3/C4 sans C5): {len((pap_sirets & sirets_with_previous_pv) - sirets_with_pv_c5)}"
    )

    # Récupérer les dates présumées de prochaine élection (depuis le PV le plus récent)
    # On prend le dernier PV (C4 ou C3) qui a une date_prochain_scrutin
    dates_presumees = {}
    for siret, date_str in db.query(PVEvent.siret, PVEvent.date_prochain_scrutin).filter(
        PVEvent.date_prochain_scrutin.isnot(None),
        PVEvent.date_prochain_scrutin != ""
    ).all():
        if siret and date_str:
            try:
                # Tenter de parser la date (format peut varier)
                from datetime import datetime

                normalized_key = normalize_siret(siret)
                if not normalized_key:
                    continue

                # Essayer plusieurs formats
                for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"]:
                    try:
                        parsed_date = datetime.strptime(date_str.strip(), fmt).date()
                        dates_presumees[normalized_key] = parsed_date
                        break
                    except (ValueError, TypeError):
                        continue
            except (AttributeError, TypeError):
                pass
    def _normalize_raw_key(key: str) -> str:
        normalized = unicodedata.normalize("NFKD", str(key))
        normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        normalized = normalized.lower()
        normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
        return normalized.strip("_")

    def _clean_raw_value(value: Any) -> Any | None:
        if value is None:
            return None
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                return None
            lowered = cleaned.lower()
            if lowered in {"nan", "none", "null"}:
                return None
            return cleaned
        return value

    def _build_raw_map(raw: Mapping[str, Any] | None) -> dict[str, Any]:
        if not raw:
            return {}
        mapped: dict[str, Any] = {}
        for key, value in raw.items():
            cleaned = _clean_raw_value(value)
            if cleaned is None:
                continue
            norm = _normalize_raw_key(key)
            if not norm or norm in mapped:
                continue
            mapped[norm] = cleaned
        return mapped

    def _pick_from_map(raw_map: dict[str, Any], *keys: str) -> Any | None:
        for key in keys:
            norm = _normalize_raw_key(key)
            if norm and norm in raw_map:
                return raw_map[norm]
        return None

    for inv in invitations:
        raw_map = _build_raw_map(getattr(inv, "raw", None))
        normalized_siret = normalize_siret(inv.siret)
        inv.siret_normalized = normalized_siret or (
            inv.siret.strip() if isinstance(inv.siret, str) else inv.siret
        )

        inv.display_denomination = inv.denomination or _pick_from_map(
            raw_map,
            "denomination",
            "denomination_usuelle",
            "raison_sociale",
            "raison sociale",
            "raison_sociale_etablissement",
            "nom_raison_sociale",
            "rs",
        )

        inv.display_enseigne = inv.enseigne or _pick_from_map(
            raw_map,
            "enseigne",
            "enseigne_commerciale",
            "enseigne commerciale",
        )

        inv.display_commune = inv.commune or _pick_from_map(
            raw_map,
            "commune",
            "ville",
            "localite",
            "adresse_ville",
            "libelle_commune_etablissement",
        )

        inv.display_adresse = inv.adresse or _pick_from_map(
            raw_map,
            "adresse_complete",
            "adresse",
            "adresse_ligne_1",
            "adresse_ligne1",
            "adresse_ligne 1",
            "adresse1",
            "adresse_postale",
            "ligne_4",
            "ligne4",
            "libelle_voie",
            "libelle_voie_etablissement",
        )

        inv.display_code_postal = inv.code_postal or _pick_from_map(
            raw_map,
            "code_postal",
            "code postal",
            "code_postal_etablissement",
            "cp",
        )

        inv.display_activite_code = inv.activite_principale or _pick_from_map(
            raw_map,
            "activite_principale",
            "code_naf",
            "naf",
            "code_ape",
            "ape",
        )

        inv.display_activite_label = inv.libelle_activite or _pick_from_map(
            raw_map,
            "libelle_activite",
            "libelle activité",
            "libelle_naf",
            "activite",
            "activite_principale_libelle",
        )

        inv.display_effectifs_label = inv.effectifs_label or _pick_from_map(
            raw_map,
            "effectifs",
            "effectif",
            "effectifs_salaries",
            "effectifs salaries",
            "effectifs categorie",
        )

        inv.display_tranche_effectifs = inv.tranche_effectifs or _pick_from_map(
            raw_map,
            "tranche_effectifs",
            "tranche_effectif",
            "tranche_effectifs_salaries",
            "tranche_effectif_salarie",
        )

        inv.display_categorie = inv.categorie_entreprise or _pick_from_map(
            raw_map,
            "categorie_entreprise",
            "categorie",
            "taille_entreprise",
            "taille",
        )

        # Enrichissement de l'effectif
        # Priorité : effectif_connu > effectif depuis PV
        inv.display_effectif = None
        if inv.effectif_connu and inv.effectif_connu > 0:
            inv.display_effectif = inv.effectif_connu
        elif normalized_siret and normalized_siret in effectifs_pv:
            inv.display_effectif = effectifs_pv[normalized_siret]

        # Calcul du statut basé sur l'existence d'un PV C5, PV précédent et date présumée
        inv.statut = "en_attente"
        inv.statut_badge = "yellow"
        inv.statut_icon = "fa-clock"
        inv.statut_label = "En attente de PV"
        inv.date_pv_c5 = None
        inv.date_presumee = None

        # Priorité 1: Si le SIRET a un PV C5 enregistré
        if normalized_siret and normalized_siret in sirets_with_pv_c5:
            inv.statut = "pv_c5_enregistre"
            inv.statut_badge = "blue"
            inv.statut_icon = "fa-check-circle"
            inv.statut_label = "PV C5 enregistré"
            inv.date_pv_c5 = pv_c5_dates.get(normalized_siret)

        # Priorité 2: Si le SIRET a un PV précédent (C3 ou C4) → Reconduction
        elif normalized_siret and normalized_siret in sirets_with_previous_pv:
            inv.statut = "reconduction"
            inv.statut_badge = "green"
            inv.statut_icon = "fa-sync-alt"
            inv.statut_label = "Reconduction"

            # Afficher le compte à rebours ou retard si date connue
            if normalized_siret and normalized_siret in dates_presumees:
                date_presumee = dates_presumees[normalized_siret]
                inv.date_presumee = date_presumee
                if date_presumee < today:
                    days_late = (today - date_presumee).days
                    inv.statut_label = f"Reconduction - Retard ({days_late}j)"
                else:
                    days_until = (date_presumee - today).days
                    inv.statut_label = f"Reconduction ({days_until}j)"

        # Priorité 3: Pas de PV précédent - vérifier si date présumée passée
        else:
            if normalized_siret and normalized_siret in dates_presumees:
                date_presumee = dates_presumees[normalized_siret]
                inv.date_presumee = date_presumee

                if date_presumee < today:
                    # Date présumée dépassée = Retard
                    days_late = (today - date_presumee).days
                    inv.statut = "retard"
                    inv.statut_badge = "red"
                    inv.statut_icon = "fa-exclamation-triangle"
                    inv.statut_label = f"Retard ({days_late}j)"
                else:
                    # Date présumée future = En attente
                    days_until = (date_presumee - today).days
                    inv.statut = "en_attente"
                    inv.statut_badge = "yellow"
                    inv.statut_icon = "fa-clock"
                    inv.statut_label = f"En attente ({days_until}j)"

        invit_label, invit_sort = _date_display_and_sort(inv.date_invit)
        inv.date_invit_display = invit_label
        inv.date_invit_sort = invit_sort

        pv_c5_label, pv_c5_sort = _date_display_and_sort(inv.date_pv_c5)
        inv.date_pv_c5_display = pv_c5_label
        inv.date_pv_c5_sort = pv_c5_sort

        presumee_label, _ = _date_display_and_sort(inv.date_presumee)
        inv.date_presumee_display = presumee_label

    # Appliquer le filtre de statut si demandé
    if statut:
        if statut == "pv_c5_enregistre":
            invitations = [inv for inv in invitations if inv.statut == "pv_c5_enregistre"]
        elif statut == "reconduction":
            invitations = [inv for inv in invitations if inv.statut == "reconduction"]
        elif statut == "en_attente":
            invitations = [inv for inv in invitations if inv.statut == "en_attente"]
        elif statut == "retard":
            invitations = [inv for inv in invitations if inv.statut == "retard"]

    # Récupérer les listes pour les filtres
    sources = [row[0] for row in db.query(Invitation.source).distinct().order_by(Invitation.source).all() if row[0]]

    def _ud_sort_key(value):
        match = re.search(r"\d+", value)
        if match:
            return (0, int(match.group()), value)
        return (1, value)

    all_uds = sorted(
        {row[0] for row in db.query(Invitation.ud).distinct().all() if row[0]},
        key=_ud_sort_key,
    )
    all_fds = [row[0] for row in db.query(Invitation.fd).distinct().order_by(Invitation.fd).all() if row[0]]

    # Liste des départements depuis les codes postaux
    all_depts_raw = db.query(func.substr(Invitation.code_postal, 1, 2)).distinct().all()
    all_depts = sorted(
        {row[0] for row in all_depts_raw if row[0] and row[0].isdigit()},
        key=lambda x: int(x),
    )

    # Pagination
    total_invitations = len(invitations)

    # Calculer le nombre de salariés connus (invitations avec effectif disponible)
    employees_count = sum(1 for inv in invitations if hasattr(inv, 'display_effectif') and inv.display_effectif and inv.display_effectif > 0)

    # Valider et limiter per_page
    per_page = max(10, min(per_page, 500))  # Entre 10 et 500 lignes
    page = max(1, page)  # Au moins page 1

    # Calculer le nombre total de pages
    import math
    total_pages = math.ceil(total_invitations / per_page) if total_invitations > 0 else 1

    # Ajuster la page si elle dépasse le total
    if page > total_pages:
        page = total_pages

    # Calculer l'offset et extraire la page demandée
    offset = (page - 1) * per_page
    invitations_page = invitations[offset:offset + per_page]

    return templates.TemplateResponse(
        "invitations.html",
        {
            "request": request,
            "invitations": invitations_page,
            "q": q,
            "source": source,
            "sources": sources,
            "est_actif": est_actif,
            "est_siege": est_siege,
            "ud": ud,
            "fd": fd,
            "departement": departement,
            "statut": statut,
            "all_uds": all_uds,
            "all_fds": all_fds,
            "all_depts": all_depts,
            "total_invitations": total_invitations,
            "employees_count": employees_count,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
            "admin_api_key": ADMIN_API_KEY,
        },
    )


@app.get("/api/invitations/export-tsv")
def export_invitations_tsv(
    request: Request,
    q: str = "",
    source: str = "",
    est_actif: str = "",
    est_siege: str = "",
    ud: str = "",
    fd: str = "",
    departement: str = "",
    statut: str = "",
    db: Session = Depends(get_session),
):
    """
    Exporte les invitations filtrées au format TSV (Tab-Separated Values)
    pour copier-coller dans Excel.
    Les mêmes filtres que /invitations sont appliqués.
    """
    from io import StringIO
    import csv

    # Réutiliser la même logique de filtrage que /invitations
    qs = db.query(Invitation)

    if q:
        like = f"%{q}%"
        qs = qs.filter(
            (Invitation.siret.like(like))
            | (Invitation.denomination.ilike(like))
            | (Invitation.commune.ilike(like))
        )

    if source:
        qs = qs.filter(Invitation.source == source)

    if est_actif:
        if est_actif == "oui":
            qs = qs.filter(Invitation.est_actif.is_(True))
        elif est_actif == "non":
            qs = qs.filter(Invitation.est_actif.is_(False))

    if est_siege:
        if est_siege == "oui":
            qs = qs.filter(Invitation.est_siege.is_(True))
        elif est_siege == "non":
            qs = qs.filter(Invitation.est_siege.is_(False))

    if ud:
        qs = qs.filter(Invitation.ud == ud)

    if fd:
        qs = qs.filter(Invitation.fd == fd)

    if departement:
        qs = qs.filter(Invitation.code_postal.like(f"{departement}%"))

    invitations = qs.order_by(Invitation.date_invit.desc().nullslast(), Invitation.id.desc()).all()

    # Récupérer les effectifs depuis les PV (même logique que /invitations)
    def normalize_siret(value):
        if value is None:
            return None
        if isinstance(value, (bytes, bytearray)):
            text = value.decode("utf-8", "ignore")
        else:
            text = str(value)
        if not text:
            return None
        stripped = text.strip()
        if not stripped:
            return None
        digits_only = "".join(ch for ch in stripped if ch.isdigit())
        if len(digits_only) == 14:
            return digits_only
        if len(stripped) == 14 and stripped.isdigit():
            return stripped
        return digits_only or stripped or None

    # Récupérer les effectifs depuis les PV
    effectifs_pv = {}
    for row in db.query(PVEvent.siret, PVEvent.effectif_siret, PVEvent.inscrits).all():
        siret_norm = normalize_siret(row[0])
        if siret_norm:
            effectif = row[1] if row[1] and row[1] > 0 else (row[2] if row[2] and row[2] > 0 else None)
            if effectif:
                if siret_norm not in effectifs_pv or effectif > effectifs_pv[siret_norm]:
                    effectifs_pv[siret_norm] = int(effectif)

    # Appliquer le filtre de statut si demandé (simplifié)
    if statut:
        sirets_with_pv_c5 = {
            normalized
            for (raw_siret,) in db.query(PVEvent.siret).filter(PVEvent.cycle == "C5").distinct().all()
            if (normalized := normalize_siret(raw_siret))
        }
        sirets_with_previous_pv = {
            normalized
            for (raw_siret,) in db.query(PVEvent.siret).filter(
                or_(PVEvent.cycle == "C3", PVEvent.cycle == "C4")
            ).distinct().all()
            if (normalized := normalize_siret(raw_siret))
        }

        filtered = []
        for inv in invitations:
            norm_siret = normalize_siret(inv.siret)
            if statut == "pv_c5_enregistre" and norm_siret in sirets_with_pv_c5:
                filtered.append(inv)
            elif statut == "reconduction" and norm_siret in sirets_with_previous_pv and norm_siret not in sirets_with_pv_c5:
                filtered.append(inv)
            elif statut in ["en_attente", "retard"]:
                # Logique simplifiée pour en_attente et retard
                filtered.append(inv)
        invitations = filtered

    # Créer le TSV
    output = StringIO()
    writer = csv.writer(output, delimiter='\t', lineterminator='\n')

    # En-têtes selon le format demandé
    writer.writerow([
        'SIRET',
        'Nom Entreprise',
        'CP',
        'Ville',
        'date d\'arrivée',
        'Cs',
        'UD',
        'FD',
        'Siège social',
        'IDCC',
        'Nbre de salariés',
        'Commentaires',
        'Date de saisie',
        'ENJEUX'
    ])

    # Écrire les données
    for inv in invitations:
        siret_norm = normalize_siret(inv.siret)

        # Déterminer l'effectif (priorité: effectif_connu > effectif depuis PV)
        effectif = inv.effectif_connu or (effectifs_pv.get(siret_norm) if siret_norm else None) or ''

        # Déterminer le département (Cs = code postal département)
        cs = inv.code_postal[:2] if inv.code_postal and len(inv.code_postal) >= 2 else ''

        # Formatage de la date d'arrivée
        date_arrivee = inv.date_invit.strftime('%d/%m/%Y') if inv.date_invit else ''

        # Date de saisie
        date_saisie = inv.date_reception.strftime('%d/%m/%Y') if inv.date_reception else ''

        writer.writerow([
            inv.siret or '',
            inv.denomination or '',
            inv.code_postal or '',
            inv.commune or '',
            date_arrivee,
            cs,
            inv.ud or '',
            inv.fd or '',
            'Oui' if inv.est_siege else 'Non' if inv.est_siege is False else '',
            inv.idcc or '',
            effectif,
            '',  # Commentaires - vide pour l'instant
            date_saisie,
            ''   # ENJEUX - vide pour l'instant
        ])

    tsv_content = output.getvalue()
    output.close()

    return Response(
        content=tsv_content,
        media_type="text/tab-separated-values; charset=utf-8",
        headers={
            "Content-Disposition": "attachment; filename=invitations_pap.tsv"
        }
    )


@app.post("/api/invitations/scan-auto")
async def scan_auto_invitations(
    request: Request,
    db: Session = Depends(get_session),
    current_user = Depends(get_current_user)
):
    """
    Scan automatique et enrichissement de toutes les invitations PAP incomplètes
    via l'API SIRENE/Pappers.
    """
    import asyncio
    from .services.sirene_api import enrichir_siret

    # Récupérer toutes les invitations sans raison sociale
    invitations = db.query(Invitation).filter(
        or_(
            Invitation.denomination.is_(None),
            Invitation.denomination == '',
        )
    ).all()

    total = len(invitations)
    enrichies = 0
    erreurs = 0
    deja_complet = db.query(Invitation).filter(
        Invitation.denomination.isnot(None),
        Invitation.denomination != ''
    ).count()

    logger.info(f"Début du scan automatique: {total} invitations à enrichir")

    for inv in invitations:
        try:
            # Normaliser le SIRET
            def normalize_siret(value):
                if value is None:
                    return None
                if isinstance(value, (bytes, bytearray)):
                    text = value.decode("utf-8", "ignore")
                else:
                    text = str(value)
                if not text:
                    return None
                stripped = text.strip()
                if not stripped:
                    return None
                digits_only = "".join(ch for ch in stripped if ch.isdigit())
                if len(digits_only) == 14:
                    return digits_only
                if len(stripped) == 14 and stripped.isdigit():
                    return stripped
                return digits_only or stripped or None

            siret = normalize_siret(inv.siret)
            if not siret:
                logger.warning(f"SIRET invalide pour invitation {inv.id}: {inv.siret}")
                erreurs += 1
                continue

            # Enrichir via SIRENE/Pappers
            data = await enrichir_siret(siret)

            if data:
                # Mise à jour des champs manquants
                if not inv.denomination and data.get("denomination"):
                    inv.denomination = data["denomination"]
                if not inv.enseigne and data.get("enseigne"):
                    inv.enseigne = data["enseigne"]
                if not inv.adresse and data.get("adresse"):
                    inv.adresse = data["adresse"]
                if not inv.code_postal and data.get("code_postal"):
                    inv.code_postal = data["code_postal"]
                if not inv.commune and data.get("commune"):
                    inv.commune = data["commune"]
                if not inv.activite_principale and data.get("activite_principale"):
                    inv.activite_principale = data["activite_principale"]
                if not inv.libelle_activite and data.get("libelle_activite"):
                    inv.libelle_activite = data["libelle_activite"]
                if not inv.tranche_effectifs and data.get("tranche_effectifs"):
                    inv.tranche_effectifs = data["tranche_effectifs"]
                if not inv.effectifs_label and data.get("effectifs_label"):
                    inv.effectifs_label = data["effectifs_label"]
                if inv.est_siege is None and data.get("est_siege") is not None:
                    inv.est_siege = data["est_siege"]
                if inv.est_actif is None and data.get("est_actif") is not None:
                    inv.est_actif = data["est_actif"]
                if not inv.categorie_entreprise and data.get("categorie_entreprise"):
                    inv.categorie_entreprise = data["categorie_entreprise"]
                if not inv.idcc and data.get("idcc"):
                    inv.idcc = data["idcc"]
                    # Si IDCC récupéré, enrichir aussi la FD
                    if inv.idcc and not inv.fd:
                        from .services.idcc_enrichment import get_idcc_enrichment_service
                        enrichment_service = get_idcc_enrichment_service()
                        inv.fd = enrichment_service.enrich_fd(inv.idcc, inv.fd, db)

                inv.date_enrichissement = datetime.now()
                enrichies += 1
                logger.info(f"✅ Enrichissement réussi pour SIRET {siret}: {inv.denomination}")
            else:
                logger.warning(f"⚠️ Aucune donnée trouvée pour SIRET {siret}")
                erreurs += 1

        except Exception as e:
            logger.error(f"❌ Erreur lors de l'enrichissement de l'invitation {inv.id} (SIRET: {inv.siret}): {e}")
            erreurs += 1

    db.commit()

    logger.info(f"✅ Scan terminé: {enrichies}/{total} enrichies, {erreurs} erreurs")

    return JSONResponse(content={
        "success": True,
        "total": total,
        "enrichies": enrichies,
        "deja_complet": deja_complet,
        "erreurs": erreurs
    })


@app.post("/api/invitations/generer-emails")
async def generer_emails_pap(
    request: Request,
    db: Session = Depends(get_session),
    current_user = Depends(get_current_user)
):
    """
    Génère les emails de relance pour les invitations PAP incomplètes ou en retard.
    """
    # TODO: Implémenter la logique de génération d'emails
    # Pour l'instant, retourne juste un message de succès

    # Récupérer les invitations incomplètes
    invitations_incomplets = db.query(Invitation).filter(
        or_(
            Invitation.denomination.is_(None),
            Invitation.denomination == '',
            Invitation.code_postal.is_(None),
            Invitation.commune.is_(None)
        )
    ).count()

    logger.info(f"Génération d'emails pour {invitations_incomplets} invitations incomplètes")

    return JSONResponse(content={
        "success": True,
        "total": invitations_incomplets,
        "message": "Emails générés avec succès"
    })


PRIORITY_TOKENS = [
    "siret",
    "raison",
    "dénomination",
    "denomination",
    "enseigne",
    "cycle",
    "date",
    "type",
    "inscrit",
    "votant",
    "blanc",
    "nul",
    "cgt",
    "siège",
    "siege",
    "effectif",
    "naf",
    "activité",
    "activite",
    "ud",
    "fd",
    "dep",
    "départ",
    "depart",
    "région",
    "region",
    "cp",
    "ville",
    "idcc",
    "statut",
    "carence",
    "pap",
    "invitation",
    "audience",
    "groupe",
    "secteur",
    "commentaire",
    "observation",
]


def _order_columns(columns: list[str]) -> list[str]:
    ordered_primary: list[str] = []
    ordered_secondary: list[str] = []

    for col in columns:
        col_str = str(col)
        lower = col_str.lower()
        if any(token in lower for token in PRIORITY_TOKENS):
            ordered_primary.append(col_str)
        else:
            ordered_secondary.append(col_str)

    return ordered_primary + ordered_secondary


def _extract_matches(df, siret_column: str | None, siret_list: list[str]) -> list[dict]:
    if not siret_column:
        return []

    series = df[siret_column].astype(str)
    mask = series.isin(siret_list)
    if not mask.any():
        return []
    return df.loc[mask].to_dict(orient="records")


def _build_ciblage_context(df, siret_list: list[str]) -> dict:
    columns = [str(col) for col in df.columns]
    ordered_columns = _order_columns(columns)
    preview = df.head(10).to_dict(orient="records")

    col_siret = next((c for c in columns if c.lower() == "siret"), None)
    match_rows = _extract_matches(df, col_siret, siret_list)

    return {
        "columns": columns,
        "ordered_columns": ordered_columns,
        "preview_rows": preview,
        "col_siren": col_siret,
        "match_rows": match_rows,
        "match_count": len(match_rows),
    }


@app.get("/extraction", response_class=HTMLResponse)
def extraction_page(request: Request):
    """
    Page d'extraction automatique de courriers PAP via GPT-4 Vision.

    Permet d'uploader des images de courriers PAP et d'en extraire automatiquement
    les informations (SIRET, dates, adresses, etc.) via l'API OpenAI.
    """
    return templates.TemplateResponse("extraction.html", {"request": request})


@app.get("/ciblage", response_class=HTMLResponse)
def ciblage_get(request: Request, db: Session = Depends(get_session)):
    # Tracker l'activité si l'utilisateur est connecté
    user = get_current_user_or_none(request, db)
    if user:
        from .activity_tracker import track_ciblage_view
        track_ciblage_view(db, user)

    import pandas as pd
    from .models import Invitation

    path = "app/static/last_ciblage.csv"
    if not os.path.exists(path):
        return templates.TemplateResponse(
            "ciblage.html",
            {
                "request": request,
                "columns": None,
                "preview_rows": None,
                "ordered_columns": [],
                "col_siren": None,
                "match_rows": [],
                "match_count": 0,
            },
        )

    df = pd.read_csv(path, dtype=str)

    invit_rows = db.query(Invitation.siret).all()
    siret_list = [r[0] for r in invit_rows if r[0]]

    context = _build_ciblage_context(df, siret_list)
    context.update({"request": request})
    return templates.TemplateResponse("ciblage.html", context)


@app.post("/ciblage/import", response_class=HTMLResponse)
def ciblage_import(request: Request, file: UploadFile = File(...), db: Session = Depends(get_session)):
    import pandas as pd
    from .models import Invitation

    df = pd.read_excel(file.file)
    os.makedirs("app/static", exist_ok=True)
    df.to_csv("app/static/last_ciblage.csv", index=False)

    invit_rows = db.query(Invitation.siret).all()
    siret_list = [r[0] for r in invit_rows if r[0]]

    context = _build_ciblage_context(df, siret_list)
    context.update({"request": request})
    return templates.TemplateResponse("ciblage.html", context)


# =========================================================
# Routes pour les Notifications et Alertes
# =========================================================

@app.get("/api/notifications", response_class=JSONResponse)
def api_notifications(db: Session = Depends(get_session)):
    """Endpoint API pour récupérer le compteur de notifications"""
    from .notifications import get_notifications_count
    return get_notifications_count(db)


@app.get("/notifications", response_class=HTMLResponse)
def notifications_page(request: Request, db: Session = Depends(get_session)):
    """Page des notifications et alertes"""
    from .notifications import get_notification_details, get_notifications_count

    # Tracker l'activité si l'utilisateur est connecté
    user = get_current_user_or_none(request, db)
    if user:
        from .activity_tracker import track_activity
        track_activity(db, user, "notifications_view", resource_name="Notifications et alertes")

    counts = get_notifications_count(db)
    details = get_notification_details(db)

    return templates.TemplateResponse(
        "notifications.html",
        {
            "request": request,
            "counts": counts,
            "details": details
        }
    )


def _format_date(value: date | None) -> str | None:
    if not value:
        return None
    return value.strftime("%d/%m/%Y")


def _format_int_fr(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            rounded = int(round(float(value)))
        except (TypeError, ValueError):
            return None
    else:
        try:
            rounded = int(round(float(str(value).replace(",", "."))))
        except (TypeError, ValueError):
            return None

    return f"{rounded:,}".replace(",", "\u202f")


def _format_percent_fr(value: float | None, decimals: int = 1) -> str | None:
    if value is None:
        return None
    formatted = f"{value:.{decimals}f}".replace(".", ",")
    return f"{formatted} %"


PV_ORGANISATION_FIELDS: tuple[tuple[str, str], ...] = (
    ("cgt_voix", "CGT"),
    ("cfdt_voix", "CFDT"),
    ("fo_voix", "FO"),
    ("cftc_voix", "CFTC"),
    ("cgc_voix", "CFE-CGC"),
    ("unsa_voix", "UNSA"),
    ("sud_voix", "Solidaires"),
    ("autre_voix", "Autre"),
)


def _collect_upcoming_for_admin(db: Session, min_effectif: int = 1000) -> list[dict[str, Any]]:
    today = date.today()
    per_siret: dict[str, dict[str, Any]] = {}

    rows = (
        db.query(
            PVEvent.siret,
            PVEvent.raison_sociale,
            PVEvent.ud,
            PVEvent.region,
            PVEvent.effectif_siret,
            PVEvent.inscrits,
            PVEvent.cycle,
            PVEvent.date_prochain_scrutin,
            PVEvent.institution,
            PVEvent.fd,
            PVEvent.idcc,
            PVEvent.sve,
            PVEvent.tx_participation_pv,
            PVEvent.votants,
            PVEvent.cgt_voix,
            PVEvent.cfdt_voix,
            PVEvent.fo_voix,
            PVEvent.cftc_voix,
            PVEvent.cgc_voix,
            PVEvent.unsa_voix,
            PVEvent.sud_voix,
            PVEvent.autre_voix,
        )
        .filter(PVEvent.date_prochain_scrutin.isnot(None))
        .all()
    )

    for row in rows:
        parsed_date = _parse_date(row.date_prochain_scrutin)
        if not parsed_date or parsed_date < today:
            continue

        effectif_value = _to_number(row.effectif_siret)
        if effectif_value is None:
            effectif_value = _to_number(row.inscrits)

        if min_effectif and (effectif_value is None or effectif_value < min_effectif):
            continue

        key = f"{row.siret or 'pv'}-{row.cycle or 'na'}"
        existing = per_siret.get(key)
        if existing is not None and parsed_date >= existing["date"]:
            continue

        payload = {
            "siret": row.siret,
            "raison_sociale": row.raison_sociale,
            "ud": row.ud,
            "region": row.region,
            "effectif": int(effectif_value) if effectif_value is not None else None,
            "cycle": row.cycle,
            "institution": row.institution,
            "fd": row.fd,
            "idcc": row.idcc,
            "date": parsed_date,
            "date_display": parsed_date.strftime("%d/%m/%Y"),
        }

        sve_value = _to_number(row.sve)
        participation_value = _to_number(row.tx_participation_pv)

        # Si tx_participation_pv est vide, calculer à partir de votants/inscrits
        if participation_value is None:
            votants_value = _to_number(row.votants)
            inscrits_value = _to_number(row.inscrits)
            if votants_value is not None and inscrits_value is not None and inscrits_value > 0:
                participation_value = (votants_value / inscrits_value) * 100

        payload["sve"] = sve_value
        payload["sve_display"] = _format_int_fr(sve_value)
        payload["participation"] = participation_value
        payload["participation_display"] = _format_percent_fr(participation_value)

        org_scores: list[dict[str, Any]] = []
        for attr, label in PV_ORGANISATION_FIELDS:
            votes_value = _to_number(getattr(row, attr, None))
            if votes_value is None or votes_value <= 0:
                continue

            percent_value = (votes_value / sve_value * 100) if sve_value else None
            org_scores.append(
                {
                    "code": attr,
                    "label": label,
                    "votes": votes_value,
                    "votes_display": _format_int_fr(votes_value),
                    "percent": percent_value,
                    "percent_display": _format_percent_fr(percent_value) if percent_value is not None else None,
                }
            )

        # Afficher toutes les organisations (pas seulement top 3)
        payload["all_orgs"] = sorted(org_scores, key=lambda entry: entry["votes"], reverse=True)

        per_siret[key] = payload

    return sorted(per_siret.values(), key=lambda item: item["date"])


@app.get("/cartographie", response_class=HTMLResponse)
def cartographie_page(request: Request, db: Session = Depends(get_session)):
    """Page de cartographie de France avec statistiques par département"""
    return templates.TemplateResponse(
        "cartographie.html",
        {
            "request": request
        }
    )


# =========================================================
# Routes d'authentification utilisateur (signup/login)
# =========================================================

@app.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request):
    """Page d'inscription pour les nouveaux utilisateurs"""
    return templates.TemplateResponse(
        "signup.html",
        {
            "request": request,
            "error": None,
            "success": False,
            "form_data": {}
        }
    )


@app.post("/signup", response_class=HTMLResponse)
def signup_post(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session),
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    phone: str = Form(""),
    organization: str = Form(""),
    fd: str = Form(""),
    ud: str = Form(""),
    region: str = Form(""),
    responsibility: str = Form(""),
    registration_reason: str = Form("")
):
    """Traitement de l'inscription d'un nouvel utilisateur"""

    # Conserver les données du formulaire pour les réafficher en cas d'erreur
    form_data = {
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "phone": phone,
        "organization": organization,
        "fd": fd,
        "ud": ud,
        "region": region,
        "responsibility": responsibility,
        "registration_reason": registration_reason
    }

    # Validation de l'email
    if not validate_email(email):
        return templates.TemplateResponse(
            "signup.html",
            {
                "request": request,
                "error": "Adresse email invalide",
                "success": False,
                "form_data": form_data
            },
            status_code=400
        )

    # Vérifier si l'email existe déjà
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        return templates.TemplateResponse(
            "signup.html",
            {
                "request": request,
                "error": "Cette adresse email est déjà utilisée",
                "success": False,
                "form_data": form_data
            },
            status_code=400
        )

    # Vérifier que les mots de passe correspondent
    if password != password_confirm:
        return templates.TemplateResponse(
            "signup.html",
            {
                "request": request,
                "error": "Les mots de passe ne correspondent pas",
                "success": False,
                "form_data": form_data
            },
            status_code=400
        )

    # Valider la force du mot de passe
    is_valid, error_message = validate_password_strength(password)
    if not is_valid:
        return templates.TemplateResponse(
            "signup.html",
            {
                "request": request,
                "error": error_message,
                "success": False,
                "form_data": form_data
            },
            status_code=400
        )

    # Créer le nouvel utilisateur
    try:
        new_user = User(
            email=email,
            hashed_password=hash_password(password),
            first_name=first_name,
            last_name=last_name,
            phone=phone or None,
            organization=organization or None,
            fd=fd or None,
            ud=ud or None,
            region=region or None,
            responsibility=responsibility or None,
            registration_reason=registration_reason or None,
            registration_ip=get_client_ip(request),
            is_approved=False,  # Nécessite l'approbation d'un admin
            is_active=True,
            role="user"
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)  # Rafraîchir pour obtenir l'ID

        # Envoyer un email de notification aux administrateurs (en arrière-plan)
        async def send_registration_emails():
            """Fonction helper pour envoyer les emails en arrière-plan"""
            try:
                from .services.email_service import get_resend_service
                import jinja2

                # Récupérer tous les administrateurs
                db_bg = SessionLocal()
                try:
                    admins = db_bg.query(User).filter(User.role == "admin", User.is_active == True).all()

                    if admins:
                        # Préparer le template
                        template_env = jinja2.Environment(
                            loader=jinja2.FileSystemLoader("app/email_templates")
                        )
                        email_template = template_env.get_template("user_registration_admin.html")

                        email_service = get_resend_service()

                        # Envoyer à chaque admin
                        for admin in admins:
                            if admin.email:
                                html_content = email_template.render(
                                    admin_name=admin.first_name or "Administrateur",
                                    first_name=new_user.first_name,
                                    last_name=new_user.last_name,
                                    email=new_user.email,
                                    phone=new_user.phone,
                                    organization=new_user.organization,
                                    fd=new_user.fd,
                                    ud=new_user.ud,
                                    region=new_user.region,
                                    responsibility=new_user.responsibility,
                                    registration_reason=new_user.registration_reason,
                                    created_at=new_user.created_at.strftime("%d/%m/%Y à %H:%M"),
                                    registration_ip=new_user.registration_ip,
                                    admin_url=f"{str(request.base_url).rstrip('/')}/admin"
                                )

                                try:
                                    await email_service.send_email(
                                        to=admin.email,
                                        subject=f"Nouvelle inscription : {new_user.first_name} {new_user.last_name}",
                                        html=html_content
                                    )
                                except Exception as email_error:
                                    logging.warning(f"Erreur lors de l'envoi d'email à l'admin {admin.email}: {email_error}")

                        logging.info(f"Notification d'inscription envoyée à {len(admins)} administrateur(s)")
                finally:
                    db_bg.close()
            except Exception as e:
                # Ne pas bloquer l'inscription si l'envoi d'email échoue
                logging.warning(f"Erreur lors de l'envoi de notification aux admins: {e}")

        # Ajouter l'envoi d'emails en tâche de fond
        background_tasks.add_task(send_registration_emails)

        # Afficher le message de succès
        return templates.TemplateResponse(
            "signup.html",
            {
                "request": request,
                "error": None,
                "success": True,
                "form_data": {}
            }
        )

    except Exception as e:
        db.rollback()
        logging.error(f"Erreur lors de l'inscription: {e}")
        return templates.TemplateResponse(
            "signup.html",
            {
                "request": request,
                "error": "Une erreur est survenue lors de l'inscription. Veuillez réessayer.",
                "success": False,
                "form_data": form_data
            },
            status_code=500
        )


@app.get("/login", response_class=HTMLResponse)
def user_login_page(request: Request):
    """Page de connexion pour les utilisateurs"""
    return templates.TemplateResponse(
        "user_login.html",
        {
            "request": request,
            "error": None,
            "info": None,
            "email_value": ""
        }
    )


@app.post("/login", response_class=HTMLResponse)
def user_login_post(
    request: Request,
    db: Session = Depends(get_session),
    email: str = Form(...),
    password: str = Form(...)
):
    """Traitement de la connexion utilisateur"""

    # Tenter l'authentification
    user = authenticate_user(db, email, password)

    if user:
        # Créer le token de session
        session_token = create_user_session_token(user.id, user.email)

        # Enregistrer les statistiques de connexion
        user.last_login = datetime.now()
        user.login_count = (user.login_count or 0) + 1
        user.session_start = datetime.now()
        db.commit()

        # Rediriger vers l'accueil avec le cookie de session
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(
            key=USER_SESSION_COOKIE_NAME,
            value=session_token,
            max_age=USER_SESSION_MAX_AGE,
            httponly=True,
            samesite="lax"
        )
        return response
    else:
        # Vérifier si l'utilisateur existe mais n'est pas approuvé
        user_exists = db.query(User).filter(User.email == email).first()

        if user_exists and not user_exists.is_approved:
            error_message = "Votre compte est en attente d'approbation par un administrateur"
        elif user_exists and not user_exists.is_active:
            error_message = "Votre compte a été désactivé. Contactez un administrateur."
        else:
            error_message = "Email ou mot de passe incorrect"

        return templates.TemplateResponse(
            "user_login.html",
            {
                "request": request,
                "error": error_message,
                "info": None,
                "email_value": email
            },
            status_code=401
        )


@app.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_page(request: Request):
    """Page de demande de réinitialisation de mot de passe"""
    return templates.TemplateResponse(
        "forgot_password.html",
        {
            "request": request,
            "error": None,
            "success": False,
            "email_value": ""
        }
    )


@app.post("/forgot-password", response_class=HTMLResponse)
async def forgot_password_post(
    request: Request,
    db: Session = Depends(get_session),
    email: str = Form(...)
):
    """Traitement de la demande de réinitialisation de mot de passe"""
    from .models import PasswordResetToken
    from .services.email_service import get_resend_service
    import jinja2

    # Toujours afficher le même message pour éviter l'énumération d'emails
    success_message = "Si cet email existe dans notre système, vous recevrez un lien de réinitialisation dans quelques minutes."

    # Chercher l'utilisateur
    user = db.query(User).filter(User.email == email).first()

    if user and user.is_active:
        # Générer un token sécurisé
        token = secrets.token_urlsafe(32)

        # Définir l'expiration (24 heures)
        expiry_hours = 24
        expires_at = datetime.now() + timedelta(hours=expiry_hours)

        # Créer le token en base
        reset_token = PasswordResetToken(
            user_id=user.id,
            token=token,
            expires_at=expires_at,
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent", "")[:500]
        )

        db.add(reset_token)
        db.commit()

        # Construire l'URL de réinitialisation
        base_url = str(request.base_url).rstrip('/')
        reset_url = f"{base_url}/reset-password/{token}"

        # Envoyer l'email
        try:
            template_env = jinja2.Environment(
                loader=jinja2.FileSystemLoader("app/email_templates")
            )
            email_template = template_env.get_template("password_reset.html")

            html_content = email_template.render(
                first_name=user.first_name or user.email.split('@')[0],
                email=user.email,
                reset_url=reset_url,
                expiry_hours=expiry_hours
            )

            email_service = get_resend_service()

            await email_service.send_email(
                to=user.email,
                subject="Réinitialisation de votre mot de passe",
                html=html_content
            )

            logging.info(f"Email de réinitialisation de mot de passe envoyé à {user.email}")

        except Exception as e:
            logging.error(f"Erreur lors de l'envoi de l'email de réinitialisation: {e}")
            # Ne pas révéler l'erreur à l'utilisateur

    # Toujours afficher le même message (sécurité)
    return templates.TemplateResponse(
        "forgot_password.html",
        {
            "request": request,
            "error": None,
            "success": True,
            "success_message": success_message,
            "email_value": ""
        }
    )


@app.get("/reset-password/{token}", response_class=HTMLResponse)
def reset_password_page(request: Request, token: str, db: Session = Depends(get_session)):
    """Page de réinitialisation de mot de passe avec token"""
    from .models import PasswordResetToken

    # Vérifier le token
    reset_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == token
    ).first()

    if not reset_token or not reset_token.can_be_used:
        return templates.TemplateResponse(
            "reset_password.html",
            {
                "request": request,
                "error": "Ce lien de réinitialisation est invalide ou a expiré. Veuillez faire une nouvelle demande.",
                "token_valid": False,
                "token": None
            },
            status_code=400
        )

    return templates.TemplateResponse(
        "reset_password.html",
        {
            "request": request,
            "error": None,
            "success": False,
            "token_valid": True,
            "token": token
        }
    )


@app.post("/reset-password/{token}", response_class=HTMLResponse)
def reset_password_post(
    request: Request,
    token: str,
    db: Session = Depends(get_session),
    password: str = Form(...),
    password_confirm: str = Form(...)
):
    """Traitement de la réinitialisation de mot de passe"""
    from .models import PasswordResetToken

    # Vérifier le token
    reset_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == token
    ).first()

    if not reset_token or not reset_token.can_be_used:
        return templates.TemplateResponse(
            "reset_password.html",
            {
                "request": request,
                "error": "Ce lien de réinitialisation est invalide ou a expiré. Veuillez faire une nouvelle demande.",
                "token_valid": False,
                "token": None
            },
            status_code=400
        )

    # Vérifier que les mots de passe correspondent
    if password != password_confirm:
        return templates.TemplateResponse(
            "reset_password.html",
            {
                "request": request,
                "error": "Les mots de passe ne correspondent pas",
                "success": False,
                "token_valid": True,
                "token": token
            },
            status_code=400
        )

    # Valider la force du mot de passe
    is_valid, error_message = validate_password_strength(password)
    if not is_valid:
        return templates.TemplateResponse(
            "reset_password.html",
            {
                "request": request,
                "error": error_message,
                "success": False,
                "token_valid": True,
                "token": token
            },
            status_code=400
        )

    # Récupérer l'utilisateur
    user = db.query(User).filter(User.id == reset_token.user_id).first()

    if not user:
        return templates.TemplateResponse(
            "reset_password.html",
            {
                "request": request,
                "error": "Utilisateur introuvable",
                "success": False,
                "token_valid": False,
                "token": None
            },
            status_code=400
        )

    # Mettre à jour le mot de passe
    user.hashed_password = hash_password(password)

    # Marquer le token comme utilisé
    reset_token.is_used = True
    reset_token.used_at = datetime.now()

    db.commit()

    logging.info(f"Mot de passe réinitialisé pour l'utilisateur {user.email}")

    # Rediriger vers la page de login avec message de succès
    return RedirectResponse(url="/login?reset=success", status_code=303)


@app.get("/logout")
def user_logout(
    request: Request,
    db: Session = Depends(get_session)
):
    """Déconnexion de l'utilisateur"""
    # Enregistrer la durée de la session avant de déconnecter
    try:
        user = get_current_user_or_none(request, db)
        if user and user.session_start:
            # Calculer la durée de la session
            session_duration = int((datetime.now() - user.session_start).total_seconds())
            # Ajouter à la durée totale
            user.total_session_duration = (user.total_session_duration or 0) + session_duration
            # Réinitialiser session_start
            user.session_start = None
            db.commit()
    except Exception as e:
        # En cas d'erreur, continuer quand même la déconnexion
        logger.error(f"Erreur lors de l'enregistrement de la durée de session: {e}")

    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(key=USER_SESSION_COOKIE_NAME)
    return response


# =========================================================
# Route profil utilisateur (protégée par authentification)
# =========================================================

@app.get("/profile", response_class=HTMLResponse)
def user_profile_page(
    request: Request,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Page de profil de l'utilisateur connecté"""
    return templates.TemplateResponse(
        "user_profile.html",
        {
            "request": request,
            "user": current_user,
            "success": None,
            "error": None
        }
    )


@app.post("/profile", response_class=HTMLResponse)
def user_profile_post(
    request: Request,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    first_name: str = Form(...),
    last_name: str = Form(...),
    phone: Optional[str] = Form(None),
    organization: str = Form(...),
    fd: Optional[str] = Form(None),
    ud: Optional[str] = Form(None),
    region: Optional[str] = Form(None),
    responsibility: Optional[str] = Form(None)
):
    """Mise à jour du profil utilisateur"""
    try:
        # Validation des champs requis
        if not first_name or not first_name.strip():
            raise ValueError("Le prénom est requis")
        if not last_name or not last_name.strip():
            raise ValueError("Le nom est requis")
        if not organization or not organization.strip():
            raise ValueError("L'organisation est requise")

        # Mise à jour des informations
        current_user.first_name = first_name.strip()
        current_user.last_name = last_name.strip()
        current_user.phone = phone.strip() if phone else None
        current_user.organization = organization.strip()
        current_user.fd = fd.strip() if fd else None
        current_user.ud = ud.strip() if ud else None
        current_user.region = region.strip() if region else None
        current_user.responsibility = responsibility.strip() if responsibility else None
        current_user.updated_at = datetime.now()

        db.commit()

        logging.info(f"Profil mis à jour pour l'utilisateur {current_user.email}")

        return templates.TemplateResponse(
            "user_profile.html",
            {
                "request": request,
                "user": current_user,
                "success": "Vos informations ont été mises à jour avec succès !",
                "error": None
            }
        )

    except ValueError as e:
        db.rollback()
        return templates.TemplateResponse(
            "user_profile.html",
            {
                "request": request,
                "user": current_user,
                "success": None,
                "error": str(e)
            }
        )
    except Exception as e:
        db.rollback()
        logging.error(f"Erreur lors de la mise à jour du profil: {e}")
        return templates.TemplateResponse(
            "user_profile.html",
            {
                "request": request,
                "user": current_user,
                "success": None,
                "error": "Une erreur est survenue lors de la mise à jour de vos informations"
            }
        )


# =========================================================
# Routes admin (protégées par authentification)
# =========================================================

@app.get("/admin", response_class=HTMLResponse)
def admin_page(
    request: Request,
    db: Session = Depends(get_session),
    current_user = Depends(get_current_user)
):
    total_pv = db.query(func.count(PVEvent.id)).scalar() or 0
    total_sirets = db.query(func.count(func.distinct(PVEvent.siret))).scalar() or 0
    total_summary = db.query(func.count(SiretSummary.siret)).scalar() or 0
    total_invitations = db.query(func.count(Invitation.id)).scalar() or 0

    # Statistiques utilisateurs
    total_users = db.query(func.count(User.id)).scalar() or 0
    pending_users = db.query(func.count(User.id)).filter(User.is_approved == False).scalar() or 0
    approved_users = db.query(func.count(User.id)).filter(User.is_approved == True).scalar() or 0

    # Récupérer les demandes en attente
    pending_user_requests = db.query(User).filter(User.is_approved == False).order_by(User.created_at.desc()).all()

    # Récupérer tous les utilisateurs pour la section de gestion
    all_users = db.query(User).order_by(User.created_at.desc()).all()

    last_summary_date = db.query(func.max(SiretSummary.date_pv_max)).scalar()
    last_invitation_date = db.query(func.max(Invitation.date_invit)).scalar()

    upcoming = _collect_upcoming_for_admin(db)
    upcoming_preview = upcoming[:5]

    db_path = _sqlite_path_from_engine()
    db_exists = bool(db_path and os.path.exists(db_path))
    db_size = os.path.getsize(db_path) if db_exists else None
    db_hash = _cached_sha256(db_path) if db_exists else ""

    stats = {
        "pv_total": total_pv,
        "pv_sirets": total_sirets,
        "summary_total": total_summary,
        "invit_total": total_invitations,
        "last_summary": _format_date(last_summary_date),
        "last_invitation": _format_date(last_invitation_date),
        "upcoming_total": len(upcoming),
        "upcoming_next": upcoming[0]["date_display"] if upcoming else None,
    }

    invitations_asset = {
        "auto_enabled": INVITATIONS_AUTO_IMPORT,
        "url": INVITATIONS_URL or None,
        "expected_hash": INVITATIONS_SHA256 or None,
        "count": total_invitations,
        "last_date": stats["last_invitation"],
        "inferred_url": INVITATIONS_INFERRED_URLS[0] if INVITATIONS_INFERRED_URLS else None,
        "inferred_urls": INVITATIONS_INFERRED_URLS,
        "effective_url": INVITATIONS_EFFECTIVE_URL,
    }

    db_asset = {
        "path": db_path,
        "exists": db_exists,
        "size_mb": round(db_size / (1024 * 1024), 1) if db_size else None,
        "expected_hash": DB_SHA256 or None,
        "actual_hash": db_hash or None,
        "hash_match": bool(db_hash and DB_SHA256 and db_hash == DB_SHA256),
        "url": DB_URL or None,
    }

    sirene_key = (os.getenv("SIRENE_API_KEY") or "").strip()
    sirene_token = (os.getenv("SIRENE_API_TOKEN") or "").strip()

    masked_value = None
    display_value = sirene_key or sirene_token
    if display_value:
        if len(display_value) >= 8:
            masked_value = f"{display_value[:4]}••••{display_value[-4:]}"
        else:
            masked_value = "••••"

    sirene_status = {
        "configured": bool(display_value),
        "masked": masked_value,
        "has_integration_key": bool(sirene_key),
        "has_token": bool(sirene_token),
    }

    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "stats": stats,
            "db_asset": db_asset,
            "invitations_asset": invitations_asset,
            "sirene_status": sirene_status,
            "upcoming_preview": upcoming_preview,
            "upcoming_threshold": 1000,
            "admin_api_key": ADMIN_API_KEY,
            "total_users": total_users,
            "pending_users": pending_users,
            "approved_users": approved_users,
        },
    )


@app.get("/admin/users", response_class=HTMLResponse)
def admin_users_page(
    request: Request,
    db: Session = Depends(get_session),
    current_user = Depends(get_current_user)
):
    """Page dédiée à la gestion des utilisateurs"""
    # Statistiques utilisateurs
    total_users = db.query(func.count(User.id)).scalar() or 0
    pending_users = db.query(func.count(User.id)).filter(User.is_approved == False).scalar() or 0
    approved_users = db.query(func.count(User.id)).filter(User.is_approved == True).scalar() or 0

    # Récupérer les demandes en attente
    pending_user_requests = db.query(User).filter(User.is_approved == False).order_by(User.created_at.desc()).all()

    # Récupérer tous les utilisateurs
    all_users = db.query(User).order_by(User.created_at.desc()).all()

    return templates.TemplateResponse(
        "admin_users.html",
        {
            "request": request,
            "total_users": total_users,
            "pending_users": pending_users,
            "approved_users": approved_users,
            "pending_user_requests": pending_user_requests,
            "all_users": all_users,
        },
    )


# =========================================================
# Routes API admin pour gestion des utilisateurs
# =========================================================

@app.post("/admin/users/{user_id}/approve")
def approve_user(
    user_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session),
    current_user = Depends(require_admin_user)
):
    """Approuver une demande d'inscription utilisateur"""
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        return {"success": False, "error": "Utilisateur non trouvé"}

    if user.is_approved:
        return {"success": False, "error": "Utilisateur déjà approuvé"}

    # Approuver l'utilisateur
    user.is_approved = True
    user.approved_at = datetime.now()
    user.approved_by = current_user.email  # current_user est maintenant un objet User
    db.commit()

    # Envoyer un email de confirmation à l'utilisateur (en arrière-plan)
    async def send_approval_email():
        """Fonction helper pour envoyer l'email d'approbation en arrière-plan"""
        try:
            from .services.email_service import get_resend_service
            import jinja2

            # Préparer le template
            template_env = jinja2.Environment(
                loader=jinja2.FileSystemLoader("app/email_templates")
            )
            email_template = template_env.get_template("user_approved.html")

            email_service = get_resend_service()

            html_content = email_template.render(
                first_name=user.first_name or user.email.split('@')[0],
                email=user.email,
                login_url=f"{os.getenv('APP_URL', 'https://votre-app.railway.app')}/login",
                approved_date=user.approved_at.strftime("%d/%m/%Y à %H:%M")
            )

            try:
                await email_service.send_email(
                    to=user.email,
                    subject="Votre compte PAP/CSE a été approuvé !",
                    html=html_content
                )
                logging.info(f"Email d'approbation envoyé à {user.email}")
            except Exception as email_error:
                logging.warning(f"Erreur lors de l'envoi d'email d'approbation à {user.email}: {email_error}")

        except Exception as e:
            # Ne pas bloquer l'approbation si l'envoi d'email échoue
            logging.warning(f"Erreur lors de l'envoi de notification d'approbation: {e}")

    # Ajouter l'envoi d'email en tâche de fond
    background_tasks.add_task(send_approval_email)

    return {
        "success": True,
        "message": f"Utilisateur {user.full_name} ({user.email}) approuvé avec succès"
    }


@app.post("/admin/users/{user_id}/reject")
def reject_user(
    user_id: int,
    db: Session = Depends(get_session),
    current_user = Depends(require_admin_user)
):
    """Rejeter une demande d'inscription utilisateur (suppression)"""
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        return {"success": False, "error": "Utilisateur non trouvé"}

    email = user.email
    name = user.full_name

    # Supprimer l'utilisateur
    db.delete(user)
    db.commit()

    return {
        "success": True,
        "message": f"Demande de {name} ({email}) rejetée et supprimée"
    }


@app.post("/admin/users/{user_id}/deactivate")
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_session),
    current_user = Depends(require_admin_user)
):
    """Désactiver un compte utilisateur"""
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        return {"success": False, "error": "Utilisateur non trouvé"}

    user.is_active = False
    db.commit()

    return {
        "success": True,
        "message": f"Compte de {user.full_name} ({user.email}) désactivé"
    }


@app.post("/admin/users/{user_id}/activate")
def activate_user(
    user_id: int,
    db: Session = Depends(get_session),
    current_user = Depends(require_admin_user)
):
    """Réactiver un compte utilisateur"""
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        return {"success": False, "error": "Utilisateur non trouvé"}

    user.is_active = True
    db.commit()

    return {
        "success": True,
        "message": f"Compte de {user.full_name} ({user.email}) réactivé"
    }


@app.post("/admin/users/{user_id}/make-admin")
def make_user_admin(
    user_id: int,
    db: Session = Depends(get_session),
    current_user = Depends(require_admin_user)
):
    """Promouvoir un utilisateur au rôle admin"""
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        return {"success": False, "error": "Utilisateur non trouvé"}

    if user.role == "admin":
        return {"success": False, "error": "Cet utilisateur est déjà administrateur"}

    user.role = "admin"
    db.commit()

    return {
        "success": True,
        "message": f"{user.full_name} ({user.email}) est maintenant administrateur"
    }


@app.post("/admin/users/{user_id}/delete")
def delete_user(
    user_id: int,
    db: Session = Depends(get_session),
    current_user = Depends(require_admin_user)
):
    """Supprimer un utilisateur définitivement"""
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        return {"success": False, "error": "Utilisateur non trouvé"}

    if user.role == "admin":
        # Compter le nombre d'admins
        admin_count = db.query(func.count(User.id)).filter(User.role == "admin").scalar()
        if admin_count <= 1:
            return {"success": False, "error": "Impossible de supprimer le dernier administrateur"}

    name = user.full_name
    email = user.email

    db.delete(user)
    db.commit()

    return {
        "success": True,
        "message": f"Utilisateur {name} ({email}) supprimé définitivement"
    }


@app.get("/admin/diagnostics", response_class=HTMLResponse)
def admin_diagnostics(
    request: Request,
    db: Session = Depends(get_session),
    current_user = Depends(require_admin_user)
):
    """Page de diagnostic des doublons d'invitations"""

    # Compter le total
    total = db.query(func.count(Invitation.id)).scalar() or 0

    # Compter les SIRET uniques
    unique_sirets = db.query(func.count(func.distinct(Invitation.siret))).scalar() or 0

    # Calculer les doublons
    duplicates = total - unique_sirets

    # Compter par source
    sources = db.query(
        Invitation.source,
        func.count(Invitation.id)
    ).group_by(Invitation.source).all()

    sources_data = [{"source": s or "Sans source", "count": c} for s, c in sources]

    # Trouver les top 10 SIRET avec le plus de doublons
    duplicated_sirets = db.query(
        Invitation.siret,
        func.count(Invitation.id).label('count')
    ).group_by(Invitation.siret).having(func.count(Invitation.id) > 1).order_by(
        func.count(Invitation.id).desc()
    ).limit(10).all()

    top_duplicates = []
    for siret, count in duplicated_sirets:
        dates = db.query(Invitation.date_invit).filter(Invitation.siret == siret).limit(3).all()
        dates_str = ", ".join([str(d[0]) for d in dates if d[0]])
        top_duplicates.append({
            "siret": siret,
            "count": count,
            "dates": dates_str
        })

    # Statistiques FD/UD/IDCC
    with_raw = db.query(func.count(Invitation.id)).filter(Invitation.raw.isnot(None)).scalar() or 0

    fd_filled = db.query(func.count(Invitation.id)).filter(
        Invitation.fd.isnot(None), Invitation.fd != ""
    ).scalar() or 0

    ud_filled = db.query(func.count(Invitation.id)).filter(
        Invitation.ud.isnot(None), Invitation.ud != ""
    ).scalar() or 0

    idcc_filled = db.query(func.count(Invitation.id)).filter(
        Invitation.idcc.isnot(None), Invitation.idcc != ""
    ).scalar() or 0

    # Exemple d'invitation avec raw pour debug
    sample_with_raw = db.query(Invitation).filter(Invitation.raw.isnot(None)).first()
    sample_raw_keys = []
    if sample_with_raw and sample_with_raw.raw:
        sample_raw_keys = sorted(sample_with_raw.raw.keys())[:20]  # Limité à 20 clés

    return templates.TemplateResponse("admin_diagnostics.html", {
        "request": request,
        "total": total,
        "unique_sirets": unique_sirets,
        "duplicates": duplicates,
        "sources": sources_data,
        "top_duplicates": top_duplicates,
        "has_duplicates": duplicates > 0,
        "with_raw": with_raw,
        "fd_filled": fd_filled,
        "ud_filled": ud_filled,
        "idcc_filled": idcc_filled,
        "sample_raw_keys": sample_raw_keys
    })

@app.post("/admin/diagnostics/remove-duplicates")
def remove_duplicates(
    db: Session = Depends(get_session),
    current_user = Depends(require_admin_user)
):
    """Supprime les doublons d'invitations (garde le plus récent par SIRET)"""

    # Trouver les IDs à GARDER (ID max par SIRET)
    subq = db.query(
        Invitation.siret,
        func.max(Invitation.id).label('max_id')
    ).group_by(Invitation.siret).subquery()

    ids_to_keep = db.query(Invitation.id).join(
        subq,
        Invitation.id == subq.c.max_id
    ).all()

    ids_to_keep_set = {id_tuple[0] for id_tuple in ids_to_keep}

    # Supprimer les doublons
    deleted = db.query(Invitation).filter(
        ~Invitation.id.in_(ids_to_keep_set)
    ).delete(synchronize_session=False)

    db.commit()

    return RedirectResponse(url="/admin/diagnostics?success=1", status_code=303)

@app.post("/admin/diagnostics/migrate-columns")
def migrate_columns(
    db: Session = Depends(get_session),
    current_user = Depends(require_admin_user)
):
    """Remplit les colonnes structurées depuis le champ raw"""

    from .migrations import _pick_from_raw, _pick_bool_from_raw

    # Récupérer toutes les invitations avec raw non-null
    invitations = db.query(Invitation).filter(Invitation.raw.isnot(None)).all()

    updated_count = 0

    for inv in invitations:
        raw = inv.raw or {}
        updated = False

        # Si déjà rempli, skip
        if inv.denomination and inv.commune and inv.code_postal:
            continue

        # Denomination
        if not inv.denomination:
            inv.denomination = _pick_from_raw(
                raw,
                "denomination", "denomination_usuelle", "raison_sociale", "raison sociale",
                "raison_sociale_etablissement", "nom_raison_sociale", "rs", "nom",
                "nom_entreprise", "societe", "entreprise", "nom_de_l_entreprise", "libelle"
            )
            if inv.denomination:
                updated = True

        # Enseigne
        if not inv.enseigne:
            inv.enseigne = _pick_from_raw(raw, "enseigne", "enseigne_commerciale", "enseigne commerciale", "nom_commercial")
            if inv.enseigne:
                updated = True

        # Adresse
        if not inv.adresse:
            inv.adresse = _pick_from_raw(
                raw,
                "adresse_complete", "adresse", "adresse_ligne_1", "adresse_ligne1", "adresse_ligne 1",
                "adresse1", "adresse_postale", "ligne_4", "ligne4", "libelle_voie", "libelle_voie_etablissement",
                "rue", "numero_et_voie", "voie", "adresse_etablissement", "adresse2", "complement_adresse",
                "numero_voie", "adresse_geo", "adresse_complete_etablissement"
            )
            if inv.adresse:
                updated = True

        # Code postal
        if not inv.code_postal:
            inv.code_postal = _pick_from_raw(
                raw, "code_postal", "code postal", "cp", "code_postal_etablissement", "postal"
            )
            if inv.code_postal:
                updated = True

        # Commune
        if not inv.commune:
            inv.commune = _pick_from_raw(
                raw, "commune", "ville", "localite", "adresse_ville", "libelle_commune_etablissement", "city"
            )
            if inv.commune:
                updated = True

        # Activité principale
        if not inv.activite_principale:
            inv.activite_principale = _pick_from_raw(
                raw, "activite_principale", "code_naf", "naf", "code_ape", "ape"
            )
            if inv.activite_principale:
                updated = True

        # Libellé activité
        if not inv.libelle_activite:
            inv.libelle_activite = _pick_from_raw(
                raw, "libelle_activite", "libelle activité", "libelle_naf", "activite",
                "activite_principale_libelle"
            )
            if inv.libelle_activite:
                updated = True

        # Effectifs
        if not inv.effectifs_label:
            inv.effectifs_label = _pick_from_raw(
                raw, "effectifs", "effectif", "effectifs_salaries", "effectifs salaries", "effectifs categorie",
                "effectif_salarie", "nb_salaries", "nombre_salaries", "salaries", "nombre_de_salaries",
                "effectif_total", "total_effectif", "nb_employes", "nombre_employes"
            )
            if inv.effectifs_label:
                updated = True

        # Tranche effectifs
        if not inv.tranche_effectifs:
            inv.tranche_effectifs = _pick_from_raw(
                raw, "tranche_effectifs", "tranche_effectif", "tranche_effectifs_salaries",
                "tranche_effectif_salarie"
            )
            if inv.tranche_effectifs:
                updated = True

        # Catégorie entreprise
        if not inv.categorie_entreprise:
            inv.categorie_entreprise = _pick_from_raw(
                raw, "categorie_entreprise", "categorie", "taille_entreprise", "taille"
            )
            if inv.categorie_entreprise:
                updated = True

        # Est actif
        if inv.est_actif is None:
            inv.est_actif = _pick_bool_from_raw(raw, "est_actif", "actif", "etat_etablissement", "etat")
            if inv.est_actif is not None:
                updated = True

        # Est siège
        if inv.est_siege is None:
            inv.est_siege = _pick_bool_from_raw(raw, "est_siege", "siege", "siege_social")
            if inv.est_siege is not None:
                updated = True

        if updated:
            updated_count += 1

    db.commit()

    return RedirectResponse(url=f"/admin/diagnostics?migrated={updated_count}", status_code=303)

@app.get("/admin/clean-nan", response_class=HTMLResponse)
def clean_nan_page(
    request: Request,
    current_user = Depends(require_admin_user)
):
    """Page simple pour exécuter le nettoyage des valeurs 'nan'"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Nettoyage des valeurs NaN</title>
        <meta charset="utf-8">
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                max-width: 800px;
                margin: 50px auto;
                padding: 20px;
                background-color: #f5f5f5;
            }
            .card {
                background: white;
                border-radius: 8px;
                padding: 30px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            h1 {
                color: #333;
                margin-top: 0;
            }
            .info {
                background: #e3f2fd;
                border-left: 4px solid #2196F3;
                padding: 15px;
                margin: 20px 0;
            }
            button {
                background: #d32f2f;
                color: white;
                border: none;
                padding: 12px 24px;
                font-size: 16px;
                border-radius: 4px;
                cursor: pointer;
                margin-top: 20px;
            }
            button:hover {
                background: #b71c1c;
            }
            button:disabled {
                background: #ccc;
                cursor: not-allowed;
            }
            #result {
                margin-top: 20px;
                padding: 15px;
                border-radius: 4px;
                display: none;
            }
            .success {
                background: #c8e6c9;
                border-left: 4px solid #4caf50;
            }
            .error {
                background: #ffcdd2;
                border-left: 4px solid #f44336;
            }
            .loading {
                display: inline-block;
                width: 20px;
                height: 20px;
                border: 3px solid rgba(255,255,255,.3);
                border-radius: 50%;
                border-top-color: white;
                animation: spin 1s ease-in-out infinite;
            }
            @keyframes spin {
                to { transform: rotate(360deg); }
            }
            pre {
                background: #f5f5f5;
                padding: 10px;
                border-radius: 4px;
                overflow-x: auto;
            }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>🧹 Nettoyage des valeurs "nan"</h1>

            <div class="info">
                <strong>ℹ️ Information</strong><br>
                Cet outil nettoie toutes les valeurs "nan" (chaîne de caractères) dans les colonnes UD, FD et IDCC
                et les convertit en NULL pour un affichage correct avec "—" dans l'interface.
            </div>

            <p><strong>Tables concernées :</strong></p>
            <ul>
                <li>Invitation (colonnes: ud, fd, idcc)</li>
                <li>PVEvent (colonnes: UD, FD, idcc)</li>
                <li>SiretSummary (colonnes: ud_c3, ud_c4, fd_c3, fd_c4, idcc)</li>
            </ul>

            <button id="cleanBtn" onclick="cleanNan()">
                🚀 Lancer le nettoyage
            </button>

            <div id="result"></div>
        </div>

        <script>
            async function cleanNan() {
                const btn = document.getElementById('cleanBtn');
                const result = document.getElementById('result');

                btn.disabled = true;
                btn.innerHTML = '<span class="loading"></span> Nettoyage en cours...';
                result.style.display = 'none';

                try {
                    const response = await fetch('/admin/clean-nan/execute', {
                        method: 'POST'
                    });

                    const data = await response.json();

                    if (data.success) {
                        result.className = 'success';
                        result.innerHTML = `
                            <strong>${data.message}</strong><br><br>
                            <strong>📊 Détails :</strong>
                            <pre>${JSON.stringify(data.tables, null, 2)}</pre>
                        `;
                    } else {
                        result.className = 'error';
                        result.innerHTML = `
                            <strong>${data.message}</strong><br><br>
                            Erreur : ${data.error || 'Inconnue'}
                        `;
                    }
                } catch (error) {
                    result.className = 'error';
                    result.innerHTML = `
                        <strong>❌ Erreur de connexion</strong><br><br>
                        ${error.message}
                    `;
                }

                result.style.display = 'block';
                btn.disabled = false;
                btn.innerHTML = '🚀 Lancer le nettoyage';
            }
        </script>
    </body>
    </html>
    """
    return html

@app.post("/admin/clean-nan/execute")
def clean_nan_values(
    db: Session = Depends(get_session),
    current_user = Depends(require_admin_user)
):
    """
    Nettoie toutes les valeurs 'nan' dans les tables et les convertit en NULL.

    Retourne un JSON avec les statistiques de nettoyage.
    """
    from fastapi.responses import JSONResponse

    try:
        stats = {
            "success": True,
            "tables": {},
            "total_cleaned": 0
        }

        # 1. Table Invitation
        inv_stats = {}

        # Compter FD
        inv_fd_count = db.query(Invitation).filter(
            Invitation.fd.in_(['nan', 'NaN', 'NAN', 'Nan'])
        ).count()
        inv_stats["fd"] = inv_fd_count

        # Compter UD
        inv_ud_count = db.query(Invitation).filter(
            Invitation.ud.in_(['nan', 'NaN', 'NAN', 'Nan'])
        ).count()
        inv_stats["ud"] = inv_ud_count

        # Compter IDCC
        inv_idcc_count = db.query(Invitation).filter(
            Invitation.idcc.in_(['nan', 'NaN', 'NAN', 'Nan'])
        ).count()
        inv_stats["idcc"] = inv_idcc_count

        # Nettoyer Invitation.fd
        if inv_fd_count > 0:
            db.execute(
                update(Invitation)
                .where(Invitation.fd.in_(['nan', 'NaN', 'NAN', 'Nan']))
                .values(fd=None)
            )

        # Nettoyer Invitation.ud
        if inv_ud_count > 0:
            db.execute(
                update(Invitation)
                .where(Invitation.ud.in_(['nan', 'NaN', 'NAN', 'Nan']))
                .values(ud=None)
            )

        # Nettoyer Invitation.idcc
        if inv_idcc_count > 0:
            db.execute(
                update(Invitation)
                .where(Invitation.idcc.in_(['nan', 'NaN', 'NAN', 'Nan']))
                .values(idcc=None)
            )

        inv_stats["total"] = inv_fd_count + inv_ud_count + inv_idcc_count
        stats["tables"]["Invitation"] = inv_stats

        # 2. Table PVEvent
        pv_stats = {}

        # Compter FD
        pv_fd_count = db.query(PVEvent).filter(
            PVEvent.fd.in_(['nan', 'NaN', 'NAN', 'Nan'])
        ).count()
        pv_stats["fd"] = pv_fd_count

        # Compter UD
        pv_ud_count = db.query(PVEvent).filter(
            PVEvent.ud.in_(['nan', 'NaN', 'NAN', 'Nan'])
        ).count()
        pv_stats["ud"] = pv_ud_count

        # Compter IDCC
        pv_idcc_count = db.query(PVEvent).filter(
            PVEvent.idcc.in_(['nan', 'NaN', 'NAN', 'Nan'])
        ).count()
        pv_stats["idcc"] = pv_idcc_count

        # Nettoyer PVEvent.fd
        if pv_fd_count > 0:
            db.execute(
                update(PVEvent)
                .where(PVEvent.fd.in_(['nan', 'NaN', 'NAN', 'Nan']))
                .values(fd=None)
            )

        # Nettoyer PVEvent.ud
        if pv_ud_count > 0:
            db.execute(
                update(PVEvent)
                .where(PVEvent.ud.in_(['nan', 'NaN', 'NAN', 'Nan']))
                .values(ud=None)
            )

        # Nettoyer PVEvent.idcc
        if pv_idcc_count > 0:
            db.execute(
                update(PVEvent)
                .where(PVEvent.idcc.in_(['nan', 'NaN', 'NAN', 'Nan']))
                .values(idcc=None)
            )

        pv_stats["total"] = pv_fd_count + pv_ud_count + pv_idcc_count
        stats["tables"]["PVEvent"] = pv_stats

        # 3. Table SiretSummary
        summary_stats = {}

        # Compter FD C3
        summary_fd_c3_count = db.query(SiretSummary).filter(
            SiretSummary.fd_c3.in_(['nan', 'NaN', 'NAN', 'Nan'])
        ).count()
        summary_stats["fd_c3"] = summary_fd_c3_count

        # Compter FD C4
        summary_fd_c4_count = db.query(SiretSummary).filter(
            SiretSummary.fd_c4.in_(['nan', 'NaN', 'NAN', 'Nan'])
        ).count()
        summary_stats["fd_c4"] = summary_fd_c4_count

        # Compter UD C3
        summary_ud_c3_count = db.query(SiretSummary).filter(
            SiretSummary.ud_c3.in_(['nan', 'NaN', 'NAN', 'Nan'])
        ).count()
        summary_stats["ud_c3"] = summary_ud_c3_count

        # Compter UD C4
        summary_ud_c4_count = db.query(SiretSummary).filter(
            SiretSummary.ud_c4.in_(['nan', 'NaN', 'NAN', 'Nan'])
        ).count()
        summary_stats["ud_c4"] = summary_ud_c4_count

        # Compter IDCC
        summary_idcc_count = db.query(SiretSummary).filter(
            SiretSummary.idcc.in_(['nan', 'NaN', 'NAN', 'Nan'])
        ).count()
        summary_stats["idcc"] = summary_idcc_count

        # Nettoyer SiretSummary.fd_c3
        if summary_fd_c3_count > 0:
            db.execute(
                update(SiretSummary)
                .where(SiretSummary.fd_c3.in_(['nan', 'NaN', 'NAN', 'Nan']))
                .values(fd_c3=None)
            )

        # Nettoyer SiretSummary.fd_c4
        if summary_fd_c4_count > 0:
            db.execute(
                update(SiretSummary)
                .where(SiretSummary.fd_c4.in_(['nan', 'NaN', 'NAN', 'Nan']))
                .values(fd_c4=None)
            )

        # Nettoyer SiretSummary.ud_c3
        if summary_ud_c3_count > 0:
            db.execute(
                update(SiretSummary)
                .where(SiretSummary.ud_c3.in_(['nan', 'NaN', 'NAN', 'Nan']))
                .values(ud_c3=None)
            )

        # Nettoyer SiretSummary.ud_c4
        if summary_ud_c4_count > 0:
            db.execute(
                update(SiretSummary)
                .where(SiretSummary.ud_c4.in_(['nan', 'NaN', 'NAN', 'Nan']))
                .values(ud_c4=None)
            )

        # Nettoyer SiretSummary.idcc
        if summary_idcc_count > 0:
            db.execute(
                update(SiretSummary)
                .where(SiretSummary.idcc.in_(['nan', 'NaN', 'NAN', 'Nan']))
                .values(idcc=None)
            )

        summary_stats["total"] = (
            summary_fd_c3_count + summary_fd_c4_count +
            summary_ud_c3_count + summary_ud_c4_count + summary_idcc_count
        )
        stats["tables"]["SiretSummary"] = summary_stats

        # Commit toutes les modifications
        db.commit()

        # Calculer le total
        stats["total_cleaned"] = (
            inv_stats["total"] + pv_stats["total"] + summary_stats["total"]
        )

        stats["message"] = f"✅ Nettoyage terminé avec succès! {stats['total_cleaned']} valeurs 'nan' nettoyées."

        return JSONResponse(content=stats)

    except Exception as e:
        db.rollback()
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e),
                "message": "❌ Erreur lors du nettoyage des valeurs 'nan'"
            }
        )

@app.get("/recherche-siret", response_class=HTMLResponse)
def recherche_siret_page(request: Request):
    return templates.TemplateResponse("recherche-siret.html", {
        "request": request,
        "admin_api_key": ADMIN_API_KEY,
    })


@app.get("/etablissements-carte", response_class=HTMLResponse)
def etablissements_carte_page(request: Request):
    """
    Page de recherche et visualisation des établissements d'une entreprise sur une carte.
    Utilise l'API Pappers pour récupérer les données avec géolocalisation.
    """
    return templates.TemplateResponse("etablissements-carte.html", {
        "request": request,
    })


@app.get("/mentions-legales", response_class=HTMLResponse)
def mentions_legales_page(request: Request):
    return templates.TemplateResponse("mentions-legales.html", {"request": request})


@app.get("/siret/{siret}", response_class=HTMLResponse)
def siret_detail(siret: str, request: Request, db: Session = Depends(get_session)):
    from .models import PVEvent, Invitation
    param_siret = (siret or "").strip()
    normalized_param = "".join(ch for ch in param_siret if ch.isdigit())
    candidate_sirets = []
    for value in (normalized_param, param_siret):
        if value and value not in candidate_sirets:
            candidate_sirets.append(value)
    if not candidate_sirets:
        candidate_sirets.append(siret)
    query_sirets = candidate_sirets or [siret]

    # Résumé agrégé issu de siret_summary
    summary_row = None
    for candidate in candidate_sirets:
        summary_row = (
            db.query(SiretSummary)
            .filter(SiretSummary.siret == candidate)
            .first()
        )
        if summary_row:
            break

    # Historiques détaillés
    pv_history = (
        db.query(PVEvent)
        .filter(PVEvent.siret.in_(query_sirets))
        .order_by(PVEvent.date_pv.desc())
        .all()
    )
    invitations = (
        db.query(Invitation)
        .filter(Invitation.siret.in_(query_sirets))
        .order_by(Invitation.date_invit.desc())
        .all()
    )

    if not summary_row and not pv_history and not invitations:
        return templates.TemplateResponse("siret.html", {"request": request, "row": None})

    # Helpers -----------------------------------------------------------------
    def _to_date(value):
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            candidate = value.strip()
            if not candidate:
                return None
            normalized = candidate.replace("Z", "+00:00")
            try:
                return datetime.fromisoformat(normalized).date()
            except ValueError:
                pass
            iso_prefix = candidate[:10]
            if len(iso_prefix) == 10:
                try:
                    return datetime.strptime(iso_prefix, "%Y-%m-%d").date()
                except ValueError:
                    pass
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
                try:
                    return datetime.strptime(candidate, fmt).date()
                except ValueError:
                    continue
        return None

    def _to_datetime(value):
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime.combine(value, datetime.min.time())
        if isinstance(value, str):
            candidate = value.strip()
            if not candidate:
                return None
            normalized = candidate.replace("Z", "+00:00")
            try:
                return datetime.fromisoformat(normalized)
            except ValueError:
                pass
            for fmt in (
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d",
                "%d/%m/%Y %H:%M:%S",
                "%d/%m/%Y %H:%M",
                "%d/%m/%Y",
                "%Y/%m/%d %H:%M:%S",
                "%Y/%m/%d",
            ):
                try:
                    return datetime.strptime(candidate, fmt)
                except ValueError:
                    continue
        return None

    def _to_bool(value):
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            cleaned = value.strip().lower()
            if not cleaned:
                return None
            if cleaned in {"1", "true", "vrai", "oui", "o", "y", "yes"}:
                return True
            if cleaned in {"0", "false", "faux", "non", "n"}:
                return False
        return None

    def _add_years(base: date | None, years: int) -> date | None:
        if base is None:
            return None
        target_year = base.year + years
        try:
            return base.replace(year=target_year)
        except ValueError:
            last_day = calendar.monthrange(target_year, base.month)[1]
            return date(target_year, base.month, min(base.day, last_day))
    def _to_int(value):
        if value is None:
            return None
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            if value != value:  # NaN
                return None
            return int(round(value))
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                return None
            cleaned = cleaned.replace("\xa0", "").replace(" ", "").replace(",", ".")
            try:
                return int(float(cleaned))
            except ValueError:
                return None
        return None

    def _to_float(value):
        if value is None:
            return None
        if isinstance(value, (int, float)):
            if isinstance(value, float) and value != value:
                return None
            return float(value)
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                return None
            cleaned = cleaned.replace("\xa0", "").replace(",", ".")
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None

    def _set_if_missing(obj, attr: str, value):
        if value is None:
            return
        current = getattr(obj, attr, None)
        if current is None or (isinstance(current, str) and not current.strip()):
            setattr(obj, attr, value)

    def _clean_cycle(value) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        return text.upper()

    def _cycle_event(cycle_name: str | None):
        target = _clean_cycle(cycle_name)
        if not target:
            return None
        for pv in pv_history:
            candidate = _clean_cycle(getattr(pv, "cycle", None))
            if candidate == target:
                return pv
        return None

    # Construction du résumé exploitable dans le template ---------------------
    if summary_row:
        summary = summary_row
    else:
        defaults = {column.name: None for column in SiretSummary.__table__.columns}
        defaults["siret"] = siret
        summary = SimpleNamespace(**defaults)

    display_siret = next((candidate for candidate in candidate_sirets if candidate), siret)
    if getattr(summary, "siret", None) in (None, "") and display_siret:
        summary.siret = display_siret
    base_event = pv_history[0] if pv_history else None
    latest_invitation = invitations[0] if invitations else None
    pv_c3 = _cycle_event("C3")
    pv_c4 = _cycle_event("C4")

    if base_event:
        _set_if_missing(summary, "raison_sociale", base_event.raison_sociale)
        _set_if_missing(summary, "idcc", base_event.idcc)
        _set_if_missing(summary, "cp", base_event.cp)
        _set_if_missing(summary, "ville", base_event.ville)
        _set_if_missing(summary, "region", base_event.region)
        _set_if_missing(summary, "ul", base_event.ul)

    if latest_invitation:
        label = latest_invitation.denomination or latest_invitation.enseigne
        _set_if_missing(summary, "raison_sociale", label)
        _set_if_missing(summary, "cp", latest_invitation.code_postal)
        _set_if_missing(summary, "ville", latest_invitation.commune)

    if pv_c3:
        _set_if_missing(summary, "fd_c3", pv_c3.fd)
        _set_if_missing(summary, "ud_c3", pv_c3.ud)
        _set_if_missing(summary, "date_pv_c3", _to_date(pv_c3.date_pv))
        _set_if_missing(summary, "inscrits_c3", _to_int(pv_c3.inscrits))
        _set_if_missing(summary, "votants_c3", _to_int(pv_c3.votants))
        _set_if_missing(summary, "cgt_voix_c3", _to_int(pv_c3.cgt_voix))
        _set_if_missing(summary, "cfdt_voix_c3", _to_int(pv_c3.cfdt_voix))
        _set_if_missing(summary, "fo_voix_c3", _to_int(pv_c3.fo_voix))
        _set_if_missing(summary, "cftc_voix_c3", _to_int(pv_c3.cftc_voix))
        _set_if_missing(summary, "cgc_voix_c3", _to_int(pv_c3.cgc_voix))
        _set_if_missing(summary, "unsa_voix_c3", _to_int(pv_c3.unsa_voix))
        _set_if_missing(summary, "sud_voix_c3", _to_int(pv_c3.sud_voix))
        _set_if_missing(summary, "solidaire_voix_c3", _to_int(pv_c3.solidaire_voix))
        _set_if_missing(summary, "autre_voix_c3", _to_int(pv_c3.autre_voix))

    if pv_c4:
        _set_if_missing(summary, "fd_c4", pv_c4.fd)
        _set_if_missing(summary, "ud_c4", pv_c4.ud)
        _set_if_missing(summary, "date_pv_c4", _to_date(pv_c4.date_pv))
        _set_if_missing(summary, "inscrits_c4", _to_int(pv_c4.inscrits))
        _set_if_missing(summary, "votants_c4", _to_int(pv_c4.votants))
        _set_if_missing(summary, "cgt_voix_c4", _to_int(pv_c4.cgt_voix))
        _set_if_missing(summary, "cfdt_voix_c4", _to_int(pv_c4.cfdt_voix))
        _set_if_missing(summary, "fo_voix_c4", _to_int(pv_c4.fo_voix))
        _set_if_missing(summary, "cftc_voix_c4", _to_int(pv_c4.cftc_voix))
        _set_if_missing(summary, "cgc_voix_c4", _to_int(pv_c4.cgc_voix))
        _set_if_missing(summary, "unsa_voix_c4", _to_int(pv_c4.unsa_voix))
        _set_if_missing(summary, "sud_voix_c4", _to_int(pv_c4.sud_voix))
        _set_if_missing(summary, "solidaire_voix_c4", _to_int(pv_c4.solidaire_voix))
        _set_if_missing(summary, "autre_voix_c4", _to_int(pv_c4.autre_voix))
        _set_if_missing(summary, "effectif_siret", _to_int(pv_c4.effectif_siret))
        _set_if_missing(summary, "tranche1_effectif", pv_c4.tranche1_effectif)
        _set_if_missing(summary, "tranche2_effectif", pv_c4.tranche2_effectif)
        siret_moins_50_value = _to_int(pv_c4.siret_moins_50)
        if siret_moins_50_value is not None:
            _set_if_missing(summary, "siret_moins_50", bool(siret_moins_50_value))
        _set_if_missing(summary, "nb_college_siret", _to_int(pv_c4.nb_college_siret))
        _set_if_missing(summary, "score_siret_cgt", _to_int(pv_c4.score_siret_cgt))
        _set_if_missing(summary, "score_siret_cfdt", _to_int(pv_c4.score_siret_cfdt))
        _set_if_missing(summary, "score_siret_fo", _to_int(pv_c4.score_siret_fo))
        _set_if_missing(summary, "score_siret_cftc", _to_int(pv_c4.score_siret_cftc))
        _set_if_missing(summary, "score_siret_cgc", _to_int(pv_c4.score_siret_cgc))
        _set_if_missing(summary, "score_siret_unsa", _to_int(pv_c4.score_siret_unsa))
        _set_if_missing(summary, "score_siret_sud", _to_int(pv_c4.score_siret_sud))
        _set_if_missing(summary, "score_siret_autre", _to_int(pv_c4.score_siret_autre))
        _set_if_missing(summary, "pct_siret_cgt", _to_float(pv_c4.pct_siret_cgt))
        _set_if_missing(summary, "pct_siret_cfdt", _to_float(pv_c4.pct_siret_cfdt))
        _set_if_missing(summary, "pct_siret_fo", _to_float(pv_c4.pct_siret_fo))
        _set_if_missing(summary, "pct_siret_cgc", _to_float(pv_c4.pct_siret_cgc))
        _set_if_missing(summary, "presence_cgt_siret", pv_c4.presence_cgt_siret)
        _set_if_missing(summary, "pres_siret_cgt", pv_c4.pres_siret_cgt)

    if not getattr(summary, "effectif_siret", None) and pv_c3:
        _set_if_missing(summary, "effectif_siret", _to_int(pv_c3.effectif_siret))
        _set_if_missing(summary, "tranche1_effectif", pv_c3.tranche1_effectif)
        _set_if_missing(summary, "tranche2_effectif", pv_c3.tranche2_effectif)

    if getattr(summary, "dep", None) in (None, ""):
        summary.dep = (pv_c4.ud if pv_c4 and pv_c4.ud else (pv_c3.ud if pv_c3 else None))

    if getattr(summary, "ul", None) in (None, ""):
        summary.ul = pv_c4.ul if pv_c4 and pv_c4.ul else (pv_c3.ul if pv_c3 else getattr(summary, "ul", None))

    if getattr(summary, "statut_pap", None) in (None, ""):
        if pv_c4 and pv_c3:
            summary.statut_pap = "C3+C4"
        elif pv_c4:
            summary.statut_pap = "C4"
        elif pv_c3:
            summary.statut_pap = "C3"
        elif invitations:
            summary.statut_pap = "Invitation"

    # Dates clés ----------------------------------------------------------------
    for attr in ("date_pv_c3", "date_pv_c4", "date_pv_max", "date_pap_c5"):
        value = getattr(summary, attr, None)
        if isinstance(value, str):
            parsed = _to_date(value)
            setattr(summary, attr, parsed)

    if getattr(summary, "date_pv_max", None) is None and pv_history:
        candidates = [d for d in (_to_date(pv.date_pv) for pv in pv_history) if d]
        if candidates:
            summary.date_pv_max = max(candidates)

    latest_inv_date = latest_invitation.date_invit if latest_invitation else None
    if getattr(summary, "date_pap_c5", None) is None and latest_inv_date:
        summary.date_pap_c5 = latest_inv_date

    pap_display = getattr(summary, "date_pap_c5", None) or latest_inv_date
    if isinstance(pap_display, str):
        pap_display = _to_date(pap_display) or pap_display
    summary.date_pap_c5_display = pap_display
    summary.date_pap_c5_label = (
        pap_display.strftime("%d/%m/%Y")
        if isinstance(pap_display, (date, datetime))
        else (str(pap_display) if pap_display else None)
    )

    # Indicateur d'implantation CGT (C4 uniquement) ---------------------------
    if getattr(summary, "cgt_implantee", None) is None:
        def _truthy_flag(value) -> bool:
            if value is None:
                return False
            text = str(value).strip().lower()
            return text in {"oui", "o", "1", "true", "vrai", "y", "yes"}

        cgt_present = False
        for pv in pv_history:
            # Ne compter que le cycle C4
            if getattr(pv, "cycle", None) != "C4":
                continue
            if _to_int(pv.cgt_voix) and _to_int(pv.cgt_voix) > 0:
                cgt_present = True
                break
            if _truthy_flag(pv.pres_siret_cgt) or _truthy_flag(pv.presence_cgt_siret) or _truthy_flag(pv.pres_pv_cgt):
                cgt_present = True
                break
        summary.cgt_implantee = cgt_present

    row = summary

    # Timeline -----------------------------------------------------------------
    timeline_events = []
    for pv in pv_history:
        event_date = _to_date(pv.date_pv)
        raw_cycle = getattr(pv, "cycle", None)
        cycle_label = _clean_cycle(raw_cycle)
        type_label = getattr(pv, "type", None)
        type_text = str(type_label).lower().strip() if type_label is not None else ""
        display_cycle = cycle_label
        if not display_cycle and type_label is not None:
            display_cycle = str(type_label).strip() or None
        if not display_cycle and raw_cycle is not None:
            candidate_cycle = str(raw_cycle).strip()
            display_cycle = candidate_cycle or None
        timeline_events.append(
            {
                "date": event_date,
                "date_label": event_date.strftime("%d/%m/%Y") if event_date else None,
                "type": "pv",
                "cycle": display_cycle,
                "inscrits": _to_int(pv.inscrits),
                "votants": _to_int(pv.votants),
                "cgt_voix": _to_int(pv.cgt_voix),
                "carence": "car" in type_text,
                "fd": pv.fd,
                "ud": pv.ud,
            }
        )

    for inv in invitations:
        event_date = _to_date(inv.date_invit)
        timeline_events.append(
            {
                "date": event_date,
                "date_label": event_date.strftime("%d/%m/%Y") if event_date else None,
                "type": "invitation",
                "source": inv.source,
            }
        )

    timeline_events.sort(key=lambda ev: ev["date"] or date.min, reverse=True)

    cycle_projection = None
    if row is not None:
        cycle_duration_years = 4
        base_c4_date = _to_date(getattr(row, "date_pv_c4", None))
        if base_c4_date:
            projected_date = _add_years(base_c4_date, cycle_duration_years)
            if projected_date:
                countdown_details = None
                today = date.today()
                total_days = (projected_date - today).days
                if total_days is not None:
                    if total_days > 0:
                        months_remaining = int(round(total_days / 30.44))
                        years_remaining = round(total_days / 365, 1)
                        if total_days > 365:
                            years_label = f"{years_remaining:.1f}".rstrip("0").rstrip(".")
                            primary_label = f"{years_label} ans"
                        elif total_days > 60:
                            primary_label = f"{months_remaining} mois"
                        else:
                            primary_label = f"{total_days} jours"
                        secondary_label = f"{total_days} jours au total"
                        status = "upcoming"
                    elif total_days > -30:
                        primary_label = "Bientôt !"
                        secondary_label = "Échéance proche"
                        status = "imminent"
                    else:
                        primary_label = "Dépassé"
                        secondary_label = f"de {abs(total_days)} jours"
                        status = "overdue"
                    countdown_details = {
                        "total_days": total_days,
                        "primary_label": primary_label,
                        "secondary_label": secondary_label,
                        "status": status,
                    }

                cycle_projection = {
                    "projected_date": projected_date,
                    "projected_label": projected_date.strftime("%d/%m/%Y"),
                    "duration_years": cycle_duration_years,
                    "countdown": countdown_details,
                }

    # Informations Sirene -------------------------------------------------------
    sirene_data = None
    if invitations:
        enriched_inv = next((inv for inv in invitations if inv.date_enrichissement is not None), None)
        if enriched_inv:
            enrichment_dt = _to_datetime(enriched_inv.date_enrichissement)
            enrichment_raw = enriched_inv.date_enrichissement
            if enrichment_dt:
                enrichment_label = enrichment_dt.strftime("%d/%m/%Y")
            elif enrichment_raw:
                enrichment_label = str(enrichment_raw).strip() or None
            else:
                enrichment_label = None

            sirene_data = {
                "denomination": enriched_inv.denomination,
                "enseigne": enriched_inv.enseigne,
                "adresse": enriched_inv.adresse,
                "code_postal": enriched_inv.code_postal,
                "commune": enriched_inv.commune,
                "activite_principale": enriched_inv.activite_principale,
                "libelle_activite": enriched_inv.libelle_activite,
                "tranche_effectifs": enriched_inv.tranche_effectifs,
                "effectifs_label": enriched_inv.effectifs_label,
                "est_siege": _to_bool(enriched_inv.est_siege),
                "est_actif": _to_bool(enriched_inv.est_actif),
                "categorie_entreprise": enriched_inv.categorie_entreprise,
                "idcc": enriched_inv.idcc,
                "idcc_url": enriched_inv.idcc_url,
                "date_enrichissement": enrichment_dt,
                "date_enrichissement_label": enrichment_label,
                "date_enrichissement_raw": enrichment_raw,
            }

    return templates.TemplateResponse(
        "siret.html",
        {
            "request": request,
            "row": row,
            "pv_history": pv_history,
            "invitations": invitations,
            "timeline_events": timeline_events,
            "sirene_data": sirene_data,
            "cycle_projection": cycle_projection,
        },
    )
