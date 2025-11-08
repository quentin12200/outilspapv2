"""
Module d'authentification pour les endpoints d'administration.
"""
import os
import secrets
from typing import Optional
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

# Configuration de l'API Key
# En production, cette clé doit être définie dans les variables d'environnement
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "").strip()

# Si aucune clé n'est définie en production, générer un avertissement
if not ADMIN_API_KEY:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(
        "⚠️ ADMIN_API_KEY not set! Admin endpoints are NOT protected. "
        "Please set ADMIN_API_KEY environment variable in production."
    )
    # En développement, on peut générer une clé temporaire
    # ATTENTION: En production, cette clé doit TOUJOURS être définie dans l'environnement
    if os.getenv("ENV", "development").lower() == "development":
        ADMIN_API_KEY = secrets.token_urlsafe(32)
        logger.warning(f"Generated temporary API key for development: {ADMIN_API_KEY}")

# Header pour l'API Key
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_api_key(api_key: Optional[str] = Security(api_key_header)) -> str:
    """
    Vérifie que l'API Key fournie est valide.

    Args:
        api_key: L'API Key fournie dans le header X-API-Key

    Returns:
        L'API Key si elle est valide

    Raises:
        HTTPException: Si l'API Key est manquante ou invalide
    """
    # Si aucune clé n'est configurée, on désactive l'authentification
    # ATTENTION: Cela ne devrait JAMAIS arriver en production !
    if not ADMIN_API_KEY:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning("API Key authentication is DISABLED - no ADMIN_API_KEY configured")
        return "unauthenticated"

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key manquante. Fournissez une clé API valide dans le header X-API-Key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Comparaison sécurisée pour éviter les timing attacks
    if not secrets.compare_digest(api_key, ADMIN_API_KEY):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API Key invalide.",
        )

    return api_key


# Alias pour faciliter l'utilisation dans les endpoints
require_api_key = get_api_key
