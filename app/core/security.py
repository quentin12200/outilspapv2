"""
Module de sécurité pour l'authentification des utilisateurs.
"""
from __future__ import annotations

import os
import secrets
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

security = HTTPBasic()


def get_admin_credentials() -> tuple[str, str]:
    """Retourne les identifiants admin configurés via l'environnement."""
    username = os.getenv("ADMIN_USER", "admin")
    password = os.getenv("ADMIN_PASSWORD")
    if not password:
        raise RuntimeError(
            "ADMIN_PASSWORD doit être défini (voir .env.example pour la configuration)."
        )
    return username, password


def verify_admin(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    """Valide les identifiants reçus via HTTP Basic."""
    expected_user, expected_password = get_admin_credentials()
    user_ok = secrets.compare_digest(
        credentials.username.encode("utf-8"), expected_user.encode("utf-8")
    )
    password_ok = secrets.compare_digest(
        credentials.password.encode("utf-8"), expected_password.encode("utf-8")
    )
    if not (user_ok and password_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants incorrects",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


def verify_admin_optional(
    credentials: HTTPBasicCredentials = Depends(security),
) -> Optional[str]:
    """Valide les identifiants si fournis, sinon laisse passer l'appelant."""
    try:
        return verify_admin(credentials)
    except HTTPException:
        return None
