# 🔧 Migration de la base de données - created_at / updated_at

## Problème résolu

**Erreur rencontrée:**
```
sqlite3.OperationalError: no such column: invitations.created_at
```

Cette erreur se produit quand vous avez une base de données existante qui ne contient pas les nouvelles colonnes `created_at` et `updated_at` ajoutées au modèle `Invitation`.

## ✅ Solution rapide

### Option 1 : Nouvelle installation (recommandé en développement)

Si vous démarrez une nouvelle installation ou que vous pouvez réinitialiser la base de données :

```bash
# Supprimer l'ancienne base de données (ATTENTION: perte de données)
rm papcse.db

# Créer une nouvelle base avec toutes les colonnes
python init_or_migrate_db.py
```

### Option 2 : Migration de la base existante (production)

Si vous avez des données existantes à conserver :

```bash
# Exécuter le script de migration
python init_or_migrate_db.py
```

Ce script va :
- ✅ Détecter automatiquement si la base existe
- ✅ Ajouter uniquement les colonnes manquantes
- ✅ Créer les index nécessaires
- ✅ Conserver toutes vos données existantes

## 📋 Scripts disponibles

### `init_or_migrate_db.py` (Recommandé)

Script intelligent qui détecte automatiquement l'état de la base :

```bash
python init_or_migrate_db.py
```

**Fonctionnalités:**
- ✨ Crée la base si elle n'existe pas
- 🔧 Ajoute les colonnes manquantes si la base existe
- 📊 Affiche un rapport détaillé
- ✅ Sécurisé : utilise des transactions

**Sortie attendue:**
```
🚀 Initialisation/Migration de la base de données
============================================================
📍 Base de données: papcse.db
✨ Nouvelle base de données - Création de toutes les tables...
✅ Toutes les tables ont été créées avec succès!
============================================================
✅ Table 'invitations': 30 colonnes
   ✅ id
   ✅ siret
   ✅ created_at
   ✅ updated_at
============================================================
🎉 Base de données prête à l'emploi!
```

### `add_timestamp_columns.py` (Migration SQLite pure)

Alternative utilisant SQLite directement (nécessite une base existante) :

```bash
python add_timestamp_columns.py
```

**Fonctionnalités:**
- 🔧 Ajoute `created_at` et `updated_at`
- 📊 Crée l'index sur `created_at`
- ⚠️ Nécessite que la base existe déjà

## 🏗️ Colonnes ajoutées

Les colonnes suivantes ont été ajoutées au modèle `Invitation` :

| Colonne | Type | Nullable | Default | Index | Description |
|---------|------|----------|---------|-------|-------------|
| `created_at` | DATETIME | NOT NULL | CURRENT_TIMESTAMP | ✅ | Date de création de l'invitation |
| `updated_at` | DATETIME | NULL | CURRENT_TIMESTAMP | ❌ | Date de dernière modification |

**Index créé:**
- `idx_invitations_created_at` sur la colonne `created_at`

## 🚀 Déploiement en production

### Étape 1 : Sauvegarde

**TOUJOURS faire une sauvegarde avant migration :**

```bash
# Copier la base de données
cp papcse.db papcse.db.backup.$(date +%Y%m%d_%H%M%S)
```

### Étape 2 : Migration

```bash
# Exécuter le script de migration
python init_or_migrate_db.py
```

### Étape 3 : Vérification

```bash
# Démarrer l'application
uvicorn app.main:app --reload

# Tester l'import PDF PAP
# → Aller sur /admin
# → Section "Importer PAP"
# → Upload un PDF test
```

### Étape 4 : Rollback (si problème)

Si la migration échoue :

```bash
# Arrêter l'application
# Ctrl+C

# Restaurer la sauvegarde
mv papcse.db.backup.XXXXXX_XXXXXX papcse.db

# Redémarrer
uvicorn app.main:app --reload
```

## 🔍 Vérification manuelle

Pour vérifier que les colonnes existent :

```python
# Dans un shell Python
from app.db import engine
from sqlalchemy import inspect

inspector = inspect(engine)
columns = [col['name'] for col in inspector.get_columns('invitations')]

print("created_at" in columns)  # Doit afficher: True
print("updated_at" in columns)  # Doit afficher: True
```

Ou avec SQLite directement :

```bash
# Si sqlite3 est installé
sqlite3 papcse.db "PRAGMA table_info(invitations);" | grep -E "created_at|updated_at"
```

## ⚠️ Problèmes courants

### Erreur : "database is locked"

**Cause:** L'application est en cours d'exécution.

**Solution:**
```bash
# Arrêter l'application (Ctrl+C)
# Puis relancer la migration
python init_or_migrate_db.py
```

### Erreur : "duplicate column name"

**Cause:** Les colonnes existent déjà.

**Solution:** Aucune action requise, c'est normal ! Le script détecte cela automatiquement.

### Erreur : "unable to open database file"

**Cause:** Problème de permissions.

**Solution:**
```bash
# Vérifier les permissions
ls -l papcse.db

# Corriger si nécessaire
chmod 644 papcse.db
```

## 📚 Contexte technique

### Pourquoi ces colonnes ?

Les colonnes `created_at` et `updated_at` sont nécessaires pour :

1. **Génération d'emails ciblée**
   - Seules les invitations créées dans la dernière heure reçoivent des emails
   - Évite les doublons pour les anciens PAP

2. **Tracking et audit**
   - Savoir quand une invitation a été importée
   - Suivre les modifications au fil du temps

3. **Analyses et statistiques**
   - Graphiques de la croissance des imports
   - Détection des pics d'activité

### Architecture de la solution

```
app/models.py (Modèle SQLAlchemy)
    ↓
    définit: created_at, updated_at
    ↓
init_or_migrate_db.py (Script de migration)
    ↓
    détecte si colonnes existent
    ↓
    [NON] → ALTER TABLE ADD COLUMN
    [OUI] → Aucune action
    ↓
    CREATE INDEX (si nécessaire)
    ↓
✅ Base de données à jour
```

## 🎓 Pour les développeurs

### Ajouter une migration à l'avenir

Si vous ajoutez de nouvelles colonnes au modèle :

1. Modifier `app/models.py`
2. Créer un script de migration similaire à `init_or_migrate_db.py`
3. Tester localement
4. Sauvegarder la base de production
5. Exécuter la migration en production
6. Vérifier que tout fonctionne

### Utiliser Alembic (optionnel)

Pour une gestion plus professionnelle des migrations :

```bash
# Installer Alembic
pip install alembic

# Initialiser Alembic
alembic init alembic

# Créer une migration
alembic revision --autogenerate -m "Ajout created_at et updated_at"

# Appliquer la migration
alembic upgrade head
```

## ✅ Checklist de validation

Après la migration :

- [ ] Script exécuté sans erreur
- [ ] Base de données contient `created_at` et `updated_at`
- [ ] Index `idx_invitations_created_at` créé
- [ ] Application démarre sans erreur
- [ ] Page `/admin` accessible
- [ ] Import PDF PAP fonctionne
- [ ] Génération d'emails fonctionne
- [ ] Export Excel fonctionne

---

**Dernière mise à jour:** 2025-01-29
**Version:** 1.0
