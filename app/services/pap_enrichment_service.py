"""
Service d'enrichissement complet pour les PAP.

Ce service coordonne l'extraction, l'enrichissement et la recherche d'historique
pour chaque PAP scanné.

Workflow:
1. Extraction GPT-4 Vision
2. Enrichissement Pappers API
3. Enrichissement Sirene API (fallback)
4. Recherche dans la base de données des PV
5. Calcul des données dérivées (UD, FD, etc.)
"""

import logging
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import or_
from datetime import datetime

from ..models import SiretSummary, PVEvent, Invitation
from .document_extractor import DocumentExtractor
from .pappers_api import PappersAPI
from .sirene_api import SireneAPI
from .pap_campaign_service import PAPCampaignService

logger = logging.getLogger(__name__)


class PAPEnrichmentService:
    """Service pour enrichir les PAP avec toutes les sources de données disponibles."""

    def __init__(self, db: Session):
        """
        Initialise le service d'enrichissement.

        Args:
            db: Session de base de données
        """
        self.db = db
        self.extractor = DocumentExtractor()
        self.pappers = PappersAPI()
        self.sirene = SireneAPI()
        self.campaign_service = PAPCampaignService(db)

    async def enrich_pap_from_pdf(
        self,
        pdf_data: bytes,
        filename: str,
        is_pdf: bool = True
    ) -> Dict[str, Any]:
        """
        Enrichit un PAP depuis un PDF avec toutes les sources de données.

        Args:
            pdf_data: Données du PDF
            filename: Nom du fichier original
            is_pdf: True si c'est un PDF (sinon image)

        Returns:
            Dictionnaire enrichi avec:
            - Données extraites par GPT-4
            - Données Pappers/Sirene
            - Historique PV depuis la base
            - Classification enjeux/standard
            - Recommandations UD/FD
        """
        logger.info(f"📄 Début enrichissement PAP: {filename}")

        # Étape 1: Extraction GPT-4 + enrichissement Pappers/Sirene (déjà intégré)
        extracted_data = await self.extractor.extract_from_document(
            pdf_data,
            is_pdf=is_pdf
        )

        extracted_data['filename'] = filename

        # Étape 2: Recherche dans la base de données des PV
        siret = extracted_data.get('siret')
        if siret and self._is_valid_siret(siret):
            logger.info(f"🔍 Recherche historique PV pour SIRET: {siret}")

            # Récupérer le résumé SIRET s'il existe
            siret_summary = self._get_siret_summary(siret)
            if siret_summary:
                extracted_data['historique_pv'] = self._format_siret_summary(siret_summary)
                logger.info(f"✅ Historique PV trouvé pour {siret}")

                # Utiliser les données de la base si manquantes
                if not extracted_data.get('ud') and siret_summary.ud_c3:
                    extracted_data['ud'] = siret_summary.ud_c3
                if not extracted_data.get('fd') and siret_summary.fd_c3:
                    extracted_data['fd'] = siret_summary.fd_c3
            else:
                extracted_data['historique_pv'] = {
                    'found': False,
                    'message': 'Aucun historique PV trouvé dans la base'
                }
                logger.info(f"ℹ️ Aucun historique PV pour {siret}")

            # Récupérer les événements PV détaillés
            pv_events = self._get_pv_events(siret)
            if pv_events:
                extracted_data['historique_pv']['evenements'] = pv_events
                logger.info(f"✅ {len(pv_events)} événements PV trouvés")

            # Récupérer les anciennes invitations
            old_invitations = self._get_old_invitations(siret)
            if old_invitations:
                extracted_data['historique_pv']['anciennes_invitations'] = old_invitations
                logger.info(f"✅ {len(old_invitations)} anciennes invitations trouvées")

        # Étape 3: Classification enjeux/standard
        analyzed = self.campaign_service.analyze_pap(extracted_data)

        # Étape 4: Enrichir avec les données calculées
        enriched_data = {
            **extracted_data,
            **analyzed,
            'enrichment_timestamp': datetime.now().isoformat(),
            'enrichment_sources': self._get_enrichment_sources(extracted_data)
        }

        logger.info(f"✅ Enrichissement terminé pour {filename}")
        logger.info(f"   - SIRET: {enriched_data.get('siret', 'N/A')}")
        logger.info(f"   - Raison sociale: {enriched_data.get('raison_sociale', 'N/A')}")
        logger.info(f"   - Catégorie: {enriched_data.get('category', 'N/A')}")
        logger.info(f"   - UD: {enriched_data.get('ud', 'N/A')}")
        logger.info(f"   - Historique PV: {'Oui' if enriched_data.get('historique_pv', {}).get('found') else 'Non'}")

        return enriched_data

    async def enrich_pap_batch(
        self,
        files_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Enrichit un batch de PAP.

        Args:
            files_data: Liste de dicts avec 'data' (bytes), 'filename', 'is_pdf'

        Returns:
            Résultats d'analyse batch avec données enrichies
        """
        logger.info(f"🚀 Enrichissement batch de {len(files_data)} fichiers")

        enriched_paps = []
        errors = []

        for i, file_info in enumerate(files_data, 1):
            try:
                enriched = await self.enrich_pap_from_pdf(
                    pdf_data=file_info['data'],
                    filename=file_info['filename'],
                    is_pdf=file_info.get('is_pdf', True)
                )
                enriched_paps.append(enriched)
            except Exception as e:
                logger.error(f"❌ Erreur enrichissement {file_info['filename']}: {str(e)}")
                errors.append({
                    'filename': file_info['filename'],
                    'error': str(e)
                })

        # Analyser le batch complet
        if enriched_paps:
            batch_analysis = self.campaign_service.analyze_batch(enriched_paps)
            batch_analysis['extraction_errors'] = errors
            batch_analysis['extraction_success_rate'] = (
                len(enriched_paps) / len(files_data) * 100 if files_data else 0
            )
            return batch_analysis
        else:
            return {
                'total': 0,
                'enjeux': [],
                'standard': [],
                'stats': {
                    'count_enjeux': 0,
                    'count_standard': 0,
                    'by_ud': {},
                    'by_department': {}
                },
                'extraction_errors': errors,
                'extraction_success_rate': 0
            }

    def _get_siret_summary(self, siret: str) -> Optional[SiretSummary]:
        """
        Récupère le résumé SIRET depuis la base de données.

        Args:
            siret: Numéro SIRET

        Returns:
            SiretSummary ou None
        """
        try:
            return self.db.query(SiretSummary).filter(
                SiretSummary.siret == siret
            ).first()
        except Exception as e:
            logger.error(f"Erreur récupération SiretSummary pour {siret}: {str(e)}")
            return None

    def _get_pv_events(self, siret: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Récupère les événements PV pour un SIRET.

        Args:
            siret: Numéro SIRET
            limit: Nombre max d'événements à retourner

        Returns:
            Liste d'événements PV formatés
        """
        try:
            events = self.db.query(PVEvent).filter(
                PVEvent.siret == siret
            ).order_by(PVEvent.date_scrutin.desc()).limit(limit).all()

            return [
                {
                    'id': event.id,
                    'cycle': event.cycle,
                    'date_scrutin': event.date_scrutin.isoformat() if event.date_scrutin else None,
                    'type_scrutin': event.type_scrutin,
                    'votants': event.votants,
                    'exprimes': event.exprimes,
                    'notes': event.notes,
                    'source': event.source
                }
                for event in events
            ]
        except Exception as e:
            logger.error(f"Erreur récupération PVEvents pour {siret}: {str(e)}")
            return []

    def _get_old_invitations(self, siret: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Récupère les anciennes invitations pour un SIRET.

        Args:
            siret: Numéro SIRET
            limit: Nombre max d'invitations à retourner

        Returns:
            Liste d'invitations formatées
        """
        try:
            invitations = self.db.query(Invitation).filter(
                Invitation.siret == siret
            ).order_by(Invitation.date_invit.desc()).limit(limit).all()

            return [
                {
                    'id': inv.id,
                    'date_invit': inv.date_invit.isoformat() if inv.date_invit else None,
                    'date_election': inv.date_election.isoformat() if inv.date_election else None,
                    'ud': inv.ud,
                    'fd': inv.fd,
                    'source': inv.source,
                    'effectif_connu': inv.effectif_connu
                }
                for inv in invitations
            ]
        except Exception as e:
            logger.error(f"Erreur récupération Invitations pour {siret}: {str(e)}")
            return []

    def _format_siret_summary(self, summary: SiretSummary) -> Dict[str, Any]:
        """
        Formate un SiretSummary pour l'affichage.

        Args:
            summary: Objet SiretSummary

        Returns:
            Dictionnaire formaté
        """
        return {
            'found': True,
            'siret': summary.siret,
            'raison_sociale': summary.raison_sociale,
            'adresse': summary.adresse,
            'code_postal': summary.code_postal,
            'commune': summary.commune,
            'ud_c3': summary.ud_c3,
            'ud_c4': summary.ud_c4,
            'fd_c3': summary.fd_c3,
            'fd_c4': summary.fd_c4,
            'dep': summary.dep,
            # Scores électoraux C3
            'voix_cgt_c3': summary.voix_cgt_c3,
            'voix_cfdt_c3': summary.voix_cfdt_c3,
            'voix_fo_c3': summary.voix_fo_c3,
            'voix_cftc_c3': summary.voix_cftc_c3,
            'voix_cfe_cgc_c3': summary.voix_cfe_cgc_c3,
            'voix_unsa_c3': summary.voix_unsa_c3,
            'voix_solidaires_c3': summary.voix_solidaires_c3,
            'voix_autre_c3': summary.voix_autre_c3,
            'voix_non_syndiques_c3': summary.voix_non_syndiques_c3,
            # Scores électoraux C4
            'voix_cgt_c4': summary.voix_cgt_c4,
            'voix_cfdt_c4': summary.voix_cfdt_c4,
            'voix_fo_c4': summary.voix_fo_c4,
            'voix_cftc_c4': summary.voix_cftc_c4,
            'voix_cfe_cgc_c4': summary.voix_cfe_cgc_c4,
            'voix_unsa_c4': summary.voix_unsa_c4,
            'voix_solidaires_c4': summary.voix_solidaires_c4,
            'voix_autre_c4': summary.voix_autre_c4,
            'voix_non_syndiques_c4': summary.voix_non_syndiques_c4,
            # Élus
            'elus_cgt_c3': summary.elus_cgt_c3,
            'elus_cgt_c4': summary.elus_cgt_c4,
            # Inscrits
            'inscrits_c3': summary.inscrits_c3,
            'inscrits_c4': summary.inscrits_c4,
            # Présence CGT
            'presence_cgt_c3': summary.presence_cgt_c3,
            'presence_cgt_c4': summary.presence_cgt_c4,
            # Dates
            'date_pv_c3': summary.date_pv_c3.isoformat() if summary.date_pv_c3 else None,
            'date_pv_c4': summary.date_pv_c4.isoformat() if summary.date_pv_c4 else None,
            'date_pap_c5': summary.date_pap_c5.isoformat() if summary.date_pap_c5 else None,
            'statut_pap': summary.statut_pap
        }

    @staticmethod
    def _is_valid_siret(siret: Optional[str]) -> bool:
        """Vérifie si un SIRET est valide."""
        if not siret:
            return False
        siret_clean = ''.join(c for c in str(siret) if c.isdigit())
        return len(siret_clean) == 14

    @staticmethod
    def _get_enrichment_sources(data: Dict[str, Any]) -> List[str]:
        """
        Identifie les sources utilisées pour l'enrichissement.

        Args:
            data: Données enrichies

        Returns:
            Liste des sources (GPT-4, Pappers, Sirene, Base PV, etc.)
        """
        sources = ['GPT-4 Vision']

        metadata = data.get('_metadata', {})
        if metadata.get('enriched_with_pappers'):
            sources.append('Pappers API')
        if metadata.get('enriched_with_sirene'):
            sources.append('Sirene API')
        if metadata.get('siret_auto_found'):
            sources.append('Recherche web GPT')

        if data.get('historique_pv', {}).get('found'):
            sources.append('Base de données PV')

        return sources
