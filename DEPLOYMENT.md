# 🚀 Guide de Déploiement - Railway

Ce guide explique comment déployer l'application sur Railway avec téléchargement automatique de la base de données depuis GitHub Releases.

## 📦 Prérequis

1. Compte Railway (https://railway.app)
2. Base de données `pap.db` uploadée sur GitHub Releases
3. Variables d'environnement configurées

## 🔧 Configuration Railway

### 1. Variables d'environnement obligatoires

Allez dans **Railway → Votre Projet → Variables** et ajoutez :

#### `DB_URL` (obligatoire)
URL directe vers le fichier de base de données sur GitHub Releases.

**Format** :
```
https://github.com/VOTRE_USERNAME/VOTRE_REPO/releases/download/TAG/FICHIER.db
```

**Exemple** :
```
https://github.com/quentin12200/outilspapv2/releases/download/v1.0.0/pap.db
```

#### `DB_SHA256` (recommandé)
Hash SHA256 du fichier pour vérifier son intégrité.

**Pour l'obtenir** :
```bash
# À la racine du projet
./scripts/get_db_sha256.sh
```

Ou manuellement :
```bash
sha256sum pap.db
# ou sur macOS
shasum -a 256 pap.db
```

**Exemple** :
```
40ffd2d5576c673e78f6f5816d90619c5e5674e01d81359e976bf81729f5b769
```

#### `DB_GH_TOKEN` (optionnel)
Seulement nécessaire si votre repository est **privé**.

**Pour le créer** :
1. GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Generate new token
3. Sélectionnez le scope `repo`
4. Copiez le token et ajoutez-le dans Railway

### 2. Autres variables d'environnement

Railway configure automatiquement `PORT`. Pas besoin de le définir.

## 🎯 Comment ça fonctionne

### Au démarrage de l'application :

1. **Vérification** : L'app vérifie si `pap.db` existe déjà
2. **Téléchargement** : Si absent, télécharge depuis `DB_URL`
3. **Validation** : Si `DB_SHA256` est fourni, vérifie l'intégrité
4. **Démarrage** : L'application démarre avec la base chargée

### Code concerné :

Le code de bootstrap se trouve dans `app/main.py` :

```python
DB_URL = os.getenv("DB_URL", "").strip()
DB_SHA256 = os.getenv("DB_SHA256", "").lower().strip()
DB_GH_TOKEN = os.getenv("DB_GH_TOKEN", "").strip() or None

ensure_sqlite_asset()  # Télécharge automatiquement
```

## 📝 Checklist de déploiement

- [ ] Base de données uploadée sur GitHub Releases
- [ ] Variable `DB_URL` configurée sur Railway
- [ ] Variable `DB_SHA256` configurée (recommandé)
- [ ] Variable `DB_GH_TOKEN` configurée (si repo privé)
- [ ] Application déployée sur Railway
- [ ] Vérifier les logs Railway pour confirmer le téléchargement
- [ ] Tester l'accès à l'application

## 🐛 Dépannage

### Erreur : "SHA256 mismatch"
Le fichier téléchargé ne correspond pas au hash fourni.

**Solution** :
1. Régénérez le SHA256 : `./scripts/get_db_sha256.sh`
2. Mettez à jour la variable `DB_SHA256` sur Railway
3. Redéployez

### Erreur : "Failed to download database"
Impossible de télécharger le fichier.

**Solutions** :
- Vérifiez que l'URL `DB_URL` est correcte
- Si repo privé, vérifiez `DB_GH_TOKEN`
- Vérifiez que le release existe sur GitHub

### L'application démarre mais la base est vide
La base a été téléchargée mais est vide.

**Solution** :
- Vérifiez que vous avez uploadé le bon fichier sur GitHub Releases
- Téléchargez manuellement le fichier depuis l'URL pour vérifier son contenu

## 🔄 Mise à jour de la base de données

Pour mettre à jour la base en production :

1. **Uploadez la nouvelle version** sur GitHub Releases (nouveau tag)
2. **Mettez à jour `DB_URL`** avec la nouvelle URL du tag
3. **Recalculez le SHA256** et mettez à jour `DB_SHA256`
4. **Redéployez** l'application sur Railway

## 📚 Ressources

- [Documentation Railway](https://docs.railway.app)
- [GitHub Releases](https://docs.github.com/en/repositories/releasing-projects-on-github)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)

## ✅ Exemple complet de configuration

```env
# Variables Railway
DB_URL=https://github.com/quentin12200/outilspapv2/releases/download/v1.0.0/pap.db
DB_SHA256=40ffd2d5576c673e78f6f5816d90619c5e5674e01d81359e976bf81729f5b769
# DB_GH_TOKEN=ghp_xxxxxxxxxxxxx (seulement si repo privé)
```

---

🎉 **Votre application est prête pour Railway !**
