# Configuration OpenAI sur Railway

Ce guide vous explique comment configurer l'extraction automatique de courriers PAP via GPT-4 sur Railway.

## 🎯 Prérequis

1. ✅ Un compte OpenAI avec une clé API
2. ✅ Des crédits sur votre compte OpenAI (~$5-10 pour commencer)
3. ✅ Au moins un modèle GPT-4 activé dans votre projet OpenAI

## 🔑 Étape 1 : Obtenir votre clé API OpenAI

1. Allez sur [OpenAI Platform](https://platform.openai.com/)
2. Connectez-vous ou créez un compte
3. Allez dans **Settings** → **Billing** → Ajoutez des crédits
4. Allez dans **API Keys** : https://platform.openai.com/api-keys
5. Cliquez sur **"Create new secret key"**
6. **Copiez la clé** (elle commence par `sk-proj-...`)

   ⚠️ **IMPORTANT** : Vous ne pourrez voir cette clé qu'une seule fois !

## 📋 Étape 2 : Vérifier les modèles disponibles

1. Allez dans votre projet OpenAI : https://platform.openai.com/settings/organization/general
2. Vérifiez que vous avez accès à au moins **un** de ces modèles :
   - ✅ `gpt-4o` (recommandé)
   - ✅ `gpt-4o-2024-11-20`
   - ✅ `gpt-4o-2024-08-06`
   - ✅ `gpt-4o-mini`
   - ✅ `gpt-4-turbo`

💡 **Astuce** : L'application essaiera automatiquement plusieurs modèles dans l'ordre jusqu'à trouver un qui fonctionne !

## ⚙️ Étape 3 : Configurer Railway

### Via l'interface web Railway

1. **Connectez-vous à [Railway](https://railway.app/)**
2. **Sélectionnez votre projet** `outilspapv2`
3. **Cliquez sur votre service** (généralement nommé d'après votre repo)
4. **Allez dans l'onglet "Variables"**
5. **Cliquez sur "New Variable"**
6. **Ajoutez** :

```
Variable: OPENAI_API_KEY
Value: sk-proj-VOTRE_CLE_COPIEE_ETAPE_1
```

7. **(Optionnel)** Si vous voulez forcer un modèle spécifique, ajoutez aussi :

```
Variable: OPENAI_MODEL
Value: gpt-4o-2024-11-20
```

8. **Cliquez sur "Add"** ou "Save"

### Via la CLI Railway (alternatif)

```bash
railway variables set OPENAI_API_KEY="sk-proj-..."
railway variables set OPENAI_MODEL="gpt-4o"  # Optionnel
```

## 🚀 Étape 4 : Redéployer

Railway redéploiera automatiquement votre application quand vous ajoutez une variable.

Si ce n'est pas le cas :
1. Allez dans l'onglet **"Deployments"**
2. Cliquez sur **"Redeploy"** sur le dernier déploiement

Ou depuis la CLI :
```bash
railway up
```

## ✅ Étape 5 : Vérifier que ça fonctionne

Une fois l'application redéployée, testez l'extraction :

### Méthode 1 : Via l'interface web

1. Allez sur votre application : `https://votre-app.up.railway.app`
2. Menu **"Données PAP"** → **"Extraction automatique"**
3. Uploadez une photo de courrier PAP
4. Cliquez sur **"Extraire les informations"**

### Méthode 2 : Via l'API

```bash
curl -X GET "https://votre-app.up.railway.app/api/extract/health"
```

Réponse attendue :
```json
{
  "status": "operational",
  "openai_configured": true,
  "message": "Service d'extraction prêt"
}
```

Si vous voyez `"openai_configured": false`, la clé API n'est pas configurée correctement.

## 🔍 Système de fallback automatique

L'application essaiera **automatiquement plusieurs modèles** dans cet ordre :

1. `gpt-4o`
2. `gpt-4o-2024-11-20`
3. `gpt-4o-2024-08-06`
4. `gpt-4o-2024-05-13`
5. `gpt-4o-mini`
6. `gpt-4o-mini-2024-07-18`
7. `gpt-4-turbo`
8. `gpt-4-turbo-2024-04-09`

✅ **Avantage** : Vous n'avez pas besoin de configurer manuellement le modèle, le système trouvera automatiquement celui qui fonctionne !

## 🐛 Dépannage

### Erreur : "Clé API non configurée"

**Vérifications** :
1. La variable `OPENAI_API_KEY` est bien définie dans Railway
2. Il n'y a pas d'espaces avant/après la clé
3. L'application a bien été redéployée après l'ajout de la variable

**Solution** :
```bash
# Vérifier les variables
railway variables

# Si la variable n'apparaît pas, l'ajouter à nouveau
railway variables set OPENAI_API_KEY="sk-proj-..."
```

### Erreur : "Project does not have access to model"

**Cause** : Votre projet OpenAI n'a pas accès au modèle spécifié.

**Solution** :
1. **Ne rien faire** : Le système essaiera automatiquement les autres modèles
2. Ou vérifiez votre projet OpenAI et activez les modèles GPT-4
3. Ou ajoutez des crédits à votre compte OpenAI

### Erreur : "Invalid API key"

**Causes possibles** :
1. La clé est incorrecte ou a été révoquée
2. Il y a des espaces avant/après la clé

**Solution** :
1. Générez une nouvelle clé sur https://platform.openai.com/api-keys
2. Mettez à jour la variable sur Railway
3. Redéployez

### Erreur : "Insufficient credits"

**Cause** : Vous n'avez plus de crédits OpenAI.

**Solution** :
1. Allez sur https://platform.openai.com/settings/organization/billing
2. Ajoutez des crédits à votre compte

## 💰 Coûts estimés

Avec le système de fallback automatique, le modèle utilisé dépendra de ce qui est disponible :

- **gpt-4o** : ~$0.01-0.03 par document (~1-3 centimes)
- **gpt-4o-mini** : ~$0.001-0.003 par document (~0.1-0.3 centimes) ⭐ Très économique
- **gpt-4-turbo** : ~$0.02-0.05 par document (~2-5 centimes)

**Exemples** :
- 100 documents avec gpt-4o-mini : ~$0.10-0.30
- 1000 documents avec gpt-4o : ~$10-30

💡 Les images sont automatiquement optimisées pour réduire les coûts.

## 📊 Voir les logs

Pour voir quel modèle a été utilisé :

1. Sur Railway, allez dans **"Deployments"**
2. Cliquez sur le déploiement actif
3. Regardez les **logs**

Vous verrez :
```
Tentative d'extraction avec le modèle: gpt-4o
⚠️ Modèle gpt-4o non accessible, essai du suivant...
Tentative d'extraction avec le modèle: gpt-4o-2024-11-20
✅ Extraction réussie avec le modèle: gpt-4o-2024-11-20
```

## 🔒 Sécurité

✅ **Bonnes pratiques** :
- La clé API est stockée dans les variables d'environnement (sécurisé)
- Ne JAMAIS commiter la clé dans le code
- Ne JAMAIS partager la clé publiquement

❌ **À éviter** :
- Mettre la clé dans un fichier `.env` committé sur Git
- Partager des screenshots contenant la clé
- Afficher la clé dans les logs

## 📚 Ressources

- [Documentation OpenAI](https://platform.openai.com/docs)
- [Railway Documentation](https://docs.railway.app/)
- [Guide d'extraction GPT](./EXTRACTION_COURRIERS_GPT.md)

---

**Besoin d'aide ?** Consultez les logs de Railway ou la documentation OpenAI.
