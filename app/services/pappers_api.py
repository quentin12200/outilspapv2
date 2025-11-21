"""
Service d'intégration avec l'API Pappers (https://www.pappers.fr/)
Documentation: https://www.pappers.fr/api/documentation
"""

import os
import httpx
import asyncio
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# URL de base de l'API Pappers
PAPPERS_API_BASE = "https://api.pappers.fr/v2"

# Timeout pour les requêtes (secondes)
REQUEST_TIMEOUT = 10.0

class PappersAPIError(Exception):
    """Exception levée en cas d'erreur avec l'API Pappers"""
    pass

class PappersAPI:
    """Client pour l'API Pappers"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialise le client API Pappers

        Args:
            api_key: Clé API Pappers. Si None, cherche dans les variables d'environnement.
        """
        self.api_key = api_key or os.getenv("PAPPERS_API_KEY")
        
        if not self.api_key:
            logger.warning("[PAPPERS API] ⚠️ NO API KEY configured")
        else:
            logger.info(f"[PAPPERS API] API Key configured: {self.api_key[:5]}...")

    async def get_siret(self, siret: str) -> Optional[Dict[str, Any]]:
        """
        Récupère les informations d'un établissement par son SIRET via Pappers

        Args:
            siret: Numéro SIRET (14 chiffres)

        Returns:
            Dictionnaire avec les infos de l'établissement ou None si non trouvé
        """
        if not self.api_key:
            logger.error("[PAPPERS API] Tentative d'appel sans clé API")
            return None

        siret_clean = siret.strip().replace(" ", "")
        if len(siret_clean) != 14 or not siret_clean.isdigit():
            logger.warning(f"SIRET invalide: {siret}")
            return None

        url = f"{PAPPERS_API_BASE}/entreprise"
        params = {
            "api_token": self.api_key,
            "siret": siret_clean
        }

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.get(url, params=params)

                if response.status_code == 200:
                    data = response.json()
                    # Pappers retourne l'entreprise complète, il faut extraire l'établissement
                    etablissement = next(
                        (e for e in data.get("etablissements", []) if e.get("siret") == siret_clean),
                        None
                    )
                    if etablissement:
                        return self._parse_etablissement(etablissement, data)
                    return None
                elif response.status_code == 404:
                    logger.info(f"SIRET non trouvé (Pappers): {siret_clean}")
                    return None
                else:
                    logger.error(f"Erreur API Pappers pour SIRET {siret_clean} ({response.status_code}): {response.text[:200]}")
                    raise PappersAPIError(f"Erreur API Pappers (code {response.status_code})")

        except httpx.RequestError as e:
            logger.error(f"Erreur réseau API Pappers pour SIRET {siret_clean}: {e}")
            raise PappersAPIError(f"Erreur de connexion à l'API Pappers: {type(e).__name__}")

    async def search_siret(
        self,
        q: str,
        code_postal: Optional[str] = None,
        commune: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Recherche des établissements via Pappers
        """
        if not self.api_key:
            return []

        url = f"{PAPPERS_API_BASE}/recherche"
        params = {
            "api_token": self.api_key,
            "q": q,
            "par_page": limit,
            "bases": "entreprises" # On cherche dans la base entreprises
        }
        
        if code_postal:
            params["code_postal"] = code_postal
        if commune:
            params["ville"] = commune

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.get(url, params=params)

                if response.status_code == 200:
                    data = response.json()
                    results = data.get("resultats", [])
                    # Pappers retourne des entreprises ou établissements selon la recherche
                    # On essaie de normaliser
                    parsed_results = []
                    for res in results:
                        # Si c'est un établissement (souvent le cas si recherche précise)
                        # Sinon on prend le siège
                        etab = res
                        # Adaptation selon la structure de réponse de Pappers (qui peut varier)
                        # Pour la recherche, Pappers retourne une liste d'entreprises avec un établissement représentatif souvent
                        
                        parsed = self._parse_search_result(res)
                        parsed_results.append(parsed)
                        
                    return parsed_results[:limit]
                else:
                    logger.error(f"Erreur recherche Pappers ({response.status_code}): {response.text[:200]}")
                    return []

        except httpx.RequestError as e:
            logger.error(f"Erreur réseau recherche Pappers: {e}")
            return []

    def _parse_etablissement(self, etab: Dict[str, Any], entreprise: Dict[str, Any]) -> Dict[str, Any]:
        """
        Adapte le format Pappers au format attendu par l'application (similaire à SireneAPI)
        """
        adresse_ligne_1 = etab.get("adresse_ligne_1", "")
        adresse_ligne_2 = etab.get("adresse_ligne_2", "")
        adresse_complete = f"{adresse_ligne_1} {adresse_ligne_2}".strip()

        # Convention collective (Pappers donne souvent une liste)
        cc_list = entreprise.get("convention_collective_principale", {})
        idcc = None
        if cc_list:
             # Parfois c'est un dict, parfois une liste, on gère le cas simple
             if isinstance(cc_list, dict):
                 idcc = str(cc_list.get("idcc", ""))
        
        if not idcc and entreprise.get("conventions_collectives"):
             # Prendre la première
             first_cc = entreprise["conventions_collectives"][0]
             idcc = str(first_cc.get("idcc", ""))

        return {
            "siret": etab.get("siret"),
            "siren": entreprise.get("siren"),
            "denomination": entreprise.get("nom_entreprise") or f"{entreprise.get('prenom', '')} {entreprise.get('nom', '')}".strip(),
            "enseigne": etab.get("enseigne"),
            "adresse": adresse_complete,
            "code_postal": etab.get("code_postal"),
            "commune": etab.get("ville"),
            "activite_principale": etab.get("code_naf"),
            "libelle_activite": etab.get("libelle_code_naf"),
            "tranche_effectifs": entreprise.get("tranche_effectif"), # Pappers donne ça au niveau entreprise souvent
            "effectifs_label": entreprise.get("effectif_libelle"), # Ou à calculer
            "est_siege": etab.get("siege", False),
            "est_actif": not (etab.get("etablissement_cesse", False) or entreprise.get("entreprise_cessee", False)),
            "date_creation": etab.get("date_creation"),
            "categorie_entreprise": entreprise.get("categorie_entreprise"),
            "idcc": idcc,
            "source": "Pappers",
            "latitude": etab.get("latitude"),
            "longitude": etab.get("longitude")
        }

    def _parse_search_result(self, res: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse un résultat de recherche Pappers
        """
        # La structure de recherche est un peu différente
        # Pour la recherche, les coordonnées sont souvent dans le siège
        siege = res.get("siege", {})
        return {
            "siret": siege.get("siret") if siege else res.get("siret"), # Fallback
            "siren": res.get("siren"),
            "denomination": res.get("nom_entreprise"),
            "adresse": f"{siege.get('adresse_ligne_1', '')} {siege.get('adresse_ligne_2', '')}".strip(),
            "code_postal": siege.get("code_postal"),
            "commune": siege.get("ville"),
            "activite_principale": res.get("code_naf"),
            "libelle_activite": res.get("libelle_code_naf"),
            "est_siege": True, # Dans la recherche on a souvent l'entreprise/siège
            "est_actif": not res.get("entreprise_cessee", False),
            "latitude": siege.get("latitude"),
            "longitude": siege.get("longitude")
        }

# Instance par défaut
pappers_api = PappersAPI()
