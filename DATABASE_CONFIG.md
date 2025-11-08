# Configuration de la base de données

## Téléchargement automatique de papcse.db

L'application télécharge automatiquement la base de données `papcse.db` depuis GitHub Release au premier démarrage si elle n'existe pas localement.

## Configuration sur Railway

### Étape 1 : Ajouter la variable d'environnement

Dans Railway, allez dans les **Variables** de votre projet et ajoutez :

```
DB_URL=https://github.com/quentin12200/outilspapv2/releases/download/v1.0.0/papcse.db
DB_SHA256=2a699fe2236005cadc756ec59f8f21fa35fd542262823b9998b7fc49192d445d
```

### Étape 2 : Redémarrer l'application

Railway redémarrera automatiquement l'application après l'ajout de la variable.

### Étape 3 : Vérifier le téléchargement

Dans les logs Railway, vous devriez voir :

```
Downloading database from GitHub Release...
Database downloaded successfully!
```

## Variables d'environnement disponibles

| Variable | Description | Requis |
|----------|-------------|--------|
| `DB_URL` | URL de téléchargement de papcse.db depuis GitHub Release | ✅ Oui |
| `DB_SHA256` | Hash SHA256 pour vérifier l'intégrité (optionnel) | ❌ Non |
| `DB_GH_TOKEN` | Token GitHub si repo privé (optionnel) | ❌ Non |
| `DB_FAIL_ON_HASH_MISMATCH` | Échouer si le hash ne correspond pas (défaut: false) | ❌ Non |
| `DATABASE_URL` | Chemin local de la base SQLite (défaut: `sqlite:///./papcse.db`) | ❌ Non |
| `INVITATIONS_URL` | (Optionnel) Fichier Excel contenant les invitations PAP à charger automatiquement (sinon, tentative sur la même release que `DB_URL`) | ❌ Non |
| `INVITATIONS_SHA256` | Hash SHA256 du fichier d'invitations (recommandé si `INVITATIONS_URL`) | ❌ Non |
| `INVITATIONS_GH_TOKEN` | Token GitHub si l'asset invitations est privé (défaut : `DB_GH_TOKEN`) | ❌ Non |
| `INVITATIONS_FAIL_ON_HASH_MISMATCH` | Échouer si le hash des invitations ne correspond pas | ❌ Non |

## Fonctionnement

### Au démarrage de l'application :

1. ✅ L'application vérifie si `papcse.db` existe localement
2. ⬇️ Si absent ET `DB_URL` est défini → télécharge depuis GitHub
3. ✅ Si le hash `DB_SHA256` est fourni → vérifie l'intégrité
4. 📩 Si `INVITATIONS_URL` est défini **ou si un fichier est trouvé automatiquement sur la même release** et que la table `invitations` est vide → import automatique du fichier Excel (une seule fois)
5. 🚀 Démarre avec la base de données

### Mise à jour de la base :

Pour forcer une mise à jour de la base :

1. **Sur Railway** : Supprimez le volume persistent (si utilisé) et redémarrez
2. **En local** : Supprimez `papcse.db` et relancez l'application

## Structure de la base v1.0.0

La version v1.0.0 de la base contient :

### Tables principales :

- **`siret_summary`** : Synthèse par SIRET avec tous les scores syndicaux (C3, C4)
- **`Tous_PV`** : Détails de tous les PV avec scores de TOUS les syndicats
- **`invitations`** : Invitations PAP Cycle 5

### Nouvelles colonnes v1.0.0 :

#### Scores syndicaux complets :
- CGT, CFDT, FO, CFTC, CGC, UNSA, SUD, SOLIDAIRES, AUTRE

#### Métadonnées enrichies :
- Région, UL, OETAMIC, quadrimestre
- CAC 40 / SBF 120 (code, nom du groupe)
- Composition des effectifs (Ouvriers, Employés, Techniciens, etc.)
- Infos SIREN (groupe) : effectifs, scores agrégés
- Calendrier : durée mandat, date prochain scrutin

#### Agrégations SIRET :
- Scores et présences agrégés au niveau SIRET
- Pourcentages par syndicat
- Nombre de collèges, effectifs par tranche

## Taille du fichier

📦 **Taille approximative** : ~80 Mo

⚠️ **Trop gros pour GitHub** : C'est pourquoi nous utilisons GitHub Releases

✅ **Solution** : Téléchargement automatique au démarrage

## Dépannage

### Erreur : "Failed to download database"

**Causes possibles :**
- URL incorrecte dans `DB_URL`
- Repo privé sans `DB_GH_TOKEN`
- Problème réseau

**Solution :**
1. Vérifiez l'URL dans Railway
2. Consultez les logs pour voir l'erreur exacte
3. Si repo privé, ajoutez `DB_GH_TOKEN`

### Erreur : "SHA256 mismatch"

**Cause :** Le hash du fichier téléchargé ne correspond pas à `DB_SHA256`

**Solution :**
1. Vérifiez que `DB_SHA256` correspond bien à la release v1.0.0
2. Ou supprimez `DB_SHA256` des variables (vérification désactivée)

### La base ne se télécharge pas

**Cause :** La base existe déjà localement

**Solution :**
- En production : La base ne sera téléchargée qu'une seule fois
- Pour forcer : Supprimez le fichier et redémarrez

## Exemple de configuration complète

```env
# Base de données
DATABASE_URL=sqlite:///./papcse.db
DB_URL=https://github.com/quentin12200/outilspapv2/releases/download/v1.0.0/papcse.db

# Optionnel : vérification d'intégrité (hash v1.0.0)
DB_SHA256=2a699fe2236005cadc756ec59f8f21fa35fd542262823b9998b7fc49192d445d

# Optionnel : invitations PAP préchargées
# (sinon placer un fichier `papcse-invitations.xlsx` ou `.csv` sur la même release)
# INVITATIONS_URL=https://github.com/quentin12200/outilspapv2/releases/download/v1.0.0/invitations.xlsx
# INVITATIONS_SHA256=...

# Optionnel : si repo privé
# DB_GH_TOKEN=ghp_xxxxx
```

## Page Admin

Une fois l'application démarrée, vous pouvez voir le statut de la base dans la page **Admin** :

🔗 `https://votre-app.up.railway.app/admin`

La section **"Base de données (papcse.db)"** affiche :
- ✅ Statut (Base chargée)
- 🏷️ Version (v1.0.0)
- 🔗 URL de téléchargement

---

**Questions ?** Consultez les logs Railway ou la documentation FastAPI.
