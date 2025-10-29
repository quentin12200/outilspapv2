# PV Retenus – Audience Interpro et SVE

Ce dépôt contient les fichiers liés au suivi de l’audience interprofessionnelle de la CGT,
notamment les bases de données issues des PV retenus.

## 🗄️ Contenu
- **`papcse.db`** : base de données SQLite utilisée pour l’analyse des PV CSE et SVE.
  Ce fichier n’est pas versionné dans Git pour des raisons de taille,
  mais il est disponible en téléchargement via les *Releases*.

📦 **Téléchargement direct :**
[👉 Télécharger la dernière version (.db)](https://github.com/quentin12200/outilspapv2/releases/latest)

> ℹ️ Définissez la variable d’environnement `DB_URL` avec l’URL de l’asset `papcse.db`
> (par exemple l’URL de la release ci-dessus) pour que l’application télécharge
> automatiquement la base si elle est absente. Utilisez `DB_SHA256` pour imposer
> l’empreinte attendue et `DB_GH_TOKEN` si l’archive est privée.

## 🔐 Vérification d’intégrité
Pour vérifier que le fichier téléchargé n’a pas été altéré, comparez le SHA-256 :

```bash
shasum -a 256 papcse.db
# ou
python - <<'PY'
from pathlib import Path
import hashlib

path = Path('papcse.db')
hasher = hashlib.sha256()
with path.open('rb') as fd:
    for chunk in iter(lambda: fd.read(1_048_576), b''):
        hasher.update(chunk)
print(hasher.hexdigest())
PY
```

Définissez la valeur attendue dans la variable d'environnement `DB_SHA256`
pour que l'application refuse automatiquement tout fichier qui ne correspond pas.
Les formats `36f5a9...` et `sha256:36f5a9...` sont acceptés.

## 🌐 Accéder à l'application en ligne

L'application est hébergée et accessible directement à l'adresse suivante :

[👉 outilspap.up.railway.app](https://outilspap.up.railway.app/)

## 🚀 Afficher l'application en local

1. **Installer les dépendances** :
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -U pip
   pip install -r requirements.txt
   ```
2. **Configurer l'environnement** :
   Dupliquez le fichier `.env.example` sous le nom `.env` pour définir les variables nécessaires.
   Assurez-vous d'indiquer un `DATABASE_URL` (par défaut `sqlite:///./papcse.db`) et, si besoin,
   un `DB_URL` pointant vers l'asset `papcse.db`.
3. **Lancer le serveur FastAPI** :
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
4. **Ouvrir l'application** :
   Rendez-vous sur [http://localhost:8000](http://localhost:8000) dans votre navigateur pour consulter l'interface.

💡 Vous pouvez également exécuter le script `run.sh` qui automatise ces étapes :

```bash
./run.sh
```
