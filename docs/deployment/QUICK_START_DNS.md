# 🚀 Guide Rapide : Connecter votre domaine o2switch à Railway

## 📋 Résumé en 3 étapes

### ✅ Étape 1 : Dans Railway (5 minutes)
1. Allez sur https://railway.app
2. Ouvrez votre projet `outilspapv2`
3. Cliquez sur **Settings → Domains**
4. Cliquez **"+ Custom Domain"**
5. Entrez : `votre-domaine.com`
6. **Notez les informations DNS affichées** (voir ci-dessous)

### ✅ Étape 2 : Dans cPanel o2switch (5 minutes)
1. Connectez-vous à votre **cPanel o2switch**
2. Allez dans **"Zone Editor"** (section Domaines)
3. Cliquez sur **"Manage"** pour votre domaine
4. Ajoutez les enregistrements DNS de Railway (voir ci-dessous)

### ✅ Étape 3 : Attendre (30 min - 2h)
1. Attendez la propagation DNS
2. Vérifiez sur https://dnschecker.org/
3. Accédez à `https://votre-domaine.com`

---

## 🎯 Informations DNS à configurer

### Configuration recommandée

**Dans o2switch cPanel → Zone Editor :**

```
┌─────────────────────────────────────────────────────┐
│ Enregistrement 1 : Domaine principal               │
├─────────────────────────────────────────────────────┤
│ Type:   A                                          │
│ Name:   @                                          │
│ Value:  [IP fournie par Railway]                  │
│ TTL:    14400                                      │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ Enregistrement 2 : Sous-domaine www                │
├─────────────────────────────────────────────────────┤
│ Type:   CNAME                                      │
│ Name:   www                                        │
│ Value:  [votre-app].up.railway.app                │
│ TTL:    14400                                      │
└─────────────────────────────────────────────────────┘
```

### Exemple concret

Si Railway vous donne :
- **URL** : `outilspapv2-production.up.railway.app`
- **IP** : `35.123.45.67`

Configurez dans o2switch :

```
Type    Name    Value
──────────────────────────────────────────────────────
A       @       35.123.45.67
CNAME   www     outilspapv2-production.up.railway.app
```

---

## 🔍 Comment récupérer les informations de Railway

### Méthode visuelle

1. **Railway → Projet → Settings → Domains**
2. Après avoir ajouté votre custom domain, Railway affiche :

```
┌──────────────────────────────────────────┐
│ Configure DNS Records                   │
├──────────────────────────────────────────┤
│                                          │
│ Add these DNS records to your domain:   │
│                                          │
│ Type: A                                  │
│ Name: @                                  │
│ Value: 35.123.45.67                      │
│                                          │
│ OR                                       │
│                                          │
│ Type: CNAME                              │
│ Name: @                                  │
│ Value: outilspapv2-production.up.railway.app │
│                                          │
└──────────────────────────────────────────┘
```

3. **Copiez ces valeurs** et configurez-les dans o2switch

---

## ⚡ Configuration alternative : Sous-domaine

Si vous préférez `app.votre-domaine.com` :

### Dans Railway
- Custom domain : `app.votre-domaine.com`

### Dans o2switch
```
Type    Name    Value
──────────────────────────────────────────────────────
CNAME   app     outilspapv2-production.up.railway.app
```

**Avantages** :
- ✅ Plus simple (pas de problème avec CNAME sur @)
- ✅ Garde votre domaine principal libre pour autre chose
- ✅ Configuration très rapide

---

## 🧪 Vérifier que ça fonctionne

### Test DNS (après 30 minutes)

```bash
# Vérifier votre domaine
dig votre-domaine.com

# Devrait afficher l'IP de Railway
# Answer section:
# votre-domaine.com.  14400  IN  A  35.123.45.67
```

### Test en ligne

1. Allez sur https://dnschecker.org/
2. Entrez `votre-domaine.com`
3. Vérifiez que l'IP correspond à Railway

### Test final

```
https://votre-domaine.com
```

➡️ Devrait afficher votre application !

---

## 🎨 Schéma de l'architecture

```
┌─────────────────────┐
│  Utilisateur        │
│  (Navigateur Web)   │
└──────────┬──────────┘
           │
           │ https://votre-domaine.com
           │
           ▼
┌─────────────────────┐
│   DNS o2switch      │ ← Configuration DNS dans cPanel
│                     │
│  votre-domaine.com  │ → 35.123.45.67 (IP Railway)
│  www → CNAME        │ → outilspapv2.up.railway.app
└──────────┬──────────┘
           │
           │ Redirection DNS
           │
           ▼
┌─────────────────────┐
│  Railway            │
│                     │
│  Application        │ ← Votre app FastAPI
│  FastAPI            │
│  + Base SQLite      │
│  + APIs             │
│                     │
│  SSL automatique ✅ │ ← Certificat Let's Encrypt
└─────────────────────┘
```

---

## 💰 Coûts

| Service | Coût | Usage |
|---------|------|-------|
| **o2switch** | ~5-7€/mois | Domaine + DNS (+ emails) |
| **Railway** | Gratuit ou 5$/mois | Hébergement application |
| **Total** | ~10-12€/mois | Infrastructure complète |

---

## ❓ FAQ Rapide

**Q : Combien de temps pour que le domaine fonctionne ?**
R : 30 minutes à 2 heures maximum

**Q : Est-ce que je perds mon site actuel sur o2switch ?**
R : Non, vous pouvez garder un site sur o2switch en utilisant un sous-domaine pour l'app Railway

**Q : Le SSL est automatique ?**
R : Oui, Railway génère automatiquement un certificat Let's Encrypt gratuit

**Q : Je peux utiliser www et sans www ?**
R : Oui, configurez les deux enregistrements DNS (voir ci-dessus)

**Q : Qu'est-ce qui se passe si Railway tombe ?**
R : Railway a un uptime de 99.9%. En cas de problème, revenez sur o2switch avec l'ancien DNS

**Q : Je peux garder mes emails @votre-domaine.com ?**
R : Oui ! Les emails sont gérés par des enregistrements MX séparés (ne touchez pas aux MX)

---

## 📞 Besoin d'aide ?

1. **Documentation complète** : Voir `DEPLOYMENT_DNS_O2SWITCH.md`
2. **Support Railway** : https://railway.app/help
3. **Support o2switch** : Via cPanel → Ouvrir un ticket
4. **Vérifier DNS** : https://dnschecker.org/

---

**Version** : 1.0
**Dernière mise à jour** : 2025-11-15
