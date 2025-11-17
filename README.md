# 🏢 PAP/CSE - Tableau de bord

> Plateforme de suivi et d'analyse des Protocoles d'Accord Préélectoraux (PAP) et des résultats CSE (Comité Social et Économique) pour la CGT.

[![License](https://img.shields.io/badge/license-Private-red.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.0-green.svg)](https://fastapi.tiangolo.com/)

## 📋 Vue d'ensemble

Cette application permet de :

- 📊 **Suivre l'audience interprofessionnelle** de la CGT via les PV retenus
- 📨 **Gérer les invitations PAP** et le ciblage des entreprises
- 🔍 **Rechercher et enrichir** les données SIRET via l'API Sirene
- 📈 **Visualiser les KPI** et statistiques d'audience
- ✉️ **Envoyer des emails automatiques** (inscription, approbation, reset password)
- 👤 **Gérer les utilisateurs** avec espace personnel conforme RGPD

## 🚀 Accès rapide

- **🌐 Application en production** : [https://pap-cse.org](https://pap-cse.org)
- **📚 Documentation complète** : [docs/](./docs/)
- **🔒 Sécurité** : [SECURITY.md](./SECURITY.md)

## ✨ Fonctionnalités principales

### 📊 Tableau de bord
- Suivi en temps réel des KPI d'audience
- Visualisation des résultats CSE et SVE
- Statistiques par région, département, secteur

### 📨 Gestion des invitations
- Import massif d'invitations (Excel/CSV)
- Enrichissement automatique via API Sirene
- Suivi du statut des invitations

### 🔍 Recherche SIRET
- Recherche d'établissements par SIRET, nom, adresse
- Enrichissement automatique des données (NAF, IDCC, effectifs)
- Calcul automatique des élus CSE

### 👥 Gestion des utilisateurs
- Système d'authentification sécurisé
- Approbation par administrateur
- Espace utilisateur personnel (conformité RGPD)
- Reset de mot de passe par email

### ✉️ Emails automatiques
- Notification admin lors des inscriptions
- Email de bienvenue après approbation
- Reset de mot de passe sécurisé
- Service Resend pour l'envoi fiable

## 🛠️ Technologies

- **Backend** : FastAPI 0.115.0 (Python 3.13)
- **Base de données** : SQLite + SQLAlchemy 2.0.36
- **Frontend** : Jinja2 Templates + TailwindCSS + Alpine.js
- **Emails** : Resend API
- **Déploiement** : Railway
- **APIs externes** : INSEE Sirene, SIRET2IDCC

## 📦 Installation

### Prérequis

- Python 3.13+
- SQLite 3
- Variables d'environnement configurées (voir `.env.example`)

### Installation locale

```bash
# Cloner le dépôt
git clone https://github.com/quentin12200/outilspapv2.git
cd outilspapv2

# Créer un environnement virtuel
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ou
.venv\Scripts\activate  # Windows

# Installer les dépendances
pip install -r requirements.txt

# Copier le fichier de configuration
cp .env.example .env
# Éditer .env avec vos valeurs

# Lancer l'application
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Accédez à l'application sur `http://localhost:8000`

## 🔐 Configuration

### Variables d'environnement essentielles

```bash
# Base de données
DATABASE_URL=sqlite:///./papcse.db

# API Sirene (INSEE)
SIRENE_API_TOKEN=votre_token_insee

# Emails (Resend)
RESEND_API_KEY=re_xxxxxxxxxxxxx
RESEND_FROM_EMAIL=noreply@pap-cse.org
RESEND_FROM_NAME=PAP/CSE - Tableau de bord

# Application
APP_URL=https://pap-cse.org
SECRET_KEY=votre_secret_key_aleatoire

# Admin (optionnel)
ADMIN_API_KEY=votre_api_key_admin
```

Pour plus de détails, consultez la [documentation de déploiement](./docs/deployment/).

## 📚 Documentation

La documentation complète est organisée par thématique dans le dossier [`docs/`](./docs/) :

| Catégorie | Description | Lien |
|-----------|-------------|------|
| 🚀 **Déploiement** | Guides de déploiement Railway, O2Switch, DNS | [docs/deployment/](./docs/deployment/) |
| ✨ **Fonctionnalités** | Resend, emails, espace utilisateur RGPD | [docs/features/](./docs/features/) |
| 🗄️ **Base de données** | Configuration, migrations | [docs/database/](./docs/database/) |
| 🔧 **Développement** | Background tasks, optimisation, branches | [docs/development/](./docs/development/) |
| 🔨 **Corrections** | Documentation des bugs résolus | [docs/fixes/](./docs/fixes/) |
| 🔌 **API** | Sirene, SIRET2IDCC, rate limiting | [docs/api/](./docs/api/) |
| 🧪 **Tests** | Tests et débogage | [docs/testing/](./docs/testing/) |
| 📖 **Guides** | Tutoriels utilisateur | [docs/guides/](./docs/guides/) |

👉 **Index complet** : [docs/README.md](./docs/README.md)

## 🧭 Découvrir la plateforme

La page `/presentation` présente la vocation de l'outil « PAP/CSE · Tableau de bord » :

- **Héros introductif** pour rappeler le suivi ciblage PAP et les publics visés
- **Cartes de fonctionnalités** décrivant les modules principaux
- **Boucle PAP → PV** et **calendrier C5** pour visualiser la continuité
- **Guide de démarrage** listant les étapes essentielles

👉 Accédez-y depuis `https://pap-cse.org/presentation`

## 🗄️ Base de données

### Téléchargement

La base de données `papcse.db` n'est pas versionnée dans Git pour des raisons de taille.

📦 **Téléchargement :** [👉 Dernière version (.db)](https://github.com/quentin12200/outilspapv2/releases/latest)

ℹ️ **Où placer le fichier ?** Déposez `papcse.db` à la racine du dépôt (au même niveau que ce README) ou mettez à jour la variable d'environnement `DATABASE_URL`.

### Vérification d'intégrité

Pour vérifier que le fichier téléchargé n'a pas été altéré, comparez le SHA-256 :

```bash
sha256sum papcse.db
```

👉 **Déploiement :** L'application calcule cette empreinte au démarrage si la variable `DB_SHA256` est renseignée. Par défaut, elle continue à fonctionner même si le hash ne correspond plus (par exemple après un enrichissement local). Pour retrouver un blocage strict en cas d'écart, définissez `DB_FAIL_ON_HASH_MISMATCH=1` dans vos variables d'environnement.

## 🌐 API Sirene

Les recherches SIRET réalisées depuis la page « Recherche de SIRET » s'appuient sur l'API Sirene de l'INSEE. Pour éviter les erreurs 401/403 et bénéficier d'un débit confortable, ajoutez un jeton Bearer dans la variable d'environnement `SIRENE_API_TOKEN` (ou `SIRENE_API_KEY`) sur votre instance Railway.

📖 **Documentation :** [docs/api/](./docs/api/)

## 🔒 Sécurité

Pour signaler une vulnérabilité de sécurité, consultez [SECURITY.md](./SECURITY.md).

Mesures de sécurité implémentées :
- ✅ Authentification par cookie sécurisé
- ✅ Hachage bcrypt des mots de passe
- ✅ Tokens de reset sécurisés (24h expiration)
- ✅ Anti-énumération des emails
- ✅ Protection CSRF
- ✅ Approbation manuelle des utilisateurs

## 📝 Contribution

### Workflow Git

1. Créez une branche feature :
   ```bash
   git checkout -b feature/ma-fonctionnalite
   ```

2. Faites vos modifications et commitez :
   ```bash
   git add .
   git commit -m "Ajouter ma fonctionnalité"
   ```

3. Poussez la branche :
   ```bash
   git push origin feature/ma-fonctionnalite
   ```

4. Créez une Pull Request sur GitHub

📖 **Guide complet :** [docs/development/BRANCHES.md](./docs/development/BRANCHES.md)

### Standards de code

- Suivre les conventions PEP 8 pour Python
- Utiliser les type hints
- Documenter les fonctions complexes
- Écrire des commits clairs et descriptifs

## ❓ FAQ

### « Codex ne prend actuellement pas en charge la mise à jour des demandes d'extraction en dehors de Codex »

Ce message apparaît lorsque l'assistant n'a pas la possibilité de modifier une *pull request* GitHub existante. Pour publier un correctif, il faut donc créer une nouvelle branche locale, y committer les changements, et ouvrir une nouvelle *pull request* correspondante sur GitHub.

**Étapes type :**

1. Mettre à jour la branche : `git pull origin main`
2. Créer une nouvelle branche : `git checkout -b fix/mon-correctif`
3. Apporter les modifications et committer
4. Pousser : `git push origin fix/mon-correctif`
5. Ouvrir une nouvelle PR sur GitHub

### Comment importer des invitations ?

Consultez le guide complet : [docs/guides/GUIDE_REIMPORT_INVITATIONS.md](./docs/guides/GUIDE_REIMPORT_INVITATIONS.md)

Template disponible : [docs/guides/TEMPLATE_README.md](./docs/guides/TEMPLATE_README.md)

### Comment configurer les emails ?

Voir la documentation : [docs/features/RESEND_INTEGRATION_RECAP.md](./docs/features/RESEND_INTEGRATION_RECAP.md)

## 📧 Support

Pour toute question ou problème :

1. Consultez la [documentation](./docs/)
2. Vérifiez les [issues GitHub](https://github.com/quentin12200/outilspapv2/issues)
3. Créez une nouvelle issue si nécessaire

## 📄 Licence

Projet privé - CGT - Tous droits réservés

---

**Dernière mise à jour :** 2025-11-16
**Version :** 2.0.0
**Mainteneur :** [@quentin12200](https://github.com/quentin12200)
