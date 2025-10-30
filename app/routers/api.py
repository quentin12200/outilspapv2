from fastapi import APIRouter, UploadFile, File, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from ..db import get_session, Base, engine
from .. import etl
from ..models import SiretSummary, PVEvent, Invitation
from ..schemas import SiretSummaryOut


router = APIRouter(prefix="/api", tags=["api"])

from fastapi.responses import RedirectResponse

@router.post("/ingest/pv")
async def ingest_pv(file: UploadFile = File(...), db: Session = Depends(get_session)):
    n = etl.ingest_pv_excel(db, file.file)
    return RedirectResponse(url="/?retour=1", status_code=303)

@router.post("/ingest/invit")
async def ingest_invit(file: UploadFile = File(...), db: Session = Depends(get_session)):
    n = etl.ingest_invit_excel(db, file.file)
    return RedirectResponse(url="/?retour=1", status_code=303)

@router.post("/build/summary")
def build_summary(db: Session = Depends(get_session)):
    n = etl.build_siret_summary(db)
    return RedirectResponse(url="/?retour=1", status_code=303)

@router.get("/siret", response_model=List[SiretSummaryOut])
def list_sirets(q: str = Query(None), db: Session = Depends(get_session)):
    qs = db.query(SiretSummary)
    if q:
        like = f"%{q}%"
        qs = qs.filter((SiretSummary.siret.like(like)) | (SiretSummary.raison_sociale.ilike(like)))
    return qs.limit(200).all()

@router.get("/siret/{siret}", response_model=SiretSummaryOut)
def get_siret(siret: str, db: Session = Depends(get_session)):
    row = db.query(SiretSummary).get(siret)
    if not row: 
        return {}
    return row

@router.get("/siret/{siret}/timeseries")
def siret_timeseries(siret: str, db: Session = Depends(get_session)):
    rows = (db.query(PVEvent)
              .filter(PVEvent.siret==siret)
              .order_by(PVEvent.date_pv.asc())
              .all())
    # renvoie des séries pour Plotly
    return {
        "dates": [r.date_pv for r in rows if r.date_pv],
        "inscrits": [r.inscrits or 0 for r in rows if r.date_pv],
        "votants": [r.votants or 0 for r in rows if r.date_pv],
        "cgt_voix": [r.cgt_voix or 0 for r in rows if r.date_pv],
    }

@router.get("/stats/dashboard")
def dashboard_stats(db: Session = Depends(get_session)):
    """Retourne les statistiques pour le tableau de bord"""

    # Nombre total de SIRET
    total_siret = db.query(func.count(SiretSummary.siret)).scalar() or 0

    # Nombre d'invitations PAP C5
    total_invitations = db.query(func.count(Invitation.id)).scalar() or 0

    # Nombre de SIRET avec CGT implantée
    cgt_implantee = db.query(func.count(SiretSummary.siret)).filter(
        SiretSummary.cgt_implantee == True
    ).scalar() or 0

    # Nombre total d'inscrits C3 et C4
    total_inscrits_c3 = db.query(func.sum(SiretSummary.inscrits_c3)).scalar() or 0
    total_inscrits_c4 = db.query(func.sum(SiretSummary.inscrits_c4)).scalar() or 0

    # Nombre total de voix CGT C3 et C4
    total_voix_cgt_c3 = db.query(func.sum(SiretSummary.cgt_voix_c3)).scalar() or 0
    total_voix_cgt_c4 = db.query(func.sum(SiretSummary.cgt_voix_c4)).scalar() or 0

    # Répartition par département (top 10)
    dep_stats = db.query(
        SiretSummary.dep,
        func.count(SiretSummary.siret).label('count')
    ).filter(
        SiretSummary.dep.isnot(None)
    ).group_by(
        SiretSummary.dep
    ).order_by(
        func.count(SiretSummary.siret).desc()
    ).limit(10).all()

    # Évolution mensuelle des invitations (6 derniers mois)
    from datetime import datetime, timedelta
    six_months_ago = datetime.now() - timedelta(days=180)

    monthly_invitations = db.query(
        func.strftime('%Y-%m', Invitation.date_invit).label('month'),
        func.count(Invitation.id).label('count')
    ).filter(
        Invitation.date_invit >= six_months_ago
    ).group_by(
        func.strftime('%Y-%m', Invitation.date_invit)
    ).order_by('month').all()

    # Statistiques par statut PAP
    statut_stats = db.query(
        SiretSummary.statut_pap,
        func.count(SiretSummary.siret).label('count')
    ).filter(
        SiretSummary.statut_pap.isnot(None)
    ).group_by(
        SiretSummary.statut_pap
    ).all()

    return {
        "total_siret": total_siret,
        "total_invitations": total_invitations,
        "cgt_implantee": cgt_implantee,
        "cgt_implantee_percent": round((cgt_implantee / total_siret * 100) if total_siret > 0 else 0, 1),
        "total_inscrits_c3": int(total_inscrits_c3),
        "total_inscrits_c4": int(total_inscrits_c4),
        "total_voix_cgt_c3": int(total_voix_cgt_c3),
        "total_voix_cgt_c4": int(total_voix_cgt_c4),
        "percent_voix_c3": round((total_voix_cgt_c3 / total_inscrits_c3 * 100) if total_inscrits_c3 > 0 else 0, 1),
        "percent_voix_c4": round((total_voix_cgt_c4 / total_inscrits_c4 * 100) if total_inscrits_c4 > 0 else 0, 1),
        "departments": [{"dep": d[0], "count": d[1]} for d in dep_stats],
        "monthly_invitations": [{"month": m[0], "count": m[1]} for m in monthly_invitations],
        "statut_stats": [{"statut": s[0], "count": s[1]} for s in statut_stats]
    }
