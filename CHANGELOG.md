# Changelog

## [2.0.0] — 2024-XX-XX
- Création de la branche `feat/dashboard-c5-c3c4-restore`.
- Authentification HTTP Basic pour l'administration et les imports.
- Nouveau moteur d'ingestion (`etl_improved.py`) avec validation, mises à jour idempotentes et journalisation.
- Reconstruction complète du tableau d'accueil : filtres combinables, pagination configurable, tri paramétrable.
- Exposition de statistiques globales dédupliquées via `compute_global_stats` et `/api/stats/global`.
- Ajout d'un dashboard graphique Plotly (présence, départements, fédérations).
- Ajout des exports CSV/Excel filtrés.
- Mise en place d'un audit log (`logs/audit.log`).
- Documentation refondue (README, guides, checklist) et ajout de tests unitaires de base.

## [1.x] — Versions précédentes
- Import manuel des PV et invitations sans authentification.
- Tableau d'accueil limité (100 lignes, filtres partiels).
- Absence de validation stricte des fichiers et de métriques globales.
