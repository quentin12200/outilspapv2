# app/main.py

import os
import hashlib
import urllib.request
import logging
import re
import unicodedata
import tempfile
from types import SimpleNamespace
from urllib.parse import urlparse
from fastapi import FastAPI, Request, Depends, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import Any, Mapping

# --- Imports bas niveau (engine/Base) d'abord ---
from .db import get_session, Base, engine, SessionLocal
from datetime import date, datetime

from .models import Invitation, SiretSummary, PVEvent

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


def _is_truthy(value: str) -> bool:
    return value in {"1", "true", "yes", "on"}

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

def _download(url: str, dest: str, token: str | None = None) -> None:
    headers = {"Accept": "application/octet-stream"}
    if token:
        headers["Authorization"] = f"token {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp, open(dest, "wb") as f:
        f.write(resp.read())

logger = logging.getLogger(__name__)


def _download_to_temp(url: str, token: str | None = None) -> str:
    """Télécharge un fichier distant vers un fichier temporaire et retourne son chemin."""
    suffix = os.path.splitext(urlparse(url).path)[1]
    fd, tmp_path = tempfile.mkstemp(prefix="papcse-asset-", suffix=suffix or "")
    os.close(fd)
    try:
        _download(url, tmp_path, token=token)
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
    if not INVITATIONS_URL:
        return

    existing = session.query(func.count(Invitation.id)).scalar() or 0
    if existing > 0:
        logger.info(
            "Skipping automatic invitation import: table already contains %s rows.",
            existing,
        )
        return

    tmp_path: str | None = None
    try:
        tmp_path = _download_to_temp(INVITATIONS_URL, token=INVITATIONS_GH_TOKEN)
        if INVITATIONS_SHA256:
            digest = _sha256_file(tmp_path).lower()
            if digest != INVITATIONS_SHA256:
                _log_or_raise_hash_mismatch(
                    "invitations seed",
                    INVITATIONS_SHA256,
                    digest,
                    True,
                    INVITATIONS_FAIL_ON_HASH_MISMATCH,
                )

        from . import etl  # Import tardif pour éviter les références circulaires

        inserted = etl.ingest_invit_excel(session, tmp_path)
        logger.info(
            "Automatically imported %s invitations from %s.",
            inserted,
            INVITATIONS_URL,
        )
    except Exception:
        logger.exception("Automatic invitation import failed")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass

# Télécharge/ prépare le fichier AVANT d’importer les routers
ensure_sqlite_asset()

# =========================================================
# App & Routers
# =========================================================

# ⚠️ Import des routers APRÈS ensure_sqlite_asset()
from .routers import api  # noqa: E402

app = FastAPI(title="PAP/CSE · Tableau de bord")
app.include_router(api.router)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

@app.on_event("startup")
def on_startup():
    # Création des tables après que le fichier .db soit prêt
    Base.metadata.create_all(bind=engine)

    # Exécute les migrations pour ajouter les colonnes Sirene si nécessaire
    from .migrations import run_migrations
    run_migrations()

    # Si le résumé SIRET est vide, le reconstruire automatiquement afin que
    # le tableau de bord ne s'affiche pas avec des compteurs à zéro lors du
    # premier démarrage (base préremplie).
    try:
        with SessionLocal() as session:
            _auto_seed_invitations(session)
            total_summary = session.query(func.count(SiretSummary.siret)).scalar() or 0
            if total_summary == 0:
                from . import etl

                generated = etl.build_siret_summary(session)
                logger.info("Siret summary rebuilt at startup (%s rows)", generated)
    except Exception:  # pragma: no cover - protection démarrage
        logger.exception("Unable to rebuild siret_summary at startup")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/presentation", response_class=HTMLResponse)
def presentation(request: Request, db: Session = Depends(get_session)):
    total_sirets = db.query(func.count(SiretSummary.siret)).scalar() or 0
    invitations_total = db.query(func.count(Invitation.id)).scalar() or 0
    pap_sirets = (
        db.query(func.count(SiretSummary.siret))
        .filter(SiretSummary.date_pap_c5.isnot(None))
        .scalar()
        or 0
    )
    c4_carence = (
        db.query(func.count(SiretSummary.siret))
        .filter(SiretSummary.carence_c4.is_(True))
        .scalar()
        or 0
    )

    feature_blocks = [
        {
            "title": "Tableau de bord",
            "description": "Suivez les indicateurs clés sur les SIRET à enjeu et visualisez la couverture des invitations PAP.",
            "icon": "fa-chart-line",
            "href": "/",
        },
        {
            "title": "Invitations PAP",
            "description": "Retrouvez chaque invitation importée, filtrez par département ou source et suivez les relances.",
            "icon": "fa-envelope-open-text",
            "href": "/invitations",
        },
        {
            "title": "Recherche SIRET",
            "description": "Identifiez rapidement un établissement via l’API Sirene et reliez-le à vos ciblages locaux.",
            "icon": "fa-search",
            "href": "/recherche-siret",
        },
        {
            "title": "Mes ciblages",
            "description": "Chargez vos fichiers de ciblage C3/C4 pour croiser audience, résultats et priorités CGT.",
            "icon": "fa-crosshairs",
            "href": "/ciblage",
        },
    ]

    timeline = [
        {
            "title": "Invitation PAP reçue",
            "subtitle": "Le PAP arrive dans l’UD / FD",
            "description": "Enregistrez la date dans l’outil pour tracer le point de départ du cycle C5.",
            "icon": "fa-inbox",
        },
        {
            "title": "Mobilisation des équipes",
            "subtitle": "Préparation de la candidature",
            "description": "Associez le SIRET aux militant·es référent·es et vérifiez l’implantation CGT existante.",
            "icon": "fa-people-group",
        },
        {
            "title": "Scrutin C5",
            "subtitle": "PV à récupérer",
            "description": "Lorsque le PV est publié, rattachez-le au même SIRET pour fermer la boucle PAP → PV.",
            "icon": "fa-file-circle-check",
        },
    ]

    c5_calendar = [
        {
            "period": "T1 2025",
            "focus": "Campagne d’invitations massives",
            "details": "Consolider les retours PAP et prioriser les établissements à ≥ 1 000 inscrit·es.",
        },
        {
            "period": "T2 2025",
            "focus": "Dépôt des listes",
            "details": "Ajuster les candidatures avec les UD / FD et suivre les carences à éviter.",
        },
        {
            "period": "T3 2025",
            "focus": "Tenue des scrutins C5",
            "details": "Anticiper la collecte des PV et pointer les établissements sans retour.",
        },
        {
            "period": "T4 2025",
            "focus": "Analyse des résultats",
            "details": "Comparer voix CGT / inscrits pour mesurer l’impact des invitations.",
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
            "feature_blocks": feature_blocks,
            "timeline": timeline,
            "c5_calendar": c5_calendar,
        },
    )


@app.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    q: str = "",
    sort: str = "date_pap_c5",
    fd: str = "",
    dep: str = "",
    statut: str = "",
    cgt_implantee: str = "",
    db: Session = Depends(get_session)
):
    qs = db.query(SiretSummary)

    # Recherche textuelle
    if q:
        like = f"%{q}%"
        qs = qs.filter(
            (SiretSummary.siret.like(like)) |
            (SiretSummary.raison_sociale.ilike(like))
        )

    # Filtre par FD (recherche dans fd_c3 ou fd_c4)
    if fd:
        fd_like = f"%{fd}%"
        qs = qs.filter(
            (SiretSummary.fd_c3.ilike(fd_like)) |
            (SiretSummary.fd_c4.ilike(fd_like))
        )

    # Filtre par département
    if dep:
        qs = qs.filter(SiretSummary.dep == dep)

    # Filtre par statut PAP
    if statut:
        qs = qs.filter(SiretSummary.statut_pap == statut)

    # Filtre CGT implantée
    if cgt_implantee:
        if cgt_implantee == "oui":
            qs = qs.filter(SiretSummary.cgt_implantee == True)
        elif cgt_implantee == "non":
            qs = qs.filter(SiretSummary.cgt_implantee == False)

    # Apply sorting
    if sort == "inscrits_c3":
        qs = qs.order_by(SiretSummary.inscrits_c3.desc().nullslast())
    elif sort == "inscrits_c4":
        qs = qs.order_by(SiretSummary.inscrits_c4.desc().nullslast())
    else:  # default: date_pap_c5
        qs = qs.order_by(SiretSummary.date_pap_c5.desc().nullslast())

    rows = qs.limit(100).all()

    # Ajoute un fallback pour l'affichage de la date PAP C5 directement depuis les invitations
    missing_dates = [r.siret for r in rows if getattr(r, "date_pap_c5", None) is None]
    fallback_dates: dict[str, date] = {}
    if missing_dates:
        fallback_dates = dict(
            db.query(
                Invitation.siret,
                func.max(Invitation.date_invit).label("latest_date"),
            )
            .filter(Invitation.siret.in_(missing_dates))
            .group_by(Invitation.siret)
            .all()
        )

    for r in rows:
        display_date = getattr(r, "date_pap_c5", None) or fallback_dates.get(r.siret)
        if isinstance(display_date, str):
            parsed = _parse_date(display_date)
            display_date = parsed or display_date
        label = None
        if isinstance(display_date, (datetime, date)):
            label = display_date.strftime("%d/%m/%Y")
        elif display_date is not None:
            label = str(display_date)
        setattr(r, "date_pap_c5_display", display_date)
        setattr(r, "date_pap_c5_label", label)

    top_departments_query = (
        db.query(
            SiretSummary.dep.label("dep"),
            func.count(SiretSummary.siret).label("count"),
        )
        .filter(SiretSummary.date_pap_c5.isnot(None))
        .filter(SiretSummary.dep.isnot(None))
        .group_by(SiretSummary.dep)
        .order_by(func.count(SiretSummary.siret).desc())
        .limit(10)
        .all()
    )

    top_departments = [
        {"dep": dep or "Non renseigné", "count": count}
        for dep, count in top_departments_query
    ]

    # Récupère les valeurs distinctes pour les filtres
    all_deps = db.query(SiretSummary.dep).distinct().filter(SiretSummary.dep.isnot(None)).order_by(SiretSummary.dep).all()
    all_fds = db.query(SiretSummary.fd_c3).distinct().filter(SiretSummary.fd_c3.isnot(None)).order_by(SiretSummary.fd_c3).all()
    all_fds_c4 = db.query(SiretSummary.fd_c4).distinct().filter(SiretSummary.fd_c4.isnot(None)).order_by(SiretSummary.fd_c4).all()

    # Combine les FDs C3 et C4 et déduplique
    all_fds_combined = list(set([fd[0] for fd in all_fds] + [fd[0] for fd in all_fds_c4 if fd[0]]))
    all_fds_combined.sort()

    return templates.TemplateResponse("index.html", {
        "request": request,
        "rows": rows,
        "top_departments": top_departments,
        "q": q,
        "sort": sort,
        "fd": fd,
        "dep": dep,
        "statut": statut,
        "cgt_implantee": cgt_implantee,
        "all_deps": [d[0] for d in all_deps],
        "all_fds": all_fds_combined,
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

    options = {
        "cycles": set(),
        "institutions": set(),
        "fds": set(),
        "idccs": set(),
        "uds": set(),
        "regions": set(),
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

        effectif_value = _to_number(row.effectif_siret)
        if effectif_value is None:
            effectif_value = _to_number(row.inscrits)

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

        if search_term:
            siret_value = str(row.siret or "")
            raison = (row.raison_sociale or "").lower()
            if search_term not in siret_value.lower() and search_term not in raison:
                continue

        key = f"{row.siret or 'pv'}-{row.cycle or 'na'}"
        payload = {
            "siret": row.siret,
            "raison_sociale": row.raison_sociale,
            "ud": row.ud,
            "region": row.region,
            "effectif": int(effectif_value) if effectif_value is not None else None,
            "cycle": row.cycle,
            "date": parsed_date,
            "date_display": parsed_date.strftime("%d/%m/%Y"),
            "date_pv": _parse_date(row.date_pv),
            "institution": row.institution,
            "fd": row.fd,
            "idcc": row.idcc,
        }

        existing = per_siret.get(key)
        if existing is None or parsed_date < existing["date"]:
            per_siret[key] = payload

    elections_list = sorted(per_siret.values(), key=lambda item: item["date"])

    return templates.TemplateResponse(
        "calendrier.html",
        {
            "request": request,
            "elections": elections_list,
            "filters": {
                "min_effectif": min_effectif,
                "q": q,
                "cycle": cycle_filter,
                "institution": institution_filter,
                "fd": fd_filter,
                "idcc": idcc_filter,
                "ud": ud_filter,
                "region": region_filter,
            },
            "options": {
                "cycles": sorted(options["cycles"]),
                "institutions": sorted(options["institutions"]),
                "fds": sorted(options["fds"]),
                "idccs": sorted(options["idccs"]),
                "uds": sorted(options["uds"]),
                "regions": sorted(options["regions"]),
            },
        },
    )


@app.get("/invitations", response_class=HTMLResponse)
def invitations(
    request: Request,
    q: str = "",
    source: str = "",
    est_actif: str = "",
    est_siege: str = "",
    db: Session = Depends(get_session),
):
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

    invitations = (
        qs.order_by(Invitation.date_invit.desc().nullslast(), Invitation.id.desc()).all()
    )

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

    sources = [row[0] for row in db.query(Invitation.source).distinct().order_by(Invitation.source).all() if row[0]]

    return templates.TemplateResponse(
        "invitations.html",
        {
            "request": request,
            "invitations": invitations,
            "q": q,
            "source": source,
            "sources": sources,
            "est_actif": est_actif,
            "est_siege": est_siege,
            "total_invitations": len(invitations),
        },
    )

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


@app.get("/ciblage", response_class=HTMLResponse)
def ciblage_get(request: Request, db: Session = Depends(get_session)):
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

def _format_date(value: date | None) -> str | None:
    if not value:
        return None
    return value.strftime("%d/%m/%Y")


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

        existing = per_siret.get(key)
        if existing is None or parsed_date < existing["date"]:
            per_siret[key] = payload

    return sorted(per_siret.values(), key=lambda item: item["date"])


@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request, db: Session = Depends(get_session)):
    total_pv = db.query(func.count(PVEvent.id)).scalar() or 0
    total_sirets = db.query(func.count(func.distinct(PVEvent.siret))).scalar() or 0
    total_summary = db.query(func.count(SiretSummary.siret)).scalar() or 0
    total_invitations = db.query(func.count(Invitation.id)).scalar() or 0

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
        "auto_enabled": bool(INVITATIONS_URL),
        "url": INVITATIONS_URL or None,
        "expected_hash": INVITATIONS_SHA256 or None,
        "count": total_invitations,
        "last_date": stats["last_invitation"],
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
        },
    )

@app.get("/admin/diagnostics", response_class=HTMLResponse)
def admin_diagnostics(request: Request, db: Session = Depends(get_session)):
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

    return templates.TemplateResponse("admin_diagnostics.html", {
        "request": request,
        "total": total,
        "unique_sirets": unique_sirets,
        "duplicates": duplicates,
        "sources": sources_data,
        "top_duplicates": top_duplicates,
        "has_duplicates": duplicates > 0
    })

@app.post("/admin/diagnostics/remove-duplicates")
def remove_duplicates(db: Session = Depends(get_session)):
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
def migrate_columns(db: Session = Depends(get_session)):
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

@app.get("/recherche-siret", response_class=HTMLResponse)
def recherche_siret_page(request: Request):
    return templates.TemplateResponse("recherche-siret.html", {"request": request})

@app.get("/siret/{siret}", response_class=HTMLResponse)
def siret_detail(siret: str, request: Request, db: Session = Depends(get_session)):
    from .models import PVEvent, Invitation

    # Résumé agrégé issu de siret_summary
    summary_row = db.query(SiretSummary).filter(SiretSummary.siret == siret).first()

    # Historiques détaillés
    pv_history = (
        db.query(PVEvent)
        .filter(PVEvent.siret == siret)
        .order_by(PVEvent.date_pv.desc())
        .all()
    )
    invitations = (
        db.query(Invitation)
        .filter(Invitation.siret == siret)
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
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
                try:
                    return datetime.strptime(candidate, fmt).date()
                except ValueError:
                    continue
        return None

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

    def _cycle_event(cycle_name: str):
        target = (cycle_name or "").strip().upper()
        for pv in pv_history:
            if (pv.cycle or "").strip().upper() == target:
                return pv
        return None

    # Construction du résumé exploitable dans le template ---------------------
    if summary_row:
        summary = summary_row
    else:
        defaults = {column.name: None for column in SiretSummary.__table__.columns}
        defaults["siret"] = siret
        summary = SimpleNamespace(**defaults)

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
            if parsed:
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

    # Indicateur d'implantation CGT --------------------------------------------
    if getattr(summary, "cgt_implantee", None) is None:
        def _truthy_flag(value) -> bool:
            if value is None:
                return False
            text = str(value).strip().lower()
            return text in {"oui", "o", "1", "true", "vrai", "y", "yes"}

        cgt_present = False
        for pv in pv_history:
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
        timeline_events.append(
            {
                "date": event_date,
                "date_label": event_date.strftime("%d/%m/%Y") if event_date else None,
                "type": "pv",
                "cycle": pv.cycle,
                "inscrits": _to_int(pv.inscrits),
                "votants": _to_int(pv.votants),
                "cgt_voix": _to_int(pv.cgt_voix),
                "carence": "car" in (pv.type or "").lower(),
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

    # Informations Sirene -------------------------------------------------------
    sirene_data = None
    if invitations:
        enriched_inv = next((inv for inv in invitations if inv.date_enrichissement is not None), None)
        if enriched_inv:
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
                "est_siege": enriched_inv.est_siege,
                "est_actif": enriched_inv.est_actif,
                "categorie_entreprise": enriched_inv.categorie_entreprise,
                "date_enrichissement": enriched_inv.date_enrichissement,
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
        },
    )
