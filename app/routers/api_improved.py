"""Routes API sécurisées et améliorées pour les opérations d'import et de consultation."""
from __future__ import annotations

import urllib.parse
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from ..core.logging_config import audit_logger, get_logger
from ..core.security import verify_admin
from ..db import get_session
from ..etl_improved import (
    ETLResult,
    build_siret_summary,
    compute_global_stats,
    ingest_invit_excel,
    ingest_pv_excel,
)
from ..models import PVEvent, SiretSummary
from ..schemas import SiretSummaryOut

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["api"])


def _build_redirect(kind: str, result: ETLResult) -> RedirectResponse:
    params = {
        "status": kind,
        "success": "1" if result.success else "0",
        "inserted": str(result.inserted),
        "updated": str(result.updated),
        "skipped": str(result.skipped),
        "errors": str(len(result.errors)),
        "warnings": str(len(result.warnings)),
    }
    url = "/admin?" + urllib.parse.urlencode(params)
    return RedirectResponse(url=url, status_code=303)


def _should_return_json(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return "application/json" in accept.lower()


@router.post("/ingest/pv")
async def ingest_pv(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_session),
    user: str = Depends(verify_admin),
):
    result = ingest_pv_excel(db, file.file)
    audit_logger.log_import(user, "pv", result.inserted + result.updated, result.success)
    if result.success:
        rebuilt = build_siret_summary(db)
        audit_logger.log_build_summary(user, rebuilt, True)
    else:
        audit_logger.log_build_summary(user, 0, False)

    payload = result.to_dict()
    payload["kind"] = "pv"

    if _should_return_json(request):
        status = 200 if result.success else 400
        return JSONResponse(payload, status_code=status)
    return _build_redirect("pv", result)


@router.post("/ingest/invit")
async def ingest_invit(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_session),
    user: str = Depends(verify_admin),
):
    result = ingest_invit_excel(db, file.file)
    audit_logger.log_import(user, "invit", result.inserted + result.updated, result.success)
    if result.success:
        rebuilt = build_siret_summary(db)
        audit_logger.log_build_summary(user, rebuilt, True)
    else:
        audit_logger.log_build_summary(user, 0, False)

    payload = result.to_dict()
    payload["kind"] = "invit"

    if _should_return_json(request):
        status = 200 if result.success else 400
        return JSONResponse(payload, status_code=status)
    return _build_redirect("invit", result)


@router.post("/admin/rebuild-summary")
async def rebuild_summary(
    request: Request,
    db: Session = Depends(get_session),
    user: str = Depends(verify_admin),
):
    try:
        rows = build_siret_summary(db)
        audit_logger.log_build_summary(user, rows, True)
        payload = {"success": True, "rows": rows}
    except Exception as exc:  # pragma: no cover - sécurité
        audit_logger.log_build_summary(user, 0, False)
        logger.exception("Erreur lors du rebuild du résumé")
        payload = {"success": False, "error": str(exc)}

    if _should_return_json(request):
        status = 200 if payload.get("success") else 500
        return JSONResponse(payload, status_code=status)
    params = {"status": "rebuild", "success": "1" if payload.get("success") else "0", "rows": payload.get("rows", 0)}
    url = "/admin?" + urllib.parse.urlencode(params)
    return RedirectResponse(url=url, status_code=303)


@router.get("/siret", response_model=List[SiretSummaryOut])
def list_sirets(
    q: Optional[str] = Query(None, description="Recherche texte (SIRET ou raison sociale)"),
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_session),
):
    qs = db.query(SiretSummary)
    if q:
        like = f"%{q}%"
        qs = qs.filter(
            (SiretSummary.siret.like(like)) | (SiretSummary.raison_sociale.ilike(like))
        )
    return qs.order_by(SiretSummary.date_pap_c5.desc().nullslast()).limit(limit).all()


@router.get("/siret/{siret}", response_model=SiretSummaryOut)
def get_siret(siret: str, db: Session = Depends(get_session)):
    row = db.query(SiretSummary).get(siret)
    if not row:
        return JSONResponse({"detail": "SIRET introuvable"}, status_code=404)
    return row


@router.get("/siret/{siret}/timeseries")
def siret_timeseries(siret: str, db: Session = Depends(get_session)):
    rows = (
        db.query(PVEvent)
        .filter(PVEvent.siret == siret)
        .order_by(PVEvent.date_pv.asc())
        .all()
    )
    return {
        "dates": [r.date_pv for r in rows if r.date_pv],
        "inscrits": [r.inscrits or 0 for r in rows if r.date_pv],
        "votants": [r.votants or 0 for r in rows if r.date_pv],
        "cgt_voix": [r.cgt_voix or 0 for r in rows if r.date_pv],
    }


@router.get("/stats/global")
def global_stats(db: Session = Depends(get_session)):
    stats = compute_global_stats(db)
    return stats
