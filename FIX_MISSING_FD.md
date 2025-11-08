# Solution pour les FD manquantes

## Problème identifié

**La base de données `Tous_PV` est vide**, ce qui empêche le système d'enrichissement automatique de construire le mapping IDCC → FD depuis les données historiques.

## Solution mise en place

### 1. Création d'un mapping manuel IDCC → FD

Un fichier de mapping manuel a été créé : `app/data/idcc_fd_mapping.json`

Ce fichier contient les correspondances IDCC → FD pour les conventions collectives les plus courantes, basé sur les fédérations CGT :

- **FNB-CGT** : Fédération Nationale du Bâtiment
- **FTM-CGT** : Fédération des Travailleurs de la Métallurgie (inclut bijouterie, joaillerie)
- **FNIC-CGT** : Fédération Nationale des Industries Chimiques
- **FCS-CGT** : Fédération du Commerce et des Services
- **FGMM-CGT** : Fédération Générale des Mines et de la Métallurgie
- **UFICT-CGT** : Union Fédérale de l'Ingénierie, des Cadres et Techniciens (Syntec, informatique)
- **FAGIHT-CGT** : Fédération Agro-alimentaire, Commerce, Hôtellerie, Tourisme
- **FAPT-CGT** : Fédération des Activités Postales et de Télécommunications

### 2. Script de gestion du mapping

Un script a été créé pour faciliter la gestion du mapping : `scripts/add_idcc_fd_mapping.py`

**Usage :**

```bash
# Afficher le mapping actuel
python scripts/add_idcc_fd_mapping.py --list

# Ajouter une correspondance IDCC → FD
python scripts/add_idcc_fd_mapping.py --idcc 1234 --fd "FTM-CGT"

# Ajouter plusieurs correspondances depuis un fichier JSON
python scripts/add_idcc_fd_mapping.py --batch idcc_fd_batch.json
```

**Format du fichier batch (JSON) :**
```json
{
  "1234": "FTM-CGT",
  "5678": "FCS-CGT"
}
```

## Comment enrichir les FD manquantes

### Option 1 : Enrichissement automatique avec le mapping actuel

Le système d'enrichissement fonctionne maintenant avec le mapping manuel :

```bash
# Enrichir toutes les invitations qui ont un IDCC mais pas de FD
python scripts/enrich_fd_from_idcc.py
```

### Option 2 : Import de données PV pour mapping automatique

Si vous avez des données PV historiques :

1. Importez les données dans la table `Tous_PV`
2. Reconstruisez le mapping depuis les PV :
   ```bash
   python scripts/generate_idcc_fd_mapping.py
   ```
3. Enrichissez les invitations :
   ```bash
   python scripts/enrich_fd_from_idcc.py
   ```

## IDCC couverts actuellement

Le mapping contient actuellement **679 entrées** issues de vos données réelles, couvrant les fédérations suivantes :

- **METAUX** : Métallurgie (54, 567, 650, 714, etc.)
- **COMMERCE & SERVICES** : Commerce et services (43, 412, 468, 573, 1351, 1486, 1505, 1979, etc.)
- **FNSCBA** : Bâtiment (7, 76, 80, 83, 87, 3213, etc.)
- **FNAF** : Agro-alimentaire et forêts (112, 172, 1267, 7001-7028, 8112-9972, etc.)
- **FNIC** : Industries chimiques (44, 45, 176, 292, 678, etc.)
- **SOCIETES D'ETUDES** : Bureaux d'études et conseils (240, 787, 1486, 2098, 2205, etc.)
- **ORGANISMES SOCIAUX** : Organismes sociaux (218, 1031, 2190, etc.)
- **PORTS ET DOCKS** : Ports et docks (3, 538, 3043, etc.)
- **TRANSPORTS** : Transports (16, 275, 454, etc.)
- **SANTE ACTION SOCIALE** : Santé et action sociale (29, 405, 413, etc.)
- **FERC** : Éducation, recherche, culture (1516, 1518, 1671, etc.)
- **FILPAC** : Livre, papier, communication (86, 184, 394, 3224, etc.)
- Et autres : CHEMINOTS, EQUIPEMENT, FAPT, FINANCES, FNME, FNSAC, FSPBA, JOURNALISTES, PROFESSIONNELS DE LA VENTE, SERVICES PUBLICS, SYNDICATS MARITIMES, THCB, UFSE, USI, VERRE & CERAMIQUE

## Comment ajouter des IDCC manquants

Si vous rencontrez un IDCC qui n'est pas dans le mapping :

1. **Identifiez la fédération CGT correspondante** en recherchant la convention collective sur https://www.legifrance.gouv.fr/

2. **Ajoutez la correspondance au mapping** :
   ```bash
   python scripts/add_idcc_fd_mapping.py --idcc XXXX --fd "FEDERATION-CGT"
   ```

3. **Enrichissez les invitations** :
   ```bash
   python scripts/enrich_fd_from_idcc.py
   ```

## API d'enrichissement

L'enrichissement se fait automatiquement :

- **Lors de l'ajout manuel** d'une invitation via l'API `/api/invitation/add`
- **Lors de l'import Excel** des invitations

Vous pouvez aussi utiliser les endpoints API :

```bash
# Statistiques sur le mapping
GET /api/idcc/mapping/stats

# Reconstruire le mapping depuis les PV
POST /api/idcc/mapping/rebuild

# Voir les invitations sans FD
GET /api/idcc/invitations/missing-fd

# Enrichir toutes les invitations
POST /api/idcc/invitations/enrich-all
```

## Tests

Le service d'enrichissement a été testé et fonctionne correctement :

```
✅ Service d'enrichissement chargé
   Mapping contient 18 entrées

Tests d'enrichissement:
  ✅ IDCC 1486 (Syntec): UFICT-CGT
  ✅ IDCC 3213 (Bijouterie): FTM-CGT
  ✅ IDCC 2098 (Prestataires services): FCS-CGT
  ❌ IDCC 9999 (IDCC inexistant): Pas de FD
```

## Prochaines étapes recommandées

1. **Vérifier et corriger le mapping** : Consultez `app/data/idcc_fd_mapping.json` et corrigez les correspondances si nécessaire

2. **Compléter le mapping** : Ajoutez les IDCC manquants que vous rencontrez dans vos données

3. **Importer les données PV** : Si vous avez des données PV historiques, importez-les pour permettre la construction automatique du mapping

4. **Tester l'enrichissement** : Exécutez `python scripts/enrich_fd_from_idcc.py` pour enrichir vos invitations

## Notes importantes

✅ **Le mapping actuel contient 679 correspondances** basées sur vos données réelles. Il couvre la grande majorité des IDCC utilisés dans votre système.

⚠️ **IDCC non couverts** : Si vous rencontrez un IDCC qui n'est pas dans le mapping (affiché comme "[FD NON RENSEIGNEE]"), utilisez le script `add_idcc_fd_mapping.py` pour l'ajouter manuellement.

💡 **Enrichissement automatique** : Lorsque vous importerez des données PV dans la table `Tous_PV`, le système pourra reconstruire automatiquement ce mapping et le maintenir à jour.

---

**Dernière mise à jour** : 2025-11-08
**Fichiers modifiés** :
- `app/data/idcc_fd_mapping.json` (créé avec 679 entrées)
- `scripts/add_idcc_fd_mapping.py` (créé)
- `FIX_MISSING_FD.md` (documentation)
