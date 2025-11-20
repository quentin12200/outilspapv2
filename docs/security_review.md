# Revue de sécurité – outilspapv2

## Résumé exécutif
Une inspection rapide du code backend a mis en évidence deux faiblesses de contrôle d'accès/session qui exposent potentiellement les routes d’administration et les sessions utilisateur. Les corrections ont été mises en place (blocage du démarrage sans clé d’API admin, durcissement des cookies, redirection HTTPS + HSTS), et la revue a été étendue à l’authentification utilisateur (CSRF/rate-limit à compléter).

## Constatations détaillées

### 1) Authentification admin désormais bloquante sans `ADMIN_API_KEY`
- **Risque initial** : En production, si la variable d’environnement `ADMIN_API_KEY` n’était pas définie, tous les endpoints d’administration protégés devenaient accessibles sans authentification.
- **Correctif** : Importer `app/auth.py` déclenche désormais une erreur bloquante lorsque `ENV` n’est pas un environnement de dev/test et qu’aucune clé n’est fournie. Une clé déterministe est injectée pour les tests, et une clé aléatoire reste générée uniquement pour le développement.【F:app/auth.py†L10-L42】
- **Tests** : `test_security_config.py` vérifie que le module échoue explicitement en production sans clé et reste importable en développement/test.【F:test_security_config.py†L1-L38】

### 2) Cookies de session utilisateur durcis par défaut
- **Risque initial** : Le cookie de session utilisateur était envoyé sans attribut `secure` et avec `samesite="lax"`, facilitant CSRF et interception sur HTTP.
- **Correctif** : Les drapeaux sont désormais calculés en fonction de l’environnement et configurables via les variables d’env. En production/staging, `secure=True` et `samesite="strict"` sont appliqués par défaut.【F:app/user_auth.py†L5-L52】【F:app/main.py†L3733-L3748】
- **Tests** : Un test vérifie que le défaut en production force `secure` et `samesite=strict`.【F:test_security_config.py†L40-L55】

### 3) HTTPS forcé et en-tête HSTS en environnements sensibles
- **Risque initial** : Aucune redirection HTTPS ni en-tête HSTS n’étaient appliqués, exposant les cookies et le trafic à un éventuel downgrade HTTP.
- **Correctif** : Un middleware force désormais la redirection vers HTTPS quand `FORCE_HTTPS` est actif (activé par défaut hors dev/test) et ajoute l’en-tête `Strict-Transport-Security` configurable.【F:app/main.py†L162-L172】【F:app/main.py†L724-L746】

### 4) Authentification utilisateur : CSRF et rate limiting à ajouter
- **Observation** : Les formulaires utilisateur (ex. `/login`) ne portent pas de jeton CSRF et ne sont pas protégés par un mécanisme anti-brute-force ou de verrouillage temporaire en cas d’échecs répétés.【F:app/templates/user_login.html†L62-L110】【F:app/main.py†L3703-L3749】
- **Recommandation** : Ajouter un jeton CSRF synchronisé pour les formulaires sensibles et mettre en place une limitation de tentatives (par IP et par compte) avec backoff ou Captcha après plusieurs échecs.

## Prochaines étapes proposées
1. **Déjà appliqué** : blocage du démarrage sans `ADMIN_API_KEY` hors dev/test, plus tests unitaires.
2. **Déjà appliqué** : cookies de session `secure=True` + `samesite=strict` en production/staging.
3. **Déjà appliqué** : redirection HTTPS et en-tête HSTS activables via `FORCE_HTTPS` / `HSTS_*`.
4. **À faire** : implémenter un jeton CSRF sur les formulaires et un mécanisme de rate limiting/lockout sur la connexion.
