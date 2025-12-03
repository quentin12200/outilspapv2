# 📊 Template Tableau de Bord UD CGT - Package Complet

## 🎯 Objectif

Ce package fournit un **template générique** et des **outils d'automatisation** pour créer et gérer des tableaux de bord pour les Unions Départementales CGT. Il est optimisé pour être utilisé avec **Claude Code** et s'intègre facilement avec le **PAP CSE Dashboard**.

## 📦 Contenu du Package

### Fichiers principaux

1. **`template_tableau_bord_ud.json`** 
   - Template JSON structuré décrivant la structure complète du tableau de bord
   - Format machine-readable pour Claude Code
   - Contient tous les champs, types de données et métadonnées

2. **`GUIDE_TEMPLATE_UD.md`**
   - Guide complet d'utilisation (60+ pages)
   - Cas d'usage détaillés
   - Exemples de prompts pour Claude Code
   - Scripts et indicateurs

3. **`ud_automation.py`**
   - Script Python d'automatisation
   - 5 commandes principales : create, export, rapport, sync-dashboard, validate
   - Prêt à l'emploi ou à adapter

## 🚀 Installation

### Prérequis

```bash
# Python 3.8+
python --version

# Installer les dépendances
pip install pandas openpyxl
```

### Récupération des fichiers

```bash
# Télécharger les 3 fichiers depuis Claude.ai
# Ou depuis votre repository Git (si partagé)
ls -l
# template_tableau_bord_ud.json
# GUIDE_TEMPLATE_UD.md
# ud_automation.py
```

## 🎬 Démarrage Rapide

### Cas 1 : Créer un nouveau tableau de bord pour une UD

```bash
# Avec le script Python
python ud_automation.py create --ud 34 --nom "Hérault"

# Ou avec Claude Code
# Prompt : "Crée un nouveau tableau de bord UD pour le département 34 (Hérault) 
#           en utilisant le template JSON fourni"
```

**Résultat** : Fichier Excel `TABLEAU_de_BORD_UD34_YYYYMMDD.xlsx` avec toutes les feuilles et structures

### Cas 2 : Analyser un tableau existant

```bash
# Générer un rapport complet
python ud_automation.py rapport --fichier TABLEAU_de_BORD_UD66.xlsx

# Résultat : rapport_TABLEAU_de_BORD_UD66_YYYYMMDD.md
```

### Cas 3 : Exporter vers JSON (pour Claude Code)

```bash
# Exporter la feuille A CIBLE
python ud_automation.py export --fichier TABLEAU_de_BORD_UD66.xlsx --feuille "A CIBLE"

# Résultat : A_CIBLE_YYYYMMDD.json
```

### Cas 4 : Synchroniser avec PAP CSE Dashboard

```bash
# Préparer l'export
python ud_automation.py sync-dashboard \
  --fichier TABLEAU_de_BORD_UD66.xlsx \
  --ud-code ud66 \
  --api-url https://app.pap-cse.org/api

# Résultat : export_dashboard_ud66_YYYYMMDD.json
```

### Cas 5 : Valider les données

```bash
# Vérifier la cohérence des données
python ud_automation.py validate --fichier TABLEAU_de_BORD_UD66.xlsx

# Résultat : Liste des erreurs éventuelles (SIRET invalides, incohérences, etc.)
```

## 🤖 Utilisation avec Claude Code

### Configuration

1. **Placer les fichiers dans votre projet**
   ```
   mon_projet_ud/
   ├── template_tableau_bord_ud.json
   ├── GUIDE_TEMPLATE_UD.md
   ├── ud_automation.py
   └── data/
       └── TABLEAU_de_BORD_UD66.xlsx
   ```

2. **Lancer Claude Code**
   ```bash
   claude-code
   ```

### Exemples de Prompts

#### Création d'un nouveau tableau

```
Contexte : Je suis responsable de l'UD 11 (Aude) et j'ai besoin d'un tableau de bord
Fichiers disponibles : template_tableau_bord_ud.json, GUIDE_TEMPLATE_UD.md
Tâche : Crée un nouveau fichier Excel "TABLEAU_de_BORD_UD11_2025.xlsx" avec :
  - Toutes les feuilles du template
  - Nom correct "TDB 11" pour la feuille principale
  - Structure des colonnes identique au template
  - Feuilles vides (pas de données)
Format : Fichier Excel .xlsx
```

#### Analyse et rapport

```
Contexte : J'ai un tableau de bord UD 66 avec des données réelles
Fichier : data/TABLEAU_de_BORD_UD66.xlsx
Tâche : Génère un rapport Markdown détaillé incluant :
  1. Nombre total d'entreprises (cibles et absentes)
  2. Statistiques de syndicalisation
  3. Liste des élections dans les 3 prochains mois
  4. Top 10 des entreprises absentes par effectif
  5. Répartition des dossiers par pilote
Format : Fichier Markdown avec tableaux et statistiques
```

#### Migration vers Dashboard

```
Contexte : Je veux intégrer mes données UD dans PAP CSE Dashboard
Fichier : data/TABLEAU_de_BORD_UD66.xlsx
Tâche : Extrais toutes les entreprises de "A CIBLE" et génère un fichier JSON compatible API :
  - Champs obligatoires : siret, nom_entreprise, nb_salaries, date_election
  - Champs optionnels : voix_cgt, nb_syndiques, pilote, idcc
  - Format : Array d'objets JSON
  - Validation : SIRET 14 chiffres, dates au format ISO
Contraintes : Exclure les lignes sans SIRET
Format : JSON compatible avec POST /api/entreprises/bulk
```

#### Détection d'anomalies

```
Contexte : Je veux vérifier la qualité de mes données
Fichier : data/TABLEAU_de_BORD_UD66.xlsx
Tâche : Analyse la feuille "A CIBLE" et détecte :
  1. SIRET invalides (pas 14 chiffres)
  2. Incohérences (nb_syndiqués > nb_salariés)
  3. Dates incohérentes (scrutin avant présentation CE)
  4. Champs obligatoires manquants
  5. Doublons de SIRET
Format : Rapport JSON avec liste des erreurs par type
Action : Pour chaque erreur, indique la ligne concernée et la correction suggérée
```

#### Enrichissement automatique

```
Contexte : J'ai une liste de SIRET et je veux enrichir mes données
Fichier : data/TABLEAU_de_BORD_UD66.xlsx
API disponible : API Entreprise (France) ou Pappers
Tâche : Pour chaque entreprise dans "A CIBLE ABSENTE" :
  1. Récupérer les infos via l'API (raison sociale, effectif, convention collective)
  2. Compléter les colonnes NB SALARIES et idcc si vides
  3. Ajouter une colonne "date_maj" avec la date de mise à jour
Contraintes : 
  - Ne pas écraser les données existantes
  - Logger les erreurs API
  - Respecter les limites de taux (rate limiting)
Format : Nouveau fichier Excel avec données enrichies
```

## 📚 Structure des Données

### Feuilles Excel

| Feuille | Description | Utilisation |
|---------|-------------|-------------|
| **TDB {NUM}** | Tableau de bord réunions | Planning événements UD |
| **A CIBLE** | Entreprises avec CGT | Suivi développement |
| **A CIBLE ABSENTE** | Entreprises sans CGT | Ciblage implantation |
| **AVS** | Animateurs Vie Syndicale | Annuaire national (référence) |
| **CARTE EVS** | Carte géographique | Visualisation (optionnel) |
| **COORDONNEES EVS** | Équipe confédérale | Contacts Montreuil (référence) |

### Colonnes Essentielles (A CIBLE)

```json
{
  "identifiants": ["CIBLE", "N° SIRET"],
  "effectifs": ["NB SALARIES", "NB SYNDIQUES"],
  "elections": ["DATE SCRUTIN", "DATE PRESENTATION CE", "VOIX CGT"],
  "suivi": ["SUIVI PAP", "PILOTE"],
  "contacts": ["CONTACT", "TELEPHONE", "MAIL"],
  "strategie": ["ENJEUX", "OBJET"]
}
```

## 🔗 Intégration PAP CSE Dashboard

### Format d'export compatible

```json
{
  "ud_code": "ud66",
  "date_export": "2024-12-03T10:30:00",
  "entreprises": [
    {
      "siret": "12345678901234",
      "nom_entreprise": "Entreprise Exemple",
      "nb_salaries": 250,
      "date_election": "2025-03-15",
      "voix_cgt": 45,
      "nb_syndiques": 12,
      "pilote": "Jean Dupont",
      "idcc": "1486",
      "source": "tableau_bord_ud"
    }
  ]
}
```

### API Endpoints suggérés

- `POST /api/entreprises/bulk` : Import massif
- `GET /api/entreprises?ud_code=ud66` : Liste par UD
- `PUT /api/entreprises/{siret}` : Mise à jour unitaire

## 📊 Indicateurs Calculables

### Par Entreprise

```python
taux_syndicalisation = (NB_SYNDIQUES / NB_SALARIES) * 100
jours_avant_election = (DATE_SCRUTIN - aujourdhui).days
performance_electorale = (VOIX_CGT / total_exprimés) * 100
```

### Par UD

```python
nb_entreprises_suivies = count(A CIBLE)
nb_entreprises_cibles = count(A CIBLE ABSENTE)
couverture_salaries = sum(NB SALARIES in A CIBLE)
taux_syndicalisation_moyen = sum(NB_SYNDIQUES) / sum(NB_SALARIES) * 100
elections_trimestre = count(DATE_SCRUTIN in next 90 days)
```

## 🔧 Personnalisation

### Ajouter une colonne

1. Éditer `template_tableau_bord_ud.json`
   ```json
   {
     "nom": "MA_NOUVELLE_COLONNE",
     "type": "text",
     "description": "Description de la colonne",
     "obligatoire": false
   }
   ```

2. Modifier `ud_automation.py`
   ```python
   # Ajouter dans FEUILLES_STRUCTURE['A CIBLE']['colonnes']
   'MA_NOUVELLE_COLONNE'
   ```

3. Mettre à jour dans Excel
   - Ajouter la colonne en en-tête
   - Ajuster les formules si nécessaire

### Créer un nouvel indicateur

```python
# Dans ud_automation.py
def calculer_indicateur_personnalise(df):
    """
    Exemple : Score de priorité d'une entreprise
    """
    df['score_priorite'] = (
        (df['NB SALARIES'] / 100) * 0.4 +  # Poids effectif
        (df['NB SYNDIQUES'] > 0) * 0.3 +   # Présence syndicale
        (df['ENJEUX'].str.len() > 100) * 0.3  # Enjeux documentés
    )
    return df.sort_values('score_priorite', ascending=False)
```

## 🛡️ Bonnes Pratiques

### Sécurité

- ⚠️ **NE JAMAIS** commit des fichiers Excel avec données réelles sur Git
- ✅ Utiliser `.gitignore` : `*.xlsx` (sauf templates vides)
- ✅ Anonymiser les données avant partage
- ✅ Chiffrer les exports JSON contenant des données sensibles

### Organisation

```
mon_projet_ud/
├── templates/              # Templates vides
│   ├── template_tableau_bord_ud.json
│   └── template_vide.xlsx
├── scripts/               # Scripts d'automatisation
│   └── ud_automation.py
├── data/                  # Données réelles (gitignored)
│   ├── TABLEAU_de_BORD_UD66_2024.xlsx
│   └── TABLEAU_de_BORD_UD66_2025.xlsx
├── exports/               # Exports générés (gitignored)
│   ├── rapports/
│   └── json/
└── docs/                  # Documentation
    ├── GUIDE_TEMPLATE_UD.md
    └── README.md
```

### Versionnement

- Nommer les fichiers avec la date : `TDB_UD66_20241203.xlsx`
- Archiver les versions annuelles
- Conserver l'historique des modifications importantes

## 🆘 Dépannage

### Problème : Erreur "SIRET invalide"

**Cause** : Le SIRET ne contient pas 14 chiffres ou comporte des espaces

**Solution** :
```python
# Nettoyer les SIRET
df['N° SIRET'] = df['N° SIRET'].astype(str).str.replace(' ', '').str.zfill(14)
```

### Problème : Dates non reconnues

**Cause** : Format de date Excel non standard

**Solution** :
```python
# Forcer la conversion
df['DATE SCRUTIN'] = pd.to_datetime(df['DATE SCRUTIN'], errors='coerce', dayfirst=True)
```

### Problème : Feuille AVS vide

**Cause** : La feuille n'a pas été copiée depuis le template national

**Solution** :
1. Télécharger le template national avec AVS complet
2. Copier la feuille AVS dans votre fichier UD
3. Filtrer sur votre département

## 📖 Documentation Complète

Pour plus de détails, consulter **`GUIDE_TEMPLATE_UD.md`** qui contient :
- 📋 Explications détaillées de chaque feuille
- 🤖 60+ exemples de prompts pour Claude Code
- 📊 Formules d'indicateurs avancés
- 🔗 Guide d'intégration Dashboard
- 🎓 Tutoriels pas-à-pas

## 🤝 Contribution

Pour améliorer ce template :

1. **Identifier un besoin**
   - Colonne manquante
   - Nouvel indicateur
   - Automatisation supplémentaire

2. **Proposer une amélioration**
   - Documenter le cas d'usage
   - Fournir un exemple de code
   - Tester sur données réelles

3. **Partager avec la communauté**
   - Via les canaux CGT appropriés
   - En préservant la confidentialité des données

## 📞 Support

### Questions sur l'utilisation
- Consulter `GUIDE_TEMPLATE_UD.md`
- Contacter l'équipe Vie Syndicale confédérale
- Utiliser Claude Code pour générer des exemples

### Questions techniques
- Issues sur repository Git (si applicable)
- Documentation Python/pandas
- Aide Claude Code

### Contact confédéral
Voir feuille `COORDONNEES EVS` dans le template pour les contacts de l'équipe Vie Syndicale à Montreuil.

---

## 📝 Changelog

### Version 1.0 (Décembre 2024)
- ✨ Template JSON complet
- ✨ Guide d'utilisation 60+ pages
- ✨ Script Python d'automatisation
- ✨ Support Claude Code
- ✨ Intégration PAP CSE Dashboard

---

**Licence** : Usage interne CGT  
**Auteur** : Template générique adapté de l'UD 66  
**Maintenance** : Équipe Vie Syndicale confédérale

**Version** : 1.0  
**Date** : Décembre 2024
