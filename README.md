# PV Retenus – Audience Interpro et SVE

Ce dépôt contient les fichiers liés au suivi de l’audience interprofessionnelle de la CGT,
notamment les bases de données issues des PV retenus.

## 🗄️ Contenu
- **`papcse.db`** : base de données SQLite utilisée pour l’analyse des PV CSE et SVE.  
  Ce fichier n’est pas versionné dans Git pour des raisons de taille,  
  mais il est disponible en téléchargement via les *Releases*.

📦 **Téléchargement direct :**
[👉 Télécharger la dernière version (.db)](https://github.com/quentin12200/outilspapv2/releases/latest)

ℹ️ **Où placer le fichier ?** Déposez `papcse.db` à la racine du dépôt (au même niveau
que ce README) ou mettez à jour la variable d’environnement `DATABASE_URL` pour pointer
vers son emplacement.

## 🔐 Vérification d’intégrité
Pour vérifier que le fichier téléchargé n’a pas été altéré, comparez le SHA-256 :

```bash
sha256sum papcse.db
# 36f5a979939849c7429d2ea3f06d376de3485dc645b59daf26b2be2eb866d6b8  papcse.db
```

