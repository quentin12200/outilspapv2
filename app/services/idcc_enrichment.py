"""
Service d'enrichissement automatique FD à partir des IDCC.

Principe: Toutes les entreprises avec un IDCC DOIVENT avoir une FD.
Ce service utilise la correspondance IDCC→FD extraite de la base PV.
"""
import json
from pathlib import Path
from typing import Optional, Dict
from collections import Counter
from sqlalchemy.orm import Session

from app.models import PVEvent


class IDCCEnrichmentService:
    """Service pour enrichir automatiquement les FD à partir des IDCC."""

    def __init__(self):
        self._mapping: Optional[Dict[str, str]] = None
        self._mapping_file = Path(__file__).parent.parent / "data" / "idcc_fd_mapping.json"

    def _load_mapping(self) -> Dict[str, str]:
        """Charge le mapping IDCC→FD depuis le fichier JSON."""
        if not self._mapping_file.exists():
            return {}

        try:
            with open(self._mapping_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("mapping", {})
        except Exception as e:
            print(f"⚠️  Erreur lecture du mapping IDCC→FD: {e}")
            return {}

    def _build_mapping_from_pv(self, session: Session) -> Dict[str, str]:
        """
        Construit le mapping IDCC→FD depuis la table Tous_PV.

        Pour chaque IDCC, on choisit la FD la plus fréquente parmi tous les PV.
        """
        # Récupérer tous les couples (IDCC, FD) des PV
        pv_pairs = session.query(PVEvent.idcc, PVEvent.fd).filter(
            PVEvent.idcc.isnot(None),
            PVEvent.idcc != "",
            PVEvent.fd.isnot(None),
            PVEvent.fd != ""
        ).all()

        if not pv_pairs:
            return {}

        # Grouper par IDCC et compter les FD
        idcc_to_fds = {}
        for idcc, fd in pv_pairs:
            idcc = idcc.strip()
            fd = fd.strip()
            if idcc not in idcc_to_fds:
                idcc_to_fds[idcc] = []
            idcc_to_fds[idcc].append(fd)

        # Pour chaque IDCC, choisir la FD la plus fréquente
        idcc_to_fd = {}
        for idcc, fds in idcc_to_fds.items():
            fd_counter = Counter(fds)
            most_common_fd = fd_counter.most_common(1)[0][0]
            idcc_to_fd[idcc] = most_common_fd

        return idcc_to_fd

    def _save_mapping(self, mapping: Dict[str, str]):
        """Sauvegarde le mapping dans un fichier JSON."""
        self._mapping_file.parent.mkdir(parents=True, exist_ok=True)

        from datetime import datetime
        output_data = {
            "description": "Table de correspondance IDCC → FD générée depuis la base PV",
            "generated_at": datetime.now().isoformat(),
            "total_entries": len(mapping),
            "mapping": mapping
        }

        with open(self._mapping_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

    def get_mapping(self, session: Session, force_rebuild: bool = False) -> Dict[str, str]:
        """
        Récupère le mapping IDCC→FD.

        Args:
            session: Session SQLAlchemy
            force_rebuild: Si True, reconstruit le mapping depuis les PV

        Returns:
            Dictionnaire {IDCC: FD}
        """
        if self._mapping is None or force_rebuild:
            if force_rebuild or not self._mapping_file.exists():
                # Construire depuis les PV
                self._mapping = self._build_mapping_from_pv(session)
                if self._mapping:
                    self._save_mapping(self._mapping)
            else:
                # Charger depuis le fichier
                self._mapping = self._load_mapping()

        return self._mapping or {}

    def get_fd_for_idcc(self, idcc: str, session: Session) -> Optional[str]:
        """
        Retourne la FD correspondant à un IDCC.

        Args:
            idcc: Code IDCC
            session: Session SQLAlchemy

        Returns:
            Code FD ou None si non trouvé
        """
        if not idcc:
            return None

        idcc = idcc.strip()
        mapping = self.get_mapping(session)
        return mapping.get(idcc)

    def enrich_fd(self, idcc: Optional[str], current_fd: Optional[str], session: Session) -> Optional[str]:
        """
        Enrichit une FD à partir d'un IDCC.

        Principe: Si l'IDCC est renseigné mais pas la FD, on la recherche
        automatiquement dans le mapping.

        Args:
            idcc: Code IDCC (peut être None)
            current_fd: FD actuelle (peut être None)
            session: Session SQLAlchemy

        Returns:
            FD enrichie ou current_fd si déjà renseignée
        """
        # Si la FD est déjà renseignée, on ne fait rien
        if current_fd and current_fd.strip():
            return current_fd

        # Si pas d'IDCC, on ne peut rien faire
        if not idcc or not idcc.strip():
            return current_fd

        # Chercher la FD correspondante
        fd = self.get_fd_for_idcc(idcc, session)
        return fd if fd else current_fd

    def rebuild_mapping(self, session: Session) -> int:
        """
        Reconstruit le mapping IDCC→FD depuis les PV.

        Returns:
            Nombre d'entrées dans le mapping
        """
        mapping = self._build_mapping_from_pv(session)
        if mapping:
            self._save_mapping(mapping)
            self._mapping = mapping
        return len(mapping)


# Instance singleton du service
_enrichment_service: Optional[IDCCEnrichmentService] = None


def get_idcc_enrichment_service() -> IDCCEnrichmentService:
    """Retourne l'instance singleton du service d'enrichissement."""
    global _enrichment_service
    if _enrichment_service is None:
        _enrichment_service = IDCCEnrichmentService()
    return _enrichment_service
