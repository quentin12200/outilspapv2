"""
Portail de consultation des PAPs par UD et FD.

Permet aux Unions Départementales et Fédérations de consulter
tous les PAPs qui leur sont destinés via un lien unique.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..db import get_session
from ..models import PAPDocument, TableauBordUD

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Portail UD/FD"])

# Templates Jinja2
templates = Jinja2Templates(directory="app/templates")


@router.get("/ud/{numero_departement}/paps", response_class=HTMLResponse)
async def portail_ud(
    numero_departement: str,
    request: Request,
    db: Session = Depends(get_session)
):
    """
    Portail de consultation des PAPs pour une Union Départementale.

    Affiche tous les PAPs destinés à une UD spécifique.
    """
    try:
        # Vérifier que l'UD existe
        ud = db.query(TableauBordUD).filter(
            TableauBordUD.numero_departement == numero_departement
        ).first()

        if not ud:
            raise HTTPException(
                status_code=404,
                detail=f"Union Départementale {numero_departement} non trouvée"
            )

        # Récupérer tous les PAPs pour ce département
        paps = db.query(PAPDocument).filter(
            PAPDocument.numero_departement == numero_departement,
            PAPDocument.is_active == True
        ).order_by(desc(PAPDocument.uploaded_at)).all()

        # Calculer les statistiques
        total_paps = len(paps)
        paps_enjeux = sum(1 for p in paps if p.is_priority)
        paps_standard = total_paps - paps_enjeux
        paps_cgt_history = sum(1 for p in paps if p.has_cgt_history)

        # Grouper par FD
        paps_by_fd = {}
        for pap in paps:
            fd = pap.fd if pap.fd else "sans fd"
            if fd not in paps_by_fd:
                paps_by_fd[fd] = []
            paps_by_fd[fd].append(pap)

        return templates.TemplateResponse("portail_ud.html", {
            "request": request,
            "ud": ud,
            "paps": paps,
            "stats": {
                "total": total_paps,
                "enjeux": paps_enjeux,
                "standard": paps_standard,
                "cgt_history": paps_cgt_history
            },
            "paps_by_fd": paps_by_fd
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de l'affichage du portail UD {numero_departement}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/fd/{code_fd}/paps", response_class=HTMLResponse)
async def portail_fd(
    code_fd: str,
    request: Request,
    db: Session = Depends(get_session)
):
    """
    Portail de consultation des PAPs pour une Fédération.

    Affiche tous les PAPs destinés à une FD spécifique.
    """
    try:
        # Gérer le cas "sans fd"
        if code_fd.lower() == "sans-fd":
            code_fd = "sans fd"

        # Récupérer tous les PAPs pour cette FD
        paps = db.query(PAPDocument).filter(
            PAPDocument.fd == code_fd,
            PAPDocument.is_active == True
        ).order_by(desc(PAPDocument.uploaded_at)).all()

        if not paps:
            logger.warning(f"Aucun PAP trouvé pour la FD {code_fd}")

        # Calculer les statistiques
        total_paps = len(paps)
        paps_enjeux = sum(1 for p in paps if p.is_priority)
        paps_standard = total_paps - paps_enjeux
        paps_cgt_history = sum(1 for p in paps if p.has_cgt_history)

        # Grouper par département
        paps_by_dept = {}
        for pap in paps:
            dept = pap.numero_departement if pap.numero_departement else "Non défini"
            if dept not in paps_by_dept:
                paps_by_dept[dept] = []
            paps_by_dept[dept].append(pap)

        return templates.TemplateResponse("portail_fd.html", {
            "request": request,
            "code_fd": code_fd,
            "paps": paps,
            "stats": {
                "total": total_paps,
                "enjeux": paps_enjeux,
                "standard": paps_standard,
                "cgt_history": paps_cgt_history
            },
            "paps_by_dept": paps_by_dept
        })

    except Exception as e:
        logger.error(f"Erreur lors de l'affichage du portail FD {code_fd}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/ud/{numero_departement}/paps")
async def api_get_paps_by_ud(
    numero_departement: str,
    db: Session = Depends(get_session)
):
    """
    API JSON pour récupérer les PAPs d'une UD.

    Utile pour intégrations externes ou applications mobiles.
    """
    try:
        paps = db.query(PAPDocument).filter(
            PAPDocument.numero_departement == numero_departement,
            PAPDocument.is_active == True
        ).order_by(desc(PAPDocument.uploaded_at)).all()

        return {
            "success": True,
            "numero_departement": numero_departement,
            "total": len(paps),
            "paps": [
                {
                    "id": p.id,
                    "filename": p.filename,
                    "pdf_url": p.pdf_url,
                    "siret": p.siret,
                    "raison_sociale": p.raison_sociale,
                    "ville": p.ville,
                    "effectif": p.effectif,
                    "inscrits": p.inscrits,
                    "date_invitation": p.date_invitation.isoformat() if p.date_invitation else None,
                    "date_election": p.date_election.isoformat() if p.date_election else None,
                    "uploaded_at": p.uploaded_at.isoformat() if p.uploaded_at else None,
                    "is_priority": p.is_priority,
                    "has_cgt_history": p.has_cgt_history,
                    "fd": p.fd
                }
                for p in paps
            ]
        }
    except Exception as e:
        logger.error(f"Erreur API PAPs UD {numero_departement}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/fd/{code_fd}/paps")
async def api_get_paps_by_fd(
    code_fd: str,
    db: Session = Depends(get_session)
):
    """
    API JSON pour récupérer les PAPs d'une FD.

    Utile pour intégrations externes ou applications mobiles.
    """
    try:
        # Gérer le cas "sans fd"
        if code_fd.lower() == "sans-fd":
            code_fd = "sans fd"

        paps = db.query(PAPDocument).filter(
            PAPDocument.fd == code_fd,
            PAPDocument.is_active == True
        ).order_by(desc(PAPDocument.uploaded_at)).all()

        return {
            "success": True,
            "code_fd": code_fd,
            "total": len(paps),
            "paps": [
                {
                    "id": p.id,
                    "filename": p.filename,
                    "pdf_url": p.pdf_url,
                    "siret": p.siret,
                    "raison_sociale": p.raison_sociale,
                    "ville": p.ville,
                    "effectif": p.effectif,
                    "inscrits": p.inscrits,
                    "date_invitation": p.date_invitation.isoformat() if p.date_invitation else None,
                    "date_election": p.date_election.isoformat() if p.date_election else None,
                    "uploaded_at": p.uploaded_at.isoformat() if p.uploaded_at else None,
                    "is_priority": p.is_priority,
                    "has_cgt_history": p.has_cgt_history,
                    "numero_departement": p.numero_departement,
                    "nom_departement": p.nom_departement
                }
                for p in paps
            ]
        }
    except Exception as e:
        logger.error(f"Erreur API PAPs FD {code_fd}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
