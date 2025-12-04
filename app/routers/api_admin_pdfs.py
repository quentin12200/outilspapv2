"""
Routes API pour la gestion des PDFs PAP stockés
"""

import logging
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ..user_auth import require_admin_user
from ..audit import log_admin_action
from ..db import get_session
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/pdfs", tags=["Admin PDFs"])

# Répertoire de stockage des PDFs - Utilise le volume Railway persistant
PAP_UPLOADS_DIR = Path("/app/data/pap_uploads")
PAP_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


class PDFInfo(BaseModel):
    filename: str
    siret: Optional[str] = None
    date_upload: str
    size_kb: float
    url: str
    age_days: int


class PDFListResponse(BaseModel):
    success: bool
    total: int
    total_size_mb: float
    pdfs: List[PDFInfo]


class CleanupRequest(BaseModel):
    days_old: int = 90


class CleanupResponse(BaseModel):
    success: bool
    deleted_count: int
    freed_space_mb: float
    message: str


@router.get("/list", response_model=PDFListResponse)
async def list_pdfs(
    current_user = Depends(require_admin_user)
):
    """
    Liste tous les PDFs PAP stockés avec leurs métadonnées.
    """
    try:
        pdfs = []
        total_size = 0

        # Parcourir tous les PDFs dans le dossier
        for pdf_path in PAP_UPLOADS_DIR.glob("*.pdf"):
            if pdf_path.name == ".gitkeep":
                continue

            try:
                stat = pdf_path.stat()
                size_kb = stat.st_size / 1024
                total_size += stat.st_size

                # Extraire SIRET du nom de fichier (format: SIRET_DATE.pdf)
                filename = pdf_path.name
                siret = None
                date_str = None

                if "_" in filename:
                    parts = filename.replace(".pdf", "").split("_")
                    if len(parts) >= 2 and parts[0].isdigit() and len(parts[0]) == 14:
                        siret = parts[0]
                        date_str = parts[1] if len(parts[1]) == 8 else None

                # Date de modification du fichier
                mtime = datetime.fromtimestamp(stat.st_mtime)
                age_days = (datetime.now() - mtime).days

                pdfs.append(PDFInfo(
                    filename=filename,
                    siret=siret,
                    date_upload=mtime.strftime("%Y-%m-%d %H:%M:%S"),
                    size_kb=round(size_kb, 2),
                    url=f"/pap-pdfs/{filename}",
                    age_days=age_days
                ))
            except Exception as e:
                logger.error(f"Erreur lecture fichier {pdf_path}: {e}")

        # Trier par date (plus récent en premier)
        pdfs.sort(key=lambda x: x.date_upload, reverse=True)

        return PDFListResponse(
            success=True,
            total=len(pdfs),
            total_size_mb=round(total_size / (1024 * 1024), 2),
            pdfs=pdfs
        )

    except Exception as e:
        logger.error(f"Erreur lors du listage des PDFs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete/{filename}")
async def delete_pdf(
    filename: str,
    db: Session = Depends(get_session),
    current_user = Depends(require_admin_user)
):
    """
    Supprime un PDF spécifique.
    """
    try:
        # Validation du nom de fichier (sécurité)
        if ".." in filename or "/" in filename or "\\" in filename:
            raise HTTPException(status_code=400, detail="Nom de fichier invalide")

        pdf_path = PAP_UPLOADS_DIR / filename

        if not pdf_path.exists():
            raise HTTPException(status_code=404, detail="PDF non trouvé")

        # Récupérer la taille avant suppression
        size_mb = pdf_path.stat().st_size / (1024 * 1024)

        # Supprimer le fichier
        pdf_path.unlink()

        # Logger l'action
        log_admin_action(
            db=db,
            user_id=current_user.id if hasattr(current_user, 'id') else None,
            action="delete_pdf",
            details={"filename": filename, "size_mb": round(size_mb, 2)}
        )

        return {
            "success": True,
            "message": f"PDF {filename} supprimé avec succès",
            "freed_space_mb": round(size_mb, 2)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la suppression du PDF {filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cleanup", response_model=CleanupResponse)
async def cleanup_old_pdfs(
    request: CleanupRequest,
    db: Session = Depends(get_session),
    current_user = Depends(require_admin_user)
):
    """
    Supprime les PDFs plus vieux que X jours.
    """
    try:
        cutoff_date = datetime.now() - timedelta(days=request.days_old)
        deleted_count = 0
        freed_space = 0

        for pdf_path in PAP_UPLOADS_DIR.glob("*.pdf"):
            if pdf_path.name == ".gitkeep":
                continue

            try:
                mtime = datetime.fromtimestamp(pdf_path.stat().st_mtime)

                if mtime < cutoff_date:
                    size = pdf_path.stat().st_size
                    pdf_path.unlink()
                    deleted_count += 1
                    freed_space += size
                    logger.info(f"PDF supprimé: {pdf_path.name} (age: {(datetime.now() - mtime).days} jours)")

            except Exception as e:
                logger.error(f"Erreur suppression {pdf_path.name}: {e}")

        freed_space_mb = freed_space / (1024 * 1024)

        # Logger l'action
        log_admin_action(
            db=db,
            user_id=current_user.id if hasattr(current_user, 'id') else None,
            action="cleanup_pdfs",
            details={
                "days_old": request.days_old,
                "deleted_count": deleted_count,
                "freed_space_mb": round(freed_space_mb, 2)
            }
        )

        return CleanupResponse(
            success=True,
            deleted_count=deleted_count,
            freed_space_mb=round(freed_space_mb, 2),
            message=f"{deleted_count} PDF(s) supprimé(s), {round(freed_space_mb, 2)} MB libérés"
        )

    except Exception as e:
        logger.error(f"Erreur lors du nettoyage des PDFs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_pdf_stats(
    current_user = Depends(require_admin_user)
):
    """
    Retourne les statistiques sur les PDFs stockés.
    """
    try:
        total_count = 0
        total_size = 0
        by_age = {
            "moins_7_jours": 0,
            "7_30_jours": 0,
            "30_90_jours": 0,
            "plus_90_jours": 0
        }

        for pdf_path in PAP_UPLOADS_DIR.glob("*.pdf"):
            if pdf_path.name == ".gitkeep":
                continue

            try:
                stat = pdf_path.stat()
                total_count += 1
                total_size += stat.st_size

                mtime = datetime.fromtimestamp(stat.st_mtime)
                age_days = (datetime.now() - mtime).days

                if age_days < 7:
                    by_age["moins_7_jours"] += 1
                elif age_days < 30:
                    by_age["7_30_jours"] += 1
                elif age_days < 90:
                    by_age["30_90_jours"] += 1
                else:
                    by_age["plus_90_jours"] += 1

            except Exception as e:
                logger.error(f"Erreur lecture {pdf_path.name}: {e}")

        return {
            "success": True,
            "total_count": total_count,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "by_age": by_age,
            "directory": str(PAP_UPLOADS_DIR.absolute())
        }

    except Exception as e:
        logger.error(f"Erreur lors du calcul des stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import-existing")
async def import_existing_pdfs(
    request: Request,
    force_reimport: bool = False,
    db: Session = Depends(get_session),
    current_user = Depends(require_admin_user)
):
    """
    Importe tous les PDFs existants dans le volume Railway vers la table pap_documents.

    Pour chaque PDF:
    - Extrait le SIRET du nom de fichier (format: SIRET_DATE.pdf)
    - OU cherche le SIRET dans EmailLog pour les PDFs avec UUID
    - Cherche les données dans la table invitations (si disponible)
    - Crée un enregistrement PAPDocument (avec ou sans données complètes)
    - Les PAPs apparaissent ensuite dans les portails UD/FD

    Cette fonction gère:
    - PDFs avec format SIRET_DATE.pdf (nouveaux)
    - PDFs avec UUID.pdf (anciens, retrouve SIRET via EmailLog)
    - Imports avec ou sans invitation (données minimales si pas d'invitation)

    Args:
        force_reimport: Si True, réimporte même les PDFs déjà en base (met à jour)
    """
    try:
        from ..models import PAPDocument, Invitation
        import re

        imported = 0
        updated = 0
        skipped = 0
        errors = []

        logger.info(f"🔄 Démarrage import en masse des PDFs existants (force_reimport={force_reimport})...")

        # Lister tous les PDFs
        pdf_files = list(PAP_UPLOADS_DIR.glob("*.pdf"))
        total_pdfs = len(pdf_files)

        logger.info(f"📁 {total_pdfs} PDF(s) trouvé(s) dans {PAP_UPLOADS_DIR}")

        for pdf_path in pdf_files:
            if pdf_path.name == ".gitkeep":
                continue

            try:
                # Vérifier si déjà importé
                existing = db.query(PAPDocument).filter(
                    PAPDocument.filename == pdf_path.name
                ).first()

                is_reimport = False
                if existing and not force_reimport:
                    skipped += 1
                    logger.debug(f"⏭️  {pdf_path.name} déjà importé")
                    continue
                elif existing and force_reimport:
                    # Supprimer l'ancien pour le recréer
                    db.delete(existing)
                    is_reimport = True
                    logger.info(f"🔄 {pdf_path.name} - suppression de l'ancien enregistrement pour ré-importation")

                siret = None

                # Méthode 1 : Extraire le SIRET du nom du fichier (format: SIRET_DATE.pdf)
                match = re.match(r'(\d{14})_\d{8}\.pdf', pdf_path.name)
                if match:
                    siret = match.group(1)
                    logger.debug(f"📄 {pdf_path.name} - SIRET extrait du nom: {siret}")
                else:
                    # Méthode 2 : Chercher dans EmailLog pour les PDFs avec UUID
                    from ..models import EmailLog

                    # Chercher un email qui a ce PDF en attachement ou dans metadata
                    email_log = db.query(EmailLog).filter(
                        EmailLog.extra_metadata.cast(String).contains(pdf_path.name)
                    ).first()

                    if email_log and email_log.siret:
                        siret = email_log.siret
                        logger.debug(f"📧 {pdf_path.name} - SIRET trouvé via EmailLog: {siret}")
                    else:
                        # Méthode 3 : Chercher par nom de fichier dans les metadata
                        email_with_file = db.query(EmailLog).filter(
                            EmailLog.extra_metadata.cast(String).contains(pdf_path.name.replace('.pdf', ''))
                        ).first()

                        if email_with_file and email_with_file.siret:
                            siret = email_with_file.siret
                            logger.debug(f"📎 {pdf_path.name} - SIRET trouvé via metadata: {siret}")

                if not siret:
                    errors.append({
                        'filename': pdf_path.name,
                        'error': 'Impossible de trouver le SIRET (format invalide et pas dans EmailLog)'
                    })
                    logger.warning(f"⚠️  {pdf_path.name} - SIRET introuvable")
                    continue

                # Chercher les données dans la table invitations
                invitation = db.query(Invitation).filter(
                    Invitation.siret == siret
                ).first()

                # Calculer la taille du fichier
                file_size_kb = pdf_path.stat().st_size / 1024

                # Si on a une invitation, utiliser ses données
                if invitation:
                    fd_value = invitation.fd if invitation.fd else "sans fd"

                    pap_doc = PAPDocument(
                        filename=pdf_path.name,
                        pdf_url=f"/pap-pdfs/{pdf_path.name}",
                        file_size_kb=file_size_kb,
                        siret=siret,
                        raison_sociale=invitation.raison_sociale,
                        ville=invitation.ville,
                        code_postal=invitation.code_postal,
                        effectif=invitation.effectif,
                        inscrits=invitation.inscrits,
                        date_invitation=invitation.date_invitation,
                        date_election=invitation.date_election,
                        numero_departement=invitation.numero_departement,
                        nom_departement=invitation.nom_departement,
                        ud=invitation.ud,
                        fd=fd_value,
                        idcc=invitation.idcc,
                        is_priority=invitation.is_priority or False,
                        priority_reasons=invitation.priority_reasons,
                        has_cgt_history=invitation.has_cgt_history or False,
                        cgt_c3=invitation.cgt_c3 or False,
                        cgt_c4=invitation.cgt_c4 or False,
                        created_by=current_user.id if hasattr(current_user, 'id') else None,
                        is_active=True,
                        uploaded_at=datetime.fromtimestamp(pdf_path.stat().st_mtime)
                    )

                    db.add(pap_doc)
                    if is_reimport:
                        updated += 1
                        logger.info(f"🔄 {pdf_path.name} ré-importé (SIRET: {siret}, UD: {invitation.ud}, FD: {fd_value})")
                    else:
                        imported += 1
                        logger.info(f"✅ {pdf_path.name} importé (SIRET: {siret}, UD: {invitation.ud}, FD: {fd_value})")

                else:
                    # Pas d'invitation, mais on importe quand même avec données minimales
                    # Chercher dans EmailLog pour avoir des données supplémentaires
                    from ..models import EmailLog
                    email_log = db.query(EmailLog).filter(
                        EmailLog.siret == siret
                    ).order_by(EmailLog.created_at.desc()).first()

                    # Essayer d'extraire des infos de l'email
                    raison_sociale = None
                    if email_log and email_log.extra_metadata:
                        metadata = email_log.extra_metadata
                        if isinstance(metadata, dict):
                            raison_sociale = metadata.get('raison_sociale')

                    pap_doc = PAPDocument(
                        filename=pdf_path.name,
                        pdf_url=f"/pap-pdfs/{pdf_path.name}",
                        file_size_kb=file_size_kb,
                        siret=siret,
                        raison_sociale=raison_sociale or f"Entreprise {siret}",
                        ville=None,
                        code_postal=None,
                        effectif=None,
                        inscrits=None,
                        date_invitation=None,
                        date_election=None,
                        numero_departement=None,
                        nom_departement=None,
                        ud="inconnu",
                        fd="inconnu",
                        idcc=None,
                        is_priority=False,
                        priority_reasons=None,
                        has_cgt_history=False,
                        cgt_c3=False,
                        cgt_c4=False,
                        created_by=current_user.id if hasattr(current_user, 'id') else None,
                        is_active=True,
                        uploaded_at=datetime.fromtimestamp(pdf_path.stat().st_mtime)
                    )

                    db.add(pap_doc)
                    if is_reimport:
                        updated += 1
                        logger.warning(f"🔄 {pdf_path.name} ré-importé sans invitation (SIRET: {siret}, données incomplètes)")
                    else:
                        imported += 1
                        logger.warning(f"⚠️  {pdf_path.name} importé sans invitation (SIRET: {siret}, données incomplètes)")

            except Exception as e:
                errors.append({
                    'filename': pdf_path.name,
                    'error': str(e)
                })
                logger.error(f"❌ Erreur import {pdf_path.name}: {e}")

        # Commit tous les imports d'un coup
        if imported > 0 or updated > 0:
            db.commit()
            logger.info(f"💾 {imported} PDF(s) importé(s), {updated} PDF(s) ré-importé(s) en base de données")

        # Logger l'action
        log_admin_action(
            request=request,
            api_key=None,
            action="import_existing_pdfs",
            resource_type="pdfs",
            success=True,
            resource_id=f"batch_{imported}",
            request_params={
                "total_pdfs": total_pdfs
            },
            response_summary={
                "imported": imported,
                "updated": updated,
                "skipped": skipped,
                "errors_count": len(errors)
            }
        )

        return {
            "success": True,
            "total_pdfs": total_pdfs,
            "imported": imported,
            "updated": updated,
            "skipped": skipped,
            "errors": errors,
            "message": f"{imported} PDF(s) importé(s), {updated} ré-importé(s), {skipped} déjà existant(s), {len(errors)} erreur(s)"
        }

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Erreur lors de l'import en masse: {e}")
        raise HTTPException(status_code=500, detail=str(e))
