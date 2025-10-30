from fastapi import APIRouter, UploadFile, File, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from datetime import datetime
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

    # Enrichissement automatique des nouvelles invitations via API Sirene
    # (uniquement celles qui n'ont pas encore été enrichies)
    invitations_non_enrichies = db.query(Invitation).filter(
        Invitation.date_enrichissement.is_(None)
    ).all()

    enrichis = 0
    for invitation in invitations_non_enrichies[:50]:  # Limite à 50 pour éviter timeout (30 req/min max)
        try:
            data = await enrichir_siret(invitation.siret)
            if data:
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
        except Exception:
            pass  # On continue même si une erreur se produit

    db.commit()

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


# ============================================================================
# ENRICHISSEMENT API SIRENE
# ============================================================================

@router.get("/sirene/search")
async def sirene_search(
    nom: str = Query(..., min_length=2),
    ville: str = Query(..., min_length=2),
    limit: int = Query(10, ge=1, le=20),
):
    """Recherche d'établissements via l'API Sirene."""

    try:
        results = await rechercher_siret(nom, ville, limit)
        return {"results": results}
    except SireneAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


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
