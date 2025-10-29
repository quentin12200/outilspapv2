from __future__ import annotations

import hashlib
import os
import re
import urllib.request
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from .config import IS_SQLITE
from .core.logging_config import get_logger, setup_logging
from .core.pagination import PageParams, build_pagination_html, paginate
from .core.security import verify_admin
from .db import Base, SessionLocal, engine, get_session
from .etl_improved import build_siret_summary, compute_global_stats, ensure_schema
from .models import Invitation, PVEvent, SiretSummary
from .normalization import normalize_fd_label, normalize_os_label

setup_logging(os.getenv("LOG_LEVEL", "INFO"), os.getenv("LOG_FILE"))
logger = get_logger(__name__)

DB_ASSET_URL = (os.getenv("DB_URL") or os.getenv("DATABASE_RELEASE_URL") or "").strip()
DB_ASSET_TOKEN = (os.getenv("DB_GH_TOKEN") or "").strip() or None
DB_ASSET_SHA = (
    os.getenv("DB_SHA256")
    or os.getenv("DB_CHECKSUM")
    or os.getenv("DATABASE_RELEASE_SHA256")
    or os.getenv("DATABASE_RELEASE_CHECKSUM")
    or ""
).strip().lower()
if DB_ASSET_SHA.startswith("sha256:"):
    DB_ASSET_SHA = DB_ASSET_SHA.split(":", 1)[1]
if DB_ASSET_SHA and not re.fullmatch(r"[0-9a-f]{64}", DB_ASSET_SHA):
    DB_ASSET_SHA = ""


def _sqlite_path_from_engine() -> Optional[Path]:
    if not IS_SQLITE:
        return None
    db_path = engine.url.database
    if not db_path or db_path == ":memory:":
        return None
    return Path(db_path)


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _download(url: str, dest: Path, token: Optional[str] = None) -> None:
    headers = {"Accept": "application/octet-stream"}
    if token:
        headers["Authorization"] = f"token {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp, dest.open("wb") as handle:
        handle.write(resp.read())


def ensure_sqlite_asset() -> None:
    db_path = _sqlite_path_from_engine()
    if not db_path:
        return
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if DB_ASSET_URL and not db_path.exists():
        logger.info("Téléchargement de la base SQLite depuis %s", DB_ASSET_URL)
        _download(DB_ASSET_URL, db_path, token=DB_ASSET_TOKEN)
    if DB_ASSET_SHA and db_path.exists():
        digest = _sha256_file(db_path).lower()
        if digest != DB_ASSET_SHA:
            if DB_ASSET_URL:
                logger.warning(
                    "Empreinte SHA256 inattendue pour %s (obtenu %s, attendu %s). Téléchargement d'une copie propre…",
                    db_path,
                    digest,
                    DB_ASSET_SHA,
                )
                tmp_path = db_path.with_suffix(db_path.suffix + ".download")
                _download(DB_ASSET_URL, tmp_path, token=DB_ASSET_TOKEN)
                new_digest = _sha256_file(tmp_path).lower()
                if new_digest == DB_ASSET_SHA:
                    tmp_path.replace(db_path)
                    logger.info("Fichier SQLite remplacé après vérification de l'empreinte SHA256.")
                    return
                tmp_path.unlink(missing_ok=True)
            raise RuntimeError(
                "SHA256 mismatch for DB file:\n"
                f"  got:  {digest}\n"
                f"  want: {DB_ASSET_SHA}\n"
                f"  path: {db_path}"
            )


ensure_sqlite_asset()

app = FastAPI(title="PAP/CSE Dashboard", version="2.0.0")

from .routers.api_improved import router as api_router  # noqa: E402
from .routers.dashboard import router as dashboard_router  # noqa: E402
from .routers.exports import router as exports_router  # noqa: E402

app.include_router(api_router)
app.include_router(exports_router)
app.include_router(dashboard_router)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_schema(engine)
    with SessionLocal() as session:
        stats = compute_global_stats(session)
        pap_rows = stats.get("pap_c5_rows", 0) or 0
        if pap_rows and not (1000 <= pap_rows <= 10000):
            logger.warning(
                "Le volume d'invitations PAP (C5) semble anormal : %s lignes (attendu entre 1 000 et 10 000)",
                pap_rows,
            )
        if session.query(SiretSummary).count() == 0:
            has_pv = session.query(func.count(PVEvent.id)).scalar() or 0
            has_inv = session.query(func.count(Invitation.id)).scalar() or 0
            if has_pv or has_inv:
                logger.info("Reconstruction initiale du tableau de synthèse SIRET.")
                build_siret_summary(session)


def _parse_date_param(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


@app.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    q: str = Query("", description="Recherche texte"),
    fd: Optional[List[str]] = Query(None),
    dep: Optional[List[str]] = Query(None, alias="dep"),
    presence: Optional[List[str]] = Query(None),
    os_query: Optional[List[str]] = Query(None, alias="os"),
    date_pap_from: Optional[str] = Query(None),
    date_pap_to: Optional[str] = Query(None),
    date_pv_from: Optional[str] = Query(None),
    date_pv_to: Optional[str] = Query(None),
    show_all: bool = Query(False, alias="all"),
    sort: str = Query("date_pap_c5"),
    direction: str = Query("desc"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=10, le=200),
    db: Session = Depends(get_session),
):
    fd_filters = [normalize_fd_label(value) or value for value in (fd or []) if value]
    dep_filters = [value for value in (dep or []) if value]
    presence_filters = [value for value in (presence or []) if value]

    raw_os = []
    for value in os_query or []:
        if not value:
            continue
        raw_os.extend([part.strip() for part in value.split(",") if part.strip()])
    os_filters: List[str] = []
    for value in raw_os:
        canonical = normalize_os_label(value)
        os_filters.append(canonical or value.upper())

    pap_from = _parse_date_param(date_pap_from)
    pap_to = _parse_date_param(date_pap_to)
    pv_from = _parse_date_param(date_pv_from)
    pv_to = _parse_date_param(date_pv_to)

    def apply_filters(base_query):
        qset = base_query
        if not show_all:
            qset = qset.filter(SiretSummary.has_match_c5_pv.is_(True))
        if q:
            like = f"%{q}%"
            qset = qset.filter(
                or_(SiretSummary.siret.like(like), SiretSummary.raison_sociale.ilike(like))
            )
        if fd_filters:
            qset = qset.filter(SiretSummary.fd.in_(fd_filters))
        if dep_filters:
            qset = qset.filter(SiretSummary.departement.in_(dep_filters))
        if presence_filters:
            qset = qset.filter(SiretSummary.presence.in_(presence_filters))
        if os_filters:
            for value in os_filters:
                pattern = f"%{value}%"
                qset = qset.filter(
                    or_(SiretSummary.os_c3.ilike(pattern), SiretSummary.os_c4.ilike(pattern))
                )
        if pap_from:
            qset = qset.filter(SiretSummary.date_pap_c5 >= pap_from)
        if pap_to:
            qset = qset.filter(SiretSummary.date_pap_c5 <= pap_to)
        if pv_from:
            qset = qset.filter(SiretSummary.date_pv_last >= pv_from)
        if pv_to:
            qset = qset.filter(SiretSummary.date_pv_last <= pv_to)
        return qset

    query = apply_filters(db.query(SiretSummary))

    sort_columns = {
        "date_pap_c5": SiretSummary.date_pap_c5,
        "date_pv_last": SiretSummary.date_pv_last,
        "raison_sociale": SiretSummary.raison_sociale,
        "departement": SiretSummary.departement,
        "fd": SiretSummary.fd,
    }
    sort_column = sort_columns.get(sort, SiretSummary.date_pap_c5)
    if direction.lower() == "asc":
        ordered_query = query.order_by(sort_column.asc().nullslast())
    else:
        ordered_query = query.order_by(sort_column.desc().nullslast())

    page_params = PageParams(page=page, per_page=per_page)
    page_data = paginate(ordered_query, page_params)

    if page_data.total == 0:
        has_raw = (db.query(func.count(PVEvent.id)).scalar() or 0) or (
            db.query(func.count(Invitation.id)).scalar() or 0
        )
        if has_raw:
            build_siret_summary(db)
            query = apply_filters(db.query(SiretSummary))
            if direction.lower() == "asc":
                ordered_query = query.order_by(sort_column.asc().nullslast())
            else:
                ordered_query = query.order_by(sort_column.desc().nullslast())
            page_data = paginate(ordered_query, page_params)

    query_args: Dict[str, List[str] | str] = {
        "q": q,
        "fd": fd or [],
        "dep": dep or [],
        "presence": presence or [],
        "os": os_query or [],
        "date_pap_from": date_pap_from or "",
        "date_pap_to": date_pap_to or "",
        "date_pv_from": date_pv_from or "",
        "date_pv_to": date_pv_to or "",
        "all": "1" if show_all else "",
        "sort": sort,
        "direction": direction,
        "per_page": str(per_page),
    }
    pagination_html = build_pagination_html(page_data.page, page_data.total_pages, "/", query_args)

    fd_options = [
        value
        for (value,) in db.query(SiretSummary.fd)
        .filter(SiretSummary.fd.isnot(None))
        .distinct()
        .order_by(SiretSummary.fd.asc())
    ]
    dep_options = [
        value
        for (value,) in db.query(SiretSummary.departement)
        .filter(SiretSummary.departement.isnot(None))
        .distinct()
        .order_by(SiretSummary.departement.asc())
    ]

    global_stats = compute_global_stats(db)

    context = {
        "request": request,
        "rows": page_data.items,
        "pagination_html": pagination_html,
        "page_data": page_data,
        "q": q,
        "show_all": show_all,
        "fd_options": fd_options,
        "dep_options": dep_options,
        "presence_options": ["C3+C4", "C3", "C4", "Aucune"],
        "selected_fd": fd_filters,
        "selected_dep": dep_filters,
        "selected_presence": presence_filters,
        "selected_os": ", ".join(raw_os),
        "date_pap_from": pap_from,
        "date_pap_to": pap_to,
        "date_pv_from": pv_from,
        "date_pv_to": pv_to,
        "per_page": per_page,
        "sort": sort,
        "direction": direction,
        "per_page_options": [25, 50, 100, 200],
        "global_stats": global_stats,
    }
    return templates.TemplateResponse("index_paginated.html", context)


@app.get("/ciblage", response_class=HTMLResponse)
def ciblage_get(request: Request, db: Session = Depends(get_session)):
    path = Path("app/static/last_ciblage.csv")
    if not path.exists():
        return templates.TemplateResponse(
            "ciblage.html", {"request": request, "columns": None, "preview_rows": None}
        )
    df = pd.read_csv(path, dtype=str)
    preview_rows = df.head(20).fillna("").to_dict(orient="records")
    columns = list(df.columns)
    col_siren = next((col for col in columns if "siren" in col.lower()), None)

    match_rows: List[Dict[str, str]] = []
    match_count = 0
    if col_siren:
        sirets = [str(v).zfill(9) for v in df[col_siren].fillna("") if str(v).strip()]
        invit_map = {
            inv.siret[:9]: inv
            for inv in db.query(Invitation).filter(
                Invitation.siret.in_([s + "000000" for s in sirets])
            )
        }
        for row in preview_rows:
            key = str(row.get(col_siren) or "").zfill(9)
            if key in invit_map:
                match_rows.append(row)
        match_count = len(match_rows)

    return templates.TemplateResponse(
        "ciblage.html",
        {
            "request": request,
            "columns": columns,
            "preview_rows": preview_rows,
            "col_siren": col_siren,
            "match_rows": match_rows,
            "match_count": match_count,
        },
    )


@app.post("/ciblage/import", response_class=HTMLResponse)
async def ciblage_import(
    request: Request,
    file: UploadFile = File(...),
    user: str = Depends(verify_admin),
):
    dest = Path("app/static/last_ciblage.csv")
    dest.parent.mkdir(parents=True, exist_ok=True)
    content = await file.read()
    dest.write_bytes(content)
    message = (
        f"Fichier {file.filename} importé avec succès." if file.filename else "Fichier de ciblage importé."
    )
    return templates.TemplateResponse("admin.html", {"request": request, "message": message})


@app.get("/siret/{siret}", response_class=HTMLResponse)
def siret_detail(siret: str, request: Request, db: Session = Depends(get_session)):
    summary = db.query(SiretSummary).filter(SiretSummary.siret == siret).first()
    if not summary:
        raise HTTPException(status_code=404, detail="SIRET introuvable")
    pv_rows = (
        db.query(PVEvent)
        .filter(PVEvent.siret == siret)
        .order_by(PVEvent.date_pv.desc().nullslast())
        .all()
    )
    invit_rows = (
        db.query(Invitation)
        .filter(Invitation.siret == siret)
        .order_by(Invitation.date_invit.desc().nullslast())
        .all()
    )
    return templates.TemplateResponse(
        "siret.html",
        {
            "request": request,
            "row": summary,
            "pv_rows": pv_rows,
            "invit_rows": invit_rows,
        },
    )


@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0.0"}


@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request, user: str = Depends(verify_admin)):
    params = request.query_params
    status = params.get("status")
    success = params.get("success") == "1"
    message = None
    if status == "pv":
        if success:
            message = (
                f"PV importés : {params.get('inserted', '0')} insérés, {params.get('updated', '0')} mis à jour"
            )
            warn = params.get("warnings")
            err = params.get("errors")
            if warn and warn != "0":
                message += f" — {warn} avertissement(s)"
            if err and err != "0":
                message += f" — {err} erreur(s)"
        else:
            message = "Échec de l'import des PV — consultez les logs."
    elif status == "invit":
        if success:
            message = (
                f"Invitations importées : {params.get('inserted', '0')} insérées, {params.get('updated', '0')} mises à jour"
            )
            warn = params.get("warnings")
            err = params.get("errors")
            if warn and warn != "0":
                message += f" — {warn} avertissement(s)"
            if err and err != "0":
                message += f" — {err} erreur(s)"
        else:
            message = "Échec de l'import des invitations."
    elif status == "rebuild":
        message = (
            "Résumé reconstruit avec succès." if success else "Erreur lors du rebuild du résumé."
        )
    return templates.TemplateResponse("admin.html", {"request": request, "message": message})
