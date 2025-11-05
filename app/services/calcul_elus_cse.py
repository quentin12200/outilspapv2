"""
Service de calcul du nombre d'élus CSE par organisation syndicale.

Basé sur :
- Le barème légal du Code du travail (Article R2314-1)
- La méthode de répartition proportionnelle "plus forte moyenne" (méthode d'Hondt)
"""

from typing import Dict, Any


def calculer_nombre_elus_cse(effectif: int) -> int:
    """
    Retourne le nombre de membres titulaires du CSE selon l'effectif de l'entreprise.

    Basé sur le barème légal du Code du travail (Article R2314-1).

    Args:
        effectif: Nombre de salariés de l'entreprise

    Returns:
        Nombre de sièges de titulaires au CSE

    Examples:
        >>> calculer_nombre_elus_cse(50)
        4
        >>> calculer_nombre_elus_cse(1500)
        19
        >>> calculer_nombre_elus_cse(10)
        0
    """
    if effectif < 11:
        return 0
    elif effectif < 25:
        return 1
    elif effectif < 50:
        return 2
    elif effectif < 75:
        return 4
    elif effectif < 100:
        return 5
    elif effectif < 125:
        return 6
    elif effectif < 150:
        return 7
    elif effectif < 175:
        return 8
    elif effectif < 200:
        return 9
    elif effectif < 250:
        return 10
    elif effectif < 400:
        return 11
    elif effectif < 500:
        return 12
    elif effectif < 750:
        return 13
    elif effectif < 1000:
        return 14
    elif effectif < 1250:
        return 15
    elif effectif < 1500:
        return 17
    elif effectif < 1750:
        return 19
    elif effectif < 2000:
        return 21
    elif effectif < 2250:
        return 23
    elif effectif < 2500:
        return 24
    elif effectif < 2750:
        return 25
    elif effectif < 3000:
        return 26
    elif effectif < 3750:
        return 27
    elif effectif < 4500:
        return 29
    elif effectif < 5250:
        return 30
    elif effectif < 6000:
        return 31
    elif effectif < 6750:
        return 32
    elif effectif < 7500:
        return 33
    elif effectif < 10000:
        return 34
    else:
        return 35


def repartir_sieges_plus_forte_moyenne(
    voix_par_orga: Dict[str, int],
    nb_sieges_total: int
) -> Dict[str, int]:
    """
    Répartit les sièges entre organisations selon la méthode de la plus forte moyenne.

    Aussi appelée méthode d'Hondt, cette méthode est utilisée pour la répartition
    proportionnelle des sièges au CSE selon les résultats électoraux.

    Algorithme :
    1. Pour chaque organisation, calculer : voix / (sièges_déjà_attribués + 1)
    2. Attribuer un siège à l'organisation ayant le quotient le plus élevé
    3. Répéter jusqu'à épuisement des sièges

    Args:
        voix_par_orga: Dictionnaire {nom_organisation: nombre_de_voix}
        nb_sieges_total: Nombre total de sièges à répartir

    Returns:
        Dictionnaire {nom_organisation: nombre_de_sieges_attribues}

    Examples:
        >>> repartir_sieges_plus_forte_moyenne(
        ...     {"CGT": 450, "CFDT": 300, "FO": 150, "UNSA": 100},
        ...     19
        ... )
        {'CGT': 9, 'CFDT': 6, 'FO': 3, 'UNSA': 1}
    """
    # Filtrer les organisations sans voix et initialiser les sièges à 0
    sieges = {
        orga: 0
        for orga, voix in voix_par_orga.items()
        if voix and voix > 0
    }

    # Si aucune organisation n'a de voix, retourner vide
    if not sieges:
        return {}

    # Attribuer les sièges un par un
    for _ in range(nb_sieges_total):
        # Calculer le quotient de chaque organisation
        quotients = {}
        for orga in sieges.keys():
            voix = voix_par_orga[orga]
            quotients[orga] = voix / (sieges[orga] + 1)

        # Attribuer le siège à l'organisation avec le plus fort quotient
        if quotients:
            orga_gagnante = max(quotients, key=quotients.get)
            sieges[orga_gagnante] += 1

    return sieges


def calculer_elus_cse_complet(
    effectif: int,
    voix_par_orga: Dict[str, int]
) -> Dict[str, Any]:
    """
    Calcule le nombre d'élus CSE complet : nombre de sièges et répartition.

    Args:
        effectif: Effectif de l'entreprise
        voix_par_orga: Dictionnaire {nom_orga: voix}

    Returns:
        Dictionnaire contenant :
        - nb_sieges_total: Nombre total de sièges CSE
        - elus_par_orga: Répartition des élus par organisation
        - total_voix: Total des voix exprimées

    Examples:
        >>> calculer_elus_cse_complet(
        ...     1500,
        ...     {"CGT": 450, "CFDT": 300, "FO": 150}
        ... )
        {
            'nb_sieges_total': 19,
            'elus_par_orga': {'CGT': 9, 'CFDT': 6, 'FO': 4},
            'total_voix': 900
        }
    """
    # Calculer le nombre de sièges selon l'effectif
    nb_sieges_total = calculer_nombre_elus_cse(effectif)

    # Si pas de sièges, retourner vide
    if nb_sieges_total == 0:
        return {
            "nb_sieges_total": 0,
            "elus_par_orga": {},
            "total_voix": 0
        }

    # Calculer le total des voix
    total_voix = sum(v for v in voix_par_orga.values() if v and v > 0)

    # Si pas de voix, pas de répartition
    if total_voix == 0:
        return {
            "nb_sieges_total": nb_sieges_total,
            "elus_par_orga": {},
            "total_voix": 0
        }

    # Répartir les sièges
    elus_par_orga = repartir_sieges_plus_forte_moyenne(
        voix_par_orga,
        nb_sieges_total
    )

    return {
        "nb_sieges_total": nb_sieges_total,
        "elus_par_orga": elus_par_orga,
        "total_voix": total_voix
    }


# Mapping des noms de colonnes vers des noms affichables
ORGANISATIONS_LABELS = {
    "cgt_voix": "CGT",
    "cfdt_voix": "CFDT",
    "fo_voix": "FO",
    "cftc_voix": "CFTC",
    "cgc_voix": "CGC-CFE",
    "unsa_voix": "UNSA",
    "sud_voix": "SUD",
    "autre_voix": "Autres"
}
