"""
Tests unitaires pour app/services/pappers_api.py

Ces tests vérifient :
- L'extraction de l'IDCC avec les 3 fallbacks
- Le calcul de l'effectif depuis min/max
- Le parsing des établissements
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from app.services.pappers_api import PappersAPI


class TestExtractIDCC:
    """Tests de la fonction _extract_idcc() avec ses 3 fallbacks."""

    def test_extract_idcc_direct(self):
        """Test Fallback 1: IDCC direct au niveau entreprise."""
        entreprise = {
            "siren": "388302028",
            "idcc": 1597,
            "nom_entreprise": "J.D. ELEC"
        }

        idcc = PappersAPI._extract_idcc(entreprise)

        assert idcc == "1597"

    def test_extract_idcc_convention_principale(self):
        """Test Fallback 2: IDCC dans convention_collective_principale."""
        entreprise = {
            "siren": "388302028",
            "convention_collective_principale": {
                "idcc": 2420,
                "nom": "Convention collective nationale des cadres du bâtiment"
            }
        }

        idcc = PappersAPI._extract_idcc(entreprise)

        assert idcc == "2420"

    def test_extract_idcc_conventions_list(self):
        """Test Fallback 3: IDCC dans conventions_collectives[0]."""
        entreprise = {
            "siren": "388302028",
            "conventions_collectives": [
                {"idcc": 1597, "nom": "Convention..."},
                {"idcc": 2420, "nom": "Convention..."}
            ]
        }

        idcc = PappersAPI._extract_idcc(entreprise)

        assert idcc == "1597"  # Premier de la liste

    def test_extract_idcc_not_found(self):
        """Test: IDCC non trouvé → retourne None."""
        entreprise = {
            "siren": "388302028",
            "nom_entreprise": "Test SA"
        }

        idcc = PappersAPI._extract_idcc(entreprise)

        assert idcc is None

    def test_extract_idcc_zero_ignored(self):
        """Test: IDCC = 0 est ignoré (invalide)."""
        entreprise = {
            "siren": "388302028",
            "idcc": 0
        }

        idcc = PappersAPI._extract_idcc(entreprise)

        assert idcc is None

    def test_extract_idcc_priority_order(self):
        """Test: Les fallbacks sont appelés dans le bon ordre."""
        entreprise = {
            "siren": "388302028",
            "idcc": 1111,  # Fallback 1 (prioritaire)
            "convention_collective_principale": {
                "idcc": 2222  # Fallback 2 (sera ignoré)
            },
            "conventions_collectives": [
                {"idcc": 3333}  # Fallback 3 (sera ignoré)
            ]
        }

        idcc = PappersAPI._extract_idcc(entreprise)

        # Doit retourner le Fallback 1
        assert idcc == "1111"


class TestCalculEffectif:
    """Tests du calcul d'effectif depuis effectif_min/effectif_max."""

    def test_calcul_effectif_moyenne(self):
        """Test: Calcul de la moyenne (10+19)/2 = 14."""
        pappers_api = PappersAPI()

        etablissement = {"siret": "38830202800039"}
        entreprise = {
            "effectif_min": 10,
            "effectif_max": 19,
            "effectif": "Entre 10 et 19 salariés"  # Texte (non utilisé)
        }

        result = pappers_api._parse_etablissement(etablissement, entreprise)

        assert result["effectif"] == 14
        assert result["effectif_min"] == 10
        assert result["effectif_max"] == 19
        assert result["effectifs_label"] == "Entre 10 et 19 salariés"

    def test_calcul_effectif_grandes_tranches(self):
        """Test: Calcul pour grande entreprise (100+500)/2 = 300."""
        pappers_api = PappersAPI()

        etablissement = {"siret": "12345678901234"}
        entreprise = {
            "effectif_min": 100,
            "effectif_max": 500
        }

        result = pappers_api._parse_etablissement(etablissement, entreprise)

        assert result["effectif"] == 300

    def test_calcul_effectif_missing_data(self):
        """Test: Si min/max absents → effectif = None."""
        pappers_api = PappersAPI()

        etablissement = {"siret": "12345678901234"}
        entreprise = {}  # Pas de données effectif

        result = pappers_api._parse_etablissement(etablissement, entreprise)

        assert result["effectif"] is None


class TestParseEtablissement:
    """Tests du parsing complet d'un établissement."""

    def test_parse_etablissement_complet(self, sample_pappers_response):
        """Test: Parsing avec toutes les données présentes."""
        pappers_api = PappersAPI()

        etab = sample_pappers_response["etablissements"][0]
        entreprise = sample_pappers_response

        result = pappers_api._parse_etablissement(etab, entreprise)

        # Vérifications essentielles
        assert result["siret"] == "38830202800039"
        assert result["siren"] == "388302028"
        assert result["denomination"] == "J.D. ELEC"
        assert result["code_postal"] == "71200"
        assert result["commune"] == "LE CREUSOT"
        assert result["adresse"] == "39 RUE DES ABATTOIRS B"
        assert result["est_siege"] is True
        assert result["est_actif"] is True

        # Nouvelles données (nos corrections)
        assert result["effectif"] == 14  # (10+19)/2
        assert result["idcc"] == "1597"  # Premier IDCC
        assert result["source"] == "Pappers"

    def test_parse_etablissement_avec_idcc(self):
        """Test: Parsing avec IDCC dans conventions_collectives."""
        pappers_api = PappersAPI()

        etablissement = {
            "siret": "12345678901234",
            "code_postal": "75001",
            "ville": "Paris"
        }

        entreprise = {
            "siren": "123456789",
            "nom_entreprise": "Test SARL",
            "effectif_min": 50,
            "effectif_max": 99,
            "conventions_collectives": [
                {"idcc": 1234, "nom": "Test"}
            ]
        }

        result = pappers_api._parse_etablissement(etablissement, entreprise)

        assert result["idcc"] == "1234"
        assert result["effectif"] == 74  # (50+99)/2


@pytest.mark.asyncio
class TestGetSiret:
    """Tests de la méthode get_siret() (appel API réel mocké)."""

    @patch('httpx.AsyncClient')
    async def test_get_siret_success(self, mock_client_class, sample_pappers_response):
        """Test: Récupération réussie d'un SIRET."""
        # Mock de la réponse HTTP
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value=sample_pappers_response)

        mock_client = Mock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        mock_client_class.return_value = mock_client

        # Appel de get_siret
        pappers_api = PappersAPI(api_key="test_key")
        result = await pappers_api.get_siret("38830202800039")

        # Vérifications
        assert result is not None
        assert result["siret"] == "38830202800039"
        assert result["effectif"] == 14
        assert result["idcc"] == "1597"

    @patch('httpx.AsyncClient')
    async def test_get_siret_not_found(self, mock_client_class):
        """Test: SIRET non trouvé → retourne None."""
        mock_response = Mock()
        mock_response.status_code = 404

        mock_client = Mock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        mock_client_class.return_value = mock_client

        pappers_api = PappersAPI(api_key="test_key")
        result = await pappers_api.get_siret("99999999999999")

        assert result is None

    async def test_get_siret_sans_api_key(self, monkeypatch):
        """Test: Appel sans clé API → retourne None."""
        # S'assurer qu'il n'y a pas de clé dans l'environnement
        monkeypatch.delenv("PAPPERS_API_KEY", raising=False)

        pappers_api = PappersAPI(api_key=None)
        result = await pappers_api.get_siret("38830202800039")

        assert result is None


# ============================================================================
# Tests d'intégration (nécessitent l'API Pappers réelle)
# ============================================================================

@pytest.mark.integration
@pytest.mark.pappers
@pytest.mark.asyncio
async def test_get_siret_integration_real_api():
    """
    Test d'intégration avec l'API Pappers réelle.

    ⚠️ Nécessite PAPPERS_API_KEY dans .env
    Exécuter avec: pytest -m pappers
    """
    import os
    api_key = os.getenv("PAPPERS_API_KEY")

    if not api_key:
        pytest.skip("PAPPERS_API_KEY non configurée")

    pappers_api = PappersAPI(api_key=api_key)
    result = await pappers_api.get_siret("38830202800039")

    # Vérifications sur données réelles
    assert result is not None
    assert result["siret"] == "38830202800039"
    assert result["siren"] == "388302028"
    assert result["denomination"] == "J.D. ELEC"
    assert result["effectif"] is not None  # Doit être calculé
    assert result["idcc"] is not None      # Doit être trouvé
