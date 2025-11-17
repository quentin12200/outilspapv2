# Configuration Railway pour l'extraction GPT

## 📋 Prérequis

Avant de déployer sur Railway, assurez-vous d'avoir :

1. ✅ Un compte OpenAI avec une clé API valide
2. ✅ Des crédits sur votre compte OpenAI (~$5-10 minimum)
3. ✅ Un projet Railway configuré

## 🚀 Étapes de configuration

### 1. Créer et configurer la clé API OpenAI

#### a) Créer une nouvelle clé (si pas encore fait)

1. Allez sur https://platform.openai.com/api-keys
2. Cliquez sur **"Create new secret key"**
3. Donnez un nom : `Railway - OutilsPAP`
4. **Copiez immédiatement la clé** (elle ne sera plus visible après)
5. Format : `sk-proj-xxxxx...`

#### b) Ajouter des crédits

1. Allez sur https://platform.openai.com/settings/organization/billing
2. Cliquez sur **"Add payment method"**
3. Ajoutez $5-10 pour commencer
4. Configurez les limites de dépenses si souhaité

### 2. Configurer Railway

#### Option A : Via l'interface Railway (Recommandé)

1. **Connectez-vous à Railway** : https://railway.app/

2. **Sélectionnez votre projet** `outilspapv2`

3. **Ouvrez les Variables d'environnement** :
   - Cliquez sur votre service
   - Onglet **"Variables"**
   - Ou utilisez le raccourci `CMD/CTRL + K` → "Variables"

4. **Ajoutez la variable `OPENAI_API_KEY`** :
   ```
   Variable name:  OPENAI_API_KEY
   Value:         sk-proj-VOTRE_CLE_COMPLETE_ICI
   ```

5. **Cliquez sur "Add"** puis **"Deploy"**

#### Option B : Via Railway CLI

```bash
# Se connecter
railway login

# Sélectionner le projet
railway link

# Ajouter la variable
railway variables set OPENAI_API_KEY=sk-proj-VOTRE_CLE_ICI

# Déployer
railway up
```

### 3. Vérifier que les autres variables sont configurées

Assurez-vous que ces variables sont aussi présentes (selon `.env.railway.example`) :

| Variable | Description | Obligatoire |
|----------|-------------|-------------|
| `DB_URL` | URL de téléchargement de la base | ✅ Oui |
| `DB_SHA256` | Hash de la base | ⚠️ Recommandé |
| `OPENAI_API_KEY` | Clé OpenAI | ✅ Oui (nouvelle) |
| `SIRENE_API_KEY` | Clé API Sirene | ⚠️ Recommandé |

**Exemple de configuration complète :**

```bash
# Base de données
DB_URL=https://github.com/quentin12200/outilspapv2/releases/download/v1.0.0/papcse.db
DB_SHA256=36f5a979939849c7429d2ea3f06d376de3485dc645b59daf26b2be2eb866d6b8

# OpenAI (NOUVEAU)
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Sirene (optionnel)
SIRENE_API_KEY=votre_cle_sirene_ici
```

### 4. Déployer la nouvelle branche

#### a) Via l'interface Railway

1. Allez dans **Settings → Source**
2. Dans **"Branch"**, changez vers : `claude/add-gpt-extraction-011CUrhaod8vzkG7ZHeXooi3`
3. Cliquez sur **"Deploy"**

OU

#### b) Merger la branche et déployer depuis main

```bash
# Localement
git checkout main
git merge claude/add-gpt-extraction-011CUrhaod8vzkG7ZHeXooi3
git push origin main
```

Railway déploiera automatiquement.

### 5. Vérifier le déploiement

Une fois déployé, vérifiez que tout fonctionne :

#### a) Vérifier les logs

Dans Railway :
1. Cliquez sur votre service
2. Onglet **"Deployments"**
3. Cliquez sur le dernier déploiement
4. Consultez les logs

**Logs attendus :**
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

**Pas d'erreur de type :**
```
❌ DocumentExtractorError: Clé API OpenAI manquante
```

#### b) Tester l'endpoint de santé

```bash
# Remplacez YOUR-APP.railway.app par votre URL Railway
curl https://YOUR-APP.railway.app/api/extract/health
```

**Réponse attendue :**
```json
{
  "status": "operational",
  "openai_configured": true,
  "message": "Service d'extraction prêt"
}
```

**Si non configuré :**
```json
{
  "status": "not_configured",
  "openai_configured": false,
  "message": "Clé OpenAI non configurée..."
}
```

#### c) Tester l'interface web

1. Allez sur `https://YOUR-APP.railway.app/extraction`
2. Vérifiez que le statut indique **"✓ Opérationnel"** (en vert)
3. Uploadez une image de test
4. Vérifiez que l'extraction fonctionne

## 🔒 Sécurité

### Bonnes pratiques

✅ **À FAIRE :**
- Stocker la clé API uniquement dans les variables d'environnement Railway
- Configurer des limites de dépenses sur OpenAI
- Surveiller l'utilisation via https://platform.openai.com/usage
- Révoquer et renouveler la clé régulièrement

❌ **À NE JAMAIS FAIRE :**
- Commiter la clé dans le code source
- Partager la clé publiquement (chat, email, Slack)
- Utiliser la même clé pour plusieurs environnements
- Afficher la clé dans les logs

### Limiter les coûts

Sur OpenAI Platform :
1. **Settings → Limits**
2. Configurez :
   - Monthly budget : $10-50 (selon votre usage)
   - Email alerts : Activé à 80% et 100%

## 📊 Monitoring et coûts

### Surveiller l'utilisation

1. **OpenAI Dashboard** : https://platform.openai.com/usage
   - Consultez l'utilisation quotidienne
   - Coût par requête
   - Nombre de tokens utilisés

2. **Railway Logs**
   - Chaque extraction log le coût estimé
   - Format : `Extraction réussie - SIRET: xxx - Cost: $0.02`

### Estimation des coûts

| Usage | Documents/mois | Coût estimé |
|-------|----------------|-------------|
| Faible | 10-50 | $0.50 - $1.50 |
| Moyen | 100-200 | $2 - $6 |
| Élevé | 500-1000 | $10 - $30 |

**Modèle utilisé :** GPT-4o (~$0.01-0.03 par document)

## 🐛 Dépannage

### "Service non configuré" sur Railway

**Symptômes :**
- Page /extraction affiche "✗ Non configuré"
- Endpoint /api/extract/health retourne `openai_configured: false`

**Solutions :**
1. Vérifiez que `OPENAI_API_KEY` est bien dans les variables Railway
2. Vérifiez qu'il n'y a pas d'espaces avant/après la clé
3. Redéployez le service
4. Consultez les logs Railway

### "Invalid API Key"

**Solutions :**
1. Vérifiez que la clé commence par `sk-proj-`
2. Testez la clé avec curl :
```bash
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer sk-proj-VOTRE_CLE"
```
3. Générez une nouvelle clé si nécessaire

### Coûts trop élevés

**Solutions :**
1. Configurez des limites de dépenses sur OpenAI
2. Vérifiez l'utilisation : https://platform.openai.com/usage
3. Optimisez les images avant upload
4. Utilisez `temperature=0.1` (déjà configuré)

### Erreur de déploiement sur Railway

```
ERROR: Could not install packages due to an OSError
```

**Solution :**
Les dépendances sont correctes dans requirements.txt. Railway devrait installer :
- `openai==1.54.3`
- `pillow==10.4.0`

Si problème, vérifiez les logs de build Railway.

## 📞 Support

### OpenAI
- Documentation : https://platform.openai.com/docs
- Support : https://help.openai.com/

### Railway
- Documentation : https://docs.railway.app/
- Discord : https://discord.gg/railway

## ✅ Checklist de déploiement

Avant de déclarer le déploiement réussi :

- [ ] Clé API OpenAI créée et configurée sur Railway
- [ ] Variable `OPENAI_API_KEY` présente dans Railway
- [ ] Branche déployée sur Railway
- [ ] Logs Railway sans erreur
- [ ] `/api/extract/health` retourne `operational`
- [ ] Page `/extraction` accessible
- [ ] Statut "✓ Opérationnel" visible
- [ ] Test d'extraction réussi avec une image
- [ ] Limites de coûts configurées sur OpenAI
- [ ] Monitoring activé

---

**Dernière mise à jour :** 8 novembre 2024
