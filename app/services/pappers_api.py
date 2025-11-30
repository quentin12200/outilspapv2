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

    async def get_etablissements_by_siren(self, siren: str) -> Dict[str, Any]:
        """
        Récupère tous les établissements d'une entreprise par son SIREN via Pappers

        Args:
            siren: Numéro SIREN (9 chiffres)

        Returns:
            Dictionnaire avec les infos de l'entreprise et la liste de ses établissements
        """
        if not self.api_key:
            logger.error("[PAPPERS API] Tentative d'appel sans clé API")
            return {"success": False, "error": "API key manquante"}

        siren_clean = siren.strip().replace(" ", "")
        if len(siren_clean) != 9 or not siren_clean.isdigit():
            logger.warning(f"SIREN invalide: {siren}")
            return {"success": False, "error": "SIREN invalide"}

        url = f"{PAPPERS_API_BASE}/entreprise"
        params = {
            "api_token": self.api_key,
            "siren": siren_clean
        }

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.get(url, params=params)

                if response.status_code == 200:
                    data = response.json()
                    etablissements_data = data.get("etablissements", [])

                    # Parser tous les établissements
                    etablissements_parsed = []
                    for etab in etablissements_data:
                        parsed = self._parse_etablissement(etab, data)
                        etablissements_parsed.append(parsed)

                    siege = data.get("siege", {}) or {}
                    siege_adresse = " ".join(
                        part
                        for part in [
                            siege.get("adresse_ligne_1", ""),
                            siege.get("adresse_ligne_2", ""),
                            ("%s %s" % (siege.get("code_postal", ""), siege.get("ville", ""))).strip(),
                        ]
                        if part
                    ).strip()

                    entreprise_payload = {
                        "siren": data.get("siren"),
                        "nom": data.get("nom_entreprise"),
                        "siege": siege,
                        "siege_adresse": siege_adresse,
                        "categorie_entreprise": data.get("categorie_entreprise"),
                        "forme_juridique": data.get("forme_juridique"),
                        "activite_principale": data.get("code_naf"),
                        "libelle_activite": data.get("libelle_code_naf"),
                        "code_naf": data.get("code_naf"),
                        "libelle_code_naf": data.get("libelle_code_naf"),
                        "tranche_effectif": data.get("tranche_effectif"),
                        "effectif": data.get("effectif"),
                        "effectif_libelle": data.get("effectif_libelle") or data.get("effectif"),
                        "effectif_annee": data.get("effectif_annee"),
                        "date_creation": data.get("date_creation"),
                        "capital": data.get("capital"),
                        "idcc": self._extract_idcc(data),
                        "numero_tva_intracommunautaire": data.get("numero_tva_intracommunautaire"),
                        "convention_collective_renseignee": self._extract_idcc(data),
                        "libelle_convention_collective": self._extract_convention_libelle(data),
                        "representants": data.get("representants", []),
                        "entreprise_cessee": data.get("entreprise_cessee", False),
                        "date_cessation": data.get("date_cessation"),
                        "procedure_collective": data.get("procedure_collective", False),
                        "derniere_mise_a_jour": data.get("date_derniere_mise_a_jour")
                    }

                    return {
                        "success": True,
                        "entreprise": entreprise_payload,
                        "etablissements": etablissements_parsed,
                        "total": len(etablissements_parsed)
                    }
                elif response.status_code == 404:
                    logger.info(f"SIREN non trouvé (Pappers): {siren_clean}")
                    return {"success": False, "error": "SIREN non trouvé"}
                else:
                    logger.error(f"Erreur API Pappers pour SIREN {siren_clean} ({response.status_code}): {response.text[:200]}")
                    return {"success": False, "error": f"Erreur API (code {response.status_code})"}

        except httpx.RequestError as e:
            logger.error(f"Erreur réseau API Pappers pour SIREN {siren_clean}: {e}")
            return {"success": False, "error": f"Erreur de connexion: {type(e).__name__}"}

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

        idcc = self._extract_idcc(entreprise)

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
            "forme_juridique": entreprise.get("forme_juridique"),
            "est_siege": etab.get("siege", False),
            "est_actif": not (etab.get("etablissement_cesse", False) or entreprise.get("entreprise_cessee", False)),
            "date_creation": etab.get("date_creation"),
            "categorie_entreprise": entreprise.get("categorie_entreprise"),
            "idcc": idcc,
            "source": "Pappers",
            "latitude": etab.get("latitude"),
            "longitude": etab.get("longitude")
        }

    @staticmethod
    def _extract_idcc(entreprise: Dict[str, Any]) -> Optional[str]:
        """Extrait l'IDCC depuis la réponse Pappers (dict ou liste)."""

        cc_list = entreprise.get("convention_collective_principale", {})
        if cc_list and isinstance(cc_list, dict):
            idcc = str(cc_list.get("idcc", "")).strip()
            if idcc:
                return idcc

        conventions = entreprise.get("conventions_collectives") or []
        if isinstance(conventions, list) and conventions:
            first_cc = conventions[0] or {}
            idcc = str(first_cc.get("idcc", "")).strip()
            if idcc:
                return idcc

        return None

    @staticmethod
    def _extract_convention_libelle(entreprise: Dict[str, Any]) -> Optional[str]:
        """Extrait le libellé de la convention collective depuis la réponse Pappers."""

        cc_list = entreprise.get("convention_collective_principale", {})
        if cc_list and isinstance(cc_list, dict):
            libelle = cc_list.get("nom", "") or cc_list.get("libelle", "")
            if libelle:
                return libelle.strip()

        conventions = entreprise.get("conventions_collectives") or []
        if isinstance(conventions, list) and conventions:
            first_cc = conventions[0] or {}
            libelle = first_cc.get("nom", "") or first_cc.get("libelle", "")
            if libelle:
                return libelle.strip()

        return None

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


async def get_entreprise_etablissements(siren: str) -> List[Dict[str, Any]]:
    """
    Récupère tous les établissements d'une entreprise via son SIREN
    avec leurs coordonnées GPS (latitude/longitude).

    Args:
        siren: Numéro SIREN de l'entreprise (9 chiffres)

    Returns:
        Liste des établissements avec leurs données Pappers (incluant coordonnées GPS)
    """
    try:
        # Récupérer l'entreprise complète avec tous ses établissements
        entreprise_data = await pappers_api.get_siren(siren)

        if not entreprise_data:
            logger.warning(f"Entreprise {siren} non trouvée via Pappers")
            return []

        # Extraire les établissements
        etablissements = []

        # L'API Pappers retourne les établissements dans "etablissements"
        etabs_list = entreprise_data.get("etablissements", [])

        for etab in etabs_list:
            etablissements.append({
                "siret": etab.get("siret"),
                "siren": siren,
                "nom_complet": etab.get("nom_entreprise") or entreprise_data.get("nom_entreprise"),
                "enseigne": etab.get("enseigne"),
                "adresse_complete": (
                    f"{etab.get('adresse_ligne_1', '')} "
                    f"{etab.get('adresse_ligne_2', '')} "
                    f"{etab.get('code_postal', '')} "
                    f"{etab.get('ville', '')}"
                ).strip(),
                "adresse_ligne_1": etab.get("adresse_ligne_1"),
                "adresse_ligne_2": etab.get("adresse_ligne_2"),
                "code_postal": etab.get("code_postal"),
                "commune": etab.get("ville"),
                "code_naf": etab.get("code_naf"),
                "libelle_code_naf": etab.get("libelle_code_naf"),
                "est_siege": etab.get("est_siege", False),
                "est_actif": not etab.get("etablissement_cesse", False),
                "date_creation": etab.get("date_creation"),
                "date_cessation": etab.get("date_cessation"),
                "effectif": etab.get("effectif"),
                "tranche_effectif": etab.get("tranche_effectif"),
                "latitude": etab.get("latitude"),
                "longitude": etab.get("longitude"),
                "forme_juridique": entreprise_data.get("forme_juridique"),
                "categorie_entreprise": entreprise_data.get("categorie_entreprise"),
            })

        logger.info(f"✅ {len(etablissements)} établissements trouvés pour SIREN {siren} via Pappers")
        return etablissements

    except Exception as e:
        logger.error(f"Erreur lors de la récupération des établissements pour SIREN {siren}: {e}")
        return []
