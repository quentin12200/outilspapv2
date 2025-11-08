# Guide de Sécurité

## Authentification API

### Configuration de l'API Key

Tous les endpoints d'administration nécessitent une authentification par API Key pour protéger les opérations sensibles.

#### Endpoints protégés

Les endpoints suivants requièrent une API Key valide dans le header `X-API-Key` :

- `POST /api/ingest/pv` - Ingestion de PV
- `POST /api/ingest/invit` - Ingestion d'invitations
- `POST /api/build/summary` - Reconstruction de la table siret_summary
- `POST /api/enrichir/idcc` - Enrichissement des IDCC
- `POST /api/sirene/enrichir-tout` - Enrichissement via API Sirene (déprécié)
- `POST /api/sirene/enrichir/{siret}` - Enrichissement d'un SIRET spécifique
- `POST /api/invitation/add` - Ajout manuel d'invitation

#### Configuration

1. **En production**, définissez la variable d'environnement `ADMIN_API_KEY` :

```bash
export ADMIN_API_KEY="votre_cle_api_secrete_ici"
```

⚠️ **IMPORTANT** : Utilisez une clé forte et aléatoire. Vous pouvez générer une clé sécurisée avec :

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

2. **En développement**, si aucune clé n'est définie, le système génère automatiquement une clé temporaire et l'affiche dans les logs.

#### Utilisation

Pour appeler un endpoint protégé, incluez le header `X-API-Key` :

```bash
curl -X POST "http://localhost:8000/api/build/summary" \
  -H "X-API-Key: votre_cle_api" \
  -H "Content-Type: application/json"
```

Avec HTTPie :
```bash
http POST localhost:8000/api/build/summary X-API-Key:votre_cle_api
```

#### Codes d'erreur

- **401 Unauthorized** : API Key manquante
- **403 Forbidden** : API Key invalide

## Validation des Inputs

### SIRET

Les numéros SIRET sont validés pour :
- Longueur exacte de 14 chiffres
- Format numérique uniquement
- Nettoyage automatique des espaces et caractères spéciaux

### Dates

Les dates sont validées et supportent les formats suivants :
- `YYYY-MM-DD` (ISO 8601)
- `DD/MM/YYYY` (format français)
- `YYYY/MM/DD`
- `DD-MM-YYYY`

### Fichiers Excel

Les fichiers uploadés sont validés pour :
- Type MIME accepté (Excel .xls ou .xlsx)
- Extension de fichier correcte
- Taille maximale (configurable, par défaut 50MB)

## Scripts de Migration

### clean_nan_values.py

**Description** : Script de migration one-time pour nettoyer les valeurs 'nan' dans les tables Invitation, PVEvent et SiretSummary.

**Utilisation** :
```bash
python scripts/clean_nan_values.py
```

**Colonnes affectées** :
- Invitation : `fd`, `ud`, `idcc`
- PVEvent : `fd`, `ud`, `idcc`
- SiretSummary : `fd_c3`, `fd_c4`, `ud_c3`, `ud_c4`, `idcc`

**Notes** :
- Ce script convertit les chaînes 'nan', 'NaN', 'NAN' en NULL
- Exécute toutes les modifications dans une transaction unique
- Affiche un rapport détaillé des modifications effectuées
- En cas d'erreur, effectue un rollback automatique

## Bonnes Pratiques

### Gestion des Secrets

1. ❌ **NE JAMAIS** commiter les clés API dans le code source
2. ✅ Utiliser des variables d'environnement pour tous les secrets
3. ✅ Utiliser un fichier `.env` en local (à ajouter dans `.gitignore`)
4. ✅ En production, configurer les secrets via le gestionnaire de secrets de votre plateforme (ex: Kubernetes Secrets, AWS Secrets Manager, etc.)

### Rotation des Clés

Changez régulièrement votre API Key (recommandé : tous les 90 jours minimum) :

1. Générez une nouvelle clé
2. Mettez à jour la variable d'environnement `ADMIN_API_KEY`
3. Redémarrez l'application
4. Mettez à jour tous les clients utilisant l'ancienne clé

### Logs et Monitoring

- Les tentatives d'accès non autorisées sont loggées
- Surveillez les logs pour détecter des tentatives d'attaque
- En production, activez un système d'alerting sur les erreurs 401/403

## Améliorations Futures

Pour renforcer la sécurité, envisagez :

1. **Rate Limiting** : Limiter le nombre de requêtes par IP/clé API
2. **OAuth2/JWT** : Pour une authentification plus robuste avec expiration de tokens
3. **Audit Logs** : Enregistrer toutes les opérations d'administration
4. **RBAC** : Rôles et permissions différenciés par endpoint
5. **HTTPS** : Forcer HTTPS en production (jamais HTTP pour les endpoints authentifiés)
