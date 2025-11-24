"""
Service d'extraction de données PAP depuis fichiers Excel, images ou PDF

Ce service combine :
- Extraction standard via ETL pour fichiers Excel
- Extraction IA via GPT-4 Vision pour images/PDF
"""

import logging
import pandas as pd
from typing import Dict, Any, Optional
from pathlib import Path

from ..etl import (
    _normalize_cols,
    _col_detect,
    _to14,
    _todate,
    _to_int,
    _norm_cycle,
    _sum_int
)

logger = logging.getLogger(__name__)


class PAPExtractionError(Exception):
    """Exception levée lors d'erreurs d'extraction de PAP."""
    pass


def extract_pap_from_excel(file_path: str) -> Dict[str, Any]:
    """
    Extrait les données d'un fichier PAP Excel en utilisant l'ETL standard.

    Args:
        file_path: Chemin vers le fichier Excel

    Returns:
        Dict contenant les données extraites :
        {
            'siret': str,
            'raison_sociale': str,
            'cycle': str,
            'date_pv': date,
            'inscrits': int,
            'votants': int,
            'cgt_voix': int,
            'idcc': str,
            'fd': str,
            'ud': str,
            'cp': str,
            'ville': str,
            'effectif': int,
            ...
        }

    Raises:
        PAPExtractionError: Si l'extraction échoue
    """
    try:
        logger.info(f"Extraction Excel PAP: {file_path}")

        # Lire le fichier Excel
        xls = pd.ExcelFile(file_path)
        sheet = xls.sheet_names[0]
        df = pd.read_excel(xls, sheet_name=sheet, dtype=str)
        df = _normalize_cols(df)

        # Détection des colonnes importantes
        c_siret   = _col_detect(df, ["siret"])
        c_cycle   = _col_detect(df, ["cycle"])
        c_datepv  = "date" if "date" in df.columns else _col_detect(df, ["date pv","date pap","date_pv","date du pv","date du pap"])
        c_ins     = _col_detect(df, ["inscrit","inscrits"])
        c_vot     = _col_detect(df, ["votant","votants"])
        c_cgt     = [c for c in df.columns if "cgt" in c] or []
        c_idcc    = _col_detect(df, ["idcc"])
        c_fd      = _col_detect(df, ["fd","fédération","federation"])
        c_ud      = _col_detect(df, ["ud","union départementale","union departementale"])
        c_rs      = _col_detect(df, ["raison sociale","raison","dénomination","denomination","entreprise"])
        c_cp      = _col_detect(df, ["cp","code postal"])
        c_ville   = _col_detect(df, ["ville","commune"])

        # Essayer d'extraire la première ligne (généralement, les PAP ont 1 ligne)
        if len(df) == 0:
            raise PAPExtractionError("Fichier vide")

        # Prendre la première ligne avec un SIRET valide
        pap_data = None
        for idx, row in df.iterrows():
            r = row.to_dict()
            siret = _to14(r.get(c_siret))
            if siret:
                pap_data = {
                    'siret': siret,
                    'raison_sociale': str(r.get(c_rs)) if c_rs and r.get(c_rs) else None,
                    'cycle': _norm_cycle(r.get(c_cycle)) if c_cycle else None,
                    'date_pv': _todate(r.get(c_datepv)) if c_datepv else None,
                    'inscrits': _to_int(r.get(c_ins)) if c_ins else None,
                    'votants': _to_int(r.get(c_vot)) if c_vot else None,
                    'cgt_voix': _sum_int([r.get(c) for c in c_cgt]) if c_cgt else None,
                    'idcc': str(r.get(c_idcc)) if c_idcc and r.get(c_idcc) else None,
                    'fd': str(r.get(c_fd)) if c_fd and r.get(c_fd) else None,
                    'ud': str(r.get(c_ud)) if c_ud and r.get(c_ud) else None,
                    'cp': str(r.get(c_cp)) if c_cp and r.get(c_cp) else None,
                    'ville': str(r.get(c_ville)) if c_ville and r.get(c_ville) else None,
                    'effectif': _to_int(r.get(c_ins)) if c_ins else None,  # Utiliser inscrits comme proxy
                }
                break

        if not pap_data:
            raise PAPExtractionError("Aucun SIRET valide trouvé dans le fichier")

        logger.info(f"✅ Extraction Excel réussie: SIRET={pap_data['siret']}")
        return pap_data

    except Exception as e:
        logger.error(f"❌ Erreur extraction Excel: {e}")
        raise PAPExtractionError(f"Erreur extraction Excel: {e}")


async def extract_pap_from_image_or_pdf(file_path: str) -> Dict[str, Any]:
    """
    Extrait les données d'un fichier PAP image ou PDF en utilisant l'IA.

    Args:
        file_path: Chemin vers le fichier image/PDF

    Returns:
        Dict contenant les données extraites

    Raises:
        PAPExtractionError: Si l'extraction échoue
    """
    try:
        from ..services.document_extractor import DocumentExtractor

        logger.info(f"Extraction IA PAP: {file_path}")

        # Déterminer si c'est un PDF
        file_ext = Path(file_path).suffix.lower()
        is_pdf = file_ext == '.pdf'

        # Lire le fichier
        with open(file_path, 'rb') as f:
            file_data = f.read()

        # Extraire via IA
        extractor = DocumentExtractor()
        data = await extractor.extract_from_document(file_data, is_pdf=is_pdf)

        if not data:
            raise PAPExtractionError("Aucune donnée extraite du document")

        # Normaliser les données au format attendu
        pap_data = {
            'siret': data.get('siret') or data.get('siren'),
            'raison_sociale': data.get('raison_sociale') or data.get('denomination'),
            'cycle': None,  # Pas toujours disponible dans les courriers
            'date_pv': data.get('date_election'),
            'inscrits': data.get('effectif'),
            'votants': None,
            'cgt_voix': None,
            'idcc': data.get('idcc'),
            'fd': None,
            'ud': None,
            'cp': data.get('code_postal'),
            'ville': data.get('commune'),
            'effectif': data.get('effectif'),
            'adresse': data.get('adresse'),
        }

        if not pap_data['siret']:
            raise PAPExtractionError("SIRET non trouvé dans le document")

        logger.info(f"✅ Extraction IA réussie: SIRET={pap_data['siret']}")
        return pap_data

    except ImportError:
        raise PAPExtractionError("DocumentExtractor non disponible")
    except Exception as e:
        logger.error(f"❌ Erreur extraction IA: {e}")
        raise PAPExtractionError(f"Erreur extraction IA: {e}")


async def extract_pap_auto(file_path: str) -> Dict[str, Any]:
    """
    Extrait automatiquement les données d'un fichier PAP.

    Détecte le type de fichier et utilise la méthode appropriée :
    - Excel: ETL standard
    - Image/PDF: IA (GPT-4 Vision)

    Args:
        file_path: Chemin vers le fichier

    Returns:
        Dict contenant les données extraites

    Raises:
        PAPExtractionError: Si l'extraction échoue
    """
    try:
        file_ext = Path(file_path).suffix.lower()

        # Fichiers Excel
        if file_ext in ['.xlsx', '.xls', '.xlsm']:
            try:
                return extract_pap_from_excel(file_path)
            except PAPExtractionError as e:
                logger.warning(f"⚠️ Extraction Excel échouée, tentative avec IA...")
                # Fallback sur IA si Excel échoue
                return await extract_pap_from_image_or_pdf(file_path)

        # Fichiers image/PDF
        elif file_ext in ['.jpg', '.jpeg', '.png', '.pdf']:
            return await extract_pap_from_image_or_pdf(file_path)

        else:
            raise PAPExtractionError(f"Type de fichier non supporté: {file_ext}")

    except Exception as e:
        logger.error(f"❌ Erreur extraction auto: {e}")
        raise PAPExtractionError(f"Erreur extraction: {e}")
