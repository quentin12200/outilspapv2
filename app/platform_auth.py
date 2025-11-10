"""
Module d'authentification pour l'accès à la plateforme.
Gère les sessions utilisateur avec un mot de passe unique.
"""
import os
import secrets
from typing import Optional
from fastapi import Request
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

# Configuration du mot de passe de la plateforme
PLATFORM_PASSWORD = os.getenv("PLATFORM_PASSWORD", "papcse2025").strip()

# Clé secrète pour signer les cookies de session
# En production, cette clé doit être définie dans les variables d'environnement
SECRET_KEY = os.getenv("PLATFORM_SESSION_SECRET", secrets.token_urlsafe(32))

# Serializer pour les cookies de session
serializer = URLSafeTimedSerializer(SECRET_KEY)

# Nom du cookie de session
SESSION_COOKIE_NAME = "platform_session"

# Durée de validité de la session (en secondes) - 24 heures par défaut
SESSION_MAX_AGE = int(os.getenv("PLATFORM_SESSION_MAX_AGE", 86400))


def create_session_token() -> str:
    """
    Crée un token de session signé pour l'accès à la plateforme.

    Returns:
        Le token de session signé
    """
    return serializer.dumps({"authenticated": True})


def verify_session_token(token: str) -> bool:
    """
    Vérifie un token de session.

    Args:
        token: Le token de session à vérifier

    Returns:
        True si le token est valide, False sinon
    """
    try:
        data = serializer.loads(token, max_age=SESSION_MAX_AGE)
        return data.get("authenticated", False)
    except (BadSignature, SignatureExpired):
        return False


def verify_password(password: str) -> bool:
    """
    Vérifie le mot de passe de la plateforme.

    Args:
        password: Le mot de passe fourni

    Returns:
        True si le mot de passe est correct, False sinon
    """
    return password == PLATFORM_PASSWORD


class PlatformAuthException(Exception):
    """Exception personnalisée pour l'authentification plateforme"""
    def __init__(self, redirect_url: str = "/login"):
        self.redirect_url = redirect_url
        super().__init__("Non authentifié")


def get_current_platform_user(request: Request) -> bool:
    """
    Vérifie que l'utilisateur est authentifié pour accéder à la plateforme.
    Utilisé comme dépendance FastAPI pour protéger les routes.

    Args:
        request: La requête FastAPI

    Returns:
        True si authentifié

    Raises:
        PlatformAuthException: Si l'utilisateur n'est pas connecté (redirige vers login)
    """
    session_token = request.cookies.get(SESSION_COOKIE_NAME)

    if not session_token:
        raise PlatformAuthException("/login")

    authenticated = verify_session_token(session_token)

    if not authenticated:
        # Token invalide ou expiré
        raise PlatformAuthException("/login")

    return True


def is_platform_authenticated(request: Request) -> bool:
    """
    Vérifie si l'utilisateur est authentifié pour accéder à la plateforme.
    Version non-bloquante pour les templates.

    Args:
        request: La requête FastAPI

    Returns:
        True si l'utilisateur est authentifié, False sinon
    """
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_token:
        return False

    return verify_session_token(session_token)
