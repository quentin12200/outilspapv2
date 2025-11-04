"""
Module pour gérer les filtres globaux (UD, FD, Région)
appliqués sur l'ensemble du site
"""
from typing import Optional
from fastapi import Request
from sqlalchemy.orm import Query


class GlobalFilters:
    """Class pour extraire et appliquer les filtres globaux"""

    def __init__(self, ud: Optional[str] = None, fd: Optional[str] = None, region: Optional[str] = None):
        self.ud = ud
        self.fd = fd
        self.region = region

    @classmethod
    def from_request(cls, request: Request) -> "GlobalFilters":
        """
        Extrait les filtres globaux depuis les query parameters de la requête

        Args:
            request: La requête FastAPI

        Returns:
            Instance de GlobalFilters avec les filtres extraits
        """
        # Vérifier d'abord dans les query params
        ud = request.query_params.get('global_ud')
        fd = request.query_params.get('global_fd')
        region = request.query_params.get('global_region')

        # Si pas dans les query params, vérifier dans les cookies (fallback)
        if not (ud or fd or region):
            ud = request.cookies.get('filter_ud')
            fd = request.cookies.get('filter_fd')
            region = request.cookies.get('filter_region')

        return cls(ud=ud, fd=fd, region=region)

    def has_filter(self) -> bool:
        """Vérifie si au moins un filtre est actif"""
        return bool(self.ud or self.fd or self.region)

    def apply_to_pv_query(self, query: Query) -> Query:
        """
        Applique les filtres globaux à une requête sur la table PVEvent

        Args:
            query: Query SQLAlchemy sur PVEvent

        Returns:
            Query filtrée
        """
        from .models import PVEvent

        if self.ud:
            query = query.filter(PVEvent.ud == self.ud)
        elif self.fd:
            query = query.filter(PVEvent.fd == self.fd)
        elif self.region:
            query = query.filter(PVEvent.region == self.region)

        return query

    def apply_to_invitation_query(self, query: Query) -> Query:
        """
        Applique les filtres globaux à une requête sur la table Invitation

        Args:
            query: Query SQLAlchemy sur Invitation

        Returns:
            Query filtrée
        """
        from .models import Invitation
        from sqlalchemy.orm import aliased

        if self.ud:
            query = query.filter(Invitation.ud == self.ud)
        elif self.fd:
            query = query.filter(Invitation.fd == self.fd)
        elif self.region:
            # Invitation ne possède pas directement la région :
            # on joint sur SiretSummary pour récupérer la région associée.
            from .models import SiretSummary

            summary_alias = aliased(SiretSummary)
            query = query.join(
                summary_alias,
                summary_alias.siret == Invitation.siret,
                isouter=False,
            ).filter(summary_alias.region == self.region)

        return query

    def apply_to_siret_summary_query(self, query: Query) -> Query:
        """
        Applique les filtres globaux à une requête sur la table SiretSummary

        Args:
            query: Query SQLAlchemy sur SiretSummary

        Returns:
            Query filtrée
        """
        from .models import SiretSummary

        if self.ud:
            # SiretSummary a ud_c3 et ud_c4, on filtre sur les deux
            from sqlalchemy import or_
            query = query.filter(or_(
                SiretSummary.ud_c3 == self.ud,
                SiretSummary.ud_c4 == self.ud
            ))
        elif self.fd:
            # SiretSummary a fd_c3 et fd_c4, on filtre sur les deux
            from sqlalchemy import or_
            query = query.filter(or_(
                SiretSummary.fd_c3 == self.fd,
                SiretSummary.fd_c4 == self.fd
            ))
        elif self.region:
            query = query.filter(SiretSummary.region == self.region)

        return query

    def get_label(self) -> str:
        """Retourne un label lisible du filtre actif"""
        if self.ud:
            return f"UD: {self.ud}"
        elif self.fd:
            return f"FD: {self.fd}"
        elif self.region:
            return f"Région: {self.region}"
        return "Aucun filtre"

    def to_dict(self) -> dict:
        """Convertit les filtres en dictionnaire"""
        return {
            'ud': self.ud,
            'fd': self.fd,
            'region': self.region,
            'has_filter': self.has_filter(),
            'label': self.get_label()
        }
