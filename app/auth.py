"""
Module d'authentification pour les endpoints d'administration.
"""
import os
import secrets
from typing import Optional
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

ENVIRONMENT = os.getenv("ENV", "development").lower()
IS_DEV_ENV = ENVIRONMENT in {"development", "dev", "local"}
IS_TEST_ENV = ENVIRONMENT in {"test", "testing", "ci"}

# Configuration de l'API Key
# En production, cette clé doit être définie dans les variables d'environnement
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "").strip()

# Si aucune clé n'est définie en production, lever immédiatement une erreur
if not ADMIN_API_KEY:
    import logging

    logger = logging.getLogger(__name__)

    if IS_DEV_ENV:
        ADMIN_API_KEY = secrets.token_urlsafe(32)
        logger.warning(
            "⚠️ ADMIN_API_KEY not set! Generated temporary key for development only: %s",
            ADMIN_API_KEY,
        )
    elif IS_TEST_ENV:
        ADMIN_API_KEY = "test-admin-api-key"
        logger.warning(
            "ADMIN_API_KEY not set; using deterministic test key because ENV=%s",
            ENVIRONMENT,
        )
    else:
        raise RuntimeError(
            "ADMIN_API_KEY must be set in production/staging environments. "
            "Set ENV=development for local runs or define ADMIN_API_KEY."
        )

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
