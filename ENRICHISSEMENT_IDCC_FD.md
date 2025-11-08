# Enrichissement automatique FD à partir des IDCC

## Principe

**Toutes les entreprises avec un IDCC DOIVENT avoir une FD (Fédération).**

Ce système enrichit automatiquement les FD manquantes en utilisant la correspondance IDCC → FD extraite de la base de données des PV (table `Tous_PV`).

## Fonctionnement

### 1. Construction du mapping IDCC → FD

Le mapping est construit en analysant tous les PV de la base de données :

- Pour chaque IDCC, on identifie toutes les FD associées dans les PV
- On choisit la FD la plus fréquente pour chaque IDCC
- Le mapping est sauvegardé dans `app/data/idcc_fd_mapping.json`

### 2. Enrichissement automatique

L'enrichissement se fait automatiquement dans 2 cas :

#### A. Lors de l'ajout manuel d'une invitation (API)

Quand vous ajoutez une invitation via l'API `/api/invitation/add` :
- Si un IDCC est fourni mais pas de FD
- Le système recherche automatiquement la FD correspondante
- La FD est ajoutée automatiquement à l'invitation

#### B. Lors de l'import Excel

Quand vous importez des invitations depuis un fichier Excel :
- Pour chaque ligne avec IDCC mais sans FD
- Le système enrichit automatiquement la FD depuis le mapping
- L'enrichissement se fait pendant l'import

## Utilisation

### Via les scripts Python

#### 1. Générer le mapping IDCC → FD depuis les PV

```bash
python scripts/generate_idcc_fd_mapping.py
```

Ce script :
- Analyse tous les PV avec IDCC et FD
- Crée le fichier `app/data/idcc_fd_mapping.json`
- Affiche les statistiques et les conflits éventuels

#### 2. Enrichir en masse les invitations existantes

```bash
python scripts/enrich_fd_from_idcc.py
```

Ce script :
- Charge le mapping IDCC → FD (ou le construit si absent)
- Identifie toutes les invitations avec IDCC mais sans FD
- Enrichit automatiquement ces invitations
- Affiche un résumé des enrichissements

### Via l'API REST

#### 1. Obtenir les statistiques sur le mapping

```bash
GET /api/idcc/mapping/stats
```

Retourne :
- Nombre total de correspondances IDCC → FD
- Un échantillon du mapping

#### 2. Reconstruire le mapping depuis les PV

```bash
POST /api/idcc/mapping/rebuild
```

Force la reconstruction du mapping depuis la table `Tous_PV`.

#### 3. Voir les invitations problématiques

```bash
GET /api/idcc/invitations/missing-fd
```

Retourne :
- Nombre d'invitations avec IDCC mais sans FD
- Des exemples d'invitations à enrichir
- Un pourcentage du problème

#### 4. Enrichir en masse toutes les invitations

```bash
POST /api/idcc/invitations/enrich-all
```

Enrichit automatiquement toutes les invitations qui ont un IDCC mais pas de FD.

## Architecture technique

### Service d'enrichissement

`app/services/idcc_enrichment.py` :
- `IDCCEnrichmentService` : Service singleton pour gérer l'enrichissement
- `get_mapping()` : Charge ou construit le mapping IDCC → FD
- `enrich_fd()` : Enrichit une FD à partir d'un IDCC
- `rebuild_mapping()` : Reconstruit le mapping depuis les PV

### Intégration dans l'application

1. **Route API d'ajout** (`app/routers/api.py`) :
   - Enrichissement automatique lors de l'ajout manuel

2. **Import ETL** (`app/etl.py`) :
   - Enrichissement automatique lors de l'import Excel

3. **Routes d'enrichissement** (`app/routers/api_idcc_enrichment.py`) :
   - API pour gérer l'enrichissement en masse

## Exemple de mapping

```json
{
  "description": "Table de correspondance IDCC → FD",
  "generated_at": "2025-11-07T12:00:00",
  "total_entries": 150,
  "mapping": {
    "16": "BÂTIMENT",
    "54": "CHIMIE",
    "176": "MÉTALLURGIE",
    "2098": "BANQUE",
    ...
  }
}
```

## Gestion des conflits

Quand un IDCC a plusieurs FD possibles dans les PV :
- Le système choisit automatiquement la FD la plus fréquente
- Les conflits sont documentés dans le fichier JSON généré
- Un avertissement est affiché lors de la génération du mapping

## Avertissements

⚠️ **Base de données vide** : Le mapping ne peut être construit que si la table `Tous_PV` contient des données. Assurez-vous que la base `papcse.db` est bien téléchargée et contient les PV.

⚠️ **IDCC sans correspondance** : Si un IDCC n'est pas trouvé dans le mapping, la FD restera vide. Dans ce cas, il faut soit :
- Vérifier que les PV contiennent bien cet IDCC
- Ajouter manuellement la correspondance dans le mapping
- Contacter l'administrateur pour mettre à jour la base PV

## Monitoring

Pour vérifier l'état de l'enrichissement :

1. **Statistiques générales** :
   ```bash
   GET /api/idcc/invitations/missing-fd
   ```

2. **État du mapping** :
   ```bash
   GET /api/idcc/mapping/stats
   ```

3. **Logs applicatifs** :
   - Les enrichissements automatiques sont tracés dans les logs
   - Recherchez "Enrichissement automatique FD"
