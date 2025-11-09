"""
Router API pour l'extraction automatique d'informations depuis les courriers PAP.

Ce module expose des endpoints pour uploader des documents (images, PDFs)
et en extraire automatiquement les informations via GPT-4 Vision.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, date

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import Invitation
from ..services.document_extractor import DocumentExtractor, DocumentExtractorError
from ..audit import log_admin_action

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/extract", tags=["Extraction de documents"])


class ExtractionResult(BaseModel):
    """Résultat d'extraction d'un document."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class BatchExtractionResult(BaseModel):
    """Résultat d'extraction en batch."""
    total: int
    successful: int
    failed: int
    results: List[ExtractionResult]
    total_cost_usd: float


class InvitationCreate(BaseModel):
    """Schéma pour créer une invitation depuis les données extraites."""
    siret: str
    date_invit: date
    source: str = "Extraction GPT"
    ud: Optional[str] = None
    fd: Optional[str] = None
    idcc: Optional[str] = None
    effectif_connu: Optional[int] = None
    date_reception: Optional[date] = None
    date_election: Optional[date] = None
    structure_saisie: Optional[str] = None


@router.post("/document", response_model=ExtractionResult)
async def extract_document(
    request: Request,
    file: UploadFile = File(..., description="Image ou PDF du courrier PAP"),
    auto_save: bool = Form(False, description="Sauvegarder automatiquement dans la base"),
    db: Session = Depends(get_session)
):
    """
    Extrait les informations d'un courrier PAP depuis une image ou un PDF.

    **Utilisation:**
    1. Upload une image (JPG, PNG) ou un PDF du courrier PAP
    2. L'API utilise GPT-4 Vision pour extraire automatiquement les informations
    3. Si auto_save=true, crée automatiquement une invitation dans la base

    **Informations extraites:**
    - SIRET, SIREN
    - Raison sociale, adresse
    - Dates (invitation, élection, limite candidature)
    - Effectif, collèges, sièges
    - Convention collective (IDCC)
    - Contacts
    - Et bien plus...

    **Exemples:**
    ```bash
    # Extraction simple
    curl -X POST "http://localhost:8000/api/extract/document" \\
      -F "file=@courrier_pap.jpg"

    # Extraction avec sauvegarde automatique
    curl -X POST "http://localhost:8000/api/extract/document?auto_save=true" \\
      -F "file=@courrier_pap.jpg"
    ```
    """
    try:
        # Vérifier le type de fichier
        if file.content_type not in [
            "image/jpeg", "image/jpg", "image/png", "image/webp",
            "application/pdf"
        ]:
            raise HTTPException(
                status_code=400,
                detail=f"Type de fichier non supporté: {file.content_type}. "
                       f"Formats acceptés: JPG, PNG, WEBP, PDF"
            )

        # Lire le fichier
        file_data = await file.read()

        # Déterminer si c'est un PDF
        is_pdf = file.content_type == "application/pdf"

        # Extraire les informations
        extractor = DocumentExtractor()
        extracted_data = await extractor.extract_from_document(file_data, is_pdf=is_pdf)

        # Log de l'extraction
        log_admin_action(
            request=request,
            api_key=None,  # Pas d'authentification pour ce endpoint public
            action="extract_document",
            resource_type="document",
            success=True,
            resource_id=extracted_data.get("siret", "unknown"),
            request_params={
                "filename": file.filename,
                "auto_save": auto_save
            },
            response_summary={
                "confidence": extracted_data.get("confidence"),
                "siret": extracted_data.get("siret")
            }
        )

        # Sauvegarder automatiquement si demandé
        saved_invitation = None
        if auto_save and extracted_data.get("siret"):
            try:
                saved_invitation = await _save_as_invitation(
                    extracted_data=extracted_data,
                    db=db
                )
                logger.info(f"Invitation créée automatiquement - SIRET: {extracted_data['siret']}")
            except Exception as e:
                logger.error(f"Erreur lors de la sauvegarde automatique: {str(e)}")
                # Ne pas bloquer l'extraction si la sauvegarde échoue

        return ExtractionResult(
            success=True,
            data=extracted_data,
            metadata={
                "auto_saved": saved_invitation is not None,
                "invitation_id": saved_invitation.id if saved_invitation else None
            }
        )

    except DocumentExtractorError as e:
        logger.error(f"Erreur d'extraction: {str(e)}")
        raise HTTPException(status_code=422, detail=str(e))

    except Exception as e:
        logger.error(f"Erreur inattendue: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")


@router.post("/batch", response_model=BatchExtractionResult)
async def extract_batch(
    request: Request,
    files: List[UploadFile] = File(..., description="Liste d'images de courriers PAP"),
    auto_save: bool = Form(False, description="Sauvegarder automatiquement dans la base"),
    db: Session = Depends(get_session)
):
    """
    Extrait les informations de plusieurs courriers PAP en une seule requête.

    **Utilisation:**
    - Upload plusieurs images de courriers PAP
    - Traite tous les documents en séquence
    - Retourne un résumé avec les succès et échecs

    **Exemple:**
    ```bash
    curl -X POST "http://localhost:8000/api/extract/batch" \\
      -F "files=@courrier1.jpg" \\
      -F "files=@courrier2.jpg" \\
      -F "files=@courrier3.jpg" \\
      -F "auto_save=true"
    ```
    """
    results = []
    successful = 0
    failed = 0
    total_cost = 0.0

    extractor = DocumentExtractor()

    for i, file in enumerate(files, 1):
        logger.info(f"Traitement du fichier {i}/{len(files)}: {file.filename}")

        try:
            file_data = await file.read()

            # Vérifier le type
            if file.content_type not in [
                "image/jpeg", "image/jpg", "image/png", "image/webp",
                "application/pdf"
            ]:
                raise ValueError(f"Type de fichier non supporté: {file.content_type}")

            # Déterminer si c'est un PDF
            is_pdf = file.content_type == "application/pdf"

            # Extraire
            extracted_data = extractor.extract_from_document(file_data, is_pdf=is_pdf)

            # Sauvegarder si demandé
            saved_invitation = None
            if auto_save and extracted_data.get("siret"):
                try:
                    saved_invitation = await _save_as_invitation(extracted_data, db)
                except Exception as e:
                    logger.error(f"Erreur sauvegarde fichier {i}: {str(e)}")

            results.append(ExtractionResult(
                success=True,
                data=extracted_data,
                metadata={
                    "filename": file.filename,
                    "auto_saved": saved_invitation is not None,
                    "invitation_id": saved_invitation.id if saved_invitation else None
                }
            ))

            successful += 1
            total_cost += extracted_data.get("_metadata", {}).get("cost_estimate_usd", 0)

        except Exception as e:
            logger.error(f"Échec fichier {i} ({file.filename}): {str(e)}")
            results.append(ExtractionResult(
                success=False,
                error=str(e),
                metadata={"filename": file.filename}
            ))
            failed += 1

    # Log du batch
    log_admin_action(
        request=request,
        api_key=None,  # Pas d'authentification pour ce endpoint public
        action="extract_batch",
        resource_type="document_batch",
        success=True,
        resource_id=f"batch_{len(files)}",
        request_params={
            "total_files": len(files),
            "auto_save": auto_save
        },
        response_summary={
            "successful": successful,
            "failed": failed,
            "total_cost_usd": total_cost
        }
    )

    return BatchExtractionResult(
        total=len(files),
        successful=successful,
        failed=failed,
        results=results,
        total_cost_usd=total_cost
    )


@router.post("/save-invitation")
async def save_invitation(
    request: Request,
    invitation: InvitationCreate,
    db: Session = Depends(get_session)
):
    """
    Sauvegarde manuellement une invitation depuis des données extraites.

    Utile si vous avez fait une extraction sans auto_save et voulez
    sauvegarder les résultats après révision.
    """
    try:
        # Vérifier si une invitation existe déjà pour ce SIRET
        existing = db.query(Invitation).filter(
            Invitation.siret == invitation.siret,
            Invitation.date_invit == invitation.date_invit
        ).first()

        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Une invitation existe déjà pour ce SIRET à cette date"
            )

        # Créer l'invitation
        new_invitation = Invitation(
            siret=invitation.siret,
            date_invit=invitation.date_invit,
            source=invitation.source,
            ud=invitation.ud,
            fd=invitation.fd,
            idcc=invitation.idcc,
            effectif_connu=invitation.effectif_connu,
            date_reception=invitation.date_reception,
            date_election=invitation.date_election,
            structure_saisie=invitation.structure_saisie,
            raw={}  # Les données brutes seront ajoutées si nécessaire
        )

        db.add(new_invitation)
        db.commit()
        db.refresh(new_invitation)

        log_admin_action(
            request=request,
            api_key=None,  # Pas d'authentification pour ce endpoint public
            action="save_invitation_from_extraction",
            resource_type="invitation",
            success=True,
            resource_id=str(new_invitation.id),
            request_params={
                "siret": invitation.siret
            },
            response_summary={
                "invitation_id": new_invitation.id
            }
        )

        return {
            "success": True,
            "invitation_id": new_invitation.id,
            "siret": new_invitation.siret
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


async def _save_as_invitation(
    extracted_data: Dict[str, Any],
    db: Session
) -> Optional[Invitation]:
    """
    Sauvegarde automatiquement les données extraites comme invitation.

    Args:
        extracted_data: Données extraites par GPT
        db: Session de base de données

    Returns:
        L'invitation créée ou None si erreur
    """
    try:
        siret = extracted_data.get("siret")
        if not siret or len(siret) != 14:
            logger.warning("SIRET invalide ou manquant, impossible de sauvegarder")
            return None

        # Parser la date d'invitation
        date_invit_str = extracted_data.get("date_invitation")
        if date_invit_str:
            try:
                date_invit = datetime.strptime(date_invit_str, "%Y-%m-%d").date()
            except ValueError:
                date_invit = datetime.now().date()
        else:
            date_invit = datetime.now().date()

        # Parser la date d'élection
        date_election = None
        date_election_str = extracted_data.get("date_election")
        if date_election_str:
            try:
                date_election = datetime.strptime(date_election_str, "%Y-%m-%d").date()
            except ValueError:
                pass

        # Vérifier si existe déjà
        existing = db.query(Invitation).filter(
            Invitation.siret == siret,
            Invitation.date_invit == date_invit
        ).first()

        if existing:
            logger.warning(f"Invitation déjà existante pour {siret} à la date {date_invit}")
            return existing

        # Créer l'invitation
        invitation = Invitation(
            siret=siret,
            date_invit=date_invit,
            source="Scan automatique",
            ud=None,  # À remplir manuellement
            fd=None,  # À remplir manuellement
            idcc=extracted_data.get("idcc"),
            effectif_connu=extracted_data.get("effectif"),
            date_election=date_election,
            date_reception=datetime.now().date(),
            structure_saisie="Scanner PAP",
            raw=extracted_data  # Stocker toutes les données extraites
        )

        db.add(invitation)
        db.commit()
        db.refresh(invitation)

        return invitation

    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde automatique: {str(e)}")
        db.rollback()
        return None


@router.get("/health")
async def health_check():
    """
    Vérifie que le service d'extraction est opérationnel.

    Retourne l'état du service et la configuration OpenAI.
    """
    from ..config import OPENAI_API_KEY

    is_configured = OPENAI_API_KEY is not None and OPENAI_API_KEY != ""

    return {
        "status": "operational" if is_configured else "not_configured",
        "openai_configured": is_configured,
        "message": "Service d'extraction prêt" if is_configured else
                   "Clé OpenAI non configurée. Ajoutez OPENAI_API_KEY dans le fichier .env"
    }
