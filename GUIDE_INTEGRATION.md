# Guide d'intégration — Migration vers la v2.0

Ce guide accompagne la mise à niveau depuis la branche historique vers `feat/dashboard-c5-c3c4-restore`.

## 1. Sauvegarder l'existant
- Exporter la base SQLite actuelle (`papcse.db`).
- Conserver les fichiers de configuration `.env` et scripts personnalisés.

## 2. Mettre à jour le code
```bash
git fetch origin
git checkout feat/dashboard-c5-c3c4-restore
git pull
```

## 3. Recréer l'environnement
```bash
rm -rf .venv
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 4. Adapter la configuration
1. Fusionner vos variables existantes avec le nouveau `.env.example`.
2. Vérifier les nouvelles variables : `ADMIN_USER`, `ADMIN_PASSWORD`, `LOG_FILE`, `AUDIT_LOG_FILE`.
3. Si la base SQLite est déjà disponible, définir `DATABASE_URL=sqlite:///chemin/vers/papcse.db`.
4. Sinon, fournir `DB_URL` et `DB_SHA256` pour téléchargement automatique.

## 5. Initialiser la base
- Copier le fichier SQLite sauvegardé vers le chemin attendu.
- Lancer `uvicorn app.main:app --reload` pour permettre à `ensure_schema` de créer/ajouter les colonnes manquantes (`pv_events.autres_indics`, nouvelles colonnes `siret_summary`).

## 6. Vérifications fonctionnelles
- `/health` doit retourner `{"status": "ok", "version": "2.0.0"}`.
- `/api/stats/global` doit afficher des volumes cohérents.
- `/` doit afficher le tableau avec métriques.
- `/dashboard` doit afficher les graphiques.
- `/admin` doit demander une authentification.

## 7. Reconstruire le tableau de synthèse
Depuis l'admin :
1. Cliquer sur **Mettre à jour le tableau** (POST `/api/admin/rebuild-summary`).
2. Vérifier que le message de succès apparaît et que les métriques globales sont cohérentes.

## 8. Régénérer les fichiers statiques (optionnel)
- `app/static/last_ciblage.csv` peut être replacé depuis la sauvegarde si nécessaire.
- Remplacer `app/static/img/logo.png` par votre visuel si besoin (dimensions similaires recommandées).

## 9. Recettes manuelles conseillées
- Importer un fichier PV test → vérifier le message dans l'admin et la mise à jour du tableau.
- Importer un fichier invitations test → idem.
- Tester un export CSV (`/exports/siret-summary/csv`) avec filtres.
- Vérifier la fiche d'un SIRET (`/siret/{siret}`).

## 10. Monitoring post-migration
- Surveiller `logs/app.log` et `logs/audit.log` les premiers jours.
- Mettre en place un cron pour sauvegarder régulièrement `papcse.db`.

Bon déploiement !
