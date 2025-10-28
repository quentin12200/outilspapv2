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
    qs = db.query(SiretSummary)
    if q:
        like = f"%{q}%"
        qs = qs.filter((SiretSummary.siret.like(like)) | (SiretSummary.raison_sociale.ilike(like)))
    rows = qs.order_by(SiretSummary.date_pap_c5.desc().nullslast()).limit(100).all()
    sirets = [r.siret for r in rows]
    summary_rows = []
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
            db.query(PVEvent.siret, PVEvent.autres_indics, PVEvent.fd)
            .filter(PVEvent.siret.in_(sirets))
            .all()
        )
        for siret, autres, fd in pv_org_rows:
            if fd:
                orga_map.setdefault(siret, set()).add(str(fd).strip())
            if isinstance(autres, dict):
                for orga, score in autres.items():
                    try:
                        has_presence = float(score) if score is not None else 0
                    except (TypeError, ValueError):
                        has_presence = 0
                    if has_presence:
                        orga_map.setdefault(siret, set()).add(str(orga).strip())

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
            summary_rows.append(
                {
                    "siret": row.siret,
                    "raison_sociale": row.raison_sociale,
                    "departement": row.dep,
                    "pap_count": pap_counts.get(row.siret, 0),
                    "pv_c3_count": pv_counts.get(row.siret, {}).get("C3", 0),
                    "pv_c4_count": pv_counts.get(row.siret, {}).get("C4", 0),
                    "organisations": sorted(o for o in orgas if o),
                }
            )

    return templates.TemplateResponse(
        "index.html",
        {"request": request, "rows": rows, "q": q, "summary_rows": summary_rows},
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
