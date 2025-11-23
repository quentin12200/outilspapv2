"""
Router API pour le chatbot IA.

Ce module expose des endpoints pour interagir avec le chatbot IA
qui permet de poser des questions en langage naturel sur les données PAP/CSE.
"""

import logging
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_session
from ..services.chatbot_ia import ChatbotIA
from ..audit import log_admin_action

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chatbot", tags=["Chatbot IA"])


class ChatbotQuestion(BaseModel):
    """Schéma pour une question au chatbot."""
    question: str = Field(..., min_length=1, max_length=500, description="Question en langage naturel")


class ChatbotResponse(BaseModel):
    """Schéma pour la réponse du chatbot."""
    question: str
    answer: str
    sql: str | None = None
    sql_explanation: str | None = None
    total_results: int | None = None
    metadata: Dict[str, Any] | None = None
    error: str | None = None


@router.post("/ask", response_model=ChatbotResponse)
async def chatbot_ask(
    request: Request,
    question_data: ChatbotQuestion,
    db: Session = Depends(get_session)
):
    """
    Pose une question au chatbot IA.

    Le chatbot peut répondre à des questions en langage naturel sur:
    - Statistiques des invitations PAP
    - Informations sur les élections
    - Analyses par département, fédération, etc.
    - Données temporelles (retards, prochaines élections)

    **Exemples de questions:**
    - "Combien d'invitations PAP en retard dans le 75 ?"
    - "Quelles entreprises ont une élection ce mois-ci ?"
    - "Statistiques des invitations par source"
    - "Top 5 des fédérations avec le plus d'invitations"
    - "Nombre de PV d'élections avec carence"
    - "Taux de participation moyen par région"

    **Requête:**
    ```json
    {
        "question": "Combien d'invitations en retard dans le 75 ?"
    }
    ```

    **Réponse:**
    ```json
    {
        "question": "Combien d'invitations en retard dans le 75 ?",
        "answer": "Il y a **23 invitations** en retard dans le département 75 (Paris) 🔴",
        "sql": "SELECT COUNT(*) ...",
        "sql_explanation": "Compte les invitations du département 75...",
        "total_results": 1,
        "metadata": {
            "model": "gpt-4o",
            "timestamp": "2024-03-15T10:30:00",
            "response_type": "count"
        }
    }
    ```
    """
    try:
        # Initialiser le chatbot
        chatbot = ChatbotIA()

        # Poser la question
        result = chatbot.ask(question_data.question, db)

        # Log de l'action
        log_admin_action(
            request=request,
            api_key=None,  # Pas d'authentification pour ce endpoint (accessible depuis l'admin)
            action="chatbot_ask",
            resource_type="chatbot",
            success=True,
            resource_id=None,
            request_params={
                "question": question_data.question
            },
            response_summary={
                "has_results": result.get("total_results", 0) > 0,
                "response_type": result.get("metadata", {}).get("response_type")
            }
        )

        return ChatbotResponse(**result)

    except ValueError as e:
        logger.warning(f"Erreur de validation: {str(e)}")
        return ChatbotResponse(
            question=question_data.question,
            answer=f"⚠️ {str(e)}",
            error=str(e)
        )

    except Exception as e:
        logger.error(f"Erreur lors du traitement de la question: {str(e)}")
        return ChatbotResponse(
            question=question_data.question,
            answer="❌ Une erreur est survenue. Veuillez réessayer.",
            error=str(e)
        )


@router.get("/examples")
async def get_chatbot_examples():
    """
    Retourne une liste d'exemples de questions pour le chatbot.

    Ces exemples permettent aux utilisateurs de découvrir
    les capacités du chatbot et de s'inspirer pour leurs propres questions.

    **Réponse:**
    ```json
    {
        "examples": [
            {
                "category": "Statistiques générales",
                "questions": [
                    "Combien d'invitations PAP dans la base ?",
                    "Nombre total de PV d'élections ?"
                ]
            },
            ...
        ]
    }
    ```
    """
    examples = [
        {
            "category": "📊 Statistiques générales",
            "questions": [
                "Combien d'invitations PAP dans la base ?",
                "Nombre total de PV d'élections ?",
                "Combien de SIRET uniques ?",
                "Statistiques des invitations par source"
            ]
        },
        {
            "category": "📅 Analyses temporelles",
            "questions": [
                "Combien d'invitations en retard ?",
                "Quelles entreprises ont une élection ce mois-ci ?",
                "Prochaines élections dans les 30 jours",
                "Invitations reçues cette semaine"
            ]
        },
        {
            "category": "🗺️ Analyses géographiques",
            "questions": [
                "Combien d'invitations en retard dans le 75 ?",
                "Top 10 des départements avec le plus d'invitations",
                "Répartition des PV par région",
                "Statistiques par Union Départementale"
            ]
        },
        {
            "category": "🏢 Analyses sectorielles",
            "questions": [
                "Top 5 des fédérations avec le plus d'invitations",
                "Répartition des PV par fédération",
                "Invitations sans IDCC",
                "Statistiques par convention collective"
            ]
        },
        {
            "category": "📈 Analyses électorales",
            "questions": [
                "Taux de participation moyen",
                "Nombre d'élections avec carence",
                "Top 3 des syndicats les plus présents",
                "Résultats CGT dans les dernières élections",
                "Entreprises avec SVE (Syndicat Voix Electeur)"
            ]
        },
        {
            "category": "📄 Scanner PAP",
            "questions": [
                "Combien d'invitations scannées automatiquement ?",
                "Invitations avec source Scan automatique vs manuelles",
                "Dernières invitations scannées"
            ]
        },
        {
            "category": "🎯 Argumentaires Syndicaux",
            "questions": [
                "Quels sont les freins à la syndicalisation ?",
                "Comment lever les freins à la syndicalisation ?",
                "Comment améliorer la qualité de vie syndicale ?",
                "Quelle stratégie pour syndiquer les ICTAM ?",
                "Comment assurer la continuité syndicale actif/retraité ?",
                "Pourquoi perdons-nous des adhérents ?"
            ]
        }
    ]

    return {
        "examples": examples,
        "total_examples": sum(len(cat["questions"]) for cat in examples)
    }


@router.get("/health")
async def chatbot_health():
    """
    Vérifie que le service de chatbot est opérationnel.

    Retourne l'état du service et la configuration OpenAI.

    **Réponse:**
    ```json
    {
        "status": "operational",
        "openai_configured": true,
        "model": "gpt-4o",
        "message": "Service de chatbot prêt"
    }
    ```
    """
    from ..config import OPENAI_API_KEY, OPENAI_MODEL

    is_configured = OPENAI_API_KEY is not None and OPENAI_API_KEY != ""

    return {
        "status": "operational" if is_configured else "not_configured",
        "openai_configured": is_configured,
        "model": OPENAI_MODEL or "gpt-4o",
        "message": "Service de chatbot prêt" if is_configured else
                   "Clé OpenAI non configurée. Ajoutez OPENAI_API_KEY dans le fichier .env"
    }


@router.get("/argumentaires")
async def get_argumentaires():
    """
    Récupère tous les argumentaires disponibles.

    Retourne les argumentaires sur la syndicalisation, les freins et leviers, etc.
    Ces informations peuvent être utilisées pour nourrir le chatbot ou afficher
    des guides aux utilisateurs.

    **Réponse:**
    ```json
    {
        "argumentaires": {
            "syndicalisation": {
                "titre": "Freins à la syndicalisation et moyens pour les lever",
                "sections": [...]
            }
        },
        "disponibles": ["syndicalisation"],
        "total": 1
    }
    ```
    """
    from pathlib import Path
    import json

    # Chemin vers le dossier des argumentaires
    argumentaires_dir = Path(__file__).parent.parent / "data" / "argumentaires"
    argumentaires = {}

    try:
        # Charger le fichier de syndicalisation
        syndi_path = argumentaires_dir / "syndicalisation_freins_leviers.json"
        if syndi_path.exists():
            with open(syndi_path, 'r', encoding='utf-8') as f:
                argumentaires['syndicalisation'] = json.load(f)

        return {
            "argumentaires": argumentaires,
            "disponibles": list(argumentaires.keys()),
            "total": len(argumentaires),
            "message": f"{len(argumentaires)} argumentaire(s) chargé(s) avec succès"
        }

    except Exception as e:
        logger.error(f"Erreur lors du chargement des argumentaires: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors du chargement des argumentaires: {str(e)}"
        )


@router.get("/argumentaires/{argumentaire_id}")
async def get_argumentaire_by_id(argumentaire_id: str):
    """
    Récupère un argumentaire spécifique par son ID.

    **Paramètres:**
    - argumentaire_id: ID de l'argumentaire (ex: "syndicalisation")

    **Réponse:**
    ```json
    {
        "id": "syndicalisation",
        "titre": "Freins à la syndicalisation et moyens pour les lever",
        "description": "...",
        "sections": [...]
    }
    ```
    """
    from pathlib import Path
    import json

    # Chemin vers le dossier des argumentaires
    argumentaires_dir = Path(__file__).parent.parent / "data" / "argumentaires"

    # Mapping des IDs vers les fichiers
    fichiers = {
        "syndicalisation": "syndicalisation_freins_leviers.json"
    }

    if argumentaire_id not in fichiers:
        raise HTTPException(
            status_code=404,
            detail=f"Argumentaire '{argumentaire_id}' non trouvé. Argumentaires disponibles: {list(fichiers.keys())}"
        )

    try:
        fichier_path = argumentaires_dir / fichiers[argumentaire_id]
        if not fichier_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Fichier d'argumentaire non trouvé: {fichiers[argumentaire_id]}"
            )

        with open(fichier_path, 'r', encoding='utf-8') as f:
            argumentaire = json.load(f)

        return {
            "id": argumentaire_id,
            **argumentaire
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors du chargement de l'argumentaire {argumentaire_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors du chargement de l'argumentaire: {str(e)}"
        )
