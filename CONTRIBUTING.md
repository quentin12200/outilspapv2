# Contribuer à PAP/CSE Dashboard

## Préparer son environnement
1. Cloner le dépôt et créer un virtualenv (`python -m venv .venv`).
2. Installer les dépendances (`pip install -r requirements.txt`).
3. Copier `.env.example` vers `.env` et définir au minimum `ADMIN_PASSWORD`.
4. Lancer les tests (`pytest`) avant toute PR.

## Règles de code
- Respecter la structure existante (module `app/core` pour les utilitaires, `app/routers` pour les routes).
- Ajouter des tests unitaires pour toute nouvelle fonction critique.
- Documenter les nouvelles variables d'environnement dans `.env.example` et le README.
- Ne jamais committer `papcse.db`, `.env` ou des données sensibles.

## Workflow Git
1. Créer une branche descriptive : `feat/...`, `fix/...`, `chore/...`.
2. Commits atomiques avec messages clairs (français accepté).
3. Vérifier `git status` → aucun fichier non suivi sensible.
4. Lancer `pytest` et, si pertinent, un démarrage local avant de soumettre la PR.

## Pull requests
- Décrire le contexte, les changements principaux et les tests effectués.
- Ajouter des captures d'écran pour les modifications UI notables.
- Mentionner toute migration de base nécessaire.

Merci pour votre contribution !
