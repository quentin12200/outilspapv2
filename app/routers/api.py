from fastapi import APIRouter, UploadFile, File, Depends, Query, HTTPException, BackgroundTasks, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, select
from typing import List
from datetime import datetime, timedelta, date
import re
import logging

from ..db import get_session, Base, engine, SessionLocal
from .. import etl
from ..models import SiretSummary, PVEvent, Invitation
from ..schemas import SiretSummaryOut
from ..services.sirene_api import enrichir_siret, SireneAPIError, rechercher_siret
from ..services.idcc_enrichment import get_idcc_enrichment_service
from ..background_tasks import task_tracker, run_build_siret_summary, run_enrichir_invitations_idcc
from ..validators import validate_siret, validate_date, validate_excel_file, ValidationError
from ..auth import require_api_key
from ..models import AuditLog
from ..audit import log_admin_action


router = APIRouter(prefix="/api", tags=["api"])
logger = logging.getLogger(__name__)

from fastapi.responses import RedirectResponse


def _month_bucket_expression(db: Session, column):
    """Return a SQL expression that groups dates by month across dialects."""

    try:
        bind = db.get_bind()
        dialect = (bind.dialect.name if bind is not None else "sqlite").lower()
    except Exception:
        # Fallback to SQLite if we can't determine the dialect
        dialect = "sqlite"

    if dialect == "postgresql":
        return func.to_char(column, "YYYY-MM")
    if dialect.startswith("mysql"):
        return func.date_format(column, "%Y-%m")

    # SQLite (and default fallback) uses strftime
    return func.strftime("%Y-%m", column)

@router.post("/ingest/pv")
async def ingest_pv(
    file: UploadFile = File(...),
    db: Session = Depends(get_session),
    api_key: str = Depends(require_api_key)
):
    """Ingestion de PV (requiert authentification API Key)"""
    # Valider le fichier Excel
    validate_excel_file(file)

    try:
        n = etl.ingest_pv_excel(db, file.file)
        logger.info(f"Ingestion PV réussie : {n} lignes traitées")
        return RedirectResponse(url="/?retour=1", status_code=303)
    except Exception as e:
        logger.error(f"Erreur lors de l'ingestion PV : {e}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'ingestion du fichier : {str(e)}")

@router.post("/ingest/invit")
async def ingest_invit(
    file: UploadFile = File(...),
    db: Session = Depends(get_session),
    api_key: str = Depends(require_api_key)
):
    """Ingestion d'invitations (requiert authentification API Key)"""
    # Valider le fichier Excel
    validate_excel_file(file)

    try:
        n = etl.ingest_invit_excel(db, file.file)
        logger.info(f"Ingestion invitations réussie : {n} lignes traitées")
        return RedirectResponse(url="/?retour=1", status_code=303)
    except Exception as e:
        logger.error(f"Erreur lors de l'ingestion invitations : {e}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'ingestion du fichier : {str(e)}")

@router.post("/build/summary")
def build_summary(
    background_tasks: BackgroundTasks,
    api_key: str = Depends(require_api_key)
):
    """
    Lance la reconstruction de la table siret_summary en arrière-plan.
    Retourne immédiatement avec un statut "en cours".
    Utiliser GET /api/build/summary/status pour suivre la progression.

    Requiert authentification API Key.
    """
    # Vérifier si une tâche est déjà en cours
    task_id = "build_siret_summary"
    current_status = task_tracker.get_task_status(task_id)

    if current_status and current_status["status"] == "running":
        return {
            "status": "already_running",
            "message": "Une reconstruction est déjà en cours",
            "task_id": task_id,
            "started_at": current_status["started_at"].isoformat(),
        }

    # Lancer la tâche en arrière-plan
    background_tasks.add_task(run_build_siret_summary, SessionLocal)

    return {
        "status": "started",
        "message": "La reconstruction de la table siret_summary a été lancée en arrière-plan",
        "task_id": task_id,
        "check_status_url": "/api/build/summary/status"
    }


@router.get("/build/summary/status")
def get_build_summary_status():
    """
    Récupère le statut de la tâche de reconstruction de siret_summary.
    """
    from datetime import datetime

    task_id = "build_siret_summary"
    status = task_tracker.get_task_status(task_id)

    if not status:
        return {
            "status": "not_found",
            "message": "Aucune tâche de reconstruction en cours ou récente"
        }

    response = {
        "status": status["status"],
        "description": status["description"],
        "started_at": status["started_at"].isoformat() if status["started_at"] else None,
        "completed_at": status["completed_at"].isoformat() if status["completed_at"] else None,
    }

    # Ajouter le temps écoulé pour les tâches en cours
    if status["status"] == "running" and status["started_at"]:
        elapsed = (datetime.now() - status["started_at"]).total_seconds()
        response["elapsed_seconds"] = elapsed

    # Ajouter la durée totale pour les tâches terminées
    if status["completed_at"] and status["started_at"]:
        duration = (status["completed_at"] - status["started_at"]).total_seconds()
        response["duration_seconds"] = duration

    if status["status"] == "completed":
        response["result"] = status["result"]
    elif status["status"] == "failed":
        response["error"] = status["error"]

    return response


@router.post("/enrichir/idcc")
def enrichir_idcc(
    background_tasks: BackgroundTasks,
    api_key: str = Depends(require_api_key)
):
    """
    Lance l'enrichissement des IDCC manquants en arrière-plan via l'API SIRENE.
    Retourne immédiatement avec un statut "en cours".
    Utiliser GET /api/enrichir/idcc/status pour suivre la progression.

    Requiert authentification API Key.
    """
    # Vérifier si une tâche est déjà en cours
    task_id = "enrichir_invitations_idcc"
    current_status = task_tracker.get_task_status(task_id)

    if current_status and current_status["status"] == "running":
        return {
            "status": "already_running",
            "message": "Un enrichissement IDCC est déjà en cours",
            "task_id": task_id,
            "started_at": current_status["started_at"].isoformat(),
        }

    # Lancer la tâche en arrière-plan
    background_tasks.add_task(run_enrichir_invitations_idcc)

    return {
        "status": "started",
        "message": "L'enrichissement des IDCC a été lancé en arrière-plan",
        "task_id": task_id,
        "check_status_url": "/api/enrichir/idcc/status"
    }


@router.get("/enrichir/idcc/status")
def get_enrichir_idcc_status():
    """
    Récupère le statut de la tâche d'enrichissement IDCC.
    """
    from datetime import datetime

    task_id = "enrichir_invitations_idcc"
    status = task_tracker.get_task_status(task_id)

    if not status:
        return {
            "status": "not_found",
            "message": "Aucune tâche d'enrichissement IDCC en cours ou récente"
        }

    response = {
        "status": status["status"],
        "description": status["description"],
        "started_at": status["started_at"].isoformat() if status["started_at"] else None,
        "completed_at": status["completed_at"].isoformat() if status["completed_at"] else None,
    }

    # Ajouter le temps écoulé pour les tâches en cours
    if status["status"] == "running" and status["started_at"]:
        elapsed = (datetime.now() - status["started_at"]).total_seconds()
        response["elapsed_seconds"] = elapsed

    # Ajouter la durée totale pour les tâches terminées
    if status["completed_at"] and status["started_at"]:
        duration = (status["completed_at"] - status["started_at"]).total_seconds()
        response["duration_seconds"] = duration

    if status["status"] == "completed":
        response["result"] = status["result"]
    elif status["status"] == "failed":
        response["error"] = status["error"]

    return response


@router.get("/siret", response_model=List[SiretSummaryOut])
def list_sirets(q: str = Query(None), db: Session = Depends(get_session)):
    qs = db.query(SiretSummary)
    if q:
        like = f"%{q}%"
        qs = qs.filter((SiretSummary.siret.like(like)) | (SiretSummary.raison_sociale.ilike(like)))
    return qs.limit(200).all()


@router.get("/search/autocomplete")
def search_autocomplete(q: str = Query(..., min_length=2), db: Session = Depends(get_session)):
    """
    Endpoint d'autocomplete pour la recherche
    Retourne les 10 premiers résultats correspondants
    """
    if len(q) < 2:
        return []

    like = f"%{q}%"
    results = db.query(SiretSummary).filter(
        (SiretSummary.siret.like(like)) |
        (SiretSummary.raison_sociale.ilike(like))
    ).limit(10).all()

    return [
        {
            "siret": r.siret,
            "raison_sociale": r.raison_sociale or "Sans nom",
            "dep": r.dep,
            "ville": r.ville,
            "date_pap_c5": (
                r.date_pap_c5.strftime("%d/%m/%Y")
                if isinstance(r.date_pap_c5, (datetime, date))
                else (str(r.date_pap_c5) if r.date_pap_c5 else None)
            ),
        }
        for r in results
    ]

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

    try:
        return _compute_dashboard_stats(db)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.exception("Error computing dashboard stats")
        raise HTTPException(status_code=500, detail=f"Error computing dashboard stats: {str(e)}")


def _compute_dashboard_stats(db: Session):
    """
    Helper function to compute dashboard statistics.

    Raises:
        Exception: If critical database queries fail
    """
    import logging
    logger = logging.getLogger(__name__)

    def _to_number(value):
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            cleaned = (
                value.strip()
                .replace("\u202f", "")
                .replace("\xa0", "")
                .replace(" ", "")
            )
            cleaned = cleaned.replace(",", ".")
            if not cleaned:
                return None
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None

    def _parse_date_value(value):
        if not value:
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                return None
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d.%m.%Y"):
                try:
                    return datetime.strptime(cleaned, fmt).date()
                except ValueError:
                    continue
            try:
                return datetime.fromisoformat(cleaned).date()
            except ValueError:
                return None
        return None

    def _format_date_display(value):
        if not value:
            return None
        if isinstance(value, datetime):
            value = value.date()
        if isinstance(value, date):
            return value.strftime("%d/%m/%Y")
        return None

    audience_threshold = 1000

    try:
        total_siret = db.query(func.count(SiretSummary.siret)).scalar() or 0
    except Exception as e:
        logger.error(f"Error counting total SIRET: {e}")
        raise

    #
    # Détermination des SIRET cible (≥ 1000 inscrits au dernier PV du cycle 4)
    # ----------------------------------------------------------------------
    def _normalize_siret(value):
        """Return a canonical 14-digit SIRET or ``None`` when the value is invalid."""
        if value is None:
            return None

        if isinstance(value, (bytes, bytearray)):
            text = value.decode("utf-8", "ignore")
        else:
            text = str(value)

        stripped = text.strip()
        if not stripped:
            return None

        digits_only = "".join(ch for ch in stripped if ch.isdigit())
        if len(digits_only) == 14:
            return digits_only

        if len(stripped) == 14 and stripped.isdigit():
            return stripped

        return digits_only or stripped or None

    try:
        latest_c4_rows = (
            db.query(
                PVEvent.siret,
                PVEvent.id,
                PVEvent.date_pv,
                PVEvent.inscrits,
                PVEvent.cgt_voix,
            )
            .filter(PVEvent.cycle.isnot(None))
            .filter(PVEvent.cycle.ilike("%C4%"))
            .all()
        )
    except Exception as e:
        logger.error(f"Error fetching C4 PV events: {e}")
        raise

    latest_per_siret: dict[str, dict[str, float]] = {}
    for siret_value, pv_id, pv_date_value, inscrits_value, cgt_voix_value in latest_c4_rows:
        siret_str = _normalize_siret(siret_value)
        if not siret_str:
            continue

        parsed_pv_date = _parse_date_value(pv_date_value)

        # Use date as primary sort key, ID as tiebreaker only when dates are equal
        # This ensures deterministic ordering while still being chronologically correct
        try:
            pv_order = int(pv_id or 0)
        except (TypeError, ValueError):
            pv_order = 0

        order_tuple = (
            parsed_pv_date or date.min,
            pv_order,  # Secondary sort: higher ID = more recent when dates are equal
        )

        current = latest_per_siret.get(siret_str)
        if current and order_tuple <= current.get("order", (date.min, 0)):
            continue

        latest_per_siret[siret_str] = {
            "order": order_tuple,
            "date": parsed_pv_date,
            "inscrits": _to_number(inscrits_value) or 0.0,
            "cgt_voix": _to_number(cgt_voix_value) or 0.0,
        }

    eligible_sirets = {
        siret
        for siret, payload in latest_per_siret.items()
        if payload.get("inscrits", 0) >= audience_threshold
    }

    audience_siret = len(eligible_sirets)

    summary_rows = []
    if eligible_sirets:
        summary_rows = (
            db.query(
                SiretSummary.siret,
                SiretSummary.dep,
                SiretSummary.carence_c4,
                SiretSummary.cgt_implantee,
                SiretSummary.cgt_voix_c4,
                SiretSummary.statut_pap,
                SiretSummary.inscrits_c4,
            )
            .filter(SiretSummary.siret.in_(eligible_sirets))
            .all()
        )

    audience_siret_c4_carence = sum(1 for row in summary_rows if row.carence_c4)
    audience_siret_c4_pv = max(audience_siret - audience_siret_c4_carence, 0)

    audience_inscrits = int(
        sum(latest_per_siret[s]["inscrits"] for s in eligible_sirets)
    )

    audience_cgt_implantee = sum(1 for row in summary_rows if row.cgt_implantee)

    audience_voix_cgt = 0
    for row in summary_rows:
        if row.cgt_voix_c4 is not None:
            audience_voix_cgt += row.cgt_voix_c4
        else:
            audience_voix_cgt += latest_per_siret.get(row.siret, {}).get("cgt_voix", 0) or 0
    audience_voix_cgt = int(audience_voix_cgt)

    if eligible_sirets:
        audience_invitations = (
            db.query(func.count(func.distinct(Invitation.siret)))
            .filter(Invitation.siret.in_(eligible_sirets))
            .scalar()
            or 0
        )
    else:
        audience_invitations = 0

    # Répartition par département (top 10) sur la cible
    dep_counts: dict[str, int] = {}
    for row in summary_rows:
        dep_value = (str(row.dep) if row.dep is not None else "").strip()
        if not dep_value:
            continue
        dep_counts[dep_value] = dep_counts.get(dep_value, 0) + 1

    dep_stats = sorted(
        dep_counts.items(), key=lambda item: (-item[1], item[0])
    )[:10]

    six_months_ago = date.today() - timedelta(days=180)

    month_bucket = _month_bucket_expression(db, Invitation.date_invit)

    monthly_rows = (
        db.query(
            month_bucket.label("month"),
            func.count(Invitation.id).label("count"),
        )
        .filter(Invitation.date_invit >= six_months_ago)
        .group_by(month_bucket)
        .order_by(month_bucket)
        .all()
    )

    monthly_invitations: list[dict[str, object]] = []
    for month_key, count in monthly_rows:
        label = None
        if month_key:
            try:
                month_date = datetime.strptime(f"{month_key}-01", "%Y-%m-%d").date()
                label = month_date.strftime("%d/%m/%Y")
            except ValueError:
                label = str(month_key)
        monthly_invitations.append({
            "month": month_key,
            "count": count,
            "label": label,
        })

    today = date.today()

    upcoming_rows = (
        db.query(
            PVEvent.siret,
            PVEvent.cycle,
            PVEvent.date_prochain_scrutin,
            PVEvent.effectif_siret,
            PVEvent.inscrits,
            PVEvent.quadrimestre_scrutin,
        )
        .filter(PVEvent.date_prochain_scrutin.isnot(None))
        .all()
    )

    cycle5_reference_start = date(2025, 1, 1)
    cycle5_reference_end = date(2028, 12, 31)

    upcoming_entries: list[dict[str, object]] = []

    for (
        siret,
        cycle,
        next_date,
        effectif_siret,
        inscrits,
        quadrimestre,
    ) in upcoming_rows:
        parsed_date = _parse_date_value(next_date)
        if not parsed_date:
            continue

        if parsed_date < cycle5_reference_start or parsed_date > cycle5_reference_end:
            continue

        siret_value = _normalize_siret(siret)
        if not siret_value:
            continue

        effectif_value = _to_number(effectif_siret)
        if effectif_value is None:
            effectif_value = _to_number(inscrits)

        upcoming_entries.append(
            {
                "siret": siret_value,
                "date": parsed_date,
                "effectif": effectif_value,
                "cycle_marker": cycle,
                "quadrimestre": quadrimestre,
            }
        )

    missing_effectif_sirets = {
        entry["siret"]
        for entry in upcoming_entries
        if entry.get("effectif") is None
    }

    summary_lookup: dict[str, dict[str, object]] = {}
    if missing_effectif_sirets:
        lookup_rows = (
            db.query(
                SiretSummary.siret,
                SiretSummary.effectif_siret,
                SiretSummary.inscrits_c4,
                SiretSummary.inscrits_c3,
            )
            .filter(SiretSummary.siret.in_(missing_effectif_sirets))
            .all()
        )
        summary_lookup = {
            row.siret: {
                "effectif_siret": row.effectif_siret,
                "inscrits_c4": row.inscrits_c4,
                "inscrits_c3": row.inscrits_c3,
            }
            for row in lookup_rows
        }

    for entry in upcoming_entries:
        if entry.get("effectif") is not None:
            continue

        summary_row = summary_lookup.get(entry["siret"])
        if summary_row:
            for key in ("effectif_siret", "inscrits_c4", "inscrits_c3"):
                candidate = _to_number(summary_row.get(key))
                if candidate:
                    entry["effectif"] = candidate
                    break

        if entry.get("effectif") is None:
            latest_payload = latest_per_siret.get(entry["siret"])
            if latest_payload:
                entry["effectif"] = latest_payload.get("inscrits")

        if entry.get("effectif") is None:
            entry["effectif"] = 0.0

    declared_c5_by_siret: dict[str, dict[str, object]] = {}
    for entry in upcoming_entries:
        siret_value = entry["siret"]  # type: ignore[index]
        parsed_date = entry["date"]  # type: ignore[index]
        current = declared_c5_by_siret.get(siret_value)
        if current is None:
            declared_c5_by_siret[siret_value] = {
                "date": parsed_date,
                "effectif": entry.get("effectif") or 0.0,
            }
            continue

        current_date = current.get("date")
        if isinstance(parsed_date, date) and (
            not isinstance(current_date, date) or parsed_date < current_date
        ):
            declared_c5_by_siret[siret_value] = {
                "date": parsed_date,
                "effectif": entry.get("effectif") or 0.0,
            }

    quarter_counts: dict[tuple[int, int], int] = {}
    for payload in declared_c5_by_siret.values():
        declared_date = payload.get("date")
        if not isinstance(declared_date, date):
            continue
        quarter_index = ((declared_date.month - 1) // 3) + 1
        key = (declared_date.year, quarter_index)
        quarter_counts[key] = quarter_counts.get(key, 0) + 1

    def _iterate_quarters(start: date, end: date):
        year = start.year
        quarter = ((start.month - 1) // 3) + 1
        final_quarter = ((end.month - 1) // 3) + 1
        while year < end.year or (year == end.year and quarter <= final_quarter):
            yield year, quarter
            quarter += 1
            if quarter > 4:
                quarter = 1
                year += 1

    upcoming_quarters = [
        {
            "label": f"T{quarter} {year}",
            "count": quarter_counts.get((year, quarter), 0),
        }
        for year, quarter in _iterate_quarters(
            cycle5_reference_start, cycle5_reference_end
        )
    ]

    declared_dates_sorted = sorted(
        [
            payload["date"]
            for payload in declared_c5_by_siret.values()
            if isinstance(payload.get("date"), date)
        ]
    )
    future_dates = [d for d in declared_dates_sorted if d >= today]

    coverage_start_date = declared_dates_sorted[0] if declared_dates_sorted else None
    coverage_end_date = declared_dates_sorted[-1] if declared_dates_sorted else None
    upcoming_next_date = future_dates[0] if future_dates else None

    declared_total_all = len(declared_c5_by_siret)
    declared_total_eligible = sum(
        1
        for payload in declared_c5_by_siret.values()
        if (_to_number(payload.get("effectif")) or 0) >= audience_threshold
    )

    future_total_all = sum(1 for d in future_dates)
    future_total_eligible = sum(
        1
        for payload in declared_c5_by_siret.values()
        if isinstance(payload.get("date"), date)
        and payload["date"] >= today  # type: ignore[index]
        and (_to_number(payload.get("effectif")) or 0) >= audience_threshold
    )

    declared_percent = round(
        (declared_total_eligible / audience_siret * 100) if audience_siret > 0 else 0,
        1,
    )
    future_percent = round(
        (future_total_eligible / audience_siret * 100) if audience_siret > 0 else 0,
        1,
    )

    c3_condition = or_(
        SiretSummary.date_pv_c3.isnot(None),
        SiretSummary.carence_c3.is_(True),
    )
    c4_condition = or_(
        SiretSummary.date_pv_c4.isnot(None),
        SiretSummary.carence_c4.is_(True),
    )
    possessions_condition = or_(c3_condition, c4_condition)

    autres_possessions_total = (
        db.query(func.count(SiretSummary.siret))
        .filter(possessions_condition)
        .scalar()
        or 0
    )
    autres_possessions_c3 = (
        db.query(func.count(SiretSummary.siret))
        .filter(c3_condition)
        .scalar()
        or 0
    )
    autres_possessions_c4 = (
        db.query(func.count(SiretSummary.siret))
        .filter(c4_condition)
        .scalar()
        or 0
    )

    invitations_period_start = date(2025, 1, 1)
    invitations_period_end_raw = (
        db.query(func.max(Invitation.date_invit)).scalar()
    )
    invitations_period_end = _parse_date_value(invitations_period_end_raw)
    invitations_period_total = 0
    if invitations_period_end:
        invitations_period_total = (
            db.query(func.count(Invitation.id))
            .filter(Invitation.date_invit >= invitations_period_start)
            .filter(Invitation.date_invit <= invitations_period_end)
            .scalar()
            or 0
        )

    invitations_total = db.query(func.count(Invitation.id)).scalar() or 0

    pv_total = db.query(func.count(PVEvent.id)).scalar() or 0
    pv_sirets = db.query(func.count(func.distinct(PVEvent.siret))).scalar() or 0
    last_summary_date_raw = db.query(func.max(SiretSummary.date_pv_max)).scalar()
    last_summary_date = _parse_date_value(last_summary_date_raw)
    last_invitation_date = invitations_period_end

    pv_sirets_subquery = select(SiretSummary.siret).where(possessions_condition)
    pap_pv_overlap = (
        db.query(func.count(func.distinct(Invitation.siret)))
        .filter(Invitation.siret.in_(pv_sirets_subquery))
        .scalar()
        or 0
    )
    pap_pv_overlap_percent = round(
        (pap_pv_overlap / invitations_total * 100) if invitations_total > 0 else 0,
        1,
    )

    invitations_period_start_display = _format_date_display(
        invitations_period_start
    )
    invitations_period_end_display = _format_date_display(invitations_period_end)

    global_stats = {
        "pv_total": pv_total,
        "pv_sirets": pv_sirets,
        "summary_total": total_siret,
        "last_summary": _format_date_display(last_summary_date),
        "invit_total": invitations_total,
        "last_invitation": _format_date_display(last_invitation_date),
        "upcoming_total": declared_total_eligible,
        "upcoming_next": _format_date_display(upcoming_next_date),
        "upcoming_threshold": audience_threshold,
        "upcoming_period_start": cycle5_reference_start.isoformat(),
        "upcoming_period_end": cycle5_reference_end.isoformat(),
        "upcoming_period_start_display": _format_date_display(
            cycle5_reference_start
        ),
        "upcoming_period_end_display": _format_date_display(
            cycle5_reference_end
        ),
        "upcoming_total_all": declared_total_all,
        "upcoming_next_all": _format_date_display(upcoming_next_date),
    }

    # Statistiques par statut PAP sur la cible
    statut_counts: dict[str, int] = {}
    for row in summary_rows:
        statut_value = (str(row.statut_pap) if row.statut_pap is not None else "").strip()
        if not statut_value:
            continue
        statut_counts[statut_value] = statut_counts.get(statut_value, 0) + 1

    statut_stats = sorted(
        statut_counts.items(), key=lambda item: (-item[1], item[0])
    )

    # ============================================================================
    # NOUVEAUX INDICATEURS ENRICHIS
    # ============================================================================

    # 1. Taux de réponse PAP
    invitations_avec_reponse = (
        db.query(func.count(Invitation.id))
        .filter(Invitation.date_reception.isnot(None))
        .scalar() or 0
    )
    taux_reponse_pap = round(
        (invitations_avec_reponse / invitations_total * 100) if invitations_total > 0 else 0,
        1,
    )

    # 2. Élections dans les 30 prochains jours
    thirty_days_later = today + timedelta(days=30)
    elections_next_30_days = (
        db.query(func.count(func.distinct(Invitation.siret)))
        .filter(Invitation.date_election.isnot(None))
        .filter(Invitation.date_election >= today)
        .filter(Invitation.date_election <= thirty_days_later)
        .scalar() or 0
    )

    # 3. Taux de programmation élections
    invitations_election_programmee = (
        db.query(func.count(Invitation.id))
        .filter(Invitation.date_election.isnot(None))
        .scalar() or 0
    )
    taux_programmation_elections = round(
        (invitations_election_programmee / invitations_total * 100) if invitations_total > 0 else 0,
        1,
    )

    # 4. Invitations sans réponse > 30 jours
    thirty_days_ago = today - timedelta(days=30)
    invitations_sans_reponse_30j = (
        db.query(func.count(Invitation.id))
        .filter(Invitation.date_invit < thirty_days_ago)
        .filter(Invitation.date_reception.is_(None))
        .scalar() or 0
    )

    # 5. Taux d'enrichissement API SIRENE
    invitations_enrichies = (
        db.query(func.count(Invitation.id))
        .filter(Invitation.date_enrichissement.isnot(None))
        .scalar() or 0
    )
    taux_enrichissement_sirene = round(
        (invitations_enrichies / invitations_total * 100) if invitations_total > 0 else 0,
        1,
    )

    return {
        "audience_threshold": audience_threshold,
        "audience_siret": audience_siret,
        "audience_siret_c4_pv": audience_siret_c4_pv,
        "audience_siret_c4_carence": audience_siret_c4_carence,
        "audience_share_percent": round(
            (audience_siret / total_siret * 100) if total_siret > 0 else 0, 1
        ),
        "audience_inscrits": audience_inscrits,
        "audience_invitations": audience_invitations,
        "audience_invitations_percent": round(
            (audience_invitations / audience_siret * 100) if audience_siret > 0 else 0,
            1,
        ),
        "audience_non_invites": max(audience_siret - audience_invitations, 0),
        "audience_cgt_implantee": audience_cgt_implantee,
        "audience_cgt_implantee_percent": round(
            (audience_cgt_implantee / audience_siret * 100) if audience_siret > 0 else 0,
            1,
        ),
        "audience_sans_cgt": max(audience_siret - audience_cgt_implantee, 0),
        "audience_voix_cgt": audience_voix_cgt,
        "audience_voix_percent": round(
            (audience_voix_cgt / audience_inscrits * 100) if audience_inscrits > 0 else 0,
            1,
        ),
        "audience_upcoming_c5": future_total_eligible,
        "audience_upcoming_c5_percent": future_percent,
        "audience_upcoming_declared_total": declared_total_eligible,
        "audience_upcoming_declared_percent": declared_percent,
        "audience_upcoming_future_total": future_total_eligible,
        "audience_upcoming_future_percent": future_percent,
        "audience_upcoming_period_start": cycle5_reference_start.isoformat(),
        "audience_upcoming_period_end": cycle5_reference_end.isoformat(),
        "audience_upcoming_period_start_display": _format_date_display(
            cycle5_reference_start
        ),
        "audience_upcoming_period_end_display": _format_date_display(
            cycle5_reference_end
        ),
        "audience_upcoming_coverage_start_display": _format_date_display(
            coverage_start_date
        ),
        "audience_upcoming_coverage_end_display": _format_date_display(
            coverage_end_date
        ),
        "audience_upcoming_declared_total_all": declared_total_all,
        "audience_upcoming_future_total_all": future_total_all,
        "autres_possessions_total": autres_possessions_total,
        "autres_possessions_c3": autres_possessions_c3,
        "autres_possessions_c4": autres_possessions_c4,
        "invitations_period_total": invitations_period_total,
        "invitations_period_start": invitations_period_start.isoformat(),
        "invitations_period_end": (
            invitations_period_end.isoformat() if invitations_period_end else None
        ),
        "invitations_period_start_display": invitations_period_start_display,
        "invitations_period_end_display": invitations_period_end_display,
        "pap_pv_overlap": pap_pv_overlap,
        "pap_pv_overlap_percent": pap_pv_overlap_percent,
        "departments": [{"dep": d[0], "count": d[1]} for d in dep_stats],
        "monthly_invitations": monthly_invitations,
        "upcoming_quarters": upcoming_quarters,
        "statut_stats": [{"statut": s[0], "count": s[1]} for s in statut_stats],
        "global_stats": global_stats,
        # Nouveaux indicateurs enrichis
        "invitations_avec_reponse": invitations_avec_reponse,
        "taux_reponse_pap": taux_reponse_pap,
        "elections_next_30_days": elections_next_30_days,
        "invitations_election_programmee": invitations_election_programmee,
        "taux_programmation_elections": taux_programmation_elections,
        "invitations_sans_reponse_30j": invitations_sans_reponse_30j,
        "invitations_enrichies": invitations_enrichies,
        "taux_enrichissement_sirene": taux_enrichissement_sirene,
    }


# ============================================================================
# ENRICHISSEMENT API SIRENE
# ============================================================================

def _normalise_search_term(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _search_local_siret(
    db: Session,
    nom: str,
    code_postal: str | None,
    ville: str | None,
    limit: int
) -> list[dict[str, str]]:
    """Fallback local en cas d'échec de l'API Sirene."""

    query = db.query(SiretSummary)

    cleaned_name = _normalise_search_term(nom)
    if cleaned_name:
        for token in cleaned_name.split():
            query = query.filter(SiretSummary.raison_sociale.ilike(f"%{token}%"))

    # Prioritize postal code over city
    if code_postal:
        query = query.filter(SiretSummary.cp.ilike(f"{code_postal}%"))
    elif ville:
        cleaned_city = _normalise_search_term(ville)
        if cleaned_city:
            for token in cleaned_city.split():
                query = query.filter(SiretSummary.ville.ilike(f"%{token}%"))

    if not cleaned_name and not code_postal and not ville:
        return []

    rows = (
        query
        .order_by(func.coalesce(SiretSummary.inscrits_c4, 0).desc())
        .limit(limit)
        .all()
    )

    results: list[dict[str, str]] = []
    for row in rows:
        adresse_parts = [
            row.cp or "",
            (row.ville or "").title(),
        ]
        adresse = " ".join(part for part in adresse_parts if part).strip()

        fd = row.fd_c4 or row.fd_c3
        idcc = row.idcc
        meta_parts = [
            f"FD {fd}" if fd else "",
            f"IDCC {idcc}" if idcc else "",
        ]
        activite = " • ".join(part for part in meta_parts if part)

        results.append({
            "siret": row.siret,
            "siren": row.siren,
            "denomination": row.raison_sociale or "Raison sociale inconnue",
            "adresse": adresse,
            "activite": activite,
        })

    return results


@router.get("/sirene/search")
async def sirene_search(
    nom: str = Query(..., min_length=2),
    code_postal: str | None = Query(None, min_length=5, max_length=5),
    ville: str | None = Query(None, min_length=2),
    limit: int = Query(10, ge=1, le=20),
    db: Session = Depends(get_session),
):
    """Recherche d'établissements via l'API Sirene."""

    sirene_error: str | None = None
    results: List[dict] = []

    try:
        results = await rechercher_siret(nom, code_postal, ville, limit)
    except SireneAPIError as exc:
        sirene_error = str(exc)

    if results:
        return {"results": results, "source": "sirene"}

    fallback = _search_local_siret(db, nom, code_postal, ville, limit)
    if fallback:
        response = {"results": fallback, "source": "local"}
        if sirene_error:
            response["warning"] = sirene_error
        return response

    if sirene_error:
        raise HTTPException(status_code=502, detail=sirene_error)

    return {"results": [], "source": "sirene"}


@router.post("/sirene/enrichir/{siret}")
async def enrichir_un_siret(
    siret: str,
    db: Session = Depends(get_session),
    api_key: str = Depends(require_api_key)
):
    """
    Enrichit une invitation avec les données de l'API Sirene.

    Requiert authentification API Key.
    """
    # Valider le SIRET
    try:
        siret_clean = validate_siret(siret, raise_exception=True)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Vérifie que l'invitation existe
    invitation = db.query(Invitation).filter(Invitation.siret == siret_clean).first()
    if not invitation:
        raise HTTPException(status_code=404, detail=f"Aucune invitation trouvée pour le SIRET {siret_clean}")

    try:
        # Récupère les données depuis l'API Sirene
        data = await enrichir_siret(siret_clean)

        if not data:
            raise HTTPException(status_code=404, detail=f"SIRET {siret_clean} non trouvé dans l'API Sirene")

        # Met à jour l'invitation
        invitation.denomination = data.get("denomination")
        invitation.enseigne = data.get("enseigne")
        invitation.adresse = data.get("adresse")
        invitation.code_postal = data.get("code_postal")
        invitation.commune = data.get("commune")
        invitation.activite_principale = data.get("activite_principale")
        invitation.libelle_activite = data.get("libelle_activite")
        invitation.tranche_effectifs = data.get("tranche_effectifs")
        invitation.effectifs_label = data.get("effectifs_label")
        invitation.est_siege = data.get("est_siege")
        invitation.est_actif = data.get("est_actif")
        invitation.categorie_entreprise = data.get("categorie_entreprise")
        invitation.idcc = data.get("idcc")  # Convention collective
        invitation.date_enrichissement = datetime.now()

        db.commit()

        return {
            "success": True,
            "message": f"SIRET {siret_clean} enrichi avec succès",
            "data": data
        }

    except SireneAPIError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/sirene/enrichir-tout")
async def enrichir_toutes_invitations(
    force: bool = Query(False, description="Forcer le réenrichissement même si déjà fait"),
    db: Session = Depends(get_session),
    api_key: str = Depends(require_api_key)
):
    """
    [DEPRECATED] Enrichit toutes les invitations qui n'ont pas encore été enrichies.

    ⚠️ AVERTISSEMENT : Cet endpoint exécute les enrichissements de manière séquentielle
    et peut prendre beaucoup de temps, bloquant le serveur.

    RECOMMANDATION : Utilisez plutôt POST /api/enrichir/idcc qui exécute la tâche
    en arrière-plan de manière asynchrone et non-bloquante.

    Si force=True, réenrichit même celles déjà enrichies.

    Requiert authentification API Key.
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.warning("⚠️ Endpoint /api/sirene/enrichir-tout is deprecated. Use /api/enrichir/idcc instead.")
    # Récupère les invitations à enrichir
    query = db.query(Invitation)
    if not force:
        query = query.filter(Invitation.date_enrichissement.is_(None))

    invitations = query.all()

    if not invitations:
        return {
            "success": True,
            "message": "Aucune invitation à enrichir",
            "enrichis": 0,
            "erreurs": 0
        }

    enrichis = 0
    erreurs = 0
    erreurs_details = []

    # Parallélisation avec semaphore pour limiter le nombre de requêtes simultanées
    # Limite à 5 requêtes simultanées pour ne pas surcharger l'API Sirene
    import asyncio
    semaphore = asyncio.Semaphore(5)

    async def enrichir_invitation_safe(invitation):
        """Enrichit une invitation avec gestion d'erreur et semaphore"""
        nonlocal enrichis, erreurs, erreurs_details

        async with semaphore:
            try:
                # Récupère les données depuis l'API Sirene
                data = await enrichir_siret(invitation.siret)

                if data:
                    # Met à jour l'invitation
                    invitation.denomination = data.get("denomination")
                    invitation.enseigne = data.get("enseigne")
                    invitation.adresse = data.get("adresse")
                    invitation.code_postal = data.get("code_postal")
                    invitation.commune = data.get("commune")
                    invitation.activite_principale = data.get("activite_principale")
                    invitation.libelle_activite = data.get("libelle_activite")
                    invitation.tranche_effectifs = data.get("tranche_effectifs")
                    invitation.effectifs_label = data.get("effectifs_label")
                    invitation.est_siege = data.get("est_siege")
                    invitation.est_actif = data.get("est_actif")
                    invitation.categorie_entreprise = data.get("categorie_entreprise")
                    invitation.idcc = data.get("idcc")  # Convention collective
                    invitation.date_enrichissement = datetime.now()
                    enrichis += 1
                else:
                    erreurs += 1
                    erreurs_details.append(f"SIRET {invitation.siret} non trouvé")

            except SireneAPIError as e:
                erreurs += 1
                erreurs_details.append(f"SIRET {invitation.siret}: {str(e)}")
            except Exception as e:
                erreurs += 1
                erreurs_details.append(f"SIRET {invitation.siret}: Erreur inattendue - {type(e).__name__}")
                logger.error(f"Unexpected error enriching {invitation.siret}: {e}", exc_info=True)

    # Exécuter les enrichissements en parallèle (limité par le semaphore)
    await asyncio.gather(*[enrichir_invitation_safe(inv) for inv in invitations])

    # Sauvegarde en base
    db.commit()

    return {
        "success": True,
        "message": f"{enrichis} invitations enrichies, {erreurs} erreurs",
        "enrichis": enrichis,
        "erreurs": erreurs,
        "erreurs_details": erreurs_details[:10]  # Limite à 10 premières erreurs
    }


@router.get("/sirene/stats")
def stats_enrichissement(db: Session = Depends(get_session)):
    """
    Retourne les statistiques sur l'enrichissement des invitations
    """
    total = db.query(func.count(Invitation.id)).scalar() or 0
    enrichis = db.query(func.count(Invitation.id)).filter(
        Invitation.date_enrichissement.isnot(None)
    ).scalar() or 0
    non_enrichis = total - enrichis

    # Invitations avec établissements actifs
    actifs = db.query(func.count(Invitation.id)).filter(
        Invitation.est_actif == True
    ).scalar() or 0

    # Invitations avec établissements inactifs
    inactifs = db.query(func.count(Invitation.id)).filter(
        Invitation.est_actif == False
    ).scalar() or 0

    # Top 10 des tranches d'effectifs
    effectifs_stats = db.query(
        Invitation.effectifs_label,
        func.count(Invitation.id).label('count')
    ).filter(
        Invitation.effectifs_label.isnot(None)
    ).group_by(
        Invitation.effectifs_label
    ).order_by(
        func.count(Invitation.id).desc()
    ).limit(10).all()

    # Top 10 des activités
    activites_stats = db.query(
        Invitation.libelle_activite,
        func.count(Invitation.id).label('count')
    ).filter(
        Invitation.libelle_activite.isnot(None)
    ).group_by(
        Invitation.libelle_activite
    ).order_by(
        func.count(Invitation.id).desc()
    ).limit(10).all()

    return {
        "total": total,
        "enrichis": enrichis,
        "non_enrichis": non_enrichis,
        "pourcentage_enrichis": round((enrichis / total * 100) if total > 0 else 0, 1),
        "actifs": actifs,
        "inactifs": inactifs,
        "effectifs": [{"label": e[0], "count": e[1]} for e in effectifs_stats],
        "activites": [{"label": a[0], "count": a[1]} for a in activites_stats]
    }


@router.get("/stats/enriched")
def enriched_kpi_stats(db: Session = Depends(get_session)):
    """
    Retourne les KPIs simplifiés pour la homepage dashboard.
    """
    # Total des invitations
    total_invitations = db.query(func.count(Invitation.id)).scalar() or 0

    # Seuil d'audience (fixe)
    audience_threshold = 1000

    # Calcul du PAP ↔ PV overlap
    # D'abord, récupère les SIRET qui ont des PV (via SiretSummary)
    c3_condition = or_(
        SiretSummary.date_pv_c3.isnot(None),
        SiretSummary.carence_c3.is_(True),
    )
    c4_condition = or_(
        SiretSummary.date_pv_c4.isnot(None),
        SiretSummary.carence_c4.is_(True),
    )
    possessions_condition = or_(c3_condition, c4_condition)

    pv_sirets_subquery = select(SiretSummary.siret).where(possessions_condition)
    pap_pv_overlap = (
        db.query(func.count(func.distinct(Invitation.siret)))
        .filter(Invitation.siret.in_(pv_sirets_subquery))
        .scalar()
        or 0
    )
    pap_pv_overlap_percent = round(
        (pap_pv_overlap / total_invitations * 100) if total_invitations > 0 else 0,
        1,
    )

    # CGT implantée - compte les SIRET avec cgt_implantee = True
    cgt_implanted_count = (
        db.query(func.count(SiretSummary.siret))
        .filter(SiretSummary.cgt_implantee.is_(True))
        .scalar()
        or 0
    )

    # Total SIRET pour calculer le pourcentage
    total_siret = db.query(func.count(SiretSummary.siret)).scalar() or 0
    cgt_implanted_percent = round(
        (cgt_implanted_count / total_siret * 100) if total_siret > 0 else 0,
        1,
    )

    # Elections dans les 30 prochains jours
    today = date.today()
    thirty_days_later = today + timedelta(days=30)

    # Compte les PVEvents avec date_prochain_scrutin dans les 30 jours
    elections_next_30_days = (
        db.query(func.count(func.distinct(PVEvent.siret)))
        .filter(PVEvent.date_prochain_scrutin.isnot(None))
        .filter(PVEvent.date_prochain_scrutin >= today)
        .filter(PVEvent.date_prochain_scrutin <= thirty_days_later)
        .scalar()
        or 0
    )

    return {
        "total_invitations": total_invitations,
        "audience_threshold": audience_threshold,
        "pap_pv_overlap_percent": pap_pv_overlap_percent,
        "cgt_implanted_count": cgt_implanted_count,
        "cgt_implanted_percent": cgt_implanted_percent,
        "elections_next_30_days": elections_next_30_days,
    }


@router.get("/stats/dashboard-enhanced")
def dashboard_enhanced_stats(db: Session = Depends(get_session)):
    """
    Statistiques enrichies pour les nouveaux graphiques du dashboard
    """
    # Top 10 secteurs d'activité (depuis invitations enrichies)
    activites_stats = db.query(
        Invitation.libelle_activite,
        func.count(Invitation.id).label('count')
    ).filter(
        Invitation.libelle_activite.isnot(None)
    ).group_by(
        Invitation.libelle_activite
    ).order_by(
        func.count(Invitation.id).desc()
    ).limit(10).all()

    # Top 10 entreprises par effectifs (depuis invitations enrichies)
    top_effectifs = db.query(
        Invitation.siret,
        Invitation.denomination,
        Invitation.effectifs_label,
        Invitation.tranche_effectifs
    ).filter(
        Invitation.tranche_effectifs.isnot(None),
        Invitation.est_actif == True
    ).order_by(
        Invitation.tranche_effectifs.desc()
    ).limit(10).all()

    # Compte par département (pour la carte de France)
    dep_counts = db.query(
        SiretSummary.dep,
        func.count(SiretSummary.siret).label('count')
    ).filter(
        SiretSummary.dep.isnot(None)
    ).group_by(
        SiretSummary.dep
    ).order_by(
        func.count(SiretSummary.siret).desc()
    ).all()

    # Évolution des invitations sur les 12 derniers mois
    twelve_months_ago = date.today() - timedelta(days=365)

    month_bucket = _month_bucket_expression(db, Invitation.date_invit)

    monthly_evolution = (
        db.query(
            month_bucket.label('month'),
            func.count(Invitation.id).label('count')
        )
        .filter(Invitation.date_invit >= twelve_months_ago)
        .group_by(month_bucket)
        .order_by(month_bucket)
        .all()
    )

    return {
        "activites": [{"label": a[0][:50], "count": a[1]} for a in activites_stats],  # Tronquer les noms longs
        "top_effectifs": [
            {
                "siret": e[0],
                "denomination": e[1] or "Sans nom",
                "effectifs_label": e[2],
                "tranche": e[3]
            }
            for e in top_effectifs
        ],
        "departements": [{"dep": d[0], "count": d[1]} for d in dep_counts],
        "monthly_evolution": [{"month": m[0], "count": m[1]} for m in monthly_evolution]
    }

@router.get("/siret/{siret}/check")
def check_siret_exists(siret: str, db: Session = Depends(get_session)):
    """
    Vérifie si un SIRET existe dans la base et retourne ses données.
    Utile pour pré-remplir le formulaire d'ajout PAP.
    """
    # Cherche dans SiretSummary
    summary = db.query(SiretSummary).filter(SiretSummary.siret == siret).first()
    
    # Cherche dans Invitations
    invitation = db.query(Invitation).filter(Invitation.siret == siret).order_by(Invitation.date_invit.desc()).first()
    
    # Cherche dans PVEvent
    pv_event = db.query(PVEvent).filter(PVEvent.siret == siret).order_by(PVEvent.date_pv.desc()).first()
    
    if not summary and not invitation and not pv_event:
        return {"exists": False, "data": None}
    
    # Construit les données depuis les différentes sources
    data = {
        "siret": siret,
        "raison_sociale": None,
        "ville": None,
        "code_postal": None,
        "ud": None,
        "fd": None,
        "idcc": None,
        "effectif": None,
    }
    
    # Priorise SiretSummary pour les données
    if summary:
        data["raison_sociale"] = summary.raison_sociale
        data["ville"] = summary.ville
        data["code_postal"] = summary.cp
        data["ud"] = summary.ud_c4 or summary.ud_c3
        data["fd"] = summary.fd_c4 or summary.fd_c3
        data["idcc"] = summary.idcc
        data["effectif"] = summary.effectif_siret
    
    # Complète avec Invitation si nécessaire
    if invitation:
        if not data["raison_sociale"]:
            data["raison_sociale"] = invitation.denomination
        if not data["ville"]:
            data["ville"] = invitation.commune
        if not data["code_postal"]:
            data["code_postal"] = invitation.code_postal
        if not data["ud"] and invitation.ud:
            data["ud"] = invitation.ud
        if not data["fd"] and invitation.fd:
            data["fd"] = invitation.fd
        if not data["idcc"] and invitation.idcc:
            data["idcc"] = invitation.idcc
        if not data["effectif"] and invitation.effectif_connu:
            data["effectif"] = invitation.effectif_connu
    
    # Complète avec PVEvent si nécessaire
    if pv_event:
        if not data["raison_sociale"]:
            data["raison_sociale"] = pv_event.raison_sociale
        if not data["ville"]:
            data["ville"] = pv_event.ville
        if not data["code_postal"]:
            data["code_postal"] = pv_event.cp
        if not data["ud"]:
            data["ud"] = pv_event.ud
        if not data["fd"]:
            data["fd"] = pv_event.fd
        if not data["idcc"]:
            data["idcc"] = pv_event.idcc
        if not data["effectif"]:
            data["effectif"] = int(pv_event.effectif_siret) if pv_event.effectif_siret else None
    
    return {"exists": True, "data": data}


@router.post("/invitation/add")
def add_pap_invitation(
    siret: str = Query(..., min_length=14, max_length=14),
    raison_sociale: str = Query(...),
    ville: str = Query(...),
    code_postal: str = Query(...),
    date_invit: str = Query(...),
    ud: str = Query(None),
    fd: str = Query(None),
    idcc: str = Query(None),
    effectif_connu: int = Query(None),
    date_reception: str = Query(None),
    date_election: str = Query(None),
    structure_saisie: str = Query(None),
    source: str = Query("Manuel"),
    db: Session = Depends(get_session),
    api_key: str = Depends(require_api_key)
):
    """
    Ajoute une nouvelle invitation PAP manuellement.

    Requiert authentification API Key.
    """
    # Valider le SIRET
    try:
        siret_clean = validate_siret(siret, raise_exception=True)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Valider et parser les dates
    try:
        date_invit_parsed = validate_date(date_invit, raise_exception=True)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=f"date_invit: {str(e)}")

    date_reception_parsed = None
    if date_reception:
        try:
            date_reception_parsed = validate_date(date_reception, raise_exception=True)
        except ValidationError as e:
            raise HTTPException(status_code=400, detail=f"date_reception: {str(e)}")

    date_election_parsed = None
    if date_election:
        try:
            date_election_parsed = validate_date(date_election, raise_exception=True)
        except ValidationError as e:
            raise HTTPException(status_code=400, detail=f"date_election: {str(e)}")

    # Enrichissement automatique FD à partir de l'IDCC
    # Principe: Toutes les entreprises avec un IDCC DOIVENT avoir une FD
    if idcc and not fd:
        enrichment_service = get_idcc_enrichment_service()
        fd = enrichment_service.enrich_fd(idcc, fd, db)

    # Crée la nouvelle invitation
    nouvelle_invitation = Invitation(
        siret=siret_clean,
        date_invit=date_invit_parsed,
        source=source,
        denomination=raison_sociale,
        commune=ville,
        code_postal=code_postal,
        ud=ud,
        fd=fd,
        idcc=idcc,
        effectif_connu=effectif_connu,
        date_reception=date_reception_parsed,
        date_election=date_election_parsed,
        structure_saisie=structure_saisie,
    )
    
    db.add(nouvelle_invitation)
    db.commit()
    db.refresh(nouvelle_invitation)
    
    return {
        "success": True,
        "message": f"Invitation PAP ajoutée pour le SIRET {siret}",
        "invitation_id": nouvelle_invitation.id
    }


@router.get("/siret/{siret}/enrichir-sirene")
async def enrichir_siret_from_api(siret: str):
    """
    Enrichit un SIRET directement depuis l'API Sirene (sans l'enregistrer).
    Utile pour pré-remplir le formulaire d'ajout PAP.
    """
    # Valider le SIRET
    try:
        siret_clean = validate_siret(siret, raise_exception=True)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        data = await enrichir_siret(siret_clean)
        
        if not data:
            raise HTTPException(status_code=404, detail=f"SIRET {siret_clean} non trouvé dans l'API Sirene")

        # Formatte les données pour le formulaire
        return {
            "success": True,
            "data": {
                "siret": siret_clean,
                "raison_sociale": data.get("denomination"),
                "ville": data.get("commune"),
                "code_postal": data.get("code_postal"),
                "adresse": data.get("adresse"),
                "effectif": None,  # L'API Sirene ne donne pas l'effectif exact, juste la tranche
                "ud": None,
                "fd": None,
                "idcc": None,
            }
        }
    except SireneAPIError as e:
        raise HTTPException(status_code=503, detail=f"Erreur API Sirene: {str(e)}")


# ============================================================================
# AUDIT LOGS
# ============================================================================

@router.get("/audit/logs")
def get_audit_logs(
    limit: int = Query(100, ge=1, le=1000, description="Nombre de logs à retourner"),
    offset: int = Query(0, ge=0, description="Offset pour pagination"),
    user_identifier: str = Query(None, description="Filtrer par utilisateur (hash API key)"),
    resource_type: str = Query(None, description="Filtrer par type de ressource"),
    success: bool = Query(None, description="Filtrer par succès/échec"),
    action: str = Query(None, description="Filtrer par action"),
    db: Session = Depends(get_session),
    api_key: str = Depends(require_api_key)
):
    """
    Récupère les audit logs pour monitoring et conformité.

    Requiert authentification API Key.

    Paramètres de filtrage :
    - user_identifier : Hash de l'API key
    - resource_type : Type de ressource (pv, invitation, siret_summary, etc.)
    - success : True pour succès uniquement, False pour échecs uniquement
    - action : Action spécifique (ex: "POST /api/ingest/pv")

    Returns:
        Liste des audit logs avec pagination
    """
    query = db.query(AuditLog).order_by(AuditLog.timestamp.desc())

    # Appliquer les filtres
    if user_identifier:
        query = query.filter(AuditLog.user_identifier == user_identifier)

    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type)

    if success is not None:
        query = query.filter(AuditLog.success == success)

    if action:
        query = query.filter(AuditLog.action.like(f"%{action}%"))

    # Compter le total pour la pagination
    total = query.count()

    # Appliquer pagination
    logs = query.offset(offset).limit(limit).all()

    # Formater la réponse
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "logs": [
            {
                "id": log.id,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                "user_identifier": log.user_identifier,
                "ip_address": log.ip_address,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "method": log.method,
                "status_code": log.status_code,
                "success": log.success,
                "request_params": log.request_params,
                "response_summary": log.response_summary,
                "error_message": log.error_message,
                "duration_ms": log.duration_ms,
            }
            for log in logs
        ]
    }


@router.get("/audit/stats")
def get_audit_stats(
    days: int = Query(7, ge=1, le=90, description="Nombre de jours à analyser"),
    db: Session = Depends(get_session),
    api_key: str = Depends(require_api_key)
):
    """
    Récupère des statistiques sur les audit logs.

    Requiert authentification API Key.

    Returns:
        Statistiques agrégées sur les derniers N jours
    """
    from datetime import timedelta

    since = datetime.now() - timedelta(days=days)

    # Nombre total d'actions
    total_actions = db.query(func.count(AuditLog.id)).filter(
        AuditLog.timestamp >= since
    ).scalar() or 0

    # Nombre de succès vs échecs
    success_count = db.query(func.count(AuditLog.id)).filter(
        AuditLog.timestamp >= since,
        AuditLog.success == True
    ).scalar() or 0

    failure_count = db.query(func.count(AuditLog.id)).filter(
        AuditLog.timestamp >= since,
        AuditLog.success == False
    ).scalar() or 0

    # Actions par type de ressource
    resource_stats = db.query(
        AuditLog.resource_type,
        func.count(AuditLog.id).label('count')
    ).filter(
        AuditLog.timestamp >= since
    ).group_by(
        AuditLog.resource_type
    ).order_by(
        func.count(AuditLog.id).desc()
    ).all()

    # Utilisateurs les plus actifs
    user_stats = db.query(
        AuditLog.user_identifier,
        func.count(AuditLog.id).label('count')
    ).filter(
        AuditLog.timestamp >= since
    ).group_by(
        AuditLog.user_identifier
    ).order_by(
        func.count(AuditLog.id).desc()
    ).limit(10).all()

    # Temps de réponse moyen
    avg_duration = db.query(
        func.avg(AuditLog.duration_ms)
    ).filter(
        AuditLog.timestamp >= since,
        AuditLog.duration_ms.isnot(None)
    ).scalar() or 0

    return {
        "period_days": days,
        "since": since.isoformat(),
        "total_actions": total_actions,
        "success_count": success_count,
        "failure_count": failure_count,
        "success_rate": round((success_count / total_actions * 100) if total_actions > 0 else 0, 2),
        "avg_duration_ms": round(avg_duration, 2),
        "by_resource_type": [
            {"resource_type": r[0], "count": r[1]}
            for r in resource_stats
        ],
        "top_users": [
            {"user_identifier": u[0], "count": u[1]}
            for u in user_stats
        ]
    }


@router.post("/invitations/update-fd-from-idcc")
async def update_fd_from_idcc(
    request: Request,
    db: Session = Depends(get_session),
    api_key: str = Depends(require_api_key)
):
    """
    Met à jour les FD (Fédérations) à partir des IDCC en utilisant le mapping idcc_to_fd_mapping.json
    """
    import json
    import os

    # Charger le mapping IDCC -> FD
    mapping_file = os.path.join(os.path.dirname(__file__), "..", "data", "idcc_to_fd_mapping.json")
    try:
        with open(mapping_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            idcc_to_fd = data.get("mapping", {})
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Fichier de mapping IDCC -> FD introuvable")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors du chargement du mapping: {str(e)}")

    if not idcc_to_fd:
        raise HTTPException(status_code=500, detail="Mapping IDCC -> FD vide")

    # Récupérer toutes les invitations
    invitations = db.query(Invitation).all()

    updated_count = 0
    skipped_count = 0
    not_found_count = 0

    for invitation in invitations:
        # Vérifier si l'invitation a un IDCC
        if not invitation.idcc:
            skipped_count += 1
            continue

        # Convertir l'IDCC en string pour la recherche
        idcc_str = str(invitation.idcc).strip()

        # Chercher la FD correspondante
        if idcc_str in idcc_to_fd:
            new_fd = idcc_to_fd[idcc_str]

            # Mettre à jour seulement si la FD est différente ou vide
            if not invitation.fd or invitation.fd == "[FD NON RENSEIGNEE]" or invitation.fd != new_fd:
                invitation.fd = new_fd
                updated_count += 1
        else:
            not_found_count += 1

    # Sauvegarder les modifications
    try:
        db.commit()
        log_admin_action(
            request,
            api_key,
            "update_fd_from_idcc",
            "invitations",
            True,
            resource_id="bulk",
            details={
                "updated": updated_count,
                "skipped": skipped_count,
                "not_found": not_found_count
            }
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur lors de la sauvegarde: {str(e)}")

    return {
        "success": True,
        "message": "Mise à jour des FD terminée",
        "total_invitations": len(invitations),
        "updated": updated_count,
        "skipped_without_idcc": skipped_count,
        "not_found_in_mapping": not_found_count,
        "mapping_size": len(idcc_to_fd)
    }
