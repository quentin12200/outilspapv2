# 📚 Documentation PAP/CSE - Tableau de bord

Documentation complète du projet PAP/CSE (Protocole d'Accord Préélectoral / Comité Social et Économique).

## 📂 Structure de la documentation

### 🚀 [Déploiement](./deployment/)

Documentation relative au déploiement et à la configuration de l'application.

- **[DEPLOYMENT.md](./deployment/DEPLOYMENT.md)** - Guide de déploiement général
- **[DEPLOYMENT_O2SWITCH.md](./deployment/DEPLOYMENT_O2SWITCH.md)** - Déploiement sur O2Switch
- **[DEPLOYMENT_DNS_O2SWITCH.md](./deployment/DEPLOYMENT_DNS_O2SWITCH.md)** - Configuration DNS sur O2Switch
- **[QUICK_START_DNS.md](./deployment/QUICK_START_DNS.md)** - Guide rapide configuration DNS

### ✨ [Fonctionnalités](./features/)

Documentation des fonctionnalités principales de l'application.

- **[RESEND_INTEGRATION_RECAP.md](./features/RESEND_INTEGRATION_RECAP.md)** - Intégration du service d'emails Resend
- **[RESEND_INTEGRATION.md](./features/RESEND_INTEGRATION.md)** - Documentation technique Resend
- **[VERIFICATION_EMAILS_AUTOMATIQUES.md](./features/VERIFICATION_EMAILS_AUTOMATIQUES.md)** - Vérification des emails automatiques
- **[ESPACE_UTILISATEUR_RGPD.md](./features/ESPACE_UTILISATEUR_RGPD.md)** - Espace utilisateur personnel (conformité RGPD)

### 🗄️ [Base de données](./database/)

Documentation de la base de données et des migrations.

- **[DATABASE_CONFIG.md](./database/DATABASE_CONFIG.md)** - Configuration de la base de données
- **[MIGRATION_INVITATIONS.md](./database/MIGRATION_INVITATIONS.md)** - Migration des invitations
- **[WAITING_FOR_DB.md](./database/WAITING_FOR_DB.md)** - Attente de disponibilité de la DB

### 🔧 [Développement](./development/)

Guides et bonnes pratiques pour le développement.

- **[BACKGROUND_TASKS.md](./development/BACKGROUND_TASKS.md)** - Utilisation des tâches en arrière-plan
- **[OPTIMIZATION.md](./development/OPTIMIZATION.md)** - Optimisations de performance
- **[BRANCHES.md](./development/BRANCHES.md)** - Gestion des branches Git
- **[ARCHIVES_BRANCHES.md](./development/ARCHIVES_BRANCHES.md)** - Archives des anciennes branches
- **[CONTINUITY_PLAN.md](./development/CONTINUITY_PLAN.md)** - Plan de continuité

### 🔨 [Corrections](./fixes/)

Documentation des corrections et résolutions de bugs.

- **[FIX_ENRICHISSEMENT_IDCC.md](./fixes/FIX_ENRICHISSEMENT_IDCC.md)** - Correction enrichissement IDCC
- **[FIX_IDCC_API_SIRET2IDCC.md](./fixes/FIX_IDCC_API_SIRET2IDCC.md)** - Correction API SIRET2IDCC
- **[FIX_MISSING_FD.md](./fixes/FIX_MISSING_FD.md)** - Correction champs FD manquants
- **[FIX_NAN_VALUES.md](./fixes/FIX_NAN_VALUES.md)** - Correction valeurs NaN
- **[RESUME_CORRECTIONS_API_SIRENE.md](./fixes/RESUME_CORRECTIONS_API_SIRENE.md)** - Résumé corrections API Sirene

### 🔌 [API](./api/)

Documentation des intégrations API externes.

- **[API_SIRENE_RATE_LIMITING.md](./api/API_SIRENE_RATE_LIMITING.md)** - Gestion du rate limiting API Sirene
- **[RAILWAY_API_SIRENE.md](./api/RAILWAY_API_SIRENE.md)** - Configuration API Sirene sur Railway
- **[VALIDATION_API_SIRENE.md](./api/VALIDATION_API_SIRENE.md)** - Validation de l'API Sirene
- **[FAQ_API_SIRENE_404.md](./api/FAQ_API_SIRENE_404.md)** - FAQ erreurs 404 API Sirene

### 🧪 [Tests](./testing/)

Documentation des tests et débogage.

- **[TEST_RECHERCHE_SIRET.md](./testing/TEST_RECHERCHE_SIRET.md)** - Tests de recherche SIRET
- **[INSTRUCTIONS_TEST_KPI.md](./testing/INSTRUCTIONS_TEST_KPI.md)** - Instructions test KPI
- **[DEBUG_KPI_HOMEPAGE.md](./testing/DEBUG_KPI_HOMEPAGE.md)** - Débogage KPI page d'accueil

### 📖 [Guides](./guides/)

Guides d'utilisation et tutoriels.

- **[GUIDE_EXPLOITATION_IA.md](./guides/GUIDE_EXPLOITATION_IA.md)** - Guide d'exploitation avec IA
- **[GUIDE_REIMPORT_INVITATIONS.md](./guides/GUIDE_REIMPORT_INVITATIONS.md)** - Guide de réimport des invitations
- **[TEMPLATE_README.md](./guides/TEMPLATE_README.md)** - Template d'import des invitations
- **[CALCUL_ELUS_CSE.md](./guides/CALCUL_ELUS_CSE.md)** - Calcul des élus CSE
- **[EXTRACTION_COURRIERS_GPT.md](./guides/EXTRACTION_COURRIERS_GPT.md)** - Extraction de courriers avec GPT
- **[ENRICHISSEMENT_FD_AUTOMATIQUE.md](./guides/ENRICHISSEMENT_FD_AUTOMATIQUE.md)** - Enrichissement automatique FD
- **[ENRICHISSEMENT_IDCC_FD.md](./guides/ENRICHISSEMENT_IDCC_FD.md)** - Enrichissement IDCC/FD
- **[RAILWAY_CONFIG_OPENAI.md](./guides/RAILWAY_CONFIG_OPENAI.md)** - Configuration OpenAI sur Railway
- **[RAILWAY_GPT_EXTRACTION.md](./guides/RAILWAY_GPT_EXTRACTION.md)** - Extraction GPT sur Railway

## 🚀 Démarrage rapide

1. **Installation** : Consultez le [README principal](../README.md)
2. **Déploiement** : Voir [DEPLOYMENT.md](./deployment/DEPLOYMENT.md)
3. **Configuration** : Voir [DATABASE_CONFIG.md](./database/DATABASE_CONFIG.md)

## 🔒 Sécurité

Pour les informations de sécurité, consultez [SECURITY.md](../SECURITY.md) à la racine du projet.

## 📝 Contribution

Pour contribuer au projet :

1. Créez une branche feature (voir [BRANCHES.md](./development/BRANCHES.md))
2. Suivez les bonnes pratiques de développement (voir [OPTIMIZATION.md](./development/OPTIMIZATION.md))
3. Testez vos modifications (voir dossier [testing/](./testing/))
4. Créez une Pull Request

## 📧 Support

Pour toute question ou problème, consultez la documentation appropriée ci-dessus ou contactez l'équipe de développement.

---

**Dernière mise à jour :** 2025-11-16
