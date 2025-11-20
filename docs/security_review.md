# Revue de sécurité – outilspapv2

## Résumé exécutif
Une inspection rapide du code backend a mis en évidence deux faiblesses de contrôle d'accès/session qui exposent potentiellement les routes d’administration et les sessions utilisateur. Les corrections suggérées sont limitées et concrètes (blocage du démarrage sans clé d’API admin et durcissement du cookie de session utilisateur).

## Constatations détaillées

### 1) Authentification admin désactivée si `ADMIN_API_KEY` est absente
- **Risque** : En production, si la variable d’environnement `ADMIN_API_KEY` n’est pas définie, tous les endpoints d’administration protégés par `require_api_key` deviennent accessibles sans authentification (la fonction retourne la chaîne `"unauthenticated"`). Un simple oubli de configuration annule donc totalement la protection attendue.
- **Preuve** : Le module `app/auth.py` génère une clé temporaire seulement en environnement `development`, sinon il laisse `ADMIN_API_KEY` vide et désactive l’authentification (`return "unauthenticated"`).【F:app/auth.py†L10-L67】
- **Recommandation** : Faire échouer le démarrage de l’application (ou lever une exception au premier appel) lorsque `ADMIN_API_KEY` est manquante hors environnement de développement. Ajouter une validation de configuration au boot et des tests end-to-end pour vérifier le rejet d’une requête sans en-tête `X-API-Key`.

### 2) Cookie de session utilisateur non marqué `secure` et lax en SameSite
- **Risque** : Le cookie de session utilisateur est envoyé sans attribut `secure`; il peut être intercepté sur une connexion non chiffrée (ou réutilisé dans certains contextes de proxy), et le mode `samesite="lax"` permet certains scénarios de CSRF sur des requêtes GET/POST initiées depuis un autre site. Sur un site exposé publiquement, le cookie devrait être limité aux contextes HTTPS stricts.
- **Preuve** : Lors du login (`/login`), le cookie `user_session` est défini avec `httponly=True` mais sans `secure`, et `samesite` vaut `"lax"`.【F:app/main.py†L3678-L3708】
- **Recommandation** : Passer `secure=True` lorsque le site est servi derrière HTTPS, et envisager `samesite="strict"` (ou intégrer un jeton CSRF pour les formulaires). Ajouter un paramètre de configuration pour forcer ces drapeaux en production.

## Prochaines étapes proposées
1. Bloquer le démarrage ou lever une erreur claire si `ADMIN_API_KEY` n’est pas fournie en production, et ajouter un test d’intégration couvrant ce cas.
2. Durcir le cookie de session utilisateur (`secure=True`, `samesite=strict`) et introduire une stratégie CSRF simple pour les formulaires sensibles.
3. Vérifier que les environnements de déploiement imposent HTTPS (redirect 301 vers HTTPS et en-tête `Strict-Transport-Security`).
