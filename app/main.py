# app/main.py

import os
import hashlib
import urllib.request
from fastapi import FastAPI, Request, Depends, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

# --- Imports bas niveau (engine/Base) d'abord ---
from .db import get_session, Base, engine
from .models import SiretSummary

# =========================================================
# Bootstrap DB (AVANT d'importer les routers)
# =========================================================

DB_URL = os.getenv("DB_URL", "").strip()                # URL de l'asset Release GitHub
DB_SHA256 = os.getenv("DB_SHA256", "").lower().strip()  # Empreinte optionnelle
DB_GH_TOKEN = os.getenv("DB_GH_TOKEN", "").strip() or None  # Token si repo privé

def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

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

    if DB_URL and not os.path.exists(db_path):
        _download(DB_URL, db_path, token=DB_GH_TOKEN)

    if DB_SHA256 and os.path.exists(db_path):
        digest = _sha256_file(db_path).lower()
        if digest != DB_SHA256:
            raise RuntimeError(
                f"SHA256 mismatch for DB file:\n  got:  {digest}\n  want: {DB_SHA256}\n  path: {db_path}"
            )

# Télécharge/ prépare le fichier AVANT d’importer les routers
ensure_sqlite_asset()

# =========================================================
# App & Routers
# =========================================================

# ⚠️ Import des routers APRÈS ensure_sqlite_asset()
from .routers import api  # noqa: E402

app = FastAPI(title="PAP/CSE Dashboard")
app.include_router(api.router)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

@app.on_event("startup")
def on_startup():
    # Création des tables après que le fichier .db soit prêt
    Base.metadata.create_all(bind=engine)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
def index(request: Request, q: str = "", sort: str = "date_pap_c5", db: Session = Depends(get_session)):
    qs = db.query(SiretSummary)
    if q:
        like = f"%{q}%"
        qs = qs.filter(
            (SiretSummary.siret.like(like)) |
            (SiretSummary.raison_sociale.ilike(like))
        )

    # Apply sorting
    if sort == "inscrits_c3":
        qs = qs.order_by(SiretSummary.inscrits_c3.desc().nullslast())
    elif sort == "inscrits_c4":
        qs = qs.order_by(SiretSummary.inscrits_c4.desc().nullslast())
    else:  # default: date_pap_c5
        qs = qs.order_by(SiretSummary.date_pap_c5.desc().nullslast())

    rows = qs.limit(100).all()
    return templates.TemplateResponse("index.html", {"request": request, "rows": rows, "q": q, "sort": sort})

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

    # Récupère tous les SIRET des invitations
    invit_rows = db.query(Invitation.siret).all()
    siret_list = [r[0] for r in invit_rows if r[0]]

    # Cherche une colonne SIRET dans le fichier
    col_siret = next((c for c in df.columns if c.lower() in ['siret']), None)

    match_rows = []
    if col_siret:
        # Correspondance directe avec les SIRET complets
        match_rows = df[df[col_siret].astype(str).isin(siret_list)].to_dict(orient="records")

    return templates.TemplateResponse(
        "ciblage.html",
        {
            "request": request,
            "columns": columns,
            "preview_rows": preview,
            "col_siren": col_siret,  # Garde le nom pour rétrocompatibilité template
            "match_rows": match_rows,
            "match_count": len(match_rows),
        }
    )

@app.post("/ciblage/import", response_class=HTMLResponse)
def ciblage_import(request: Request, file: UploadFile = File(...), db: Session = Depends(get_session)):
    import pandas as pd
    from .models import Invitation

    df = pd.read_excel(file.file)  # nécessite openpyxl + python-multipart
    os.makedirs("app/static", exist_ok=True)
    df.to_csv("app/static/last_ciblage.csv", index=False)

    columns = list(df.columns)
    preview = df.head(10).to_dict(orient="records")

    # Récupère tous les SIRET des invitations
    invit_rows = db.query(Invitation.siret).all()
    siret_list = [r[0] for r in invit_rows if r[0]]

    # Cherche une colonne SIRET dans le fichier
    col_siret = next((c for c in df.columns if c.lower() in ['siret']), None)

    match_rows = []
    if col_siret:
        # Correspondance directe avec les SIRET complets
        match_rows = df[df[col_siret].astype(str).isin(siret_list)].to_dict(orient="records")

    return templates.TemplateResponse(
        "ciblage.html",
        {
            "request": request,
            "columns": columns,
            "preview_rows": preview,
            "col_siren": col_siret,  # Garde le nom pour rétrocompatibilité template
            "match_rows": match_rows,
            "match_count": len(match_rows),
        }
    )

@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})

@app.get("/recherche-siret", response_class=HTMLResponse)
def recherche_siret_page(request: Request):
    return templates.TemplateResponse("recherche-siret.html", {"request": request})
