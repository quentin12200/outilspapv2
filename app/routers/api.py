from fastapi import APIRouter, UploadFile, File, Depends, Query, HTTPException, BackgroundTasks, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, select
from typing import List
from datetime import datetime, timedelta, date
import re
import logging

from ..db import get_session, Base, engine, SessionLocal
from .. import etl
from ..models import SiretSummary, PVEvent, Invitation, User, UserActivity
from ..schemas import SiretSummaryOut
from ..services.sirene_api import enrichir_siret, SireneAPIError, rechercher_siret
from ..services.idcc_enrichment import get_idcc_enrichment_service
from ..background_tasks import task_tracker, run_build_siret_summary, run_enrichir_invitations_idcc
from ..validators import validate_siret, validate_date, validate_excel_file, ValidationError
from ..user_auth import require_admin_user, get_current_user
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
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_session),
    current_user: User = Depends(require_admin_user)
):
    """Ingestion de PV (requiert role administrateur)"""
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
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_session),
    current_user: User = Depends(require_admin_user)
):
    """Ingestion d'invitations (requiert role administrateur)"""
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
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session),
    current_user: User = Depends(require_admin_user)
):
    """
    Lance la reconstruction de la table siret_summary en arrière-plan.
    Retourne immédiatement avec un statut "en cours".
    Utiliser GET /api/build/summary/status pour suivre la progression.

    Requiert role administrateur.
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
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session),
    current_user: User = Depends(require_admin_user)
):
    """
    Lance l'enrichissement des IDCC manquants en arrière-plan via l'API SIRENE.
    Retourne immédiatement avec un statut "en cours".
    Utiliser GET /api/enrichir/idcc/status pour suivre la progression.

    Requiert role administrateur.
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
def list_sirets(q: str = Query(None), db: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    qs = db.query(SiretSummary)
    if q:
        like = f"%{q}%"
        qs = qs.filter((SiretSummary.siret.like(like)) | (SiretSummary.raison_sociale.ilike(like)))
    return qs.limit(200).all()


@router.get("/search/autocomplete")
def search_autocomplete(q: str = Query(..., min_length=2), db: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
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
def get_siret(siret: str, db: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    row = db.query(SiretSummary).get(siret)
    if not row: 
        return {}
    return row

@router.get("/siret/{siret}/timeseries")
def siret_timeseries(siret: str, db: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
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
def dashboard_stats(db: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
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
    current_user: User = Depends(require_admin_user)
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
    current_user: User = Depends(require_admin_user)
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
    current_user: User = Depends(require_admin_user)
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


@router.get("/etablissements/{siret_or_siren}")
async def get_etablissements_by_siret_or_siren(siret_or_siren: str):
    """
    Récupère tous les établissements d'une entreprise à partir d'un SIRET ou SIREN.

    Si un SIRET est fourni (14 chiffres), on extrait le SIREN et on récupère tous les établissements.
    Si un SIREN est fourni (9 chiffres), on récupère directement tous les établissements.

    Utilise l'API Pappers pour obtenir les données avec géolocalisation.
    """
    from ..services.pappers_api import pappers_api

    # Nettoyer l'input
    clean_value = siret_or_siren.strip().replace(" ", "")

    # Déterminer si c'est un SIRET ou un SIREN
    if len(clean_value) == 14 and clean_value.isdigit():
        # C'est un SIRET, extraire le SIREN (9 premiers chiffres)
        siren = clean_value[:9]
        logger.info(f"SIRET détecté: {clean_value}, extraction du SIREN: {siren}")
    elif len(clean_value) == 9 and clean_value.isdigit():
        # C'est un SIREN
        siren = clean_value
        logger.info(f"SIREN détecté: {siren}")
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Format invalide. Attendu: SIRET (14 chiffres) ou SIREN (9 chiffres). Reçu: {len(clean_value)} chiffres"
        )

    # Appeler l'API Pappers
    result = await pappers_api.get_etablissements_by_siren(siren)

    if not result.get("success"):
        error_msg = result.get("error", "Erreur inconnue")
        if "non trouvé" in error_msg.lower():
            raise HTTPException(status_code=404, detail=error_msg)
        else:
            raise HTTPException(status_code=503, detail=f"Erreur API Pappers: {error_msg}")

    return result


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
    current_user: User = Depends(require_admin_user)
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
    current_user: User = Depends(require_admin_user)
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
    current_user: User = Depends(require_admin_user)
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
            current_user.email,
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


@router.get("/rapport-ia-pap")
def generer_rapport_ia_pap(db: Session = Depends(get_session)):
    """
    Génère un rapport complet de la situation PAP prioritaire.

    Priorité 1: Boîtes avec élection dans les 90 prochains jours
    Priorité 2: Entreprises avec élection dans l'année à venir

    Pour chaque entreprise, retourne:
    - SIRET
    - Raison sociale
    - Nombre d'inscrits
    - Implantation syndicale (organisations présentes)
    - Nombre de collèges (calculé depuis les PV si non disponible dans siret_summary)
    - Nombre de PV (nombre de procès-verbaux enregistrés)
    - Nombre d'établissements (basé sur le nombre de PV distincts)
    - Département
    - Ville
    - Carence (oui/non)
    - Invitations PAP reçues
    - Enjeux identifiés
    - Date de la prochaine élection
    """

    def _to_number(value):
        """Convertit une valeur en nombre"""
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
        """Parse une date depuis différents formats"""
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

    def _analyser_implantations(row):
        """Analyse les implantations syndicales d'un SIRET"""
        orgs = []

        # Méthode 1 : Utiliser les colonnes cgt_implantee, cfdt_implantee, etc. (plus fiables)
        # Méthode 2 : Vérifier pres_siret_* (peut être vide)
        # Méthode 3 : Vérifier si voix > 0 dans les cycles

        # CGT
        if (row.cgt_implantee or
            row.pres_siret_cgt or
            (row.cgt_voix_c4 and _to_number(row.cgt_voix_c4) > 0) or
            (row.cgt_voix_c3 and _to_number(row.cgt_voix_c3) > 0)):
            orgs.append("CGT")

        # CFDT
        if (row.pres_siret_cfdt or
            (row.cfdt_voix_c4 and _to_number(row.cfdt_voix_c4) > 0) or
            (row.cfdt_voix_c3 and _to_number(row.cfdt_voix_c3) > 0)):
            orgs.append("CFDT")

        # FO
        if (row.pres_siret_fo or
            (row.fo_voix_c4 and _to_number(row.fo_voix_c4) > 0) or
            (row.fo_voix_c3 and _to_number(row.fo_voix_c3) > 0)):
            orgs.append("FO")

        # CFTC
        if (row.pres_siret_cftc or
            (row.cftc_voix_c4 and _to_number(row.cftc_voix_c4) > 0) or
            (row.cftc_voix_c3 and _to_number(row.cftc_voix_c3) > 0)):
            orgs.append("CFTC")

        # CGC
        if (row.pres_siret_cgc or
            (row.cgc_voix_c4 and _to_number(row.cgc_voix_c4) > 0) or
            (row.cgc_voix_c3 and _to_number(row.cgc_voix_c3) > 0)):
            orgs.append("CGC")

        # UNSA
        if (row.pres_siret_unsa or
            (row.unsa_voix_c4 and _to_number(row.unsa_voix_c4) > 0) or
            (row.unsa_voix_c3 and _to_number(row.unsa_voix_c3) > 0)):
            orgs.append("UNSA")

        # SUD
        if (row.pres_siret_sud or
            (row.sud_voix_c4 and _to_number(row.sud_voix_c4) > 0) or
            (row.sud_voix_c3 and _to_number(row.sud_voix_c3) > 0)):
            orgs.append("SUD")

        # AUTRE
        if row.pres_siret_autre:
            orgs.append("AUTRE")

        return orgs if orgs else ["Aucune implantation identifiée"]

    def _analyser_enjeux(siret, inscrits, has_invitation, carence, nb_colleges, orgs, cgt_voix=None, votants=None):
        """Analyse les enjeux d'une entreprise"""
        enjeux = []

        # Enjeux liés à la taille
        if inscrits >= 1000:
            enjeux.append(f"🎯 Très forte audience ({int(inscrits)} inscrits)")
        elif inscrits >= 500:
            enjeux.append(f"📊 Forte audience ({int(inscrits)} inscrits)")

        # Enjeux liés à l'implantation CGT
        if "CGT" in orgs:
            if inscrits >= 1000:
                enjeux.append("✅ CGT IMPLANTÉE - RENFORCEMENT PRIORITAIRE (forte audience)")
            elif inscrits >= 500:
                enjeux.append("✅ CGT implantée - Consolidation recommandée")
            else:
                enjeux.append("✅ CGT implantée - Maintien position")

            # Ajouter le score CGT si disponible (basé sur les votants)
            if cgt_voix and votants and votants > 0:
                pct_cgt = (cgt_voix / votants) * 100
                if pct_cgt >= 50:
                    enjeux.append(f"💪 CGT majoritaire ({pct_cgt:.1f}%)")
                elif pct_cgt >= 30:
                    enjeux.append(f"💪 CGT bien positionnée ({pct_cgt:.1f}%)")
                else:
                    enjeux.append(f"📈 CGT à renforcer ({pct_cgt:.1f}%)")
        else:
            if inscrits >= 1000:
                enjeux.append("⚠️ CGT NON IMPLANTÉE - OPPORTUNITÉ MAJEURE (forte audience)")
            elif inscrits >= 500:
                enjeux.append("⚠️ CGT NON implantée - Priorité d'intervention")
            else:
                enjeux.append("⚠️ CGT non implantée - Prospection")

        # Enjeux liés à la carence
        if carence:
            enjeux.append("🔴 CARENCE - Opportunité de (re)conquête")

        # Enjeux liés à l'invitation PAP
        if has_invitation:
            enjeux.append("✓ Invitation PAP reçue (C5)")
        else:
            enjeux.append("ℹ️ Pas d'invitation PAP détectée")

        # Enjeux liés aux collèges
        if nb_colleges and nb_colleges > 1:
            enjeux.append(f"🏢 Pluralité de collèges ({int(nb_colleges)})")

        # Situation syndicale globale
        if len(orgs) == 1 and orgs[0] == "Aucune implantation identifiée":
            enjeux.append("⚠️ Aucune organisation syndicale - Terrain vierge")
        elif len(orgs) > 4:
            enjeux.append(f"⚔️ Forte concurrence syndicale ({len(orgs)} organisations)")

        return enjeux

    def _calculer_score_priorite(entreprise):
        """Calcule un score de priorité pour trier les entreprises"""
        score = 0

        # CRITÈRE 1 : CGT déjà implantée avec forte audience = PRIORITÉ ABSOLUE
        is_cgt = "CGT" in entreprise.get("implantations_syndicales", [])
        inscrits = entreprise.get("inscrits", 0)

        if is_cgt and inscrits >= 1000:
            score += 10000  # Priorité maximale : renforcement CGT forte audience
        elif is_cgt and inscrits >= 500:
            score += 5000   # Haute priorité : renforcement CGT audience moyenne
        elif is_cgt:
            score += 2000   # Priorité : maintien position CGT

        # CRITÈRE 2 : Forte audience sans CGT = opportunité
        if not is_cgt and inscrits >= 1000:
            score += 3000   # Opportunité majeure d'implantation
        elif not is_cgt and inscrits >= 500:
            score += 1000   # Opportunité d'implantation

        # CRITÈRE 3 : Carence (opportunité de reconquête)
        if entreprise.get("carence"):
            score += 500

        # CRITÈRE 4 : Urgence temporelle (jours restants)
        jours = entreprise.get("jours_restants")
        if jours is not None:
            if jours <= 30:
                score += 300
            elif jours <= 60:
                score += 200
            elif jours <= 90:
                score += 100

        # CRITÈRE 5 : Nombre d'inscrits (pondération)
        score += inscrits * 0.1

        return score

    # Dates de référence
    today = date.today()
    date_90_jours = today + timedelta(days=90)
    date_1_an = today + timedelta(days=365)

    # Récupère tous les PV avec date_prochain_scrutin
    pv_elections = db.query(
        PVEvent.siret,
        PVEvent.date_prochain_scrutin,
        PVEvent.effectif_siret,
        PVEvent.inscrits
    ).filter(
        PVEvent.date_prochain_scrutin.isnot(None)
    ).all()

    # Récupère les invitations avec date_election
    invitations_elections = db.query(
        Invitation.siret,
        Invitation.date_election,
        Invitation.effectif_connu
    ).filter(
        Invitation.date_election.isnot(None)
    ).all()

    # Fonction pour normaliser les SIRET (enlever espaces, tirets)
    def normalize_siret(siret):
        if not siret:
            return None
        return ''.join(c for c in str(siret) if c.isdigit())

    # Map des SIRET avec leur date d'élection (prend la plus proche)
    siret_elections = {}

    # Ajoute les dates depuis PVEvent
    for siret, date_election, effectif_siret, inscrits in pv_elections:
        parsed_date = _parse_date_value(date_election)
        if not parsed_date or parsed_date < today:
            continue

        siret_norm = normalize_siret(siret)
        if not siret_norm:
            continue

        if siret_norm not in siret_elections or parsed_date < siret_elections[siret_norm]['date']:
            siret_elections[siret_norm] = {
                'date': parsed_date,
                'effectif': _to_number(effectif_siret) or _to_number(inscrits),
                'source': 'pv'
            }

    # Ajoute les dates depuis Invitation (si plus proche)
    for siret, date_election, effectif in invitations_elections:
        parsed_date = _parse_date_value(date_election)
        if not parsed_date or parsed_date < today:
            continue

        siret_norm = normalize_siret(siret)
        if not siret_norm:
            continue

        if siret_norm not in siret_elections or parsed_date < siret_elections[siret_norm]['date']:
            siret_elections[siret_norm] = {
                'date': parsed_date,
                'effectif': _to_number(effectif),
                'source': 'invitation'
            }

    # Récupère les invitations PAP pour voir quels SIRET ont reçu une invitation
    invitations_map = {}
    invitations = db.query(Invitation.siret, Invitation.date_invit).all()
    for siret, date_invit in invitations:
        siret_norm = normalize_siret(siret)
        if siret_norm:
            if siret_norm not in invitations_map:
                invitations_map[siret_norm] = []
            invitations_map[siret_norm].append(date_invit)

    # Calcule le nombre de PV et de collèges par SIRET depuis la table Tous_PV
    pv_stats_map = {}
    pv_stats = db.query(
        PVEvent.siret,
        func.count(PVEvent.id).label('nb_pv'),
        func.count(func.distinct(PVEvent.deno_coll)).label('nb_colleges_distinct')
    ).group_by(PVEvent.siret).all()

    for siret, nb_pv, nb_colleges in pv_stats:
        siret_norm = normalize_siret(siret)
        if siret_norm:
            pv_stats_map[siret_norm] = {
                'nb_pv': nb_pv,
                'nb_colleges': nb_colleges
            }

    logger.info(f"📊 Stats PV: {len(pv_stats_map)} SIRET avec PV trouvés")

    # Debug: afficher quelques exemples de SIRET dans PVEvent
    if pv_stats_map:
        premiers_sirets = list(pv_stats_map.keys())[:5]
        logger.info(f"🔍 Exemples de SIRET dans PVEvent: {premiers_sirets}")
        # Chercher RATP dans les SIRET
        ratp_sirets = [s for s in pv_stats_map.keys() if s and '77566343' in str(s)]
        if ratp_sirets:
            logger.info(f"🔍 SIRET RATP trouvés dans PVEvent: {ratp_sirets}")
            for rs in ratp_sirets[:3]:
                logger.info(f"  - {rs}: {pv_stats_map[rs]}")
        else:
            logger.warning(f"⚠️ Aucun SIRET RATP (commençant par 77566343) trouvé dans PVEvent")

    # Debug: afficher un exemple pour RATP
    ratp_siret = "77566343800494"
    if ratp_siret in pv_stats_map:
        logger.info(f"🔍 RATP {ratp_siret}: {pv_stats_map[ratp_siret]}")
    else:
        logger.warning(f"⚠️ RATP {ratp_siret} PAS trouvé dans pv_stats_map")

    # Récupère la liste des noms de collèges distincts par SIRET
    colleges_map = {}
    colleges_query = db.query(
        PVEvent.siret,
        PVEvent.deno_coll
    ).filter(
        PVEvent.siret.isnot(None),
        PVEvent.deno_coll.isnot(None),
        PVEvent.deno_coll != ''
    ).all()

    for siret, deno_coll in colleges_query:
        siret_norm = normalize_siret(siret)
        if siret_norm:
            if siret_norm not in colleges_map:
                colleges_map[siret_norm] = []
            # Ajouter seulement si pas déjà dans la liste (pour avoir des collèges uniques)
            if deno_coll and deno_coll.strip() and deno_coll not in colleges_map[siret_norm]:
                colleges_map[siret_norm].append(deno_coll)

    logger.info(f"📋 Collèges: {len(colleges_map)} SIRET avec collèges trouvés")
    # Debug: afficher un exemple pour RATP
    ratp_siret = "77566343800494"
    if ratp_siret in colleges_map:
        logger.info(f"🔍 RATP {ratp_siret} collèges: {colleges_map[ratp_siret]}")
    else:
        logger.warning(f"⚠️ RATP {ratp_siret} PAS trouvé dans colleges_map")

    # Filtre les SIRET qui ont une élection dans les délais
    sirets_priorite_1 = {  # Élections dans les 90 jours
        siret for siret, data in siret_elections.items()
        if data['date'] <= date_90_jours
    }

    sirets_priorite_2 = {  # Élections dans l'année (mais pas dans les 90 jours)
        siret for siret, data in siret_elections.items()
        if data['date'] > date_90_jours and data['date'] <= date_1_an
    }

    # Récupère les données complètes depuis SiretSummary
    all_sirets_p1 = []
    all_sirets_p2 = []

    if sirets_priorite_1:
        all_sirets_p1 = db.query(SiretSummary).filter(
            SiretSummary.siret.in_(sirets_priorite_1)
        ).all()

    if sirets_priorite_2:
        all_sirets_p2 = db.query(SiretSummary).filter(
            SiretSummary.siret.in_(sirets_priorite_2)
        ).all()

    # Sépare en deux groupes
    priorite_1 = []  # Élections dans les 90 jours
    priorite_2 = []  # Élections dans l'année

    def _traiter_siret(row, election_data):
        """Traite un SIRET et retourne l'objet entreprise"""
        # Détermine l'effectif (priorité: inscrits_c4 > inscrits_c3 > effectif_siret)
        effectif = None
        if row.inscrits_c4:
            effectif = _to_number(row.inscrits_c4)
        elif row.inscrits_c3:
            effectif = _to_number(row.inscrits_c3)
        elif row.effectif_siret:
            effectif = _to_number(row.effectif_siret)

        # Utilise l'effectif depuis election_data si disponible
        if not effectif and election_data.get('effectif'):
            effectif = election_data['effectif']

        if not effectif:
            return None

        # Filtre : Exclure les entreprises de moins de 50 salariés (non prioritaires)
        if effectif < 50:
            return None

        # Détermine la carence
        carence = row.carence_c4 or row.carence_c3 or False

        # Analyse les implantations syndicales
        orgs = _analyser_implantations(row)

        # Normaliser le SIRET pour le matching avec PVEvent et invitations
        siret_norm = normalize_siret(row.siret)

        # Vérifie si le SIRET a une invitation PAP
        has_invitation = siret_norm in invitations_map if siret_norm else False
        invitations_dates = invitations_map.get(siret_norm, []) if siret_norm else []

        # Récupère les stats PV pour ce SIRET (avec SIRET normalisé)
        pv_stats = pv_stats_map.get(siret_norm, {'nb_pv': 0, 'nb_colleges': 0})
        nb_pv = pv_stats.get('nb_pv', 0)

        # Récupère la liste des collèges pour ce SIRET (avec SIRET normalisé)
        colleges_list = colleges_map.get(siret_norm, [])

        # Debug pour RATP
        if row.siret == "77566343800494":
            logger.info(f"🔍 RATP dans _traiter_siret: siret_norm={siret_norm}, nb_pv={nb_pv}, colleges={colleges_list}")

        # Détermine le nombre de collèges
        # Note: Il n'y a pas de nb_colleges_c4/c3 dans SiretSummary
        nb_colleges = 0
        if row.nb_college_siret and _to_number(row.nb_college_siret):
            nb_colleges = int(_to_number(row.nb_college_siret))
        elif pv_stats.get('nb_colleges'):
            nb_colleges = pv_stats.get('nb_colleges')

        # Récupère les voix CGT et votants pour le calcul du pourcentage
        cgt_voix = _to_number(row.cgt_voix_c4) or _to_number(row.cgt_voix_c3)
        votants = _to_number(row.votants_c4) or _to_number(row.votants_c3)

        # Récupère les voix de TOUTES les organisations
        voix_organisations = {
            "CGT": cgt_voix,
            "CFDT": _to_number(row.cfdt_voix_c4) or _to_number(row.cfdt_voix_c3),
            "FO": _to_number(row.fo_voix_c4) or _to_number(row.fo_voix_c3),
            "CFTC": _to_number(row.cftc_voix_c4) or _to_number(row.cftc_voix_c3),
            "CGC": _to_number(row.cgc_voix_c4) or _to_number(row.cgc_voix_c3),
            "UNSA": _to_number(row.unsa_voix_c4) or _to_number(row.unsa_voix_c3),
            "SUD": _to_number(row.sud_voix_c4) or _to_number(row.sud_voix_c3),
        }
        # Filtrer les voix nulles
        voix_organisations = {k: int(v) for k, v in voix_organisations.items() if v and v > 0}

        # Calcul du SVE (Suffrages Valablement Exprimés) = somme de toutes les voix
        # Note: Il n'y a pas de colonne sve_c4/c3 dans SiretSummary
        sve = sum(voix_organisations.values()) if voix_organisations else 0

        # Analyse les enjeux
        enjeux = _analyser_enjeux(
            row.siret,
            effectif,
            has_invitation,
            carence,
            nb_colleges,
            orgs,
            cgt_voix,
            votants
        )

        # Date de l'élection
        date_election = election_data.get('date')
        jours_restants = (date_election - today).days if date_election else None

        # Construction de l'objet entreprise
        entreprise = {
            "siret": row.siret,
            "raison_sociale": row.raison_sociale or "Non renseignée",
            "inscrits": int(effectif),
            "departement": row.dep or "Non renseigné",
            "ville": row.ville or "Non renseignée",
            "code_postal": row.cp or "Non renseigné",
            "region": row.region or "Non renseignée",
            "nb_colleges": nb_colleges,
            "colleges": colleges_list,  # Liste des noms de collèges
            "nb_pv": nb_pv,
            "nb_etablissements": nb_pv,  # Le nombre d'établissements = nombre de PV distincts
            "carence": carence,
            "implantations_syndicales": orgs,
            "invitations_pap": [
                d.strftime("%d/%m/%Y") if isinstance(d, date) else str(d)
                for d in invitations_dates
            ] if invitations_dates else [],
            "enjeux": enjeux,
            "fd": row.fd_c4 or row.fd_c3 or "Non renseignée",
            "ud": row.ud_c4 or row.ud_c3 or "Non renseigné",
            "idcc": row.idcc or "Non renseigné",
            "date_election": date_election.strftime("%d/%m/%Y") if date_election else "Non renseignée",
            "jours_restants": jours_restants,
            "sve": int(sve) if sve else 0,
            "votants": int(votants) if votants else 0,
            "voix_organisations": voix_organisations,
        }

        return entreprise

    # Traite les SIRET de priorité 1 (90 jours)
    for row in all_sirets_p1:
        siret_norm = normalize_siret(row.siret)
        election_data = siret_elections.get(siret_norm, {})
        if not election_data:
            # Fallback: essayer avec le SIRET non normalisé
            election_data = siret_elections.get(row.siret, {})

        # Debug pour RATP
        if row.siret == "77566343800494":
            logger.info(f"🔍 RATP P1: siret_norm={siret_norm}, election_data={election_data}")

        entreprise = _traiter_siret(row, election_data)
        if entreprise:
            priorite_1.append(entreprise)

    # Traite les SIRET de priorité 2 (1 an)
    for row in all_sirets_p2:
        siret_norm = normalize_siret(row.siret)
        election_data = siret_elections.get(siret_norm, {})
        if not election_data:
            # Fallback: essayer avec le SIRET non normalisé
            election_data = siret_elections.get(row.siret, {})

        entreprise = _traiter_siret(row, election_data)
        if entreprise:
            priorite_2.append(entreprise)

    # Tri par score de priorité (décroissant) - met en avant :
    # 1. CGT implantée + forte audience (renforcement)
    # 2. Forte audience sans CGT (implantation)
    # 3. Urgence temporelle
    priorite_1.sort(key=lambda x: -_calculer_score_priorite(x))
    priorite_2.sort(key=lambda x: -_calculer_score_priorite(x))

    # Statistiques globales
    stats = {
        "total_priorite_1": len(priorite_1),
        "total_priorite_2": len(priorite_2),
        "total_inscrits_p1": sum(e["inscrits"] for e in priorite_1),
        "total_inscrits_p2": sum(e["inscrits"] for e in priorite_2),
        "cgt_implantee_p1": sum(1 for e in priorite_1 if "CGT" in e["implantations_syndicales"]),
        "cgt_implantee_p2": sum(1 for e in priorite_2 if "CGT" in e["implantations_syndicales"]),
        "carence_p1": sum(1 for e in priorite_1 if e["carence"]),
        "carence_p2": sum(1 for e in priorite_2 if e["carence"]),
        "avec_invitation_p1": sum(1 for e in priorite_1 if e["invitations_pap"]),
        "avec_invitation_p2": sum(1 for e in priorite_2 if e["invitations_pap"]),
    }

    return {
        "success": True,
        "date_generation": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "date_reference": today.strftime("%d/%m/%Y"),
        "date_limite_p1": date_90_jours.strftime("%d/%m/%Y"),
        "date_limite_p2": date_1_an.strftime("%d/%m/%Y"),
        "statistiques": stats,
        "priorite_1": {
            "titre": "Priorité 1: Boîtes avec élection dans les 90 jours",
            "description": f"Élections du {today.strftime('%d/%m/%Y')} au {date_90_jours.strftime('%d/%m/%Y')} - Intervention urgente",
            "entreprises": priorite_1
        },
        "priorite_2": {
            "titre": "Priorité 2: Entreprises avec élection dans l'année",
            "description": f"Élections du {date_90_jours.strftime('%d/%m/%Y')} au {date_1_an.strftime('%d/%m/%Y')} - Planification à moyen terme",
            "entreprises": priorite_2
        }
    }


@router.get("/pv/siret/{siret}")
async def get_pv_by_siret(
    siret: str,
    db: Session = Depends(get_session)
):
    """
    Récupère tous les PV (procès-verbaux) associés à un SIRET.
    Retourne les résultats électoraux : inscrits, voix par organisation, etc.

    Args:
        siret: Numéro SIRET (14 chiffres)

    Returns:
        Liste des PV avec résultats électoraux détaillés
    """
    try:
        # Nettoyer le SIRET
        siret_clean = ''.join(c for c in siret if c.isdigit())

        if len(siret_clean) != 14:
            raise HTTPException(status_code=400, detail="SIRET invalide (doit contenir 14 chiffres)")

        # Récupérer tous les PV pour ce SIRET
        pv_list = db.query(PVEvent).filter(PVEvent.siret == siret_clean).all()

        if not pv_list:
            return {
                "success": True,
                "siret": siret_clean,
                "count": 0,
                "pv": []
            }

        # Formatter les résultats
        formatted_pv = []
        for pv in pv_list:
            # Calculer les organisations présentes avec leurs voix
            organisations = []

            org_map = [
                ("CGT", pv.cgt_voix, pv.pres_pv_cgt),
                ("CFDT", pv.cfdt_voix, pv.pres_pv_cfdt),
                ("FO", pv.fo_voix, pv.pres_pv_fo),
                ("CFTC", pv.cftc_voix, pv.pres_pv_cftc),
                ("CGC", pv.cgc_voix, pv.pres_pv_cgc),
                ("UNSA", pv.unsa_voix, pv.pres_pv_unsa),
                ("SUD/Solidaires", pv.sud_voix, pv.pres_pv_sud),
                ("Autre", pv.autre_voix, pv.pres_pv_autre),
            ]

            total_voix = 0
            for nom, voix, presence in org_map:
                if voix and voix > 0:
                    total_voix += voix
                    organisations.append({
                        "nom": nom,
                        "voix": voix,
                        "presence": presence or "OUI"
                    })

            # Calculer les pourcentages
            for org in organisations:
                if total_voix > 0:
                    org["pourcentage"] = round((org["voix"] / total_voix) * 100, 2)
                else:
                    org["pourcentage"] = 0

            # Trier par nombre de voix décroissant
            organisations.sort(key=lambda x: x["voix"], reverse=True)

            formatted_pv.append({
                "id_pv": pv.id_pv,
                "date_scrutin": pv.date_pv,
                "cycle": pv.cycle,
                "institution": pv.institution,
                "raison_sociale": pv.raison_sociale,
                "ville": pv.ville,
                "cp": pv.cp,
                "ud": pv.ud,
                "region": pv.region,
                "inscrits": pv.inscrits,
                "votants": pv.votants,
                "sve": pv.sve,
                "taux_participation": pv.tx_participation_pv,
                "organisations": organisations,
                "total_voix": total_voix,
                "effectif_siret": pv.effectif_siret,
                "idcc": pv.idcc
            })

        # Trier par date décroissante (plus récent en premier)
        formatted_pv.sort(key=lambda x: x["date_scrutin"] or "", reverse=True)

        logger.info(f"✅ {len(formatted_pv)} PV trouvés pour SIRET {siret_clean}")

        return {
            "success": True,
            "siret": siret_clean,
            "count": len(formatted_pv),
            "pv": formatted_pv
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des PV pour SIRET {siret}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")


async def _get_pv_from_tous_pv(siren: str, db: Session):
    """
    Fonction fallback qui interroge directement la table Tous_PV quand siret_summary est vide.
    Retourne le même format que get_pv_by_siren.
    """
    # Récupérer tous les PV de ce SIREN
    pv_list = db.query(PVEvent).filter(PVEvent.siren == siren).all()

    if not pv_list:
        return {
            "success": True,
            "siren": siren,
            "count": 0,
            "pv": [],
            "source": "Tous_PV"
        }

    formatted_results = []

    for pv in pv_list:
        # Calculer les organisations et leurs voix
        organisations = []

        # Utiliser getattr pour éviter les AttributeError
        sud_voix_value = getattr(pv, 'sud_voix', None) or getattr(pv, 'solidaire_voix', None)

        # NOTE: Les colonnes siege_* n'existent pas dans toutes les bases de données
        # On les met à None pour éviter les erreurs SQL lors du fallback
        org_map = [
            ("CGT", getattr(pv, 'cgt_voix', None), None),
            ("CFDT", getattr(pv, 'cfdt_voix', None), None),
            ("FO", getattr(pv, 'fo_voix', None), None),
            ("CFTC", getattr(pv, 'cftc_voix', None), None),
            ("CGC", getattr(pv, 'cgc_voix', None), None),
            ("UNSA", getattr(pv, 'unsa_voix', None), None),
            ("SUD/Solidaires", sud_voix_value, None),
            ("Autre", getattr(pv, 'autre_voix', None), None),
        ]

        total_voix = 0
        for nom, voix, sieges in org_map:
            if voix and voix > 0:
                total_voix += voix
                organisations.append({
                    "nom": nom,
                    "voix": int(voix),
                    "sieges": int(sieges) if sieges else 0
                })

        # Calculer les pourcentages
        for org in organisations:
            if total_voix > 0:
                org["pourcentage"] = round((org["voix"] / total_voix) * 100, 2)
            else:
                org["pourcentage"] = 0

        # Trier par nombre de voix décroissant
        organisations.sort(key=lambda x: x["voix"], reverse=True)

        # Calculer taux de participation
        taux_participation = None
        inscrits = getattr(pv, 'inscrits', None)
        votants = getattr(pv, 'votants', None)
        if inscrits and inscrits > 0 and votants:
            taux_participation = round((votants / inscrits) * 100, 2)

        # Déterminer si c'est une carence
        carence = False
        institution = getattr(pv, 'institution', None)
        votants = getattr(pv, 'votants', None)
        if institution and "car" in str(institution).lower():
            carence = True
        elif not votants or votants <= 0:
            carence = True

        # Parser la date
        date_scrutin = None
        date_pv = getattr(pv, 'date_pv', None)
        if date_pv:
            try:
                if isinstance(date_pv, str):
                    date_scrutin = datetime.strptime(date_pv, "%Y-%m-%d").strftime("%Y-%m-%d")
                else:
                    date_scrutin = date_pv.strftime("%Y-%m-%d") if hasattr(date_pv, 'strftime') else str(date_pv)
            except Exception as e:
                logger.warning(f"Erreur parsing date {date_pv}: {e}")
                date_scrutin = str(date_pv) if date_pv else None

        formatted_results.append({
            "siret": getattr(pv, 'siret', None),
            "cycle": getattr(pv, 'cycle', None) or "N/A",
            "date_scrutin": date_scrutin,
            "raison_sociale": getattr(pv, 'raison_sociale', None),
            "ville": getattr(pv, 'ville', None),
            "cp": getattr(pv, 'cp', None),
            "ud": getattr(pv, 'ud', None),
            "fd": getattr(pv, 'fd', None),
            "region": getattr(pv, 'region', None),
            "inscrits": int(getattr(pv, 'inscrits', 0)) if getattr(pv, 'inscrits', None) else 0,
            "votants": int(getattr(pv, 'votants', 0)) if getattr(pv, 'votants', None) else 0,
            "taux_participation": taux_participation,
            "carence": carence,
            "organisations": organisations,
            "total_voix": total_voix,
            "effectif_siret": int(getattr(pv, 'effectif_siret', 0)) if getattr(pv, 'effectif_siret', None) else None,
            "effectif_siren": int(getattr(pv, 'effectif_siren', 0)) if getattr(pv, 'effectif_siren', None) else None,
            "idcc": getattr(pv, 'idcc', None),
            "nb_colleges": int(getattr(pv, 'nb_college_siret', 0)) if getattr(pv, 'nb_college_siret', None) else None
        })

    # Trier par date décroissante
    formatted_results.sort(key=lambda x: x["date_scrutin"] or "", reverse=True)

    logger.info(f"✅ {len(formatted_results)} résultats électoraux trouvés pour SIREN {siren} depuis Tous_PV (fallback)")

    return {
        "success": True,
        "siren": siren,
        "count": len(formatted_results),
        "pv": formatted_results,
        "source": "Tous_PV"
    }


@router.get("/pv/siren/{siren}")
async def get_pv_by_siren(
    siren: str,
    db: Session = Depends(get_session)
):
    """
    Récupère tous les résultats électoraux associés à un SIREN (entreprise).
    Utilise la table siret_summary (calendrier) qui contient les données agrégées.
    Si siret_summary est vide, fallback vers la table Tous_PV directement.
    Retourne les résultats électoraux : inscrits, voix par organisation, sièges, etc.

    Args:
        siren: Numéro SIREN (9 chiffres)

    Returns:
        Liste des résultats électoraux avec données agrégées (Cycle 3 et Cycle 4)
    """
    try:
        # Nettoyer le SIREN
        siren_clean = ''.join(c for c in siren if c.isdigit())

        if len(siren_clean) != 9:
            raise HTTPException(status_code=400, detail="SIREN invalide (doit contenir 9 chiffres)")

        # Récupérer tous les SIRETs de cette entreprise depuis siret_summary
        sirets_list = db.query(SiretSummary).filter(SiretSummary.siren == siren_clean).all()

        # FALLBACK: Si siret_summary est vide, chercher dans Tous_PV directement
        if not sirets_list:
            logger.info(f"⚠️  SIREN {siren_clean} non trouvé dans siret_summary, fallback vers Tous_PV")
            return await _get_pv_from_tous_pv(siren_clean, db)

        # Formatter les résultats
        formatted_results = []

        for siret_data in sirets_list:
            # Traiter Cycle 3 si présent
            if siret_data.date_pv_c3:
                organisations_c3 = []

                org_map_c3 = [
                    ("CGT", siret_data.cgt_voix_c3, siret_data.cgt_siege_c3),
                    ("CFDT", siret_data.cfdt_voix_c3, siret_data.cfdt_siege_c3),
                    ("FO", siret_data.fo_voix_c3, siret_data.fo_siege_c3),
                    ("CFTC", siret_data.cftc_voix_c3, siret_data.cftc_siege_c3),
                    ("CGC", siret_data.cgc_voix_c3, siret_data.cgc_siege_c3),
                    ("UNSA", siret_data.unsa_voix_c3, siret_data.unsa_siege_c3),
                    ("SUD/Solidaires", siret_data.sud_voix_c3 or siret_data.solidaire_voix_c3, siret_data.sud_siege_c3),
                    ("Autre", siret_data.autre_voix_c3, siret_data.autre_siege_c3),
                ]

                total_voix_c3 = 0
                for nom, voix, sieges in org_map_c3:
                    if voix and voix > 0:
                        total_voix_c3 += voix
                        organisations_c3.append({
                            "nom": nom,
                            "voix": voix,
                            "sieges": sieges or 0
                        })

                # Calculer les pourcentages
                for org in organisations_c3:
                    if total_voix_c3 > 0:
                        org["pourcentage"] = round((org["voix"] / total_voix_c3) * 100, 2)
                    else:
                        org["pourcentage"] = 0

                # Trier par nombre de voix décroissant
                organisations_c3.sort(key=lambda x: x["voix"], reverse=True)

                # Calculer taux de participation
                taux_participation_c3 = None
                if siret_data.inscrits_c3 and siret_data.inscrits_c3 > 0 and siret_data.votants_c3:
                    taux_participation_c3 = round((siret_data.votants_c3 / siret_data.inscrits_c3) * 100, 2)

                formatted_results.append({
                    "siret": siret_data.siret,
                    "cycle": "Cycle 3",
                    "date_scrutin": siret_data.date_pv_c3.strftime("%Y-%m-%d") if siret_data.date_pv_c3 else None,
                    "raison_sociale": siret_data.raison_sociale,
                    "ville": siret_data.ville,
                    "cp": siret_data.cp,
                    "ud": siret_data.ud_c3,
                    "fd": siret_data.fd_c3,
                    "region": siret_data.region,
                    "inscrits": siret_data.inscrits_c3,
                    "votants": siret_data.votants_c3,
                    "taux_participation": taux_participation_c3,
                    "carence": siret_data.carence_c3,
                    "organisations": organisations_c3,
                    "total_voix": total_voix_c3,
                    "effectif_siret": siret_data.effectif_siret,
                    "effectif_siren": siret_data.effectif_siren,
                    "idcc": siret_data.idcc,
                    "nb_colleges": siret_data.nb_college_siret
                })

            # Traiter Cycle 4 si présent
            if siret_data.date_pv_c4:
                organisations_c4 = []

                org_map_c4 = [
                    ("CGT", siret_data.cgt_voix_c4, siret_data.cgt_siege_c4),
                    ("CFDT", siret_data.cfdt_voix_c4, siret_data.cfdt_siege_c4),
                    ("FO", siret_data.fo_voix_c4, siret_data.fo_siege_c4),
                    ("CFTC", siret_data.cftc_voix_c4, siret_data.cftc_siege_c4),
                    ("CGC", siret_data.cgc_voix_c4, siret_data.cgc_siege_c4),
                    ("UNSA", siret_data.unsa_voix_c4, siret_data.unsa_siege_c4),
                    ("SUD/Solidaires", siret_data.sud_voix_c4 or siret_data.solidaire_voix_c4, siret_data.sud_siege_c4),
                    ("Autre", siret_data.autre_voix_c4, siret_data.autre_siege_c4),
                ]

                total_voix_c4 = 0
                for nom, voix, sieges in org_map_c4:
                    if voix and voix > 0:
                        total_voix_c4 += voix
                        organisations_c4.append({
                            "nom": nom,
                            "voix": voix,
                            "sieges": sieges or 0
                        })

                # Calculer les pourcentages
                for org in organisations_c4:
                    if total_voix_c4 > 0:
                        org["pourcentage"] = round((org["voix"] / total_voix_c4) * 100, 2)
                    else:
                        org["pourcentage"] = 0

                # Trier par nombre de voix décroissant
                organisations_c4.sort(key=lambda x: x["voix"], reverse=True)

                # Calculer taux de participation
                taux_participation_c4 = None
                if siret_data.inscrits_c4 and siret_data.inscrits_c4 > 0 and siret_data.votants_c4:
                    taux_participation_c4 = round((siret_data.votants_c4 / siret_data.inscrits_c4) * 100, 2)

                formatted_results.append({
                    "siret": siret_data.siret,
                    "cycle": "Cycle 4",
                    "date_scrutin": siret_data.date_pv_c4.strftime("%Y-%m-%d") if siret_data.date_pv_c4 else None,
                    "raison_sociale": siret_data.raison_sociale,
                    "ville": siret_data.ville,
                    "cp": siret_data.cp,
                    "ud": siret_data.ud_c4,
                    "fd": siret_data.fd_c4,
                    "region": siret_data.region,
                    "inscrits": siret_data.inscrits_c4,
                    "votants": siret_data.votants_c4,
                    "taux_participation": taux_participation_c4,
                    "carence": siret_data.carence_c4,
                    "organisations": organisations_c4,
                    "total_voix": total_voix_c4,
                    "effectif_siret": siret_data.effectif_siret,
                    "effectif_siren": siret_data.effectif_siren,
                    "idcc": siret_data.idcc,
                    "nb_colleges": siret_data.nb_college_siret
                })

        # Trier par date décroissante (plus récent en premier)
        formatted_results.sort(key=lambda x: x["date_scrutin"] or "", reverse=True)

        logger.info(f"✅ {len(formatted_results)} résultats électoraux trouvés pour SIREN {siren_clean} depuis siret_summary")

        return {
            "success": True,
            "siren": siren_clean,
            "count": len(formatted_results),
            "pv": formatted_results,
            "source": "siret_summary"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des résultats électoraux pour SIREN {siren}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")


@router.get("/entreprise/{siret}")
async def get_entreprise_fiche_complete(
    siret: str,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Récupère la fiche complète d'une entreprise avec toutes les données disponibles.

    Données agrégées :
    - Informations de base (raison sociale, adresse, SIREN/SIRET)
    - PV électoraux (Cycle 4 uniquement)
    - Invitations PAP (historique complet)
    - Liste des établissements (tous les SIRET du SIREN)
    - Statistiques agrégées

    Args:
        siret: Numéro SIRET (14 chiffres) ou SIREN (9 chiffres)

    Returns:
        Fiche entreprise complète avec toutes les données disponibles
    """
    try:
        # Nettoyer l'input
        siret_clean = ''.join(c for c in siret if c.isdigit())

        # Déterminer si c'est un SIRET ou SIREN
        if len(siret_clean) == 14:
            siren = siret_clean[:9]
            is_siret = True
        elif len(siret_clean) == 9:
            siren = siret_clean
            siret_clean = None
            is_siret = False
        else:
            raise HTTPException(
                status_code=400,
                detail="Numéro invalide (doit contenir 9 chiffres pour SIREN ou 14 pour SIRET)"
            )

        logger.info(f"📋 Récupération fiche entreprise pour {'SIRET' if is_siret else 'SIREN'}: {siret_clean or siren}")

        # ==================== 1. INFORMATIONS DE BASE ====================
        # Récupérer les infos de base depuis siret_summary ou Tous_PV
        info_base = None
        siret_principal = siret_clean or None

        if is_siret:
            # Chercher dans siret_summary
            siret_data = db.query(SiretSummary).filter(SiretSummary.siret == siret_clean).first()
            if siret_data:
                info_base = {
                    "siret": siret_data.siret,
                    "siren": siren,
                    "raison_sociale": siret_data.raison_sociale,
                    "ville": siret_data.ville,
                    "code_postal": siret_data.cp,
                    "region": siret_data.region,
                    "effectif_siret": siret_data.effectif_siret,
                    "effectif_siren": siret_data.effectif_siren,
                    "idcc": siret_data.idcc,
                }
            else:
                # Fallback vers Tous_PV
                pv_data = db.query(PVEvent).filter(PVEvent.siret == siret_clean).first()
                if pv_data:
                    info_base = {
                        "siret": pv_data.siret,
                        "siren": siren,
                        "raison_sociale": getattr(pv_data, 'raison_sociale', None),
                        "ville": getattr(pv_data, 'ville', None),
                        "code_postal": getattr(pv_data, 'cp', None),
                        "region": getattr(pv_data, 'region', None),
                        "effectif_siret": getattr(pv_data, 'effectif_siret', None),
                        "effectif_siren": getattr(pv_data, 'effectif_siren', None),
                        "idcc": getattr(pv_data, 'idcc', None),
                    }

        # Si pas trouvé ou si SIREN, chercher le premier établissement du SIREN
        if not info_base:
            siret_data = db.query(SiretSummary).filter(SiretSummary.siren == siren).first()
            if siret_data:
                siret_principal = siret_data.siret
                info_base = {
                    "siret": siret_data.siret,
                    "siren": siren,
                    "raison_sociale": siret_data.raison_sociale,
                    "ville": siret_data.ville,
                    "code_postal": siret_data.cp,
                    "region": siret_data.region,
                    "effectif_siret": siret_data.effectif_siret,
                    "effectif_siren": siret_data.effectif_siren,
                    "idcc": siret_data.idcc,
                }
            else:
                # Dernier fallback : Tous_PV
                pv_data = db.query(PVEvent).filter(PVEvent.siren == siren).first()
                if pv_data:
                    siret_principal = getattr(pv_data, 'siret', None)
                    info_base = {
                        "siret": siret_principal,
                        "siren": siren,
                        "raison_sociale": getattr(pv_data, 'raison_sociale', None),
                        "ville": getattr(pv_data, 'ville', None),
                        "code_postal": getattr(pv_data, 'cp', None),
                        "region": getattr(pv_data, 'region', None),
                        "effectif_siret": getattr(pv_data, 'effectif_siret', None),
                        "effectif_siren": getattr(pv_data, 'effectif_siren', None),
                        "idcc": getattr(pv_data, 'idcc', None),
                    }

        if not info_base:
            raise HTTPException(
                status_code=404,
                detail=f"Aucune donnée trouvée pour {'SIRET' if is_siret else 'SIREN'} {siret_clean or siren}"
            )

        # ==================== 2. PV ÉLECTORAUX (CYCLE 4 UNIQUEMENT) ====================
        pv_data = await get_pv_by_siren(siren, db)

        # Filtrer pour ne garder que Cycle 4
        pv_cycle_4 = []
        if pv_data.get("success") and pv_data.get("pv"):
            pv_cycle_4 = [pv for pv in pv_data["pv"] if pv.get("cycle") == "Cycle 4"]

        # ==================== 3. INVITATIONS PAP ====================
        invitations = db.query(Invitation).filter(
            or_(
                Invitation.siret == siret_clean if siret_clean else False,
                Invitation.siren == siren
            ),
            Invitation.est_actif == True
        ).order_by(Invitation.date_invit.desc()).all()

        invitations_list = []
        for inv in invitations:
            invitations_list.append({
                "id": inv.id,
                "siret": inv.siret,
                "raison_sociale": inv.raison_sociale,
                "ville": inv.ville,
                "code_postal": inv.code_postal,
                "date_invit": inv.date_invit.strftime("%Y-%m-%d") if inv.date_invit else None,
                "date_reception": inv.date_reception.strftime("%Y-%m-%d") if inv.date_reception else None,
                "date_election": inv.date_election.strftime("%Y-%m-%d") if inv.date_election else None,
                "effectif_connu": inv.effectif_connu,
                "ud": inv.ud,
                "fd": inv.fd,
                "idcc": inv.idcc,
                "structure_saisie": inv.structure_saisie,
                "source": inv.source,
            })

        # ==================== 4. LISTE DES ÉTABLISSEMENTS ====================
        etablissements_summary = db.query(SiretSummary).filter(
            SiretSummary.siren == siren
        ).all()

        etablissements_list = []
        for etab in etablissements_summary:
            etablissements_list.append({
                "siret": etab.siret,
                "raison_sociale": etab.raison_sociale,
                "ville": etab.ville,
                "code_postal": etab.cp,
                "effectif_siret": etab.effectif_siret,
                "has_pv_c3": etab.date_pv_c3 is not None,
                "has_pv_c4": etab.date_pv_c4 is not None,
            })

        # Si siret_summary est vide, chercher dans Tous_PV
        if not etablissements_list:
            etablissements_pv = db.query(PVEvent).filter(
                PVEvent.siren == siren
            ).all()

            # Dédupliquer par SIRET
            sirets_vus = set()
            for pv in etablissements_pv:
                siret_pv = getattr(pv, 'siret', None)
                if siret_pv and siret_pv not in sirets_vus:
                    sirets_vus.add(siret_pv)
                    etablissements_list.append({
                        "siret": siret_pv,
                        "raison_sociale": getattr(pv, 'raison_sociale', None),
                        "ville": getattr(pv, 'ville', None),
                        "code_postal": getattr(pv, 'cp', None),
                        "effectif_siret": getattr(pv, 'effectif_siret', None),
                        "has_pv_c3": getattr(pv, 'cycle', None) == "Cycle 3",
                        "has_pv_c4": getattr(pv, 'cycle', None) == "Cycle 4",
                    })

        # ==================== 5. STATISTIQUES AGRÉGÉES ====================
        stats = {
            "nb_etablissements": len(etablissements_list),
            "nb_pv_c4": len(pv_cycle_4),
            "nb_invitations_pap": len(invitations_list),
            "effectif_total_siren": info_base.get("effectif_siren"),
        }

        # Calculer présence CGT dans les PV C4
        nb_pv_avec_cgt = 0
        total_voix_cgt = 0
        for pv in pv_cycle_4:
            for org in pv.get("organisations", []):
                if org.get("nom") == "CGT":
                    nb_pv_avec_cgt += 1
                    total_voix_cgt += org.get("voix", 0)
                    break

        stats["presence_cgt_c4"] = nb_pv_avec_cgt
        stats["total_voix_cgt_c4"] = total_voix_cgt

        # ==================== RÉPONSE FINALE ====================
        logger.info(f"✅ Fiche entreprise récupérée : {stats['nb_pv_c4']} PV C4, {stats['nb_invitations_pap']} invitations PAP, {stats['nb_etablissements']} établissements")

        # ==================== ENREGISTREMENT DE L'ACTIVITÉ ====================
        if current_user:
            try:
                activity = UserActivity(
                    user_id=current_user.id,
                    activity_type="entreprise_fiche_view",
                    resource_id=siren,
                    resource_name=info_base.get("raison_sociale", f"SIREN {siren}"),
                    extra_data={
                        "siret": siret_principal,
                        "nb_pv_c4": stats["nb_pv_c4"],
                        "nb_invitations_pap": stats["nb_invitations_pap"],
                        "nb_etablissements": stats["nb_etablissements"],
                    }
                )
                db.add(activity)
                db.commit()
                logger.info(f"📝 Activité enregistrée pour user {current_user.id} : fiche {siren}")
            except Exception as e:
                logger.warning(f"Erreur lors de l'enregistrement de l'activité : {e}")
                db.rollback()

        return {
            "success": True,
            "siret": siret_principal,
            "siren": siren,
            "info_base": info_base,
            "pv_cycle_4": pv_cycle_4,
            "invitations_pap": invitations_list,
            "etablissements": etablissements_list,
            "stats": stats,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de la fiche entreprise: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")
