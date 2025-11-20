"""
Router API pour l'envoi d'emails via Resend.

Ce module expose des endpoints pour :
- Envoyer des emails (test, invitation, notification)
- Consulter les logs d'emails envoyés
- Récupérer les statistiques d'envoi
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from ..db import get_session
from ..models import EmailLog, User
from ..services.email_service import get_resend_service, ResendEmailError
from ..audit import log_admin_action
from ..user_auth import require_admin_user
from .. import config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/email", tags=["Email"])


# ==================== Schémas Pydantic ====================

class SendEmailRequest(BaseModel):
    """Schéma pour envoyer un email personnalisé."""
    to: EmailStr | List[EmailStr] = Field(..., description="Destinataire(s) de l'email")
    subject: str = Field(..., min_length=1, max_length=500, description="Sujet de l'email")
    html: str = Field(..., min_length=1, description="Contenu HTML de l'email")
    cc: Optional[List[EmailStr]] = Field(None, description="Destinataires en copie (CC)")
    bcc: Optional[List[EmailStr]] = Field(None, description="Destinataires en copie cachée (BCC)")
    reply_to: Optional[EmailStr] = Field(None, description="Adresse de réponse")
    from_email: Optional[EmailStr] = Field(None, description="Email expéditeur (optionnel)")
    template_name: Optional[str] = Field(None, description="Nom du template utilisé")
    tags: Optional[List[Dict[str, str]]] = Field(None, description="Tags pour catégoriser")
    context_type: Optional[str] = Field(None, description="Type de contexte (invitation, notification, etc.)")
    extra_metadata: Optional[Dict[str, Any]] = Field(None, description="Métadonnées additionnelles")


class SendTemplateEmailRequest(BaseModel):
    """Schéma pour envoyer un email depuis un template."""
    to: EmailStr | List[EmailStr] = Field(..., description="Destinataire(s)")
    template_name: str = Field(..., description="Nom du template (sans .html)")
    subject: str = Field(..., min_length=1, max_length=500, description="Sujet")
    template_data: Dict[str, Any] = Field(default_factory=dict, description="Données pour le template")
    cc: Optional[List[EmailStr]] = None
    bcc: Optional[List[EmailStr]] = None
    reply_to: Optional[EmailStr] = None
    from_email: Optional[EmailStr] = None
    tags: Optional[List[Dict[str, str]]] = None
    context_type: Optional[str] = None
    extra_metadata: Optional[Dict[str, Any]] = None


class EmailResponse(BaseModel):
    """Schéma de réponse après envoi d'email."""
    success: bool
    message: str
    email_id: Optional[str] = None
    log_id: Optional[int] = None


class EmailLogResponse(BaseModel):
    """Schéma pour un log d'email."""
    id: int
    to_email: str
    subject: str
    status: str
    template_name: Optional[str]
    resend_id: Optional[str]
    created_at: datetime
    sent_at: Optional[datetime]
    error_message: Optional[str]


class EmailStatsResponse(BaseModel):
    """Schéma pour les statistiques d'emails."""
    total: int
    sent: int
    failed: int
    pending: int
    delivered: int
    opened: int
    clicked: int
    bounced: int


# ==================== Fonctions utilitaires ====================

def load_email_template(template_name: str, data: Dict[str, Any]) -> str:
    """
    Charge et remplit un template d'email.

    Args:
        template_name: Nom du template (sans .html)
        data: Données pour remplir le template

    Returns:
        Contenu HTML du template rempli

    Raises:
        HTTPException: Si le template n'existe pas
    """
    template_path = Path(__file__).parent.parent / "email_templates" / f"{template_name}.html"

    if not template_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Template '{template_name}' not found"
        )

    try:
        with open(template_path, "r", encoding="utf-8") as f:
            template_content = f.read()

        # Remplacement simple des variables {{ variable }}
        # Pour une solution plus robuste, utilisez Jinja2
        for key, value in data.items():
            template_content = template_content.replace(f"{{{{ {key} }}}}", str(value))

        return template_content

    except Exception as e:
        logger.error(f"Error loading template {template_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error loading template: {str(e)}"
        )


async def create_email_log(
    db: Session,
    to_email: str,
    subject: str,
    from_email: str,
    template_name: Optional[str] = None,
    status: str = "pending",
    resend_id: Optional[str] = None,
    error_message: Optional[str] = None,
    cc_emails: Optional[str] = None,
    bcc_emails: Optional[str] = None,
    reply_to: Optional[str] = None,
    context_type: Optional[str] = None,
    extra_metadata: Optional[Dict[str, Any]] = None,
    user_id: Optional[int] = None,
    siret: Optional[str] = None,
    tags: Optional[List[Dict[str, str]]] = None,
    request: Optional[Request] = None
) -> EmailLog:
    """
    Crée un log d'email dans la base de données.

    Returns:
        L'objet EmailLog créé
    """
    email_log = EmailLog(
        to_email=to_email,
        cc_emails=cc_emails,
        bcc_emails=bcc_emails,
        from_email=from_email,
        reply_to=reply_to,
        subject=subject,
        template_name=template_name,
        status=status,
        resend_id=resend_id,
        error_message=error_message,
        context_type=context_type,
        extra_metadata=extra_metadata,
        user_id=user_id,
        siret=siret,
        tags=tags,
        ip_address=request.client.host if request else None,
        user_agent=request.headers.get("user-agent") if request else None,
        sent_at=datetime.now() if status == "sent" else None
    )

    db.add(email_log)
    db.commit()
    db.refresh(email_log)

    return email_log


# ==================== Endpoints ====================

@router.post("/send", response_model=EmailResponse)
async def send_email(
    request: Request,
    email_data: SendEmailRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(require_admin_user)
):
    """
    Envoie un email personnalisé via Resend.

    **Exemple de requête:**
    ```json
    {
        "to": "user@example.com",
        "subject": "Test Email",
        "html": "<h1>Hello World</h1><p>This is a test email.</p>",
        "from_email": "noreply@example.com",
        "context_type": "test"
    }
    ```
    """
    try:
        # Récupérer le service Resend
        resend_service = get_resend_service()

        # Convertir to en liste si nécessaire
        to_emails = email_data.to if isinstance(email_data.to, list) else [email_data.to]
        to_email = to_emails[0]  # Pour le log

        # Préparer l'email
        from_email = email_data.from_email or config.RESEND_FROM_EMAIL

        # Créer le log AVANT l'envoi
        email_log = await create_email_log(
            db=db,
            to_email=to_email,
            subject=email_data.subject,
            from_email=from_email,
            template_name=email_data.template_name,
            cc_emails=",".join(email_data.cc) if email_data.cc else None,
            bcc_emails=",".join(email_data.bcc) if email_data.bcc else None,
            reply_to=email_data.reply_to,
            context_type=email_data.context_type,
            extra_metadata=email_data.extra_metadata,
            tags=email_data.tags,
            request=request
        )

        # Envoyer l'email
        result = await resend_service.send_email(
            to=email_data.to,
            subject=email_data.subject,
            html=email_data.html,
            from_email=from_email,
            cc=email_data.cc,
            bcc=email_data.bcc,
            reply_to=email_data.reply_to,
            tags=email_data.tags
        )

        # Mettre à jour le log avec le résultat
        email_log.status = "sent"
        email_log.resend_id = result.get("id")
        email_log.sent_at = datetime.now()
        db.commit()

        logger.info(f"Email sent successfully to {to_email}. Log ID: {email_log.id}")

        return EmailResponse(
            success=True,
            message="Email sent successfully",
            email_id=result.get("id"),
            log_id=email_log.id
        )

    except ResendEmailError as e:
        # Mettre à jour le log en cas d'erreur
        if 'email_log' in locals():
            email_log.status = "failed"
            email_log.error_message = str(e)
            db.commit()

        logger.error(f"Error sending email: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error sending email: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.post("/send-template", response_model=EmailResponse)
async def send_template_email(
    request: Request,
    email_data: SendTemplateEmailRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(require_admin_user)
):
    """
    Envoie un email depuis un template.

    **Templates disponibles:**
    - `test`: Email de test
    - `invitation`: Notification d'invitation électorale
    - `user_approved`: Notification d'approbation de compte
    - `user_registration_admin`: Notification admin pour nouvelle demande d'accès

    **Exemple de requête:**
    ```json
    {
        "to": "user@example.com",
        "template_name": "test",
        "subject": "Email de test",
        "template_data": {
            "timestamp": "2024-03-15 10:30:00",
            "recipient_email": "user@example.com"
        }
    }
    ```
    """
    try:
        # Charger le template
        html_content = load_email_template(email_data.template_name, email_data.template_data)

        # Créer la requête d'envoi
        send_request = SendEmailRequest(
            to=email_data.to,
            subject=email_data.subject,
            html=html_content,
            cc=email_data.cc,
            bcc=email_data.bcc,
            reply_to=email_data.reply_to,
            from_email=email_data.from_email,
            template_name=email_data.template_name,
            tags=email_data.tags,
            context_type=email_data.context_type,
            extra_metadata=email_data.extra_metadata
        )

        # Envoyer via l'endpoint send
        return await send_email(request, send_request, db)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending template email: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send template email: {str(e)}")


@router.post("/send-test", response_model=EmailResponse)
async def send_test_email(
    request: Request,
    to: EmailStr,
    db: Session = Depends(get_session),
    current_user: User = Depends(require_admin_user)
):
    """
    Envoie un email de test pour vérifier la configuration Resend.

    **Paramètres:**
    - `to`: Adresse email du destinataire

    **Exemple:**
    ```
    POST /api/email/send-test?to=user@example.com
    ```
    """
    try:
        # Préparer les données du template
        template_data = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "recipient_email": to
        }

        # Envoyer via le template test
        return await send_template_email(
            request=request,
            email_data=SendTemplateEmailRequest(
                to=to,
                template_name="test",
                subject="Email de test - PAP/CSE",
                template_data=template_data,
                context_type="test"
            ),
            db=db
        )

    except Exception as e:
        logger.error(f"Error sending test email: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send test email: {str(e)}")


@router.get("/logs", response_model=List[EmailLogResponse])
async def get_email_logs(
    db: Session = Depends(get_session),
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None,
    to_email: Optional[str] = None,
    context_type: Optional[str] = None,
    days: Optional[int] = None,
    current_user: User = Depends(require_admin_user)
):
    """
    Récupère les logs d'emails envoyés.

    **Paramètres:**
    - `limit`: Nombre maximum de logs à retourner (défaut: 50)
    - `offset`: Nombre de logs à sauter (pagination)
    - `status`: Filtrer par statut (sent, failed, pending, delivered, etc.)
    - `to_email`: Filtrer par email destinataire
    - `context_type`: Filtrer par type de contexte
    - `days`: Filtrer par nombre de jours (ex: 7 pour les 7 derniers jours)

    **Exemple:**
    ```
    GET /api/email/logs?limit=20&status=sent&days=7
    ```
    """
    try:
        query = db.query(EmailLog)

        # Filtres
        if status:
            query = query.filter(EmailLog.status == status)
        if to_email:
            query = query.filter(EmailLog.to_email.like(f"%{to_email}%"))
        if context_type:
            query = query.filter(EmailLog.context_type == context_type)
        if days:
            cutoff_date = datetime.now() - timedelta(days=days)
            query = query.filter(EmailLog.created_at >= cutoff_date)

        # Tri et pagination
        logs = query.order_by(EmailLog.created_at.desc()).offset(offset).limit(limit).all()

        return [
            EmailLogResponse(
                id=log.id,
                to_email=log.to_email,
                subject=log.subject,
                status=log.status,
                template_name=log.template_name,
                resend_id=log.resend_id,
                created_at=log.created_at,
                sent_at=log.sent_at,
                error_message=log.error_message
            )
            for log in logs
        ]

    except Exception as e:
        logger.error(f"Error retrieving email logs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve logs: {str(e)}")


@router.get("/stats", response_model=EmailStatsResponse)
async def get_email_stats(
    db: Session = Depends(get_session),
    days: Optional[int] = None,
    current_user: User = Depends(require_admin_user)
):
    """
    Récupère les statistiques d'envoi d'emails.

    **Paramètres:**
    - `days`: Filtrer par nombre de jours (ex: 30 pour les 30 derniers jours)

    **Exemple:**
    ```
    GET /api/email/stats?days=30
    ```
    """
    try:
        query = db.query(EmailLog)

        if days:
            cutoff_date = datetime.now() - timedelta(days=days)
            query = query.filter(EmailLog.created_at >= cutoff_date)

        # Compter par statut
        stats = {
            "total": query.count(),
            "sent": query.filter(EmailLog.status == "sent").count(),
            "failed": query.filter(EmailLog.status == "failed").count(),
            "pending": query.filter(EmailLog.status == "pending").count(),
            "delivered": query.filter(EmailLog.status == "delivered").count(),
            "opened": query.filter(EmailLog.status == "opened").count(),
            "clicked": query.filter(EmailLog.status == "clicked").count(),
            "bounced": query.filter(EmailLog.status == "bounced").count(),
        }

        return EmailStatsResponse(**stats)

    except Exception as e:
        logger.error(f"Error retrieving email stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve stats: {str(e)}")


@router.get("/templates")
async def list_email_templates(current_user: User = Depends(require_admin_user)):
    """
    Liste tous les templates d'emails disponibles.

    **Retourne:**
    Liste des templates avec leurs descriptions
    """
    try:
        templates_dir = Path(__file__).parent.parent / "email_templates"

        if not templates_dir.exists():
            return {"templates": []}

        templates = []
        for template_file in templates_dir.glob("*.html"):
            template_name = template_file.stem
            templates.append({
                "name": template_name,
                "filename": template_file.name,
                "path": str(template_file)
            })

        return {"templates": templates}

    except Exception as e:
        logger.error(f"Error listing templates: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list templates: {str(e)}")
