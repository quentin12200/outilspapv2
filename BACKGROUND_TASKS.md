# Tâches de fond (Background Tasks)

## Problème

La fonction `build_siret_summary()` reconstruit la table `siret_summary` à partir de tous les PV et invitations. Avec une base de 126k+ lignes, cette opération peut prendre plusieurs minutes et causer des **timeouts** si exécutée de manière synchrone.

## Solution : FastAPI BackgroundTasks

L'application utilise maintenant **FastAPI BackgroundTasks** pour exécuter les opérations lourdes en arrière-plan sans bloquer l'API.

## Configuration

### Variable d'environnement

Dans `.env` :

```bash
# Par défaut : false (recommandé en production)
AUTO_BUILD_SUMMARY_ON_STARTUP=false
```

- **`false`** (recommandé) : Au démarrage, l'application ne reconstruit PAS automatiquement `siret_summary`. Vous devez la lancer manuellement via l'API.
- **`true`** : Reconstruction automatique au démarrage (peut causer des timeouts, à éviter en production)

## Utilisation

### 1. Lancer la reconstruction en arrière-plan

```bash
curl -X POST http://localhost:8000/api/build/summary
```

Réponse :
```json
{
  "status": "started",
  "message": "La reconstruction de la table siret_summary a été lancée en arrière-plan",
  "task_id": "build_siret_summary",
  "check_status_url": "/api/build/summary/status"
}
```

### 2. Vérifier le statut de la tâche

```bash
curl http://localhost:8000/api/build/summary/status
```

**Pendant l'exécution :**
```json
{
  "status": "running",
  "description": "Reconstruction de la table siret_summary",
  "started_at": "2025-11-06T14:30:00.123456",
  "completed_at": null
}
```

**Après succès :**
```json
{
  "status": "completed",
  "description": "Reconstruction de la table siret_summary",
  "started_at": "2025-11-06T14:30:00.123456",
  "completed_at": "2025-11-06T14:35:23.789012",
  "result": {
    "rows": 125432
  }
}
```

**En cas d'erreur :**
```json
{
  "status": "failed",
  "description": "Reconstruction de la table siret_summary",
  "started_at": "2025-11-06T14:30:00.123456",
  "completed_at": "2025-11-06T14:31:15.456789",
  "error": "Error in build_siret_summary: ..."
}
```

### 3. Tâche déjà en cours

Si vous essayez de lancer une nouvelle reconstruction alors qu'une tâche est déjà en cours :

```json
{
  "status": "already_running",
  "message": "Une reconstruction est déjà en cours",
  "task_id": "build_siret_summary",
  "started_at": "2025-11-06T14:30:00.123456"
}
```

## Workflow recommandé en production

### Déploiement initial

1. **Déployer** l'application avec `AUTO_BUILD_SUMMARY_ON_STARTUP=false`
2. **Attendre** que l'application démarre (quelques secondes)
3. **Lancer** la reconstruction en arrière-plan :
   ```bash
   curl -X POST https://votre-app.com/api/build/summary
   ```
4. **Surveiller** le statut :
   ```bash
   watch -n 5 curl https://votre-app.com/api/build/summary/status
   ```

### Mise à jour des données

Après avoir importé de nouveaux PV ou invitations :

```bash
# 1. Importer les données via l'interface admin ou l'API
# 2. Relancer la reconstruction
curl -X POST https://votre-app.com/api/build/summary

# 3. Vérifier le statut
curl https://votre-app.com/api/build/summary/status
```

## Limitations actuelles

### Stockage en mémoire

Le tracker de tâches utilise un dictionnaire Python en mémoire (`task_tracker`). Cela signifie que :

- ✅ Simple et rapide
- ✅ Aucune dépendance externe
- ⚠️ **Les statuts sont perdus au redémarrage** de l'application
- ⚠️ **Une seule instance** d'application (pas de load balancing)

### Pour un déploiement multi-instances

Si vous avez besoin de plusieurs instances (load balancing), vous devriez :

1. **Option A : Celery + Redis**
   - Worker dédié pour les tâches lourdes
   - Queue persistante
   - Monitoring avancé

2. **Option B : Redis pour le tracking uniquement**
   - Garder FastAPI BackgroundTasks
   - Stocker les statuts dans Redis
   - Permet le load balancing

3. **Option C : Base de données**
   - Créer une table `background_tasks`
   - Stocker les statuts en DB
   - Plus lent mais simple

## Architecture technique

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ POST /api/build/summary
       ▼
┌─────────────────────────────┐
│   FastAPI BackgroundTasks   │
│  (Lance task en arrière-plan)│
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│  run_build_siret_summary()  │
│  (Fonction background)       │
│  - Crée nouvelle session DB  │
│  - Appelle etl.build_...()  │
│  - Track statut dans mémoire │
└─────────────────────────────┘
```

## Logs

Les logs montrent la progression de la tâche :

```
INFO:app.background_tasks:Task build_siret_summary started: Reconstruction de la table siret_summary
INFO:app.background_tasks:Starting build_siret_summary in background...
INFO:app.background_tasks:build_siret_summary completed: 125432 rows generated
INFO:app.background_tasks:Task build_siret_summary completed successfully
```

En cas d'erreur :

```
ERROR:app.background_tasks:Task build_siret_summary failed: Error in build_siret_summary: ...
```

## Tests

### Test manuel

```bash
# Terminal 1 : Lancer l'application
uvicorn app.main:app --reload

# Terminal 2 : Lancer la reconstruction
curl -X POST http://localhost:8000/api/build/summary

# Terminal 2 : Vérifier le statut (en boucle)
watch -n 2 curl -s http://localhost:8000/api/build/summary/status | jq
```

### Test de protection contre les doubles exécutions

```bash
# Lancer deux fois rapidement
curl -X POST http://localhost:8000/api/build/summary
curl -X POST http://localhost:8000/api/build/summary

# La deuxième devrait retourner "already_running"
```

## Troubleshooting

### La tâche reste bloquée en "running"

Si l'application crash pendant une tâche, le statut reste "running". Au prochain démarrage, l'historique est perdu (stockage en mémoire).

**Solution :** Relancer simplement `POST /api/build/summary` après le redémarrage.

### Timeout au démarrage

Si vous avez `AUTO_BUILD_SUMMARY_ON_STARTUP=true` et des timeouts :

1. Mettre `AUTO_BUILD_SUMMARY_ON_STARTUP=false`
2. Redémarrer l'application
3. Lancer manuellement via l'API

### La tâche échoue

Vérifier les logs de l'application pour voir l'erreur détaillée :

```bash
docker logs votre-container
# ou
tail -f logs/app.log
```

## Évolutions futures

- [ ] Ajouter un endpoint pour annuler une tâche en cours
- [ ] Ajouter un système de retry automatique en cas d'échec
- [ ] Implémenter un nettoyage automatique des anciennes tâches (déjà prévu dans `TaskTracker.cleanup_old_tasks()`)
- [ ] Ajouter un progress indicator (pourcentage de progression)
- [ ] Migrer vers Redis pour le tracking multi-instances
- [ ] Ajouter une interface admin pour gérer les tâches
