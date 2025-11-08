"""
Module de validation des inputs pour l'application.
"""
import re
from datetime import date, datetime
from typing import Optional
from fastapi import HTTPException, UploadFile


class ValidationError(Exception):
    """Exception levée lors d'une erreur de validation"""
    pass


def validate_siret(siret: str, raise_exception: bool = True) -> Optional[str]:
    """
    Valide et normalise un numéro SIRET.

    Args:
        siret: Le numéro SIRET à valider
        raise_exception: Si True, lève une exception en cas d'erreur.
                        Si False, retourne None en cas d'erreur.

    Returns:
        Le SIRET normalisé (14 chiffres) ou None si invalide et raise_exception=False

    Raises:
        ValidationError: Si le SIRET est invalide et raise_exception=True
    """
    if not siret:
        if raise_exception:
            raise ValidationError("SIRET manquant")
        return None

    # Nettoyer le SIRET (supprimer espaces, tirets, etc.)
    cleaned = re.sub(r"[^0-9]", "", str(siret).strip())

    # Vérifier la longueur
    if len(cleaned) != 14:
        if raise_exception:
            raise ValidationError(f"SIRET invalide: doit contenir exactement 14 chiffres (reçu: {len(cleaned)} chiffres)")
        return None

    # Vérifier que ce sont bien tous des chiffres
    if not cleaned.isdigit():
        if raise_exception:
            raise ValidationError("SIRET invalide: doit contenir uniquement des chiffres")
        return None

    # Validation Luhn (algorithme de checksum pour SIRET)
    # Note: Cette validation est optionnelle car tous les SIRET ne passent pas le test Luhn
    # en raison de modifications historiques du format
    # Pour l'instant, on se contente de vérifier le format

    return cleaned


def validate_siren(siren: str, raise_exception: bool = True) -> Optional[str]:
    """
    Valide et normalise un numéro SIREN.

    Args:
        siren: Le numéro SIREN à valider
        raise_exception: Si True, lève une exception en cas d'erreur

    Returns:
        Le SIREN normalisé (9 chiffres) ou None si invalide et raise_exception=False

    Raises:
        ValidationError: Si le SIREN est invalide et raise_exception=True
    """
    if not siren:
        if raise_exception:
            raise ValidationError("SIREN manquant")
        return None

    # Nettoyer le SIREN
    cleaned = re.sub(r"[^0-9]", "", str(siren).strip())

    # Vérifier la longueur
    if len(cleaned) != 9:
        if raise_exception:
            raise ValidationError(f"SIREN invalide: doit contenir exactement 9 chiffres (reçu: {len(cleaned)} chiffres)")
        return None

    # Vérifier que ce sont bien tous des chiffres
    if not cleaned.isdigit():
        if raise_exception:
            raise ValidationError("SIREN invalide: doit contenir uniquement des chiffres")
        return None

    return cleaned


def validate_date(date_str: str, raise_exception: bool = True) -> Optional[date]:
    """
    Valide et parse une date.

    Args:
        date_str: La date sous forme de string (formats supportés: YYYY-MM-DD, DD/MM/YYYY)
        raise_exception: Si True, lève une exception en cas d'erreur

    Returns:
        L'objet date ou None si invalide et raise_exception=False

    Raises:
        ValidationError: Si la date est invalide et raise_exception=True
    """
    if not date_str:
        if raise_exception:
            raise ValidationError("Date manquante")
        return None

    # Essayer plusieurs formats
    formats = [
        "%Y-%m-%d",      # ISO format
        "%d/%m/%Y",      # Format français
        "%Y/%m/%d",
        "%d-%m-%Y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except (ValueError, TypeError):
            continue

    # Aucun format n'a fonctionné
    if raise_exception:
        raise ValidationError(f"Format de date invalide: '{date_str}'. Formats acceptés: YYYY-MM-DD, DD/MM/YYYY")
    return None


def validate_excel_file(file: UploadFile, max_size_mb: int = 50) -> None:
    """
    Valide un fichier Excel uploadé.

    Args:
        file: Le fichier uploadé
        max_size_mb: Taille maximale en MB

    Raises:
        HTTPException: Si le fichier est invalide
    """
    # Vérifier que le fichier existe
    if not file:
        raise HTTPException(status_code=400, detail="Aucun fichier fourni")

    # Vérifier le type MIME
    allowed_mime_types = [
        "application/vnd.ms-excel",  # .xls
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # .xlsx
        "application/octet-stream",  # Fallback générique
    ]

    if file.content_type not in allowed_mime_types:
        # Vérifier aussi l'extension du nom de fichier
        if not (file.filename.endswith(".xls") or file.filename.endswith(".xlsx")):
            raise HTTPException(
                status_code=400,
                detail=f"Type de fichier invalide: {file.content_type}. Seuls les fichiers Excel (.xls, .xlsx) sont acceptés."
            )

    # Vérifier la taille (si disponible)
    # Note: UploadFile ne fournit pas toujours la taille avant lecture
    # Cette vérification sera faite lors de la lecture du fichier si nécessaire

    # Vérifier l'extension
    if not file.filename:
        raise HTTPException(status_code=400, detail="Nom de fichier manquant")

    filename_lower = file.filename.lower()
    if not (filename_lower.endswith(".xls") or filename_lower.endswith(".xlsx")):
        raise HTTPException(
            status_code=400,
            detail=f"Extension de fichier invalide: {file.filename}. Seuls .xls et .xlsx sont acceptés."
        )


def validate_idcc(idcc: str, raise_exception: bool = True) -> Optional[str]:
    """
    Valide un code IDCC (Identifiant de Convention Collective).

    Args:
        idcc: Le code IDCC à valider
        raise_exception: Si True, lève une exception en cas d'erreur

    Returns:
        L'IDCC nettoyé ou None si invalide et raise_exception=False

    Raises:
        ValidationError: Si l'IDCC est invalide et raise_exception=True
    """
    if not idcc:
        if raise_exception:
            raise ValidationError("IDCC manquant")
        return None

    # Nettoyer l'IDCC (supprimer espaces)
    cleaned = str(idcc).strip()

    # Un IDCC est généralement composé de 4 chiffres
    # Mais on accepte aussi des formats avec lettres (ex: "0016")
    if not re.match(r"^[0-9]{1,5}$", cleaned):
        if raise_exception:
            raise ValidationError(f"IDCC invalide: doit être un nombre de 1 à 5 chiffres (reçu: {cleaned})")
        return None

    return cleaned
