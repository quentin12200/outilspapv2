# Tests Unitaires - OutilsPAPv2

Ce dossier contient tous les tests unitaires et d'intégration pour le projet OutilsPAPv2.

## 📁 Structure

```
tests/
├── README.md                          # Ce fichier
├── conftest.py                        # Fixtures communes (automatiquement chargé)
├── __init__.py
├── services/
│   ├── __init__.py
│   ├── test_pappers_api.py           # Tests API Pappers
│   └── test_document_extractor.py    # Tests extraction PDF/GPT-4
└── routers/
    └── (à venir)
```

## 🚀 Installation

```bash
# Installer pytest et ses dépendances
pip install pytest pytest-asyncio pytest-mock pytest-cov
```

## ▶️ Exécution des Tests

### Tous les tests

```bash
# Mode verbose avec couleurs
pytest

# Avec résumé détaillé
pytest -v
```

### Tests par catégorie (markers)

```bash
# Tests unitaires uniquement (rapides, sans IO)
pytest -m unit

# Tests d'intégration (avec API réelles)
pytest -m integration

# Tests nécessitant l'API Pappers
pytest -m pappers

# Tests nécessitant l'API OpenAI
pytest -m openai

# Tous les tests SAUF les intégrations
pytest -m "not integration"
```

### Tests par fichier

```bash
# Tests Pappers uniquement
pytest tests/services/test_pappers_api.py -v

# Tests Document Extractor uniquement
pytest tests/services/test_document_extractor.py -v
```

### Tests par fonction

```bash
# Un test spécifique
pytest tests/services/test_pappers_api.py::TestExtractIDCC::test_extract_idcc_direct -v

# Tous les tests d'une classe
pytest tests/services/test_pappers_api.py::TestExtractIDCC -v
```

## 📊 Coverage (Couverture de Code)

```bash
# Générer un rapport de couverture
pytest --cov=app --cov-report=html --cov-report=term

# Voir le rapport HTML
# Le rapport sera dans htmlcov/index.html
```

## 🔧 Configuration

La configuration pytest se trouve dans `pytest.ini` à la racine du projet.

### Markers disponibles

- `unit` : Tests unitaires (rapides, sans IO)
- `integration` : Tests d'intégration (avec DB, API externes)
- `slow` : Tests lents (> 1s)
- `pappers` : Tests nécessitant l'API Pappers
- `openai` : Tests nécessitant l'API OpenAI

## 🧪 Tests Actuels

### `test_pappers_api.py`

Tests pour `app/services/pappers_api.py` :

**TestExtractIDCC** (6 tests)
- ✅ Extraction IDCC direct au niveau entreprise
- ✅ Extraction depuis `convention_collective_principale`
- ✅ Extraction depuis `conventions_collectives[0]`
- ✅ IDCC non trouvé → retourne None
- ✅ IDCC = 0 est ignoré (invalide)
- ✅ Ordre de priorité des fallbacks

**TestCalculEffectif** (3 tests)
- ✅ Calcul moyenne depuis `effectif_min`/`effectif_max`
- ✅ Grandes tranches (100-500 → 300)
- ✅ Données manquantes → None

**TestParseEtablissement** (2 tests)
- ✅ Parsing complet avec toutes les données
- ✅ Parsing avec IDCC dans conventions_collectives

**TestGetSiret** (3 tests)
- ✅ Récupération réussie d'un SIRET (mocked)
- ✅ SIRET non trouvé (404)
- ✅ Appel sans clé API

**Tests d'intégration**
- ⚠️ `test_get_siret_integration_real_api` (nécessite PAPPERS_API_KEY)

### `test_document_extractor.py`

Tests pour `app/services/document_extractor.py` :

**TestDocumentExtractorInit** (3 tests)
- ✅ Initialisation avec clé API
- ✅ Erreur si pas de clé API
- ✅ Modèle personnalisé

**TestValidateSiret** (8 tests)
- ✅ SIRET valide (14 chiffres)
- ✅ SIRET avec espaces/tirets (nettoyé)
- ✅ SIRET trop court/long
- ✅ SIRET avec lettres
- ✅ SIRET None/vide

**TestEncodeImage** (1 test)
- ✅ Encodage base64

**TestValidateAndConvertImage** (4 tests)
- ✅ Conversion RGB
- ✅ Conversion RGBA → RGB
- ✅ Redimensionnement grandes images
- ✅ Erreur image invalide

**TestEstimateCost** (3 tests)
- ✅ Coût gpt-4o-mini
- ✅ Coût gpt-4o
- ✅ Coût modèle inconnu (fallback)

**TestEnrichDataWithApis** (5 tests)
- ✅ Enrichissement ignoré sans SIRET
- ✅ Enrichissement ignoré si données complètes
- ✅ Enrichissement via Pappers
- ✅ Fallback sur Sirene si Pappers échoue
- ✅ Label effectif en notes si pas de nombre

**TestSearchSiretFromData** (3 tests)
- ✅ Recherche impossible sans raison sociale
- ✅ Recherche SIRET réussie
- ✅ SIRET non trouvé

**TestExtractFromDocument** (2 tests)
- ✅ Extraction depuis PDF
- ✅ Extraction depuis image

**Tests d'intégration**
- ⚠️ `test_extract_from_image_integration_real_api` (nécessite OPENAI_API_KEY)

## 🔐 Tests d'Intégration

Les tests d'intégration nécessitent des clés API réelles configurées dans `.env` :

```bash
# .env
PAPPERS_API_KEY=votre_cle_pappers
OPENAI_API_KEY=votre_cle_openai
```

Pour exécuter UNIQUEMENT les tests d'intégration :

```bash
# Tests avec API Pappers
pytest -m pappers -v

# Tests avec API OpenAI
pytest -m openai -v

# Tous les tests d'intégration
pytest -m integration -v
```

⚠️ **IMPORTANT** : Les tests d'intégration :
- Consomment des crédits API réels
- Peuvent être lents (appels réseau)
- Nécessitent une connexion internet
- Sont automatiquement skippés si les clés ne sont pas configurées

## 📝 Fixtures Communes

Les fixtures sont définies dans `conftest.py` et automatiquement disponibles dans tous les tests :

### Données de test

- `sample_siret` : SIRET valide pour les tests
- `sample_siren` : SIREN valide pour les tests
- `sample_pappers_response` : Réponse type API Pappers (J.D. ELEC)
- `sample_pap_data` : Données PAP extraites type

### Mocks API

- `mock_pappers_api` : Mock de l'API Pappers avec réponse réussie
- `mock_openai_client` : Mock du client OpenAI (GPT-4 Vision)
- `mock_db_session` : Mock de session SQLAlchemy

### Variables d'environnement

- `mock_env` : Configure les variables d'env pour les tests

## 🎯 Bonnes Pratiques

### Écrire un nouveau test

```python
import pytest
from app.services.my_service import MyService

class TestMyService:
    """Tests pour MyService."""

    def test_my_function_success(self):
        """Test: Description claire du scénario testé."""
        # Arrange (Préparer)
        service = MyService()
        input_data = {"key": "value"}

        # Act (Agir)
        result = service.my_function(input_data)

        # Assert (Vérifier)
        assert result == expected_value

    @pytest.mark.asyncio
    async def test_async_function(self):
        """Test: Fonction asynchrone."""
        service = MyService()

        result = await service.async_function()

        assert result is not None
```

### Utiliser les fixtures

```python
def test_with_fixture(sample_siret, mock_pappers_api):
    """Test: Utilisation de fixtures."""
    # Les fixtures sont automatiquement injectées
    assert len(sample_siret) == 14

    # Le mock est déjà configuré
    result = await mock_pappers_api.get_siret(sample_siret)
    assert result is not None
```

### Mocker une dépendance

```python
from unittest.mock import patch, Mock

@patch('app.services.my_service.external_api')
def test_with_mock(mock_external_api):
    """Test: Mocker une API externe."""
    # Configurer le mock
    mock_external_api.get_data.return_value = {"result": "success"}

    # Utiliser le service (qui utilise external_api)
    service = MyService()
    result = service.process()

    # Vérifier
    assert result == {"result": "success"}
    mock_external_api.get_data.assert_called_once()
```

## 🐛 Debugging

### Voir les print() dans les tests

```bash
pytest -s
```

### Voir les logs

```bash
pytest --log-cli-level=INFO
```

### S'arrêter au premier échec

```bash
pytest -x
```

### Relancer uniquement les tests échoués

```bash
pytest --lf
```

### Mode verbose maximum

```bash
pytest -vv --tb=long
```

## 📈 Statistiques Actuelles

```
Total de tests : 43
- test_pappers_api.py : 15 tests
- test_document_extractor.py : 28 tests

Tests unitaires : 41
Tests d'intégration : 2
```

## 🔜 Tests à Ajouter

- [ ] Tests pour `app/routers/api_campaign.py` (SSE)
- [ ] Tests pour `app/services/sirene_api.py`
- [ ] Tests pour `app/services/etl.py` (import Excel)
- [ ] Tests pour les modèles de base de données
- [ ] Tests end-to-end pour les workflows complets

## 📚 Ressources

- [Documentation pytest](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [unittest.mock](https://docs.python.org/3/library/unittest.mock.html)

---

**Dernière mise à jour** : 2025-12-11
