"""
Système de notifications pour alerter les utilisateurs.

Gère les badges de notification pour :
- Invitations PAP en retard (>60 jours)
- Élections dans les 15 jours
- Nouvelles invitations scannées
"""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from .models import Invitation


def get_notifications_count(db: Session) -> dict:
    """
    Calcule le nombre de notifications pour chaque catégorie.

    Returns:
        dict: Dictionnaire avec les compteurs de notifications
        {
            "invitations_retard": int,
            "elections_proches": int,
            "nouvelles_invitations": int,
            "total": int
        }
    """
    now = datetime.now()

    # Invitations en retard (>60 jours sans retour)
    date_60_jours = now - timedelta(days=60)
    invitations_retard = db.query(func.count(Invitation.id)).filter(
        and_(
            Invitation.date_invit.isnot(None),
            Invitation.date_invit < date_60_jours,
            Invitation.est_actif == True
        )
    ).scalar() or 0

    # Élections dans les 15 jours (désactivé - champ date_1er_tour inexistant)
    elections_proches = 0

    # Nouvelles invitations scannées (dernières 7 jours)
    date_7_jours = now - timedelta(days=7)
    nouvelles_invitations = db.query(func.count(Invitation.id)).filter(
        and_(
            Invitation.date_invit.isnot(None),
            Invitation.date_invit >= date_7_jours,
            Invitation.source == "Scan automatique",
            Invitation.est_actif == True
        )
    ).scalar() or 0

    total = invitations_retard + elections_proches + nouvelles_invitations

    return {
        "invitations_retard": invitations_retard,
        "elections_proches": elections_proches,
        "nouvelles_invitations": nouvelles_invitations,
        "total": total
    }


def get_notification_details(db: Session) -> dict:
    """
    Récupère les détails des notifications avec les listes d'éléments.

    Returns:
        dict: Dictionnaire avec les détails de chaque notification
    """
    now = datetime.now()

    # Invitations en retard
    date_60_jours = now - timedelta(days=60)
    invitations_retard_list = db.query(Invitation).filter(
        and_(
            Invitation.date_invit.isnot(None),
            Invitation.date_invit < date_60_jours,
            Invitation.est_actif == True
        )
    ).order_by(Invitation.date_invit.asc()).limit(50).all()

    # Élections proches (désactivé - champ date_1er_tour inexistant)
    elections_proches_list = []

    # Nouvelles invitations
    date_7_jours = now - timedelta(days=7)
    nouvelles_invitations_list = db.query(Invitation).filter(
        and_(
            Invitation.date_invit.isnot(None),
            Invitation.date_invit >= date_7_jours,
            Invitation.source == "Scan automatique",
            Invitation.est_actif == True
        )
    ).order_by(Invitation.date_invit.desc()).limit(50).all()

    return {
        "invitations_retard": [
            {
                "id": inv.id,
                "raison_sociale": inv.denomination,  # denomination dans le modèle Invitation
                "ville": inv.commune,  # commune dans le modèle Invitation
                "date_invitation": inv.date_invit,
                "jours_retard": (now.date() - inv.date_invit).days if inv.date_invit else 0
            }
            for inv in invitations_retard_list
        ],
        "elections_proches": [],
        "nouvelles_invitations": [
            {
                "id": inv.id,
                "raison_sociale": inv.denomination,  # denomination dans le modèle Invitation
                "ville": inv.commune,  # commune dans le modèle Invitation
                "date_invit": inv.date_invit,
                "jours_depuis": (now.date() - inv.date_invit).days if inv.date_invit else 0
            }
            for inv in nouvelles_invitations_list
        ]
    }
