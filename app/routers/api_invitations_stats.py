"""
Endpoint pour les statistiques enrichies des invitations PAP
"""
from fastapi import Depends, APIRouter, Request
from sqlalchemy.orm import Session, Query as SAQuery
from sqlalchemy import func, and_, or_
from datetime import datetime, timedelta, date
from typing import List, Dict, Any

from ..db import get_session
from ..models import Invitation
from ..filters import GlobalFilters

router = APIRouter(prefix="/api/invitations/stats", tags=["invitations_stats"])


@router.get("/enriched")
def get_enriched_invitation_stats(
    request: Request, db: Session = Depends(get_session)
):
    """
    Retourne des statistiques enrichies sur les invitations PAP :
    - Comptage par UD/FD/département
    - Alertes (invitations sans réponse > 30j, élections à venir dans 7j)
    - Statuts (en attente, réponse reçue, élection programmée, retard)
    """

    today = date.today()
    thirty_days_ago = today - timedelta(days=30)
    seven_days_ahead = today + timedelta(days=7)
    one_year_ahead = today + timedelta(days=365)

    global_filters = GlobalFilters.from_request(request)

    def _apply_invitation(query: SAQuery) -> SAQuery:
        if global_filters and global_filters.has_filter():
            return global_filters.apply_to_invitation_query(query)
        return query

    # === Comptage par UD ===
    invitations_by_ud = (
        _apply_invitation(
            db.query(
                Invitation.ud,
                func.count(Invitation.id).label("count")
            )
            .filter(Invitation.ud.isnot(None), Invitation.ud != "")
        )
        .group_by(Invitation.ud)
        .order_by(func.count(Invitation.id).desc())
        .all()
    )

    # === Comptage par FD ===
    invitations_by_fd = (
        _apply_invitation(
            db.query(
                Invitation.fd,
                func.count(Invitation.id).label("count")
            )
            .filter(Invitation.fd.isnot(None), Invitation.fd != "")
        )
        .group_by(Invitation.fd)
        .order_by(func.count(Invitation.id).desc())
        .all()
    )

    # === Comptage par département (extrait du code postal) ===
    invitations_by_dept = (
        _apply_invitation(
            db.query(
                func.substr(Invitation.code_postal, 1, 2).label("departement"),
                func.count(Invitation.id).label("count")
            )
            .filter(Invitation.code_postal.isnot(None), Invitation.code_postal != "")
        )
        .group_by(func.substr(Invitation.code_postal, 1, 2))
        .order_by(func.count(Invitation.id).desc())
        .all()
    )

    # === Invitations sans réponse depuis > 30 jours ===
    no_response_count = (
        _apply_invitation(db.query(func.count(Invitation.id)))
        .filter(
            Invitation.date_invit < thirty_days_ago,
            Invitation.date_reception.is_(None)
        )
        .scalar() or 0
    )

    # Détails des invitations sans réponse (top 10)
    no_response_details = (
        _apply_invitation(db.query(Invitation))
        .filter(
            Invitation.date_invit < thirty_days_ago,
            Invitation.date_reception.is_(None)
        )
        .order_by(Invitation.date_invit)
        .limit(10)
        .all()
    )

    # === Élections programmées dans les 7 prochains jours ===
    upcoming_elections_7days_count = (
        _apply_invitation(db.query(func.count(Invitation.id)))
        .filter(
            Invitation.date_election >= today,
            Invitation.date_election <= seven_days_ahead
        )
        .scalar() or 0
    )

    # Détails des élections à venir (7 jours)
    upcoming_elections_7days_details = (
        _apply_invitation(db.query(Invitation))
        .filter(
            Invitation.date_election >= today,
            Invitation.date_election <= seven_days_ahead
        )
        .order_by(Invitation.date_election)
        .limit(10)
        .all()
    )

    # === Élections programmées dans l'année à venir ===
    upcoming_elections_1year_count = (
        _apply_invitation(db.query(func.count(Invitation.id)))
        .filter(
            Invitation.date_election >= today,
            Invitation.date_election <= one_year_ahead
        )
        .scalar() or 0
    )

    # Détails des élections dans l'année
    upcoming_elections_1year_details = (
        _apply_invitation(db.query(Invitation))
        .filter(
            Invitation.date_election >= today,
            Invitation.date_election <= one_year_ahead
        )
        .order_by(Invitation.date_election)
        .limit(10)
        .all()
    )

    # === Statistiques de statut ===
    total_invitations = _apply_invitation(
        db.query(func.count(Invitation.id))
    ).scalar() or 0

    # Réponse reçue
    response_received_count = (
        _apply_invitation(db.query(func.count(Invitation.id)))
        .filter(Invitation.date_reception.isnot(None))
        .scalar() or 0
    )

    # Élection programmée
    election_programmed_count = (
        _apply_invitation(db.query(func.count(Invitation.id)))
        .filter(Invitation.date_election.isnot(None))
        .scalar() or 0
    )

    # En attente (pas de réponse, invitation < 30 jours)
    pending_count = (
        _apply_invitation(db.query(func.count(Invitation.id)))
        .filter(
            Invitation.date_reception.is_(None),
            Invitation.date_invit >= thirty_days_ago
        )
        .scalar() or 0
    )

    # Date dépassée (pas de réponse, invitation > 30 jours) = no_response_count

    return {
        "by_ud": [{"ud": row.ud, "count": row.count} for row in invitations_by_ud],
        "by_fd": [{"fd": row.fd, "count": row.count} for row in invitations_by_fd],
        "by_department": [{"department": row.departement, "count": row.count} for row in invitations_by_dept],
        "alerts": {
            "no_response_30days": {
                "count": no_response_count,
                "details": [
                    {
                        "siret": inv.siret,
                        "denomination": inv.denomination,
                        "date_invit": str(inv.date_invit) if inv.date_invit else None,
                        "days_since_invitation": (today - inv.date_invit).days if inv.date_invit else None
                    }
                    for inv in no_response_details
                ]
            },
            "upcoming_elections_7days": {
                "count": upcoming_elections_7days_count,
                "details": [
                    {
                        "siret": inv.siret,
                        "denomination": inv.denomination,
                        "date_election": str(inv.date_election) if inv.date_election else None,
                        "days_until_election": (inv.date_election - today).days if inv.date_election else None
                    }
                    for inv in upcoming_elections_7days_details
                ]
            },
            "upcoming_elections_1year": {
                "count": upcoming_elections_1year_count,
                "details": [
                    {
                        "siret": inv.siret,
                        "denomination": inv.denomination,
                        "date_election": str(inv.date_election) if inv.date_election else None,
                        "days_until_election": (inv.date_election - today).days if inv.date_election else None
                    }
                    for inv in upcoming_elections_1year_details
                ]
            }
        },
        "status_summary": {
            "total": total_invitations,
            "response_received": response_received_count,
            "election_programmed": election_programmed_count,
            "pending": pending_count,
            "overdue": no_response_count
        },
        "global_filter": global_filters.to_dict(),
    }

