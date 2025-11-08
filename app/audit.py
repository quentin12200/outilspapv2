"""
Service d'audit logging pour tracer toutes les opérations administratives.
"""
import hashlib
import time
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import Request
from sqlalchemy.orm import Session

from .models import AuditLog
from .db import SessionLocal

logger = logging.getLogger(__name__)


def hash_api_key(api_key: Optional[str]) -> str:
    """
    Hashe l'API key pour ne pas la stocker en clair dans les logs.

    Args:
        api_key: L'API key à hasher

    Returns:
        Hash SHA256 de l'API key (8 premiers caractères)
    """
    if not api_key:
        return "anonymous"

    # SHA256 hash
    hash_obj = hashlib.sha256(api_key.encode())
    return hash_obj.hexdigest()[:16]  # 16 premiers caractères du hash


def get_client_ip(request: Request) -> str:
    """
    Récupère l'IP du client depuis la requête.

    Gère les proxies (X-Forwarded-For, X-Real-IP).
    """
    # Check for proxy headers
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # X-Forwarded-For peut contenir plusieurs IPs, prendre la première
        return forwarded.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fallback to direct connection IP
    if request.client:
        return request.client.host

    return "unknown"


class AuditLogger:
    """
    Service d'audit logging pour tracer les opérations administratives.

    Usage:
        audit_logger = AuditLogger(request, api_key)
        audit_logger.log_action(
            action="POST /api/ingest/pv",
            resource_type="pv",
            success=True,
            response_summary={"rows_inserted": 150}
        )
    """

    def __init__(
        self,
        request: Request,
        api_key: Optional[str] = None,
        db: Optional[Session] = None
    ):
        """
        Initialise l'audit logger.

        Args:
            request: La requête FastAPI
            api_key: L'API key de l'utilisateur (sera hashée)
            db: Session de base de données (optionnelle, créée si absente)
        """
        self.request = request
        self.api_key = api_key
        self.db = db
        self.start_time = time.time()

    def log_action(
        self,
        action: str,
        resource_type: str,
        success: bool,
        resource_id: Optional[str] = None,
        request_params: Optional[Dict[str, Any]] = None,
        response_summary: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        status_code: int = 200
    ) -> None:
        """
        Enregistre une action dans les audit logs.

        Args:
            action: Description de l'action (ex: "POST /api/ingest/pv")
            resource_type: Type de ressource affectée (ex: "pv", "invitation")
            success: True si succès, False si erreur
            resource_id: ID de la ressource affectée (ex: SIRET)
            request_params: Paramètres de la requête
            response_summary: Résumé de la réponse
            error_message: Message d'erreur si échec
            status_code: Code HTTP de la réponse
        """
        try:
            # Calculer la durée
            duration_ms = int((time.time() - self.start_time) * 1000)

            # Créer l'entry d'audit
            audit_entry = AuditLog(
                user_identifier=hash_api_key(self.api_key),
                ip_address=get_client_ip(self.request),
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                timestamp=datetime.now(),
                method=self.request.method,
                status_code=status_code,
                success=success,
                request_params=request_params or {},
                response_summary=response_summary or {},
                error_message=error_message,
                user_agent=self.request.headers.get("User-Agent", ""),
                duration_ms=duration_ms
            )

            # Sauvegarder dans la base
            if self.db:
                self.db.add(audit_entry)
                self.db.commit()
            else:
                # Créer une session temporaire si aucune n'est fournie
                db = SessionLocal()
                try:
                    db.add(audit_entry)
                    db.commit()
                finally:
                    db.close()

            # Logger aussi dans les logs applicatifs
            log_message = (
                f"AUDIT: {action} | "
                f"user={hash_api_key(self.api_key)} | "
                f"ip={get_client_ip(self.request)} | "
                f"success={success} | "
                f"duration={duration_ms}ms"
            )

            if success:
                logger.info(log_message)
            else:
                logger.warning(f"{log_message} | error={error_message}")

        except Exception as e:
            # Ne jamais faire crasher l'application à cause de l'audit logging
            logger.error(f"Failed to write audit log: {e}", exc_info=True)


def log_admin_action(
    request: Request,
    api_key: Optional[str],
    action: str,
    resource_type: str,
    success: bool,
    **kwargs
) -> None:
    """
    Helper function pour logger une action admin rapidement.

    Args:
        request: La requête FastAPI
        api_key: L'API key de l'utilisateur
        action: Description de l'action
        resource_type: Type de ressource
        success: True si succès
        **kwargs: Paramètres supplémentaires pour log_action()
    """
    audit_logger = AuditLogger(request, api_key)
    audit_logger.log_action(action, resource_type, success, **kwargs)


def create_audit_middleware():
    """
    Crée un middleware FastAPI pour logger automatiquement toutes les requêtes admin.

    Usage dans main.py:
        app.middleware("http")(create_audit_middleware())
    """
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request as StarletteRequest

    async def audit_middleware(request: StarletteRequest, call_next):
        """Middleware pour audit logging automatique."""
        # Ne logger que les endpoints d'administration
        admin_paths = ["/api/ingest/", "/api/build/", "/api/enrichir/", "/api/invitation/add", "/api/sirene/enrichir"]

        is_admin_endpoint = any(request.url.path.startswith(path) for path in admin_paths)

        if is_admin_endpoint and request.method in ["POST", "PUT", "DELETE"]:
            # Récupérer l'API key du header
            api_key = request.headers.get("X-API-Key")

            # Créer l'audit logger
            audit_logger = AuditLogger(request, api_key)

            try:
                # Exécuter la requête
                response = await call_next(request)

                # Logger le succès
                audit_logger.log_action(
                    action=f"{request.method} {request.url.path}",
                    resource_type=_extract_resource_type(request.url.path),
                    success=response.status_code < 400,
                    status_code=response.status_code,
                    request_params=dict(request.query_params)
                )

                return response

            except Exception as e:
                # Logger l'erreur
                audit_logger.log_action(
                    action=f"{request.method} {request.url.path}",
                    resource_type=_extract_resource_type(request.url.path),
                    success=False,
                    status_code=500,
                    error_message=str(e)
                )
                raise

        else:
            # Requête non-admin, passer sans logger
            return await call_next(request)

    return audit_middleware


def _extract_resource_type(path: str) -> str:
    """Extrait le type de ressource depuis le path."""
    if "/ingest/pv" in path:
        return "pv"
    elif "/ingest/invit" in path:
        return "invitation"
    elif "/build/summary" in path:
        return "siret_summary"
    elif "/enrichir/idcc" in path:
        return "idcc_enrichment"
    elif "/enrichir" in path:
        return "sirene_enrichment"
    elif "/invitation/add" in path:
        return "invitation"
    else:
        return "unknown"
