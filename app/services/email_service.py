"""
Service d'intégration avec Resend pour l'envoi d'emails
Documentation: https://resend.com/docs/api-reference/emails/send
"""

import os
import resend
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ResendEmailError(Exception):
    """Exception levée en cas d'erreur avec l'API Resend"""
    pass


class ResendEmailService:
    """Client pour l'API Resend d'envoi d'emails"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialise le client API Resend

        Args:
            api_key: Clé API Resend
                    Si None, cherche dans RESEND_API_KEY
        """
        self.api_key = api_key or os.getenv("RESEND_API_KEY")

        if not self.api_key:
            logger.warning("[RESEND] ⚠️ NO API KEY configured - Email sending will fail")
            raise ResendEmailError("RESEND_API_KEY not configured")

        # Configure Resend avec la clé API
        resend.api_key = self.api_key

        logger.info(f"[RESEND] Service initialized with API key: {self.api_key[:8]}...{self.api_key[-4:]}")

        # Email par défaut pour l'envoi
        self.default_from_email = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev")
        logger.info(f"[RESEND] Default from email: {self.default_from_email}")

    async def send_email(
        self,
        to: str | List[str],
        subject: str,
        html: str,
        from_email: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        reply_to: Optional[str] = None,
        text: Optional[str] = None,
        tags: Optional[List[Dict[str, str]]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Envoie un email via Resend

        Args:
            to: Adresse(s) email du/des destinataire(s)
            subject: Sujet de l'email
            html: Contenu HTML de l'email
            from_email: Adresse email de l'expéditeur (optionnel)
            cc: Liste d'adresses en copie (optionnel)
            bcc: Liste d'adresses en copie cachée (optionnel)
            reply_to: Adresse email de réponse (optionnel)
            text: Version texte brut de l'email (optionnel)
            tags: Tags pour catégoriser l'email (optionnel)
            attachments: Pièces jointes (optionnel)

        Returns:
            Dictionnaire avec l'ID de l'email envoyé

        Raises:
            ResendEmailError: En cas d'erreur lors de l'envoi
        """
        try:
            # Préparer les paramètres
            params = {
                "from": from_email or self.default_from_email,
                "to": to if isinstance(to, list) else [to],
                "subject": subject,
                "html": html
            }

            # Ajouter les paramètres optionnels
            if cc:
                params["cc"] = cc
            if bcc:
                params["bcc"] = bcc
            if reply_to:
                params["reply_to"] = reply_to
            if text:
                params["text"] = text
            if tags:
                params["tags"] = tags
            if attachments:
                params["attachments"] = attachments

            # Envoyer l'email
            logger.info(f"[RESEND] Sending email to {to} with subject: {subject}")

            response = resend.Emails.send(params)

            logger.info(f"[RESEND] Email sent successfully. ID: {response.get('id')}")

            return {
                "success": True,
                "id": response.get("id"),
                "message": "Email sent successfully"
            }

        except Exception as e:
            error_msg = str(e)
            logger.error(f"[RESEND] Error sending email: {error_msg}")
            raise ResendEmailError(f"Failed to send email: {error_msg}")

    async def send_batch_emails(
        self,
        emails: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Envoie plusieurs emails en batch via Resend

        Args:
            emails: Liste de dictionnaires contenant les paramètres de chaque email
                   Chaque dictionnaire doit avoir au minimum: to, subject, html

        Returns:
            Dictionnaire avec les résultats de l'envoi batch

        Raises:
            ResendEmailError: En cas d'erreur lors de l'envoi
        """
        try:
            # Préparer les emails pour le batch
            batch_params = []
            for email_data in emails:
                params = {
                    "from": email_data.get("from_email") or self.default_from_email,
                    "to": email_data.get("to") if isinstance(email_data.get("to"), list) else [email_data.get("to")],
                    "subject": email_data.get("subject"),
                    "html": email_data.get("html")
                }

                # Ajouter les paramètres optionnels
                if email_data.get("cc"):
                    params["cc"] = email_data["cc"]
                if email_data.get("bcc"):
                    params["bcc"] = email_data["bcc"]
                if email_data.get("reply_to"):
                    params["reply_to"] = email_data["reply_to"]
                if email_data.get("text"):
                    params["text"] = email_data["text"]
                if email_data.get("tags"):
                    params["tags"] = email_data["tags"]

                batch_params.append(params)

            logger.info(f"[RESEND] Sending batch of {len(batch_params)} emails")

            response = resend.Batch.send(batch_params)

            logger.info(f"[RESEND] Batch emails sent successfully")

            return {
                "success": True,
                "data": response.get("data"),
                "message": f"Batch of {len(batch_params)} emails sent successfully"
            }

        except Exception as e:
            error_msg = str(e)
            logger.error(f"[RESEND] Error sending batch emails: {error_msg}")
            raise ResendEmailError(f"Failed to send batch emails: {error_msg}")

    async def get_email(self, email_id: str) -> Dict[str, Any]:
        """
        Récupère les informations d'un email envoyé

        Args:
            email_id: ID de l'email Resend

        Returns:
            Dictionnaire avec les informations de l'email

        Raises:
            ResendEmailError: En cas d'erreur lors de la récupération
        """
        try:
            logger.info(f"[RESEND] Retrieving email: {email_id}")

            response = resend.Emails.get(email_id)

            return {
                "success": True,
                "data": response
            }

        except Exception as e:
            error_msg = str(e)
            logger.error(f"[RESEND] Error retrieving email {email_id}: {error_msg}")
            raise ResendEmailError(f"Failed to retrieve email: {error_msg}")


# Instance globale du service (sera initialisée au démarrage de l'app)
_resend_service: Optional[ResendEmailService] = None


def get_resend_service() -> ResendEmailService:
    """Récupère l'instance globale du service Resend"""
    global _resend_service
    if _resend_service is None:
        _resend_service = ResendEmailService()
    return _resend_service


def init_resend_service(api_key: Optional[str] = None):
    """Initialise le service Resend avec une clé API spécifique"""
    global _resend_service
    _resend_service = ResendEmailService(api_key=api_key)
    return _resend_service
