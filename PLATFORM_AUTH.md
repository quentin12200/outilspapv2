# Protection par mot de passe de la plateforme

## Vue d'ensemble

La plateforme PAP/CSE est maintenant protégée par un système d'authentification par mot de passe. Tous les utilisateurs doivent s'authentifier avant d'accéder aux outils et fonctionnalités.

## Fonctionnement

### Pages publiques (accessibles sans authentification)

- `/login` - Page de connexion
- `/logout` - Déconnexion
- `/health` - Point de vérification de santé de l'application
- `/mentions-legales` - Mentions légales
- `/static/*` - Ressources statiques (CSS, JS, images)

### Pages protégées

Toutes les autres pages nécessitent une authentification :
- Page d'accueil `/`
- Calendrier `/calendrier`
- Invitations `/invitations`
- Extraction `/extraction`
- Ciblage `/ciblage`
- Cartographie `/cartographie`
- Recherche SIRET `/recherche-siret`
- Statistiques `/stats`
- Espace admin `/admin` (nécessite en plus une authentification admin séparée)

## Configuration

### Variables d'environnement

Vous pouvez configurer l'authentification via les variables d'environnement suivantes :

```bash
# Mot de passe pour accéder à la plateforme (par défaut : papcse2025)
PLATFORM_PASSWORD=votre_mot_de_passe

# Clé secrète pour signer les sessions (générée automatiquement si non définie)
PLATFORM_SESSION_SECRET=votre_cle_secrete

# Durée de validité des sessions en secondes (défaut : 86400 = 24 heures)
PLATFORM_SESSION_MAX_AGE=86400
```

### Modifier le mot de passe

Pour modifier le mot de passe par défaut :

1. Définissez la variable d'environnement `PLATFORM_PASSWORD` :
   ```bash
   export PLATFORM_PASSWORD="mon_nouveau_mot_de_passe"
   ```

2. Ou ajoutez-la dans votre fichier `.env` :
   ```bash
   PLATFORM_PASSWORD=mon_nouveau_mot_de_passe
   ```

3. Redémarrez l'application

### Sécurité

- Les sessions utilisent des tokens signés avec une clé secrète
- Les cookies de session sont configurés avec `httponly=True` et `samesite="lax"` pour la sécurité
- Les sessions expirent automatiquement après 24 heures (configurable)
- Le mot de passe par défaut devrait être changé en production

## Utilisation

### Connexion

1. Accédez à l'URL de la plateforme
2. Vous serez automatiquement redirigé vers `/login` si vous n'êtes pas authentifié
3. Entrez le mot de passe
4. Vous serez redirigé vers la page d'accueil

### Déconnexion

Pour vous déconnecter, accédez à `/logout` ou cliquez sur le bouton de déconnexion (si disponible dans l'interface).

## Architecture technique

### Fichiers ajoutés/modifiés

- `app/platform_auth.py` - Module d'authentification de la plateforme
- `app/templates/login.html` - Page de connexion
- `app/main.py` - Routes de login/logout et middleware de protection
- `.env.example` - Documentation des variables d'environnement

### Middleware

Le middleware `PlatformAuthMiddleware` vérifie automatiquement l'authentification pour toutes les requêtes entrantes, sauf pour les chemins définis dans `PUBLIC_PATHS` et `PUBLIC_PREFIXES`.

### Gestion des exceptions

Le gestionnaire d'exceptions `platform_auth_exception_handler` intercepte les `PlatformAuthException` et redirige automatiquement vers `/login`.

## Différence avec l'authentification admin

- **Authentification plateforme** : Protège l'accès général à la plateforme avec un mot de passe unique
- **Authentification admin** : Protège l'espace d'administration avec un login et mot de passe séparés

Les deux systèmes sont indépendants et utilisent des cookies de session différents.
