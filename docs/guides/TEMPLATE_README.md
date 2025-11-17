# 📋 Template d'import des invitations PAP

## Fichier template fourni

- **`template_invitations.csv`** : Template au format CSV avec exemples

## Comment utiliser le template

### Option 1 : Ouvrir avec Excel et sauvegarder en .xlsx

1. Ouvrir `template_invitations.csv` avec Microsoft Excel
2. Supprimer les lignes d'exemple (garder juste les en-têtes)
3. Ajouter vos données
4. **Fichier → Enregistrer sous → Format : Excel (.xlsx)**
5. Importer le fichier `.xlsx` sur https://outilspap.up.railway.app/admin

### Option 2 : Copier les en-têtes dans votre fichier Excel existant

Si vous avez déjà un fichier Excel avec vos données :

1. Ouvrir `template_invitations.csv` pour voir les noms de colonnes
2. Renommer vos colonnes pour qu'elles correspondent
3. Importer votre fichier

## Colonnes du template

| Colonne               | Obligatoire | Description                                    | Exemple                                    |
|-----------------------|-------------|------------------------------------------------|-------------------------------------------|
| SIRET                 | ✅ OUI      | Numéro SIRET à 14 chiffres                     | 12345678901234                            |
| Date invitation       | ✅ OUI      | Date d'invitation au PAP                       | 15/01/2025                                |
| Raison sociale        | ⭐ Recommandé | Nom de l'entreprise                           | EXEMPLE ENTREPRISE SAS                    |
| Enseigne              | Optionnel   | Enseigne commerciale                           | EXEMPLE & CO                              |
| Adresse               | ⭐ Recommandé | Adresse complète de l'établissement           | 10 rue de la République                   |
| Ville                 | ⭐ Recommandé | Ville                                         | Lyon                                      |
| Code Postal           | ⭐ Recommandé | Code postal                                   | 69001                                     |
| Source                | Optionnel   | Origine de l'invitation                        | Mail UD, RED, Courrier                    |
| Activité principale   | Optionnel   | Code NAF/APE                                   | 4711A                                     |
| Libellé activité      | Optionnel   | Description de l'activité                      | Commerce de détail                        |
| Effectifs             | Optionnel   | Tranche d'effectifs                            | 50 à 99 salariés                          |
| Actif                 | Optionnel   | Établissement actif ou fermé                   | Oui / Non                                 |
| Siège                 | Optionnel   | Siège social ou établissement secondaire       | Oui / Non                                 |

## Format des données

### SIRET
- **Format :** 14 chiffres sans espaces
- **Valide :** `12345678901234`
- **Invalide :** `123 456 789 01234`, `123456789`, `ABC123`

### Date
- **Formats acceptés :**
  - `15/01/2025` (JJ/MM/AAAA) ✅ Recommandé
  - `2025-01-15` (AAAA-MM-JJ)
  - `15-01-2025` (JJ-MM-AAAA)

### Actif / Siège
- **Valeurs acceptées :**
  - Pour OUI : `Oui`, `oui`, `1`, `yes`, `y`, `true`, `O`
  - Pour NON : `Non`, `non`, `0`, `no`, `n`, `false`, `N`
  - Vide = inconnu

## Générer un template Excel (.xlsx)

Si vous voulez créer un nouveau template Excel avec Python :

```python
import pandas as pd

# Créer un DataFrame avec les colonnes
df = pd.DataFrame(columns=[
    'SIRET', 'Date invitation', 'Raison sociale', 'Enseigne',
    'Adresse', 'Ville', 'Code Postal', 'Source',
    'Activité principale', 'Libellé activité', 'Effectifs',
    'Actif', 'Siège'
])

# Ajouter des exemples
df.loc[0] = [
    '12345678901234', '15/01/2025', 'EXEMPLE ENTREPRISE SAS', 'EXEMPLE & CO',
    '10 rue de la République', 'Lyon', '69001', 'Mail UD',
    '4711A', 'Commerce de détail', '50 à 99 salariés',
    'Oui', 'Oui'
]

# Sauvegarder en Excel
df.to_excel('template_invitations.xlsx', index=False)
print("✅ Template créé : template_invitations.xlsx")
```

## Validation avant import

Avant d'importer, vérifiez que :

- [ ] Les colonnes SIRET et Date sont remplies pour chaque ligne
- [ ] Les SIRET ont 14 chiffres
- [ ] Les dates sont au bon format
- [ ] Le fichier est au format .xlsx ou .xls
- [ ] Les en-têtes de colonnes correspondent aux noms attendus

## Support

Pour toute question, consultez le guide complet : **GUIDE_REIMPORT_INVITATIONS.md**
