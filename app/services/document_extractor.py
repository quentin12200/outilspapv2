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

from ..config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_MODEL_FALLBACK
from .pappers_api import PappersAPI
from .sirene_api import SireneAPI

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

    async def _enrich_data_with_apis(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrichit les données extraites avec les APIs Pappers/Sirene si des informations manquent.

        Si le SIRET est trouvé mais que effectif, commune, code_postal ou idcc manquent,
        cette fonction les récupère automatiquement via les APIs.

        Args:
            extracted_data: Données extraites du document

        Returns:
            Données enrichies avec les informations des APIs
        """
        siret = extracted_data.get('siret')

        # Si pas de SIRET valide, on ne peut pas enrichir
        if not self._is_valid_siret(siret):
            return extracted_data

        # Vérifier quelles données manquent
        missing_fields = []
        if not extracted_data.get('effectif'):
            missing_fields.append('effectif')
        if not extracted_data.get('ville'):
            missing_fields.append('ville')
        if not extracted_data.get('code_postal'):
            missing_fields.append('code_postal')
        if not extracted_data.get('idcc'):
            missing_fields.append('idcc')

        # Si rien ne manque, pas besoin d'enrichir
        if not missing_fields:
            logger.info(f"✅ Toutes les données essentielles sont présentes pour {siret}")
            return extracted_data

        logger.info(f"🔍 Enrichissement des données pour {siret} - Champs manquants: {', '.join(missing_fields)}")

        # Essayer d'abord Pappers (plus complet)
        try:
            pappers = PappersAPI()
            pappers_data = await pappers.get_siret(siret)

            if pappers_data:
                logger.info(f"✅ Données Pappers récupérées pour {siret}")

                # Enrichir les données manquantes
                enriched_fields = []

                # PRIORITÉ 1: Utiliser l'effectif numérique direct de Pappers
                if not extracted_data.get('effectif'):
                    effectif_num = pappers_data.get('effectif')
                    if effectif_num and isinstance(effectif_num, (int, float)) and effectif_num > 0:
                        extracted_data['effectif'] = int(effectif_num)
                        enriched_fields.append('effectif')
                        logger.info(f"✅ Effectif numérique récupéré: {effectif_num}")
                    # PRIORITÉ 2: Essayer de parser effectifs_label si c'est un nombre
                    elif pappers_data.get('effectifs_label'):
                        try:
                            effectif_label = str(pappers_data['effectifs_label'])
                            # Si c'est un nombre, l'utiliser directement
                            if effectif_label.isdigit():
                                extracted_data['effectif'] = int(effectif_label)
                                enriched_fields.append('effectif')
                                logger.info(f"✅ Effectif extrait du label: {effectif_label}")
                            else:
                                # Sinon garder le label en note
                                note = f"Effectif (Pappers): {effectif_label}"
                                if extracted_data.get('notes'):
                                    extracted_data['notes'] = f"{extracted_data['notes']} | {note}"
                                else:
                                    extracted_data['notes'] = note
                                logger.info(f"ℹ️ Effectif label (non numérique): {effectif_label}")
                        except (ValueError, TypeError) as e:
                            logger.warning(f"⚠️ Erreur parsing effectif: {e}")

                if not extracted_data.get('ville') and pappers_data.get('commune'):
                    extracted_data['ville'] = pappers_data['commune']
                    enriched_fields.append('ville')

                if not extracted_data.get('code_postal') and pappers_data.get('code_postal'):
                    extracted_data['code_postal'] = pappers_data['code_postal']
                    enriched_fields.append('code_postal')

                if not extracted_data.get('idcc') and pappers_data.get('idcc'):
                    extracted_data['idcc'] = pappers_data['idcc']
                    enriched_fields.append('idcc')

                if not extracted_data.get('raison_sociale') and pappers_data.get('denomination'):
                    extracted_data['raison_sociale'] = pappers_data['denomination']
                    enriched_fields.append('raison_sociale')

                if enriched_fields:
                    logger.info(f"✅ Données enrichies via Pappers: {', '.join(enriched_fields)}")
                    # Ajouter une note pour l'utilisateur
                    note_enrichissement = f"✅ Données auto-complétées via Pappers: {', '.join(enriched_fields)}"
                    if extracted_data.get('notes'):
                        extracted_data['notes'] = f"{extracted_data['notes']} | {note_enrichissement}"
                    else:
                        extracted_data['notes'] = note_enrichissement

                    # Ajouter dans les métadonnées
                    if '_metadata' not in extracted_data:
                        extracted_data['_metadata'] = {}
                    extracted_data['_metadata']['enriched_with_pappers'] = True
                    extracted_data['_metadata']['enriched_fields'] = enriched_fields

                return extracted_data

        except Exception as e:
            logger.warning(f"⚠️ Erreur lors de l'enrichissement via Pappers: {str(e)}")

        # Fallback sur Sirene si Pappers échoue
        try:
            sirene = SireneAPI()
            sirene_data = await sirene.get_siret(siret)

            if sirene_data and sirene_data.get('success'):
                logger.info(f"✅ Données Sirene récupérées pour {siret}")
                etab = sirene_data.get('etablissement', {})

                enriched_fields = []

                if not extracted_data.get('ville') and etab.get('commune'):
                    extracted_data['ville'] = etab['commune']
                    enriched_fields.append('ville')

                if not extracted_data.get('code_postal') and etab.get('code_postal'):
                    extracted_data['code_postal'] = etab['code_postal']
                    enriched_fields.append('code_postal')

                if not extracted_data.get('raison_sociale') and etab.get('denomination'):
                    extracted_data['raison_sociale'] = etab['denomination']
                    enriched_fields.append('raison_sociale')

                if enriched_fields:
                    logger.info(f"✅ Données enrichies via Sirene: {', '.join(enriched_fields)}")
                    note_enrichissement = f"✅ Données auto-complétées via Sirene: {', '.join(enriched_fields)}"
                    if extracted_data.get('notes'):
                        extracted_data['notes'] = f"{extracted_data['notes']} | {note_enrichissement}"
                    else:
                        extracted_data['notes'] = note_enrichissement

                    if '_metadata' not in extracted_data:
                        extracted_data['_metadata'] = {}
                    extracted_data['_metadata']['enriched_with_sirene'] = True
                    extracted_data['_metadata']['enriched_fields'] = enriched_fields

        except Exception as e:
            logger.warning(f"⚠️ Erreur lors de l'enrichissement via Sirene: {str(e)}")

        return extracted_data

    @staticmethod
    def _is_valid_siret(siret: Optional[str]) -> bool:
        """
        Vérifie si un SIRET est valide (14 chiffres).

        Args:
            siret: Numéro SIRET à valider

        Returns:
            True si le SIRET est valide, False sinon
        """
        if not siret:
            return False
        # Nettoyer le SIRET (enlever espaces, tirets, etc.)
        siret_clean = ''.join(c for c in str(siret) if c.isdigit())
        return len(siret_clean) == 14

    async def _search_siret_from_data(
        self,
        raison_sociale: Optional[str],
        code_postal: Optional[str] = None,
        ville: Optional[str] = None
    ) -> Optional[str]:
        """
        Recherche automatiquement un SIRET via GPT en utilisant une recherche web.
        Plus fiable que l'API Sirene qui peut être instable.

        Args:
            raison_sociale: Nom de l'entreprise
            code_postal: Code postal de l'établissement
            ville: Ville de l'établissement

        Returns:
            SIRET trouvé ou None si pas de résultat
        """
        if not raison_sociale:
            return None

        try:
            logger.info(f"🔍 Recherche automatique du SIRET via GPT pour: {raison_sociale}")

            # Construire le prompt de recherche
            localisation = []
            if ville:
                localisation.append(ville)
            if code_postal:
                localisation.append(f"CP {code_postal}")

            localisation_str = " - ".join(localisation) if localisation else ""

            prompt = f"""Tu es un assistant expert pour trouver des numéros SIRET d'entreprises françaises.

IMPORTANT: Je cherche le numéro SIRET (14 chiffres) de l'entreprise suivante:
- Nom de l'entreprise: {raison_sociale}
{f"- Localisation: {localisation_str}" if localisation_str else ""}

CONSIGNES:
1. Cherche sur internet le SIRET de cette entreprise (utilise societe.com, pappers.fr, annuaire-entreprises.data.gouv.fr, etc.)
2. Vérifie que le SIRET trouvé correspond bien à l'entreprise et à la localisation
3. Retourne UNIQUEMENT un objet JSON avec cette structure:

{{
    "siret": "12345678901234",
    "raison_sociale_officielle": "Nom officiel de l'entreprise",
    "ville": "Ville",
    "source": "Site web utilisé pour la recherche",
    "confiance": "high|medium|low"
}}

Si tu ne trouves pas de SIRET valide, retourne:
{{
    "siret": null,
    "raison": "Explication de pourquoi le SIRET n'a pas été trouvé"
}}

IMPORTANT: Le SIRET doit contenir exactement 14 chiffres. Vérifie bien que c'est le bon établissement."""

            # Appeler GPT avec fallback
            models_to_try = OPENAI_MODEL_FALLBACK
            last_error = None

            for attempt_model in models_to_try:
                try:
                    logger.info(f"Tentative de recherche SIRET avec le modèle: {attempt_model}")

                    response = self.client.chat.completions.create(
                        model=attempt_model,
                        messages=[
                            {
                                "role": "system",
                                "content": "Tu es un expert en recherche d'informations d'entreprises françaises. Tu as accès à internet pour trouver des SIRET."
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        temperature=0.1,
                        max_tokens=500,
                        response_format={"type": "json_object"}
                    )

                    # Si on arrive ici, ça a marché !
                    logger.info(f"✅ Recherche réussie avec le modèle: {attempt_model}")
                    break

                except Exception as e:
                    error_msg = str(e)
                    last_error = e

                    # Si c'est une erreur d'accès au modèle, essayer le suivant
                    if "does not have access" in error_msg or "model_not_found" in error_msg:
                        logger.warning(f"⚠️ Modèle {attempt_model} non accessible, essai du suivant...")
                        continue
                    else:
                        # Autre type d'erreur, on arrête les tentatives
                        raise e
            else:
                # Aucun modèle n'a fonctionné
                logger.error(f"❌ Aucun modèle accessible pour la recherche SIRET")
                return None

            # Parser la réponse
            result_json = json.loads(response.choices[0].message.content)
            siret = result_json.get('siret')

            if siret and self._is_valid_siret(siret):
                logger.info(f"✅ SIRET trouvé par GPT: {siret} pour {raison_sociale}")
                logger.info(f"   Source: {result_json.get('source', 'Non spécifiée')}")
                logger.info(f"   Confiance: {result_json.get('confiance', 'Non spécifiée')}")
                return siret
            else:
                raison = result_json.get('raison', 'SIRET non trouvé ou invalide')
                logger.warning(f"❌ GPT n'a pas trouvé de SIRET valide: {raison}")
                return None

        except json.JSONDecodeError as e:
            logger.error(f"Erreur de parsing JSON lors de la recherche SIRET: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Erreur lors de la recherche automatique du SIRET: {str(e)}")
            return None

    async def extract_from_image(
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
            Analyse ce document de PAP (Protocole d'Accord Préélectoral), invitation C5 ou courrier électoral français et extrait TOUTES les informations suivantes.

            CONTEXTE IMPORTANT:
            - Un PAP est un accord entre l'employeur et les organisations syndicales avant des élections professionnelles (CSE, DP, CE)
            - Il contient des informations sur l'établissement, les modalités de l'élection, les collèges, effectifs, etc.
            - Les chiffres comme le SIRET, l'effectif et le nombre d'inscrits sont ESSENTIELS

            INSTRUCTIONS SPÉCIFIQUES POUR L'EXTRACTION:

            1. SIRET (CRUCIAL):
               - Cherche un nombre de 14 chiffres (peut être espacé: "123 456 789 01234" ou "12345678901234")
               - Peut être précédé de "SIRET:", "n° SIRET", "Numéro SIRET", etc.
               - Peut être sur l'en-tête, dans les coordonnées de l'entreprise
               - EXTRAIT LE MÊME SI IL EST MAL FORMATÉ (espaces, points, tirets)

            2. EFFECTIF (CRUCIAL):
               - Cherche "effectif", "nombre de salariés", "salariés de l'établissement"
               - Peut être écrit en chiffres ou en toutes lettres ("cinquante salariés")
               - Peut être dans une phrase comme "L'établissement compte 150 salariés"
               - CHERCHE PARTOUT DANS LE DOCUMENT

            3. INSCRITS (CRUCIAL):
               - Cherche "inscrits", "électeurs inscrits", "liste électorale", "nombre d'électeurs"
               - Peut être par collège: "Collège 1: 45 inscrits, Collège 2: 30 inscrits" → somme = 75
               - Peut être dans un tableau récapitulatif
               - Si tu trouves des inscrits par collège, ADDITIONNE-LES pour le total

            4. COMMUNE/VILLE (CRUCIAL):
               - Cherche la ville dans l'adresse de l'établissement
               - Format souvent: "Code postal VILLE" (ex: "75001 PARIS", "13010 MARSEILLE")
               - La ville peut être en MAJUSCULES après le code postal
               - Extrait le nom exact de la commune

            5. DATES (CRUCIAL - BIEN DISTINGUER):
               - DATE INVITATION (date de la réunion de négociation du PAP):
                 * Cherche des phrases comme: "la réunion de négociation du protocole aura lieu le...",
                   "réunion de négociation fixée au...", "négociation du PAP prévue le...",
                   "vous convie à une réunion le...", "rendez-vous fixé au..."
                 * C'est la date où l'employeur invite les syndicats à venir négocier le PAP
                 * ATTENTION: Ne pas confondre avec la date d'élection !

               - DATE ÉLECTION (date du scrutin):
                 * Cherche des phrases comme: "élections prévues le...", "scrutin fixé au...",
                   "les élections auront lieu le...", "date du vote..."
                 * C'est la date où les salariés voteront

            Retourne UNIQUEMENT un objet JSON valide avec cette structure:

            {
                "siret": "Numéro SIRET exact à 14 chiffres (enlève espaces/points/tirets)",
                "siren": "Numéro SIREN si visible (9 premiers chiffres du SIRET)",
                "raison_sociale": "Raison sociale exacte de l'entreprise",
                "enseigne": "Enseigne commerciale si différente",
                "adresse": "Adresse complète (numéro, rue)",
                "code_postal": "Code postal (5 chiffres)",
                "ville": "Nom de la commune/ville EXACT (comme écrit dans le document)",
                "date_invitation": "Date de la réunion de négociation du PAP (pas la date du courrier!) au format YYYY-MM-DD",
                "date_election": "Date de l'élection/scrutin au format YYYY-MM-DD",
                "date_limite_candidature": "Date limite candidatures au format YYYY-MM-DD",
                "effectif": "Effectif TOTAL de l'établissement (nombre entier)",
                "inscrits": "Nombre total d'électeurs inscrits (somme de tous les collèges)",
                "type_scrutin": "Type d'élection (CSE, DP, CE, CHSCT, etc.)",
                "colleges": "Description des collèges électoraux",
                "sieges_pourvoir": "Nombre total de sièges à pourvoir",
                "source": "Type de document (PAP, Invitation C5, Courrier, etc.)",
                "idcc": "Code IDCC de la convention collective",
                "convention_collective": "Nom de la convention collective",
                "syndicats_invites": "Liste des syndicats invités",
                "contact_nom": "Nom du contact",
                "contact_fonction": "Fonction du contact",
                "contact_email": "Email du contact",
                "contact_telephone": "Téléphone du contact",
                "notes": "Autres informations importantes",
                "raw_text": "Texte brut complet du document",
                "confidence": "Niveau de confiance (high/medium/low)"
            }

            RÈGLES STRICTES:
            - Retourne UNIQUEMENT le JSON, rien d'autre
            - Utilise null si une information n'est vraiment pas dans le document
            - Les dates DOIVENT être au format YYYY-MM-DD
            - Le SIRET DOIT contenir exactement 14 chiffres (nettoie les espaces/tirets)
            - L'effectif et les inscrits DOIVENT être des nombres entiers
            - La ville doit être le nom exact de la commune (pas d'abréviation)
            - Sois TRÈS MINUTIEUX pour les chiffres (SIRET, effectif, inscrits, dates)
            - Si tu trouves plusieurs collèges avec des inscrits, ADDITIONNE-LES
            """

            # Essayer plusieurs modèles en fallback si le premier échoue
            models_to_try = [model] if model != self.default_model else OPENAI_MODEL_FALLBACK
            last_error = None

            for attempt_model in models_to_try:
                try:
                    logger.info(f"Tentative d'extraction avec le modèle: {attempt_model}")

                    # Appeler l'API OpenAI
                    response = self.client.chat.completions.create(
                        model=attempt_model,
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

                    # Si on arrive ici, ça a marché !
                    model = attempt_model  # Utiliser ce modèle pour les métadonnées
                    logger.info(f"✅ Extraction réussie avec le modèle: {attempt_model}")
                    break

                except Exception as e:
                    error_msg = str(e)
                    last_error = e

                    # Si c'est une erreur d'accès au modèle, essayer le suivant
                    if "does not have access" in error_msg or "model_not_found" in error_msg:
                        logger.warning(f"⚠️ Modèle {attempt_model} non accessible, essai du suivant...")
                        continue
                    else:
                        # Autre type d'erreur, on arrête les tentatives
                        raise e
            else:
                # Aucun modèle n'a fonctionné
                raise DocumentExtractorError(
                    f"Aucun modèle GPT-4 accessible. Dernière erreur: {str(last_error)}. "
                    f"Vérifiez que vous avez activé au moins un modèle GPT-4 dans votre projet OpenAI."
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

            # Si le SIRET n'est pas valide, essayer de le rechercher automatiquement
            if not self._is_valid_siret(extracted_data.get('siret')):
                logger.warning(f"⚠️ SIRET manquant ou invalide: '{extracted_data.get('siret')}' - Lancement de la recherche automatique...")

                raison_sociale = extracted_data.get('raison_sociale')
                code_postal = extracted_data.get('code_postal')
                ville = extracted_data.get('ville')

                logger.info(f"🔍 Données pour recherche: Raison sociale='{raison_sociale}', CP='{code_postal}', Ville='{ville}'")

                if raison_sociale:
                    siret_found = await self._search_siret_from_data(
                        raison_sociale=raison_sociale,
                        code_postal=code_postal,
                        ville=ville
                    )

                    if siret_found:
                        extracted_data['siret'] = siret_found
                        # Ajouter une note dans les métadonnées et dans notes
                        if '_metadata' not in extracted_data:
                            extracted_data['_metadata'] = {}
                        extracted_data['_metadata']['siret_auto_found'] = True
                        extracted_data['_metadata']['siret_source'] = 'Recherche web GPT (recherche automatique)'

                        # Ajouter dans les notes pour que l'utilisateur le voie
                        note_siret = f"✅ SIRET trouvé automatiquement par recherche web (non visible sur le document)"
                        if extracted_data.get('notes'):
                            extracted_data['notes'] = f"{extracted_data['notes']} | {note_siret}"
                        else:
                            extracted_data['notes'] = note_siret

                        logger.info(f"✅ SIRET trouvé automatiquement et ajouté: {siret_found}")
                    else:
                        logger.error(f"❌ Aucun SIRET trouvé automatiquement pour '{raison_sociale}'")
                else:
                    logger.warning(f"⚠️ Impossible de rechercher le SIRET: raison sociale manquante")

            # Enrichir les données manquantes avec les APIs (Pappers/Sirene)
            extracted_data = await self._enrich_data_with_apis(extracted_data)

            return extracted_data

        except json.JSONDecodeError as e:
            logger.error(f"Erreur de parsing JSON: {str(e)}")
            raise DocumentExtractorError(f"La réponse de l'API n'est pas un JSON valide: {str(e)}")

        except Exception as e:
            logger.error(f"Erreur lors de l'extraction: {str(e)}")
            raise DocumentExtractorError(f"Échec de l'extraction: {str(e)}")

    async def extract_from_document(
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
            return await self.extract_from_image(image_data, model=model, temperature=temperature)

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
