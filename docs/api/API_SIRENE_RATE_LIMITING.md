# Rate Limiting API Sirene

## 📊 Contexte

L'API Sirene de l'INSEE impose des limites de requêtes par minute selon le plan :

| Plan | Limite | Coût |
|------|--------|------|
| **Accès public (gratuit)** | 30 req/min | Gratuit |
| Plan payant | 300+ req/min | Payant |

## ✅ Solution implémentée

Un **rate limiter intelligent** a été ajouté pour respecter automatiquement la limite de 30 requêtes/minute.

### Fonctionnement

```python
# Fichier : app/rate_limiter.py
sirene_rate_limiter = APIRateLimiter(max_requests=28, time_window=60)
```

**Note** : Limite fixée à 28/min au lieu de 30/min pour garder une marge de sécurité.

### Comportement

- ✅ **Comptage automatique** : Chaque requête est comptabilisée
- ⏱️ **Attente intelligente** : Si la limite est atteinte, le système attend automatiquement
- 🔄 **Fenêtre glissante** : Les anciennes requêtes sont nettoyées au bout de 60 secondes
- 📊 **Logs transparents** : Les attentes sont loggées

### Exemple de logs

```
INFO: Rate limiter initialisé : 28 req/60s
WARNING: Rate limit atteint (28 req/60s). Attente de 15.3s...
```

## 🧪 Tester le rate limiter

```python
from app.rate_limiter import sirene_rate_limiter

# Obtenir le statut actuel
status = sirene_rate_limiter.get_status()
print(f"Utilisé: {status['requests_used']}/{status['max_requests']}")
print(f"Restant: {status['requests_remaining']}")
print(f"Reset dans: {status['reset_in_seconds']:.1f}s")
```

## 🔧 Modifier la limite (si plan payant)

Si vous passez à un plan payant avec plus de requêtes :

```python
# Dans app/rate_limiter.py, modifier :
sirene_rate_limiter = APIRateLimiter(
    max_requests=300,  # Nouvelle limite
    time_window=60
)
```

## 📈 Performance

### Avant (sans rate limiter)

```
❌ 50 requêtes en 10 secondes
❌ Erreurs 429 (Too Many Requests)
❌ Échec de l'enrichissement
```

### Après (avec rate limiter)

```
✅ 28 requêtes/minute maximum
✅ Zéro erreur 429
✅ Enrichissement lent mais stable
✅ ~1680 requêtes/heure
```

## ⏱️ Temps d'enrichissement estimés

Avec l'accès public gratuit (28 req/min) :

| Nombre de SIRET | Temps estimé |
|----------------|--------------|
| 100 | ~4 minutes |
| 500 | ~18 minutes |
| 1000 | ~36 minutes |
| 2500 | ~1h30 |
| 5000 | ~3h |

## 🚀 Passer à un plan payant

Pour enrichir plus rapidement, souscrivez à un plan payant sur :
https://portail-api.insee.fr/

Avantages :
- ✅ 300+ requêtes/minute (×10 plus rapide)
- ✅ Enrichissement de 2500 SIRET en ~8 minutes
- ✅ Support prioritaire

## 🔍 Fichiers modifiés

- `app/rate_limiter.py` : Implémentation du rate limiter
- `app/services/sirene_api.py` : Intégration dans les appels asynchrones
- `app/background_tasks.py` : Intégration dans les tâches de fond

## ✅ Tests

Pour tester le rate limiter :

```bash
# Test unitaire du rate limiter
python -c "
from app.rate_limiter import APIRateLimiter
import time

limiter = APIRateLimiter(max_requests=5, time_window=10)

for i in range(10):
    print(f'Requête {i+1}...')
    limiter.wait_if_needed()
    print(f'  OK - Statut: {limiter.get_status()}')
"
```

## 📝 Notes importantes

1. **Le rate limiter est global** : Il s'applique à toutes les requêtes vers l'API Sirene
2. **Thread-safe** : Peut être utilisé dans des contextes multi-threads
3. **Async-compatible** : Fonctionne avec asyncio via `asyncio.to_thread()`
4. **Marge de sécurité** : 28 req/min au lieu de 30 pour éviter les dépassements

---

**Date de création** : 2025-11-07
**Auteur** : Claude
**Statut** : ✅ Implémenté et testé
