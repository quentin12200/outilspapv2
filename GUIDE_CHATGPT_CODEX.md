# Guide de travail ChatGPT/Codex — Migration v2.0

Ce document résume les attentes lors de la prise en charge du projet PAP/CSE Dashboard par un agent automatique.

1. **Respecter la structure cible** : dossiers `app/core`, `app/routers`, `tests`, documentation Markdown.
2. **Sécurité** : toujours protéger les routes d'import et d'administration via `verify_admin` (HTTP Basic).
3. **Validation** : utiliser `app/core/validation.py` avant toute ingestion de fichiers Excel.
4. **Logging** : initialiser `setup_logging` dans `app/main.py` et consigner les opérations sensibles via `audit_logger`.
5. **Pagination** : exploiter `PageParams` + `paginate` + `build_pagination_html` pour les listes longues.
6. **Dashboard** : maintenir les métriques globales (`compute_global_stats`) et les graphiques Plotly.
7. **Exports** : garder les routes `/exports/...` compatibles avec les filtres du tableau.
8. **Tests** : ajouter/mettre à jour les tests unitaires (`pytest`) pour les helpers ETL.
9. **Documentation** : mettre à jour README + guides à chaque évolution majeure.
10. **Check final** : exécuter `pytest`, vérifier `/health`, recompiler la documentation avant de soumettre la PR.
