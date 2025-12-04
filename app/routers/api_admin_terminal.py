"""
Terminal web sécurisé pour les administrateurs
Permet d'exécuter des commandes prédéfinies sans accès shell complet
"""

import logging
import subprocess
import shlex
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from ..user_auth import require_admin_user
from ..audit import log_admin_action
from ..db import get_session
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/terminal", tags=["Admin Terminal"])


class CommandRequest(BaseModel):
    command: str


class CommandResponse(BaseModel):
    success: bool
    output: str
    error: Optional[str] = None


# Liste des commandes autorisées (whitelist pour sécurité)
ALLOWED_COMMANDS = {
    # Git commands
    "git status": ["git", "status"],
    "git log": ["git", "log", "--oneline", "-10"],
    "git branch": ["git", "branch", "-a"],
    "git diff": ["git", "diff", "--stat"],

    # Database info
    "db info": ["sqlite3", "data/pap.db", ".tables"],
    "db schema ud": ["sqlite3", "data/pap.db", ".schema tableaux_bord_ud"],
    "db count ud": ["sqlite3", "data/pap.db", "SELECT COUNT(*) FROM tableaux_bord_ud;"],

    # System info
    "disk space": ["df", "-h"],
    "memory": ["free", "-h"],
    "processes": ["ps", "aux"],

    # Python/App info
    "python version": ["python", "--version"],
    "pip list": ["pip", "list"],

    # Migrations
    "force migration": ["python", "force_create_ud_table.py"],

    # Gestion des PDFs
    "pdfs list": ["ls", "-lh", "/app/data/pap_uploads/"],
    "pdfs count": ["bash", "-c", "ls /app/data/pap_uploads/*.pdf 2>/dev/null | wc -l"],
    "pdfs size": ["du", "-sh", "/app/data/pap_uploads/"],

    # Liste des commandes
    "help": None,  # Commande spéciale traitée séparément
}


@router.post("/execute", response_model=CommandResponse)
async def execute_command(
    request: CommandRequest,
    db: Session = Depends(get_session),
    current_user = Depends(require_admin_user)
):
    """
    Exécute une commande prédéfinie dans le terminal admin.

    Seules les commandes de la whitelist peuvent être exécutées.
    """
    command = request.command.strip()

    # Commande help spéciale
    if command == "help":
        help_text = "Commandes disponibles :\n\n"
        for cmd in sorted(ALLOWED_COMMANDS.keys()):
            help_text += f"  • {cmd}\n"

        return CommandResponse(
            success=True,
            output=help_text
        )

    # Vérifier si la commande est autorisée
    if command not in ALLOWED_COMMANDS:
        logger.warning(f"Commande non autorisée tentée par {current_user.email}: {command}")

        return CommandResponse(
            success=False,
            output="",
            error=f"❌ Commande non autorisée : '{command}'\n\nTapez 'help' pour voir les commandes disponibles."
        )

    # Récupérer la commande système correspondante
    system_command = ALLOWED_COMMANDS[command]

    try:
        # Exécuter la commande
        result = subprocess.run(
            system_command,
            capture_output=True,
            text=True,
            timeout=30,  # Timeout de 30 secondes
            cwd="/home/user/outilspapv2"  # Répertoire de travail
        )

        output = result.stdout
        if result.stderr:
            output += f"\n[STDERR]\n{result.stderr}"

        # Logger l'action
        log_admin_action(
            db=db,
            user_id=current_user.id if hasattr(current_user, 'id') else None,
            action="terminal_command",
            details={"command": command, "success": result.returncode == 0}
        )

        return CommandResponse(
            success=result.returncode == 0,
            output=output if output else "(aucune sortie)",
            error=None if result.returncode == 0 else f"Code de sortie : {result.returncode}"
        )

    except subprocess.TimeoutExpired:
        logger.error(f"Timeout lors de l'exécution de la commande : {command}")
        return CommandResponse(
            success=False,
            output="",
            error="⏱️ Timeout : la commande a pris trop de temps (>30s)"
        )

    except Exception as e:
        logger.error(f"Erreur lors de l'exécution de la commande {command}: {e}")
        return CommandResponse(
            success=False,
            output="",
            error=f"❌ Erreur : {str(e)}"
        )


@router.get("/commands")
async def get_available_commands(
    current_user = Depends(require_admin_user)
):
    """Retourne la liste des commandes disponibles"""
    return {
        "success": True,
        "commands": sorted(ALLOWED_COMMANDS.keys())
    }
