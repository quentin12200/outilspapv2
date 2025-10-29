import hashlib
import logging
import os
import re
import urllib.request
from datetime import datetime, date
from math import ceil
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from . import etl
from .config import IS_SQLITE
from .db import Base, SessionLocal, engine, get_session
from .models import Invitation, PVEvent, SiretSummary
from .normalization import normalize_fd_label, normalize_os_label

logger = logging.getLogger(__name__)

DB_ASSET_URL = (
    os.getenv("DB_URL")
    or os.getenv("DATABASE_RELEASE_URL")
    or ""
).strip()
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
        _download(DB_ASSET_URL, db_path, token=DB_ASSET_TOKEN)
    if DB_ASSET_SHA and db_path.exists():
        digest = _sha256_file(db_path).lower()
        if digest != DB_ASSET_SHA:
            raise RuntimeError(
                "SHA256 mismatch for DB file:\n"
                f"  got:  {digest}\n"
                f"  want: {DB_ASSET_SHA}\n"
                f"  path: {db_path}"
            )


ensure_sqlite_asset()

from .routers import api  # noqa: E402

app = FastAPI(title="PAP/CSE Dashboard")
app.include_router(api.router)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

Base.metadata.create_all(bind=engine)
etl.ensure_schema(engine)

try:
    with SessionLocal() as startup_session:
        stats = etl.compute_global_stats(startup_session)
        pap_rows = stats.get("pap_c5_rows", 0) or 0
        if pap_rows and (pap_rows < 1000 or pap_rows > 10000):
            logger.warning(
                "Le volume d'invitations PAP (C5) semble anormal : %s lignes (attendu entre 1 000 et 10 000)",
                pap_rows,
            )
except Exception as exc:  # pragma: no cover
    logger.warning("Impossible de calculer les statistiques globales au démarrage : %s", exc)


def _parse_date_param(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


@app.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_session)):
    params = request.query_params
    q = (params.get("q") or "").strip()
    show_all = (params.get("all") or "").lower() in {"1", "true", "yes", "on"}

    fd_filters = []
    for value in params.getlist("fd"):
        if value:
            fd_filters.append(normalize_fd_label(value) or value)

    dep_filters = [value for value in params.getlist("dep") if value]

    presence_filters = [value for value in params.getlist("presence") if value]

    raw_os_filters = []
    for value in params.getlist("os"):
        if not value:
            continue
        raw_os_filters.extend([part.strip() for part in value.split(",") if part.strip()])
    os_filters = []
    for value in raw_os_filters:
        canonical = normalize_os_label(value)
        if canonical:
            os_filters.append(canonical)
        else:
            os_filters.append(value.upper())

    date_pap_from = _parse_date_param(params.get("date_pap_from"))
    date_pap_to = _parse_date_param(params.get("date_pap_to"))
    date_pv_from = _parse_date_param(params.get("date_pv_from"))
    date_pv_to = _parse_date_param(params.get("date_pv_to"))

    base_query = db.query(SiretSummary)
    if not show_all:
        base_query = base_query.filter(SiretSummary.has_match_c5_pv.is_(True))

    if q:
        like = f"%{q}%"
        base_query = base_query.filter(
            or_(SiretSummary.siret.like(like), SiretSummary.raison_sociale.ilike(like))
        )

    if fd_filters:
        base_query = base_query.filter(SiretSummary.fd.in_(fd_filters))

    if dep_filters:
        base_query = base_query.filter(SiretSummary.departement.in_(dep_filters))

    if presence_filters:
        base_query = base_query.filter(SiretSummary.presence.in_(presence_filters))

    if os_filters:
        for os_value in os_filters:
            pattern = f"%{os_value}%"
            base_query = base_query.filter(
                or_(SiretSummary.os_c3.ilike(pattern), SiretSummary.os_c4.ilike(pattern))
            )

    if date_pap_from:
        base_query = base_query.filter(SiretSummary.date_pap_c5 >= date_pap_from)
    if date_pap_to:
        base_query = base_query.filter(SiretSummary.date_pap_c5 <= date_pap_to)
    if date_pv_from:
        base_query = base_query.filter(SiretSummary.date_pv_last >= date_pv_from)
    if date_pv_to:
        base_query = base_query.filter(SiretSummary.date_pv_last <= date_pv_to)

    order_clause = (
        SiretSummary.date_pap_c5.desc().nullslast(),
        SiretSummary.date_pv_last.desc().nullslast(),
        SiretSummary.siret.asc(),
    )

    total_rows = base_query.count()

    if total_rows == 0:
        has_data = (db.query(func.count(PVEvent.id)).scalar() or 0) or (
            db.query(func.count(Invitation.id)).scalar() or 0
        )
        if has_data:
            etl.build_siret_summary(db)
            base_query = db.query(SiretSummary)
            if not show_all:
                base_query = base_query.filter(SiretSummary.has_match_c5_pv.is_(True))
            if q:
                like = f"%{q}%"
                base_query = base_query.filter(
                    or_(SiretSummary.siret.like(like), SiretSummary.raison_sociale.ilike(like))
                )
            if fd_filters:
                base_query = base_query.filter(SiretSummary.fd.in_(fd_filters))
            if dep_filters:
                base_query = base_query.filter(SiretSummary.departement.in_(dep_filters))
            if presence_filters:
                base_query = base_query.filter(SiretSummary.presence.in_(presence_filters))
            if os_filters:
                for os_value in os_filters:
                    pattern = f"%{os_value}%"
                    base_query = base_query.filter(
                        or_(SiretSummary.os_c3.ilike(pattern), SiretSummary.os_c4.ilike(pattern))
                    )
            if date_pap_from:
                base_query = base_query.filter(SiretSummary.date_pap_c5 >= date_pap_from)
            if date_pap_to:
                base_query = base_query.filter(SiretSummary.date_pap_c5 <= date_pap_to)
            if date_pv_from:
                base_query = base_query.filter(SiretSummary.date_pv_last >= date_pv_from)
            if date_pv_to:
                base_query = base_query.filter(SiretSummary.date_pv_last <= date_pv_to)
            total_rows = base_query.count()

    page_sizes = [25, 50, 100, 200]
    default_page_size = 50
    try:
        requested_page_size = int(params.get("per_page") or params.get("page_size") or default_page_size)
    except ValueError:
        requested_page_size = default_page_size
    if requested_page_size not in page_sizes:
        for size in page_sizes:
            if requested_page_size <= size:
                requested_page_size = size
                break
        else:
            requested_page_size = page_sizes[-1]
    page_size = requested_page_size

    try:
        requested_page = int(params.get("page") or 1)
    except ValueError:
        requested_page = 1
    requested_page = max(1, requested_page)

    total_pages = max(1, ceil(total_rows / page_size)) if total_rows else 1
    page = min(requested_page, total_pages)
    offset = (page - 1) * page_size if total_rows else 0

    rows = (
        base_query.order_by(*order_clause).offset(offset).limit(page_size).all()
        if total_rows
        else []
    )

    pagination = {
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "total_rows": total_rows,
        "start": offset + 1 if rows else 0,
        "end": offset + len(rows) if rows else 0,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "sizes": page_sizes,
    }

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

    context = {
        "request": request,
        "rows": rows,
        "q": q,
        "show_all": show_all,
        "fd_options": fd_options,
        "dep_options": dep_options,
        "presence_options": ["C3+C4", "C3", "C4", "Aucune"],
        "selected_fd": fd_filters,
        "selected_dep": dep_filters,
        "selected_presence": presence_filters,
        "selected_os": ", ".join(raw_os_filters),
        "date_pap_from": date_pap_from,
        "date_pap_to": date_pap_to,
        "date_pv_from": date_pv_from,
        "date_pv_to": date_pv_to,
        "pagination": pagination,
    }
    return templates.TemplateResponse("index.html", context)


@app.get("/ciblage", response_class=HTMLResponse)
def ciblage_get(request: Request, db: Session = Depends(get_session)):
    import pandas as pd

    path = "app/static/last_ciblage.csv"
    if not os.path.exists(path):
        return templates.TemplateResponse("ciblage.html", {"request": request, "columns": None, "preview_rows": None})
    df = pd.read_csv(path, dtype=str)
    preview_rows = df.head(20).fillna("").to_dict(orient="records")
    columns = list(df.columns)
    col_siren = None
    for col in columns:
        if "siren" in col.lower():
            col_siren = col
            break
    match_rows = []
    match_count = 0
    if col_siren:
        sirets = [str(v).zfill(9) for v in df[col_siren].fillna("") if str(v).strip()]
        invit_map = {
            inv.siret[:9]: inv
            for inv in db.query(Invitation).filter(Invitation.siret.in_([s + "000000" for s in sirets])).all()
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


@app.get("/siret/{siret}", response_class=HTMLResponse)
def siret_detail(siret: str, request: Request, db: Session = Depends(get_session)):
    summary = db.query(SiretSummary).filter(SiretSummary.siret == siret).first()
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
    return {"status": "ok"}


@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})


@app.post("/ciblage/import", response_class=HTMLResponse)
async def ciblage_import(request: Request, file: UploadFile = File(...)):
    dest = Path("app/static/last_ciblage.csv")
    dest.parent.mkdir(parents=True, exist_ok=True)
    content = await file.read()
    dest.write_bytes(content)
    message = f"Fichier {file.filename} importé avec succès." if file.filename else "Fichier de ciblage importé."
    return templates.TemplateResponse("admin.html", {"request": request, "message": message})
