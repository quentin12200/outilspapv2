# PAP/CSE Dashboard v2.0

Application FastAPI destinée au suivi des invitations PAP C5 et des PV C3/C4 afin de piloter l'implantation syndicale CGT. Cette version apporte une authentification simple, des filtres avancés, un dashboard graphique et un moteur d'agrégation résilient.

## ✨ Fonctionnalités clés

- **Accueil enrichi** : tableau filtrable (texte, FD, département, présence C3/C4, OS, bornes de dates) présentant uniquement les entreprises PAP ↔ PV par défaut.
- **Encart de métriques globales** : calculs dédupliqués (structures distinctes, lignes PAP/PV, correspondances) exposés via `GET /api/stats/global`.
- **Dashboard analytique** : graphiques Plotly (répartition présence, top départements, fédérations) et compteurs principaux.
- **Admin sécurisé** : imports Excel (PV, invitations) et reconstruction du résumé accessibles après authentification HTTP Basic.
- **Exports CSV/Excel** : téléchargements filtrés des agrégats ou des tables sources (`/exports/...`).
- **ETL robuste** : validation des fichiers, normalisation FD/OS, mise à jour idempotente et journalisation détaillée.

## 🧱 Architecture

```
app/
├── core/                # Sécurité, validation, pagination, logging
├── routers/             # API REST, exports, dashboard
├── templates/           # Jinja2 (accueil, dashboard, admin, ciblage, fiche SIRET)
├── etl_improved.py      # Ingestion & agrégation
├── models.py            # ORM SQLAlchemy
├── main.py              # Application FastAPI
└── static/              # Logo, scripts, fichiers importés
```

## 🚀 Démarrage rapide

1. **Cloner et créer l'environnement**
   ```bash
   git clone https://github.com/quentin12200/outilspapv2.git
   cd outilspapv2
   python -m venv .venv
   source .venv/bin/activate
   pip install -U pip
   pip install -r requirements.txt
   ```
2. **Configurer l'environnement**
   ```bash
   cp .env.example .env
   # Éditer ADMIN_PASSWORD, DATABASE_URL, DB_URL/DB_SHA256 si nécessaire
   ```
3. **Lancer le serveur**
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
4. **Ouvrir l'interface** : [http://localhost:8000](http://localhost:8000)

Le script `./run.sh` automatise ces étapes en local.

## ⚙️ Variables d'environnement principales

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | URL SQLAlchemy (par défaut `sqlite:///./papcse.db`). |
| `DB_URL` | URL HTTPS du fichier `papcse.db` à télécharger depuis les releases. |
| `DB_SHA256` | Empreinte attendue du fichier SQLite (optionnel mais recommandé). |
| `ADMIN_USER` / `ADMIN_PASSWORD` | Identifiants HTTP Basic pour l'espace admin. |
| `LOG_LEVEL` / `LOG_FILE` | Configuration des logs applicatifs. |
| `AUDIT_LOG_FILE` | Journalisation des imports/exports sensibles. |

## 🔐 Sécurité & journaux

- Authentification HTTP Basic obligatoire sur `/admin`, `/api/ingest/*`, `/api/admin/rebuild-summary` et `/ciblage/import`.
- Logs applicatifs centralisés dans `logs/app.log` (niveau configurable).
- Audit trail dans `logs/audit.log` pour suivre imports, exports et rebuilds.

## 📊 API & endpoints

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `GET` | `/` | Tableau principal avec filtres et pagination. |
| `GET` | `/dashboard` | Visualisations Plotly (présence, départements, fédérations). |
| `GET` | `/api/stats/global` | Statistiques globales dédupliquées. |
| `POST` | `/api/ingest/pv` | Import Excel des PV C3/C4 (auth requis). |
| `POST` | `/api/ingest/invit` | Import Excel des invitations PAP C5 (auth requis). |
| `POST` | `/api/admin/rebuild-summary` | Reconstruit la table agrégée SIRET (auth requis). |
| `GET` | `/exports/siret-summary/csv` | Export CSV filtré du tableau de synthèse. |
| `GET` | `/exports/siret-summary/excel` | Export Excel filtré. |
| `GET` | `/exports/pv-events/csv` | Export CSV des PV bruts. |
| `GET` | `/exports/invitations/csv` | Export CSV des invitations. |
| `GET` | `/siret/{siret}` | Fiche détaillée d'une structure (PV & invitations). |
| `POST` | `/ciblage/import` | Import CSV de ciblage (auth requis). |

## ✅ Tests

Lancer la suite de tests unitaires :
```bash
pytest tests/ -v
```

## 📚 Documentation complémentaire

- [INSTALLATION.md](INSTALLATION.md) — Guide d'installation détaillé.
- [GUIDE_UTILISATEUR.md](GUIDE_UTILISATEUR.md) — Mode d'emploi pour les militant·es.
- [GUIDE_INTEGRATION.md](GUIDE_INTEGRATION.md) — Étapes d'intégration de la v2.0 dans un projet existant.
- [AMELIORATIONS.md](AMELIORATIONS.md) — Liste des améliorations apportées.
- [CHECKLIST_INTEGRATION.md](CHECKLIST_INTEGRATION.md) — Liste de contrôle avant mise en production.
- [CHANGELOG.md](CHANGELOG.md) — Historique des versions.
- [CONTRIBUTING.md](CONTRIBUTING.md) — Règles de contribution.

## 📦 Téléchargement de la base de données

Les releases GitHub contiennent le fichier `papcse.db`. Configurez `DB_URL` et, idéalement, `DB_SHA256` pour que l'application télécharge et valide automatiquement la base lors du démarrage. Exemple :

```bash
export DB_URL="https://github.com/quentin12200/outilspapv2/releases/download/v1.0.0/papcse.db"
export DB_SHA256="36f5a979939849c7429d2ea3f06d376de3485dc645b59daf26b2be2eb866d6b8"
```

Bon déploiement ! ✊
