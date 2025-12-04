"""
Service de gestion de campagnes PAP (Protocole d'Accord Préélectoral).

Ce service permet d'analyser des PAP en masse, d'identifier les cibles prioritaires
et de générer des emails différenciés pour les UD.
"""

import logging
import json
import os
from typing import Dict, Any, List, Optional
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models import SiretSummary

logger = logging.getLogger(__name__)


class PAPCampaignService:
    """Service pour gérer les campagnes d'envoi de PAP aux UD."""

    # Seuils pour définir un PAP à enjeux
    SEUIL_EFFECTIF_ENJEUX = 1000
    SEUIL_RATIO_INSCRITS_DEPT = 1.5  # 150% de la moyenne du département

    # Charger les contacts UD au démarrage de la classe
    _ud_contacts = None
    _referents_regionaux = None

    def __init__(self, db: Session):
        """
        Initialise le service de campagne PAP.

        Args:
            db: Session de base de données
        """
        self.db = db
        self._load_ud_contacts()
        self._load_referents_regionaux()

    def _load_ud_contacts(self):
        """Charge les contacts des UD depuis le fichier JSON."""
        if PAPCampaignService._ud_contacts is None:
            try:
                contacts_path = Path(__file__).parent.parent / 'data' / 'ud_contacts.json'
                with open(contacts_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    PAPCampaignService._ud_contacts = data.get('unions_departementales', {})
                    logger.info(f"✅ Contacts UD chargés: {len(PAPCampaignService._ud_contacts)} départements")
            except Exception as e:
                logger.error(f"❌ Erreur chargement contacts UD: {str(e)}")
                PAPCampaignService._ud_contacts = {}

    def _load_referents_regionaux(self):
        """Charge les référents régionaux depuis le fichier JSON."""
        if PAPCampaignService._referents_regionaux is None:
            try:
                referents_path = Path(__file__).parent.parent / 'data' / 'referents_regionaux.json'
                with open(referents_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    PAPCampaignService._referents_regionaux = {
                        'referents': data.get('referents', {}),
                        'departement_to_referent': data.get('departement_to_referent', {})
                    }
                    logger.info(f"✅ Référents régionaux chargés: {len(data.get('referents', {}))} référents")
            except Exception as e:
                logger.error(f"❌ Erreur chargement référents régionaux: {str(e)}")
                PAPCampaignService._referents_regionaux = {'referents': {}, 'departement_to_referent': {}}

    @staticmethod
    def get_ud_contact(departement: str) -> Dict[str, str]:
        """
        Récupère les informations de contact d'une UD.

        Args:
            departement: Code département (ex: "75", "13", "20A")

        Returns:
            Dictionnaire avec email et responsable
        """
        if PAPCampaignService._ud_contacts is None:
            return {
                'email': f'ud{departement.lower()}@cgt.fr',
                'responsable': None
            }

        # Essayer avec le code département tel quel
        contact = PAPCampaignService._ud_contacts.get(departement.upper())
        if contact:
            return contact

        # Essayer sans le zéro initial (ex: "01" -> "1")
        if departement.startswith('0') and len(departement) == 2:
            contact = PAPCampaignService._ud_contacts.get(departement[1])
            if contact:
                return contact

        # Fallback
        return {
            'email': f'ud{departement.lower()}@cgt.fr',
            'responsable': None
        }

    @staticmethod
    def get_referent_regional(departement: str) -> Optional[Dict[str, str]]:
        """
        Récupère les informations du référent régional pour un département.

        Args:
            departement: Code département (ex: "75", "13", "20A")

        Returns:
            Dictionnaire avec nom et email du référent, ou None si non trouvé
        """
        if PAPCampaignService._referents_regionaux is None:
            return None

        # Normaliser le code département
        dept_key = departement.upper().lstrip('0') if departement.isdigit() else departement.upper()

        # Chercher dans le mapping département -> référent
        dept_to_ref = PAPCampaignService._referents_regionaux.get('departement_to_referent', {})

        # Essayer avec le département tel quel
        referent_key = dept_to_ref.get(departement)
        if not referent_key:
            # Essayer avec zéro devant si numérique
            if departement.isdigit() and len(departement) == 1:
                referent_key = dept_to_ref.get(f'0{departement}')

        if not referent_key:
            return None

        # Récupérer les infos du référent
        referents = PAPCampaignService._referents_regionaux.get('referents', {})
        referent_data = referents.get(referent_key)

        if referent_data:
            return {
                'nom': referent_data.get('nom'),
                'email': referent_data.get('email'),
                'regions': ', '.join(referent_data.get('regions', []))
            }

        return None

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
        date_invitation = pap_data.get('date_invitation', 'N/A')
        idcc = pap_data.get('idcc', 'N/A')
        fd = pap_data.get('fd', 'N/A')
        ud = pap_data.get('ud', 'UD XX')
        priority_reasons = pap_data.get('priority_reason', [])
        pdf_url = pap_data.get('pdf_url')
        departement = pap_data.get('departement', 'XX')

        # Récupérer les vraies informations de contact UD
        ud_contact = PAPCampaignService.get_ud_contact(departement)
        recipient_email = ud_contact.get('email', f'ud{departement.lower()}@cgt.fr')
        responsable_nom = ud_contact.get('responsable')

        # Récupérer le référent régional
        referent = PAPCampaignService.get_referent_regional(departement)

        # Vérifier l'historique CGT
        historique_pv = pap_data.get('historique_pv', {})
        has_cgt_history = historique_pv.get('found', False)
        cgt_c3 = historique_pv.get('presence_cgt_c3', False)
        cgt_c4 = historique_pv.get('presence_cgt_c4', False)
        has_cgt_presence = cgt_c3 or cgt_c4

        # Salutation personnalisée si le responsable est connu
        salutation = f"Bonjour {responsable_nom}," if responsable_nom else "Bonjour,"

        # Construire le bloc du lien PDF en avant si disponible
        pdf_block = ""
        if pdf_url:
            app_url = os.getenv('APP_URL', 'http://localhost:8000')
            full_pdf_url = f"{app_url}{pdf_url}"
            pdf_block = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📎 DOCUMENT PAP EN LIGNE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

👉 Accès direct au PAP :
{full_pdf_url}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

        if is_priority:
            # Email pour PAP à enjeux
            subject = f"🔥 PAP À ENJEUX - {raison_sociale} ({ville})"

            # Adapter le message selon la présence CGT
            if has_cgt_presence:
                intro = f"""{salutation}

⚠️ ATTENTION - PAP À ENJEUX - RENOUVELLEMENT ⚠️

Nous avons reçu une invitation à un Protocole d'Accord Préélectoral pour une cible prioritaire où la CGT est déjà présente.

🔄 CONTEXTE HISTORIQUE :"""
                if cgt_c3:
                    voix_cgt_c3 = historique_pv.get('voix_cgt_c3', 'N/A')
                    elus_cgt_c3 = historique_pv.get('elus_cgt_c3', 'N/A')
                    intro += f"\n• CGT présente au C3 (dernier cycle) - {voix_cgt_c3} voix - {elus_cgt_c3} élu(s)"
                if cgt_c4:
                    voix_cgt_c4 = historique_pv.get('voix_cgt_c4', 'N/A')
                    elus_cgt_c4 = historique_pv.get('elus_cgt_c4', 'N/A')
                    intro += f"\n• CGT présente au C4 (dernier cycle) - {voix_cgt_c4} voix - {elus_cgt_c4} élu(s)"
                intro += "\n\n⚡ OBJECTIF : RENFORCER NOTRE PRÉSENCE\n"
            else:
                intro = f"""{salutation}

⚠️ ATTENTION - PAP À ENJEUX - NOUVELLE IMPLANTATION ⚠️

Nous avons reçu une invitation à un Protocole d'Accord Préélectoral pour une cible prioritaire.

🎯 OPPORTUNITÉ : Entreprise sans historique CGT connu - Potentiel de nouvelle implantation !
"""

            body = intro + pdf_block + f"""
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
• Fédération : {fd}
• Union Départementale : {ud}

📅 La réunion de négociation est fixée au : {date_invitation}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 POURQUOI C'EST UN PAP À ENJEUX ?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
            for reason in priority_reasons:
                body += f"✓ {reason}\n"

            body += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Merci de traiter cette invitation en priorité et de mobiliser les moyens nécessaires.
"""

            # Ajouter les coordonnées du référent régional si disponible
            if referent:
                body += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👤 VOTRE RÉFÉRENT RÉGIONAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{referent['nom']}
📧 {referent['email']}
📍 {referent['regions']}

Pour toute question ou accompagnement, n'hésitez pas à contacter votre référent régional.

Cordialement,
Confédération CGT"""
            else:
                body += """
Cordialement,
Confédération CGT"""

        else:
            # Email standard
            subject = f"PAP - {raison_sociale} ({ville})"

            # Adapter le message selon la présence CGT
            if has_cgt_presence:
                intro = f"""{salutation}

Nous avons reçu une invitation à un Protocole d'Accord Préélectoral pour une entreprise où la CGT est déjà présente.

🔄 CONTEXTE HISTORIQUE :"""
                if cgt_c3:
                    voix_cgt_c3 = historique_pv.get('voix_cgt_c3', 'N/A')
                    elus_cgt_c3 = historique_pv.get('elus_cgt_c3', 'N/A')
                    intro += f"\n• CGT présente au C3 (dernier cycle) - {voix_cgt_c3} voix - {elus_cgt_c3} élu(s)"
                if cgt_c4:
                    voix_cgt_c4 = historique_pv.get('voix_cgt_c4', 'N/A')
                    elus_cgt_c4 = historique_pv.get('elus_cgt_c4', 'N/A')
                    intro += f"\n• CGT présente au C4 (dernier cycle) - {voix_cgt_c4} voix - {elus_cgt_c4} élu(s)"
                intro += "\n"
            else:
                intro = f"""{salutation}

Nous avons reçu une invitation à un Protocole d'Accord Préélectoral.

💡 Entreprise sans historique CGT connu - Opportunité de nouvelle implantation.
"""

            body = intro + pdf_block + f"""
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
• Fédération : {fd}
• Union Départementale : {ud}

📅 La réunion de négociation est fixée au : {date_invitation}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Cordialement,
Confédération CGT"""

        # Utiliser le vrai email de l'UD
        return {
            'subject': subject,
            'body': body,
            'recipient': recipient_email,
            'responsable': responsable_nom,
            'referent': referent
        }
