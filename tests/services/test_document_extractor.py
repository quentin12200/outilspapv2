"""
Tests unitaires pour app/services/document_extractor.py

Ces tests vérifient :
- La validation des SIRET
- L'encodage des images
- L'enrichissement des données via les APIs
- La gestion des erreurs
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import base64
import io
from PIL import Image

from app.services.document_extractor import (
    DocumentExtractor,
    DocumentExtractorError,
    extract_from_pap_document
)


class TestDocumentExtractorInit:
    """Tests de l'initialisation du DocumentExtractor."""

    def test_init_with_api_key(self):
        """Test: Initialisation avec clé API fournie."""
        extractor = DocumentExtractor(api_key="test_key_123")

        assert extractor.api_key == "test_key_123"
        assert extractor.client is not None

    def test_init_without_api_key_raises_error(self):
        """Test: Initialisation sans clé API lève une erreur."""
        with patch('app.services.document_extractor.OPENAI_API_KEY', None):
            with pytest.raises(DocumentExtractorError) as exc_info:
                DocumentExtractor(api_key=None)

            assert "Clé API OpenAI manquante" in str(exc_info.value)

    def test_init_with_custom_model(self):
        """Test: Initialisation avec modèle personnalisé."""
        extractor = DocumentExtractor(api_key="test_key", model="gpt-4o-mini")

        assert extractor.default_model == "gpt-4o-mini"


class TestValidateSiret:
    """Tests de la validation SIRET."""

    def test_valid_siret_14_digits(self):
        """Test: SIRET valide de 14 chiffres."""
        assert DocumentExtractor._is_valid_siret("38830202800039") is True

    def test_valid_siret_with_spaces(self):
        """Test: SIRET valide avec espaces (nettoyé)."""
        assert DocumentExtractor._is_valid_siret("388 302 028 00039") is True

    def test_valid_siret_with_dashes(self):
        """Test: SIRET valide avec tirets (nettoyé)."""
        assert DocumentExtractor._is_valid_siret("388-302-028-00039") is True

    def test_invalid_siret_too_short(self):
        """Test: SIRET trop court → invalide."""
        assert DocumentExtractor._is_valid_siret("1234567890") is False

    def test_invalid_siret_too_long(self):
        """Test: SIRET trop long → invalide."""
        assert DocumentExtractor._is_valid_siret("123456789012345") is False

    def test_invalid_siret_with_letters(self):
        """Test: SIRET avec lettres → invalide."""
        assert DocumentExtractor._is_valid_siret("12345ABC890123") is False

    def test_invalid_siret_none(self):
        """Test: SIRET None → invalide."""
        assert DocumentExtractor._is_valid_siret(None) is False

    def test_invalid_siret_empty_string(self):
        """Test: SIRET vide → invalide."""
        assert DocumentExtractor._is_valid_siret("") is False


class TestEncodeImage:
    """Tests de l'encodage d'images."""

    def test_encode_image_returns_base64(self):
        """Test: L'encodage retourne bien du base64."""
        extractor = DocumentExtractor(api_key="test_key")

        # Créer une image de test simple
        test_data = b"test image data"

        result = extractor._encode_image(test_data)

        # Vérifier que c'est du base64 valide
        assert isinstance(result, str)
        # Décoder pour vérifier
        decoded = base64.b64decode(result)
        assert decoded == test_data


class TestValidateAndConvertImage:
    """Tests de la validation et conversion d'images."""

    def test_convert_rgb_image(self):
        """Test: Conversion d'une image RGB valide."""
        extractor = DocumentExtractor(api_key="test_key")

        # Créer une image de test RGB
        img = Image.new('RGB', (100, 100), color='red')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        image_data = buffer.getvalue()

        result = extractor._validate_and_convert_image(image_data)

        # Vérifier que l'image est retournée en bytes
        assert isinstance(result, bytes)
        # Vérifier qu'on peut l'ouvrir
        img_result = Image.open(io.BytesIO(result))
        assert img_result.mode in ('RGB', 'L')

    def test_convert_rgba_to_rgb(self):
        """Test: Conversion RGBA → RGB."""
        extractor = DocumentExtractor(api_key="test_key")

        # Créer une image RGBA
        img = Image.new('RGBA', (100, 100), color=(255, 0, 0, 128))
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        image_data = buffer.getvalue()

        result = extractor._validate_and_convert_image(image_data)

        # L'image doit être convertie en RGB
        img_result = Image.open(io.BytesIO(result))
        assert img_result.mode in ('RGB', 'L')

    def test_resize_large_image(self):
        """Test: Redimensionnement d'une grande image."""
        extractor = DocumentExtractor(api_key="test_key")

        # Créer une très grande image
        img = Image.new('RGB', (3000, 3000), color='blue')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        image_data = buffer.getvalue()

        result = extractor._validate_and_convert_image(image_data)

        # L'image doit être redimensionnée
        img_result = Image.open(io.BytesIO(result))
        assert max(img_result.size) <= 2000

    def test_invalid_image_raises_error(self):
        """Test: Image invalide lève une erreur."""
        extractor = DocumentExtractor(api_key="test_key")

        with pytest.raises(DocumentExtractorError) as exc_info:
            extractor._validate_and_convert_image(b"not an image")

        assert "Erreur lors du traitement de l'image" in str(exc_info.value)


class TestEstimateCost:
    """Tests de l'estimation des coûts."""

    def test_estimate_cost_gpt4o_mini(self):
        """Test: Coût pour gpt-4o-mini."""
        extractor = DocumentExtractor(api_key="test_key")

        cost = extractor._estimate_cost(1000, "gpt-4o-mini")

        # 1000 tokens × $0.00015 per 1K = $0.00015
        assert cost == pytest.approx(0.00015, rel=1e-6)

    def test_estimate_cost_gpt4o(self):
        """Test: Coût pour gpt-4o."""
        extractor = DocumentExtractor(api_key="test_key")

        cost = extractor._estimate_cost(1000, "gpt-4o")

        # 1000 tokens × $0.005 per 1K = $0.005
        assert cost == pytest.approx(0.005, rel=1e-6)

    def test_estimate_cost_unknown_model(self):
        """Test: Coût pour modèle inconnu (fallback)."""
        extractor = DocumentExtractor(api_key="test_key")

        cost = extractor._estimate_cost(1000, "unknown-model")

        # Doit utiliser le taux par défaut
        assert cost > 0


@pytest.mark.asyncio
class TestEnrichDataWithApis:
    """Tests de l'enrichissement des données."""

    async def test_enrich_skipped_without_siret(self):
        """Test: Enrichissement ignoré si pas de SIRET valide."""
        extractor = DocumentExtractor(api_key="test_key")

        data = {
            "siret": None,
            "raison_sociale": "Test SARL"
        }

        result = await extractor._enrich_data_with_apis(data)

        # Aucune modification
        assert result == data

    async def test_enrich_skipped_if_all_data_present(self):
        """Test: Enrichissement ignoré si toutes les données sont présentes."""
        extractor = DocumentExtractor(api_key="test_key")

        data = {
            "siret": "38830202800039",
            "effectif": 50,
            "ville": "Paris",
            "code_postal": "75001",
            "idcc": "1234"
        }

        result = await extractor._enrich_data_with_apis(data)

        # Aucune modification (toutes les données sont présentes)
        assert result["siret"] == "38830202800039"
        assert result["effectif"] == 50

    @patch('app.services.document_extractor.PappersAPI')
    async def test_enrich_with_pappers_success(self, mock_pappers_class):
        """Test: Enrichissement réussi via Pappers."""
        # Mock de l'API Pappers
        mock_pappers = Mock()
        mock_pappers.get_siret = AsyncMock(return_value={
            "siret": "38830202800039",
            "effectif": 14,
            "effectif_min": 10,
            "effectif_max": 19,
            "commune": "LE CREUSOT",
            "code_postal": "71200",
            "idcc": "1597",
            "denomination": "J.D. ELEC"
        })
        mock_pappers_class.return_value = mock_pappers

        extractor = DocumentExtractor(api_key="test_key")

        data = {
            "siret": "38830202800039",
            "raison_sociale": "J.D. ELEC"
            # Pas d'effectif, ville, CP, IDCC
        }

        result = await extractor._enrich_data_with_apis(data)

        # Vérifier l'enrichissement
        assert result["effectif"] == 14
        assert result["ville"] == "LE CREUSOT"
        assert result["code_postal"] == "71200"
        assert result["idcc"] == "1597"
        assert result["_metadata"]["enriched_with_pappers"] is True
        assert "effectif" in result["_metadata"]["enriched_fields"]

    @patch('app.services.document_extractor.PappersAPI')
    @patch('app.services.document_extractor.SireneAPI')
    async def test_enrich_fallback_to_sirene(self, mock_sirene_class, mock_pappers_class):
        """Test: Fallback sur Sirene si Pappers échoue."""
        # Mock Pappers qui échoue
        mock_pappers = Mock()
        mock_pappers.get_siret = AsyncMock(return_value=None)
        mock_pappers_class.return_value = mock_pappers

        # Mock Sirene qui réussit
        mock_sirene = Mock()
        mock_sirene.get_siret = AsyncMock(return_value={
            "success": True,
            "etablissement": {
                "commune": "Paris",
                "code_postal": "75001",
                "denomination": "Test SARL"
            }
        })
        mock_sirene_class.return_value = mock_sirene

        extractor = DocumentExtractor(api_key="test_key")

        data = {
            "siret": "38830202800039",
            "raison_sociale": "Test SARL"
        }

        result = await extractor._enrich_data_with_apis(data)

        # Vérifier l'enrichissement via Sirene
        assert result["ville"] == "Paris"
        assert result["code_postal"] == "75001"
        assert result["_metadata"]["enriched_with_sirene"] is True

    @patch('app.services.document_extractor.PappersAPI')
    async def test_enrich_with_effectif_label_fallback(self, mock_pappers_class):
        """Test: Si effectif n'est pas un nombre, on ajoute le label en notes."""
        # Mock Pappers qui retourne un label texte
        mock_pappers = Mock()
        mock_pappers.get_siret = AsyncMock(return_value={
            "siret": "38830202800039",
            "effectif": None,  # Pas de nombre
            "effectifs_label": "Entre 10 et 19 salariés",
            "commune": "LE CREUSOT"
        })
        mock_pappers_class.return_value = mock_pappers

        extractor = DocumentExtractor(api_key="test_key")

        data = {
            "siret": "38830202800039",
            "raison_sociale": "J.D. ELEC"
        }

        result = await extractor._enrich_data_with_apis(data)

        # Vérifier que le label est dans les notes
        assert "Entre 10 et 19 salariés" in result["notes"]


@pytest.mark.asyncio
class TestSearchSiretFromData:
    """Tests de la recherche automatique de SIRET."""

    async def test_search_siret_without_raison_sociale(self):
        """Test: Recherche impossible sans raison sociale."""
        extractor = DocumentExtractor(api_key="test_key")

        result = await extractor._search_siret_from_data(
            raison_sociale=None,
            code_postal="75001"
        )

        assert result is None

    @patch('app.services.document_extractor.OpenAI')
    async def test_search_siret_success(self, mock_openai_class):
        """Test: Recherche SIRET réussie."""
        # Mock de la réponse OpenAI
        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content='{"siret": "38830202800039", "confiance": "high", "source": "pappers.fr"}'))
        ]

        mock_client = Mock()
        mock_client.chat = Mock()
        mock_client.chat.completions = Mock()
        mock_client.chat.completions.create = Mock(return_value=mock_response)

        mock_openai_class.return_value = mock_client

        extractor = DocumentExtractor(api_key="test_key")

        result = await extractor._search_siret_from_data(
            raison_sociale="J.D. ELEC",
            code_postal="71200",
            ville="LE CREUSOT"
        )

        assert result == "38830202800039"

    @patch('app.services.document_extractor.OpenAI')
    async def test_search_siret_not_found(self, mock_openai_class):
        """Test: SIRET non trouvé par la recherche."""
        # Mock de la réponse OpenAI sans SIRET
        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content='{"siret": null, "raison": "Entreprise non trouvée"}'))
        ]

        mock_client = Mock()
        mock_client.chat = Mock()
        mock_client.chat.completions = Mock()
        mock_client.chat.completions.create = Mock(return_value=mock_response)

        mock_openai_class.return_value = mock_client

        extractor = DocumentExtractor(api_key="test_key")

        result = await extractor._search_siret_from_data(
            raison_sociale="Entreprise Inconnue",
            ville="Paris"
        )

        assert result is None


@pytest.mark.asyncio
class TestExtractFromDocument:
    """Tests de la méthode extract_from_document."""

    @patch.object(DocumentExtractor, '_convert_pdf_to_image')
    @patch.object(DocumentExtractor, 'extract_from_image')
    async def test_extract_from_pdf(self, mock_extract_image, mock_convert_pdf):
        """Test: Extraction depuis un PDF."""
        # Mock de la conversion PDF → image
        mock_convert_pdf.return_value = b"fake_image_data"

        # Mock de l'extraction
        mock_extract_image.return_value = {
            "siret": "38830202800039",
            "raison_sociale": "Test"
        }

        extractor = DocumentExtractor(api_key="test_key")

        result = await extractor.extract_from_document(
            document_data=b"fake_pdf_data",
            is_pdf=True
        )

        # Vérifier que le PDF a été converti
        mock_convert_pdf.assert_called_once()
        # Vérifier que l'extraction a été appelée sur l'image
        mock_extract_image.assert_called_once_with(
            b"fake_image_data",
            model=None,
            temperature=0.1
        )
        assert result["siret"] == "38830202800039"

    @patch.object(DocumentExtractor, 'extract_from_image')
    async def test_extract_from_image_direct(self, mock_extract_image):
        """Test: Extraction depuis une image (pas de conversion)."""
        # Mock de l'extraction
        mock_extract_image.return_value = {
            "siret": "38830202800039",
            "raison_sociale": "Test"
        }

        extractor = DocumentExtractor(api_key="test_key")

        result = await extractor.extract_from_document(
            document_data=b"fake_image_data",
            is_pdf=False
        )

        # Vérifier que l'extraction a été appelée directement
        mock_extract_image.assert_called_once_with(
            b"fake_image_data",
            model=None,
            temperature=0.1
        )
        assert result["siret"] == "38830202800039"


# ============================================================================
# Tests d'intégration (nécessitent les APIs réelles)
# ============================================================================

@pytest.mark.integration
@pytest.mark.openai
@pytest.mark.asyncio
async def test_extract_from_image_integration_real_api():
    """
    Test d'intégration avec l'API OpenAI réelle.

    ⚠️ Nécessite OPENAI_API_KEY dans .env
    Exécuter avec: pytest -m openai
    """
    import os
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        pytest.skip("OPENAI_API_KEY non configurée")

    # Créer une image de test simple avec du texte
    img = Image.new('RGB', (800, 600), color='white')
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    image_data = buffer.getvalue()

    extractor = DocumentExtractor(api_key=api_key)

    # Note: Cette image ne contient pas de PAP réel, donc l'extraction
    # va probablement retourner beaucoup de None, mais ça teste l'API
    result = await extractor.extract_from_image(image_data)

    # Vérifier que la structure de base est présente
    assert "_metadata" in result
    assert "model" in result["_metadata"]
    assert "extraction_date" in result["_metadata"]
