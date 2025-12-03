# 📦 INDEX - Template Tableau de Bord UD CGT

## 📋 Vue d'ensemble du package

Ce package contient **6 fichiers** pour transformer le tableau de bord UD 66 en template générique utilisable par toutes les Unions Départementales et compatible avec Claude Code.

**Date de création** : Décembre 2024  
**Origine** : Adaptation du fichier `TABLEAU_de_BORD__SUIVI_UD_EVS_2024_11V3.xlsx` (UD 66)

---

## 📄 Liste des fichiers

### 1. 📖 README.md
**Type** : Documentation principale  
**Taille** : ~13 KB  
**Pour qui** : Tous les utilisateurs

**Contenu** :
- Introduction au package
- Guide de démarrage rapide
- Instructions d'installation
- 5 cas d'usage principaux avec exemples
- Utilisation avec Claude Code
- Structure des données
- Intégration PAP CSE Dashboard
- FAQ et dépannage

**Quand l'utiliser** :
- 🚀 **Premier contact** avec le template
- ❓ **Besoin d'aide** rapide
- 🔍 **Chercher un cas d'usage** spécifique

**Commencer par ici** si c'est votre première utilisation !

---

### 2. 📚 GUIDE_TEMPLATE_UD.md
**Type** : Documentation technique complète  
**Taille** : ~15 KB (équivalent 60+ pages)  
**Pour qui** : Utilisateurs avancés, développeurs

**Contenu** :
- Description détaillée de chaque feuille Excel
- Colonnes et types de données
- Adaptation pour une nouvelle UD (pas-à-pas)
- Utilisation avec Claude Code (explications approfondies)
- Scripts Python exemples
- Indicateurs et KPI calculables
- Intégration Dashboard (API, format JSON)
- Validation des données
- Cas d'usage avancés (40+ exemples)
- Bonnes pratiques

**Quand l'utiliser** :
- 🔧 **Personnalisation avancée** du template
- 📊 **Créer de nouveaux indicateurs**
- 🤖 **Rédiger des prompts Claude Code** complexes
- 🔗 **Intégrer avec le PAP CSE Dashboard**

**Document de référence technique.**

---

### 3. 🗂️ template_tableau_bord_ud.json
**Type** : Schéma de données JSON  
**Taille** : ~8.6 KB  
**Pour qui** : Claude Code, développeurs, automatisation

**Contenu** :
```json
{
  "metadata": {...},
  "configuration_ud": {...},
  "feuilles": {
    "tableau_bord_principal": {...},
    "entreprises_cibles_presentes": {...},
    "entreprises_cibles_absentes": {...},
    "animateurs_vie_syndicale": {...},
    ...
  },
  "usage": {...},
  "indicateurs_cles": {...}
}
```

**Structure** :
- Description de chaque feuille
- Colonnes avec types et descriptions
- Champs obligatoires
- Instructions d'adaptation
- Métadonnées

**Quand l'utiliser** :
- 🤖 **Input pour Claude Code** (parsing automatique)
- 💻 **Développement d'outils** automatisés
- 📐 **Référence de structure** exacte
- 🔄 **Génération automatique** de fichiers

**Format machine-readable, essentiel pour l'automatisation.**

---

### 4. 🐍 ud_automation.py
**Type** : Script Python d'automatisation  
**Taille** : ~18 KB  
**Pour qui** : Utilisateurs techniques, ligne de commande

**Fonctionnalités** :
- ✨ **create** : Créer un nouveau tableau UD vide
- 📤 **export** : Exporter vers JSON
- 📊 **rapport** : Générer un rapport Markdown
- 🔄 **sync-dashboard** : Préparer export PAP CSE
- ✅ **validate** : Valider la qualité des données

**Commandes** :
```bash
# Créer un nouveau tableau pour l'UD 34
python ud_automation.py create --ud 34 --nom "Hérault"

# Générer un rapport
python ud_automation.py rapport --fichier TDB_UD66.xlsx

# Exporter vers JSON
python ud_automation.py export --fichier TDB_UD66.xlsx --feuille "A CIBLE"

# Synchroniser avec Dashboard
python ud_automation.py sync-dashboard --fichier TDB_UD66.xlsx --ud-code ud66

# Valider les données
python ud_automation.py validate --fichier TDB_UD66.xlsx
```

**Prérequis** :
```bash
pip install pandas openpyxl
```

**Quand l'utiliser** :
- ⚡ **Automatisation rapide** sans Claude Code
- 🔧 **Intégration dans scripts** existants
- 📅 **Tâches récurrentes** (rapports mensuels)
- 🎯 **Ligne de commande** préférée

**Prêt à l'emploi, aucune modification nécessaire.**

---

### 5. 🤖 PROMPTS_CLAUDE_CODE.md
**Type** : Bibliothèque de prompts  
**Taille** : ~24 KB  
**Pour qui** : Tous les utilisateurs de Claude Code

**Contenu** :
7 catégories de prompts prêts à copier-coller :

1. **Création et initialisation** (2 prompts)
   - Créer un nouveau tableau UD
   - Convertir un ancien format

2. **Analyse et rapports** (3 prompts)
   - Rapport mensuel complet
   - Analyse comparative multi-cycles
   - Cartographie forces/faiblesses

3. **Synchronisation et export** (3 prompts)
   - Export vers PAP CSE Dashboard
   - Enrichissement via API Entreprise
   - Export multi-formats (confidentiel)

4. **Validation et qualité** (2 prompts)
   - Audit complet qualité données
   - Détection doublons et fusions

5. **Automatisation et alertes** (2 prompts)
   - Système d'alertes automatiques
   - Planificateur d'actions

6. **Formation et documentation** (1 prompt)
   - Générer documentation personnalisée

7. **Optimisation et maintenance** (1 prompt)
   - Nettoyage et archivage

**Format des prompts** :
```
CONTEXTE : [situation]
FICHIERS : [fichiers utilisés]
TÂCHE : [description détaillée]
CONTRAINTES : [règles à respecter]
FORMAT SORTIE : [type de fichier attendu]
```

**Quand l'utiliser** :
- 🎯 **Chaque fois** que vous utilisez Claude Code
- 💡 **Inspiration** pour vos propres prompts
- ⚡ **Gain de temps** : copier-coller et adapter
- 📚 **Apprendre** à bien prompter

**Le fichier le plus utilisé au quotidien avec Claude Code.**

---

### 6. 🔒 .gitignore
**Type** : Configuration Git  
**Taille** : ~2.6 KB  
**Pour qui** : Utilisateurs Git/GitHub

**Contenu** :
- Règles pour **protéger les données sensibles**
- Exclusions : fichiers Excel avec données réelles
- Exclusions : exports JSON nominatifs
- Exclusions : fichiers temporaires
- **Exceptions** : templates vides OK pour Git

**Structure** :
```gitignore
# DONNÉES SENSIBLES - NE JAMAIS COMMIT
data/*.xlsx
*_UD[0-9][0-9]_*.xlsx
exports/json/export_dashboard_*.json

# FICHIERS À GARDER (EXCEPTIONS)
!templates/template_vide.xlsx
!templates/template_tableau_bord_ud.json
```

**Quand l'utiliser** :
- 📂 **Toujours** si vous utilisez Git
- 🔒 **Protection** contre les commits accidentels
- 👥 **Partage** du code sans exposer les données

**Critique pour la sécurité des données !**

---

## 🚀 Par où commencer ?

### Scénario 1 : Je découvre le template
```
1. Lire README.md (15 min)
2. Télécharger tous les fichiers
3. Essayer la commande : python ud_automation.py create --ud 99 --nom "Test"
4. Consulter PROMPTS_CLAUDE_CODE.md pour des exemples
```

### Scénario 2 : Je veux adapter pour mon UD
```
1. Lire le README.md section "Adaptation pour une nouvelle UD"
2. Consulter GUIDE_TEMPLATE_UD.md section "Adaptation"
3. Utiliser : python ud_automation.py create --ud [MON_NUM] --nom "[MON_DEPT]"
4. Ou utiliser un prompt de PROMPTS_CLAUDE_CODE.md (section 1.1)
```

### Scénario 3 : J'ai déjà un tableau, je veux l'analyser
```
1. Consulter PROMPTS_CLAUDE_CODE.md section 2 (Analyse)
2. Choisir un prompt adapté (ex: Rapport mensuel)
3. L'utiliser avec Claude Code
4. Ou utiliser : python ud_automation.py rapport --fichier [MON_FICHIER]
```

### Scénario 4 : Je veux synchroniser avec le Dashboard
```
1. Lire README.md section "Intégration PAP CSE Dashboard"
2. Consulter GUIDE_TEMPLATE_UD.md section détaillée
3. Utiliser PROMPTS_CLAUDE_CODE.md section 3.1 (Export Dashboard)
4. Ou utiliser : python ud_automation.py sync-dashboard --fichier [FICHIER] --ud-code ud66
```

### Scénario 5 : Je suis développeur, je veux automatiser
```
1. Lire template_tableau_bord_ud.json (structure)
2. Consulter ud_automation.py (code source)
3. Lire GUIDE_TEMPLATE_UD.md sections techniques
4. Adapter ud_automation.py selon besoins
```

---

## 📊 Matrice d'utilisation

| Besoin | README | GUIDE | JSON | Python | PROMPTS | .gitignore |
|--------|:------:|:-----:|:----:|:------:|:-------:|:----------:|
| Découvrir | ✅ | | | | | |
| Démarrer rapidement | ✅ | | | ✅ | ✅ | |
| Approfondir | | ✅ | | | | |
| Créer nouveau UD | ✅ | ✅ | | ✅ | ✅ | |
| Analyser données | | ✅ | | ✅ | ✅ | |
| Utiliser Claude Code | ✅ | ✅ | ✅ | | ✅ | |
| Développer outils | | ✅ | ✅ | ✅ | | |
| Intégrer Dashboard | ✅ | ✅ | ✅ | ✅ | ✅ | |
| Partager sur Git | | | | | | ✅ |
| Former nouveaux | ✅ | | | | ✅ | |

---

## 🎯 Fichiers selon niveau d'expertise

### 👶 Débutant
**À lire en priorité** :
1. README.md
2. PROMPTS_CLAUDE_CODE.md

**À utiliser** :
- Prompts de la section 1 (Création)
- Prompts de la section 2 (Analyse simple)

### 🧑 Intermédiaire
**À lire** :
1. README.md
2. GUIDE_TEMPLATE_UD.md (sections pertinentes)
3. PROMPTS_CLAUDE_CODE.md

**À utiliser** :
- ud_automation.py (commandes de base)
- Prompts sections 2-5
- template_tableau_bord_ud.json (référence)

### 👨‍💻 Avancé
**À lire** :
- Tous les fichiers

**À utiliser** :
- ud_automation.py (modification/extension)
- template_tableau_bord_ud.json (développement)
- Prompts sections 6-7
- .gitignore (personnalisation)

---

## 💾 Installation complète

```bash
# 1. Créer l'arborescence
mkdir -p mon_projet_ud/{templates,scripts,data,exports/{json,rapports},docs}

# 2. Placer les fichiers
# README.md, GUIDE_TEMPLATE_UD.md, INDEX.md → docs/
# template_tableau_bord_ud.json → templates/
# ud_automation.py → scripts/
# PROMPTS_CLAUDE_CODE.md → docs/
# .gitignore → racine du projet

# 3. Installer les dépendances Python
pip install pandas openpyxl

# 4. Tester l'installation
cd scripts
python ud_automation.py --help

# 5. Créer un premier tableau test
python ud_automation.py create --ud 99 --nom "Test" --output ../data/test_ud99.xlsx
```

---

## 🔄 Workflow recommandé

```
1. CRÉATION
   ├─ Utiliser: ud_automation.py create OU prompt 1.1
   └─ Résultat: Nouveau fichier Excel vide

2. SAISIE
   ├─ Remplir manuellement le fichier Excel
   └─ Ou importer depuis sources existantes

3. VALIDATION
   ├─ Utiliser: ud_automation.py validate
   └─ Ou prompt 4.1 (Audit qualité)

4. ANALYSE
   ├─ Utiliser: ud_automation.py rapport
   ├─ Ou prompts section 2 (Rapports)
   └─ Résultat: Rapports Markdown/JSON

5. SYNCHRONISATION
   ├─ Utiliser: ud_automation.py sync-dashboard
   └─ Ou prompt 3.1 (Export Dashboard)

6. ARCHIVAGE
   └─ Prompt 7.1 (Nettoyage + archivage)
```

---

## 🆘 Aide et support

### Question sur un fichier spécifique

| Fichier | Type de question | Où chercher |
|---------|------------------|-------------|
| README.md | Installation, démarrage | FAQ dans le fichier |
| GUIDE_TEMPLATE_UD.md | Technique, colonnes | Sections détaillées |
| template_tableau_bord_ud.json | Structure, format | Commentaires dans JSON |
| ud_automation.py | Erreurs Python | Code + docstrings |
| PROMPTS_CLAUDE_CODE.md | Utilisation Claude | Exemples + astuces |
| .gitignore | Git, sécurité | Commentaires dans fichier |

### Besoin d'aide général

1. **Problème technique** :
   - Consulter README.md section "Dépannage"
   - Vérifier les prérequis (Python, librairies)

2. **Comment faire X** :
   - Chercher dans PROMPTS_CLAUDE_CODE.md
   - Consulter GUIDE_TEMPLATE_UD.md

3. **Erreur dans les données** :
   - Lancer : `python ud_automation.py validate --fichier [FICHIER]`
   - Consulter le prompt 4.1 pour un audit détaillé

4. **Adaptation spécifique** :
   - GUIDE_TEMPLATE_UD.md section "Personnalisation"
   - Modifier ud_automation.py selon besoins

---

## 📝 Checklist d'utilisation complète

### ✅ Setup initial
- [ ] Téléchargé tous les 6 fichiers
- [ ] Installé Python 3.8+
- [ ] Installé pandas et openpyxl
- [ ] Testé ud_automation.py --help
- [ ] Lu le README.md

### ✅ Adaptation pour mon UD
- [ ] Créé un nouveau tableau avec mon numéro UD
- [ ] Ajouté les feuilles AVS et COORDONNEES EVS
- [ ] Configuré .gitignore si utilisation Git
- [ ] Personnalisé les champs si nécessaire

### ✅ Utilisation quotidienne
- [ ] Saisi les données entreprises
- [ ] Validé la qualité (validate)
- [ ] Généré un rapport mensuel
- [ ] Synchronisé avec Dashboard si applicable

### ✅ Maintenance
- [ ] Sauvegarde régulière du fichier
- [ ] Archivage des données anciennes
- [ ] Mise à jour des contacts AVS/EVS
- [ ] Nettoyage périodique (prompt 7.1)

---

## 🎓 Formation suggérée

### Niveau 1 : Utilisateur (2h)
1. Lire README.md (30 min)
2. Créer un tableau test (15 min)
3. Saisir 5 entreprises exemples (30 min)
4. Générer un rapport (15 min)
5. Essayer 3 prompts Claude Code (30 min)

### Niveau 2 : Gestionnaire (4h)
1. Formation Niveau 1 (2h)
2. Lire GUIDE_TEMPLATE_UD.md (1h)
3. Analyser données réelles avec prompts (45 min)
4. Synchroniser avec Dashboard (15 min)

### Niveau 3 : Développeur (1 jour)
1. Formations Niveau 1+2 (6h)
2. Étudier template_tableau_bord_ud.json (1h)
3. Modifier ud_automation.py (2h)
4. Créer nouveaux prompts (1h)

---

## 📞 Contacts

### Documentation
- Guide rapide : README.md
- Guide complet : GUIDE_TEMPLATE_UD.md
- Prompts : PROMPTS_CLAUDE_CODE.md

### Technique
- Structure : template_tableau_bord_ud.json
- Automatisation : ud_automation.py
- Sécurité : .gitignore

### Support confédéral
Voir feuille COORDONNEES EVS dans le template pour les contacts de l'équipe Vie Syndicale.

---

## 🏆 Bonnes pratiques

1. **Toujours** commencer par valider les données avant analyse
2. **Toujours** faire une sauvegarde avant modifications massives
3. **Ne jamais** commit de données réelles sur Git
4. **Toujours** utiliser des noms de fichiers datés (YYYYMMDD)
5. **Régulièrement** archiver les anciennes données
6. **Systématiquement** vérifier les SIRET (14 chiffres)
7. **Documenter** les modifications du template
8. **Partager** les nouveaux prompts utiles

---

**Package Template Tableau de Bord UD CGT**  
**Version** : 1.0  
**Date** : Décembre 2024  
**Auteur** : Adapté de l'UD 66  
**Maintenance** : Équipe Vie Syndicale confédérale

---

**🎉 Vous êtes prêt à utiliser le template !**

**Premier pas recommandé** : Lire le README.md puis tester la création d'un tableau avec `python ud_automation.py create --ud 99 --nom "Test"`
