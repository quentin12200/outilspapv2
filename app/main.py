import hashlib
import json
import os
import re
import urllib.request
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from . import etl
from .config import IS_SQLITE
from .db import Base, engine, get_session
from .models import Invitation, PVEvent, SiretSummary
from .normalization import normalize_fd_label

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


@app.get("/", response_class=HTMLResponse)
def index(request: Request, q: str = "", db: Session = Depends(get_session)):
    sort_key = request.query_params.get("sort") or "date_pap_c5"
    qs = db.query(SiretSummary)
    if q:
        like = f"%{q}%"
        qs = qs.filter((SiretSummary.siret.like(like)) | (SiretSummary.raison_sociale.ilike(like)))
    ordering_map = {
        "date_pap_c5": SiretSummary.date_pap_c5.desc().nullslast(),
        "inscrits_c3": SiretSummary.inscrits_c3.desc().nullslast(),
        "inscrits_c4": SiretSummary.inscrits_c4.desc().nullslast(),
    }
    order_clause = ordering_map.get(sort_key, ordering_map["date_pap_c5"])
    rows = qs.order_by(order_clause).all()
    if not rows:
        pv_total = db.query(func.count(PVEvent.id)).scalar() or 0
        invit_total = db.query(func.count(Invitation.id)).scalar() or 0
        if pv_total or invit_total:
            etl.build_siret_summary(db)
            rows = qs.order_by(order_clause).all()
    sirets = [r.siret for r in rows]
    summary_rows = []
    summary_totals = {
        "structures": 0,
        "pap_total": 0,
        "pv_c3_total": 0,
        "pv_c4_total": 0,
        "match_c3": 0,
        "match_c4": 0,
    }
    if sirets:
        pap_counts = {
            siret: count
            for siret, count in (
                db.query(Invitation.siret, func.count(Invitation.id))
                .filter(Invitation.siret.in_(sirets))
                .group_by(Invitation.siret)
                .all()
            )
        }
        pv_counts_raw = (
            db.query(PVEvent.siret, PVEvent.cycle, func.count(PVEvent.id))
            .filter(PVEvent.siret.in_(sirets), PVEvent.cycle.in_(["C3", "C4"]))
            .group_by(PVEvent.siret, PVEvent.cycle)
            .all()
        )
        pv_counts = {s: {"C3": 0, "C4": 0} for s in sirets}
        for siret, cycle, count in pv_counts_raw:
            if siret not in pv_counts:
                pv_counts[siret] = {"C3": 0, "C4": 0}
            pv_counts[siret][cycle] = count

        orga_map = {s: set() for s in sirets}
        pv_org_rows = (
            db.query(PVEvent.siret, PVEvent.autres_indics, PVEvent.fd, PVEvent.ud)
            .filter(PVEvent.siret.in_(sirets))
            .all()
        )

        def register_org(siret: str, label: str):
            label = normalize_fd_label(label) or (label or "").strip()
            if not label:
                return
            orga_map.setdefault(siret, set()).add(label)

        def iter_autres(value):
            if value is None:
                return
            if isinstance(value, dict):
                for key, item in value.items():
                    if isinstance(item, (int, float)):
                        if float(item or 0):
                            yield str(key)
                    elif isinstance(item, str):
                        stripped = item.strip()
                        if stripped:
                            yield stripped
                    else:
                        for nested in iter_autres(item):
                            yield nested
            elif isinstance(value, list):
                for elem in value:
                    for nested in iter_autres(elem):
                        yield nested
            elif isinstance(value, str):
                stripped = value.strip()
                if not stripped:
                    return
                try:
                    parsed = json.loads(stripped)
                except json.JSONDecodeError:
                    for part in re.split(r"[,;/]", stripped):
                        part = part.strip()
                        if part:
                            yield part
                else:
                    for nested in iter_autres(parsed):
                        yield nested

        for siret, autres, fd, ud in pv_org_rows:
            register_org(siret, fd)
            register_org(siret, ud)
            if autres is not None:
                for label in iter_autres(autres):
                    register_org(siret, label)

        for row in rows:
            orgas = set(orga_map.get(row.siret, set()))
            if row.fd_c3:
                orgas.add(normalize_fd_label(row.fd_c3) or str(row.fd_c3).strip())
            if row.fd_c4:
                orgas.add(normalize_fd_label(row.fd_c4) or str(row.fd_c4).strip())
            if getattr(row, "ud_c3", None):
                orgas.add(str(row.ud_c3).strip())
            if getattr(row, "ud_c4", None):
                orgas.add(str(row.ud_c4).strip())
            pap_count = pap_counts.get(row.siret, 0)
            pv_c3_count = pv_counts.get(row.siret, {}).get("C3", 0)
            pv_c4_count = pv_counts.get(row.siret, {}).get("C4", 0)
            match_c3 = bool(pap_count and pv_c3_count)
            match_c4 = bool(pap_count and pv_c4_count)
            summary_rows.append(
                {
                    "siret": row.siret,
                    "raison_sociale": row.raison_sociale,
                    "departement": row.dep,
                    "pap_count": pap_count,
                    "pv_c3_count": pv_c3_count,
                    "pv_c4_count": pv_c4_count,
                    "match_c3": match_c3,
                    "match_c4": match_c4,
                    "organisations": sorted(o for o in orgas if o),
                }
            )
            summary_totals["structures"] += 1
            summary_totals["pap_total"] += pap_count
            summary_totals["pv_c3_total"] += pv_c3_count
            summary_totals["pv_c4_total"] += pv_c4_count
            if match_c3:
                summary_totals["match_c3"] += 1
            if match_c4:
                summary_totals["match_c4"] += 1

    highlight_candidates = [row for row in rows if row.date_pap_c5]
    highlight_candidates.sort(key=lambda row: row.date_pap_c5, reverse=True)
    highlight_rows = [
        row
        for row in highlight_candidates
        if (row.inscrits_c3 or 0) > 100 or (row.inscrits_c4 or 0) > 100
    ]

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "rows": rows,
            "q": q,
            "summary_rows": summary_rows,
            "summary_totals": summary_totals if summary_rows else None,
            "sort": sort_key,
            "highlight_rows": highlight_rows,
        },
    )


@app.get("/ciblage", response_class=HTMLResponse)
def ciblage_get(request: Request, db: Session = Depends(get_session)):
    import pandas as pd

    from .models import Invitation

    path = "app/static/last_ciblage.csv"
    if not os.path.exists(path):
        return templates.TemplateResponse("ciblage.html", {"request": request, "columns": None, "preview_rows": None})
    df = pd.read_csv(path, dtype=str)
    columns = list(df.columns)
    preview = df.head(10).to_dict(orient="records")
    invit_rows = db.query(Invitation.siret).all()
    siret_list = [r[0] for r in invit_rows]
    siren_list = {s[:9] for s in siret_list if s and len(s) >= 9}
    col_siren = next((c for c in df.columns if c.lower().startswith("siren")), None)
    match_rows = []
    if col_siren:
        match_rows = df[df[col_siren].astype(str).isin(siren_list)].to_dict(orient="records")
    return templates.TemplateResponse(
        "ciblage.html",
        {
            "request": request,
            "columns": columns,
            "preview_rows": preview,
            "col_siren": col_siren,
            "match_rows": match_rows,
            "match_count": len(match_rows),
        },
    )


@app.get("/siret/{siret}", response_class=HTMLResponse)
def siret_detail(siret: str, request: Request, db: Session = Depends(get_session)):
    pv_rows = (
        db.query(PVEvent)
        .filter(PVEvent.siret == siret)
        .order_by(PVEvent.date_pv.desc().nullslast())
        .all()
    )
    invit_rows = (
        db.query(Invitation)
        .filter(Invitation.siret == siret)
        .order_by(Invitation.date_pap.desc().nullslast())
        .all()
    )
    summary = db.query(SiretSummary).filter(SiretSummary.siret == siret).first()
    return templates.TemplateResponse(
        "siret_detail.html",
        {
            "request": request,
            "siret": siret,
            "pv_rows": pv_rows,
            "invit_rows": invit_rows,
            "summary": summary,
        },
    )


@app.get("/health")
def health():
    return {"status": "ok"}
