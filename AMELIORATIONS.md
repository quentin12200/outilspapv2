# Améliorations v2.0

## Synthèse

- Authentification HTTP Basic pour toutes les opérations sensibles.
- Validation systématique des fichiers Excel (colonnes obligatoires, formats SIRET, dates plausibles).
- Ingestion idempotente : mise à jour des PV/invitations existants au lieu de dupliquer.
- Agrégat SIRET étendu avec FD normalisée, présence C3/C4, dates PAP/PV et scores syndicaux formatés.
- Calculs statistiques dédupliqués (`compute_global_stats`) exposés via `/api/stats/global`.
- Tableau d'accueil repensé : filtres combinables, pagination configurable, tri dynamique, indicateurs globaux.
- Dashboard analytique Plotly (présence, top départements, fédérations) et encart de compteurs.
- Exports CSV/Excel respectant les filtres actifs.
- Journaux applicatifs + audit trail (`logs/app.log`, `logs/audit.log`).
- Documentation complète (guides d'installation, d'utilisation, d'intégration, checklist).

## Détails techniques

| Domaine | Nouveautés |
|---------|------------|
| **Sécurité** | Module `app/core/security.py`, dépendance HTTP Basic, variables `ADMIN_USER`/`ADMIN_PASSWORD`. |
| **Validation** | `app/core/validation.py` avec rapports détaillés (erreurs, avertissements). |
| **Logging** | `app/core/logging_config.py` (console colorée, fichiers, audit logger). |
| **Pagination** | `app/core/pagination.py`, navigation accessible, HTML généré côté serveur. |
| **ETL** | `app/etl_improved.py` (classe `ETLResult`, ingestion robuste, normalisation FD/OS). |
| **Routes** | Nouveau routeur `/api` (imports, rebuild, stats), `/exports`, `/dashboard`. |
| **Templates** | `index_paginated.html`, `dashboard.html`, navigation unifiée dans `base.html`. |
| **Tests** | `tests/test_etl.py` couvre les helpers de normalisation. |
| **Docs** | README, guides, changelog, checklist mis à jour. |

## Prochaines pistes

- Mettre en place une authentification plus avancée (OAuth ou SSO interne) si nécessaire.
- Ajouter un bouton d'export direct sur l'accueil avec les filtres courants.
- Intégrer des tests d'intégration (ingestion + rebuild) avec base SQLite éphémère.
- Développer des widgets complémentaires (courbes temporelles CGT, carte choroplèthe).
