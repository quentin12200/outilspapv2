# Guide d'installation

Ce document détaille la mise en place complète de PAP/CSE Dashboard en environnement local ou serveur.

## 1. Prérequis

- Python 3.10 ou supérieur
- `pip` et `virtualenv`
- Git
- Accès internet (pour télécharger la base SQLite depuis les releases si nécessaire)

## 2. Récupération du projet

```bash
git clone https://github.com/quentin12200/outilspapv2.git
cd outilspapv2
```

## 3. Environnement Python

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

## 4. Configuration

1. Copier le fichier d'exemple :
   ```bash
   cp .env.example .env
   ```
2. Modifier `.env` pour définir :
   - `ADMIN_PASSWORD` (obligatoire) ;
   - `DATABASE_URL` si vous utilisez un autre chemin que `sqlite:///./papcse.db` ;
   - `DB_URL` et `DB_SHA256` pour que l'application télécharge automatiquement `papcse.db`.

> ℹ️ Pour des releases privées GitHub, définissez également `DB_GH_TOKEN` avec un token personnel disposant du scope `repo`.

## 5. Téléchargement manuel de la base (optionnel)

Si vous préférez gérer manuellement le fichier :

```bash
curl -L -o papcse.db "https://github.com/quentin12200/outilspapv2/releases/download/v1.0.0/papcse.db"
shasum -a 256 papcse.db  # Comparer avec la valeur officielle
```

Placez ensuite le fichier à l'emplacement attendu (`./papcse.db` si vous gardez l'URL par défaut).

## 6. Démarrage du serveur

```bash
uvicorn app.main:app --reload --port 8000
```

L'interface est accessible sur [http://localhost:8000](http://localhost:8000).

## 7. Accès administrateur

- Rendez-vous sur `/admin` et authentifiez-vous avec `ADMIN_USER` / `ADMIN_PASSWORD`.
- Depuis cette page, importez les fichiers Excel (PV, invitations) ou relancez la reconstruction du tableau.

## 8. Vérification du bon fonctionnement

```bash
# Tests unitaires
pytest tests/ -v

# Healthcheck
curl http://localhost:8000/health

# Statistiques globales
curl http://localhost:8000/api/stats/global
```

## 9. Déploiement (exemple Railway / Docker)

- Définir les variables d'environnement dans le tableau de bord (DATABASE_URL, DB_URL, DB_SHA256, ADMIN_USER/PASSWORD).
- Monter un volume persistant pour `/data` si vous laissez `sqlite:////data/papcse.db`.
- Utiliser `uvicorn app.main:app --host 0.0.0.0 --port $PORT` comme commande de démarrage.

## 10. Mise à jour

1. Récupérer la nouvelle version : `git pull`.
2. Mettre à jour les dépendances : `pip install -r requirements.txt`.
3. Redémarrer le service.

---
Besoin d'un rappel rapide ? Consultez également [GUIDE_INTEGRATION.md](GUIDE_INTEGRATION.md) pour migrer depuis la v1.0.
