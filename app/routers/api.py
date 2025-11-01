from fastapi import APIRouter, UploadFile, File, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
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

    audience_threshold = 1000

    total_siret = db.query(func.count(SiretSummary.siret)).scalar() or 0

    audience_selected = (
        db.query(
            SiretSummary.siret.label("siret"),
            func.coalesce(SiretSummary.inscrits_c4, 0).label("inscrits_c4"),
            SiretSummary.carence_c4.label("carence_c4"),
        )
        .filter(func.coalesce(SiretSummary.inscrits_c4, 0) >= audience_threshold)
        .subquery()
    )

    audience_siret = (
        db.query(func.count(audience_selected.c.siret))
        .select_from(audience_selected)
        .scalar()
        or 0
    )

    audience_siret_c4_carence = (
        db.query(func.count(audience_selected.c.siret))
        .select_from(audience_selected)
        .filter(audience_selected.c.carence_c4.is_(True))
        .scalar()
        or 0
    )

    audience_siret_c4_pv = (
        db.query(func.count(audience_selected.c.siret))
        .select_from(audience_selected)
        .filter(
            or_(
                audience_selected.c.carence_c4.is_(False),
                audience_selected.c.carence_c4.is_(None),
            )
        )
        .scalar()
        or 0
    )

    audience_inscrits = (
        db.query(func.sum(audience_selected.c.inscrits_c4))
        .select_from(audience_selected)
        .scalar()
        or 0
    )

    audience_cgt_implantee = (
        db.query(func.count(SiretSummary.siret))
        .join(audience_selected, audience_selected.c.siret == SiretSummary.siret)
        .filter(SiretSummary.cgt_implantee == True)  # noqa: E712
        .scalar()
        or 0
    )

    audience_voix_cgt = (
        db.query(func.sum(func.coalesce(SiretSummary.cgt_voix_c4, 0)))
        .join(audience_selected, audience_selected.c.siret == SiretSummary.siret)
        .scalar()
        or 0
    )

    audience_invitations = (
        db.query(func.count(func.distinct(Invitation.siret)))
        .join(audience_selected, audience_selected.c.siret == Invitation.siret)
        .scalar()
        or 0
    )

    # Répartition par département (top 10) sur la cible
    dep_stats = (
        db.query(
            SiretSummary.dep,
            func.count(SiretSummary.siret).label("count"),
        )
        .join(audience_selected, audience_selected.c.siret == SiretSummary.siret)
        .filter(SiretSummary.dep.isnot(None))
        .group_by(SiretSummary.dep)
        .order_by(func.count(SiretSummary.siret).desc())
        .limit(10)
        .all()
    )

    six_months_ago = datetime.now() - timedelta(days=180)

    monthly_invitations = (
        db.query(
            func.strftime("%Y-%m", Invitation.date_invit).label("month"),
            func.count(Invitation.id).label("count"),
        )
        .join(audience_selected, audience_selected.c.siret == Invitation.siret)
        .filter(Invitation.date_invit >= six_months_ago)
        .group_by(func.strftime("%Y-%m", Invitation.date_invit))
        .order_by("month")
        .all()
    )

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

    def _to_number(value):
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            cleaned = value.strip().replace("\u202f", "").replace("\xa0", "").replace(" ", "")
            cleaned = cleaned.replace(",", ".")
            if not cleaned:
                return None
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None

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
        if "C4" in cycle_value and "C5" not in cycle_value:
            siret_value = str(siret or "").strip()
            if siret_value:
                upcoming_c5_sirets.add(siret_value)

        key = (siret or "", cycle or "")
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

    # Statistiques par statut PAP sur la cible
    statut_stats = (
        db.query(
            SiretSummary.statut_pap,
            func.count(SiretSummary.siret).label("count"),
        )
        .join(audience_selected, audience_selected.c.siret == SiretSummary.siret)
        .filter(SiretSummary.statut_pap.isnot(None))
        .group_by(SiretSummary.statut_pap)
        .all()
    )

    audience_inscrits = int(audience_inscrits or 0)
    audience_voix_cgt = int(audience_voix_cgt or 0)

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
        "audience_upcoming_c5": len(upcoming_c5_sirets),
        "departments": [{"dep": d[0], "count": d[1]} for d in dep_stats],
        "monthly_invitations": [
            {"month": m[0], "count": m[1]} for m in monthly_invitations
        ],
        "upcoming_quarters": upcoming_quarters,
        "statut_stats": [{"statut": s[0], "count": s[1]} for s in statut_stats],
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
    from datetime import datetime, timedelta
    twelve_months_ago = datetime.now() - timedelta(days=365)

    monthly_evolution = db.query(
        func.strftime('%Y-%m', Invitation.date_invit).label('month'),
        func.count(Invitation.id).label('count')
    ).filter(
        Invitation.date_invit >= twelve_months_ago
    ).group_by(
        func.strftime('%Y-%m', Invitation.date_invit)
    ).order_by('month').all()

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
