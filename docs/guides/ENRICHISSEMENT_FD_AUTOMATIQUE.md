# Enrichissement automatique de la FD (Fédération)

**Date**: 2025-11-07

## Contexte

Lors de l'enrichissement des invitations avec l'API Siret2IDCC, l'application récupère l'IDCC (convention collective) mais pas la FD (Fédération CGT).

La FD est une information essentielle pour organiser le travail syndical, mais elle n'est pas fournie par les APIs externes.

## Solution implémentée

### Déduction automatique de la FD à partir de l'IDCC

L'application construit maintenant une **table de correspondance IDCC → FD** à partir de la base de données historique des PV (Tous_PV).

#### Principe

1. **Extraction**: Au moment de l'enrichissement, le système analyse tous les PV qui ont à la fois un IDCC et une FD renseignés
2. **Agrégation**: Pour chaque IDCC, on compte les FD associées dans les différents PV
3. **Choix**: Si plusieurs FD sont possibles pour un même IDCC, on choisit la plus fréquente
4. **Application**: Lors de l'enrichissement, si un IDCC est trouvé via l'API, la FD correspondante est automatiquement renseignée

### Code modifié

#### `app/background_tasks.py`

- **Fonction `_build_idcc_to_fd_mapping(session)`**:
  - Construit la table de correspondance à partir de la base PV
  - Gère les conflits (même IDCC avec plusieurs FD) en choisissant la FD la plus fréquente
  - Retourne un dictionnaire `{idcc: fd}`

- **Fonction `_get_siret_sync(siret)`**:
  - Récupère maintenant aussi le titre de la convention (`idcc_title`)
  - Permet des enrichissements futurs basés sur le titre

- **Fonction `run_enrichir_invitations_idcc()`**:
  - Construit la table de correspondance au début de l'enrichissement
  - Pour chaque IDCC trouvé, cherche la FD correspondante et la renseigne si elle n'est pas déjà présente
  - Compte le nombre de FD déduits et l'inclut dans le rapport final

### Exemple de flux

```
1. Invitation avec SIRET 55210055400175 (Peugeot)
   ↓
2. Appel API Siret2IDCC → IDCC: 0054 (Métallurgie)
   ↓
3. Consultation table de correspondance → FD: FTM-CGT
   ↓
4. Mise à jour invitation:
   - idcc = "0054"
   - idcc_url = "https://www.legifrance.gouv.fr/..."
   - fd = "FTM-CGT"  ← NOUVEAU !
```

### Logs

L'enrichissement affiche maintenant des logs détaillés :

```
Construction de la table de correspondance IDCC → FD à partir de la base PV...
Table de correspondance IDCC → FD construite avec 234 entrées
✓ [1/88] SIRET 55210055400175 (PEUGEOT SA...) → IDCC: 0054 | FD: FTM-CGT
FD 'FTM-CGT' déduite pour IDCC 0054
```

### Rapport final

Le rapport d'enrichissement inclut maintenant le nombre de FD déduits :

```json
{
  "total": 88,
  "traites_avec_succes": 85,
  "idcc_trouves": 42,
  "fds_deduits": 38,
  "sans_idcc": 43,
  "erreurs": 3
}
```

## Gestion des conflits

Certains IDCC peuvent être associés à plusieurs FD (par exemple, une entreprise multi-secteurs). Dans ce cas :

- Le système choisit la FD la plus fréquente
- Un avertissement est loggé : `IDCC 1234 a plusieurs FD possibles: {'FTM-CGT': 15, 'FCE-CGT': 3}. Choix de 'FTM-CGT' (la plus fréquente)`

## Script de génération (optionnel)

Un script `scripts/generate_idcc_fd_mapping.py` est disponible pour générer un fichier JSON avec la correspondance complète :

```bash
python scripts/generate_idcc_fd_mapping.py
```

Ce fichier peut être utilisé :
- Pour documentation
- Pour validation manuelle des correspondances
- Pour export vers d'autres outils

## Avantages

✅ **Automatique**: La FD est renseignée sans intervention manuelle
✅ **Basé sur les données**: Utilise l'historique réel des PV
✅ **Fiable**: Choisit la FD la plus fréquente en cas de conflit
✅ **Maintenable**: Se met à jour automatiquement avec les nouvelles données PV

## Limitations

⚠️ **Nouveaux IDCC**: Si un IDCC n'a jamais été rencontré dans les PV, la FD ne pourra pas être déduite
⚠️ **Recalcul**: La table est reconstruite à chaque enrichissement (peut être optimisé avec un cache)

## Évolutions futures

1. **Cache de la correspondance**: Sauvegarder la correspondance dans un fichier pour éviter de la recalculer
2. **API de consultation**: Endpoint pour consulter la correspondance IDCC → FD
3. **Interface admin**: Page pour visualiser et corriger manuellement les correspondances
