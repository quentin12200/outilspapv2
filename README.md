# PV Retenus – Audience Interpro et SVE

Ce dépôt contient les fichiers liés au suivi de l’audience interprofessionnelle de la CGT,
notamment les bases de données issues des PV retenus.

## 🗄️ Contenu
- **`papcse.db`** : base de données SQLite utilisée pour l’analyse des PV CSE et SVE.
  Ce fichier n’est pas versionné dans Git pour des raisons de taille,
  mais il est disponible en téléchargement via les *Releases*.

📦 **Téléchargement direct :**
[👉 Télécharger la dernière version (.db)](https://github.com/quentin12200/PV-retenus-branche-interpro-Audience-et-SVE/releases/latest)

> ℹ️ Depuis la plateforme ou en local, l'application télécharge automatiquement
> l'asset `papcse.db` de la dernière *Release* publique lorsqu'aucun fichier
> SQLite valide n'est trouvé sur le disque. Vous pouvez surcharger ce
> comportement via les variables `DATABASE_RELEASE_URL`, `DATABASE_RELEASE_ASSET`
> ou désactiver la récupération avec `DATABASE_RELEASE_SKIP=1`.

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

Définissez la valeur attendue dans la variable d'environnement `DATABASE_RELEASE_SHA256` (ou `DATABASE_RELEASE_CHECKSUM`) pour que l'application refuse automatiquement tout fichier qui ne correspond pas. Les formats `36f5a9...` et `sha256:36f5a9...` sont acceptés.

> Exemple : `DATABASE_RELEASE_SHA256="sha256:36f5a979939849c7429d2ea3f06d376de3485dc645b59daf26b2be2eb866d6b8"`

Lorsqu'un checksum est fourni, une base existante est validée au démarrage ; si elle ne correspond pas, l'application retélécharge l'asset de release jusqu'à trouver une copie conforme (dans la mesure du possible) avant de poursuivre.

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
3. **Lancer le serveur FastAPI** :
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
4. **Ouvrir l'application** :
   Rendez-vous sur [http://localhost:8000](http://localhost:8000) dans votre navigateur pour consulter l'interface.

ℹ️ **Base SQLite existante** :
Si vous disposez déjà d'un fichier `papcse.db`, placez-le à la racine du projet ou indiquez son répertoire via la
variable d'environnement `DATABASE_SEARCH_PATHS` (séparateur `:`) afin que l'application détecte automatiquement
la base lors du démarrage. Vous pouvez aussi pointer directement vers un fichier précis via `DATABASE_PATH` ou
`DATABASE_FILE`, ou fournir un répertoire d'attache grâce à `DATABASE_DIR` (par exemple le volume persistant Railway
exposé dans `RAILWAY_VOLUME_PATH`). L'application sonde également les variantes `papcse.sqlite`/`papcse.sqlite3`
présentes dans ces emplacements avant de créer une nouvelle base et, en dernier recours, retélécharge la base
depuis la dernière release si aucune copie locale n'est disponible.

💡 Vous pouvez également exécuter le script `run.sh` qui automatise ces étapes :

```bash
./run.sh
```

