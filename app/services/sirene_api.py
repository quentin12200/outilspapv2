"""
Service d'intégration avec l'API Sirene (INSEE)
Documentation: https://www.data.gouv.fr/dataservices/api-sirene-open-data/
"""

import httpx
from typing import Optional, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# URL de base de l'API Sirene
SIRENE_API_BASE = "https://api.insee.fr/entreprises/sirene/V3"

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
        self.api_key = api_key
        self.headers = {
            "Accept": "application/json"
        }
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"

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
