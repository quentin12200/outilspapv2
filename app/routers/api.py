from fastapi import APIRouter, UploadFile, File, Depends, Query
from sqlalchemy.orm import Session
from typing import List
from ..db import get_session, Base, engine
from .. import etl
from ..models import SiretSummary, PVEvent
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
