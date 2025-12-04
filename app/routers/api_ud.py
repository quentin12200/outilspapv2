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
from ..models import TableauBordUD, EntrepriseUD, EvenementUD, ElectionUD, User, ChecklistItemUD
from ..user_auth import get_current_user_or_none

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ud", tags=["Tableaux UD"])


# ===============================================
# HELPER FUNCTIONS
# ===============================================

def create_default_checklist(db: Session, entreprise_id: int, type_cible: str):
    """Crée la checklist par défaut pour une entreprise selon son type"""
    from create_checklist_table import CHECKLIST_RENFORCEMENT, CHECKLIST_IMPLANTATION

    template = CHECKLIST_RENFORCEMENT if type_cible == "presente" else CHECKLIST_IMPLANTATION

    for item_template in template:
        checklist_item = ChecklistItemUD(
            entreprise_id=entreprise_id,
            categorie=item_template["categorie"],
            libelle=item_template["libelle"],
            ordre=item_template["ordre"],
            est_coche=False,
            informations=""
        )
        db.add(checklist_item)

    db.commit()


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

        # Créer automatiquement la checklist pour cette entreprise
        try:
            create_default_checklist(session, entreprise.id, data.type_cible)
            logger.info(f"Checklist créée pour entreprise {entreprise.id}")
        except Exception as e:
            logger.error(f"Erreur création checklist: {e}")
            # Ne pas bloquer la création de l'entreprise si la checklist échoue

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


# ===============================================
# ROUTES CHECKLIST MÉTHODOLOGIQUE
# ===============================================

class ChecklistItemUpdate(BaseModel):
    est_coche: Optional[bool] = None
    informations: Optional[str] = None
    objectif: Optional[str] = None
    action: Optional[str] = None
    echeance: Optional[date] = None
    responsable: Optional[str] = None


class ChecklistItemCreate(BaseModel):
    categorie: str
    libelle: str
    ordre: int = 0
    objectif: Optional[str] = None
    action: Optional[str] = None
    echeance: Optional[date] = None
    responsable: Optional[str] = None


@router.get("/entreprises/{entreprise_id}/checklist")
async def get_checklist(
    entreprise_id: int,
    db: Session = Depends(get_session),
    user: User | None = Depends(get_current_user_or_none)
):
    """Récupère la checklist méthodologique d'une entreprise"""
    try:
        # Vérifier que l'entreprise existe
        entreprise = db.query(EntrepriseUD).filter(EntrepriseUD.id == entreprise_id).first()
        if not entreprise:
            raise HTTPException(status_code=404, detail="Entreprise non trouvée")

        # Récupérer tous les items de la checklist
        items = db.query(ChecklistItemUD).filter(
            ChecklistItemUD.entreprise_id == entreprise_id
        ).order_by(ChecklistItemUD.categorie, ChecklistItemUD.ordre).all()

        # Grouper par catégorie
        checklist_by_category = {}
        for item in items:
            if item.categorie not in checklist_by_category:
                checklist_by_category[item.categorie] = []

            checklist_by_category[item.categorie].append({
                "id": item.id,
                "libelle": item.libelle,
                "ordre": item.ordre,
                "est_coche": item.est_coche,
                "informations": item.informations,
                "objectif": item.objectif,
                "action": item.action,
                "echeance": item.echeance.isoformat() if item.echeance else None,
                "responsable": item.responsable
            })

        return {
            "success": True,
            "data": {
                "entreprise": {
                    "id": entreprise.id,
                    "nom": entreprise.nom_entreprise,
                    "type_cible": entreprise.type_cible,
                    "type_label": "Renforcement" if entreprise.type_cible == "presente" else "Implantation"
                },
                "checklist": checklist_by_category,
                "total_items": len(items),
                "items_coches": sum(1 for item in items if item.est_coche),
                "progression": round((sum(1 for item in items if item.est_coche) / len(items) * 100) if items else 0, 1)
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de la checklist: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/entreprises/{entreprise_id}/checklist/{item_id}")
async def update_checklist_item(
    entreprise_id: int,
    item_id: int,
    item_update: ChecklistItemUpdate,
    db: Session = Depends(get_session),
    user: User | None = Depends(get_current_user_or_none)
):
    """Met à jour un item de la checklist"""
    try:
        # Récupérer l'item
        item = db.query(ChecklistItemUD).filter(
            ChecklistItemUD.id == item_id,
            ChecklistItemUD.entreprise_id == entreprise_id
        ).first()

        if not item:
            raise HTTPException(status_code=404, detail="Item de checklist non trouvé")

        # Mettre à jour les champs fournis
        if item_update.est_coche is not None:
            item.est_coche = item_update.est_coche

        if item_update.informations is not None:
            item.informations = item_update.informations

        if item_update.objectif is not None:
            item.objectif = item_update.objectif

        if item_update.action is not None:
            item.action = item_update.action

        if item_update.echeance is not None:
            item.echeance = item_update.echeance

        if item_update.responsable is not None:
            item.responsable = item_update.responsable

        item.updated_at = datetime.now()
        db.commit()
        db.refresh(item)

        return {
            "success": True,
            "message": "Item mis à jour avec succès",
            "data": {
                "id": item.id,
                "est_coche": item.est_coche,
                "informations": item.informations
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour de l'item: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/entreprises/{entreprise_id}/checklist")
async def create_checklist_item(
    entreprise_id: int,
    new_item: ChecklistItemCreate,
    db: Session = Depends(get_session),
    user: User | None = Depends(get_current_user_or_none)
):
    """Ajoute un nouvel item à la checklist (ex: plan d'action personnalisé)"""
    try:
        # Vérifier que l'entreprise existe
        entreprise = db.query(EntrepriseUD).filter(EntrepriseUD.id == entreprise_id).first()
        if not entreprise:
            raise HTTPException(status_code=404, detail="Entreprise non trouvée")

        # Créer le nouvel item
        checklist_item = ChecklistItemUD(
            entreprise_id=entreprise_id,
            categorie=new_item.categorie,
            libelle=new_item.libelle,
            ordre=new_item.ordre,
            est_coche=False,
            informations="",
            objectif=new_item.objectif,
            action=new_item.action,
            echeance=new_item.echeance,
            responsable=new_item.responsable,
            created_by=user.id if user else None
        )

        db.add(checklist_item)
        db.commit()
        db.refresh(checklist_item)

        return {
            "success": True,
            "message": "Item créé avec succès",
            "data": {
                "id": checklist_item.id,
                "categorie": checklist_item.categorie,
                "libelle": checklist_item.libelle
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la création de l'item: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
