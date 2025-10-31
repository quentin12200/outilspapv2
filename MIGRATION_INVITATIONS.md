# 🔧 Migration des colonnes invitations

## Problème

Le tableau des invitations (`/invitations`) affiche des colonnes vides (tirets `—`) alors que les données sont présentes dans le fichier Excel importé.

**Cause :** Les données importées avant le commit `5893e52` ont seulement le champ `raw` (JSON) rempli, mais pas les colonnes structurées (denomination, enseigne, adresse, etc.).

## Solutions

### Solution 1 : Migration automatique (déjà implémentée)

Une migration automatique s'exécute au démarrage de l'application (`app/migrations.py`). Elle remplit les colonnes structurées depuis le champ `raw`.

**Avantage :** Automatique, aucune action requise
**Limite :** Ne fonctionne que si le champ `raw` contient les données

### Solution 2 : Script de migration manuel

Si la migration automatique ne suffit pas, exécutez le script standalone :

#### Sur Railway (via console)

```bash
# Se connecter à Railway
railway link

# Exécuter le script
railway run python scripts/migrate_and_fix_invitations.py
```

#### En local

```bash
# Créer un fichier .env avec DATABASE_URL
echo "DATABASE_URL=sqlite:///./papcse.db" > .env

# Exécuter le script
python scripts/migrate_and_fix_invitations.py
```

### Solution 3 : Réimporter les données

Si vous avez accès aux fichiers Excel originaux :

1. Aller sur `/admin`
2. Section "Import invitations PAP"
3. Télécharger le fichier Excel
4. Le nouvel import remplira automatiquement toutes les colonnes

## Vérification

Après migration, vérifiez que les colonnes s'affichent :

1. Aller sur `/invitations`
2. Vérifier que les colonnes suivantes sont remplies :
   - Raison sociale
   - Enseigne
   - Adresse
   - Ville
   - Code postal
   - Activité
   - Effectifs

## Format attendu du fichier Excel

Le script d'import détecte automatiquement les colonnes suivantes (avec aliases) :

| Champ attendu     | Aliases acceptés                                                    |
|-------------------|---------------------------------------------------------------------|
| SIRET             | `siret`, `SIRET`, `n_siret`                                         |
| Raison sociale    | `raison sociale`, `raison_sociale`, `denomination`, `rs`, `nom`     |
| Enseigne          | `enseigne`, `enseigne_commerciale`                                  |
| Adresse           | `adresse`, `adresse_1`, `adresse_ligne1`, `adresse_complete`        |
| Ville             | `ville`, `commune`, `localite`                                      |
| Code postal       | `code postal`, `cp`, `code_postal`                                  |
| Date invitation   | `date invitation`, `date_invitation`, `date`, `date_pap`            |
| Source            | `source`, `origine`, `canal`                                        |
| Activité          | `activite_principale`, `code_naf`, `naf`, `code_ape`, `ape`        |
| Effectifs         | `effectifs`, `effectif`, `tranche_effectifs`                        |
| Est actif         | `est_actif`, `actif`, `etat_etablissement`, `etat`                  |
| Est siège         | `est_siege`, `siege`, `siege_social`                                |

**Notes :**
- Les noms de colonnes sont insensibles à la casse
- Les espaces et caractères spéciaux sont normalisés automatiquement
- Seul le SIRET est obligatoire, les autres champs sont optionnels

## Diagnostic

Pour diagnostiquer l'état actuel de la base :

```bash
railway run python scripts/migrate_and_fix_invitations.py
```

Le script affichera :
- Nombre total d'invitations
- Pourcentage de colonnes NULL
- Échantillon de données raw
- Résultat de la migration

## Support

En cas de problème, vérifier les logs de l'application :

```bash
railway logs
```

Ou créer une issue sur GitHub avec :
- Capture d'écran du tableau vide
- Extrait du fichier Excel (3-5 lignes)
- Logs de l'application
