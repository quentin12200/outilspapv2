# Débug des indicateurs KPI sur la page d'accueil

## Problème
Les indicateurs clés de la page d'accueil n'affichent pas de données (affichent "—").

## Solution

### 1. Vérifier que le serveur FastAPI est démarré

Le serveur doit être en cours d'exécution pour que l'API fonctionne :

```bash
# Démarrer le serveur
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Ou si uvicorn est installé globalement :

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Vérifier que l'endpoint API fonctionne

Ouvrez http://localhost:8000/api/stats/enriched dans votre navigateur ou utilisez curl :

```bash
curl http://localhost:8000/api/stats/enriched
```

Vous devriez voir un JSON comme :

```json
{
  "total_invitations": 123,
  "audience_threshold": 1000,
  "pap_pv_overlap_percent": 45.6,
  "cgt_implanted_count": 789,
  "cgt_implanted_percent": 67.8,
  "elections_next_30_days": 12
}
```

### 3. Vérifier la console du navigateur

Ouvrez la console développeur (F12) et regardez les erreurs :

1. Allez sur la page d'accueil : http://localhost:8000/
2. Ouvrez la console (F12)
3. Vous devriez voir :
   - `Chargement des KPIs depuis /api/stats/enriched...`
   - `KPIs chargés: {données...}`

Si vous voyez une erreur réseau, cela signifie que le serveur n'est pas démarré ou n'est pas accessible.

### 4. Vérifier que la base de données contient des données

Si l'API fonctionne mais retourne tous des zéros :

```json
{
  "total_invitations": 0,
  "audience_threshold": 1000,
  "pap_pv_overlap_percent": 0.0,
  "cgt_implanted_count": 0,
  "cgt_implanted_percent": 0.0,
  "elections_next_30_days": 0
}
```

Cela signifie que votre base de données est vide. Vous devez :

1. Vérifier que le fichier de base de données existe (par défaut : `papcse.db`)
2. Importer des données via la page d'administration : http://localhost:8000/admin

### 5. Messages d'erreur visibles

Avec la dernière mise à jour, si l'API ne répond pas, vous verrez maintenant un message d'erreur rouge sur la page d'accueil indiquant :

> **Erreur de chargement des indicateurs**
> HTTP 500: Internal Server Error
> Vérifiez que le serveur FastAPI est démarré et accessible.

## Vérification rapide

```bash
# 1. Le serveur est-il en cours d'exécution ?
ps aux | grep uvicorn

# 2. Le port 8000 est-il ouvert ?
curl http://localhost:8000/

# 3. L'endpoint API fonctionne-t-il ?
curl http://localhost:8000/api/stats/enriched

# 4. Y a-t-il des données dans la base ?
# Ouvrez http://localhost:8000/invitations pour vérifier
```

## Nouveau dans cette version

- ✅ Endpoint `/api/stats/enriched` créé (app/routers/api.py:982-1053)
- ✅ Gestion des erreurs améliorée avec logs console
- ✅ Message d'erreur visible sur la page si l'API échoue
- ✅ Affichage de "0" au lieu de "—" quand les données sont vides
- ✅ Spinner de chargement pendant la requête API

## Contact

Si le problème persiste, vérifiez les logs du serveur FastAPI pour voir les erreurs détaillées.
