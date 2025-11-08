"""
Module d'authentification pour l'espace admin (interface web).
Gère les sessions utilisateur avec login/mot de passe.
"""
import os
import secrets
from typing import Optional
from fastapi import HTTPException, Request, status
from fastapi.responses import RedirectResponse
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

# Configuration des identifiants admin
ADMIN_LOGIN = os.getenv("ADMIN_LOGIN", "papcse").strip()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "evs2026").strip()

# Clé secrète pour signer les cookies de session
# En production, cette clé doit être définie dans les variables d'environnement
SECRET_KEY = os.getenv("ADMIN_SESSION_SECRET", secrets.token_urlsafe(32))

# Serializer pour les cookies de session
serializer = URLSafeTimedSerializer(SECRET_KEY)

# Nom du cookie de session
SESSION_COOKIE_NAME = "admin_session"

# Durée de validité de la session (en secondes) - 24 heures par défaut
SESSION_MAX_AGE = int(os.getenv("ADMIN_SESSION_MAX_AGE", 86400))


def create_session_token(login: str) -> str:
    """
    Crée un token de session signé pour l'utilisateur.

    Args:
        login: Le login de l'utilisateur

    Returns:
        Le token de session signé
    """
    return serializer.dumps({"login": login})


def verify_session_token(token: str) -> Optional[str]:
    """
    Vérifie un token de session et retourne le login si valide.

    Args:
        token: Le token de session à vérifier

    Returns:
        Le login de l'utilisateur si le token est valide, None sinon
    """
    try:
        data = serializer.loads(token, max_age=SESSION_MAX_AGE)
        return data.get("login")
    except (BadSignature, SignatureExpired):
        return None


def verify_credentials(login: str, password: str) -> bool:
    """
    Vérifie les identifiants de connexion.

    Args:
        login: Le login fourni
        password: Le mot de passe fourni

    Returns:
        True si les identifiants sont corrects, False sinon
    """
    return login == ADMIN_LOGIN and password == ADMIN_PASSWORD


class AdminAuthException(Exception):
    """Exception personnalisée pour l'authentification admin"""
    def __init__(self, redirect_url: str = "/admin/login"):
        self.redirect_url = redirect_url
        super().__init__("Non authentifié")


def get_current_admin_user(request: Request) -> str:
    """
    Récupère l'utilisateur admin connecté depuis la session.
    Utilisé comme dépendance FastAPI pour protéger les routes admin.

    Args:
        request: La requête FastAPI

    Returns:
        Le login de l'utilisateur connecté

    Raises:
        AdminAuthException: Si l'utilisateur n'est pas connecté (redirige vers login)
    """
    session_token = request.cookies.get(SESSION_COOKIE_NAME)

    if not session_token:
        raise AdminAuthException("/admin/login")

    login = verify_session_token(session_token)

    if not login:
        # Token invalide ou expiré
        raise AdminAuthException("/admin/login")

    return login


def is_admin_authenticated(request: Request) -> bool:
    """
    Vérifie si l'utilisateur est authentifié en tant qu'admin.
    Version non-bloquante pour les templates.

    Args:
        request: La requête FastAPI

    Returns:
        True si l'utilisateur est authentifié, False sinon
    """
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_token:
        return False

    login = verify_session_token(session_token)
    return login is not None
