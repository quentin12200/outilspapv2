# Guide d'Optimisation

## Optimisations Implémentées

### 1. Audit Logs
- Logging automatique de toutes les opérations admin via middleware
- Stockage dans SQLite pour traçabilité complète
- Endpoints `/api/audit/logs` et `/api/audit/stats` pour consultation

### 2. TaskTracker Persistant
- Persistance des tâches en base de données (SQLite)
- Cache en mémoire avec TTL de 60s
- Les tâches survivent aux redémarrages de l'application
- Auto-cleanup des tâches anciennes (> 24h)

### 3. build_siret_summary() - Stratégies d'Optimisation

#### Problème Identifié
La fonction `build_siret_summary()` traite 126k+ lignes en pandas, ce qui cause :
- Temps d'exécution long (plusieurs minutes)
- Consommation mémoire élevée
- Blocage de l'application au démarrage

#### Optimisations Court Terme (Implémentées)

1. **Exécution en arrière-plan obligatoire**
   - La reconstruction ne bloque jamais le démarrage
   - Endpoint POST `/api/build/summary` lance la tâche en background
   - Status disponible via GET `/api/build/summary/status`

2. **Index de base de données**
   - Index sur `PVEvent.siret`, `PVEvent.cycle`, `PVEvent.date_pv`
   - Index sur `Invitation.siret`, `Invitation.date_invit`
   - Index sur `SiretSummary.siret`

3. **Calcul des sièges désactivé temporairement**
   - Le calcul du quotient électoral était trop lent
   - Colonnes `*_siege_c3` et `*_siege_c4` initialisées à NULL
   - TODO: Réactiver avec calcul batch optimisé

#### Optimisations Moyen Terme (À Implémenter)

1. **Calcul incrémental**
   ```python
   # Au lieu de recalculer tout :
   # - Détecter les SIRET modifiés depuis la dernière exécution
   # - Ne recalculer que ces SIRET
   # - Merger avec les résultats existants
   ```

2. **Batch Processing avec Chunking**
   ```python
   CHUNK_SIZE = 10000  # Traiter par lots de 10k lignes
   for offset in range(0, total_rows, CHUNK_SIZE):
       chunk = pvs[offset:offset + CHUNK_SIZE]
       process_chunk(chunk)
       # Libérer la mémoire
       del chunk
       gc.collect()
   ```

3. **Parallelisation**
   ```python
   from multiprocessing import Pool

   def process_siret_batch(sirets):
       # Traiter un batch de SIRET
       pass

   with Pool(processes=4) as pool:
       results = pool.map(process_siret_batch, batches)
   ```

#### Optimisations Long Terme (Architecture)

1. **Matérialisation progressive**
   - Trigger SQL sur INSERT/UPDATE de PVEvent et Invitation
   - Mise à jour automatique de SiretSummary en quasi-temps réel
   - Évite la reconstruction complète

2. **Vue matérialisée PostgreSQL**
   ```sql
   CREATE MATERIALIZED VIEW siret_summary_mv AS
   SELECT ...
   FROM Tous_PV
   GROUP BY siret;

   CREATE UNIQUE INDEX ON siret_summary_mv (siret);

   -- Refresh incrémental
   REFRESH MATERIALIZED VIEW CONCURRENTLY siret_summary_mv;
   ```

3. **Cache Redis**
   - Mettre en cache les résultats de `build_siret_summary()`
   - TTL de 1 heure
   - Invalidation sur ingestion de nouvelles données

4. **Columnar Storage** (Advanced)
   - Utiliser Parquet/Arrow pour les données PV historiques
   - Lecture vectorisée ultra-rapide
   - Compression importante (~10x)

## Index de Base de Données

### Tables Principales

```sql
-- PVEvent
CREATE INDEX IF NOT EXISTS idx_pv_siret ON Tous_PV(siret);
CREATE INDEX IF NOT EXISTS idx_pv_cycle ON Tous_PV(Cycle);
CREATE INDEX IF NOT EXISTS idx_pv_date ON Tous_PV(date_scrutin);
CREATE INDEX IF NOT EXISTS idx_pv_siret_cycle ON Tous_PV(siret, Cycle);

-- Invitation
CREATE INDEX IF NOT EXISTS idx_invitation_siret ON invitations(siret);
CREATE INDEX IF NOT EXISTS idx_invitation_date ON invitations(date_invit);
CREATE INDEX IF NOT EXISTS idx_invitation_siret_date ON invitations(siret, date_invit);

-- SiretSummary
CREATE INDEX IF NOT EXISTS idx_summary_siret ON siret_summary(siret);
CREATE INDEX IF NOT EXISTS idx_summary_statut ON siret_summary(statut_pap);
CREATE INDEX IF NOT EXISTS idx_summary_cgt ON siret_summary(cgt_implantee);
```

### Tables d'Audit

```sql
-- AuditLog
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_logs(user_identifier);
CREATE INDEX IF NOT EXISTS idx_audit_resource ON audit_logs(resource_type);
CREATE INDEX IF NOT EXISTS idx_audit_success ON audit_logs(success);

-- BackgroundTask
CREATE INDEX IF NOT EXISTS idx_task_status ON background_tasks(status);
CREATE INDEX IF NOT EXISTS idx_task_started ON background_tasks(started_at);
```

## Monitoring

### Requêtes Lentes

Activer le logging SQLAlchemy pour identifier les requêtes lentes :

```python
import logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
```

### Métriques Clés

1. **Temps d'exécution build_siret_summary()**
   - Objectif : < 30 secondes pour 126k lignes
   - Actuel : ~2-5 minutes

2. **Utilisation mémoire**
   - Objectif : < 500MB
   - Actuel : ~1-2GB peak

3. **Temps de réponse API**
   - Objectif : < 200ms pour 95% des requêtes
   - Actuel : ~50-150ms (OK)

## Next Steps

Priorités pour les prochaines optimisations :

1. ✅ Audit logging complet
2. ✅ TaskTracker persistant
3. ⏳ build_siret_summary() incrémental
4. ⏳ Cache Redis pour les résultats
5. ⏳ Migration vers PostgreSQL (pour vues matérialisées)
6. ⏳ Calcul des sièges optimisé
