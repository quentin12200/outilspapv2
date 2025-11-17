# Guide de déploiement sur o2switch/cPanel

Ce guide vous accompagne pas à pas pour déployer l'application FastAPI sur votre hébergement o2switch avec cPanel.

## 📋 Prérequis

- Compte o2switch avec accès cPanel
- Accès SSH activé
- Python 3.11+ (disponible via "Python Setup App" dans cPanel)
- Nom de domaine configuré

---

## ⚠️ IMPORTANT : Version Python requise

**Votre application nécessite Python 3.11 ou supérieur.**

Si vous tapez `python --version` ou `python3 --version` et obtenez une version 2.x ou 3.x < 3.11, vous devez configurer Python via cPanel.

---

## 🚀 Étape 1 : Configurer Python dans cPanel

### 1.1. Accéder à "Python Setup App"

1. Connectez-vous à votre **cPanel o2switch**
2. Dans la section **"SOFTWARE"** ou **"LOGICIELS"**, cherchez **"Python Setup App"** ou **"Setup Python App"**
3. Cliquez dessus

### 1.2. Créer une nouvelle application Python

1. Cliquez sur **"Create Application"**
2. Remplissez les champs :
   - **Python version** : Sélectionnez `3.11` ou supérieur (ex: 3.11.x, 3.12.x)
   - **Application root** : `/home/VOTRE_UTILISATEUR/outilspapv2`
   - **Application URL** : `https://votre-domaine.com` (ou sous-domaine)
   - **Application startup file** : `passenger_wsgi.py`
   - **Application Entry point** : `application`

3. Cliquez sur **"Create"**

### 1.3. Noter le chemin du virtualenv

Après création, cPanel affiche le chemin du virtualenv, par exemple :
```
/home/VOTRE_UTILISATEUR/.local/share/virtualenvs/outilspapv2
```

**Notez ce chemin**, vous en aurez besoin.

---

## 🔧 Étape 2 : Préparer les fichiers en local

Sur votre machine locale (ou Railway), préparez les fichiers :

### 2.1. Vérifier les fichiers créés

Les fichiers suivants ont été créés automatiquement :
- ✅ `passenger_wsgi.py` - Point d'entrée WSGI
- ✅ `.htaccess` - Configuration Apache
- ✅ `.env.o2switch` - Template de configuration

### 2.2. Configurer les variables d'environnement

1. Copiez `.env.o2switch` vers `.env` :
```bash
cp .env.o2switch .env
```

2. Éditez `.env` et remplissez vos clés API :
```env
SIRENE_API_KEY=VOTRE_CLE_API_SIRENE
OPENAI_API_KEY=sk-proj-VOTRE_CLE_OPENAI
```

### 2.3. Mettre à jour `.htaccess`

Éditez `.htaccess` et remplacez `VOTRE_UTILISATEUR` par votre nom d'utilisateur cPanel.

**Exemple :**
```apache
PassengerAppRoot /home/moncompte/outilspapv2
PassengerPython /home/moncompte/.local/share/virtualenvs/outilspapv2/bin/python3
```

### 2.4. Mettre à jour `passenger_wsgi.py`

Éditez `passenger_wsgi.py` et vérifiez le chemin du virtualenv :
```python
INTERP = os.path.join(os.environ['HOME'], '.local', 'share', 'virtualenvs', 'outilspapv2', 'bin', 'python3')
```

---

## 📤 Étape 3 : Uploader les fichiers sur o2switch

### Option A : Via SSH (Recommandé)

#### 3.1. Se connecter en SSH

```bash
ssh VOTRE_UTILISATEUR@VOTRE_DOMAINE.com
# ou
ssh VOTRE_UTILISATEUR@ssh.o2switch.net
```

#### 3.2. Créer le répertoire de l'application

```bash
cd ~
mkdir -p outilspapv2
cd outilspapv2
```

#### 3.3. Transférer les fichiers depuis votre machine locale

Sur votre **machine locale** :

```bash
# Méthode 1 : rsync (recommandé)
rsync -avz --exclude='papcse.db' --exclude='__pycache__' --exclude='.git' \
  /chemin/local/outilspapv2/ \
  VOTRE_UTILISATEUR@VOTRE_DOMAINE.com:~/outilspapv2/

# Méthode 2 : scp
scp -r app/ requirements.txt .env passenger_wsgi.py .htaccess \
  VOTRE_UTILISATEUR@VOTRE_DOMAINE.com:~/outilspapv2/
```

#### 3.4. OU cloner depuis GitHub (si public)

Sur le **serveur SSH** :
```bash
cd ~/outilspapv2
git clone https://github.com/quentin12200/outilspapv2.git .
cp .env.o2switch .env
# Éditez .env avec vos clés
nano .env
```

### Option B : Via FileZilla / FTP

1. Installez **FileZilla**
2. Connectez-vous à votre serveur o2switch :
   - Hôte : `ftp.VOTRE_DOMAINE.com`
   - Utilisateur : Votre utilisateur cPanel
   - Mot de passe : Votre mot de passe cPanel
   - Port : 21

3. Uploadez tous les fichiers dans `/outilspapv2/`

---

## 🔨 Étape 4 : Installer les dépendances Python

### 4.1. Se connecter en SSH

```bash
ssh VOTRE_UTILISATEUR@VOTRE_DOMAINE.com
```

### 4.2. Activer le virtualenv

```bash
source ~/.local/share/virtualenvs/outilspapv2/bin/activate
```

Votre prompt devrait changer pour afficher `(outilspapv2)`.

### 4.3. Installer les dépendances

```bash
cd ~/outilspapv2
pip install --upgrade pip
pip install -r requirements.txt
```

⏱️ **Cette étape peut prendre 5-10 minutes**

### 4.4. Vérifier l'installation

```bash
python -c "import fastapi; print(fastapi.__version__)"
python -c "import uvicorn; print(uvicorn.__version__)"
```

Vous devriez voir les versions affichées sans erreur.

---

## 🗄️ Étape 5 : Configurer la base de données

### 5.1. Télécharger la base de données

L'application téléchargera automatiquement `papcse.db` depuis GitHub au premier démarrage si `DB_URL` est configuré dans `.env`.

**OU** téléchargez-la manuellement :

```bash
cd ~/outilspapv2
wget https://github.com/quentin12200/outilspapv2/releases/download/v1.0.0/papcse.db
```

### 5.2. Vérifier les permissions

```bash
chmod 644 papcse.db
chmod 755 ~/outilspapv2
```

---

## 🌐 Étape 6 : Configurer le domaine/sous-domaine

### 6.1. Dans cPanel, créer un sous-domaine (optionnel)

Si vous voulez `app.votre-domaine.com` :
1. Allez dans **"Domains"** → **"Subdomains"**
2. Créez `app` → Document Root : `/home/VOTRE_UTILISATEUR/outilspapv2`

### 6.2. Configurer le DNS (si domaine principal)

Si vous utilisez votre domaine principal :
1. Document Root = `/home/VOTRE_UTILISATEUR/outilspapv2`

---

## 🚦 Étape 7 : Démarrer l'application

### 7.1. Redémarrer l'application Python dans cPanel

1. Retournez dans **"Python Setup App"**
2. Trouvez votre application
3. Cliquez sur **"Restart"** ou **"Stop"** puis **"Start"**

### 7.2. Vérifier les logs

En SSH :
```bash
tail -f ~/logs/VOTRE_DOMAINE.com.error.log
# ou
tail -f ~/outilspapv2/passenger.log
```

---

## ✅ Étape 8 : Tester l'application

### 8.1. Accéder à votre site

Ouvrez votre navigateur et allez sur :
```
https://votre-domaine.com
```

Vous devriez voir la page d'accueil de l'application PAP/CSE.

### 8.2. Tester les endpoints API

```bash
curl https://votre-domaine.com/api/health
```

Devrait retourner :
```json
{"status": "ok"}
```

---

## 🐛 Dépannage

### Problème : "502 Bad Gateway" ou "503 Service Unavailable"

**Causes possibles :**
1. Le virtualenv n'est pas activé
2. Les dépendances ne sont pas installées
3. Erreur dans `passenger_wsgi.py`

**Solution :**
```bash
# Vérifier les logs
tail -n 50 ~/logs/VOTRE_DOMAINE.com.error.log

# Réinstaller les dépendances
source ~/.local/share/virtualenvs/outilspapv2/bin/activate
pip install -r requirements.txt
```

### Problème : "Internal Server Error 500"

**Causes possibles :**
1. Erreur dans `.env` (clés API manquantes)
2. Base de données manquante
3. Permissions incorrectes

**Solution :**
```bash
# Vérifier .env
cat .env

# Vérifier la base
ls -lh papcse.db

# Télécharger la base si manquante
wget https://github.com/quentin12200/outilspapv2/releases/download/v1.0.0/papcse.db
```

### Problème : "ImportError" ou "ModuleNotFoundError"

**Cause :** Dépendances manquantes

**Solution :**
```bash
source ~/.local/share/virtualenvs/outilspapv2/bin/activate
pip install -r requirements.txt --force-reinstall
```

### Problème : Version Python incorrecte

Si vous obtenez `Python 2.7.18` :

**Solution :**
1. Retournez dans cPanel → **"Python Setup App"**
2. Supprimez l'application actuelle
3. Recréez-la avec **Python 3.11+**

---

## 🔐 Sécurité

### Protéger les fichiers sensibles

Vérifiez que `.htaccess` contient bien :
```apache
<FilesMatch "^\.env">
    Order allow,deny
    Deny from all
</FilesMatch>
```

### Générer un utilisateur admin

En SSH :
```bash
cd ~/outilspapv2
source ~/.local/share/virtualenvs/outilspapv2/bin/activate
python -m app.user_auth create-admin
```

Suivez les instructions pour créer votre compte administrateur.

---

## 📊 Mise à jour de l'application

### Pour mettre à jour depuis GitHub

```bash
cd ~/outilspapv2
git pull origin main

# Réinstaller les dépendances si requirements.txt a changé
source ~/.local/share/virtualenvs/outilspapv2/bin/activate
pip install -r requirements.txt --upgrade

# Redémarrer l'application
# Via cPanel → Python Setup App → Restart
```

---

## 📞 Support

- **Documentation o2switch** : https://faq.o2switch.fr/
- **Support technique o2switch** : Via cPanel → "Ouvrir un ticket"
- **Documentation FastAPI** : https://fastapi.tiangolo.com/

---

## 🎉 Félicitations !

Votre application PAP/CSE est maintenant déployée sur o2switch !

### Prochaines étapes

1. ✅ Créer un utilisateur admin
2. ✅ Tester toutes les fonctionnalités
3. ✅ Configurer les sauvegardes automatiques (cPanel → Backup)
4. ✅ Configurer SSL/HTTPS (gratuit avec Let's Encrypt sur o2switch)
5. ✅ Ajouter un monitoring (optionnel)

---

## 📝 Checklist de déploiement

- [ ] Python 3.11+ configuré dans cPanel
- [ ] Application créée dans "Python Setup App"
- [ ] Fichiers uploadés sur le serveur
- [ ] `.env` configuré avec les clés API
- [ ] `.htaccess` mis à jour avec le bon utilisateur
- [ ] Dépendances installées (`pip install -r requirements.txt`)
- [ ] Base de données téléchargée (`papcse.db`)
- [ ] Domaine/sous-domaine configuré
- [ ] Application redémarrée dans cPanel
- [ ] Site accessible et fonctionnel
- [ ] Utilisateur admin créé
- [ ] SSL/HTTPS configuré

---

**Date de création** : 2025-11-15
**Version** : 1.0
**Hébergeur** : o2switch/cPanel
