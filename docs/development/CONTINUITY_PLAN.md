# Continuité de l'outil PAP

Ce document propose des axes de travail pour prolonger les évolutions récentes tout en sécurisant le fonctionnement de l'outil.

## 1. Fiabilisation et automatisation des données
- **Plan de rechargement programmé** : script `scripts/` dédié qui rejoue l'import PAP et Sirene chaque nuit avec journalisation (succès, écarts, anomalies) et alertes en cas d'échec.
- **Validation croisée** : comparer automatiquement les invitations et PV entre `app/main.py` et l'API `app/routers/api.py` pour détecter les divergences de statuts ou de dates.
- **Versionnage des jeux de données** : conserver les fichiers sources dans un stockage objet (S3, Azure Blob…) avec un hash, consigné dans une table d'audit pour faciliter les retours arrière.

## 2. Observabilité et support
- **Tableau de bord interne** : exposer une page `/admin/health` qui agrège les métriques clés (nombre d'invitations par statut, délai moyen de publication PV, erreurs récentes) et le statut des tâches asynchrones.
- **Alerting proactif** : brancher les logs FastAPI/SQL sur un service (Sentry, Logtail…) avec seuils pour les erreurs 5xx, temps de réponse et incohérences de SIRET.
- **Guide de résolution** : compléter `README.md` avec une section « Incident response » décrivant les étapes de diagnostic (consultation des logs, relance des imports, etc.).

## 3. Performance et architecture
- **Extraction des calculs lourds** : déplacer les agrégations cycle 5 et PAP vers des vues matérialisées SQL ou des jobs batch pour soulager les requêtes en temps réel.
- **Pagination API** : généraliser `limit`/`offset` sur les endpoints listant les invitations ou les PV pour réduire la charge mémoire.
- **Tests de non-régression** : ajouter un dossier `tests/` avec des fixtures de SIRET synthétiques couvrant les cas C3/C4/C5, puis intégrer `pytest` dans le pipeline CI.

## 4. Expérience utilisateur
- **Exploration des statuts** : créer un onglet « Analyse » affichant la distribution temporelle des statuts PAP (barres empilées par mois) pour suivre les efforts terrain.
- **Recherche enrichie** : proposer des filtres rapides (boutons UD/FD favoris) et une aide contextuelle expliquant les codes statut directement dans `app/templates/invitations.html`.
- **Accessibilité continue** : poursuivre l'audit aria (focus management dans la modale de graphiques, contrastes des badges et messages lecteurs d'écran).

## 5. Gouvernance et documentation
- **Roadmap trimestrielle** : maintenir ce document ou un équivalent dans `docs/` avec l'état (À faire, En cours, Fait) pour suivre les priorités du cycle.
- **Partage de connaissances** : organiser des sessions de revue de code et documenter les règles métier (statuts, cycles, exceptions) dans un guide métier dédié.
- **Formation des contributrices** : préparer un tutoriel « premier déploiement » détaillant l'ouverture d'une branche, les tests à lancer et la procédure Railway.

Chaque piste est compatible avec l’architecture actuelle et renforce la continuité fonctionnelle du projet.
