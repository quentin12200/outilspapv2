"""
Routes d'authentification avec validation par email.

Ce module fournit les endpoints pour :
- Inscription avec envoi d'email de validation
- Validation de compte par token
- Demande de réinitialisation de mot de passe
- Réinitialisation de mot de passe avec token
"""

import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import User
from ..user_auth import (
    hash_password,
    validate_email,
    validate_password_strength
)
from ..email_service import (
    send_account_validation_email,
    send_reset_password_email,
    send_welcome_email
)

# Configuration du logger
logger = logging.getLogger(__name__)

# Créer le router
router = APIRouter(prefix="/auth", tags=["Authentication Email"])

# Durées de validité des tokens
VALIDATION_TOKEN_EXPIRY_HOURS = 24  # 24 heures pour la validation email
RESET_TOKEN_EXPIRY_HOURS = 1  # 1 heure pour le reset de mot de passe


# ========================================
# Schémas Pydantic
# ========================================

class RegisterRequest(BaseModel):
    """Schéma pour l'inscription d'un nouvel utilisateur"""
    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: str = Field(..., min_length=1, max_length=255)
    last_name: str = Field(..., min_length=1, max_length=255)
    phone: Optional[str] = Field(None, max_length=20)
    organization: Optional[str] = Field(None, max_length=255)
    fd: Optional[str] = Field(None, max_length=80)
    ud: Optional[str] = Field(None, max_length=80)
    region: Optional[str] = Field(None, max_length=100)
    responsibility: Optional[str] = Field(None, max_length=255)
    registration_reason: Optional[str] = None


class RegisterResponse(BaseModel):
    """Schéma de réponse après inscription"""
    success: bool
    message: str
    email: str


class ValidateAccountResponse(BaseModel):
    """Schéma de réponse après validation de compte"""
    success: bool
    message: str


class ForgotPasswordRequest(BaseModel):
    """Schéma pour la demande de réinitialisation de mot de passe"""
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    """Schéma de réponse après demande de reset"""
    success: bool
    message: str


class ResetPasswordRequest(BaseModel):
    """Schéma pour la réinitialisation du mot de passe"""
    token: str
    new_password: str = Field(..., min_length=8)


class ResetPasswordResponse(BaseModel):
    """Schéma de réponse après réinitialisation"""
    success: bool
    message: str


# ========================================
# Endpoints
# ========================================

@router.post("/register", response_model=RegisterResponse)
async def register_user(
    data: RegisterRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session)
):
    """
    Inscrit un nouvel utilisateur et envoie un email de validation.

    Le compte est créé avec is_active=False et is_approved=False.
    L'utilisateur doit d'abord valider son email, puis attendre l'approbation admin.

    Args:
        data: Données d'inscription
        background_tasks: Tâches en arrière-plan pour l'envoi d'email
        db: Session de base de données

    Returns:
        RegisterResponse: Confirmation d'inscription

    Raises:
        HTTPException: Si l'email existe déjà ou si les données sont invalides
    """
    # Valider l'email
    if not validate_email(data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Format d'email invalide"
        )

    # Valider la force du mot de passe
    is_strong, error_msg = validate_password_strength(data.password)
    if not is_strong:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )

    # Vérifier que l'email n'existe pas déjà
    existing_user = db.query(User).filter(User.email == data.email.lower()).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Un compte existe déjà avec cet email"
        )

    # Générer un token de validation sécurisé
    validation_token = secrets.token_urlsafe(32)
    validation_token_expiry = datetime.now() + timedelta(hours=VALIDATION_TOKEN_EXPIRY_HOURS)

    # Créer le nouvel utilisateur
    new_user = User(
        email=data.email.lower(),
        hashed_password=hash_password(data.password),
        first_name=data.first_name,
        last_name=data.last_name,
        phone=data.phone,
        organization=data.organization,
        fd=data.fd,
        ud=data.ud,
        region=data.region,
        responsibility=data.responsibility,
        registration_reason=data.registration_reason,
        is_active=False,  # Désactivé jusqu'à validation email
        is_approved=False,  # Nécessite approbation admin
        email_verified=False,  # Email pas encore vérifié
        validation_token=validation_token,
        validation_token_expiry=validation_token_expiry
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        # Envoyer l'email de validation en arrière-plan
        username = f"{new_user.first_name} {new_user.last_name}"
        background_tasks.add_task(
            send_account_validation_email,
            email=new_user.email,
            token=validation_token,
            username=username
        )

        logger.info(f"Nouvel utilisateur inscrit : {new_user.email}")

        return RegisterResponse(
            success=True,
            message="Inscription réussie ! Veuillez vérifier votre email pour valider votre compte.",
            email=new_user.email
        )

    except Exception as e:
        db.rollback()
        logger.error(f"Erreur lors de l'inscription : {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'inscription"
        )


@router.get("/validate-account", response_model=ValidateAccountResponse)
async def validate_account(
    token: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session)
):
    """
    Valide un compte utilisateur via le token reçu par email.

    Active le compte (is_active=True) et marque l'email comme vérifié.
    Envoie ensuite un email de bienvenue.

    Args:
        token: Token de validation reçu par email
        background_tasks: Tâches en arrière-plan pour l'envoi d'email
        db: Session de base de données

    Returns:
        ValidateAccountResponse: Confirmation de validation

    Raises:
        HTTPException: Si le token est invalide ou expiré
    """
    # Rechercher l'utilisateur avec ce token
    user = db.query(User).filter(User.validation_token == token).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token de validation invalide"
        )

    # Vérifier que le token n'a pas expiré
    if user.validation_token_expiry and datetime.now() > user.validation_token_expiry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le lien de validation a expiré. Veuillez vous réinscrire."
        )

    # Vérifier que le compte n'est pas déjà validé
    if user.email_verified:
        return ValidateAccountResponse(
            success=True,
            message="Votre compte a déjà été validé. Vous pouvez vous connecter."
        )

    try:
        # Activer le compte et marquer l'email comme vérifié
        user.is_active = True
        user.email_verified = True
        user.validation_token = None  # Supprimer le token après utilisation
        user.validation_token_expiry = None

        db.commit()

        # Envoyer l'email de bienvenue
        username = f"{user.first_name} {user.last_name}"
        background_tasks.add_task(
            send_welcome_email,
            email=user.email,
            username=username
        )

        logger.info(f"Compte validé pour : {user.email}")

        return ValidateAccountResponse(
            success=True,
            message="Votre compte a été validé avec succès ! Votre demande d'accès est en attente d'approbation par un administrateur."
        )

    except Exception as e:
        db.rollback()
        logger.error(f"Erreur lors de la validation : {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la validation du compte"
        )


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(
    data: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session)
):
    """
    Demande de réinitialisation de mot de passe.

    Génère un token de reset et envoie un email avec le lien.
    Pour des raisons de sécurité, retourne toujours le même message
    même si l'email n'existe pas (évite l'énumération des comptes).

    Args:
        data: Email du compte à réinitialiser
        background_tasks: Tâches en arrière-plan pour l'envoi d'email
        db: Session de base de données

    Returns:
        ForgotPasswordResponse: Message générique de confirmation
    """
    # Message générique pour éviter l'énumération des emails
    generic_message = "Si un compte existe avec cet email, vous recevrez un lien de réinitialisation dans quelques instants."

    # Rechercher l'utilisateur
    user = db.query(User).filter(User.email == data.email.lower()).first()

    if not user:
        # Pour des raisons de sécurité, on ne révèle pas que l'email n'existe pas
        logger.warning(f"Tentative de reset pour email inexistant : {data.email}")
        return ForgotPasswordResponse(
            success=True,
            message=generic_message
        )

    # Vérifier que le compte est actif
    if not user.is_active or not user.email_verified:
        logger.warning(f"Tentative de reset pour compte inactif : {data.email}")
        return ForgotPasswordResponse(
            success=True,
            message=generic_message
        )

    try:
        # Générer un token de reset sécurisé
        reset_token = secrets.token_urlsafe(32)
        reset_token_expiry = datetime.now() + timedelta(hours=RESET_TOKEN_EXPIRY_HOURS)

        # Enregistrer le token
        user.reset_token = reset_token
        user.reset_token_expiry = reset_token_expiry
        db.commit()

        # Envoyer l'email de reset en arrière-plan
        username = f"{user.first_name} {user.last_name}"
        background_tasks.add_task(
            send_reset_password_email,
            email=user.email,
            token=reset_token,
            username=username
        )

        logger.info(f"Demande de reset de mot de passe pour : {user.email}")

        return ForgotPasswordResponse(
            success=True,
            message=generic_message
        )

    except Exception as e:
        db.rollback()
        logger.error(f"Erreur lors de la demande de reset : {str(e)}")
        # Même en cas d'erreur, on retourne le message générique
        return ForgotPasswordResponse(
            success=True,
            message=generic_message
        )


@router.post("/reset-password", response_model=ResetPasswordResponse)
async def reset_password(
    data: ResetPasswordRequest,
    db: Session = Depends(get_session)
):
    """
    Réinitialise le mot de passe avec le token reçu par email.

    Args:
        data: Token et nouveau mot de passe
        db: Session de base de données

    Returns:
        ResetPasswordResponse: Confirmation de réinitialisation

    Raises:
        HTTPException: Si le token est invalide ou expiré
    """
    # Rechercher l'utilisateur avec ce token
    user = db.query(User).filter(User.reset_token == data.token).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token de réinitialisation invalide"
        )

    # Vérifier que le token n'a pas expiré
    if user.reset_token_expiry and datetime.now() > user.reset_token_expiry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le lien de réinitialisation a expiré. Veuillez faire une nouvelle demande."
        )

    # Valider la force du nouveau mot de passe
    is_strong, error_msg = validate_password_strength(data.new_password)
    if not is_strong:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )

    try:
        # Mettre à jour le mot de passe
        user.hashed_password = hash_password(data.new_password)
        user.reset_token = None  # Supprimer le token après utilisation
        user.reset_token_expiry = None

        db.commit()

        logger.info(f"Mot de passe réinitialisé pour : {user.email}")

        return ResetPasswordResponse(
            success=True,
            message="Votre mot de passe a été réinitialisé avec succès. Vous pouvez maintenant vous connecter."
        )

    except Exception as e:
        db.rollback()
        logger.error(f"Erreur lors de la réinitialisation : {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la réinitialisation du mot de passe"
        )
