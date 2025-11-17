# 🔧 Fix Critique: L'IDCC n'est PAS dans l'API INSEE Sirene !

**Date**: 2025-11-07
**Problème**: 0 IDCC trouvés sur 88 SIRETs traités
**Cause racine**: Utilisation de la mauvaise API

---

## ❌ Problème identifié

### Le code utilisait l'API INSEE Sirene pour récupérer l'IDCC

```python
# ❌ ANCIEN CODE (INCORRECT)
SIRENE_API_BASE = "https://api.insee.fr/api-sirene/3.11"
idcc = unite_legale.get("identifiantConventionCollectiveRenseignee")
```

**Résultat** : 0 IDCC trouvés car **l'API Sirene ne contient PAS les IDCC** !

---

## 💡 La vraie cause

### L'IDCC n'est PAS dans le registre Sirene

L'API Sirene de l'INSEE contient :
- ✅ SIREN/SIRET (identifiants)
- ✅ Dénomination, adresse
- ✅ Code NAF (activité)
- ✅ Effectifs, forme juridique
- ❌ **PAS d'IDCC** (convention collective)

### L'IDCC provient des DSN (Déclarations Sociales Nominatives)

L'IDCC est une donnée **sociale**, pas une donnée du registre des entreprises :
- Source : DSN (déclarations employeurs)
- Gestion : Ministère du Travail
- Base de données : KALI (DILA)

---

## ✅ Solution : Utiliser l'API Siret2IDCC

### Nouvelle API utilisée

```python
# ✅ NOUVEAU CODE (CORRECT)
SIRET2IDCC_API_BASE = "https://siret2idcc.fabrique.social.gouv.fr/api/v2"
```

### Format de réponse

```json
[
  {
    "siret": "82161143100015",
    "conventions": [
      {
        "active": true,
        "nature": "IDCC",
        "num": "1486",
        "title": "Convention collective des bureaux d'études techniques",
        "shortTitle": "Bureaux D'études Techniques",
        "etat": "VIGUEUR_ETEN",
        "url": "https://www.legifrance.gouv.fr/..."
      }
    ]
  }
]
```

### Extraction de l'IDCC

```python
conventions = siret_data.get("conventions", [])
for conv in conventions:
    if conv.get("active", False) and conv.get("nature") == "IDCC":
        idcc = conv.get("num")  # ✅ Le numéro IDCC
```

---

## 🔄 Modifications apportées

### Fichier modifié : `app/background_tasks.py`

#### Fonction `_get_siret_sync()`

**AVANT** :
- ❌ Utilisait l'API Sirene INSEE
- ❌ Cherchait `identifiantConventionCollectiveRenseignee`
- ❌ Trouvait toujours `None`

**APRÈS** :
- ✅ Utilise l'API Siret2IDCC
- ✅ Extrait `conventions[].num`
- ✅ Trouve les IDCC réels

### Changements de logs

**Avant** :
```
[SIRENE AUTH] Using API key: ...
Calling API SIRENE for SIRET ...
No IDCC for ... (API OK, but no IDCC in database)
```

**Après** :
```
Calling API Siret2IDCC for SIRET ...
IDCC found for ...: 1486
```

---

## 📊 Résultats attendus

### Avant (API Sirene)
```
88 SIRETs traités
0 IDCC trouvés (0%)
```

### Après (API Siret2IDCC)
```
88 SIRETs traités
~30-50 IDCC trouvés (35-55%)
```

**Note** : Toutes les entreprises n'ont pas d'IDCC (TPE, auto-entrepreneurs, associations), mais les grandes entreprises et franchises devraient en avoir.

---

## ⚠️ Note sur l'API Siret2IDCC

### État de l'API

L'API Siret2IDCC est **archivée depuis février 2024** mais reste **fonctionnelle**.

### Alternative recommandée

Le Ministère recommande d'utiliser **API Recherche-Entreprises** :
- URL : https://recherche-entreprises.api.gouv.fr
- Maintenue par DINUM
- Plus complète et à jour

### Migration future (optionnelle)

Si l'API Siret2IDCC cesse de fonctionner, migrer vers :

1. **API Recherche-Entreprises** (recommandé)
2. **Dataset data.gouv.fr** : https://www.data.gouv.fr/datasets/liste-des-conventions-collectives-par-entreprise-siret/

---

## 🧪 Tests

### Test avec SIRET connus

SIRETs qui **devraient** avoir un IDCC :
- `55210055400175` : Peugeot SA → IDCC Métallurgie
- `75330823807996` : ACTION → IDCC Commerce
- `54204452401063` : NATIXIS → IDCC Banque

SIRETs qui **peuvent ne pas avoir** d'IDCC :
- Associations
- Auto-entrepreneurs
- TPE sans salariés

### Vérifier les logs

Après déploiement, les logs devraient montrer :
```
✓ IDCC found for 75330823807996: 2216
✓ IDCC found for 54204452401063: 2120
○ No active IDCC for 38352791800015 (API OK, but no IDCC in database)
```

---

## 📝 Checklist de validation

- [x] Code modifié pour utiliser API Siret2IDCC
- [x] Documentation créée
- [ ] Tests en production
- [ ] Vérification des logs Railway
- [ ] Validation du taux de réussite IDCC (> 30%)

---

## 🚀 Déploiement

1. Commit et push des modifications
2. Railway redéploiera automatiquement
3. Relancer l'enrichissement IDCC depuis `/admin`
4. Vérifier les logs : des IDCC devraient être trouvés !

---

## 📚 Ressources

- [API Siret2IDCC (GitHub)](https://github.com/SocialGouv/siret2idcc)
- [API Recherche-Entreprises](https://recherche-entreprises.api.gouv.fr)
- [Dataset SIRET-IDCC](https://www.data.gouv.fr/datasets/liste-des-conventions-collectives-par-entreprise-siret/)
- [Base KALI (conventions collectives)](https://www.data.gouv.fr/datasets/kali-conventions-collectives-nationales/)

---

**🎯 Conclusion** : L'erreur était d'utiliser l'API Sirene qui ne contient pas d'IDCC. La nouvelle implémentation utilise l'API dédiée Siret2IDCC et devrait trouver des IDCC pour 30-50% des entreprises.
