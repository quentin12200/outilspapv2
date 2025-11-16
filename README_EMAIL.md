# 📧 Documentation - Système d'authentification par email

## 📋 Table des matières

1. [Vue d'ensemble](#vue-densemble)
2. [Fonctionnalités](#fonctionnalités)
3. [Configuration](#configuration)
4. [Migration de la base de données](#migration-de-la-base-de-données)
5. [Intégration dans l'application](#intégration-dans-lapplication)
6. [Utilisation des endpoints](#utilisation-des-endpoints)
7. [Tests](#tests)
8. [Déploiement sur Railway](#déploiement-sur-railway)
9. [Troubleshooting](#troubleshooting)

---

## 🎯 Vue d'ensemble

Ce système fournit une authentification complète par email pour l'application PAP CSE Dashboard, incluant :

- ✅ Inscription avec validation par email
- 🔒 Réinitialisation de mot de passe
- 📧 Envoi d'emails via SMTP o2switch
- 🎨 Templates HTML professionnels et responsifs
- 🔐 Sécurité renforcée (tokens expirables, bcrypt, etc.)

---

## ✨ Fonctionnalités

### 1. Inscription avec validation email

- L'utilisateur s'inscrit avec ses informations
- Un email de validation est envoyé automatiquement
- Le compte est créé mais **inactif** (`is_active=False`)
- L'utilisateur clique sur le lien de validation (valide 24h)
- Le compte est **activé** (`is_active=True`, `email_verified=True`)
- Un email de bienvenue est envoyé
- Le compte reste en attente d'**approbation admin** (`is_approved=False`)

### 2. Réinitialisation de mot de passe

- L'utilisateur demande une réinitialisation
- Un email avec un lien sécurisé est envoyé (valide 1h)
- L'utilisateur clique sur le lien et définit un nouveau mot de passe
- Le mot de passe est mis à jour et hashé avec bcrypt

### 3. Emails envoyés

| Type | Quand | Contenu |
|------|-------|---------|
| **Validation** | Après inscription | Lien pour valider l'email (24h) |
| **Bienvenue** | Après validation email | Confirmation et info sur approbation admin |
| **Reset password** | Demande oubli mot de passe | Lien pour réinitialiser (1h) |
| **Approbation** | Admin approuve le compte | Notification que l'accès est activé |

---

## ⚙️ Configuration

### 1. Variables d'environnement

Ajoutez ces variables dans votre fichier `.env` :

```bash
# === Configuration Email (o2switch) ===
# Serveur SMTP o2switch
MAIL_SERVER=chambre.o2switch.net
MAIL_PORT=465
MAIL_USE_SSL=True
MAIL_USE_TLS=False

# Identifiants SMTP
MAIL_USERNAME=contact@pap-cse.org
MAIL_PASSWORD=votre_mot_de_passe_smtp

# Expéditeur des emails
MAIL_DEFAULT_SENDER=contact@pap-cse.org
MAIL_FROM_NAME=PAP CSE Dashboard

# URL de l'application
APP_URL=https://app.pap-cse.org
```

### 2. Configuration Railway

Dans le dashboard Railway, ajoutez les variables suivantes :

1. Allez dans votre projet → **Variables**
2. Ajoutez chaque variable avec sa valeur :
   - `MAIL_SERVER` = `chambre.o2switch.net`
   - `MAIL_PORT` = `465`
   - `MAIL_USE_SSL` = `True`
   - `MAIL_USE_TLS` = `False`
   - `MAIL_USERNAME` = `contact@pap-cse.org`
   - `MAIL_PASSWORD` = `[votre mot de passe]`
   - `MAIL_DEFAULT_SENDER` = `contact@pap-cse.org`
   - `MAIL_FROM_NAME` = `PAP CSE Dashboard`
   - `APP_URL` = `https://app.pap-cse.org`

3. Redémarrez le service

---

## 🗄️ Migration de la base de données

### Option 1 : Script Python automatique (RECOMMANDÉ)

```bash
# Depuis la racine du projet
python scripts/migrate_add_email_fields.py
```

Ce script :
- ✅ Vérifie si les colonnes existent déjà
- ✅ Ajoute les colonnes manquantes
- ✅ Crée les index nécessaires
- ✅ Affiche un rapport détaillé

### Option 2 : SQL manuel

Si vous préférez exécuter manuellement :

```bash
sqlite3 papcse.db < scripts/migrate_add_email_fields.sql
```

### Colonnes ajoutées

| Colonne | Type | Description |
|---------|------|-------------|
| `email_verified` | BOOLEAN | Email vérifié (défaut: False) |
| `validation_token` | VARCHAR(255) | Token de validation email |
| `validation_token_expiry` | DATETIME | Expiration du token de validation |
| `reset_token` | VARCHAR(255) | Token de reset de mot de passe |
| `reset_token_expiry` | DATETIME | Expiration du token de reset |

### ⚠️ Utilisateurs existants

Les utilisateurs existants auront :
- `email_verified` = `False`
- `is_active` = `True` (si déjà actif)

Pour activer automatiquement les comptes existants :

```sql
UPDATE users SET email_verified = 1 WHERE is_active = 1;
```

---

## 🔌 Intégration dans l'application

### 1. Enregistrer le router

Dans `app/main.py`, ajoutez :

```python
from app.routers import auth_email

# Enregistrer le router
app.include_router(auth_email.router)
```

### 2. Structure des fichiers

```
outilspapv2/
├── app/
│   ├── email_service.py          # ✅ Module d'envoi d'emails
│   ├── models.py                 # ✅ Modifié (champs email ajoutés)
│   ├── user_auth.py              # ✅ Existant (pas modifié)
│   └── routers/
│       └── auth_email.py         # ✅ Nouvelles routes d'authentification
├── scripts/
│   ├── migrate_add_email_fields.py   # ✅ Script de migration Python
│   └── migrate_add_email_fields.sql  # ✅ Script SQL alternatif
├── test_email.py                 # ✅ Script de test interactif
├── .env.example                  # ✅ Mis à jour
└── README_EMAIL.md               # ✅ Cette documentation
```

---

## 🔗 Utilisation des endpoints

### 1. Inscription (`POST /auth/register`)

**Requête :**

```json
{
  "email": "user@example.com",
  "password": "MotDePasse123",
  "first_name": "Jean",
  "last_name": "Dupont",
  "phone": "0612345678",
  "organization": "CGT",
  "fd": "Métallurgie",
  "ud": "Paris",
  "region": "Île-de-France",
  "responsibility": "Secrétaire",
  "registration_reason": "Accès aux statistiques CSE"
}
```

**Réponse :**

```json
{
  "success": true,
  "message": "Inscription réussie ! Veuillez vérifier votre email pour valider votre compte.",
  "email": "user@example.com"
}
```

**Email envoyé :** Validation de compte (lien valide 24h)

---

### 2. Validation de compte (`GET /auth/validate-account?token=xxx`)

**Requête :**

```
GET /auth/validate-account?token=abc123...
```

**Réponse :**

```json
{
  "success": true,
  "message": "Votre compte a été validé avec succès ! Votre demande d'accès est en attente d'approbation par un administrateur."
}
```

**Email envoyé :** Bienvenue (confirmation de validation)

---

### 3. Mot de passe oublié (`POST /auth/forgot-password`)

**Requête :**

```json
{
  "email": "user@example.com"
}
```

**Réponse :**

```json
{
  "success": true,
  "message": "Si un compte existe avec cet email, vous recevrez un lien de réinitialisation dans quelques instants."
}
```

> **Note :** Pour des raisons de sécurité, le message est le même que l'email existe ou non.

**Email envoyé :** Reset de mot de passe (lien valide 1h)

---

### 4. Réinitialisation de mot de passe (`POST /auth/reset-password`)

**Requête :**

```json
{
  "token": "xyz789...",
  "new_password": "NouveauMotDePasse123"
}
```

**Réponse :**

```json
{
  "success": true,
  "message": "Votre mot de passe a été réinitialisé avec succès. Vous pouvez maintenant vous connecter."
}
```

---

## 🧪 Tests

### Test interactif complet

```bash
python test_email.py
```

Menu du script :
1. Tester la connexion SMTP
2. Envoyer un email de validation
3. Envoyer un email de reset
4. Envoyer un email de bienvenue
5. Envoyer un email d'approbation
6. Exécuter tous les tests
0. Quitter

### Test de connexion SMTP rapide

```python
from app.email_service import test_smtp_connection

success, message = test_smtp_connection()
print(message)
```

### Test d'envoi d'email

```python
from app.email_service import send_account_validation_email

send_account_validation_email(
    email="test@example.com",
    token="test-token-123",
    username="Jean Dupont"
)
```

---

## 🚀 Déploiement sur Railway

### 1. Configurer les variables d'environnement

Dans Railway Dashboard :
- Project → Variables
- Ajouter toutes les variables MAIL_* et APP_URL
- Redémarrer le service

### 2. Appliquer la migration

**Option A : Via Railway CLI**

```bash
railway run python scripts/migrate_add_email_fields.py
```

**Option B : Manuellement**

1. Télécharger la base de données depuis Railway
2. Appliquer la migration localement
3. Re-upload la base

### 3. Vérifier le déploiement

1. Tester l'inscription : `POST https://app.pap-cse.org/auth/register`
2. Vérifier la réception de l'email
3. Cliquer sur le lien de validation
4. Vérifier l'email de bienvenue

---

## 🔧 Troubleshooting

### ❌ Problème : Emails non envoyés

**Symptômes :** Les endpoints répondent OK mais aucun email n'arrive

**Solutions :**

1. **Vérifier les logs de l'application**
   ```bash
   # Rechercher les erreurs SMTP
   grep -i "smtp" logs/*.log
   ```

2. **Tester la connexion SMTP**
   ```bash
   python test_email.py  # Option 1
   ```

3. **Vérifier les identifiants o2switch**
   - Username correct : `contact@pap-cse.org`
   - Mot de passe correct (vérifier dans le panneau o2switch)

4. **Vérifier la configuration SSL/TLS**
   - Port 465 = SSL (`MAIL_USE_SSL=True`, `MAIL_USE_TLS=False`)
   - Port 587 = STARTTLS (`MAIL_USE_SSL=False`, `MAIL_USE_TLS=True`)

---

### ❌ Problème : Token invalide ou expiré

**Symptômes :** `Token de validation invalide` ou `Le lien a expiré`

**Solutions :**

1. **Token de validation (24h)**
   - L'utilisateur doit cliquer dans les 24h
   - Sinon, il doit se réinscrire

2. **Token de reset (1h)**
   - L'utilisateur doit réinitialiser dans l'heure
   - Sinon, refaire une demande de reset

3. **Vérifier l'heure du serveur**
   ```python
   from datetime import datetime
   print(datetime.now())  # Doit être en UTC ou locale cohérente
   ```

---

### ❌ Problème : Migration échoue

**Symptômes :** `Error lors de la migration` ou colonnes déjà existantes

**Solutions :**

1. **Vérifier l'état actuel de la base**
   ```bash
   sqlite3 papcse.db "PRAGMA table_info(users);"
   ```

2. **Si colonnes déjà présentes**
   - La migration a déjà été appliquée
   - Pas besoin de la rejouer

3. **Si base corrompue**
   ```bash
   sqlite3 papcse.db "PRAGMA integrity_check;"
   ```

---

### ❌ Problème : Emails en spam

**Symptômes :** Les emails arrivent dans les spams

**Solutions :**

1. **Vérifier SPF/DKIM** (côté o2switch)
   - Demander à o2switch de vérifier la configuration DNS
   - S'assurer que les enregistrements SPF et DKIM sont corrects

2. **Améliorer le contenu**
   - Les templates actuels sont déjà optimisés
   - Éviter les mots "spam" comme "gratuit", "gagner", etc.

3. **Demander aux utilisateurs d'ajouter à leurs contacts**
   - `contact@pap-cse.org` → Contacts

---

### ❌ Problème : Railway timeout

**Symptômes :** `504 Gateway Timeout` lors de l'envoi d'email

**Solutions :**

1. **Les emails sont envoyés en BackgroundTasks**
   - L'endpoint répond immédiatement
   - L'email est envoyé en arrière-plan

2. **Si timeout persiste**
   - Augmenter le timeout SMTP dans `email_service.py` :
     ```python
     smtp = smtplib.SMTP_SSL(MAIL_SERVER, MAIL_PORT, timeout=30)
     ```

3. **Vérifier les firewall Railway**
   - Railway autorise les connexions sortantes SMTP
   - Vérifier que le port 465 n'est pas bloqué

---

## 📚 Ressources

### Documentation officielle

- [FastAPI BackgroundTasks](https://fastapi.tiangolo.com/tutorial/background-tasks/)
- [Python smtplib](https://docs.python.org/3/library/smtplib.html)
- [Bcrypt](https://github.com/pyca/bcrypt/)
- [o2switch Documentation SMTP](https://faq.o2switch.fr/)

### Fichiers importants

| Fichier | Description |
|---------|-------------|
| `app/email_service.py` | Service d'envoi d'emails |
| `app/routers/auth_email.py` | Routes d'authentification |
| `app/models.py` | Modèle User avec champs email |
| `scripts/migrate_add_email_fields.py` | Migration de la base |
| `test_email.py` | Script de test interactif |

---

## 🎓 Exemples d'utilisation

### Exemple complet : Inscription → Validation → Login

```python
import httpx

# 1. Inscription
response = httpx.post("https://app.pap-cse.org/auth/register", json={
    "email": "jean.dupont@example.com",
    "password": "MotDePasse123",
    "first_name": "Jean",
    "last_name": "Dupont",
    "organization": "CGT"
})
print(response.json())
# → Email de validation envoyé

# 2. L'utilisateur clique sur le lien dans l'email
# GET /auth/validate-account?token=abc123...

# 3. Email de bienvenue envoyé automatiquement

# 4. Admin approuve le compte (interface admin)

# 5. Email d'approbation envoyé automatiquement

# 6. L'utilisateur peut se connecter
response = httpx.post("https://app.pap-cse.org/login", data={
    "email": "jean.dupont@example.com",
    "password": "MotDePasse123"
})
```

---

## 📝 Notes importantes

### Sécurité

- ✅ Les mots de passe sont hashés avec **bcrypt** (salt automatique)
- ✅ Les tokens sont générés avec **secrets.token_urlsafe(32)**
- ✅ Les tokens expirent (24h validation, 1h reset)
- ✅ Les messages d'erreur ne révèlent pas si un email existe
- ✅ Les emails sont validés avec regex
- ✅ Force du mot de passe vérifiée (8 car, maj, min, chiffre)

### Performance

- ✅ Les emails sont envoyés en **BackgroundTasks** (non bloquant)
- ✅ Index sur validation_token et reset_token (recherche rapide)
- ✅ Timeout SMTP de 10 secondes (évite les blocages)

### Compatibilité

- ✅ SQLite (base de données actuelle)
- ✅ Python 3.8+
- ✅ FastAPI 0.115+
- ✅ Railway (environnement de production)

---

## 🤝 Support

Pour toute question ou problème :

1. Consultez cette documentation
2. Vérifiez la section [Troubleshooting](#troubleshooting)
3. Exécutez `test_email.py` pour diagnostiquer
4. Consultez les logs de l'application

---

**Dernière mise à jour :** 2025-11-15
**Version :** 1.0.0
