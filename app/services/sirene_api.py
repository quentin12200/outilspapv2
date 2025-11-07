"""
Service d'intégration avec l'API Sirene (INSEE)
Documentation: https://www.data.gouv.fr/dataservices/api-sirene-open-data/
"""

import os
import uuid
import httpx
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Import du rate limiter (sera utilisé de manière synchrone même dans les fonctions async)
try:
    from ..rate_limiter import sirene_rate_limiter
except ImportError:
    from app.rate_limiter import sirene_rate_limiter

# URL de base de l'API Sirene (version 3.11)
# Documentation: https://api.insee.fr/catalogue/
SIRENE_API_BASE = "https://api.insee.fr/api-sirene/3.11"

# Timeout pour les requêtes (secondes)
REQUEST_TIMEOUT = 10.0


class SireneAPIError(Exception):
    """Exception levée en cas d'erreur avec l'API Sirene"""
    pass


class SireneAPI:
    """Client pour l'API Sirene de l'INSEE"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialise le client API Sirene

        Args:
            api_key: Clé API optionnelle pour augmenter les limites de taux
                    Si None, utilise l'API publique (30 req/min)
        """
        provided = (api_key or "").strip()
        env_token = (os.getenv("SIRENE_API_TOKEN") or "").strip()
        env_key = (os.getenv("SIRENE_API_KEY") or os.getenv("API_SIRENE_KEY") or "").strip()

        self.bearer_token: Optional[str] = None
        self.integration_key: Optional[str] = None

        if provided:
            if self._looks_like_integration_key(provided):
                self.integration_key = provided
            else:
                self.bearer_token = provided

        if not self.bearer_token and env_token:
            self.bearer_token = env_token
        if not self.integration_key and env_key:
            self.integration_key = env_key

        # Pour compatibilité descendante, expose self.api_key avec la valeur utilisée
        self.api_key = self.bearer_token or self.integration_key

        self.headers = {
            "Accept": "application/json"
        }
        if self.bearer_token:
            self.headers["Authorization"] = f"Bearer {self.bearer_token}"
            logger.info(f"[SIRENE API] Using Bearer token (OAuth): {self.bearer_token[:8]}...{self.bearer_token[-4:]}")
        if self.integration_key:
            # API Sirene 3.11 : utiliser X-INSEE-Api-Key-Integration
            self.headers["X-INSEE-Api-Key-Integration"] = self.integration_key
            logger.info(f"[SIRENE API] Using Integration Key: {self.integration_key[:8]}...{self.integration_key[-4:]} (length: {len(self.integration_key)})")
            logger.info(f"[SIRENE API] Header: X-INSEE-Api-Key-Integration")

        if not self.bearer_token and not self.integration_key:
            logger.warning("[SIRENE API] ⚠️ NO API KEY configured - Using public access (30 req/min limit)")

    @staticmethod
    def _looks_like_integration_key(value: str) -> bool:
        """Détecte les clés API d'intégration (format UUID v4)."""
        try:
            uuid.UUID(value)
            return True
        except (ValueError, AttributeError, TypeError):
            return False

    async def get_siret(self, siret: str) -> Optional[Dict[str, Any]]:
        """
        Récupère les informations d'un établissement par son SIRET

        Args:
            siret: Numéro SIRET (14 chiffres)

        Returns:
            Dictionnaire avec les infos de l'établissement ou None si non trouvé
        """
        # Nettoie le SIRET
        siret_clean = siret.strip().replace(" ", "")

        if len(siret_clean) != 14 or not siret_clean.isdigit():
            logger.warning(f"SIRET invalide: {siret}")
            return None

        url = f"{SIRENE_API_BASE}/siret/{siret_clean}"

        try:
            # Respecter le rate limit (30 req/min pour accès public gratuit)
            await asyncio.to_thread(sirene_rate_limiter.wait_if_needed)

            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.get(url, headers=self.headers)

                if response.status_code == 200:
                    data = response.json()
                    return self._parse_etablissement(data.get("etablissement", {}))
                elif response.status_code == 404:
                    logger.info(f"SIRET non trouvé: {siret_clean}")
                    return None
                elif response.status_code == 429:
                    logger.warning("Limite de taux API Sirene atteinte")
                    raise SireneAPIError("Trop de requêtes, veuillez patienter")
                else:
                    logger.error(f"Erreur API Sirene ({response.status_code}): {response.text}")
                    raise SireneAPIError(f"Erreur API: {response.status_code}")

        except httpx.TimeoutException:
            logger.error(f"Timeout lors de la requête SIRET {siret_clean}")
            raise SireneAPIError("Timeout de l'API Sirene")
        except httpx.RequestError as e:
            logger.error(f"Erreur réseau API Sirene: {e}")
            raise SireneAPIError("Erreur de connexion à l'API Sirene")

    async def search_siret(
        self,
        denomination: str,
        code_postal: Optional[str] = None,
        commune: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Recherche des établissements par raison sociale, code postal et/ou commune.
        Utilise plusieurs stratégies de recherche pour maximiser les résultats.
        Le code postal est prioritaire sur la commune si les deux sont fournis.
        """

        denomination = (denomination or "").strip()
        code_postal = (code_postal or "").strip()
        commune = (commune or "").strip()

        if not denomination:
            return []

        url = f"{SIRENE_API_BASE}/siret"

        def _sanitize(value: str) -> str:
            cleaned = value.replace('"', ' ')
            # L'API supporte mal les doubles espaces : on compacte et on passe en majuscules
            # (l'API effectue des comparaisons insensibles à la casse mais cela évite les
            # incohérences d'encodage).
            return " ".join(cleaned.split()).upper()

        # Stratégies de recherche multiples (de la plus stricte à la plus permissive)
        search_strategies = []

        # Priorité: code postal > commune
        if code_postal:
            # Stratégie 1: Recherche stricte avec code postal
            search_strategies.append({
                "name": "strict_postal",
                "query": f'denominationUniteLegale:"{_sanitize(denomination)}" AND codePostalEtablissement:{code_postal}'
            })

            # Stratégie 2: Recherche avec wildcards + code postal
            den_parts = _sanitize(denomination).split()
            if len(den_parts) > 1:
                den_wildcard = " AND ".join([f'denominationUniteLegale:*{part}*' for part in den_parts])
                search_strategies.append({
                    "name": "wildcard_postal",
                    "query": f'({den_wildcard}) AND codePostalEtablissement:{code_postal}'
                })
            else:
                search_strategies.append({
                    "name": "wildcard_postal",
                    "query": f'denominationUniteLegale:*{_sanitize(denomination)}* AND codePostalEtablissement:{code_postal}'
                })

        elif commune:
            # Stratégie 1: Recherche stricte avec AND
            search_strategies.append({
                "name": "strict",
                "query": f'denominationUniteLegale:"{_sanitize(denomination)}" AND libelleCommuneEtablissement:"{_sanitize(commune)}"'
            })

            # Stratégie 2: Recherche avec wildcards pour matching partiel
            den_parts = _sanitize(denomination).split()
            if len(den_parts) > 1:
                # Si plusieurs mots, chercher avec wildcards sur chaque mot
                den_wildcard = " AND ".join([f'denominationUniteLegale:*{part}*' for part in den_parts])
                search_strategies.append({
                    "name": "wildcard",
                    "query": f'({den_wildcard}) AND libelleCommuneEtablissement:*{_sanitize(commune)}*'
                })
            else:
                # Un seul mot
                search_strategies.append({
                    "name": "wildcard",
                    "query": f'denominationUniteLegale:*{_sanitize(denomination)}* AND libelleCommuneEtablissement:*{_sanitize(commune)}*'
                })

        # Stratégie finale: Recherche par dénomination seule (fallback)
        search_strategies.append({
            "name": "denomination_only",
            "query": f'denominationUniteLegale:*{_sanitize(denomination)}*'
        })

        # Essayer chaque stratégie jusqu'à trouver des résultats
        for strategy in search_strategies:
            params = {
                "q": strategy["query"],
                "nombre": str(max(1, min(limit, 20))),
            }

            try:
                # Respecter le rate limit avant chaque recherche
                await asyncio.to_thread(sirene_rate_limiter.wait_if_needed)

                async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                    response = await client.get(url, headers=self.headers, params=params)

                if response.status_code == 200:
                    data = response.json()
                    etablissements = data.get("etablissements", [])

                    if etablissements:
                        logger.info(f"Sirene search: {len(etablissements)} résultats avec stratégie '{strategy['name']}'")
                        results = [self._parse_etablissement(etab) for etab in etablissements]

                        # Filtrer les résultats selon le contexte
                        if strategy["name"] == "denomination_only":
                            # Si stratégie fallback, filtrer par code postal ou commune
                            if code_postal:
                                results = [
                                    r for r in results
                                    if (r.get("code_postal") or "").startswith(code_postal)
                                ]
                            elif commune:
                                commune_lower = commune.lower()
                                results = [
                                    r for r in results
                                    if commune_lower in (r.get("commune") or "").lower()
                                ]

                        if results:
                            return results[:limit]

                    # Si pas de résultats avec cette stratégie, essayer la suivante
                    logger.info(f"Sirene search: aucun résultat avec stratégie '{strategy['name']}', essai suivant...")
                    continue

                elif response.status_code in (400, 404):
                    # Erreur de requête, essayer la stratégie suivante
                    logger.debug(f"Sirene search: erreur {response.status_code} avec stratégie '{strategy['name']}'")
                    continue

                elif response.status_code == 401:
                    logger.error("Clé API Sirene absente ou invalide")
                    raise SireneAPIError("Accès refusé par l'API Sirene")

                elif response.status_code == 429:
                    logger.warning("Limite de taux API Sirene atteinte")
                    raise SireneAPIError("Trop de requêtes, veuillez patienter")
                else:
                    logger.error(
                        "Erreur API Sirene (%s): %s",
                        response.status_code,
                        response.text,
                    )
                    raise SireneAPIError(f"Erreur API: {response.status_code}")

            except httpx.TimeoutException:
                location = f"CP:{code_postal}" if code_postal else commune or "N/A"
                logger.error(
                    "Timeout lors de la recherche Sirene pour %s / %s",
                    denomination,
                    location,
                )
                raise SireneAPIError("Timeout de l'API Sirene")
            except httpx.RequestError as e:
                logger.error(f"Erreur réseau API Sirene: {e}")
                raise SireneAPIError("Erreur de connexion à l'API Sirene")

        # Aucune stratégie n'a donné de résultats
        location = f"CP:{code_postal}" if code_postal else commune or "N/A"
        logger.info(f"Sirene search: aucun résultat trouvé pour '{denomination}' / '{location}'")
        return []

    def _parse_etablissement(self, etab: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse les données d'un établissement depuis l'API

        Args:
            etab: Données brutes de l'établissement

        Returns:
            Dictionnaire avec les champs pertinents
        """
        unite_legale = etab.get("uniteLegale", {})
        adresse = etab.get("adresseEtablissement", {})
        periodesEtablissement = etab.get("periodesEtablissement", [])
        periode_actuelle = periodesEtablissement[0] if periodesEtablissement else {}

        # Construction de l'adresse complète
        numero_voie = adresse.get("numeroVoieEtablissement", "")
        type_voie = adresse.get("typeVoieEtablissement", "")
        libelle_voie = adresse.get("libelleVoieEtablissement", "")
        complement = adresse.get("complementAdresseEtablissement", "")
        code_postal = adresse.get("codePostalEtablissement", "")
        commune = adresse.get("libelleCommuneEtablissement", "")

        adresse_complete_parts = [
            numero_voie,
            type_voie,
            libelle_voie,
            complement,
            code_postal,
            commune
        ]
        adresse_complete = " ".join([p for p in adresse_complete_parts if p]).strip()

        # Raison sociale (plusieurs champs possibles)
        denomination = (
            unite_legale.get("denominationUniteLegale") or
            unite_legale.get("denominationUsuelle1UniteLegale") or
            f"{unite_legale.get('prenomUsuelUniteLegale', '')} {unite_legale.get('nomUniteLegale', '')}".strip() or
            "Non renseigné"
        )

        # Effectifs
        tranche_effectifs = periode_actuelle.get("trancheEffectifsEtablissement")
        effectifs_label = self._get_effectifs_label(tranche_effectifs)

        # État de l'établissement
        etat_admin = periode_actuelle.get("etatAdministratifEtablissement", "A")
        est_actif = etat_admin == "A"

        # IDCC (convention collective)
        idcc = unite_legale.get("identifiantConventionCollectiveRenseignee")

        return {
            "siret": etab.get("siret"),
            "siren": etab.get("siren"),
            "denomination": denomination,
            "enseigne": periode_actuelle.get("enseigne1Etablissement"),
            "adresse": adresse_complete,
            "code_postal": code_postal,
            "commune": commune,
            "activite_principale": periode_actuelle.get("activitePrincipaleEtablissement"),
            "libelle_activite": self._get_naf_label(periode_actuelle.get("activitePrincipaleEtablissement")),
            "tranche_effectifs": tranche_effectifs,
            "effectifs_label": effectifs_label,
            "est_siege": etab.get("etablissementSiege", False),
            "est_actif": est_actif,
            "date_creation": etab.get("dateCreationEtablissement"),
            "categorie_entreprise": unite_legale.get("categorieEntreprise"),
            "idcc": idcc,  # Convention collective
        }

    def _get_effectifs_label(self, tranche: Optional[str]) -> str:
        """Convertit le code de tranche d'effectifs en libellé"""
        tranches = {
            "NN": "Non renseigné",
            "00": "0 salarié",
            "01": "1 ou 2 salariés",
            "02": "3 à 5 salariés",
            "03": "6 à 9 salariés",
            "11": "10 à 19 salariés",
            "12": "20 à 49 salariés",
            "21": "50 à 99 salariés",
            "22": "100 à 199 salariés",
            "31": "200 à 249 salariés",
            "32": "250 à 499 salariés",
            "41": "500 à 999 salariés",
            "42": "1000 à 1999 salariés",
            "51": "2000 à 4999 salariés",
            "52": "5000 à 9999 salariés",
            "53": "10000 salariés et plus",
        }
        return tranches.get(tranche, "Non renseigné")

    def _get_naf_label(self, code_naf: Optional[str]) -> str:
        """
        Retourne un libellé simplifié pour les codes NAF les plus courants
        Pour une version complète, il faudrait une table de référence
        """
        if not code_naf:
            return "Non renseigné"

        # Mapping partiel des codes NAF les plus courants
        # Pour une version complète, voir: https://www.insee.fr/fr/information/2406147
        naf_mapping = {
            "47.11": "Commerce de détail en magasin non spécialisé",
            "56.10": "Restaurants et services de restauration mobile",
            "68.20": "Location et exploitation de biens immobiliers propres",
            "70.10": "Activités des sièges sociaux",
            "84.11": "Administration publique générale",
            "85.20": "Enseignement primaire",
            "86.10": "Activités hospitalières",
            "87.10": "Hébergement médicalisé",
        }

        return naf_mapping.get(code_naf[:5], f"Code NAF: {code_naf}")


# Instance par défaut sans clé API (limite: 30 req/min)
sirene_api = SireneAPI()


async def enrichir_siret(siret: str) -> Optional[Dict[str, Any]]:
    """
    Fonction helper pour enrichir un SIRET

    Args:
        siret: Numéro SIRET

    Returns:
        Dictionnaire avec les infos enrichies ou None
    """
    try:
        return await sirene_api.get_siret(siret)
    except SireneAPIError as e:
        logger.error(f"Erreur enrichissement SIRET {siret}: {e}")
        return None


async def rechercher_siret(
    denomination: str,
    code_postal: Optional[str] = None,
    commune: Optional[str] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Helper pour rechercher des établissements via l'API Sirene."""

    try:
        return await sirene_api.search_siret(denomination, code_postal, commune, limit)
    except SireneAPIError as e:
        logger.error(
            "Erreur recherche Sirene pour %s / CP:%s / %s: %s",
            denomination,
            code_postal,
            commune,
            e,
        )
        raise
