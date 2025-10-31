# app/main.py

import os
import hashlib
import urllib.request
from fastapi import FastAPI, Request, Depends, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

# --- Imports bas niveau (engine/Base) d'abord ---
from .db import get_session, Base, engine
from .models import Invitation, SiretSummary

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

    def pick_from_raw(raw, keys):
        for key in keys:
            value = raw.get(key)
            if value:
                return value
        return None

    for inv in invitations:
        raw = inv.raw or {}

        inv.display_denomination = next(
            (
                value
                for value in [
                    inv.denomination,
                    pick_from_raw(
                        raw,
                        [
                            "denomination",
                            "denomination_usuelle",
                            "raison_sociale",
                            "raison sociale",
                            "Raison sociale",
                            "raison_sociale_etablissement",
                            "RAISON_SOCIALE",
                            "RAISON_SOCIALE_ETABLISSEMENT",
                            "raison_sociale_uai",
                            "nom_raison_sociale",
                            "NomRS",
                            "Nom",
                            "nom",
                            "rs",
                            "RS",
                        ],
                    ),
                ]
                if value
            ),
            None,
        )

        inv.display_commune = next(
            (
                value
                for value in [
                    inv.commune,
                    pick_from_raw(
                        raw,
                        [
                            "commune",
                            "Commune",
                            "ville",
                            "Ville",
                            "LibelleCommuneEtablissement",
                            "LIBELLE_COMMUNE_ETABLISSEMENT",
                            "libelle_commune_etablissement",
                            "libelle_commune",
                            "Localite",
                            "localite",
                            "adresse_ville",
                        ],
                    ),
                ]
                if value
            ),
            None,
        )

        inv.display_adresse = next(
            (
                value
                for value in [
                    inv.adresse,
                    pick_from_raw(
                        raw,
                        [
                            "adresse",
                            "Adresse",
                            "adresse_ligne_1",
                            "adresse_ligne_2",
                            "adresse_complete",
                            "adresse_pap",
                            "adresse_postale",
                            "libelle_voie",
                            "LibelleVoieEtablissement",
                            "LIBELLE_VOIE_ETABLISSEMENT",
                            "ligne_4",
                            "Ligne4",
                            "L4",
                        ],
                    ),
                ]
                if value
            ),
            None,
        )

        inv.display_code_postal = next(
            (
                value
                for value in [
                    inv.code_postal,
                    pick_from_raw(
                        raw,
                        [
                            "code_postal",
                            "Code_postal",
                            "Code Postal",
                            "codePostal",
                            "CodePostal",
                            "cp",
                            "CP",
                            "code_postal_etablissement",
                            "CODE_POSTAL_ETABLISSEMENT",
                            "CodePostalEtablissement",
                            "code_postal_uai",
                        ],
                    ),
                ]
                if value
            ),
            None,
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

@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})

@app.get("/recherche-siret", response_class=HTMLResponse)
def recherche_siret_page(request: Request):
    return templates.TemplateResponse("recherche-siret.html", {"request": request})

@app.get("/siret/{siret}", response_class=HTMLResponse)
def siret_detail(siret: str, request: Request, db: Session = Depends(get_session)):
    from .models import PVEvent, Invitation

    # Récupère le résumé SIRET
    row = db.query(SiretSummary).filter(SiretSummary.siret == siret).first()

    if not row:
        return templates.TemplateResponse("siret.html", {"request": request, "row": None})

    # Récupère l'historique complet des PV
    pv_history = db.query(PVEvent).filter(PVEvent.siret == siret).order_by(PVEvent.date_pv.desc()).all()

    # Récupère les invitations
    invitations = db.query(Invitation).filter(Invitation.siret == siret).order_by(Invitation.date_invit.desc()).all()

    # Récupère les informations enrichies Sirene (si disponible)
    sirene_data = None
    if invitations:
        # Prend la première invitation enrichie
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

    return templates.TemplateResponse("siret.html", {
        "request": request,
        "row": row,
        "pv_history": pv_history,
        "invitations": invitations,
        "sirene_data": sirene_data,
    })
