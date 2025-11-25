"""
Service de gestion de campagnes PAP (Protocole d'Accord Préélectoral).

Ce service permet d'analyser des PAP en masse, d'identifier les cibles prioritaires
et de générer des emails différenciés pour les UD.
"""

import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models import SiretSummary

logger = logging.getLogger(__name__)


class PAPCampaignService:
    """Service pour gérer les campagnes d'envoi de PAP aux UD."""

    # Seuils pour définir un PAP à enjeux
    SEUIL_EFFECTIF_ENJEUX = 1000
    SEUIL_RATIO_INSCRITS_DEPT = 1.5  # 150% de la moyenne du département

    def __init__(self, db: Session):
        """
        Initialise le service de campagne PAP.

        Args:
            db: Session de base de données
        """
        self.db = db

    def analyze_pap(self, pap_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyse un PAP et détermine s'il s'agit d'une cible prioritaire.

        Critères pour PAP à enjeux:
        - Effectif >= 1000 salariés
        - OU nombre d'inscrits important par rapport à la moyenne du département

        Args:
            pap_data: Données extraites du PAP (dict avec siret, effectif, inscrits, etc.)

        Returns:
            Dictionnaire enrichi avec is_priority, priority_reason, ud, etc.
        """
        result = {
            **pap_data,
            'is_priority': False,
            'priority_reason': [],
            'category': 'standard',
            'ud': None,
            'fd': None,
            'departement': None
        }

        # Extraire les données essentielles
        effectif = pap_data.get('effectif')
        inscrits = pap_data.get('inscrits')
        code_postal = pap_data.get('code_postal')
        siret = pap_data.get('siret')

        # Déterminer le département depuis le code postal
        if code_postal and len(str(code_postal)) >= 2:
            departement = str(code_postal)[:2]
            result['departement'] = departement
            result['ud'] = f"UD {departement}"

        # Critère 1 : Effectif >= 1000
        if effectif and isinstance(effectif, (int, float)) and effectif >= self.SEUIL_EFFECTIF_ENJEUX:
            result['is_priority'] = True
            result['priority_reason'].append(f"Effectif important: {effectif} salariés (≥ {self.SEUIL_EFFECTIF_ENJEUX})")
            result['category'] = 'enjeux'

        # Critère 2 : Inscrits importants par rapport au département
        if inscrits and isinstance(inscrits, (int, float)) and inscrits > 0 and departement:
            moyenne_dept = self._get_moyenne_inscrits_departement(departement)

            if moyenne_dept and inscrits >= (moyenne_dept * self.SEUIL_RATIO_INSCRITS_DEPT):
                result['is_priority'] = True
                result['priority_reason'].append(
                    f"Inscrits importants: {inscrits} électeurs "
                    f"(+{int((inscrits/moyenne_dept - 1) * 100)}% vs moyenne département: {int(moyenne_dept)})"
                )
                result['category'] = 'enjeux'

        # Récupérer les infos UD/FD depuis la base si SIRET connu
        if siret and self.db:
            try:
                summary = self.db.query(SiretSummary).filter(SiretSummary.siret == siret).first()
                if summary:
                    if summary.ud_c3 or summary.ud_c4:
                        result['ud'] = summary.ud_c3 or summary.ud_c4
                    if summary.fd_c3 or summary.fd_c4:
                        result['fd'] = summary.fd_c3 or summary.fd_c4
                    if summary.dep:
                        result['departement'] = summary.dep
                        if not result['ud']:
                            result['ud'] = f"UD {summary.dep}"
            except Exception as e:
                logger.warning(f"Erreur lors de la récupération des infos UD/FD pour {siret}: {str(e)}")

        return result

    def _get_moyenne_inscrits_departement(self, departement: str) -> Optional[float]:
        """
        Calcule la moyenne des inscrits dans les élections du département.

        Args:
            departement: Code département (ex: "75", "13")

        Returns:
            Moyenne des inscrits ou None si pas de données
        """
        try:
            if not self.db:
                logger.warning("Session DB non disponible pour calcul moyenne")
                return None

            # Calculer la moyenne des inscrits dans le département (collèges 3 et 4)
            result = self.db.query(
                func.avg(
                    func.coalesce(SiretSummary.inscrits_c3, 0) +
                    func.coalesce(SiretSummary.inscrits_c4, 0)
                )
            ).filter(
                SiretSummary.dep == departement,
                (SiretSummary.inscrits_c3.isnot(None)) | (SiretSummary.inscrits_c4.isnot(None))
            ).scalar()

            return float(result) if result else None

        except Exception as e:
            logger.warning(f"Erreur calcul moyenne inscrits département {departement}: {str(e)}")
            return None

    def analyze_batch(self, paps_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyse un lot de PAP et les classe par priorité.

        Args:
            paps_data: Liste de données PAP extraites

        Returns:
            Dictionnaire avec statistiques et PAP classés
        """
        results = {
            'total': len(paps_data),
            'enjeux': [],
            'standard': [],
            'stats': {
                'count_enjeux': 0,
                'count_standard': 0,
                'by_ud': {},
                'by_department': {}
            }
        }

        for pap_data in paps_data:
            analyzed = self.analyze_pap(pap_data)

            if analyzed['is_priority']:
                results['enjeux'].append(analyzed)
                results['stats']['count_enjeux'] += 1
            else:
                results['standard'].append(analyzed)
                results['stats']['count_standard'] += 1

            # Stats par UD
            ud = analyzed.get('ud', 'Inconnu')
            if ud not in results['stats']['by_ud']:
                results['stats']['by_ud'][ud] = {'enjeux': 0, 'standard': 0}

            if analyzed['is_priority']:
                results['stats']['by_ud'][ud]['enjeux'] += 1
            else:
                results['stats']['by_ud'][ud]['standard'] += 1

            # Stats par département
            dept = analyzed.get('departement', 'Inconnu')
            if dept not in results['stats']['by_department']:
                results['stats']['by_department'][dept] = {'enjeux': 0, 'standard': 0}

            if analyzed['is_priority']:
                results['stats']['by_department'][dept]['enjeux'] += 1
            else:
                results['stats']['by_department'][dept]['standard'] += 1

        return results

    @staticmethod
    def generate_email_content(pap_data: Dict[str, Any], is_priority: bool = False) -> Dict[str, str]:
        """
        Génère le contenu d'un email pour un PAP.

        Args:
            pap_data: Données analysées du PAP
            is_priority: True si PAP à enjeux, False sinon

        Returns:
            Dictionnaire avec subject, body, recipient
        """
        raison_sociale = pap_data.get('raison_sociale', 'Entreprise')
        siret = pap_data.get('siret', 'N/A')
        ville = pap_data.get('ville', 'N/A')
        code_postal = pap_data.get('code_postal', 'N/A')
        effectif = pap_data.get('effectif', 'N/A')
        inscrits = pap_data.get('inscrits', 'N/A')
        date_election = pap_data.get('date_election', 'N/A')
        idcc = pap_data.get('idcc', 'N/A')
        ud = pap_data.get('ud', 'UD XX')
        priority_reasons = pap_data.get('priority_reason', [])
        pdf_url = pap_data.get('pdf_url')

        if is_priority:
            # Email pour PAP à enjeux
            subject = f"🔥 PAP À ENJEUX - {raison_sociale} ({ville})"

            body = f"""Bonjour,

⚠️ ATTENTION - PAP À ENJEUX ⚠️

Nous avons reçu une invitation à un Protocole d'Accord Préélectoral pour une cible prioritaire :

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 INFORMATIONS ENTREPRISE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• Raison sociale : {raison_sociale}
• SIRET : {siret}
• Localisation : {code_postal} {ville}
• Effectif : {effectif} salarié(s)
• Inscrits : {inscrits} électeur(s)
• Date élection : {date_election}
• IDCC : {idcc}
• Union Départementale : {ud}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 POURQUOI C'EST UN PAP À ENJEUX ?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
            for reason in priority_reasons:
                body += f"✓ {reason}\n"

            # Ajouter le lien PDF si disponible
            if pdf_url:
                # Construire l'URL complète (à adapter selon votre domaine)
                full_pdf_url = f"https://votre-domaine.fr{pdf_url}"
                body += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📎 Document PAP disponible en ligne :
{full_pdf_url}

Merci de traiter cette invitation en priorité et de mobiliser les moyens nécessaires.

Cordialement,
Confédération CGT"""
            else:
                body += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Le document PAP complet est joint à cet email.

Merci de traiter cette invitation en priorité et de mobiliser les moyens nécessaires.

Cordialement,
Confédération CGT"""

        else:
            # Email standard
            subject = f"PAP - {raison_sociale} ({ville})"

            body = f"""Bonjour,

Nous avons reçu une invitation à un Protocole d'Accord Préélectoral :

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 INFORMATIONS ENTREPRISE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• Raison sociale : {raison_sociale}
• SIRET : {siret}
• Localisation : {code_postal} {ville}
• Effectif : {effectif} salarié(s)
• Inscrits : {inscrits} électeur(s)
• Date élection : {date_election}
• IDCC : {idcc}
• Union Départementale : {ud}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
            # Ajouter le lien PDF si disponible
            if pdf_url:
                # Construire l'URL complète (à adapter selon votre domaine)
                full_pdf_url = f"https://votre-domaine.fr{pdf_url}"
                body += f"""📎 Document PAP disponible en ligne :
{full_pdf_url}

Cordialement,
Confédération CGT"""
            else:
                body += f"""Le document PAP complet est joint à cet email.

Cordialement,
Confédération CGT"""

        # Déterminer le destinataire (email UD - pour l'instant un placeholder)
        recipient = f"ud{pap_data.get('departement', 'XX')}@cgt.fr"

        return {
            'subject': subject,
            'body': body,
            'recipient': recipient
        }
