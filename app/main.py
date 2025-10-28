# app/main.py (ou main.py selon ton arborescence)

import os
import hashlib
import urllib.request
from fastapi import FastAPI, Request, Depends, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

# --- Imports projet existants ---
from .db import get_session, Base, engine
from .models import SiretSummary
from .routers import api

# =========================================================
#          Bootstrap DB : download + SHA256 check
# =========================================================

DB_URL = os.getenv("DB_URL", "").strip()          # ex: https://github.com/.../releases/download/v1.0.0/papcse.db
DB_SHA256 = os.getenv("DB_SHA256", "").lower().strip()  # ex: 36f5a9...

def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def _sqlite_path_from_engine() -> str | None:
    try:
        # sqlite:///absolute/path.db  -> .database = "/absolute/path.db"
        # sqlite:///app/data/db.db    -> .database = "/app/data/db.db"
        # sqlite:///:memory:          -> .database = ":memory:"
        if engine.url.get_backend_name() == "sqlite":
            db_path = engine.url.database
            if db_path and db_path != ":memory:":
                return db_path
    except Exception:
        pass
    return None

def ensure_sqlite_asset():
    """
    Si DB_URL est fourni et que le backend est SQLite, télécharge le fichier
    dans le chemin pointé par engine (si manquant) et vérifie le SHA256 si fourni.
    """
    if not DB_URL:
        return  # rien à faire

    db_path = _sqlite_path_from_engine()
    if not db_path:
        return  # pas une base SQLite fichier, on ne fait rien

    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    if not os.path.exists(db_path):
        # Téléchargement de l’asset release
        urllib.request.urlretrieve(DB_URL, db_path)

    # Vérification d’intégrité optionnelle
    if DB_SHA256:
        digest = _sha256_file(db_path).lower()
        if digest != DB_SHA256:
            raise RuntimeError(
                f"SHA256 mismatch for DB file:\n  got:  {digest}\n  want: {DB_SHA256}\n  path: {db_path}"
            )

# Exécute le bootstrap au cold start
ensure_sqlite_asset()

# =========================================================
#          Application FastAPI
# =========================================================

app = FastAPI(title="PAP/CSE Dashboard")

# API routers
app.include_router(api.router)

# Static & templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# Création des tables (si tu utilises un schéma SQLAlchemy par-dessus ton .db)
# -> garde-le si tu veux créer automatiquement les tables manquantes.
Base.metadata.create_all(bind=engine)

# --- Healthcheck simple pour Railway/Probe ---
@app.get("/health")
def health():
    return {"status": "ok"}

# --- Pages / vues ---
@app.get("/", response_class=HTMLResponse)
def index(request: Request, q: str = "", db: Session = Depends(get_session)):
    qs = db.query(SiretSummary)
    if q:
        like = f"%{q}%"
        qs = qs.filter(
            (SiretSummary.siret.like(like)) |
            (SiretSummary.raison_sociale.ilike(like))
        )
    rows = qs.order_by(SiretSummary.date_pap_c5.desc().nullslast()).limit(100).all()
    return templates.TemplateResponse("index.html", {"request": request, "rows": rows, "q": q})

@app.get("/ciblage", response_class=HTMLResponse)
def ciblage_get(request: Request, db: Session = Depends(get_session)):
    import pandas as pd
    from .models import Invitation
    path = "app/static/last_ciblage.csv"
    if not os.path.exists(path):
        return templates.TemplateResponse(
            "ciblage.html",
            {"request": request, "columns": None, "preview_rows": None}
        )
    df = pd.read_csv(path, dtype=str)
    columns = list(df.columns)
    preview = df.head(10).to_dict(orient="records")

    # Lire les invitations PAP (SIRET)
    invit_rows = db.query(Invitation.siret).all()
    siret_list = [r[0] for r in invit_rows]
    siren_list = {s[:9] for s in siret_list if s and len(s) >= 9}

    # Colonne SIREN probable
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
        }
    )

@app.post("/ciblage/import", response_class=HTMLResponse)
def ciblage_import(request: Request, file: UploadFile = File(...), db: Session = Depends(get_session)):
    import pandas as pd
    from .models import Invitation

    # Lire le fichier ciblage
    df = pd.read_excel(file.file)

    # Persistance : sauvegarder le fichier importé en CSV
    os.makedirs("app/static", exist_ok=True)
    df.to_csv("app/static/last_ciblage.csv", index=False)

    columns = list(df.columns)
    preview = df.head(10).to_dict(orient="records")

    # Lire les invitations PAP (SIRET)
    invit_rows = db.query(Invitation.siret).all()
    siret_list = [r[0] for r in invit_rows]
    siren_list = {s[:9] for s in siret_list if s and len(s) >= 9}

    # Croisement sur la colonne SIREN du ciblage
    col_siren = next((c for c in df.columns if c.lower().startswith("siren")), None)

    match_rows = []
    if col_siren:
        match_rows = df[df[col_siren].astype(str).isin(siren_list)].head(20).to_dict(orient="records")

    return templates.TemplateResponse(
        "ciblage.html",
        {
            "request": request,
            "columns": columns,
            "preview_rows": preview,
            "col_siren": col_siren,
            "match_rows": match_rows,
            "match_count": len(match_rows),
        }
    )

@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})

@app.get("/siret/{siret}", response_class=HTMLResponse)
def siret_page(siret: str, request: Request, db: Session = Depends(get_session)):
    row = db.query(SiretSummary).get(siret)
    return templates.TemplateResponse("siret.html", {"request": request, "row": row})
