"""
Fixtures communes pour tous les tests.

Ce fichier est automatiquement chargé par pytest.
"""
import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
from typing import Dict, Any


# ============================================================================
# FIXTURES - Données de test
# ============================================================================

@pytest.fixture
def sample_siret():
    """SIRET valide pour les tests."""
    return "38830202800000"


@pytest.fixture
def sample_siren():
    """SIREN valide pour les tests."""
    return "388302028"


@pytest.fixture
def sample_pappers_response() -> Dict[str, Any]:
    """
    Réponse type de l'API Pappers pour un SIRET.

    Basé sur la vraie réponse de J.D. ELEC (38830202800000).
    """
    return {
        "siren": "388302028",
        "nom_entreprise": "J.D. ELEC",
        "effectif": "Entre 10 et 19 salariés",
        "effectif_min": 10,
        "effectif_max": 19,
        "tranche_effectif": "11",
        "code_naf": "43.21A",
        "libelle_code_naf": "Travaux d'installation électrique dans tous locaux",
        "forme_juridique": "SAS, société par actions simplifiée",
        "conventions_collectives": [
            {
                "nom": "Convention collective nationale concernant les ouvriers employés par les entreprises du bâtiment",
                "idcc": 1597,
                "confirmee": True
            },
            {
                "nom": "Convention collective nationale des cadres du bâtiment",
                "idcc": 2420,
                "confirmee": True
            }
        ],
        "etablissements": [
            {
                "siret": "38830202800039",
                "adresse_ligne_1": "39 RUE DES ABATTOIRS",
                "adresse_ligne_2": "B",
                "code_postal": "71200",
                "ville": "LE CREUSOT",
                "code_naf": "43.21A",
                "libelle_code_naf": "Travaux d'installation électrique dans tous locaux",
                "siege": True,
                "etablissement_cesse": False,
                "latitude": 46.78742999980233,
                "longitude": 4.439351999994265
            }
        ]
    }


@pytest.fixture
def sample_pap_data() -> Dict[str, Any]:
    """Données PAP extraites type (résultat de GPT-4 Vision)."""
    return {
        "siret": "38830202800039",
        "raison_sociale": "J.D. ELEC",
        "code_postal": "71200",
        "ville": "LE CREUSOT",
        "effectif": None,  # À enrichir via Pappers
        "idcc": None,      # À enrichir via Pappers
        "date_invitation": "2025-01-15",
        "date_election": "2025-02-20",
        "inscrits": 12,
        "notes": ""
    }


# ============================================================================
# FIXTURES - Mocks API externes
# ============================================================================

@pytest.fixture
def mock_pappers_api(sample_pappers_response):
    """Mock de l'API Pappers avec réponse réussie."""
    mock = Mock()
    mock.api_key = "test_api_key_pappers"

    # Mock de la méthode get_siret (async)
    async def mock_get_siret(siret: str):
        if siret == "38830202800039":
            etab = sample_pappers_response["etablissements"][0]
            return {
                "siret": etab["siret"],
                "siren": sample_pappers_response["siren"],
                "denomination": sample_pappers_response["nom_entreprise"],
                "code_postal": etab["code_postal"],
                "commune": etab["ville"],
                "effectif": 14,  # Moyenne calculée (10+19)/2
                "effectif_min": 10,
                "effectif_max": 19,
                "effectifs_label": "Entre 10 et 19 salariés",
                "idcc": "1597",
                "activite_principale": etab["code_naf"],
                "libelle_activite": etab["libelle_code_naf"],
            }
        return None

    mock.get_siret = AsyncMock(side_effect=mock_get_siret)
    return mock


@pytest.fixture
def mock_openai_client():
    """Mock du client OpenAI (pour GPT-4 Vision)."""
    mock = Mock()

    # Mock de la réponse GPT
    mock_response = Mock()
    mock_response.choices = [
        Mock(message=Mock(content='{"siret": "38830202800039", "raison_sociale": "J.D. ELEC", "ville": "LE CREUSOT"}'))
    ]

    mock.chat = Mock()
    mock.chat.completions = Mock()
    mock.chat.completions.create = Mock(return_value=mock_response)

    return mock


@pytest.fixture
def mock_db_session():
    """Mock de la session SQLAlchemy."""
    session = Mock()
    session.query = Mock()
    session.add = Mock()
    session.commit = Mock()
    session.rollback = Mock()
    session.close = Mock()
    return session


# ============================================================================
# FIXTURES - Variables d'environnement
# ============================================================================

@pytest.fixture
def mock_env(monkeypatch):
    """Configure les variables d'environnement pour les tests."""
    monkeypatch.setenv("PAPPERS_API_KEY", "test_pappers_key")
    monkeypatch.setenv("OPENAI_API_KEY", "test_openai_key")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")


# ============================================================================
# HOOKS pytest (setup/teardown)
# ============================================================================

def pytest_configure(config):
    """Configuration globale avant tous les tests."""
    print("\n🧪 Lancement des tests outilspapv2...")


def pytest_unconfigure(config):
    """Nettoyage après tous les tests."""
    print("\n✅ Tests terminés !")
