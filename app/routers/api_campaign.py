"""
API Router pour la gestion de campagnes PAP.

Ce module permet d'analyser des PAP en masse, de les classer par priorité
et de générer les contenus d'emails pour les UD.
"""

import logging
from typing import List, Dict, Any
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_session
from ..services.document_extractor import DocumentExtractor, DocumentExtractorError
from ..services.pap_campaign_service import PAPCampaignService
from ..audit import log_admin_action
from ..user_auth import require_admin_user
from ..models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/campaign", tags=["Campagnes PAP"])


class CampaignAnalysisResult(BaseModel):
    """Résultat d'analyse d'une campagne PAP."""
    total: int
    stats: Dict[str, Any]
    enjeux: List[Dict[str, Any]]
    standard: List[Dict[str, Any]]


class EmailGenerationRequest(BaseModel):
    """Requête de génération d'email."""
    pap_data: Dict[str, Any]
    is_priority: bool = False


@router.post("/analyze-batch")
async def analyze_pap_batch(
    request: Request,
    files: List[UploadFile] = File(..., description="Liste de PDFs de PAP à analyser"),
    db: Session = Depends(get_session),
    current_user: User = Depends(require_admin_user)
):
    """
    Analyse un lot de PAP et les classe par priorité (enjeux vs standard).

    **Fonctionnalités:**
    - Extraction automatique des données de chaque PAP (GPT-4 Vision)
    - Enrichissement avec APIs Pappers/Sirene si données manquantes
    - Classification automatique (PAP à enjeux ou standard)
    - Identification de l'UD responsable

    **Critères PAP à enjeux:**
    - Effectif ≥ 1000 salariés
    - OU inscrits importants par rapport à la moyenne du département

    **Exemple:**
    ```bash
    curl -X POST "http://localhost:8000/api/campaign/analyze-batch" \\
      -F "files=@pap1.pdf" \\
      -F "files=@pap2.pdf" \\
      -F "files=@pap3.pdf"
    ```
    """
    if not files:
        raise HTTPException(status_code=400, detail="Aucun fichier fourni")

    extracted_paps = []
    extraction_errors = []

    extractor = DocumentExtractor()
    campaign_service = PAPCampaignService(db)

    logger.info(f"🚀 Début d'analyse de campagne PAP - {len(files)} fichier(s)")

    # Étape 1 : Extraction des données de chaque PAP
    for i, file in enumerate(files, 1):
        logger.info(f"📄 Traitement du fichier {i}/{len(files)}: {file.filename}")

        try:
            # Vérifier le type de fichier
            if file.content_type not in [
                "image/jpeg", "image/jpg", "image/png", "image/webp",
                "application/pdf"
            ]:
                extraction_errors.append({
                    'filename': file.filename,
                    'error': f"Type de fichier non supporté: {file.content_type}"
                })
                continue

            # Lire le fichier
            file_data = await file.read()
            is_pdf = file.content_type == "application/pdf"

            # Extraire les informations
            extracted_data = await extractor.extract_from_document(file_data, is_pdf=is_pdf)

            # Ajouter le nom de fichier pour référence
            extracted_data['filename'] = file.filename
            # Note: on ne stocke PAS file_data ici car bytes ne sont pas JSON-sérialisables

            extracted_paps.append(extracted_data)
            logger.info(f"✅ Extraction réussie - SIRET: {extracted_data.get('siret', 'N/A')}")

        except DocumentExtractorError as e:
            logger.error(f"❌ Erreur extraction {file.filename}: {str(e)}")
            extraction_errors.append({
                'filename': file.filename,
                'error': str(e)
            })
        except Exception as e:
            logger.error(f"❌ Erreur inattendue {file.filename}: {str(e)}")
            extraction_errors.append({
                'filename': file.filename,
                'error': f"Erreur inattendue: {str(e)}"
            })

    if not extracted_paps:
        raise HTTPException(
            status_code=422,
            detail=f"Aucun PAP n'a pu être extrait. Erreurs: {extraction_errors}"
        )

    # Étape 2 : Analyse et classification des PAP
    logger.info(f"🔍 Analyse et classification de {len(extracted_paps)} PAP(s)")
    analysis_result = campaign_service.analyze_batch(extracted_paps)

    # Ajouter les erreurs d'extraction dans les stats
    analysis_result['extraction_errors'] = extraction_errors
    analysis_result['extraction_success_rate'] = (
        len(extracted_paps) / len(files) * 100 if files else 0
    )

    # Log de l'action
    log_admin_action(
        request=request,
        api_key=None,
        action="analyze_pap_campaign",
        resource_type="campaign",
        success=True,
        resource_id=f"batch_{len(files)}",
        request_params={
            'total_files': len(files),
            'successful_extractions': len(extracted_paps),
            'failed_extractions': len(extraction_errors)
        },
        response_summary={
            'enjeux': analysis_result['stats']['count_enjeux'],
            'standard': analysis_result['stats']['count_standard']
        }
    )

    logger.info(
        f"✅ Analyse terminée - "
        f"{analysis_result['stats']['count_enjeux']} enjeux, "
        f"{analysis_result['stats']['count_standard']} standard"
    )

    return analysis_result


@router.post("/generate-email")
async def generate_email_content(
    request: Request,
    email_request: EmailGenerationRequest
):
    """
    Génère le contenu d'un email pour un PAP spécifique.

    Le contenu est différencié selon que le PAP est prioritaire ou non.

    **Returns:**
    ```json
    {
        "subject": "Sujet de l'email",
        "body": "Corps de l'email pré-formaté",
        "recipient": "ud75@cgt.fr",
        "mailto_link": "mailto:ud75@cgt.fr?subject=..."
    }
    ```
    """
    try:
        pap_data = email_request.pap_data
        is_priority = email_request.is_priority

        email_content = PAPCampaignService.generate_email_content(pap_data, is_priority)

        # Générer le lien mailto:
        import urllib.parse
        mailto_link = (
            f"mailto:{email_content['recipient']}"
            f"?subject={urllib.parse.quote(email_content['subject'])}"
            f"&body={urllib.parse.quote(email_content['body'])}"
        )

        return {
            **email_content,
            'mailto_link': mailto_link
        }

    except Exception as e:
        logger.error(f"Erreur génération email: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Vérifie que le service de campagne est opérationnel."""
    return {
        "status": "operational",
        "message": "Service de campagne PAP prêt"
    }
