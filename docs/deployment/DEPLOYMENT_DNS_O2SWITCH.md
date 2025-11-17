# Configuration DNS : Domaine o2switch → Application Railway

Guide pas à pas pour faire pointer votre domaine o2switch vers votre application Railway.

## 🎯 Objectif

Faire en sorte que `votre-domaine.com` (ou `www.votre-domaine.com`) affiche votre application FastAPI hébergée sur Railway.

---

## 📋 Ce dont vous avez besoin

- ✅ Domaine acheté sur o2switch
- ✅ Accès cPanel o2switch
- ✅ Application déployée sur Railway
- ✅ Compte Railway actif

---

## 🚀 Étape 1 : Obtenir l'URL de votre application Railway

### 1.1. Se connecter à Railway

1. Allez sur https://railway.app
2. Connectez-vous à votre compte
3. Sélectionnez votre projet `outilspapv2`

### 1.2. Noter l'URL publique

Dans votre projet Railway :
1. Cliquez sur votre service (app)
2. Allez dans l'onglet **"Settings"**
3. Cherchez la section **"Domains"**
4. Vous verrez une URL comme :
   ```
   outilspapv2-production.up.railway.app
   ```

**Notez cette URL**, vous en aurez besoin.

---

## 🌐 Étape 2 : Ajouter votre domaine custom dans Railway

### 2.1. Dans Railway, ajouter un custom domain

1. Toujours dans **Settings → Domains**
2. Cliquez sur **"+ Custom Domain"**
3. Entrez votre domaine : `votre-domaine.com`
4. Railway vous donne alors les informations DNS à configurer :

   **Option A : CNAME (Recommandé)**
   ```
   Type: CNAME
   Name: @  (ou www)
   Value: outilspapv2-production.up.railway.app
   ```

   **Option B : A Record**
   ```
   Type: A
   Name: @
   Value: xxx.xxx.xxx.xxx (IP fournie par Railway)
   ```

**Notez ces informations DNS**, nous allons les configurer sur o2switch.

---

## 🔧 Étape 3 : Configurer les DNS sur o2switch

### 3.1. Accéder à la zone DNS dans cPanel

1. Connectez-vous à votre **cPanel o2switch**
2. Dans la section **"DOMAINES"** ou **"DOMAINS"**, cherchez :
   - **"Zone Editor"** ou **"Éditeur de zone"**
   - OU **"Advanced Zone Editor"**
3. Cliquez dessus

### 3.2. Sélectionner votre domaine

1. Dans la liste, trouvez votre domaine `votre-domaine.com`
2. Cliquez sur **"Manage"** ou **"Gérer"**

### 3.3. Ajouter/Modifier les enregistrements DNS

#### Pour `votre-domaine.com` (sans www)

**Méthode CNAME (Recommandé) :**

1. Cherchez un enregistrement de type `A` pour `@` ou votre domaine principal
2. **Supprimez-le** (ou notez l'IP pour pouvoir revenir en arrière)
3. Cliquez sur **"Add Record"** ou **"Ajouter un enregistrement"**
4. Remplissez :
   - **Type** : `CNAME`
   - **Name** : `@` (ou laissez vide)
   - **Record** / **Value** : `outilspapv2-production.up.railway.app`
   - **TTL** : `14400` (4 heures) ou laissez par défaut
5. Cliquez sur **"Add Record"**

**⚠️ Attention** : Certains hébergeurs n'autorisent pas CNAME sur `@` (domaine racine). Si ça ne fonctionne pas, utilisez la méthode A Record ci-dessous.

**Méthode A Record (Alternative) :**

1. Cherchez l'enregistrement de type `A` pour `@`
2. **Modifiez-le** ou créez-en un nouveau :
   - **Type** : `A`
   - **Name** : `@`
   - **Address** / **Value** : L'IP fournie par Railway (ex: `35.123.45.67`)
   - **TTL** : `14400`
3. Sauvegardez

#### Pour `www.votre-domaine.com`

1. Cliquez sur **"Add Record"**
2. Remplissez :
   - **Type** : `CNAME`
   - **Name** : `www`
   - **Record** : `outilspapv2-production.up.railway.app`
   - **TTL** : `14400`
3. Sauvegardez

### 3.4. Vérifier la configuration DNS

Votre zone DNS devrait ressembler à ça :

```
Type    Name    Value/Target
────────────────────────────────────────────────────────
A       @       35.123.45.67 (IP Railway)
CNAME   www     outilspapv2-production.up.railway.app
```

**OU (si CNAME sur @ fonctionne) :**

```
Type    Name    Value/Target
────────────────────────────────────────────────────────
CNAME   @       outilspapv2-production.up.railway.app
CNAME   www     outilspapv2-production.up.railway.app
```

---

## ⏱️ Étape 4 : Attendre la propagation DNS

### 4.1. Temps d'attente

La propagation DNS prend généralement :
- **10-30 minutes** : Première propagation
- **24-48 heures** : Propagation mondiale complète

### 4.2. Vérifier la propagation DNS

Utilisez ces outils pour vérifier :

**Méthode 1 : En ligne de commande**
```bash
# Vérifier l'enregistrement A
dig votre-domaine.com

# Vérifier le CNAME
dig www.votre-domaine.com

# Ou avec nslookup
nslookup votre-domaine.com
```

**Méthode 2 : Outils en ligne**
- https://dnschecker.org/
- https://www.whatsmydns.net/

Entrez `votre-domaine.com` et vérifiez que l'IP ou CNAME correspond à Railway.

---

## 🔒 Étape 5 : Configurer SSL/HTTPS (Gratuit)

Railway génère automatiquement un certificat SSL Let's Encrypt pour votre domaine custom.

### 5.1. Attendre l'émission du certificat

Après avoir ajouté le domaine dans Railway :
1. Dans **Railway → Settings → Domains**
2. Vous verrez votre domaine avec un statut :
   - 🟡 **"Pending"** : En attente de la configuration DNS
   - 🟢 **"Active"** : DNS configuré, certificat émis

**Temps d'attente** : 5-15 minutes après la propagation DNS

### 5.2. Forcer HTTPS

Dans Railway, vous pouvez forcer la redirection HTTP → HTTPS :
1. Allez dans **Settings → Variables**
2. Ajoutez (si ce n'est pas déjà fait) :
   ```
   FORCE_HTTPS=true
   ```

---

## ✅ Étape 6 : Tester votre domaine

### 6.1. Accéder à votre site

Ouvrez votre navigateur et allez sur :
```
https://votre-domaine.com
```

Vous devriez voir votre application PAP/CSE !

### 6.2. Vérifier le SSL

1. Cliquez sur le cadenas 🔒 dans la barre d'adresse
2. Vérifiez que le certificat est valide
3. Émetteur : Let's Encrypt

### 6.3. Tester les deux versions

```
https://votre-domaine.com       ✅
https://www.votre-domaine.com   ✅
```

Les deux devraient fonctionner.

---

## 🐛 Dépannage

### Problème : "This site can't be reached" ou "DNS_PROBE_FINISHED_NXDOMAIN"

**Cause** : DNS pas encore propagé

**Solution** :
1. Attendez 30 minutes à 1 heure
2. Vérifiez la configuration DNS dans cPanel
3. Utilisez https://dnschecker.org/ pour voir la propagation mondiale

### Problème : "SSL Certificate Error" ou "Not Secure"

**Cause** : Le certificat SSL n'est pas encore émis par Railway

**Solution** :
1. Vérifiez dans Railway → Domains que le statut est "Active"
2. Attendez 10-15 minutes supplémentaires
3. Videz le cache de votre navigateur (Ctrl+Shift+R)

### Problème : Le site affiche "Railway Default Page"

**Cause** : Le domaine n'est pas correctement configuré dans Railway

**Solution** :
1. Dans Railway → Settings → Domains
2. Vérifiez que `votre-domaine.com` est bien listé
3. Supprimez et rajoutez le domaine si nécessaire

### Problème : CNAME sur @ ne fonctionne pas

**Cause** : o2switch n'autorise pas les CNAME sur le domaine racine

**Solution** :
1. Utilisez un enregistrement `A` avec l'IP fournie par Railway
2. Ou utilisez un sous-domaine : `app.votre-domaine.com`

---

## 🎨 Option : Utiliser un sous-domaine

Si vous préférez `app.votre-domaine.com` :

### Dans Railway
1. Ajoutez le custom domain : `app.votre-domaine.com`

### Dans o2switch (cPanel → Zone Editor)
```
Type    Name    Value
────────────────────────────────────────────────
CNAME   app     outilspapv2-production.up.railway.app
```

C'est tout ! Beaucoup plus simple.

---

## 📊 Comparaison : Domaine principal vs Sous-domaine

| Aspect | Domaine principal | Sous-domaine |
|--------|------------------|--------------|
| **URL** | `votre-domaine.com` | `app.votre-domaine.com` |
| **Configuration** | Parfois complexe (CNAME sur @) | Très simple |
| **SSL** | Automatique | Automatique |
| **Recommandation** | Pour un site principal | Pour une application spécifique |

---

## 🔄 Garder Railway et o2switch séparés

### Ce qui reste sur Railway
- ✅ Application FastAPI (backend)
- ✅ Base de données SQLite
- ✅ APIs et logique métier
- ✅ Déploiements automatiques (git push)
- ✅ Logs et monitoring

### Ce que vous utilisez d'o2switch
- ✅ Nom de domaine
- ✅ Configuration DNS
- ✅ (Optionnel) Emails @votre-domaine.com

### Avantages de cette approche
- 🚀 Railway gère toute la complexité technique
- 🔄 Déploiements automatiques depuis GitHub
- 📊 Logs et monitoring intégrés
- 💰 Coût optimisé (Railway pour l'app, o2switch pour le domaine)
- 🔧 Pas de configuration serveur complexe

---

## 📧 Bonus : Configurer les emails sur o2switch

Vous pouvez toujours utiliser o2switch pour vos emails `contact@votre-domaine.com` :

1. Dans cPanel → **"Email Accounts"**
2. Créez vos adresses email
3. Les emails fonctionneront indépendamment de votre application Railway

---

## 📝 Checklist de configuration

- [ ] URL Railway notée (`xxx.up.railway.app`)
- [ ] Custom domain ajouté dans Railway
- [ ] Informations DNS notées (CNAME ou A)
- [ ] Zone DNS configurée dans cPanel o2switch
- [ ] Enregistrement A ou CNAME pour `@`
- [ ] Enregistrement CNAME pour `www`
- [ ] Attente propagation DNS (30 min - 2h)
- [ ] Vérification DNS avec `dig` ou dnschecker.org
- [ ] Certificat SSL actif dans Railway
- [ ] Site accessible sur `https://votre-domaine.com`
- [ ] Site accessible sur `https://www.votre-domaine.com`
- [ ] Tests fonctionnels complets

---

## 🎉 Félicitations !

Votre application est maintenant accessible sur votre propre domaine !

### Prochaines étapes possibles

1. ✅ Configurer les emails professionnels sur o2switch
2. ✅ Ajouter Google Analytics (optionnel)
3. ✅ Configurer un CDN comme Cloudflare (optionnel, pour performances)
4. ✅ Mettre en place des sauvegardes automatiques
5. ✅ Configurer des alertes de monitoring

---

**Date de création** : 2025-11-15
**Version** : 1.0
**Configuration** : o2switch (DNS) → Railway (App)
