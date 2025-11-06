"""
Service de calcul du nombre d'élus CSE par organisation syndicale.

Basé sur :
- Le barème légal du Code du travail (Article R2314-1)
- La méthode de répartition proportionnelle en 2 étapes (Articles R2314-19 et R2314-20) :
  1. Quotient électoral (R2314-19)
  2. Plus forte moyenne (R2314-20) pour les sièges restants
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
    elif effectif < 300:
        return 11
    elif effectif < 400:
        return 11
    elif effectif < 500:
        return 12
    elif effectif < 600:
        return 13
    elif effectif < 700:
        return 14
    elif effectif < 800:
        return 14
    elif effectif < 900:
        return 15
    elif effectif < 1000:
        return 16
    elif effectif < 1250:
        return 17
    elif effectif < 1500:
        return 18
    elif effectif < 1750:
        return 20
    elif effectif < 2000:
        return 21
    elif effectif < 2250:
        return 22
    elif effectif < 2500:
        return 23
    elif effectif < 3000:
        return 24
    elif effectif < 3500:
        return 25
    elif effectif < 4000:
        return 26
    elif effectif < 4250:
        return 26
    elif effectif < 4750:
        return 27
    elif effectif < 5000:
        return 28
    elif effectif < 5750:
        return 29
    elif effectif < 6000:
        return 30
    elif effectif < 7000:
        return 31
    elif effectif < 8250:
        return 32
    elif effectif < 9000:
        return 33
    elif effectif < 10000:
        return 34
    else:  # 10000+
        return 35


def repartir_sieges_quotient_puis_plus_forte_moyenne(
    voix_par_orga: Dict[str, int],
    nb_sieges_total: int
) -> Dict[str, int]:
    """
    Répartit les sièges selon la méthode légale française (R2314-19 et R2314-20) :
    ÉTAPE 1 : Quotient électoral (R2314-19)
    ÉTAPE 2 : Plus forte moyenne (R2314-20) pour les sièges restants

    Algorithme :
    Étape 1 - Quotient électoral :
        - Quotient = Total des voix / Nombre de sièges
        - Chaque orga reçoit ⌊ses voix / quotient⌋ sièges (partie entière)

    Étape 2 - Plus forte moyenne (pour les sièges restants) :
        - Pour chaque orga : moyenne = voix / (sièges_déjà_attribués + 1)
        - Attribuer le siège à l'orga avec la plus forte moyenne
        - Répéter jusqu'à épuisement des sièges

    Args:
        voix_par_orga: Dictionnaire {nom_organisation: nombre_de_voix}
        nb_sieges_total: Nombre total de sièges à répartir

    Returns:
        Dictionnaire {nom_organisation: nombre_de_sieges_attribues}

    Examples:
        >>> repartir_sieges_quotient_puis_plus_forte_moyenne(
        ...     {"A": 500, "B": 270, "C": 120, "D": 110},
        ...     7
        ... )
        {'A': 4, 'B': 2, 'C': 1, 'D': 0}

        # Détail : Quotient=142,86 → A:3, B:1, C:0, D:0 (4 sièges)
        # Restent 3 → B(135), A(125), C(120) → Final: A:4, B:2, C:1
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

    # Calculer le total des voix
    total_voix = sum(voix_par_orga[orga] for orga in sieges.keys())

    if total_voix == 0 or nb_sieges_total == 0:
        return sieges

    # ÉTAPE 1 : Attribution par quotient électoral (R2314-19)
    quotient_electoral = total_voix / nb_sieges_total

    sieges_attribues = 0
    for orga in sieges.keys():
        voix = voix_par_orga[orga]
        # Partie entière : nombre de fois que le quotient entre dans les voix
        nb_sieges_quotient = int(voix / quotient_electoral)
        sieges[orga] = nb_sieges_quotient
        sieges_attribues += nb_sieges_quotient

    # ÉTAPE 2 : Sièges restants par plus forte moyenne (R2314-20)
    sieges_restants = nb_sieges_total - sieges_attribues

    for _ in range(sieges_restants):
        # Calculer la moyenne de chaque organisation
        moyennes = {}
        for orga in sieges.keys():
            voix = voix_par_orga[orga]
            moyennes[orga] = voix / (sieges[orga] + 1)

        # Attribuer le siège à l'organisation avec la plus forte moyenne
        if moyennes:
            orga_gagnante = max(moyennes, key=moyennes.get)
            sieges[orga_gagnante] += 1

    return sieges


def repartir_sieges_quotient_seul(
    voix_par_orga: Dict[str, int],
    nb_sieges_total: int
) -> Dict[str, int]:
    """
    Répartit les sièges UNIQUEMENT par quotient électoral (sans plus forte moyenne).
    Méthode plus conservatrice qui reflète mieux la réalité quand les organisations
    ne présentent pas toujours de listes complètes.

    Cette méthode donne généralement moins de sièges que la "moyenne haute" car
    elle ne distribue pas les sièges restants. C'est plus proche de la réalité
    électorale.

    Algorithme :
        - Quotient = Total des voix / Nombre de sièges
        - Chaque orga reçoit ⌊ses voix / quotient⌋ sièges (partie entière)
        - Les sièges restants ne sont PAS attribués

    Args:
        voix_par_orga: Dictionnaire {nom_organisation: nombre_de_voix}
        nb_sieges_total: Nombre total de sièges à répartir

    Returns:
        Dictionnaire {nom_organisation: nombre_de_sieges_attribues}

    Examples:
        >>> repartir_sieges_quotient_seul(
        ...     {"CGT": 450, "CFDT": 300, "FO": 150},
        ...     19
        ... )
        {'CGT': 9, 'CFDT': 6, 'FO': 3}

        # Total voix: 900, Quotient: 900/19 = 47.37
        # CGT: 450/47.37 = 9.5 → 9 sièges
        # CFDT: 300/47.37 = 6.3 → 6 sièges
        # FO: 150/47.37 = 3.1 → 3 sièges
        # Total attribué: 18 sièges (1 siège non attribué)
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

    # Calculer le total des voix
    total_voix = sum(voix_par_orga[orga] for orga in sieges.keys())

    if total_voix == 0 or nb_sieges_total == 0:
        return sieges

    # Attribution par quotient électoral UNIQUEMENT
    quotient_electoral = total_voix / nb_sieges_total

    for orga in sieges.keys():
        voix = voix_par_orga[orga]
        # Partie entière : nombre de fois que le quotient entre dans les voix
        nb_sieges_quotient = int(voix / quotient_electoral)
        sieges[orga] = nb_sieges_quotient

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

    # Répartir les sièges avec QUOTIENT SEUL (méthode plus réaliste)
    # Cette méthode est plus conservatrice car elle ne suppose pas que toutes
    # les organisations présentent des listes complètes
    elus_par_orga = repartir_sieges_quotient_seul(
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
