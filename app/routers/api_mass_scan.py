"""
API pour le scan en masse de PAP avec classification automatique

Fonctionnalités:
- Upload multiple de fichiers PAP
- Analyse et extraction automatique des données
- Classification en "PAP à enjeux" vs "PAP standards"
- Génération de templates d'email personnalisés
"""

import os
import asyncio
import logging
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func

logger = logging.getLogger(__name__)

from ..db import get_db
from ..models import MassScanBatch, MassScanPAP, User, SiretSummary, Invitation, PVEvent
from ..user_auth import require_admin_user
from ..services.sirene_api import SireneAPI
from ..services.pappers_api import PappersAPI
from ..services.pap_extractor import extract_pap_auto, PAPExtractionError
from ..etl import ingest_pv_excel

router = APIRouter(prefix="/api/mass-scan", tags=["mass-scan"])


def get_average_effectif_by_department(db: Session, departement: str) -> Optional[float]:
    """
    Calcule l'effectif moyen des entreprises d'un département
    """
    try:
        avg_effectif = db.query(func.avg(SiretSummary.inscrits_c4)).filter(
            SiretSummary.dep == departement,
            SiretSummary.inscrits_c4 > 0
        ).scalar()

        return avg_effectif or 0
    except Exception as e:
        print(f"Erreur calcul effectif moyen département {departement}: {e}")
        return None


def classify_pap(
    siret: str,
    effectif_total: int,
    inscrits: int,
    effectif_departement: float,
    raison_sociale: str,
    db: Session
) -> tuple[bool, str]:
    """
    Classifie un PAP en "enjeux" ou "standard"

    Critères pour PAP à enjeux:
    1. Entreprise de + de 1000 salariés
    2. Entreprise avec nombre d'inscrits significativement supérieur à la moyenne départementale

    Returns:
        tuple[bool, str]: (is_enjeux, raison)
    """
    raisons = []
    is_enjeux = False

    # Critère 1: Entreprise de + de 1000 salariés
    if effectif_total and effectif_total >= 1000:
        is_enjeux = True
        raisons.append(f"Entreprise de grande taille ({effectif_total} salariés)")

    # Critère 2: Inscrits importants par rapport au département
    if inscrits and effectif_departement:
        # Considérer comme important si > 2x la moyenne départementale
        seuil_important = effectif_departement * 2
        if inscrits >= seuil_important:
            is_enjeux = True
            raisons.append(f"Nombre d'inscrits important ({inscrits} vs moyenne départementale de {int(effectif_departement)})")

    # Vérifier si l'entreprise a déjà une présence CGT forte
    existing_pv = db.query(SiretSummary).filter(SiretSummary.siret == siret).first()
    if existing_pv:
        if existing_pv.cgt_implantee:
            raisons.append("CGT déjà implantée")
            is_enjeux = True

    raison_texte = " ; ".join(raisons) if raisons else "Entreprise standard"

    return is_enjeux, raison_texte


def generate_email_template(pap: MassScanPAP, is_enjeux: bool) -> tuple[str, str]:
    """
    Génère le template d'email selon le type de PAP

    Returns:
        tuple[str, str]: (subject, body)
    """
    if is_enjeux:
        # Email pour PAP à enjeux
        subject = f"🔴 PAP À ENJEUX - {pap.raison_sociale or pap.denomination}"

        body = f"""<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; }}
        .header {{ background-color: #cc0000; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; }}
        .important {{ background-color: #fff3cd; border-left: 5px solid #ffc107; padding: 15px; margin: 20px 0; }}
        .info {{ background-color: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 5px; }}
        .info-label {{ font-weight: bold; color: #495057; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>⚠️ PROCÈS-VERBAL À ENJEUX</h1>
    </div>

    <div class="content">
        <div class="important">
            <strong>🎯 ATTENTION : Cette entreprise nécessite une attention particulière</strong>
            <br>
            Raison : {pap.raison_enjeux}
        </div>

        <h2>📋 Informations de l'entreprise</h2>
        <div class="info">
            <p><span class="info-label">Raison sociale :</span> {pap.raison_sociale or pap.denomination}</p>
            <p><span class="info-label">SIRET :</span> {pap.siret}</p>
            <p><span class="info-label">Adresse :</span> {pap.adresse or 'N/A'}</p>
            <p><span class="info-label">Code postal :</span> {pap.code_postal or 'N/A'}</p>
            <p><span class="info-label">Commune :</span> {pap.commune or 'N/A'}</p>
        </div>

        <h2>👥 Données sociales</h2>
        <div class="info">
            <p><span class="info-label">Union Départementale (UD) :</span> {pap.ud or 'À déterminer'}</p>
            <p><span class="info-label">Fédération (FD) :</span> {pap.fd or 'À déterminer'}</p>
            <p><span class="info-label">Effectif total :</span> {pap.effectif_total or 'N/A'} salariés</p>
            <p><span class="info-label">Nombre d'inscrits :</span> {pap.inscrits or 'N/A'}</p>
            <p><span class="info-label">IDCC :</span> {pap.idcc or 'N/A'}</p>
        </div>

        <div class="important">
            <strong>📎 Le procès-verbal est joint à cet email</strong>
            <br>
            Merci de traiter ce dossier en priorité.
        </div>

        <p style="margin-top: 30px; color: #6c757d; font-size: 12px;">
            Ce message a été généré automatiquement par la plateforme CGT Outilspap.
        </p>
    </div>
</body>
</html>"""
    else:
        # Email standard
        subject = f"PAP - {pap.raison_sociale or pap.denomination}"

        body = f"""<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; }}
        .header {{ background-color: #0056b3; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; }}
        .info {{ background-color: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 5px; }}
        .info-label {{ font-weight: bold; color: #495057; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📄 Procès-Verbal Electoral</h1>
    </div>

    <div class="content">
        <h2>📋 Informations de l'entreprise</h2>
        <div class="info">
            <p><span class="info-label">Raison sociale :</span> {pap.raison_sociale or pap.denomination}</p>
            <p><span class="info-label">SIRET :</span> {pap.siret}</p>
            <p><span class="info-label">Adresse :</span> {pap.adresse or 'N/A'}</p>
            <p><span class="info-label">Code postal :</span> {pap.code_postal or 'N/A'}</p>
            <p><span class="info-label">Commune :</span> {pap.commune or 'N/A'}</p>
        </div>

        <h2>👥 Données sociales</h2>
        <div class="info">
            <p><span class="info-label">Union Départementale (UD) :</span> {pap.ud or 'À déterminer'}</p>
            <p><span class="info-label">Fédération (FD) :</span> {pap.fd or 'À déterminer'}</p>
            <p><span class="info-label">Effectif total :</span> {pap.effectif_total or 'N/A'} salariés</p>
            <p><span class="info-label">Nombre d'inscrits :</span> {pap.inscrits or 'N/A'}</p>
            <p><span class="info-label">IDCC :</span> {pap.idcc or 'N/A'}</p>
        </div>

        <p style="margin-top: 20px;">
            📎 Le procès-verbal est joint à cet email.
        </p>

        <p style="margin-top: 30px; color: #6c757d; font-size: 12px;">
            Ce message a été généré automatiquement par la plateforme CGT Outilspap.
        </p>
    </div>
</body>
</html>"""

    return subject, body


async def analyze_pap_file(
    file_path: str,
    file_name: str,
    batch_id: int,
    db: Session,
    sirene_api: SireneAPI,
    pappers_api: PappersAPI
) -> MassScanPAP:
    """
    Analyse un fichier PAP et extrait les informations via ETL ou IA
    """
    try:
        # Extraire les données du fichier (auto-détection Excel vs Image/PDF)
        pap_data = await extract_pap_auto(file_path)

        # Créer l'objet MassScanPAP avec les données extraites
        pap = MassScanPAP(
            batch_id=batch_id,
            file_name=file_name,
            file_path=file_path,
            siret=pap_data.get('siret'),
            raison_sociale=pap_data.get('raison_sociale'),
            inscrits=pap_data.get('inscrits'),
            ud=pap_data.get('ud'),
            fd=pap_data.get('fd'),
            idcc=pap_data.get('idcc'),
            code_postal=pap_data.get('cp'),
            commune=pap_data.get('ville'),
            adresse=pap_data.get('adresse'),
            status='pending'  # Sera mis à jour lors de l'enrichissement
        )

        return pap

    except PAPExtractionError as e:
        print(f"Erreur extraction PAP {file_name}: {e}")
        pap = MassScanPAP(
            batch_id=batch_id,
            file_name=file_name,
            file_path=file_path,
            status='error',
            error=f"Extraction échouée: {str(e)}"
        )
        return pap
    except Exception as e:
        print(f"Erreur inattendue PAP {file_name}: {e}")
        pap = MassScanPAP(
            batch_id=batch_id,
            file_name=file_name,
            file_path=file_path,
            status='error',
            error=str(e)
        )
        return pap


async def process_batch_analysis(
    batch_id: int,
    db: Session
):
    """
    Traite l'analyse d'un lot de PAP en arrière-plan
    """
    try:
        # Récupérer le batch
        batch = db.query(MassScanBatch).filter(MassScanBatch.id == batch_id).first()
        if not batch:
            return

        # Mettre à jour le statut
        batch.status = 'processing'
        db.commit()

        # Récupérer tous les PAP du batch
        paps = db.query(MassScanPAP).filter(MassScanPAP.batch_id == batch_id).all()

        sirene_api = SireneAPI()
        pappers_api = PappersAPI()

        paps_enjeux = 0
        paps_standard = 0

        for pap in paps:
            try:
                # Étape 1: Extraire les données du fichier si pas déjà fait
                if not pap.siret and pap.file_path:
                    try:
                        logger.info(f"Extraction des données pour {pap.file_name}")
                        pap_data = await extract_pap_auto(pap.file_path)

                        # Mettre à jour le PAP avec les données extraites
                        pap.siret = pap_data.get('siret')
                        pap.raison_sociale = pap_data.get('raison_sociale')
                        pap.inscrits = pap_data.get('inscrits')
                        pap.ud = pap_data.get('ud')
                        pap.fd = pap_data.get('fd')
                        pap.idcc = pap_data.get('idcc')
                        pap.code_postal = pap_data.get('cp')
                        pap.commune = pap_data.get('ville')
                        pap.adresse = pap_data.get('adresse')

                        db.commit()
                        logger.info(f"✅ Extraction réussie: {pap.siret}")

                    except PAPExtractionError as e:
                        logger.error(f"❌ Erreur extraction {pap.file_name}: {e}")
                        pap.status = 'error'
                        pap.error = f"Extraction échouée: {str(e)}"
                        db.commit()
                        continue

                # Étape 2: Si le PAP a un SIRET, enrichir les données via Pappers/Sirene
                if pap.siret:
                    # Récupérer les infos de l'entreprise
                    try:
                        pappers_data = await pappers_api.get_siret(pap.siret)
                        if pappers_data:
                            pap.denomination = pappers_data.get('denomination')
                            pap.adresse = pappers_data.get('adresse')
                            pap.code_postal = pappers_data.get('code_postal')
                            pap.commune = pappers_data.get('commune')
                            pap.effectif_total = pappers_data.get('effectif')
                    except:
                        # Fallback sur Sirene
                        sirene_data = await sirene_api.get_siret(pap.siret)
                        if sirene_data:
                            pap.denomination = sirene_data.get('denomination')
                            pap.adresse = sirene_data.get('adresse')
                            pap.code_postal = sirene_data.get('code_postal')
                            pap.commune = sirene_data.get('commune')

                    # Déterminer l'UD à partir du code postal
                    if pap.code_postal:
                        dep = pap.code_postal[:2]
                        pap.ud = f"UD {dep}"

                        # Calculer l'effectif moyen du département
                        avg_effectif = get_average_effectif_by_department(db, dep)
                        if avg_effectif:
                            pap.effectif_departement = int(avg_effectif)

                    # Classifier le PAP
                    is_enjeux, raison = classify_pap(
                        pap.siret,
                        pap.effectif_total or 0,
                        pap.inscrits or 0,
                        pap.effectif_departement or 0,
                        pap.raison_sociale or pap.denomination or "",
                        db
                    )

                    pap.is_enjeux = is_enjeux
                    pap.raison_enjeux = raison

                    # Générer le template d'email
                    subject, body = generate_email_template(pap, is_enjeux)
                    pap.email_subject = subject
                    pap.email_body = body
                    pap.email_recipient = pap.ud

                    if is_enjeux:
                        paps_enjeux += 1
                    else:
                        paps_standard += 1

                    pap.status = 'analyzed'
                    pap.analyzed_at = datetime.now()

                db.commit()

            except Exception as e:
                print(f"Erreur traitement PAP {pap.id}: {e}")
                pap.status = 'error'
                pap.error = str(e)
                db.commit()

        # Mettre à jour le batch
        batch.status = 'completed'
        batch.completed_at = datetime.now()
        batch.paps_enjeux = paps_enjeux
        batch.paps_standard = paps_standard
        db.commit()

    except Exception as e:
        print(f"Erreur traitement batch {batch_id}: {e}")
        batch.status = 'failed'
        db.commit()


@router.post("/create-batch")
async def create_batch(
    files: List[UploadFile] = File(...),
    background_tasks: BackgroundTasks = None,
    user: User = Depends(require_admin_user),
    db: Session = Depends(get_db)
):
    """
    Crée un nouveau lot de scan en masse et upload les fichiers PAP
    """
    try:
        # Créer le batch
        batch = MassScanBatch(
            user_id=user.id,
            user_email=user.email,
            total_paps=len(files),
            status='pending'
        )
        db.add(batch)
        db.commit()
        db.refresh(batch)

        # Créer le dossier pour stocker les fichiers
        upload_dir = f"uploads/mass_scan/{batch.id}"
        os.makedirs(upload_dir, exist_ok=True)

        # Sauvegarder chaque fichier et créer un MassScanPAP
        for file in files:
            # Sauvegarder le fichier
            file_path = os.path.join(upload_dir, file.filename)
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)

            # Créer l'objet MassScanPAP
            pap = MassScanPAP(
                batch_id=batch.id,
                file_name=file.filename,
                file_path=file_path,
                status='pending'
            )
            db.add(pap)

        db.commit()

        # Lancer l'analyse en arrière-plan
        if background_tasks:
            background_tasks.add_task(process_batch_analysis, batch.id, db)

        return {
            "success": True,
            "batch_id": batch.id,
            "total_files": len(files),
            "message": "Lot créé avec succès. L'analyse est en cours..."
        }

    except Exception as e:
        print(f"Erreur création batch: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/batch/{batch_id}/status")
async def get_batch_status(
    batch_id: int,
    user: User = Depends(require_admin_user),
    db: Session = Depends(get_db)
):
    """
    Récupère le statut d'un lot de scan
    """
    batch = db.query(MassScanBatch).filter(MassScanBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Lot non trouvé")

    # Récupérer les PAP du batch
    paps = db.query(MassScanPAP).filter(MassScanPAP.batch_id == batch_id).all()

    return {
        "batch_id": batch.id,
        "status": batch.status,
        "total_paps": batch.total_paps,
        "paps_enjeux": batch.paps_enjeux,
        "paps_standard": batch.paps_standard,
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
        "completed_at": batch.completed_at.isoformat() if batch.completed_at else None,
        "paps": [
            {
                "id": pap.id,
                "file_name": pap.file_name,
                "siret": pap.siret,
                "raison_sociale": pap.raison_sociale or pap.denomination,
                "ud": pap.ud,
                "is_enjeux": pap.is_enjeux,
                "raison_enjeux": pap.raison_enjeux,
                "status": pap.status,
                "error": pap.error
            }
            for pap in paps
        ]
    }


@router.get("/batch/{batch_id}/paps")
async def get_batch_paps(
    batch_id: int,
    user: User = Depends(require_admin_user),
    db: Session = Depends(get_db)
):
    """
    Récupère la liste détaillée des PAP d'un lot
    """
    batch = db.query(MassScanBatch).filter(MassScanBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Lot non trouvé")

    paps = db.query(MassScanPAP).filter(MassScanPAP.batch_id == batch_id).all()

    return {
        "batch_id": batch.id,
        "paps": [
            {
                "id": pap.id,
                "file_name": pap.file_name,
                "siret": pap.siret,
                "raison_sociale": pap.raison_sociale or pap.denomination,
                "adresse": pap.adresse,
                "code_postal": pap.code_postal,
                "commune": pap.commune,
                "ud": pap.ud,
                "fd": pap.fd,
                "effectif_total": pap.effectif_total,
                "inscrits": pap.inscrits,
                "is_enjeux": pap.is_enjeux,
                "raison_enjeux": pap.raison_enjeux,
                "email_subject": pap.email_subject,
                "email_body": pap.email_body,
                "email_recipient": pap.email_recipient,
                "status": pap.status,
                "error": pap.error
            }
            for pap in paps
        ]
    }


@router.get("/batch/{batch_id}/pap/{pap_id}/email")
async def get_pap_email(
    batch_id: int,
    pap_id: int,
    user: User = Depends(require_admin_user),
    db: Session = Depends(get_db)
):
    """
    Récupère le template d'email pour un PAP spécifique
    """
    pap = db.query(MassScanPAP).filter(
        MassScanPAP.batch_id == batch_id,
        MassScanPAP.id == pap_id
    ).first()

    if not pap:
        raise HTTPException(status_code=404, detail="PAP non trouvé")

    return {
        "pap_id": pap.id,
        "subject": pap.email_subject,
        "body": pap.email_body,
        "recipient": pap.email_recipient,
        "file_path": pap.file_path
    }


@router.get("/batches")
async def list_batches(
    user: User = Depends(require_admin_user),
    db: Session = Depends(get_db)
):
    """
    Liste tous les lots de scan
    """
    batches = db.query(MassScanBatch).order_by(MassScanBatch.created_at.desc()).limit(50).all()

    return {
        "batches": [
            {
                "id": batch.id,
                "user_email": batch.user_email,
                "total_paps": batch.total_paps,
                "paps_enjeux": batch.paps_enjeux,
                "paps_standard": batch.paps_standard,
                "status": batch.status,
                "created_at": batch.created_at.isoformat() if batch.created_at else None,
                "completed_at": batch.completed_at.isoformat() if batch.completed_at else None
            }
            for batch in batches
        ]
    }
