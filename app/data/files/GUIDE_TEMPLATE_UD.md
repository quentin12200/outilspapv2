# Guide Template - Tableau de Bord Union Départementale CGT

## 📋 Vue d'ensemble

Ce template est conçu pour **standardiser et automatiser** la création de tableaux de bord pour les Unions Départementales CGT. Il est optimisé pour être utilisé avec **Claude Code** et peut facilement s'intégrer avec le **PAP CSE Dashboard**.

## 🎯 Objectifs du template

1. **Générique** : Adaptable à n'importe quelle UD en quelques modifications
2. **Structuré** : Format JSON/Markdown facilement parsable par l'IA
3. **Complet** : Couvre tous les aspects du suivi syndical (élections, implantations, contacts)
4. **Évolutif** : Permet d'ajouter de nouvelles fonctionnalités

## 📊 Structure du fichier Excel original

### Feuille 1 : TDB {NUM_DEPT}
**Objectif** : Organiser les réunions et événements de l'UD

**Colonnes principales** :
- `ORGANISATION` : Nom de l'événement/réunion
- `DATE ET HEURE` : Planification temporelle
- `RUBRIQUE` : Catégorie de l'événement
- `PRÉSENTATEUR` : Responsable de l'animation
- `Ordre du jour` : Points à traiter
- `Référent CEC` : Lien avec les comités centraux

**Usage** : Planification et suivi des activités de l'UD

---

### Feuille 2 : A CIBLE
**Objectif** : Suivi des entreprises où **la CGT est présente** avec potentiel de développement

**Colonnes clés** :
```
CIBLE                    → Nom de l'entreprise
N° SIRET                 → Identifiant unique (crucial pour PAP CSE)
NB SALARIES              → Effectif
DATE PRESENTATION CE     → Date de passage au CE
DATE SCRUTIN             → Date des élections
SUIVI PAP                → État du Protocole d'Accord Préélectoral
VOIX CGT                 → Résultats électoraux
NB SYNDIQUES             → Nombre d'adhérents
PILOTE                   → Responsable UD du dossier
ENJEUX                   → Analyse stratégique
CONTACT / TELEPHONE / MAIL → Coordonnées terrain
```

**Indicateurs calculables** :
- Taux de syndicalisation = NB SYNDIQUES / NB SALARIES
- Résultat électoral = VOIX CGT / total exprimés
- Échéance prochaine = DATE SCRUTIN + cycle électoral

---

### Feuille 3 : A CIBLE ABSENTE
**Objectif** : Suivi des entreprises où **la CGT n'est pas encore présente**

**Spécificités** :
- Même structure que "A CIBLE"
- Ajout de colonnes : `UD`, `ANNEE`
- Focus sur **l'implantation** plutôt que le développement

**Usage** : Cibler les entreprises prioritaires pour créer une section syndicale

---

### Feuille 4 : AVS
**Objectif** : Annuaire national des Animateurs Vie Syndicale

**Colonnes** :
```
DPT                              → Numéro département (01-95, 2A, 2B)
UD                               → Nom de l'Union Départementale
NOM / PRENOM                     → Identité de l'animateur
TEL PORTABLE / TEL UD            → Contacts
En responsabilité depuis le      → Date de prise de fonction
MAIL                             → Email
```

**Note importante** : Cette feuille est **commune à toutes les UD** (liste nationale). Utiliser un filtre sur `DPT` pour isoler son département.

---

### Feuille 5 : CARTE EVS
**Objectif** : Visualisation géographique (peut être vide)

---

### Feuille 6 : COORDONNEES EVS
**Objectif** : Contacts de l'équipe confédérale Vie Syndicale (Montreuil)

**Colonnes** :
```
NOM Prénom    → Conseiller confédéral
Mail          → Email @cgt.fr
Téléphone     → Direct
Fonction      → Conseiller.ère, Animateur.rice, Responsable de pôle
Pôle          → Droits et moyens syndicaux, etc.
Espace        → VIE SYNDICALE
```

**Note** : Liste de référence commune, ne pas modifier

---

## 🔧 Adaptation pour une nouvelle UD

### Étape 1 : Configuration de base
```json
{
  "configuration_ud": {
    "numero_departement": "34",
    "nom_departement": "Hérault",
    "code_ud": "ud34"
  }
}
```

### Étape 2 : Renommer les feuilles
- `TDB 66` → `TDB 34`
- Conserver les autres noms inchangés

### Étape 3 : Vider les données, garder la structure
```python
# Exemple avec pandas
import pandas as pd

# Lire le template
df_cible = pd.read_excel('template_ud.xlsx', sheet_name='A CIBLE')

# Garder seulement les en-têtes (ligne 0)
df_vide = pd.DataFrame(columns=df_cible.columns)

# Sauvegarder
df_vide.to_excel('ud34_nouveau.xlsx', sheet_name='A CIBLE', index=False)
```

### Étape 4 : Laisser les données nationales
- Feuille `AVS` : **Ne pas modifier** (liste nationale)
- Feuille `COORDONNEES EVS` : **Ne pas modifier** (équipe confédérale)

---

## 🤖 Utilisation avec Claude Code

### Commandes types

#### 1. Créer un nouveau tableau de bord pour une UD
```bash
# Prompt pour Claude Code
"Crée un nouveau tableau de bord UD pour le département 34 (Hérault) 
en te basant sur le template JSON fourni. 
Le fichier Excel doit contenir toutes les feuilles avec la bonne structure 
mais sans données dans A CIBLE et A CIBLE ABSENTE."
```

#### 2. Analyser un tableau de bord existant
```bash
# Prompt pour Claude Code
"Analyse le fichier TABLEAU_de_BORD__SUIVI_UD_EVS_2024_11V3.xlsx 
et génère un rapport JSON avec :
- Nombre d'entreprises cibles
- Nombre d'élections à venir dans les 6 mois
- Liste des SIRET pour intégration PAP CSE Dashboard
- Indicateurs de syndicalisation par entreprise"
```

#### 3. Synchroniser avec PAP CSE Dashboard
```bash
# Prompt pour Claude Code
"Extrais tous les SIRET et résultats électoraux de A CIBLE et A CIBLE ABSENTE
et génère un fichier CSV compatible avec l'import PAP CSE Dashboard.
Format : SIRET, NB_SALARIES, DATE_SCRUTIN, VOIX_CGT, NB_SYNDIQUES, PILOTE"
```

#### 4. Générer des rapports
```bash
# Prompt pour Claude Code
"Génère un rapport Markdown avec :
1. Synthèse par entreprise (A CIBLE)
2. Calendrier des prochaines échéances électorales
3. Tableau des entreprises sans CGT (A CIBLE ABSENTE) triées par effectif
4. Contacts des pilotes par dossier"
```

---

## 🔗 Intégration avec PAP CSE Dashboard

### Champs compatibles

| Colonne Excel | Champ Dashboard | Type | Obligatoire |
|---------------|-----------------|------|-------------|
| N° SIRET | siret | string(14) | ✅ |
| CIBLE | nom_entreprise | string | ✅ |
| NB SALARIES | nb_salaries | integer | ✅ |
| DATE SCRUTIN | date_election | date | ✅ |
| VOIX CGT | voix_cgt | integer | ❌ |
| NB SYNDIQUES | nb_syndiques | integer | ❌ |
| PILOTE | pilote | string | ❌ |
| idcc | idcc | string | ❌ |

### Script d'export vers Dashboard

```python
import pandas as pd
import json

def export_vers_dashboard(fichier_excel, ud_code):
    """
    Exporte les données A CIBLE vers un format compatible PAP CSE Dashboard
    """
    df = pd.read_excel(fichier_excel, sheet_name='A CIBLE')
    
    # Filtrer les lignes avec SIRET
    df = df[df['N° SIRET'].notna()]
    
    # Mapper vers le format Dashboard
    export = []
    for _, row in df.iterrows():
        export.append({
            'siret': str(row['N° SIRET']).replace(' ', ''),
            'nom_entreprise': row['CIBLE'],
            'nb_salaries': int(row['NB SALARIES']) if pd.notna(row['NB SALARIES']) else None,
            'date_election': row['DATE SCRUTIN'].strftime('%Y-%m-%d') if pd.notna(row['DATE SCRUTIN']) else None,
            'voix_cgt': int(row['VOIX CGT']) if pd.notna(row['VOIX CGT']) else None,
            'nb_syndiques': int(row['NB SYNDIQUES']) if pd.notna(row['NB SYNDIQUES']) else None,
            'pilote': row['PILOTE'] if pd.notna(row['PILOTE']) else None,
            'ud_code': ud_code,
            'source': 'tableau_bord_ud'
        })
    
    return export

# Utilisation
data = export_vers_dashboard('TABLEAU_de_BORD__SUIVI_UD_EVS_2024_11V3.xlsx', 'ud66')
with open('export_dashboard.json', 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
```

---

## 📊 Indicateurs et KPI automatisables

### Par entreprise
```python
def calculer_indicateurs_entreprise(row):
    return {
        'taux_syndicalisation': (row['NB SYNDIQUES'] / row['NB SALARIES'] * 100) 
                                 if row['NB SALARIES'] > 0 else 0,
        'performance_electorale': row['VOIX CGT'],  # À compléter avec total exprimés
        'jours_avant_election': (row['DATE SCRUTIN'] - pd.Timestamp.now()).days,
        'priorite': 'HAUTE' if row['ENJEUX'] and len(row['ENJEUX']) > 100 else 'NORMALE'
    }
```

### Par UD
```python
def rapport_ud_global(df_cible, df_absente):
    return {
        'nb_entreprises_presentes': len(df_cible),
        'nb_entreprises_absentes': len(df_absente),
        'total_salaries_couverts': df_cible['NB SALARIES'].sum(),
        'total_syndiques': df_cible['NB SYNDIQUES'].sum(),
        'elections_3_mois': len(df_cible[df_cible['DATE SCRUTIN'] < 
                                (pd.Timestamp.now() + pd.Timedelta(days=90))]),
        'taux_syndicalisation_moyen': (df_cible['NB SYNDIQUES'].sum() / 
                                        df_cible['NB SALARIES'].sum() * 100)
    }
```

---

## 🚀 Cas d'usage avancés avec Claude Code

### 1. Détection automatique des échéances
```
"Parcours le fichier et identifie toutes les entreprises dont la DATE SCRUTIN 
est dans les 90 prochains jours. Pour chacune :
- Vérifie si SUIVI PAP est renseigné
- Liste les PILOTES responsables
- Génère un email de rappel par pilote"
```

### 2. Analyse comparative multi-cycles
```
"Compare les résultats VOIX CGT entre différents fichiers Excel 
(un par cycle électoral C3, C4, C5) pour chaque SIRET 
et génère un graphique d'évolution"
```

### 3. Priorisation des cibles absentes
```
"Dans A CIBLE ABSENTE, trie les entreprises par :
1. NB SALARIES (effectif descendant)
2. Proximité géographique avec entreprises où CGT présente
3. Secteur d'activité (IDCC) similaire aux forces CGT locales
Génère une feuille 'PRIORITES' avec les 20 premières"
```

### 4. Génération automatique de PAP
```
"Pour chaque entreprise dans A CIBLE avec DATE SCRUTIN renseignée 
mais SUIVI PAP vide, génère un document PAP type en utilisant :
- Modèle Word fourni
- Données SIRET, NB SALARIES, PILOTE
- Calcul automatique des sièges selon effectif"
```

---

## 🔍 Validation des données

### Règles de cohérence

```python
def valider_donnees(df):
    """
    Vérifie la cohérence des données saisies
    """
    erreurs = []
    
    # SIRET : 14 chiffres
    sirets_invalides = df[~df['N° SIRET'].str.match(r'^\d{14}$', na=False)]
    if len(sirets_invalides) > 0:
        erreurs.append(f"{len(sirets_invalides)} SIRET invalides")
    
    # NB SYNDIQUES <= NB SALARIES
    incoherence = df[df['NB SYNDIQUES'] > df['NB SALARIES']]
    if len(incoherence) > 0:
        erreurs.append(f"{len(incoherence)} entreprises : nb syndiqués > effectif")
    
    # DATE SCRUTIN > DATE PRESENTATION CE
    dates_incoherentes = df[df['DATE SCRUTIN'] < df['DATE PRESENTATION CE']]
    if len(dates_incoherentes) > 0:
        erreurs.append(f"{len(dates_incoherentes)} dates incohérentes (scrutin avant présentation)")
    
    return erreurs
```

---

## 📝 Format des prompts optimaux pour Claude Code

### Structure recommandée

```
CONTEXTE : Je travaille sur le tableau de bord UD {NUM_DEPT}
FICHIER : {nom_fichier.xlsx}
TÂCHE : {action précise}
CONTRAINTES : 
- {contrainte 1}
- {contrainte 2}
FORMAT SORTIE : {JSON/Excel/Markdown/etc.}
EXEMPLE ATTENDU : {si possible, donner un exemple}
```

### Exemple concret

```
CONTEXTE : Je travaille sur le tableau de bord UD 66
FICHIER : TABLEAU_de_BORD__SUIVI_UD_EVS_2024_11V3.xlsx
TÂCHE : Extraire toutes les entreprises de la feuille "A CIBLE" 
        où DATE SCRUTIN est entre le 01/01/2025 et le 31/03/2025
CONTRAINTES :
- Inclure uniquement les colonnes : CIBLE, N° SIRET, DATE SCRUTIN, PILOTE, VOIX CGT
- Trier par DATE SCRUTIN croissante
FORMAT SORTIE : Fichier CSV avec séparateur point-virgule
EXEMPLE ATTENDU :
CIBLE;N° SIRET;DATE SCRUTIN;PILOTE;VOIX CGT
"Entreprise A";12345678901234;2025-01-15;Dupont;45
```

---

## 🛠️ Scripts utiles

### Conversion Excel → JSON
```python
import pandas as pd
import json

def excel_vers_json(fichier_excel, feuille, fichier_sortie):
    df = pd.read_excel(fichier_excel, sheet_name=feuille)
    
    # Nettoyer les NaN
    df = df.where(pd.notnull(df), None)
    
    # Convertir en dictionnaire
    data = df.to_dict('records')
    
    # Sauvegarder
    with open(fichier_sortie, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"Converti {len(data)} lignes vers {fichier_sortie}")

# Utilisation
excel_vers_json('TABLEAU_de_BORD__SUIVI_UD_EVS_2024_11V3.xlsx', 
                'A CIBLE', 
                'a_cible.json')
```

### Fusion multi-UD
```python
def fusionner_tableaux_ud(liste_fichiers):
    """
    Fusionne les données A CIBLE de plusieurs UD
    pour une vision régionale
    """
    df_total = pd.DataFrame()
    
    for fichier in liste_fichiers:
        # Extraire le numéro UD du nom de fichier
        ud_num = fichier.split('_')[-1].replace('.xlsx', '')
        
        df = pd.read_excel(fichier, sheet_name='A CIBLE')
        df['UD_ORIGINE'] = f'UD{ud_num}'
        
        df_total = pd.concat([df_total, df], ignore_index=True)
    
    return df_total

# Utilisation
dfs_regional = fusionner_tableaux_ud([
    'TABLEAU_de_BORD__SUIVI_UD_EVS_2024_11V3.xlsx',  # UD66
    'TABLEAU_de_BORD__SUIVI_UD_EVS_2024_34.xlsx',    # UD34
    'TABLEAU_de_BORD__SUIVI_UD_EVS_2024_30.xlsx'     # UD30
])
```

---

## ⚠️ Points d'attention

### Données sensibles
- ❌ **Ne jamais** publier sur Git les fichiers Excel contenant des données réelles
- ✅ **Toujours** utiliser `.gitignore` pour exclure `*.xlsx` avec données
- ✅ **Publier** uniquement le template vide ou avec données anonymisées

### Maintenance
- 🔄 Mettre à jour régulièrement la feuille `COORDONNEES EVS` (annuaire confédéral)
- 🔄 Synchroniser la feuille `AVS` avec la liste nationale
- 📅 Archiver les versions annuelles (ex: `TDB_UD66_2024.xlsx`, `TDB_UD66_2025.xlsx`)

### Performance
- Pour les fichiers volumineux (>1000 lignes), privilégier le format CSV pour les traitements
- Utiliser des index sur SIRET et DATE SCRUTIN pour accélérer les recherches

---

## 📚 Ressources

### Documentation CGT
- [Guide Élections CSE](https://www.cgt.fr/elections-professionnelles)
- [Protocole d'Accord Préélectoral](https://www.cgt.fr/pap-cse)

### Outils complémentaires
- **PAP CSE Dashboard** : https://app.pap-cse.org
- **API Entreprise** : Pour récupérer automatiquement les données SIRET
- **Pappers API** : Pour enrichir les données entreprises

---

## 🤝 Contributions

Pour améliorer ce template :
1. Identifier les colonnes manquantes utiles
2. Proposer de nouveaux indicateurs
3. Partager des scripts d'automatisation
4. Documenter les cas d'usage réels

---

## 📞 Support

Pour toute question sur l'utilisation de ce template avec Claude Code :
- Contacter l'équipe Vie Syndicale confédérale
- Consulter la feuille `COORDONNEES EVS` pour les contacts

---

**Version** : 1.0  
**Date** : Décembre 2024  
**Auteur** : Template générique adapté de l'UD 66
