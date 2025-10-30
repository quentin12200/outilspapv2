# 🔧 Instructions de Migration - Base de Données avec Colonnes Sirene

## ✅ Migration Terminée

La base de données `pap.db` a été créée avec succès avec toutes les colonnes Sirene nécessaires !

**Fichier généré** : `pap.db` (32 KB)
**SHA256** : `40ffd2d5576c673e78f6f5816d90619c5e5674e01d81359e976bf81729f5b769`

## 📋 Tables créées

La base contient les 3 tables avec le schéma complet :

1. **pv_events** - Procès-verbaux des élections
2. **invitations** - Invitations PAP C5 avec colonnes Sirene :
   - `denomination` - Raison sociale
   - `enseigne` - Enseigne commerciale
   - `adresse` - Adresse complète
   - `code_postal` - Code postal
   - `commune` - Commune
   - `activite_principale` - Code NAF
   - `libelle_activite` - Libellé de l'activité
   - `tranche_effectifs` - Code tranche d'effectifs
   - `effectifs_label` - Libellé de la tranche
   - `est_siege` - Booléen siège social
   - `est_actif` - Booléen établissement actif
   - `categorie_entreprise` - PME, ETI, GE...
   - `date_enrichissement` - Date du dernier enrichissement
3. **siret_summary** - Résumé par SIRET

## 🚀 Prochaines Étapes

### 1. Uploader la base sur GitHub Release v1.0.0

Allez sur https://github.com/quentin12200/outilspapv2/releases/tag/v1.0.0 et :
- Cliquez sur "Edit release"
- Uploadez le fichier `pap.db` (situé dans `/home/user/outilspapv2/pap.db`)
- Sauvegardez

### 2. Configurer Railway

Allez dans **Railway → Votre Projet → Variables** et ajoutez/mettez à jour :

```
DB_URL=https://github.com/quentin12200/outilspapv2/releases/download/v1.0.0/pap.db
DB_SHA256=40ffd2d5576c673e78f6f5816d90619c5e5674e01d81359e976bf81729f5b769
```

**Note** : Comme votre repo est public, vous n'avez **PAS** besoin de `DB_GH_TOKEN`.

### 3. Redéployer sur Railway

Railway devrait redéployer automatiquement. Sinon :
- Railway → Votre Projet → Deployments → Redeploy

### 4. Vérifier l'API Sirene

Une fois redéployé, testez :
- `/api/sirene/stats` - Devrait retourner des statistiques JSON
- `/api/sirene/enrichir-tout` - Pour enrichir toutes les invitations
- `/recherche-siret` - Pour tester l'enrichissement individuel

## ⚠️ Important : Base de Données Vide

**Attention** : La base actuelle est vide (0 lignes dans chaque table).

### Option A : Importer vos données existantes

Si vous avez une base existante avec des données :

```bash
# Sauvegardez d'abord votre ancienne base
cp votre_ancienne_base.db backup.db

# Exportez les données de l'ancienne base
sqlite3 backup.db ".dump pv_events" > pv_events.sql
sqlite3 backup.db ".dump invitations" > invitations.sql
sqlite3 backup.db ".dump siret_summary" > siret_summary.sql

# Importez dans la nouvelle base
sqlite3 pap.db < pv_events.sql
sqlite3 pap.db < invitations.sql
sqlite3 pap.db < siret_summary.sql
```

### Option B : Utiliser la base vide

Si vous commencez de zéro, vous pouvez utiliser la base vide directement et :
1. Importer les données via l'interface web
2. Utiliser les scripts d'import si vous en avez

## 📄 Fichiers de Configuration Mis à Jour

Les fichiers suivants ont été mis à jour avec les bonnes valeurs :
- `.env.railway.example` - Variables d'environnement Railway
- `DEPLOYMENT.md` - Guide de déploiement complet

## 🐛 Dépannage

### L'API Sirene retourne toujours 500

1. Vérifiez que la nouvelle base a bien été uploadée sur GitHub Release v1.0.0
2. Vérifiez que les variables Railway sont correctes
3. Vérifiez les logs Railway : `Railway → Deployments → View Logs`
4. Cherchez le message : "SHA256 mismatch" ou "Failed to download database"

### La base est bien téléchargée mais l'API ne fonctionne pas

1. Vérifiez les logs Railway pour des erreurs SQL
2. Testez manuellement : `curl https://votre-app.railway.app/api/sirene/stats`
3. Si erreur "no such column", la base n'a pas les bonnes colonnes

## ✅ Résultat Attendu

Après ces étapes, vous devriez avoir :
- ✅ Base de données avec toutes les colonnes Sirene
- ✅ API Sirene fonctionnelle sur Railway
- ✅ Possibilité d'enrichir les SIRET avec l'API INSEE
- ✅ Affichage des données Sirene sur les pages détail SIRET

---

**Besoin d'aide ?** Consultez `DEPLOYMENT.md` pour plus de détails.
