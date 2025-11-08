"""
Service d'extraction d'informations depuis les courriers PAP via l'API OpenAI.

Ce service utilise GPT-4 Vision pour analyser des images ou PDFs de courriers PAP
et en extraire automatiquement les informations clés (SIRET, dates, adresses, etc.).
"""

import base64
import io
import logging
from typing import Dict, Any, Optional, Union
from datetime import datetime
import json

from openai import OpenAI
from PIL import Image
try:
    from pdf2image import convert_from_bytes
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    logger.warning("pdf2image non installé - support PDF désactivé")

from ..config import OPENAI_API_KEY, OPENAI_MODEL

logger = logging.getLogger(__name__)


class DocumentExtractorError(Exception):
    """Exception levée lors d'erreurs d'extraction de documents."""
    pass


class DocumentExtractor:
    """
    Service pour extraire des informations structurées depuis des courriers PAP
    en utilisant l'API OpenAI GPT-4 Vision.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialise le service d'extraction.

        Args:
            api_key: Clé API OpenAI. Si None, utilise OPENAI_API_KEY de la config.
            model: Modèle OpenAI à utiliser. Si None, utilise OPENAI_MODEL de la config.

        Raises:
            DocumentExtractorError: Si la clé API n'est pas configurée.
        """
        self.api_key = api_key or OPENAI_API_KEY
        if not self.api_key:
            raise DocumentExtractorError(
                "Clé API OpenAI manquante. "
                "Veuillez configurer OPENAI_API_KEY dans le fichier .env"
            )

        self.client = OpenAI(api_key=self.api_key)
        self.default_model = model or OPENAI_MODEL

    def _encode_image(self, image_data: bytes) -> str:
        """
        Encode une image en base64 pour l'envoyer à l'API OpenAI.

        Args:
            image_data: Données brutes de l'image

        Returns:
            Image encodée en base64
        """
        return base64.b64encode(image_data).decode('utf-8')

    def _validate_and_convert_image(self, image_data: bytes) -> bytes:
        """
        Valide et convertit l'image au format optimal pour l'API.

        Args:
            image_data: Données de l'image

        Returns:
            Image convertie et optimisée
        """
        try:
            img = Image.open(io.BytesIO(image_data))

            # Convertir en RGB si nécessaire
            if img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')

            # Redimensionner si trop grande (max 2000x2000 pour optimiser les coûts)
            max_size = 2000
            if max(img.size) > max_size:
                ratio = max_size / max(img.size)
                new_size = tuple(int(dim * ratio) for dim in img.size)
                img = img.resize(new_size, Image.Resampling.LANCZOS)

            # Convertir en bytes
            buffer = io.BytesIO()
            img.save(buffer, format='PNG', optimize=True)
            return buffer.getvalue()

        except Exception as e:
            raise DocumentExtractorError(f"Erreur lors du traitement de l'image: {str(e)}")

    def _convert_pdf_to_image(self, pdf_data: bytes) -> bytes:
        """
        Convertit la première page d'un PDF en image.

        Args:
            pdf_data: Données du PDF

        Returns:
            Image de la première page en bytes

        Raises:
            DocumentExtractorError: Si la conversion échoue ou si pdf2image n'est pas installé
        """
        if not PDF_SUPPORT:
            raise DocumentExtractorError(
                "Support PDF non disponible. Installez pdf2image avec: "
                "pip install pdf2image"
            )

        try:
            # Convertir le PDF en images (première page seulement pour économiser)
            images = convert_from_bytes(pdf_data, first_page=1, last_page=1, dpi=200)

            if not images:
                raise DocumentExtractorError("Le PDF ne contient aucune page")

            # Convertir l'image PIL en bytes
            buffer = io.BytesIO()
            images[0].save(buffer, format='PNG', optimize=True)
            return buffer.getvalue()

        except Exception as e:
            raise DocumentExtractorError(f"Erreur lors de la conversion du PDF: {str(e)}")

    def extract_from_image(
        self,
        image_data: bytes,
        model: Optional[str] = None,
        temperature: float = 0.1
    ) -> Dict[str, Any]:
        """
        Extrait les informations d'un courrier PAP depuis une image.

        Args:
            image_data: Données de l'image du courrier
            model: Modèle OpenAI à utiliser. Si None, utilise le modèle configuré (gpt-4o par défaut)
            temperature: Température du modèle (0.1 pour plus de précision)

        Returns:
            Dictionnaire contenant les informations extraites:
            {
                "siret": "12345678901234",
                "raison_sociale": "Nom de l'entreprise",
                "adresse": "123 Rue Example",
                "code_postal": "75001",
                "ville": "Paris",
                "date_invitation": "2024-01-15",
                "date_election": "2024-02-20",
                "effectif": 150,
                "source": "PAP C5",
                "raw_text": "Texte brut extrait...",
                "confidence": "high|medium|low"
            }

        Raises:
            DocumentExtractorError: Si l'extraction échoue
        """
        try:
            # Utiliser le modèle par défaut si non spécifié
            if model is None:
                model = self.default_model

            # Valider et optimiser l'image
            processed_image = self._validate_and_convert_image(image_data)
            base64_image = self._encode_image(processed_image)

            # Construire le prompt pour l'extraction
            prompt = """
            Analyse ce courrier PAP (Protocole d'Accord Préélectoral) ou cette invitation C5 et extrait TOUTES les informations suivantes au format JSON structuré.

            Retourne UNIQUEMENT un objet JSON valide avec les champs suivants (utilise null si l'information n'est pas disponible) :

            {
                "siret": "Numéro SIRET de l'établissement (14 chiffres)",
                "siren": "Numéro SIREN si mentionné (9 chiffres)",
                "raison_sociale": "Raison sociale / nom de l'entreprise",
                "enseigne": "Enseigne commerciale si différente de la raison sociale",
                "adresse": "Adresse complète de l'établissement",
                "code_postal": "Code postal",
                "ville": "Ville",
                "date_invitation": "Date du courrier/invitation au format YYYY-MM-DD",
                "date_election": "Date prévue de l'élection au format YYYY-MM-DD",
                "date_limite_candidature": "Date limite de dépôt des candidatures au format YYYY-MM-DD",
                "effectif": "Effectif de l'entreprise (nombre entier)",
                "type_scrutin": "Type de scrutin (CSE, DP, CE, CHSCT, etc.)",
                "colleges": "Liste des collèges électoraux",
                "sieges_pourvoir": "Nombre total de sièges à pourvoir",
                "source": "Type de document (PAP C5, Invitation, Courrier, etc.)",
                "idcc": "Code IDCC de la convention collective si mentionné",
                "convention_collective": "Nom de la convention collective",
                "syndicats_invites": "Liste des organisations syndicales invitées",
                "contact_nom": "Nom du contact mentionné",
                "contact_fonction": "Fonction du contact",
                "contact_email": "Email du contact",
                "contact_telephone": "Téléphone du contact",
                "notes": "Autres informations importantes",
                "raw_text": "Texte brut complet extrait du document",
                "confidence": "Niveau de confiance (high/medium/low)"
            }

            IMPORTANT:
            - Retourne UNIQUEMENT le JSON, sans texte avant ou après
            - Utilise null pour les valeurs manquantes
            - Les dates doivent être au format YYYY-MM-DD
            - Le SIRET doit être exact (14 chiffres sans espaces)
            - Sois très précis sur les chiffres (SIRET, effectif, dates)
            """

            # Appeler l'API OpenAI
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                temperature=temperature,
                max_tokens=2000,
                response_format={"type": "json_object"}
            )

            # Parser la réponse
            result = response.choices[0].message.content
            extracted_data = json.loads(result)

            # Ajouter des métadonnées
            extracted_data["_metadata"] = {
                "model": model,
                "extraction_date": datetime.now().isoformat(),
                "tokens_used": response.usage.total_tokens,
                "cost_estimate_usd": self._estimate_cost(response.usage.total_tokens, model)
            }

            logger.info(f"Extraction réussie - SIRET: {extracted_data.get('siret', 'N/A')}")
            return extracted_data

        except json.JSONDecodeError as e:
            logger.error(f"Erreur de parsing JSON: {str(e)}")
            raise DocumentExtractorError(f"La réponse de l'API n'est pas un JSON valide: {str(e)}")

        except Exception as e:
            logger.error(f"Erreur lors de l'extraction: {str(e)}")
            raise DocumentExtractorError(f"Échec de l'extraction: {str(e)}")

    def extract_from_document(
        self,
        document_data: bytes,
        is_pdf: bool = False,
        model: Optional[str] = None,
        temperature: float = 0.1
    ) -> Dict[str, Any]:
        """
        Extrait les informations d'un courrier PAP depuis un document (image ou PDF).

        Cette méthode détecte automatiquement le type de document et applique
        le traitement approprié.

        Args:
            document_data: Données du document (image ou PDF)
            is_pdf: True si le document est un PDF, False sinon
            model: Modèle OpenAI à utiliser. Si None, utilise le modèle configuré
            temperature: Température du modèle (0.1 pour plus de précision)

        Returns:
            Dictionnaire contenant les informations extraites

        Raises:
            DocumentExtractorError: Si l'extraction échoue
        """
        try:
            # Si c'est un PDF, le convertir en image
            if is_pdf:
                logger.info("Conversion du PDF en image...")
                image_data = self._convert_pdf_to_image(document_data)
            else:
                image_data = document_data

            # Extraire les informations de l'image
            return self.extract_from_image(image_data, model=model, temperature=temperature)

        except DocumentExtractorError:
            raise
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction du document: {str(e)}")
            raise DocumentExtractorError(f"Échec de l'extraction: {str(e)}")

    def _estimate_cost(self, tokens: int, model: str) -> float:
        """
        Estime le coût de l'appel API.

        Args:
            tokens: Nombre de tokens utilisés
            model: Modèle utilisé

        Returns:
            Coût estimé en USD
        """
        # Tarifs approximatifs (à jour au 2024)
        rates = {
            "gpt-4o-mini": 0.00015 / 1000,  # $0.00015 per 1K tokens (très économique)
            "gpt-4o": 0.005 / 1000,  # $0.005 per 1K tokens (input + output moyenné)
            "gpt-4-turbo": 0.01 / 1000,
            "gpt-4": 0.03 / 1000,
        }

        rate = rates.get(model, 0.001 / 1000)
        return tokens * rate

    def extract_batch(
        self,
        images: list[bytes],
        model: Optional[str] = None
    ) -> list[Dict[str, Any]]:
        """
        Extrait les informations de plusieurs courriers en parallèle.

        Args:
            images: Liste de données d'images
            model: Modèle OpenAI à utiliser. Si None, utilise le modèle configuré

        Returns:
            Liste de dictionnaires avec les informations extraites
        """
        results = []
        total_cost = 0.0

        # Utiliser le modèle par défaut si non spécifié
        if model is None:
            model = self.default_model

        for i, image_data in enumerate(images, 1):
            logger.info(f"Traitement du document {i}/{len(images)}")
            try:
                result = self.extract_from_image(image_data, model=model)
                results.append(result)
                total_cost += result.get("_metadata", {}).get("cost_estimate_usd", 0)
            except DocumentExtractorError as e:
                logger.error(f"Échec du document {i}: {str(e)}")
                results.append({
                    "error": str(e),
                    "document_index": i
                })

        logger.info(f"Batch terminé - {len(results)} documents - Coût total estimé: ${total_cost:.4f}")
        return results


def extract_from_pap_document(image_data: bytes) -> Dict[str, Any]:
    """
    Fonction utilitaire pour extraire rapidement des informations d'un document PAP.

    Args:
        image_data: Données de l'image du courrier

    Returns:
        Dictionnaire avec les informations extraites

    Raises:
        DocumentExtractorError: Si l'extraction échoue
    """
    extractor = DocumentExtractor()
    return extractor.extract_from_image(image_data)
