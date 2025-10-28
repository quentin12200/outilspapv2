import json
import re

from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from .db import get_session, Base, engine
from .models import SiretSummary, PVEvent, Invitation
from .routers import api

app = FastAPI(title="PAP/CSE Dashboard")
app.include_router(api.router)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# Assure la création des tables au boot (simple pour démarrer)
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
        # Prélever les organisations syndicales connues à partir des PV enregistrés
        pv_org_rows = (
            db.query(PVEvent.siret, PVEvent.autres_indics, PVEvent.fd, PVEvent.ud)
            .filter(PVEvent.siret.in_(sirets))
            .all()
        )
        def register_org(siret: str, label: str):
            label = (label or "").strip()
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
                orgas.add(str(row.fd_c3).strip())
            if row.fd_c4:
                orgas.add(str(row.fd_c4).strip())
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

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "rows": rows,
            "q": q,
            "summary_rows": summary_rows,
            "summary_totals": summary_totals if summary_rows else None,
            "sort": sort_key,
        },
    )

@app.get("/ciblage", response_class=HTMLResponse)
def ciblage_get(request: Request, db: Session = Depends(get_session)):
    import os
    import pandas as pd
    from .models import Invitation
    path = "app/static/last_ciblage.csv"
    if not os.path.exists(path):
        return templates.TemplateResponse("ciblage.html", {"request": request, "columns": None, "preview_rows": None})
    df = pd.read_csv(path, dtype=str)
    columns = list(df.columns)
    preview = df.head(10).to_dict(orient="records")
    # Lire les invitations PAP (SIRET)
    invit_rows = db.query(Invitation.siret).all()
    siret_list = [r[0] for r in invit_rows]
    siren_list = {s[:9] for s in siret_list if s and len(s) >= 9}
    col_siren = None
    for c in df.columns:
        if c.lower().startswith("siren"):
            col_siren = c
            break
    match_rows = []
    if col_siren:
        match_rows = df[df[col_siren].astype(str).isin(siren_list)].to_dict(orient="records")
    return templates.TemplateResponse("ciblage.html", {
        "request": request,
        "columns": columns,
        "preview_rows": preview,
        "col_siren": col_siren,
        "match_rows": match_rows,
        "match_count": len(match_rows)
    })

from fastapi import UploadFile, File

@app.post("/ciblage/import", response_class=HTMLResponse)
def ciblage_import(request: Request, file: UploadFile = File(...), db: Session = Depends(get_session)):
    import pandas as pd
    from .models import Invitation
    # Lire le fichier ciblage
    df = pd.read_excel(file.file)
    # Persistance : sauvegarder le fichier importé en CSV
    df.to_csv("app/static/last_ciblage.csv", index=False)
    columns = list(df.columns)
    preview = df.head(10).to_dict(orient="records")
    # Lire les invitations PAP (SIRET)
    invit_rows = db.query(Invitation.siret).all()
    siret_list = [r[0] for r in invit_rows]
    siren_list = {s[:9] for s in siret_list if s and len(s) >= 9}
    # Croisement sur la colonne SIREN du ciblage
    col_siren = None
    for c in df.columns:
        if c.lower().startswith("siren"):
            col_siren = c
            break
    match_rows = []
    if col_siren:
        match_rows = df[df[col_siren].astype(str).isin(siren_list)].head(20).to_dict(orient="records")
    return templates.TemplateResponse("ciblage.html", {
        "request": request,
        "columns": columns,
        "preview_rows": preview,
        "col_siren": col_siren,
        "match_rows": match_rows,
        "match_count": len(match_rows)
    })

@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})

@app.get("/siret/{siret}", response_class=HTMLResponse)
def siret_page(siret: str, request: Request, db: Session = Depends(get_session)):
    row = db.query(SiretSummary).get(siret)
    return templates.TemplateResponse("siret.html", {"request": request, "row": row})
