"""
API Router pour le système de tableau de bord UD.
Gère les tableaux de bord, entreprises, événements et élections des Unions Départementales.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, date
from typing import List, Optional
import logging

from ..db import get_session
from ..models import TableauBordUD, EntrepriseUD, EvenementUD, ElectionUD, User
from ..user_auth import get_current_user_or_none

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ud", tags=["Tableaux UD"])


# ===============================================
# PYDANTIC MODELS (validation des données)
# ===============================================

class TableauUDCreate(BaseModel):
    numero_departement: str
    nom_departement: str
    code_ud: str
    email_ud: Optional[str] = None
    telephone_ud: Optional[str] = None
    adresse_ud: Optional[str] = None


class EntrepriseUDCreate(BaseModel):
    siret: str
    nom_entreprise: str
    type_cible: str  # "presente" ou "absente"
    enseigne: Optional[str] = None
    nb_salaries: Optional[int] = None
    nb_syndiques: Optional[int] = None
    voix_cgt: Optional[int] = None
    ville: Optional[str] = None
    code_postal: Optional[str] = None
    pilote: Optional[str] = None
    date_prochaine_election: Optional[str] = None
    date_derniere_election: Optional[str] = None
    date_presentation_ce: Optional[str] = None
    enjeux: Optional[str] = None
    objet: Optional[str] = None
    suivi_pap: Optional[str] = None
    idcc: Optional[str] = None
    nom_contact: Optional[str] = None
    telephone_contact: Optional[str] = None
    email_contact: Optional[str] = None


# ===============================================
# ROUTES - TABLEAUX DE BORD UD
# ===============================================

@router.get("/tableaux")
async def get_tableaux_ud(
    active_only: bool = Query(True, description="Ne retourner que les tableaux actifs"),
    session: Session = Depends(get_session)
):
    """Liste tous les tableaux de bord UD"""
    try:
        query = session.query(TableauBordUD)

        if active_only:
            query = query.filter(TableauBordUD.is_active == True)

        tableaux = query.order_by(TableauBordUD.numero_departement).all()

        return {
            "success": True,
            "count": len(tableaux),
            "data": [{
                "id": t.id,
                "code_ud": t.code_ud,
                "numero_departement": t.numero_departement,
                "nom_departement": t.nom_departement,
                "email_ud": t.email_ud,
                "telephone_ud": t.telephone_ud,
                "nb_entreprises_cibles": t.nb_entreprises_cibles or 0,
                "nb_entreprises_absentes": t.nb_entreprises_absentes or 0,
                "nb_total_syndiques": t.nb_total_syndiques or 0,
                "nb_prochaines_elections": t.nb_prochaines_elections or 0,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "updated_at": t.updated_at.isoformat() if t.updated_at else None
            } for t in tableaux]
        }

    except Exception as e:
        logger.error(f"Erreur lors de la récupération des tableaux UD: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tableaux/{code_ud}")
async def get_tableau_ud(
    code_ud: str,
    session: Session = Depends(get_session)
):
    """Récupère un tableau de bord UD par son code"""
    try:
        tableau = session.query(TableauBordUD).filter_by(code_ud=code_ud).first()

        if not tableau:
            raise HTTPException(status_code=404, detail="Tableau UD non trouvé")

        return {
            "success": True,
            "data": {
                "id": tableau.id,
                "code_ud": tableau.code_ud,
                "numero_departement": tableau.numero_departement,
                "nom_departement": tableau.nom_departement,
                "email_ud": tableau.email_ud,
                "telephone_ud": tableau.telephone_ud,
                "adresse_ud": tableau.adresse_ud,
                "nb_entreprises_cibles": tableau.nb_entreprises_cibles or 0,
                "nb_entreprises_absentes": tableau.nb_entreprises_absentes or 0,
                "nb_total_syndiques": tableau.nb_total_syndiques or 0,
                "nb_prochaines_elections": tableau.nb_prochaines_elections or 0,
                "is_active": tableau.is_active,
                "created_at": tableau.created_at.isoformat() if tableau.created_at else None,
                "updated_at": tableau.updated_at.isoformat() if tableau.updated_at else None
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du tableau UD {code_ud}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tableaux")
async def create_tableau_ud(
    data: TableauUDCreate,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_current_user_or_none)
):
    """Crée un nouveau tableau de bord UD"""
    try:
        # Vérifier que le code UD n'existe pas déjà
        existing = session.query(TableauBordUD).filter_by(code_ud=data.code_ud).first()
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Un tableau UD avec le code '{data.code_ud}' existe déjà"
            )

        # Créer le tableau
        tableau = TableauBordUD(
            numero_departement=data.numero_departement,
            nom_departement=data.nom_departement,
            code_ud=data.code_ud,
            email_ud=data.email_ud,
            telephone_ud=data.telephone_ud,
            adresse_ud=data.adresse_ud,
            created_by=current_user.id if current_user else None
        )

        session.add(tableau)
        session.commit()
        session.refresh(tableau)

        logger.info(f"Tableau UD créé: {tableau.code_ud} - {tableau.nom_departement}")

        return {
            "success": True,
            "message": "Tableau UD créé avec succès",
            "data": {
                "id": tableau.id,
                "code_ud": tableau.code_ud,
                "nom_departement": tableau.nom_departement
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Erreur lors de la création du tableau UD: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===============================================
# ROUTES - ENTREPRISES UD
# ===============================================

@router.get("/tableaux/{code_ud}/entreprises")
async def get_entreprises_ud(
    code_ud: str,
    type_cible: str = Query("all", description="Type: presente, absente, ou all"),
    pilote: Optional[str] = Query(None, description="Filtrer par pilote"),
    search: Optional[str] = Query(None, description="Rechercher dans le nom"),
    session: Session = Depends(get_session)
):
    """Liste les entreprises d'un tableau UD"""
    try:
        # Récupérer le tableau UD
        tableau = session.query(TableauBordUD).filter_by(code_ud=code_ud).first()
        if not tableau:
            raise HTTPException(status_code=404, detail="Tableau UD non trouvé")

        # Query de base
        query = session.query(EntrepriseUD).filter(
            EntrepriseUD.tableau_bord_id == tableau.id,
            EntrepriseUD.is_archived == False
        )

        # Filtres
        if type_cible != "all":
            query = query.filter(EntrepriseUD.type_cible == type_cible)

        if pilote:
            query = query.filter(EntrepriseUD.pilote == pilote)

        if search:
            query = query.filter(EntrepriseUD.nom_entreprise.ilike(f'%{search}%'))

        entreprises = query.order_by(EntrepriseUD.nom_entreprise).all()

        return {
            "success": True,
            "count": len(entreprises),
            "data": [{
                "id": e.id,
                "siret": e.siret,
                "nom_entreprise": e.nom_entreprise,
                "type_cible": e.type_cible,
                "nb_salaries": e.nb_salaries,
                "nb_syndiques": e.nb_syndiques or 0,
                "ville": e.ville,
                "pilote": e.pilote,
                "date_prochaine_election": e.date_prochaine_election.isoformat() if e.date_prochaine_election else None,
                "voix_cgt": e.voix_cgt,
                "enjeux": e.enjeux
            } for e in entreprises]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des entreprises UD: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tableaux/{code_ud}/entreprises")
async def create_entreprise_ud(
    code_ud: str,
    data: EntrepriseUDCreate,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_current_user_or_none)
):
    """Ajoute une entreprise à un tableau UD"""
    try:
        # Récupérer le tableau UD
        tableau = session.query(TableauBordUD).filter_by(code_ud=code_ud).first()
        if not tableau:
            raise HTTPException(status_code=404, detail="Tableau UD non trouvé")

        # Validation du type_cible
        if data.type_cible not in ['presente', 'absente']:
            raise HTTPException(
                status_code=400,
                detail="type_cible doit être 'presente' ou 'absente'"
            )

        # Convertir les dates
        date_fields = {
            'date_derniere_election': data.date_derniere_election,
            'date_prochaine_election': data.date_prochaine_election,
            'date_presentation_ce': data.date_presentation_ce
        }

        converted_dates = {}
        for field, value in date_fields.items():
            if value:
                try:
                    converted_dates[field] = datetime.fromisoformat(value.replace('Z', '+00:00')).date()
                except:
                    converted_dates[field] = None

        # Créer l'entreprise
        entreprise = EntrepriseUD(
            tableau_bord_id=tableau.id,
            siret=data.siret,
            nom_entreprise=data.nom_entreprise,
            type_cible=data.type_cible,
            enseigne=data.enseigne,
            nb_salaries=data.nb_salaries,
            nb_syndiques=data.nb_syndiques,
            voix_cgt=data.voix_cgt,
            ville=data.ville,
            code_postal=data.code_postal,
            pilote=data.pilote,
            enjeux=data.enjeux,
            objet=data.objet,
            suivi_pap=data.suivi_pap,
            idcc=data.idcc,
            nom_contact=data.nom_contact,
            telephone_contact=data.telephone_contact,
            email_contact=data.email_contact,
            created_by=current_user.id if current_user else None,
            **converted_dates
        )

        session.add(entreprise)

        # Mettre à jour les stats du tableau
        if data.type_cible == 'presente':
            tableau.nb_entreprises_cibles = (tableau.nb_entreprises_cibles or 0) + 1
        else:
            tableau.nb_entreprises_absentes = (tableau.nb_entreprises_absentes or 0) + 1

        if data.nb_syndiques:
            tableau.nb_total_syndiques = (tableau.nb_total_syndiques or 0) + data.nb_syndiques

        session.commit()
        session.refresh(entreprise)

        logger.info(f"Entreprise ajoutée au tableau {code_ud}: {entreprise.nom_entreprise}")

        return {
            "success": True,
            "message": "Entreprise ajoutée avec succès",
            "data": {"id": entreprise.id, "nom": entreprise.nom_entreprise}
        }

    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Erreur lors de l'ajout de l'entreprise: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===============================================
# ROUTES - STATISTIQUES
# ===============================================

@router.get("/tableaux/{code_ud}/stats")
async def get_stats_tableau_ud(
    code_ud: str,
    session: Session = Depends(get_session)
):
    """Récupère les statistiques détaillées d'un tableau UD"""
    try:
        # Récupérer le tableau UD
        tableau = session.query(TableauBordUD).filter_by(code_ud=code_ud).first()
        if not tableau:
            raise HTTPException(status_code=404, detail="Tableau UD non trouvé")

        # Statistiques des entreprises
        entreprises_stats = session.query(
            EntrepriseUD.type_cible,
            func.count(EntrepriseUD.id).label('count'),
            func.sum(EntrepriseUD.nb_salaries).label('total_salaries'),
            func.sum(EntrepriseUD.nb_syndiques).label('total_syndiques')
        ).filter(
            EntrepriseUD.tableau_bord_id == tableau.id,
            EntrepriseUD.is_archived == False
        ).group_by(EntrepriseUD.type_cible).all()

        # Prochaines élections (90 jours)
        date_limite = date.today() + timedelta(days=90)
        prochaines_elections = session.query(EntrepriseUD).filter(
            EntrepriseUD.tableau_bord_id == tableau.id,
            EntrepriseUD.is_archived == False,
            EntrepriseUD.date_prochaine_election.isnot(None),
            EntrepriseUD.date_prochaine_election <= date_limite,
            EntrepriseUD.date_prochaine_election >= date.today()
        ).order_by(EntrepriseUD.date_prochaine_election).all()

        # Top pilotes
        top_pilotes = session.query(
            EntrepriseUD.pilote,
            func.count(EntrepriseUD.id).label('nb_entreprises')
        ).filter(
            EntrepriseUD.tableau_bord_id == tableau.id,
            EntrepriseUD.is_archived == False,
            EntrepriseUD.pilote.isnot(None)
        ).group_by(EntrepriseUD.pilote).order_by(func.count(EntrepriseUD.id).desc()).limit(10).all()

        return {
            "success": True,
            "data": {
                "tableau_ud": {
                    "code_ud": tableau.code_ud,
                    "nom_departement": tableau.nom_departement
                },
                "entreprises": {
                    "par_type": {stat.type_cible: {
                        "count": stat.count,
                        "total_salaries": stat.total_salaries or 0,
                        "total_syndiques": stat.total_syndiques or 0
                    } for stat in entreprises_stats},
                    "total": sum(stat.count for stat in entreprises_stats)
                },
                "prochaines_elections": {
                    "count": len(prochaines_elections),
                    "liste": [{
                        "entreprise": e.nom_entreprise,
                        "date": e.date_prochaine_election.isoformat(),
                        "nb_salaries": e.nb_salaries,
                        "pilote": e.pilote
                    } for e in prochaines_elections]
                },
                "pilotes": [{
                    "nom": p.pilote,
                    "nb_entreprises": p.nb_entreprises
                } for p in top_pilotes]
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors du calcul des statistiques: {e}")
        raise HTTPException(status_code=500, detail=str(e))
