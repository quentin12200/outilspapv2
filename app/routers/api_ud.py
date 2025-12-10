"""
Routes API pour la gestion des Unions Départementales (UD)
"""

import logging
import json
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ..db import get_session
from ..models import TableauBordUD
from ..user_auth import require_admin_user
from ..audit import log_admin_action

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ud", tags=["UD Management"])


@router.get("/tableaux")
async def get_all_tableaux_bord(
    db: Session = Depends(get_session),
    current_user = Depends(require_admin_user)
):
    """Récupère tous les tableaux de bord UD"""
    try:
        tableaux = db.query(TableauBordUD).order_by(TableauBordUD.numero_departement).all()
        return {
            "success": True,
            "count": len(tableaux),
            "tableaux": [
                {
                    "id": t.id,
                    "numero_departement": t.numero_departement,
                    "nom_departement": t.nom_departement,
                    "code_ud": t.code_ud,
                    "email_ud": t.email_ud,
                    "telephone_ud": t.telephone_ud,
                    "adresse_ud": t.adresse_ud,
                    "responsable_ud": t.responsable_ud,
                    "nb_entreprises_cibles": t.nb_entreprises_cibles,
                    "nb_entreprises_absentes": t.nb_entreprises_absentes,
                    "nb_total_syndiques": t.nb_total_syndiques,
                    "nb_prochaines_elections": t.nb_prochaines_elections,
                    "is_active": t.is_active,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                    "updated_at": t.updated_at.isoformat() if t.updated_at else None,
                }
                for t in tableaux
            ]
        }
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des tableaux de bord UD: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tableaux/{numero_departement}")
async def get_tableau_bord_by_numero(
    numero_departement: str,
    db: Session = Depends(get_session),
    current_user = Depends(require_admin_user)
):
    """Récupère un tableau de bord UD par son numéro de département"""
    try:
        tableau = db.query(TableauBordUD).filter(
            TableauBordUD.numero_departement == numero_departement
        ).first()

        if not tableau:
            raise HTTPException(status_code=404, detail=f"Aucun tableau de bord trouvé pour le département {numero_departement}")

        return {
            "success": True,
            "tableau": {
                "id": tableau.id,
                "numero_departement": tableau.numero_departement,
                "nom_departement": tableau.nom_departement,
                "code_ud": tableau.code_ud,
                "email_ud": tableau.email_ud,
                "telephone_ud": tableau.telephone_ud,
                "adresse_ud": tableau.adresse_ud,
                "responsable_ud": tableau.responsable_ud,
                "nb_entreprises_cibles": tableau.nb_entreprises_cibles,
                "nb_entreprises_absentes": tableau.nb_entreprises_absentes,
                "nb_total_syndiques": tableau.nb_total_syndiques,
                "nb_prochaines_elections": tableau.nb_prochaines_elections,
                "is_active": tableau.is_active,
                "created_at": tableau.created_at.isoformat() if tableau.created_at else None,
                "updated_at": tableau.updated_at.isoformat() if tableau.updated_at else None,
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du tableau de bord UD {numero_departement}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tableaux/importer-contacts-json")
async def importer_contacts_json(
    file: UploadFile = File(...),
    db: Session = Depends(get_session),
    current_user = Depends(require_admin_user)
):
    """
    Importe les contacts des UD depuis un fichier JSON.

    Le fichier JSON doit avoir le format suivant:
    [
        {
            "numero_departement": "34",
            "nom_departement": "Hérault",
            "code_ud": "ud34",
            "email_ud": "ud34@cgt.fr",
            "telephone_ud": "04...",
            "adresse_ud": "...",
            "responsable_ud": "Nom Prénom"
        },
        ...
    ]
    """
    try:
        # Lire le fichier JSON
        content = await file.read()
        data = json.loads(content.decode('utf-8'))

        if not isinstance(data, list):
            raise HTTPException(status_code=400, detail="Le fichier JSON doit contenir une liste d'objets")

        imported_count = 0
        updated_count = 0
        skipped_count = 0
        errors = []

        for idx, ud_data in enumerate(data):
            try:
                # Vérifier les champs requis
                if not ud_data.get("numero_departement") or not ud_data.get("nom_departement") or not ud_data.get("code_ud"):
                    errors.append(f"Ligne {idx + 1}: Champs requis manquants (numero_departement, nom_departement, code_ud)")
                    skipped_count += 1
                    continue

                numero_dept = str(ud_data["numero_departement"]).strip()

                # Vérifier si l'UD existe déjà
                existing_ud = db.query(TableauBordUD).filter(
                    TableauBordUD.numero_departement == numero_dept
                ).first()

                if existing_ud:
                    # Mettre à jour
                    existing_ud.nom_departement = ud_data.get("nom_departement", existing_ud.nom_departement)
                    existing_ud.code_ud = ud_data.get("code_ud", existing_ud.code_ud)
                    existing_ud.email_ud = ud_data.get("email_ud")
                    existing_ud.telephone_ud = ud_data.get("telephone_ud")
                    existing_ud.adresse_ud = ud_data.get("adresse_ud")
                    existing_ud.responsable_ud = ud_data.get("responsable_ud")
                    updated_count += 1
                    logger.info(f"UD {numero_dept} mise à jour")
                else:
                    # Créer nouveau
                    new_ud = TableauBordUD(
                        numero_departement=numero_dept,
                        nom_departement=ud_data["nom_departement"],
                        code_ud=ud_data["code_ud"],
                        email_ud=ud_data.get("email_ud"),
                        telephone_ud=ud_data.get("telephone_ud"),
                        adresse_ud=ud_data.get("adresse_ud"),
                        responsable_ud=ud_data.get("responsable_ud"),
                        created_by=current_user.id if hasattr(current_user, 'id') else None
                    )
                    db.add(new_ud)
                    imported_count += 1
                    logger.info(f"UD {numero_dept} créée")

                # Commit après chaque UD pour isoler les erreurs
                db.commit()

            except IntegrityError as e:
                db.rollback()
                logger.error(f"Erreur d'intégrité pour le département {ud_data.get('numero_departement')}: {e}")
                errors.append(f"Ligne {idx + 1}: Erreur d'intégrité - {str(e)}")
                skipped_count += 1
            except Exception as e:
                db.rollback()
                logger.error(f"Erreur lors de l'import pour le département {ud_data.get('numero_departement')}: {e}")
                errors.append(f"Ligne {idx + 1}: {str(e)}")
                skipped_count += 1

        # Log de l'action admin
        log_admin_action(
            db=db,
            user_id=current_user.id if hasattr(current_user, 'id') else None,
            action="import_ud_contacts",
            details={
                "imported": imported_count,
                "updated": updated_count,
                "skipped": skipped_count,
                "errors_count": len(errors)
            }
        )

        response = {
            "success": True,
            "imported": imported_count,
            "updated": updated_count,
            "skipped": skipped_count,
            "total": imported_count + updated_count,
            "message": f"Import terminé: {imported_count} créées, {updated_count} mises à jour, {skipped_count} ignorées"
        }

        if errors:
            response["errors"] = errors[:10]  # Limiter à 10 premières erreurs
            response["errors_total"] = len(errors)

        return response

    except json.JSONDecodeError as e:
        logger.error(f"Erreur de parsing JSON: {e}")
        raise HTTPException(status_code=400, detail=f"Fichier JSON invalide: {str(e)}")
    except Exception as e:
        logger.error(f"Erreur lors de l'import des contacts UD: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tableaux")
async def create_tableau_bord(
    numero_departement: str,
    nom_departement: str,
    code_ud: str,
    email_ud: str = None,
    telephone_ud: str = None,
    adresse_ud: str = None,
    responsable_ud: str = None,
    db: Session = Depends(get_session),
    current_user = Depends(require_admin_user)
):
    """Crée un nouveau tableau de bord UD"""
    try:
        # Vérifier si existe déjà
        existing = db.query(TableauBordUD).filter(
            TableauBordUD.numero_departement == numero_departement
        ).first()

        if existing:
            raise HTTPException(status_code=400, detail=f"Un tableau de bord existe déjà pour le département {numero_departement}")

        # Créer
        new_tableau = TableauBordUD(
            numero_departement=numero_departement,
            nom_departement=nom_departement,
            code_ud=code_ud,
            email_ud=email_ud,
            telephone_ud=telephone_ud,
            adresse_ud=adresse_ud,
            responsable_ud=responsable_ud,
            created_by=current_user.id if hasattr(current_user, 'id') else None
        )

        db.add(new_tableau)
        db.commit()
        db.refresh(new_tableau)

        # Log de l'action
        log_admin_action(
            db=db,
            user_id=current_user.id if hasattr(current_user, 'id') else None,
            action="create_ud_tableau",
            details={"numero_departement": numero_departement, "nom_departement": nom_departement}
        )

        return {
            "success": True,
            "message": f"Tableau de bord créé pour {nom_departement}",
            "id": new_tableau.id
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Erreur lors de la création du tableau de bord UD: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/tableaux/{numero_departement}")
async def update_tableau_bord(
    numero_departement: str,
    nom_departement: str = None,
    code_ud: str = None,
    email_ud: str = None,
    telephone_ud: str = None,
    adresse_ud: str = None,
    responsable_ud: str = None,
    nb_entreprises_cibles: int = None,
    nb_entreprises_absentes: int = None,
    nb_total_syndiques: int = None,
    nb_prochaines_elections: int = None,
    is_active: bool = None,
    db: Session = Depends(get_session),
    current_user = Depends(require_admin_user)
):
    """Met à jour un tableau de bord UD"""
    try:
        tableau = db.query(TableauBordUD).filter(
            TableauBordUD.numero_departement == numero_departement
        ).first()

        if not tableau:
            raise HTTPException(status_code=404, detail=f"Aucun tableau de bord trouvé pour le département {numero_departement}")

        # Mettre à jour les champs fournis
        if nom_departement is not None:
            tableau.nom_departement = nom_departement
        if code_ud is not None:
            tableau.code_ud = code_ud
        if email_ud is not None:
            tableau.email_ud = email_ud
        if telephone_ud is not None:
            tableau.telephone_ud = telephone_ud
        if adresse_ud is not None:
            tableau.adresse_ud = adresse_ud
        if responsable_ud is not None:
            tableau.responsable_ud = responsable_ud
        if nb_entreprises_cibles is not None:
            tableau.nb_entreprises_cibles = nb_entreprises_cibles
        if nb_entreprises_absentes is not None:
            tableau.nb_entreprises_absentes = nb_entreprises_absentes
        if nb_total_syndiques is not None:
            tableau.nb_total_syndiques = nb_total_syndiques
        if nb_prochaines_elections is not None:
            tableau.nb_prochaines_elections = nb_prochaines_elections
        if is_active is not None:
            tableau.is_active = is_active

        db.commit()

        # Log de l'action
        log_admin_action(
            db=db,
            user_id=current_user.id if hasattr(current_user, 'id') else None,
            action="update_ud_tableau",
            details={"numero_departement": numero_departement}
        )

        return {
            "success": True,
            "message": f"Tableau de bord mis à jour pour le département {numero_departement}"
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Erreur lors de la mise à jour du tableau de bord UD: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/tableaux/{numero_departement}")
async def delete_tableau_bord(
    numero_departement: str,
    db: Session = Depends(get_session),
    current_user = Depends(require_admin_user)
):
    """Supprime un tableau de bord UD"""
    try:
        tableau = db.query(TableauBordUD).filter(
            TableauBordUD.numero_departement == numero_departement
        ).first()

        if not tableau:
            raise HTTPException(status_code=404, detail=f"Aucun tableau de bord trouvé pour le département {numero_departement}")

        db.delete(tableau)
        db.commit()

        # Log de l'action
        log_admin_action(
            db=db,
            user_id=current_user.id if hasattr(current_user, 'id') else None,
            action="delete_ud_tableau",
            details={"numero_departement": numero_departement}
        )

        return {
            "success": True,
            "message": f"Tableau de bord supprimé pour le département {numero_departement}"
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Erreur lors de la suppression du tableau de bord UD: {e}")
        raise HTTPException(status_code=500, detail=str(e))
