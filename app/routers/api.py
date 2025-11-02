from fastapi import APIRouter, UploadFile, File, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, select
from typing import List
from datetime import datetime, timedelta, date
import re

from ..db import get_session, Base, engine
from .. import etl
from ..models import SiretSummary, PVEvent, Invitation
from ..schemas import SiretSummaryOut
from ..services.sirene_api import enrichir_siret, SireneAPIError, rechercher_siret


router = APIRouter(prefix="/api", tags=["api"])

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
            "date_pap_c5": str(r.date_pap_c5) if r.date_pap_c5 else None,
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
    """Helper function to compute dashboard statistics"""

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

    total_siret = db.query(func.count(SiretSummary.siret)).scalar() or 0

    #
    # Détermination des SIRET cible (≥ 1000 inscrits au dernier PV du cycle 4)
    # ----------------------------------------------------------------------
    latest_c4_rows = (
        db.query(
            PVEvent.siret,
            PVEvent.id,
            PVEvent.inscrits,
            PVEvent.cgt_voix,
        )
        .filter(PVEvent.cycle.isnot(None))
        .filter(PVEvent.cycle.ilike("%C4%"))
        .all()
    )

    latest_per_siret: dict[str, dict[str, float]] = {}
    for siret_value, pv_id, inscrits_value, cgt_voix_value in latest_c4_rows:
        siret_str = (siret_value or "").strip()
        if not siret_str:
            continue

        try:
            pv_order = int(pv_id or 0)
        except (TypeError, ValueError):
            pv_order = 0

        current = latest_per_siret.get(siret_str)
        if current and pv_order <= current.get("order", 0):
            continue

        latest_per_siret[siret_str] = {
            "order": pv_order,
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
        dep_value = (row.dep or "").strip()
        if not dep_value:
            continue
        dep_counts[dep_value] = dep_counts.get(dep_value, 0) + 1

    dep_stats = sorted(
        dep_counts.items(), key=lambda item: (-item[1], item[0])
    )[:10]

    six_months_ago = date.today() - timedelta(days=180)

    if eligible_sirets:
        month_bucket = _month_bucket_expression(db, Invitation.date_invit)

        monthly_invitations = (
            db.query(
                month_bucket.label("month"),
                func.count(Invitation.id).label("count"),
            )
            .filter(Invitation.siret.in_(eligible_sirets))
            .filter(Invitation.date_invit >= six_months_ago)
            .group_by(month_bucket)
            .order_by(month_bucket)
            .all()
        )
    else:
        monthly_invitations = []

    today = date.today()
    per_cycle = {}

    upcoming_rows = (
        db.query(
            PVEvent.siret,
            PVEvent.cycle,
            PVEvent.date_prochain_scrutin,
            PVEvent.effectif_siret,
            PVEvent.inscrits,
        )
        .filter(PVEvent.date_prochain_scrutin.isnot(None))
        .all()
    )

    upcoming_c5_sirets: set[str] = set()

    for siret, cycle, next_date, effectif_siret, inscrits in upcoming_rows:
        parsed_date = _parse_date_value(next_date)
        if not parsed_date or parsed_date < today:
            continue

        effectif_value = _to_number(effectif_siret)
        if effectif_value is None:
            effectif_value = _to_number(inscrits)

        if effectif_value is None or effectif_value < audience_threshold:
            continue

        cycle_value = (cycle or "").upper()
        siret_value = str(siret or "").strip()
        if not siret_value:
            continue

        if (
            "C4" in cycle_value
            and "C5" not in cycle_value
            and siret_value in eligible_sirets
        ):
            upcoming_c5_sirets.add(siret_value)

        key = (siret_value, cycle_value)
        existing = per_cycle.get(key)
        if existing is None or parsed_date < existing:
            per_cycle[key] = parsed_date

    quarter_counts: dict[tuple[int, int], int] = {}
    for parsed_date in per_cycle.values():
        quarter_index = ((parsed_date.month - 1) // 3) + 1
        key = (parsed_date.year, quarter_index)
        quarter_counts[key] = quarter_counts.get(key, 0) + 1

    upcoming_quarters = [
        {"label": f"T{quarter} {year}", "count": count}
        for (year, quarter), count in sorted(
            quarter_counts.items(), key=lambda item: (item[0][0], item[0][1])
        )
    ][:4]

    upcoming_dates = list(per_cycle.values())
    upcoming_next_date = min(upcoming_dates) if upcoming_dates else None

    c5_upcoming_total = len(upcoming_c5_sirets)
    c5_upcoming_percent = round(
        (c5_upcoming_total / audience_siret * 100) if audience_siret > 0 else 0,
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
        "upcoming_total": len(per_cycle),
        "upcoming_next": _format_date_display(upcoming_next_date),
        "upcoming_threshold": audience_threshold,
    }

    # Statistiques par statut PAP sur la cible
    statut_counts: dict[str, int] = {}
    for row in summary_rows:
        statut_value = (row.statut_pap or "").strip()
        if not statut_value:
            continue
        statut_counts[statut_value] = statut_counts.get(statut_value, 0) + 1

    statut_stats = sorted(
        statut_counts.items(), key=lambda item: (-item[1], item[0])
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
        "audience_upcoming_c5": c5_upcoming_total,
        "audience_upcoming_c5_percent": c5_upcoming_percent,
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
        "monthly_invitations": [
            {"month": m[0], "count": m[1]} for m in monthly_invitations
        ],
        "upcoming_quarters": upcoming_quarters,
        "statut_stats": [{"statut": s[0], "count": s[1]} for s in statut_stats],
        "global_stats": global_stats,
    }


# ============================================================================
# ENRICHISSEMENT API SIRENE
# ============================================================================

def _normalise_search_term(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _search_local_siret(db: Session, nom: str, ville: str, limit: int) -> list[dict[str, str]]:
    """Fallback local en cas d'échec de l'API Sirene."""

    query = db.query(SiretSummary)

    cleaned_name = _normalise_search_term(nom)
    if cleaned_name:
        for token in cleaned_name.split():
            query = query.filter(SiretSummary.raison_sociale.ilike(f"%{token}%"))

    cleaned_city = _normalise_search_term(ville)
    if cleaned_city:
        for token in cleaned_city.split():
            query = query.filter(SiretSummary.ville.ilike(f"%{token}%"))

    if not cleaned_name and not cleaned_city:
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
    ville: str = Query(..., min_length=2),
    limit: int = Query(10, ge=1, le=20),
    db: Session = Depends(get_session),
):
    """Recherche d'établissements via l'API Sirene."""

    sirene_error: str | None = None
    results: List[dict] = []

    try:
        results = await rechercher_siret(nom, ville, limit)
    except SireneAPIError as exc:
        sirene_error = str(exc)

    if results:
        return {"results": results, "source": "sirene"}

    fallback = _search_local_siret(db, nom, ville, limit)
    if fallback:
        response = {"results": fallback, "source": "local"}
        if sirene_error:
            response["warning"] = sirene_error
        return response

    if sirene_error:
        raise HTTPException(status_code=502, detail=sirene_error)

    return {"results": [], "source": "sirene"}


@router.post("/sirene/enrichir/{siret}")
async def enrichir_un_siret(siret: str, db: Session = Depends(get_session)):
    """
    Enrichit une invitation avec les données de l'API Sirene
    """
    # Vérifie que l'invitation existe
    invitation = db.query(Invitation).filter(Invitation.siret == siret).first()
    if not invitation:
        raise HTTPException(status_code=404, detail=f"Aucune invitation trouvée pour le SIRET {siret}")

    try:
        # Récupère les données depuis l'API Sirene
        data = await enrichir_siret(siret)

        if not data:
            raise HTTPException(status_code=404, detail=f"SIRET {siret} non trouvé dans l'API Sirene")

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
        invitation.date_enrichissement = datetime.now()

        db.commit()

        return {
            "success": True,
            "message": f"SIRET {siret} enrichi avec succès",
            "data": data
        }

    except SireneAPIError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/sirene/enrichir-tout")
async def enrichir_toutes_invitations(
    force: bool = Query(False, description="Forcer le réenrichissement même si déjà fait"),
    db: Session = Depends(get_session)
):
    """
    Enrichit toutes les invitations qui n'ont pas encore été enrichies
    Si force=True, réenrichit même celles déjà enrichies
    """
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

    for invitation in invitations:
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
            erreurs_details.append(f"SIRET {invitation.siret}: Erreur inattendue")

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
