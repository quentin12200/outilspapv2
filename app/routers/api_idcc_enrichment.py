"""
Routes API pour l'enrichissement automatique IDCC → FD.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..db import get_session
from ..models import Invitation
from ..services.idcc_enrichment import get_idcc_enrichment_service


router = APIRouter(prefix="/api/idcc", tags=["idcc-enrichment"])


@router.get("/mapping/stats")
def get_mapping_stats(db: Session = Depends(get_session)):
    """
    Retourne les statistiques sur le mapping IDCC → FD.
    """
    enrichment_service = get_idcc_enrichment_service()
    mapping = enrichment_service.get_mapping(db)

    return {
        "total_mappings": len(mapping),
        "sample": dict(list(mapping.items())[:10]) if mapping else {},
        "message": "Mapping IDCC → FD chargé avec succès" if mapping else "Aucun mapping disponible"
    }


@router.post("/mapping/rebuild")
def rebuild_mapping(db: Session = Depends(get_session)):
    """
    Reconstruit le mapping IDCC → FD depuis la table Tous_PV.

    Cette opération analyse tous les PV pour créer la correspondance IDCC → FD.
    """
    enrichment_service = get_idcc_enrichment_service()

    try:
        count = enrichment_service.rebuild_mapping(db)

        if count == 0:
            return {
                "success": False,
                "message": "Aucune donnée trouvée dans la table Tous_PV. Assurez-vous que la base de données contient les PV.",
                "mappings_created": 0
            }

        return {
            "success": True,
            "message": f"Mapping reconstruit avec succès",
            "mappings_created": count
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la reconstruction du mapping: {str(e)}"
        )


@router.get("/invitations/missing-fd")
def get_invitations_missing_fd(db: Session = Depends(get_session)):
    """
    Retourne les statistiques sur les invitations avec IDCC mais sans FD.

    Ces invitations sont problématiques car toutes les entreprises avec un IDCC
    DOIVENT avoir une FD.
    """
    # Total d'invitations
    total = db.query(func.count(Invitation.id)).scalar() or 0

    # Invitations avec IDCC
    with_idcc = db.query(func.count(Invitation.id)).filter(
        Invitation.idcc.isnot(None),
        Invitation.idcc != ""
    ).scalar() or 0

    # Invitations avec IDCC mais sans FD (PROBLÈME!)
    missing_fd = db.query(func.count(Invitation.id)).filter(
        Invitation.idcc.isnot(None),
        Invitation.idcc != "",
        (Invitation.fd.is_(None) | (Invitation.fd == ""))
    ).scalar() or 0

    # Exemples
    examples = []
    if missing_fd > 0:
        sample = db.query(Invitation).filter(
            Invitation.idcc.isnot(None),
            Invitation.idcc != "",
            (Invitation.fd.is_(None) | (Invitation.fd == ""))
        ).limit(5).all()

        examples = [
            {
                "id": inv.id,
                "siret": inv.siret,
                "idcc": inv.idcc,
                "fd": inv.fd,
                "denomination": inv.denomination
            }
            for inv in sample
        ]

    return {
        "total_invitations": total,
        "with_idcc": with_idcc,
        "missing_fd": missing_fd,
        "percentage_missing": round(100 * missing_fd / with_idcc, 1) if with_idcc > 0 else 0,
        "examples": examples,
        "warning": "Ces invitations DOIVENT avoir une FD!" if missing_fd > 0 else None
    }


@router.post("/invitations/enrich-all")
def enrich_all_invitations(db: Session = Depends(get_session)):
    """
    Enrichit en masse toutes les invitations qui ont un IDCC mais pas de FD.

    Principe: Toutes les entreprises avec un IDCC DOIVENT avoir une FD.
    Cette route applique automatiquement la correspondance depuis la base PV.
    """
    enrichment_service = get_idcc_enrichment_service()

    # Obtenir le mapping
    mapping = enrichment_service.get_mapping(db)

    if not mapping:
        return {
            "success": False,
            "message": "Aucun mapping IDCC → FD disponible. Veuillez d'abord reconstruire le mapping depuis les PV.",
            "enriched": 0
        }

    # Trouver les invitations à enrichir
    invitations = db.query(Invitation).filter(
        Invitation.idcc.isnot(None),
        Invitation.idcc != "",
        (Invitation.fd.is_(None) | (Invitation.fd == ""))
    ).all()

    if not invitations:
        return {
            "success": True,
            "message": "Toutes les invitations avec IDCC ont déjà une FD",
            "enriched": 0
        }

    # Enrichir
    enriched_count = 0
    not_found_idcc = set()

    for invitation in invitations:
        idcc = invitation.idcc.strip()

        if idcc in mapping:
            invitation.fd = mapping[idcc]
            enriched_count += 1
        else:
            not_found_idcc.add(idcc)

    # Commit
    db.commit()

    return {
        "success": True,
        "message": f"{enriched_count} invitations enrichies avec leur FD",
        "enriched": enriched_count,
        "total_to_enrich": len(invitations),
        "idcc_not_found": list(not_found_idcc) if not_found_idcc else [],
        "idcc_not_found_count": len(not_found_idcc)
    }
