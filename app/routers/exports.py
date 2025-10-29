"""Exports CSV/Excel pour les données agrégées et sources."""
from __future__ import annotations

import io
from datetime import date
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..core.logging_config import audit_logger, get_logger
from ..core.security import verify_admin_optional
from ..db import get_session
from ..models import Invitation, PVEvent, SiretSummary

logger = get_logger(__name__)

router = APIRouter(prefix="/exports", tags=["exports"])


def _parse_date(raw: Optional[str]) -> Optional[date]:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        logger.warning("Filtre date invalide ignoré: %s", raw)
        return None


def _apply_summary_filters(
    qs,
    q: Optional[str],
    fd: Optional[str],
    departement: Optional[str],
    presence: Optional[str],
    os_query: Optional[str],
    date_pap_from: Optional[date],
    date_pap_to: Optional[date],
    date_pv_from: Optional[date],
    date_pv_to: Optional[date],
):
    if q:
        like = f"%{q}%"
        qs = qs.filter(
            (SiretSummary.siret.like(like)) | (SiretSummary.raison_sociale.ilike(like))
        )
    if fd:
        qs = qs.filter(SiretSummary.fd == fd)
    if departement:
        qs = qs.filter(SiretSummary.departement == departement)
    if presence:
        qs = qs.filter(SiretSummary.presence == presence)
    if os_query:
        like = f"%{os_query}%"
        qs = qs.filter(
            (SiretSummary.os_c3.ilike(like)) | (SiretSummary.os_c4.ilike(like))
        )
    if date_pap_from:
        qs = qs.filter(SiretSummary.date_pap_c5 >= date_pap_from)
    if date_pap_to:
        qs = qs.filter(SiretSummary.date_pap_c5 <= date_pap_to)
    if date_pv_from:
        qs = qs.filter(SiretSummary.date_pv_last >= date_pv_from)
    if date_pv_to:
        qs = qs.filter(SiretSummary.date_pv_last <= date_pv_to)
    return qs


def _stream_dataframe(df: pd.DataFrame, filename: str, excel: bool = False) -> StreamingResponse:
    if excel:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False)
        buffer.seek(0)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        response = StreamingResponse(buffer, media_type=media_type)
    else:
        csv_data = df.to_csv(index=False)
        response = StreamingResponse(io.StringIO(csv_data), media_type="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response


@router.get("/siret-summary/csv")
def export_summary_csv(
    q: Optional[str] = Query(None),
    fd: Optional[str] = Query(None),
    departement: Optional[str] = Query(None),
    presence: Optional[str] = Query(None),
    os_query: Optional[str] = Query(None, alias="os"),
    date_pap_from: Optional[str] = Query(None),
    date_pap_to: Optional[str] = Query(None),
    date_pv_from: Optional[str] = Query(None),
    date_pv_to: Optional[str] = Query(None),
    db: Session = Depends(get_session),
    user: Optional[str] = Depends(verify_admin_optional),
):
    qs = db.query(SiretSummary)
    qs = _apply_summary_filters(
        qs,
        q,
        fd,
        departement,
        presence,
        os_query,
        _parse_date(date_pap_from),
        _parse_date(date_pap_to),
        _parse_date(date_pv_from),
        _parse_date(date_pv_to),
    )
    df = pd.read_sql(qs.statement, db.bind)
    audit_logger.log_export(user, "siret_summary_csv", len(df))
    return _stream_dataframe(df, "siret-summary.csv")


@router.get("/siret-summary/excel")
def export_summary_excel(
    q: Optional[str] = Query(None),
    fd: Optional[str] = Query(None),
    departement: Optional[str] = Query(None),
    presence: Optional[str] = Query(None),
    os_query: Optional[str] = Query(None, alias="os"),
    date_pap_from: Optional[str] = Query(None),
    date_pap_to: Optional[str] = Query(None),
    date_pv_from: Optional[str] = Query(None),
    date_pv_to: Optional[str] = Query(None),
    db: Session = Depends(get_session),
    user: Optional[str] = Depends(verify_admin_optional),
):
    qs = db.query(SiretSummary)
    qs = _apply_summary_filters(
        qs,
        q,
        fd,
        departement,
        presence,
        os_query,
        _parse_date(date_pap_from),
        _parse_date(date_pap_to),
        _parse_date(date_pv_from),
        _parse_date(date_pv_to),
    )
    df = pd.read_sql(qs.statement, db.bind)
    audit_logger.log_export(user, "siret_summary_excel", len(df))
    return _stream_dataframe(df, "siret-summary.xlsx", excel=True)


@router.get("/pv-events/csv")
def export_pv_csv(
    db: Session = Depends(get_session),
    user: Optional[str] = Depends(verify_admin_optional),
):
    df = pd.read_sql(db.query(PVEvent).statement, db.bind)
    audit_logger.log_export(user, "pv_events_csv", len(df))
    return _stream_dataframe(df, "pv-events.csv")


@router.get("/invitations/csv")
def export_invitations_csv(
    db: Session = Depends(get_session),
    user: Optional[str] = Depends(verify_admin_optional),
):
    df = pd.read_sql(db.query(Invitation).statement, db.bind)
    audit_logger.log_export(user, "invitations_csv", len(df))
    return _stream_dataframe(df, "invitations.csv")
