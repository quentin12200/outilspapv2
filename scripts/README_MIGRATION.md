# Migration : Ajout des colonnes de géolocalisation

## Problème

La table `invitations` manque les colonnes `latitude` et `longitude` qui sont nécessaires pour :
- L'affichage des invitations sur la carte
- La géolocalisation des établissements

## Erreur rencontrée

```
sqlite3.OperationalError: no such column: invitations.latitude
```

## Solution

### Pour une nouvelle installation

Les colonnes sont créées automatiquement au démarrage de l'application grâce à `Base.metadata.create_all()`.

### Pour une base de données existante

Exécuter le script de migration :

```bash
# Depuis la racine du projet
python scripts/migrate_add_geolocation.py
```

### Sur le serveur de production (Railway)

Si vous avez accès SSH ou à un terminal :

```bash
# Se connecter au conteneur
# Puis exécuter
cd /app
python scripts/migrate_add_geolocation.py
```

Ou utiliser une migration Alembic si configuré.

### Alternative : Via l'application

Les colonnes peuvent aussi être ajoutées manuellement via SQLite :

```sql
ALTER TABLE invitations ADD COLUMN latitude FLOAT;
ALTER TABLE invitations ADD COLUMN longitude FLOAT;
```

## Vérification

Après la migration, vérifier que les colonnes existent :

```sql
PRAGMA table_info(invitations);
```

Les colonnes `latitude` et `longitude` doivent apparaître dans la liste.

## Impact

- ✅ La page `/invitations` fonctionnera correctement
- ✅ La cartographie pourra afficher les invitations géolocalisées
- ✅ Les nouvelles invitations pourront être géolocalisées

## Note importante

Ce script est **idempotent** : il peut être exécuté plusieurs fois sans risque. Il vérifie l'existence des colonnes avant de les ajouter.
