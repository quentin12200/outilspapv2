# 🧪 Guide de test - Page Recherche SIRET

## 📋 Objectif

Vérifier que la page `/recherche-siret` fonctionne correctement avec le rate limiter (30 req/min).

## ✅ Pré-requis

- Application déployée sur Railway
- Variable d'environnement `SIRENE_API_KEY` configurée
- Rate limiter activé (28 req/min)

## 🧪 Tests à effectuer

### Test 1 : Recherche simple via API Sirene

**Action :**
1. Ouvrir https://votre-app.railway.app/recherche-siret
2. Remplir le formulaire :
   - Nom : `RENAULT`
   - Code postal : `92100`
3. Cliquer sur **"API Sirene"** (bouton bleu)

**Résultat attendu :**
```
✅ Résultats affichés (plusieurs SIRET RENAULT à Boulogne-Billancourt)
✅ Possibilité de copier les SIRET
✅ Pas d'erreur 429
```

**En cas de lenteur :**
- C'est normal avec le rate limiter (28 req/min)
- Vérifier les logs Railway pour voir : `Rate limit atteint (28 req/60s). Attente de XXs...`

---

### Test 2 : Recherche multiple rapide (test du rate limiter)

**Action :**
1. Rechercher `CARREFOUR` → cliquer "API Sirene"
2. Immédiatement après, rechercher `AUCHAN` → cliquer "API Sirene"
3. Immédiatement après, rechercher `LECLERC` → cliquer "API Sirene"

**Résultat attendu :**
```
✅ Les 3 recherches fonctionnent
⏱️ Possibles délais d'attente (rate limiter)
✅ Pas d'erreur 429
```

**Logs Railway attendus :**
```
Rate limiter initialisé : 28 req/60s
API Response: status=200
Rate limit atteint (28 req/60s). Attente de 15.3s...
API Response: status=200
```

---

### Test 3 : Ajout PAP avec enrichissement Sirene

**Action :**
1. Aller sur l'onglet **"Ajouter PAP"**
2. Entrer un SIRET : `55210055400054`
3. Cliquer sur **"Vérifier"**
4. Cliquer sur **"Rechercher dans l'API Sirene"** (bouton bleu)

**Résultat attendu :**
```
✅ Les champs sont pré-remplis automatiquement :
   - Raison sociale
   - Ville
   - Code postal
✅ Message : "Données récupérées depuis l'API Sirene !"
✅ Pas d'erreur 429
```

---

### Test 4 : Recherche "Rechercher partout"

**Action :**
1. Retour sur l'onglet **"Recherche SIRET"**
2. Entrer `TOTAL` + code postal `92400`
3. Cliquer sur **"Rechercher partout"** (bouton rouge)

**Résultat attendu :**
```
✅ Pappers.fr s'ouvre dans un nouvel onglet
✅ Résultats API Sirene affichés dans l'application
✅ Pas d'erreur 429
```

---

## 🔍 Vérification des logs Railway

Après les tests, vérifier dans Railway → Logs :

### ✅ Logs attendus (succès)

```log
[SIRENE API] Using Integration Key: 47d719f0...14d9 (length: 36)
[SIRENE API] Header: X-INSEE-Api-Key-Integration
Rate limiter initialisé : 28 req/60s
API Response for SIRET: status=200
Rate limit atteint (28 req/60s). Attente de 12.5s...
```

### ❌ Logs à surveiller (problèmes)

```log
# Si clé API non trouvée
[SIRENE API] ⚠️ NO API KEY configured - Using public access (30 req/min limit)

# Si rate limit dépassé (ne devrait pas arriver)
API Response: status=429
Rate limit atteint - Nombre max de retries atteint

# Si timeout
Timeout lors de la requête SIRET
```

---

## 📊 Performance attendue

| Scenario | Temps attendu |
|----------|---------------|
| 1 recherche simple | ~1-2 secondes |
| 10 recherches successives | ~20-30 secondes (rate limiter) |
| Enrichissement 1 SIRET | ~1-2 secondes |
| Enrichissement 100 SIRET | ~4-5 minutes |

---

## ❓ Dépannage

### Problème : Erreur "Erreur lors de la recherche"

**Solution :**
1. Vérifier que `SIRENE_API_KEY` est bien définie dans Railway
2. Vérifier les logs : `[SIRENE API] Using Integration Key: ...`
3. Tester avec `test_sirene_key.py`

### Problème : Recherches très lentes

**Raisons possibles :**
- ✅ **Normal** : Rate limiter actif (28 req/min)
- ❌ Problème réseau avec l'API INSEE
- ❌ Timeout trop court

**Action :**
Vérifier les logs pour voir `Rate limit atteint`. Si présent, c'est normal.

### Problème : Toujours des erreurs 429

**Solution :**
1. Vérifier que le rate limiter est bien importé dans les fichiers
2. Vérifier que la branche `claude/fix-electoral-quotient-calculation-011CUrhaod8vzkG7ZHeXooi3` est déployée
3. Redémarrer l'application Railway

---

## ✅ Checklist de validation

- [ ] Recherche simple fonctionne
- [ ] Pas d'erreur 429
- [ ] Logs montrent le rate limiter actif
- [ ] Ajout PAP avec enrichissement fonctionne
- [ ] "Rechercher partout" fonctionne
- [ ] Attentes visibles dans les logs (rate limiter)

---

**Date de création** : 2025-11-07
**Branche** : claude/fix-electoral-quotient-calculation-011CUrhaod8vzkG7ZHeXooi3
**Statut** : ✅ Rate limiter implémenté et intégré
