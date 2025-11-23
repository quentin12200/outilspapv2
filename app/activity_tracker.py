"""
Utilitaire pour suivre l'activité des utilisateurs.

Permet de logger les accès aux ressources et d'afficher un historique
dans la section "Reprendre mon travail".
"""

from datetime import datetime
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from .models import UserActivity, User


def track_activity(
    db: Session,
    user: User,
    activity_type: str,
    resource_id: Optional[str] = None,
    resource_name: Optional[str] = None,
    extra_data: Optional[Dict[str, Any]] = None
):
    """
    Enregistre une activité utilisateur.

    Args:
        db: Session de base de données
        user: Utilisateur qui effectue l'action
        activity_type: Type d'activité (ex: "cartographie_view", "retroplanning_view")
        resource_id: Identifiant de la ressource (optionnel)
        resource_name: Nom de la ressource (optionnel)
        extra_data: Métadonnées supplémentaires (optionnel)
    """
    if not user:
        return

    # Vérifier si une activité similaire existe dans les dernières 5 minutes
    # Pour éviter les doublons
    from datetime import timedelta
    recent_cutoff = datetime.now() - timedelta(minutes=5)

    existing = db.query(UserActivity).filter(
        UserActivity.user_id == user.id,
        UserActivity.activity_type == activity_type,
        UserActivity.accessed_at >= recent_cutoff
    )

    if resource_id:
        existing = existing.filter(UserActivity.resource_id == resource_id)

    if existing.first():
        # Activité similaire récente trouvée, on ne crée pas de doublon
        return

    # Créer la nouvelle activité
    activity = UserActivity(
        user_id=user.id,
        activity_type=activity_type,
        resource_id=resource_id,
        resource_name=resource_name,
        extra_data=extra_data,
        accessed_at=datetime.now()
    )

    db.add(activity)
    db.commit()


def track_cartographie_view(db: Session, user: User, cartographie_id: int, nom_entreprise: str):
    """Enregistre la consultation d'une cartographie."""
    track_activity(
        db=db,
        user=user,
        activity_type="cartographie_view",
        resource_id=str(cartographie_id),
        resource_name=nom_entreprise
    )


def track_retroplanning_view(db: Session, user: User, retroplanning_id: int, titre: str):
    """Enregistre la consultation d'un rétroplanning."""
    track_activity(
        db=db,
        user=user,
        activity_type="retroplanning_view",
        resource_id=str(retroplanning_id),
        resource_name=titre
    )


def track_stats_view(db: Session, user: User):
    """Enregistre la consultation de la page statistiques."""
    track_activity(
        db=db,
        user=user,
        activity_type="stats_view",
        resource_name="Statistiques PAP/CSE"
    )


def track_invitations_view(db: Session, user: User, filters: Optional[Dict[str, Any]] = None):
    """Enregistre la consultation de la page invitations."""
    track_activity(
        db=db,
        user=user,
        activity_type="invitations_view",
        resource_name="Invitations PAP Cycle 5",
        extra_data=filters
    )


def track_ciblage_view(db: Session, user: User):
    """Enregistre la consultation de la page ciblage."""
    track_activity(
        db=db,
        user=user,
        activity_type="ciblage_view",
        resource_name="Ciblage d'entreprises"
    )


def track_guide_view(db: Session, user: User):
    """Enregistre la consultation du guide d'exploitation."""
    track_activity(
        db=db,
        user=user,
        activity_type="guide_view",
        resource_name="Guide d'exploitation"
    )


def cleanup_old_activities(db: Session, days: int = 30):
    """
    Nettoie les anciennes activités.

    Args:
        db: Session de base de données
        days: Nombre de jours à conserver (par défaut: 30)
    """
    from datetime import timedelta
    cutoff_date = datetime.now() - timedelta(days=days)

    db.query(UserActivity).filter(
        UserActivity.accessed_at < cutoff_date
    ).delete()

    db.commit()
