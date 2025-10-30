# 🚀 Configuration Railway avec API Sirene

## ✅ Configuration Simple (Recommandée)

### Variables Railway

Gardez vos variables **existantes** pour télécharger votre base de données :

```env
DB_URL=https://github.com/quentin12200/outilspapv2/releases/download/vX.X.X/votre-base.db
DB_SHA256=votre-sha256-existant
```

**C'est tout !** Pas besoin d'autres variables.

### 🔧 Comment ça fonctionne

1. **Au démarrage** :
   - L'application télécharge votre base depuis GitHub (si `DB_URL` est configuré)
   - SQLAlchemy crée les tables si elles n'existent pas
   - **Migration automatique** : Les colonnes Sirene sont ajoutées automatiquement si elles manquent

2. **Migration automatique des colonnes Sirene** :
   - Vérifie si les 13 colonnes Sirene existent dans la table `invitations`
   - Si elles manquent, les ajoute automatiquement :
     - `denomination` - Raison sociale
     - `enseigne` - Enseigne commerciale
     - `adresse` - Adresse complète
     - `code_postal` - Code postal
     - `commune` - Commune
     - `activite_principale` - Code NAF
     - `libelle_activite` - Libellé de l'activité
     - `tranche_effectifs` - Code tranche d'effectifs
     - `effectifs_label` - Libellé de la tranche
     - `est_siege` - Booléen siège social
     - `est_actif` - Booléen établissement actif
     - `categorie_entreprise` - PME, ETI, GE...
     - `date_enrichissement` - Date du dernier enrichissement

3. **L'API Sirene fonctionne** :
   - `/api/sirene/stats` - Statistiques sur l'enrichissement
   - `/api/sirene/enrichir-tout` - Enrichir toutes les invitations
   - `/recherche-siret` - Recherche et enrichissement individuel

## 📋 Étapes de Déploiement

### 1. Vérifier vos variables Railway

Dans **Railway → Votre Projet → Variables**, assurez-vous d'avoir :

```env
DB_URL=https://github.com/quentin12200/outilspapv2/releases/download/vX.X.X/votre-base.db
DB_SHA256=le-sha256-de-votre-base
```

**Notes** :
- Si votre repo est **public** : PAS besoin de `DB_GH_TOKEN`
- Si votre repo est **privé** : Ajoutez `DB_GH_TOKEN=ghp_xxxxx`

### 2. Déployer

Railway redéploiera automatiquement. Sinon :
- Railway → Deployments → Redeploy

### 3. Vérifier les logs

Dans **Railway → Deployments → View Logs**, vous devriez voir :

```
INFO:     Application startup complete.
```

**Pas d'erreur 404 ou 500 !**

### 4. Tester l'API Sirene

Ouvrez votre application et testez :

- **Page principale** : `https://votre-app.railway.app/`
- **Stats API Sirene** : `https://votre-app.railway.app/api/sirene/stats`
- **Recherche SIRET** : `https://votre-app.railway.app/recherche-siret`

## 🐛 Dépannage

### Erreur 404 au démarrage

**Cause** : Le fichier n'existe pas à l'URL GitHub Release
**Solution** : Vérifiez que `DB_URL` pointe vers un fichier existant

### Erreur 500 sur /api/sirene/*

**Cause** : Problème avec l'API INSEE ou les données
**Solution** :
1. Vérifiez les logs Railway pour plus de détails
2. Testez l'API INSEE directement : https://api.insee.fr/entreprises/sirene/V3/siret/VOTRE_SIRET

### Les colonnes Sirene ne s'affichent pas

**Cause** : Migration automatique n'a pas fonctionné
**Solution** :
1. Vérifiez les logs Railway au démarrage
2. Les logs devraient montrer "Migration terminée" ou "Colonnes déjà existantes"

## 🎯 Alternative : Base SQLite sans téléchargement

Si vous ne voulez **pas** télécharger de base depuis GitHub :

1. **Supprimez** les variables :
   - `DB_URL`
   - `DB_SHA256`
   - `DB_GH_TOKEN`

2. L'application créera automatiquement une base SQLite vide avec toutes les colonnes

⚠️ **Attention** : Les données seront perdues à chaque redéploiement sur Railway (le système de fichiers est éphémère)

## 📚 Fichiers Modifiés

- `app/migrations.py` - Script de migration automatique
- `app/main.py:89-96` - Intégration de la migration au startup

## ✅ Avantages de cette Approche

✅ **Aucune intervention manuelle** : Migration automatique au démarrage
✅ **Idempotente** : Peut être exécutée plusieurs fois sans problème
✅ **Sûre** : N'ajoute que les colonnes manquantes
✅ **Compatible** : Fonctionne avec vos bases existantes

---

🎉 **Votre API Sirene est maintenant configurée et prête à fonctionner sur Railway !**
