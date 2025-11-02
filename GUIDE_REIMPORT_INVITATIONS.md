# 📥 Guide : Réimporter les invitations PAP

## Pourquoi réimporter ?

Si le tableau des invitations affiche des colonnes vides (—), c'est que les données ont été importées avant la mise à jour du code. **Réimporter les données** est la solution la plus simple et la plus sûre. Vous pouvez également configurer la variable d'environnement `INVITATIONS_URL` pour que l'import se fasse automatiquement à chaque nouveau déploiement (voir `DATABASE_CONFIG.md`). Sans configuration explicite, l'application tentera de récupérer un fichier `papcse-invitations.xlsx` (ou `.csv`) présent sur la même release GitHub que `papcse.db`.

---

## 🎯 Étapes pour réimporter

### Étape 1 : Accéder à la page d'administration

1. Aller sur : **https://outilspap.up.railway.app/admin**
2. Vous verrez 4 sections :
   - Import PV (bleu)
   - **Import Invitations PAP** (vert) ← C'est celle-ci !
   - Import Ciblage (violet)
   - Mettre à jour le tableau (orange)

### Étape 2 : Préparer votre fichier Excel

Votre fichier Excel doit contenir **au minimum** une colonne `SIRET` et une colonne `date`. Les autres colonnes sont optionnelles mais recommandées.

#### 📋 Colonnes reconnues automatiquement

Le système reconnaît automatiquement plusieurs variantes de noms de colonnes :

| Donnée attendue       | Noms de colonnes acceptés (exemples)                              |
|-----------------------|-------------------------------------------------------------------|
| **SIRET** (OBLIGATOIRE) | `siret`, `SIRET`, `n_siret`, `Numéro SIRET`                      |
| **Date invitation** (OBLIGATOIRE) | `date invitation`, `date_invitation`, `date`, `date_pap`, `Date PAP` |
| Raison sociale        | `raison sociale`, `raison_sociale`, `denomination`, `rs`, `nom`, `Raison sociale` |
| Enseigne              | `enseigne`, `enseigne_commerciale`, `Enseigne commerciale`        |
| Adresse               | `adresse`, `adresse_1`, `adresse_complete`, `Adresse ligne 1`     |
| Ville                 | `ville`, `commune`, `localite`, `Ville`                           |
| Code postal           | `code postal`, `cp`, `code_postal`, `Code Postal`                 |
| Source                | `source`, `origine`, `canal`, `Source`                            |
| Activité (NAF)        | `activite_principale`, `code_naf`, `naf`, `ape`, `NAF`, `APE`    |
| Libellé activité      | `libelle_activite`, `libelle activité`, `activite`                |
| Effectifs             | `effectifs`, `effectif`, `tranche_effectifs`, `Effectifs`         |
| Établissement actif   | `est_actif`, `actif`, `etat_etablissement`, `etat`, `Actif`       |
| Siège social          | `est_siege`, `siege`, `siege_social`, `Siège social`              |
| Catégorie entreprise  | `categorie_entreprise`, `categorie`, `taille_entreprise`, `taille` |

**Notes importantes :**
- ✅ Les noms de colonnes sont **insensibles à la casse** (`SIRET` = `siret` = `Siret`)
- ✅ Les espaces et accents sont gérés automatiquement
- ✅ Vous pouvez utiliser n'importe quelle variante listée ci-dessus

#### 📄 Exemple de fichier Excel valide

**Exemple 1 : Format minimal (2 colonnes obligatoires)**
```
SIRET          | Date invitation
---------------------------------
12345678901234 | 15/01/2025
98765432109876 | 20/01/2025
```

**Exemple 2 : Format complet (recommandé)**
```
SIRET          | Date invitation | Raison sociale      | Enseigne     | Adresse           | Ville      | Code Postal | Source
-------------------------------------------------------------------------------------------------------------------------------
12345678901234 | 15/01/2025     | ENTREPRISE DUPONT   | DUPONT SARL  | 10 rue de Paris   | Lyon       | 69001       | Mail UD
98765432109876 | 20/01/2025     | SOCIETE MARTIN      | MARTIN & CO  | 5 avenue Victor   | Marseille  | 13001       | RED
```

**Exemple 3 : Format avec NAF et effectifs**
```
SIRET          | Date | Raison sociale    | Ville     | CP    | NAF   | Libellé activité              | Effectifs | Actif
------------------------------------------------------------------------------------------------------------------------
12345678901234 | 15/01/2025 | DUPONT SAS  | Lyon      | 69001 | 4711A | Commerce de détail            | 50 à 99   | Oui
98765432109876 | 20/01/2025 | MARTIN SARL | Marseille | 13001 | 8299Z | Services administratifs       | 20 à 49   | Oui
```

### Étape 3 : Importer le fichier

1. Sur la page `/admin`, section **"Importer Invitations PAP"** (cadre vert)
2. Cliquer sur **"Sélectionnez le fichier Excel des invitations"**
3. Choisir votre fichier `.xlsx` ou `.xls`
4. Cliquer sur **"Importer les invitations"** (bouton vert)

### Étape 4 : Vérifier l'import

Après l'import, la page se rafraîchit automatiquement. Vous verrez :

1. **En bas de la page admin** : Un tableau avec les dernières invitations importées
2. Vérifier que les colonnes sont bien remplies

### Étape 5 : Voir les résultats

1. Aller sur **https://outilspap.up.railway.app/invitations**
2. Vérifier que le tableau affiche maintenant :
   - ✅ SIRET (cliquable)
   - ✅ Raison sociale
   - ✅ Enseigne
   - ✅ Adresse
   - ✅ Ville
   - ✅ Code postal
   - ✅ Source
   - ✅ Actif (Oui/Non)
   - ✅ Siège (Oui/Non)
   - ✅ Activité
   - ✅ Effectifs

---

## ⚠️ Questions fréquentes

### Q1 : Que se passe-t-il si j'importe plusieurs fois le même fichier ?

**R :** Les invitations sont ajoutées à la base. Si le même SIRET avec la même date existe déjà, vous aurez un doublon.

**Solution :** Supprimer les anciennes données avant de réimporter (voir section "Suppression" ci-dessous)

### Q2 : Mon fichier Excel a des noms de colonnes différents

**R :** Pas de problème ! Le système reconnaît automatiquement de nombreuses variantes (voir tableau ci-dessus). Par exemple :
- `Raison sociale` = `raison_sociale` = `denomination` = `rs` = `nom`
- `Code Postal` = `cp` = `code_postal`

Si votre colonne n'est pas reconnue, renommez-la dans Excel avant l'import.

### Q3 : Certaines colonnes sont optionnelles, lesquelles sont importantes ?

**Obligatoires :**
- ✅ SIRET
- ✅ Date invitation

**Fortement recommandées :**
- ⭐ Raison sociale
- ⭐ Adresse
- ⭐ Ville
- ⭐ Code postal

**Optionnelles mais utiles :**
- Enseigne
- NAF / Activité
- Effectifs
- Source

### Q4 : Le format de date n'est pas reconnu

**R :** Les formats acceptés :
- `15/01/2025` (JJ/MM/AAAA)
- `2025-01-15` (AAAA-MM-JJ)
- `15-01-2025` (JJ-MM-AAAA)
- `15.01.2025` (JJ.MM.AAAA)

Excel doit formater la cellule comme **Date** (pas comme Texte).

### Q5 : Comment supprimer les anciennes invitations avant de réimporter ?

**Méthode 1 : Via Railway (recommandée)**
```bash
# Se connecter à Railway
railway link

# Ouvrir un shell Python
railway run python

# Dans le shell Python :
>>> from app.db import SessionLocal
>>> from app.models import Invitation
>>> session = SessionLocal()
>>> session.query(Invitation).delete()  # Supprime toutes les invitations
>>> session.commit()
>>> print("✅ Toutes les invitations supprimées")
>>> exit()
```

**Méthode 2 : SQL direct**
```bash
railway run sqlite3 papcse.db "DELETE FROM invitations;"
```

⚠️ **ATTENTION :** Cette action est irréversible ! Assurez-vous d'avoir une sauvegarde.

### Q6 : Puis-je importer plusieurs fichiers Excel ?

**R :** Oui ! Vous pouvez importer plusieurs fichiers successivement. Les données s'ajoutent à la base.

**Conseil :** Si vous avez plusieurs fichiers, fusionnez-les en un seul dans Excel avant l'import pour éviter les doublons.

---

## 🔧 Dépannage

### Problème : L'import échoue avec une erreur

**Vérifications :**
1. ✅ Le fichier est bien au format `.xlsx` ou `.xls`
2. ✅ Il contient au moins les colonnes `SIRET` et `date`
3. ✅ Les SIRET sont bien des nombres à 14 chiffres
4. ✅ Les dates sont au bon format
5. ✅ Le fichier n'est pas corrompu (ouvrez-le dans Excel pour vérifier)

### Problème : Après l'import, le tableau est toujours vide

**Solutions :**
1. Vérifier que l'import a bien fonctionné (voir en bas de `/admin`)
2. Vider le cache du navigateur (Ctrl+F5)
3. Vérifier les logs de l'application :
   ```bash
   railway logs
   ```
4. Exécuter le script de migration :
   ```bash
   railway run python scripts/migrate_and_fix_invitations.py
   ```

### Problème : Certaines colonnes sont toujours vides après import

**Cause probable :** Ces colonnes n'existent pas dans votre fichier Excel ou ont un nom différent.

**Solution :**
1. Ouvrir votre fichier Excel
2. Vérifier les noms des en-têtes de colonnes
3. Les renommer si nécessaire (voir tableau des noms acceptés)
4. Réimporter le fichier

---

## 📊 Workflow complet recommandé

### Première import

```
1. Préparer fichier Excel avec toutes les colonnes
2. Aller sur /admin
3. Importer le fichier (section verte)
4. Vérifier le résultat sur /invitations
```

### Ajout de nouvelles invitations

```
1. Préparer fichier Excel avec SEULEMENT les nouvelles invitations
2. Aller sur /admin
3. Importer le fichier
4. (Optionnel) Mettre à jour le tableau (section orange)
```

### Correction/Mise à jour complète

```
1. Sauvegarder les données actuelles (export SQL)
2. Supprimer toutes les invitations (voir Q5)
3. Importer le fichier complet et corrigé
4. Mettre à jour le tableau (section orange)
5. Vérifier sur /invitations
```

---

## 📞 Support

Si le problème persiste après avoir suivi ce guide :

1. Vérifier les logs :
   ```bash
   railway logs
   ```

2. Exécuter le diagnostic :
   ```bash
   railway run python scripts/migrate_and_fix_invitations.py
   ```

3. Créer une issue sur GitHub avec :
   - Capture d'écran du tableau vide
   - Extrait du fichier Excel (3-5 lignes, SIRET anonymisés)
   - Logs de l'application

---

## ✅ Checklist finale

Avant de réimporter, vérifiez :

- [ ] J'ai un fichier Excel avec les colonnes SIRET et date
- [ ] Les noms de colonnes correspondent aux variantes acceptées
- [ ] Les SIRET sont à 14 chiffres
- [ ] Les dates sont au format JJ/MM/AAAA ou AAAA-MM-JJ
- [ ] J'ai sauvegardé les données actuelles (si nécessaire)
- [ ] J'ai supprimé les anciennes invitations (si je veux éviter les doublons)

Après l'import, vérifiez :

- [ ] La page /admin affiche les invitations en bas
- [ ] La page /invitations affiche le tableau rempli
- [ ] Toutes les colonnes importantes sont visibles
- [ ] Les filtres fonctionnent correctement
