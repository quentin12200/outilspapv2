# Checklist d'intégration

## Avant déploiement
- [ ] Sauvegarde de `papcse.db` réalisée.
- [ ] Variables d'environnement définies (`DATABASE_URL`, `DB_URL`, `DB_SHA256`, `ADMIN_*`).
- [ ] Fichier `.env` mis à jour à partir de `.env.example`.
- [ ] Nouveaux dossiers créés (`logs/`, `app/core/`, `tests/`).

## Après installation
- [ ] `uvicorn app.main:app --reload` démarre sans erreur.
- [ ] `/health` retourne le statut OK avec la version 2.0.0.
- [ ] `/api/stats/global` affiche des volumes cohérents (≈ 2800 invitations C5).
- [ ] Tableau d'accueil affiche des lignes PAP ↔ PV avec filtres fonctionnels.
- [ ] Dashboard affiche les compteurs et graphiques Plotly.
- [ ] Navigation (Accueil, Dashboard, Ciblage, Administration) opérationnelle.

## Administration
- [ ] Import PV testé (message de succès + rebuild automatique).
- [ ] Import invitations testé (message de succès + rebuild automatique).
- [ ] Bouton « Mettre à jour le tableau » fonctionnel.
- [ ] Export CSV/Excel déclenche un téléchargement exploitable.

## Qualité
- [ ] `pytest tests/ -v` passe avec succès.
- [ ] `logs/app.log` et `logs/audit.log` sont générés et accessibles.
- [ ] Vérification manuelle d'une fiche SIRET (historique PV + invitations).
- [ ] Vérification d'un filtrage multi-critères (ex. FD + OS + dates).

## Go live
- [ ] Cron/backup configuré pour `papcse.db`.
- [ ] Accès admin communiqué aux utilisateurs habilités.
- [ ] Documentation partagée (GUIDE_UTILISATEUR.md, GUIDE_INTEGRATION.md).
