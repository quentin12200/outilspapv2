from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from .db import get_session, Base, engine
from .models import SiretSummary
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
    return templates.TemplateResponse("index.html", {"request": request, "rows": rows, "q": q})

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
