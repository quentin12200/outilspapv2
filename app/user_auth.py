"""
Module d'authentification pour les utilisateurs du site.
Gère l'inscription, la connexion et les sessions utilisateur avec validation admin.
"""
import os
import re
import secrets
from datetime import datetime
from typing import Optional
from passlib.context import CryptContext
from fastapi import HTTPException, Request, status
from fastapi.responses import RedirectResponse
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from sqlalchemy.orm import Session

from .models import User

# Configuration du hachage de mots de passe avec bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Clé secrète pour signer les cookies de session utilisateur
# Utilise la même clé que l'admin ou une clé dédiée
USER_SESSION_SECRET = os.getenv("USER_SESSION_SECRET") or os.getenv("ADMIN_SESSION_SECRET", secrets.token_urlsafe(32))

# Serializer pour les cookies de session
user_serializer = URLSafeTimedSerializer(USER_SESSION_SECRET)

# Nom du cookie de session utilisateur
USER_SESSION_COOKIE_NAME = "user_session"

# Durée de validité de la session (en secondes) - 7 jours par défaut
USER_SESSION_MAX_AGE = int(os.getenv("USER_SESSION_MAX_AGE", 604800))


# Routes publiques qui ne nécessitent pas d'authentification
PUBLIC_ROUTES = {
    "/signup",
    "/login",
    "/logout",
    "/admin/login",
    "/admin/logout",
    "/static",
    "/mentions-legales"
}


def hash_password(password: str) -> str:
    """
    Hash un mot de passe avec bcrypt.

    Args:
        password: Le mot de passe en clair

    Returns:
        Le mot de passe hashé
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Vérifie qu'un mot de passe correspond à son hash.

    Args:
        plain_password: Le mot de passe en clair
        hashed_password: Le hash à vérifier

    Returns:
        True si le mot de passe est correct, False sinon
    """
    return pwd_context.verify(plain_password, hashed_password)


def validate_email(email: str) -> bool:
    """
    Valide le format d'une adresse email.

    Args:
        email: L'adresse email à valider

    Returns:
        True si l'email est valide, False sinon
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Vérifie la force d'un mot de passe.

    Critères:
    - Au moins 8 caractères
    - Au moins une lettre majuscule
    - Au moins une lettre minuscule
    - Au moins un chiffre

    Args:
        password: Le mot de passe à valider

    Returns:
        Tuple (est_valide, message_erreur)
    """
    if len(password) < 8:
        return False, "Le mot de passe doit contenir au moins 8 caractères"

    if not re.search(r'[A-Z]', password):
        return False, "Le mot de passe doit contenir au moins une lettre majuscule"

    if not re.search(r'[a-z]', password):
        return False, "Le mot de passe doit contenir au moins une lettre minuscule"

    if not re.search(r'[0-9]', password):
        return False, "Le mot de passe doit contenir au moins un chiffre"

    return True, ""


def create_user_session_token(user_id: int, email: str) -> str:
    """
    Crée un token de session signé pour l'utilisateur.

    Args:
        user_id: L'ID de l'utilisateur
        email: L'email de l'utilisateur

    Returns:
        Le token de session signé
    """
    return user_serializer.dumps({"user_id": user_id, "email": email})


def verify_user_session_token(token: str) -> Optional[dict]:
    """
    Vérifie un token de session et retourne les données si valide.

    Args:
        token: Le token de session à vérifier

    Returns:
        Dict avec user_id et email si valide, None sinon
    """
    try:
        data = user_serializer.loads(token, max_age=USER_SESSION_MAX_AGE)
        return data
    except (BadSignature, SignatureExpired):
        return None


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """
    Authentifie un utilisateur avec email et mot de passe.

    Args:
        db: Session SQLAlchemy
        email: Email de l'utilisateur
        password: Mot de passe en clair

    Returns:
        L'objet User si authentification réussie, None sinon
    """
    user = db.query(User).filter(User.email == email).first()

    if not user:
        return None

    # Vérifier que le compte est approuvé
    if not user.is_approved:
        return None

    # Vérifier que le compte est actif
    if not user.is_active:
        return None

    # Vérifier le mot de passe
    if not verify_password(password, user.hashed_password):
        return None

    # Mettre à jour la dernière connexion
    user.last_login = datetime.now()
    db.commit()

    return user


def get_client_ip(request: Request) -> str:
    """
    Récupère l'adresse IP du client en tenant compte des proxies.

    Args:
        request: La requête FastAPI

    Returns:
        L'adresse IP du client
    """
    # Vérifier d'abord les headers de proxy
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Sinon utiliser l'IP directe
    if request.client:
        return request.client.host

    return "unknown"


class UserAuthException(Exception):
    """Exception personnalisée pour l'authentification utilisateur"""
    def __init__(self, redirect_url: str = "/login"):
        self.redirect_url = redirect_url
        super().__init__("Non authentifié")


def get_current_user(request: Request, db: Session) -> User:
    """
    Récupère l'utilisateur connecté depuis la session.
    Utilisé comme dépendance FastAPI pour protéger les routes utilisateur.

    Args:
        request: La requête FastAPI
        db: Session SQLAlchemy

    Returns:
        L'objet User de l'utilisateur connecté

    Raises:
        UserAuthException: Si l'utilisateur n'est pas connecté
    """
    session_token = request.cookies.get(USER_SESSION_COOKIE_NAME)

    if not session_token:
        raise UserAuthException("/login")

    session_data = verify_user_session_token(session_token)

    if not session_data:
        # Token invalide ou expiré
        raise UserAuthException("/login")

    # Récupérer l'utilisateur depuis la base
    user = db.query(User).filter(
        User.id == session_data["user_id"],
        User.is_approved == True,
        User.is_active == True
    ).first()

    if not user:
        raise UserAuthException("/login")

    return user


def is_user_authenticated(request: Request, db: Session) -> bool:
    """
    Vérifie si l'utilisateur est authentifié.
    Version non-bloquante pour les templates.

    Args:
        request: La requête FastAPI
        db: Session SQLAlchemy

    Returns:
        True si l'utilisateur est authentifié, False sinon
    """
    try:
        get_current_user(request, db)
        return True
    except UserAuthException:
        return False


def get_current_user_or_none(request: Request, db: Session) -> Optional[User]:
    """
    Récupère l'utilisateur connecté ou None.
    Version non-bloquante pour les templates.

    Args:
        request: La requête FastAPI
        db: Session SQLAlchemy

    Returns:
        L'objet User si connecté, None sinon
    """
    try:
        return get_current_user(request, db)
    except UserAuthException:
        return None


def require_admin_user(request: Request, db: Session) -> User:
    """
    Vérifie que l'utilisateur connecté est un administrateur.
    Utilisé comme dépendance FastAPI pour protéger les routes admin.

    Args:
        request: La requête FastAPI
        db: Session SQLAlchemy

    Returns:
        L'objet User de l'utilisateur connecté (avec role admin)

    Raises:
        HTTPException: Si l'utilisateur n'est pas admin
    """
    from fastapi import HTTPException, status

    user = get_current_user(request, db)

    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé. Seuls les administrateurs peuvent effectuer cette action."
        )

    return user


def is_admin_user(request: Request, db: Session) -> bool:
    """
    Vérifie si l'utilisateur connecté est un administrateur.
    Version non-bloquante pour les templates.

    Args:
        request: La requête FastAPI
        db: Session SQLAlchemy

    Returns:
        True si l'utilisateur est admin, False sinon
    """
    try:
        user = get_current_user(request, db)
        return user.role == "admin"
    except (UserAuthException, Exception):
        return False


def is_public_route(path: str) -> bool:
    """
    Vérifie si une route est publique (accessible sans authentification utilisateur).

    Les routes admin ont leur propre système d'authentification et ne sont pas
    vérifiées par le middleware utilisateur.

    Args:
        path: Le chemin de la route

    Returns:
        True si la route est publique ou admin, False sinon
    """
    # Routes exactes
    if path in PUBLIC_ROUTES:
        return True

    # Routes qui commencent par /static, /api, ou /admin (ont leur propre auth)
    if path.startswith("/static/") or path.startswith("/api/") or path.startswith("/admin"):
        return True

    return False


def require_user_auth(request: Request, db: Session) -> Optional[User]:
    """
    Middleware pour vérifier l'authentification utilisateur sur les routes protégées.
    Redirige vers /login si l'utilisateur n'est pas connecté.

    Args:
        request: La requête FastAPI
        db: Session SQLAlchemy

    Returns:
        L'utilisateur connecté ou None pour les routes publiques

    Raises:
        UserAuthException: Si l'utilisateur n'est pas connecté sur une route protégée
    """
    # Vérifier si la route est publique
    if is_public_route(request.url.path):
        return None

    # Pour les routes protégées, vérifier l'authentification
    return get_current_user(request, db)
