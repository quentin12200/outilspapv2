# Calcul du nombre d'élus CSE par syndicat

## 📋 Todo Liste

### Phase 1 : Recherche et analyse
- [x] Créer nouvelle branche `claude/calcul-elus-cse-011CUpHWrkFHCrEedJYqZmiw`
- [ ] Rechercher le barème légal du nombre d'élus CSE selon l'effectif
- [ ] Comprendre la méthode de répartition proportionnelle (plus forte moyenne)
- [ ] Identifier les données disponibles dans la base de données

### Phase 2 : Implémentation du calcul
- [ ] Créer une fonction Python `calculer_nombre_elus_cse(effectif)`
- [ ] Créer une fonction `repartir_sieges_proportionnelle(voix_par_orga, nb_sieges)`
- [ ] Ajouter les colonnes d'élus calculés dans les résultats

### Phase 3 : Intégration dans l'application
- [ ] Ajouter le calcul dans la route `/calendrier`
- [ ] Afficher les élus par syndicat dans le tableau
- [ ] Ajouter les élus dans l'export Excel
- [ ] Créer un endpoint API `/api/calcul-elus` pour tests

### Phase 4 : Tests et validation
- [ ] Tester avec des cas réels de la base de données
- [ ] Valider la cohérence des résultats
- [ ] Comparer avec des résultats connus si disponibles
- [ ] Documenter les cas limites et hypothèses

---

## 🔍 Barème légal - Nombre d'élus titulaires CSE

Selon le Code du travail (Article L2314-1 et R2314-1), le nombre de membres titulaires du CSE dépend de l'effectif de l'entreprise :

| Effectif de l'entreprise | Nombre de titulaires |
|--------------------------|---------------------|
| 11 à 24 salariés         | 1                   |
| 25 à 49 salariés         | 2                   |
| 50 à 74 salariés         | 4                   |
| 75 à 99 salariés         | 5                   |
| 100 à 124 salariés       | 6                   |
| 125 à 149 salariés       | 7                   |
| 150 à 174 salariés       | 8                   |
| 175 à 199 salariés       | 9                   |
| 200 à 249 salariés       | 10                  |
| 250 à 399 salariés       | 11                  |
| 400 à 499 salariés       | 12                  |
| 500 à 749 salariés       | 13                  |
| 750 à 999 salariés       | 14                  |
| 1000 à 1249 salariés     | 15                  |
| 1250 à 1499 salariés     | 17                  |
| 1500 à 1749 salariés     | 19                  |
| 1750 à 1999 salariés     | 21                  |
| 2000 à 2249 salariés     | 23                  |
| 2250 à 2499 salariés     | 24                  |
| 2500 à 2749 salariés     | 25                  |
| 2750 à 2999 salariés     | 26                  |
| 3000 à 3749 salariés     | 27                  |
| 3750 à 4499 salariés     | 29                  |
| 4500 à 5249 salariés     | 30                  |
| 5250 à 5999 salariés     | 31                  |
| 6000 à 6749 salariés     | 32                  |
| 6750 à 7499 salariés     | 33                  |
| 7500 à 9999 salariés     | 34                  |
| 10000 salariés et plus   | 35                  |

**Note :** Pour les entreprises < 11 salariés, il n'y a pas de CSE obligatoire.

---

## 🧮 Méthode de répartition des sièges : Plus forte moyenne

### Principe

La répartition des sièges entre les organisations syndicales se fait selon la **méthode de la plus forte moyenne** (aussi appelée méthode d'Hondt).

### Algorithme

1. **Calculer le quotient de chaque organisation**
   - Pour chaque organisation, diviser le nombre de voix par (nombre de sièges déjà attribués + 1)

2. **Attribuer un siège**
   - Le siège est attribué à l'organisation ayant le quotient le plus élevé

3. **Répéter**
   - Recalculer les quotients et attribuer le siège suivant
   - Continuer jusqu'à ce que tous les sièges soient attribués

### Exemple concret

**Entreprise de 1500 salariés → 19 sièges titulaires**

Résultats du 1er tour :
- CGT : 450 voix (45%)
- CFDT : 300 voix (30%)
- FO : 150 voix (15%)
- UNSA : 100 voix (10%)

**Calcul étape par étape :**

| Étape | CGT quotient | CFDT quotient | FO quotient | UNSA quotient | Attribution | Sièges |
|-------|-------------|---------------|-------------|---------------|-------------|--------|
| 1 | 450/1=450 | 300/1=300 | 150/1=150 | 100/1=100 | CGT | CGT:1 |
| 2 | 450/2=225 | 300/1=300 | 150/1=150 | 100/1=100 | CFDT | CGT:1, CFDT:1 |
| 3 | 450/2=225 | 300/2=150 | 150/1=150 | 100/1=100 | CGT | CGT:2, CFDT:1 |
| 4 | 450/3=150 | 300/2=150 | 150/1=150 | 100/1=100 | CGT (ex-aequo) | CGT:3, CFDT:1 |
| ... | ... | ... | ... | ... | ... | ... |

**Résultat final (19 sièges) :**
- CGT : 9 élus (47%)
- CFDT : 6 élus (32%)
- FO : 3 élus (16%)
- UNSA : 1 élu (5%)

---

## 💾 Données disponibles dans la base

Pour calculer le nombre d'élus, nous avons besoin de :

### Dans `PVEvent` :
- ✅ `effectif_siret` ou `inscrits` → effectif de l'entreprise
- ✅ `sve` → suffrages valablement exprimés (base de calcul)
- ✅ `cgt_voix`, `cfdt_voix`, `fo_voix`, etc. → voix par organisation

### Données manquantes :
- ❌ Distinction 1er tour / 2ème tour (les accords d'entreprise peuvent prévoir un 2nd tour)
- ❌ Seuil de représentativité (10% des suffrages au 1er tour)

### Hypothèses à faire :
1. On calcule sur la base des voix du PV (tour le plus récent)
2. On ne prend que les organisations ayant obtenu des voix
3. On utilise le SVE comme dénominateur

---

## 🔧 Implémentation Python

### Fonction 1 : Déterminer le nombre de sièges

```python
def calculer_nombre_elus_cse(effectif: int) -> int:
    """
    Retourne le nombre de membres titulaires du CSE selon l'effectif.
    Basé sur le barème légal (Code du travail R2314-1).
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
```

### Fonction 2 : Répartition proportionnelle (plus forte moyenne)

```python
def repartir_sieges_plus_forte_moyenne(
    voix_par_orga: dict[str, int],
    nb_sieges_total: int
) -> dict[str, int]:
    """
    Répartit les sièges entre organisations selon la méthode de la plus forte moyenne.

    Args:
        voix_par_orga: Dictionnaire {nom_orga: nombre_de_voix}
        nb_sieges_total: Nombre total de sièges à répartir

    Returns:
        Dictionnaire {nom_orga: nombre_de_sieges}
    """
    # Initialiser les sièges à 0 pour chaque organisation
    sieges = {orga: 0 for orga in voix_par_orga.keys() if voix_par_orga[orga] > 0}

    # Si aucune voix, retourner vide
    if not sieges:
        return {}

    # Attribuer les sièges un par un
    for _ in range(nb_sieges_total):
        # Calculer le quotient de chaque organisation
        quotients = {}
        for orga, voix in voix_par_orga.items():
            if voix > 0:
                quotients[orga] = voix / (sieges[orga] + 1)

        # Attribuer le siège à l'organisation avec le plus fort quotient
        if quotients:
            orga_gagnante = max(quotients, key=quotients.get)
            sieges[orga_gagnante] += 1

    return sieges
```

---

## 📊 Colonnes à ajouter dans l'affichage

### Dans le tableau calendrier :
- **Nb sièges CSE** : Nombre total de sièges calculé selon l'effectif
- **CGT élus** : Nombre d'élus CGT
- **CFDT élus** : Nombre d'élus CFDT
- **FO élus** : Nombre d'élus FO
- **Autres orgas élus** : Autres syndicats

### Dans l'export Excel :
Ajouter après les colonnes existantes :
- Colonne "Nb sièges CSE total"
- Colonnes par organisation : "CGT - Élus", "CFDT - Élus", "FO - Élus", etc.

---

## ⚠️ Cas limites et hypothèses

### Cas à gérer :
1. **Effectif inconnu** : Ne pas calculer, afficher "N/A"
2. **SVE = 0 ou NULL** : Ne pas calculer
3. **Aucune voix** : 0 élus pour tous
4. **Plusieurs PV pour un même SIRET** : Prendre le PV le plus récent
5. **2ème tour** : On ne peut pas le détecter, on calcule avec les données disponibles

### Hypothèses :
- ✅ On calcule uniquement les **titulaires** (pas les suppléants)
- ✅ On utilise le barème légal minimum (certaines entreprises peuvent avoir plus de sièges par accord)
- ✅ On ne prend pas en compte le quorum et les seuils de représentativité
- ✅ On considère que les données du PV reflètent le résultat final

---

## 🎯 Résultat attendu

Pour chaque élection dans le calendrier +1000, afficher :

**Exemple :**
```
SIRET: 12345678901234
Raison sociale: Entreprise XYZ
Effectif: 1500 → 19 sièges CSE

Résultats élections :
- CGT : 450 voix (45%) → 9 élus
- CFDT : 300 voix (30%) → 6 élus
- FO : 150 voix (15%) → 3 élus
- UNSA : 100 voix (10%) → 1 élu
```

---

## 📝 Prochaines étapes

1. ✅ Créer la branche et la todo liste
2. ⏳ Implémenter les fonctions de calcul
3. ⏳ Intégrer dans la route `/calendrier`
4. ⏳ Ajouter l'affichage dans le template
5. ⏳ Ajouter dans l'export Excel
6. ⏳ Tester avec des données réelles
7. ⏳ Valider et documenter

---

**Date de création :** 2025-11-05
**Branche :** claude/calcul-elus-cse-011CUpHWrkFHCrEedJYqZmiw
**Statut :** En cours - Phase de recherche
