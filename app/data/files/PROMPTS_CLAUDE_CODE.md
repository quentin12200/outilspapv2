# 🤖 Bibliothèque de Prompts pour Claude Code
## Template Tableau de Bord UD CGT

Cette bibliothèque contient des prompts prêts à l'emploi pour automatiser vos tâches avec Claude Code. Copiez-collez et adaptez selon vos besoins.

---

## 📋 CATÉGORIE 1 : CRÉATION ET INITIALISATION

### 1.1 Créer un nouveau tableau de bord pour une UD

```
CONTEXTE :
Je suis responsable syndical de l'UD [NUMERO] ([NOM_DEPARTEMENT]) et je dois créer notre tableau de bord de suivi des entreprises et élections CSE.

FICHIERS DISPONIBLES :
- template_tableau_bord_ud.json (structure de référence)
- GUIDE_TEMPLATE_UD.md (documentation)

TÂCHE :
Crée un nouveau fichier Excel "TABLEAU_de_BORD_UD[NUMERO]_2025.xlsx" avec :
1. Feuille "TDB [NUMERO]" : Planning des réunions et événements
   - Colonnes : ORGANISATION, DATE ET HEURE, RUBRIQUE, PRÉSENTATEUR, Ordre du jour
   - Mise en forme : titre en gras, en-têtes avec fond gris
   
2. Feuille "A CIBLE" : Entreprises où la CGT est présente
   - Toutes les colonnes du template JSON
   - Première ligne : en-têtes avec fond bleu CGT (#366092) et texte blanc
   - Colonnes obligatoires marquées en gras : CIBLE, N° SIRET
   
3. Feuille "A CIBLE ABSENTE" : Entreprises sans CGT
   - Même structure que "A CIBLE" 
   - Colonnes supplémentaires : UD, ANNEE
   
4. Feuille "NOTE" : Instructions
   - Texte : "Les feuilles AVS et COORDONNEES EVS doivent être copiées depuis le fichier national"

CONTRAINTES :
- Toutes les feuilles doivent être vides (pas de données exemple)
- Respecter exactement les noms de colonnes du template
- Largeur des colonnes auto-ajustée
- Format de date français (JJ/MM/AAAA)

FORMAT SORTIE :
Fichier Excel .xlsx prêt à l'emploi
```

### 1.2 Convertir un ancien tableau au nouveau format

```
CONTEXTE :
J'ai un ancien tableau de bord Excel avec une structure différente et je veux migrer vers le nouveau template standardisé.

FICHIERS :
- ancien_tableau_ud66.xlsx (à convertir)
- template_tableau_bord_ud.json (structure cible)

TÂCHE :
1. Analyse l'ancien fichier et identifie les colonnes correspondantes
2. Crée un mapping des colonnes :
   Ancien nom → Nouveau nom (selon template)
3. Convertis les données en préservant l'historique
4. Ajoute les colonnes manquantes (vides)
5. Valide les SIRET (format 14 chiffres)
6. Convertis les dates au format ISO

CONTRAINTES :
- Ne pas perdre de données lors de la migration
- Logger toutes les transformations effectuées
- Créer un fichier "migration_report.txt" avec les détails

FORMAT SORTIE :
- nouveau_tableau_ud66_migre.xlsx
- migration_report.txt
```

---

## 📊 CATÉGORIE 2 : ANALYSE ET RAPPORTS

### 2.1 Rapport mensuel complet

```
CONTEXTE :
Fin de mois, je dois produire un rapport d'activité pour le bureau de l'UD.

FICHIER :
data/TABLEAU_de_BORD_UD66.xlsx

TÂCHE :
Génère un rapport Markdown "rapport_mensuel_[MOIS]_[ANNEE].md" contenant :

## 1. Vue d'ensemble
- Nombre total d'entreprises suivies (A CIBLE)
- Nombre d'entreprises cibles (A CIBLE ABSENTE)
- Total salariés couverts
- Total syndiqués CGT
- Taux de syndicalisation moyen

## 2. Élections professionnelles
### Ce mois-ci
- Liste des élections du mois avec : Entreprise, Date, SIRET, Résultats
### Prochaines échéances (3 mois)
- Tableau trié par date avec colonne "Jours restants"
- Indication du statut PAP (OK / En cours / Non démarré)

## 3. Implantations
- Top 10 des entreprises "A CIBLE ABSENTE" par effectif
- Secteurs d'activité (IDCC) prioritaires
- Zones géographiques à développer

## 4. Pilotage
- Répartition des dossiers par pilote
- Pilotes avec plus de 5 dossiers (surcharge?)
- Dossiers sans pilote assigné

## 5. Alertes
- SIRET invalides ou manquants
- Élections dans moins de 30 jours sans PAP validé
- Incohérences (syndiqués > effectif)

CONTRAINTES :
- Utiliser des tableaux Markdown bien formatés
- Ajouter des émojis pour la lisibilité (📊 🎯 ⚠️)
- Inclure des graphiques en texte ASCII si pertinent
- Date de génération en en-tête

FORMAT SORTIE :
Fichier Markdown avec sections cliquables
```

### 2.2 Analyse comparative multi-cycles

```
CONTEXTE :
Je veux comparer les résultats électoraux sur plusieurs cycles pour voir notre évolution.

FICHIERS :
- TABLEAU_de_BORD_UD66_C3.xlsx (Cycle 3)
- TABLEAU_de_BORD_UD66_C4.xlsx (Cycle 4)
- TABLEAU_de_BORD_UD66_C5.xlsx (Cycle 5 en cours)

TÂCHE :
Pour chaque SIRET présent dans plusieurs cycles :

1. Créer un tableau comparatif CSV avec colonnes :
   - SIRET
   - Nom_entreprise
   - Cycle_3_voix_CGT
   - Cycle_3_date
   - Cycle_4_voix_CGT
   - Cycle_4_date
   - Cycle_5_voix_CGT
   - Cycle_5_date
   - Evolution_C3_C4 (en %)
   - Evolution_C4_C5 (en %)
   - Tendance (📈 Hausse / 📉 Baisse / ➡️ Stable)

2. Statistiques globales :
   - Nombre d'entreprises en progression
   - Nombre d'entreprises en régression
   - Progression moyenne (en voix)
   - Taux de renouvellement (nouvelles entreprises par cycle)

3. Identifier :
   - Top 5 progressions
   - Top 5 régressions
   - Entreprises avec résultats irréguliers

CONTRAINTES :
- Gérer les SIRET présents dans certains cycles seulement
- Calculer les % seulement si données disponibles
- Inclure un graphique d'évolution (ASCII ou description textuelle)

FORMAT SORTIE :
- evolution_cycles_ud66.csv
- rapport_evolution.md
```

### 2.3 Cartographie des forces et faiblesses

```
CONTEXTE :
Je veux visualiser nos implantations pour orienter notre stratégie.

FICHIER :
data/TABLEAU_de_BORD_UD66.xlsx

TÂCHE :
Analyse les données et génère un rapport JSON structuré "cartographie_ud66.json" :

{
  "forces": {
    "description": "Secteurs où la CGT est bien implantée",
    "criteres": "présence + taux syndicalisation > 5% + résultats > 30%",
    "entreprises": [
      {
        "nom": "...",
        "siret": "...",
        "effectif": 250,
        "syndiques": 15,
        "taux_syndicalisation": 6.0,
        "derniers_resultats": 35.2,
        "score_force": 8.5
      }
    ],
    "synthese": {
      "nb_entreprises": 12,
      "total_salaries": 3500,
      "total_syndiques": 210
    }
  },
  "potentiel": {
    "description": "Secteurs avec potentiel de développement",
    "criteres": "présence + effectif > 50 + taux syndicalisation < 5%",
    "entreprises": [...],
    "synthese": {...}
  },
  "opportunites": {
    "description": "Entreprises cibles prioritaires (absentes)",
    "criteres": "effectif > 100 + secteur porteur + proximité géographique",
    "entreprises": [...],
    "synthese": {...}
  },
  "difficultes": {
    "description": "Situations nécessitant un appui",
    "criteres": "baisse résultats ou nb syndiqués en chute",
    "entreprises": [...],
    "synthese": {...}
  }
}

CONTRAINTES :
- Score de force : calculé sur effectif, syndicalisation, résultats électoraux
- Inclure l'analyse IDCC (conventions collectives)
- Suggérer des actions pour chaque catégorie

FORMAT SORTIE :
JSON structuré + fichier Markdown de synthèse
```

---

## 🔄 CATÉGORIE 3 : SYNCHRONISATION ET EXPORT

### 3.1 Export vers PAP CSE Dashboard

```
CONTEXTE :
Je veux synchroniser mes données avec le PAP CSE Dashboard pour centraliser le suivi.

FICHIER :
data/TABLEAU_de_BORD_UD66.xlsx

TÂCHE :
Génère un fichier JSON "export_dashboard_ud66_[DATE].json" compatible avec l'API PAP CSE Dashboard :

{
  "ud_code": "ud66",
  "date_export": "2024-12-03T14:30:00Z",
  "version": "1.0",
  "entreprises": [
    {
      "siret": "12345678901234",
      "nom_entreprise": "Entreprise Exemple SAS",
      "nb_salaries": 250,
      "date_election": "2025-03-15",
      "date_derniere_maj": "2024-12-03",
      "voix_cgt": 45,
      "total_exprimes": 180,
      "pourcentage_cgt": 25.0,
      "nb_syndiques": 12,
      "taux_syndicalisation": 4.8,
      "pilote": "Jean Dupont",
      "idcc": "1486",
      "statut_pap": "valide",
      "source": "tableau_bord_ud",
      "metadata": {
        "enjeux": "Développement territorial",
        "commentaire": "Entreprise stratégique"
      }
    }
  ],
  "statistiques": {
    "nb_entreprises_exportees": 45,
    "nb_elections_a_venir": 8,
    "total_salaries": 12500,
    "total_syndiques": 350
  }
}

CONTRAINTES :
- Valider TOUS les SIRET (14 chiffres)
- Exclure les lignes sans date d'élection pour le Dashboard
- Calculer automatiquement pourcentage_cgt et taux_syndicalisation
- Gérer les valeurs manquantes (null au lieu de NaN)
- Format de dates ISO 8601

VALIDATION :
- Vérifier que chaque objet entreprise a au minimum : siret, nom_entreprise, nb_salaries
- Logger les entreprises exclues et les raisons

FORMAT SORTIE :
- export_dashboard_ud66_YYYYMMDD.json
- validation_report.txt
```

### 3.2 Import depuis API Entreprise (enrichissement)

```
CONTEXTE :
J'ai des SIRET dans "A CIBLE ABSENTE" mais certaines infos sont manquantes. Je veux les enrichir automatiquement via l'API Entreprise (France).

FICHIER :
data/TABLEAU_de_BORD_UD66.xlsx

API :
https://entreprise.api.gouv.fr/v3/

TÂCHE :
Pour chaque entreprise dans "A CIBLE ABSENTE" où NB SALARIES est vide :

1. Appeler l'API Entreprise avec le SIRET
2. Récupérer :
   - Raison sociale (vérifier cohérence avec CIBLE)
   - Effectif (si disponible)
   - Convention collective (IDCC)
   - Adresse complète
   - Statut juridique
   - Date de création

3. Compléter le tableau Excel :
   - Colonne NB SALARIES
   - Colonne idcc
   - Ajouter colonnes : ADRESSE, FORME_JURIDIQUE, DATE_CREATION

4. Créer un log détaillé :
   - SIRET traités avec succès
   - SIRET en erreur (cause : inexistant, API timeout, etc.)
   - Incohérences détectées (nom différent)

CONTRAINTES :
- Respecter le rate limiting de l'API (10 req/sec max)
- Ne PAS écraser les données existantes
- Marquer les données enrichies (colonne DATE_MAJ_API)
- Gérer les erreurs 404 (SIRET inexistant)
- Timeout de 5 secondes par requête

SÉCURITÉ :
- Ne pas inclure de token API dans le code (variable d'environnement)
- Logger sans exposer de données sensibles

FORMAT SORTIE :
- TABLEAU_de_BORD_UD66_enrichi.xlsx
- enrichissement_log_YYYYMMDD.txt
```

### 3.3 Export multi-formats (reporting externe)

```
CONTEXTE :
Je dois partager des données avec d'autres militants mais en respectant la confidentialité.

FICHIER :
data/TABLEAU_de_BORD_UD66.xlsx

TÂCHE :
Génère 3 exports adaptés à différents publics :

## Export 1 : Bureau UD (complet)
Fichier : export_bureau_ud66.xlsx
Contenu :
- Toutes les feuilles
- Toutes les colonnes
- Mise en forme professionnelle
- Tableaux croisés dynamiques pré-créés :
  * Par pilote
  * Par secteur (IDCC)
  * Par échéance électorale

## Export 2 : Militants (anonymisé partiel)
Fichier : export_militants_ud66.csv
Contenu :
- Feuille A CIBLE uniquement
- Colonnes : CIBLE, NB SALARIES, DATE SCRUTIN, VOIX CGT, ENJEUX
- EXCLURE : N° SIRET (confidentialité), CONTACT, TELEPHONE, MAIL
- Anonymiser : Remplacer PILOTE par "Référent UD"
- Trier par DATE SCRUTIN

## Export 3 : Communication externe (public)
Fichier : export_public_ud66.md
Contenu :
- Statistiques agrégées uniquement :
  * Nombre d'entreprises suivies
  * Total salariés
  * Nombre d'élections à venir
  * Taux de syndicalisation moyen
- Aucune donnée nominative
- Format Markdown pour site web/newsletter

CONTRAINTES :
- Vérifier qu'aucun export ne contient de données sensibles non autorisées
- Ajouter un watermark/footer : "Document UD 66 - Usage interne" sur Excel
- Horodater tous les exports

FORMAT SORTIE :
3 fichiers avec niveaux de confidentialité adaptés
```

---

## ✅ CATÉGORIE 4 : VALIDATION ET CONTRÔLE QUALITÉ

### 4.1 Audit complet de qualité des données

```
CONTEXTE :
Avant de finaliser mon tableau pour une présentation au bureau, je veux m'assurer de la qualité des données.

FICHIER :
data/TABLEAU_de_BORD_UD66.xlsx

TÂCHE :
Effectue un audit complet et génère "audit_qualite_ud66.json" :

{
  "audit_date": "2024-12-03T14:30:00",
  "fichier_analyse": "TABLEAU_de_BORD_UD66.xlsx",
  "resume": {
    "score_global": 85,
    "nb_erreurs_critiques": 3,
    "nb_avertissements": 12,
    "nb_suggestions": 8
  },
  "erreurs_critiques": [
    {
      "type": "siret_invalide",
      "feuille": "A CIBLE",
      "ligne": 15,
      "valeur_actuelle": "1234567890",
      "probleme": "SIRET doit contenir 14 chiffres",
      "correction_suggeree": "Vérifier auprès de l'entreprise",
      "impact": "Empêche l'import dans le Dashboard"
    }
  ],
  "avertissements": [
    {
      "type": "incoherence_effectifs",
      "feuille": "A CIBLE",
      "ligne": 23,
      "probleme": "NB_SYNDIQUES (15) > NB_SALARIES (12)",
      "correction_suggeree": "Vérifier les chiffres",
      "impact": "Statistiques faussées"
    }
  ],
  "suggestions": [
    {
      "type": "champ_manquant",
      "feuille": "A CIBLE",
      "colonne": "PILOTE",
      "nb_lignes_concernees": 5,
      "suggestion": "Assigner un pilote à ces dossiers",
      "priorite": "moyenne"
    }
  ],
  "validations_reussies": {
    "siret_valides": 42,
    "dates_coherentes": 45,
    "effectifs_coherents": 40,
    "emails_valides": 38
  }
}

VÉRIFICATIONS À EFFECTUER :
1. Format SIRET : 14 chiffres exactement
2. Format email : regex standard
3. Format téléphone : 10 chiffres français ou international
4. Cohérence dates : DATE_SCRUTIN > DATE_PRESENTATION_CE
5. Cohérence effectifs : NB_SYNDIQUES <= NB_SALARIES
6. IDCC valides : vérifier dans liste officielle si possible
7. Champs obligatoires : CIBLE, SIRET, NB_SALARIES
8. Doublons SIRET
9. Valeurs aberrantes : effectifs > 10000, syndiqués > 1000
10. Dates futures pour scrutins (pas dans le passé lointain)

SCORE GLOBAL :
- 100% = aucune erreur
- -5 points par erreur critique
- -2 points par avertissement
- -0.5 point par suggestion

FORMAT SORTIE :
- audit_qualite_ud66.json
- rapport_audit_humain.md (version lisible)
```

### 4.2 Détection de doublons et fusions

```
CONTEXTE :
J'ai saisi des entreprises plusieurs fois (erreurs, variantes de noms). Je veux détecter et fusionner les doublons.

FICHIER :
data/TABLEAU_de_BORD_UD66.xlsx

TÂCHE :
1. Détecte les doublons potentiels selon plusieurs critères :
   - SIRET identique (doublon certain)
   - Nom entreprise très similaire (distance Levenshtein < 3)
   - Même adresse + même secteur

2. Pour chaque groupe de doublons :
   - Liste les lignes concernées
   - Compare les valeurs de chaque colonne
   - Propose une fusion en gardant :
     * Les valeurs les plus récentes (dates)
     * Les valeurs les plus élevées (effectifs si différents)
     * La concaténation des champs texte (ENJEUX, OBJET)

3. Génère un rapport "doublons_detectes.csv" :
   SIRET_1, SIRET_2, Nom_1, Nom_2, Similarite, Type_doublon, Action_proposee

4. Crée un nouveau fichier Excel "nettoyé" avec doublons fusionnés
   - Conserver l'historique dans une feuille "FUSIONS_LOG"

CONTRAINTES :
- Ne fusionner automatiquement QUE les doublons certains (SIRET identique)
- Pour les doublons probables : demander validation manuelle
- Conserver une sauvegarde avant fusion

FORMAT SORTIE :
- doublons_detectes.csv (pour review)
- TABLEAU_de_BORD_UD66_nettoye.xlsx (si fusions auto)
- fusions_a_valider.xlsx (doublons probables)
```

---

## 📅 CATÉGORIE 5 : AUTOMATISATION ET ALERTES

### 5.1 Système d'alertes automatiques

```
CONTEXTE :
Je veux recevoir des alertes automatiques pour ne rien manquer.

FICHIER :
data/TABLEAU_de_BORD_UD66.xlsx

TÂCHE :
Crée un script qui génère "alertes_ud66.json" avec toutes les situations nécessitant une action :

{
  "date_generation": "2024-12-03T14:30:00",
  "alertes_critiques": [
    {
      "type": "election_imminente",
      "entreprise": "Entreprise X",
      "siret": "12345678901234",
      "date_election": "2024-12-15",
      "jours_restants": 12,
      "probleme": "PAP non validé",
      "action_requise": "Urgence : Finaliser le PAP",
      "pilote": "Jean Dupont",
      "priorite": "CRITIQUE"
    }
  ],
  "alertes_importantes": [
    {
      "type": "election_proche",
      "entreprise": "Entreprise Y",
      "date_election": "2025-01-20",
      "jours_restants": 48,
      "probleme": "Aucun contact récent avec section",
      "action_requise": "Planifier une réunion de préparation",
      "pilote": "Marie Martin",
      "priorite": "HAUTE"
    }
  ],
  "alertes_informatives": [
    {
      "type": "taux_syndicalisation_faible",
      "entreprise": "Entreprise Z",
      "taux_actuel": 2.1,
      "seuil": 5.0,
      "action_requise": "Campagne de syndicalisation",
      "priorite": "NORMALE"
    }
  ]
}

CRITÈRES D'ALERTE :

CRITIQUES (action dans les 15 jours) :
- Élection dans moins de 30 jours sans PAP
- Élection dans moins de 15 jours sans préparation
- SIRET invalide bloquant un dossier important
- Incohérence majeure dans les données

IMPORTANTES (action dans le mois) :
- Élection dans 30-60 jours sans organisation
- Pilote avec plus de 8 dossiers actifs
- Entreprise stratégique sans contact depuis 3 mois
- Taux de syndicalisation en baisse > 20%

INFORMATIVES (à surveiller) :
- Opportunité d'implantation (entreprise > 200 sans CGT)
- Taux de syndicalisation < 5%
- Convention collective non renseignée
- Champs optionnels manquants

FORMAT SORTIE :
- alertes_ud66.json
- email_template_alertes.html (pour envoi automatique)
```

### 5.2 Planificateur d'actions automatique

```
CONTEXTE :
Sur la base des données du tableau, je veux générer un plan d'actions priorisé.

FICHIER :
data/TABLEAU_de_BORD_UD66.xlsx

TÂCHE :
Génère un fichier "plan_actions_ud66.md" structuré :

# Plan d'Actions UD 66
Généré le [DATE]

## PRIORITÉ 1 : URGENCES (à traiter cette semaine)

### Élections imminentes
| Entreprise | Date | Jours | Actions | Pilote | Statut |
|------------|------|-------|---------|--------|--------|
| [...]      | [...] | 12   | Finaliser PAP + Préparer tract | J.Dupont | 🔴 URGENT |

### Actions requises :
1. ⏰ **[Entreprise X]** : Réunion de préparation électorale
   - Date limite : [DATE]
   - Participants : Pilote + militants + conseiller confédéral
   - Documents : PAP, listes électorales, professions de foi

## PRIORITÉ 2 : IMPORTANT (à traiter ce mois-ci)

### Développement syndical
- **[Entreprise Y]** : Campagne adhésions (taux actuel 2%, objectif 5%)
- **[Entreprise Z]** : Premier contact (0 syndiqué, 150 salariés)

### Préparation élections (30-60 jours)
[...]

## PRIORITÉ 3 : DÉVELOPPEMENT (à planifier)

### Nouvelles implantations
Top 5 des cibles par potentiel :
1. [Entreprise A] - 500 salariés - Secteur santé
2. [...]

### Consolidation
- Entreprises à taux de syndicalisation à améliorer
- Secteurs sous-représentés

## RESSOURCES NÉCESSAIRES

### Humaines
- Nombre de pilotes à renforcer : 2
- Secteurs nécessitant un appui confédéral : [...]

### Matérielles
- Tracts élections : 5 entreprises
- Formation PAP : 3 militants

## CALENDRIER PRÉVISIONNEL
- Semaine 1 : [actions priorité 1]
- Semaine 2 : [...]
- Mois prochain : [actions priorité 2]
- Trimestre : [actions priorité 3]

CONTRAINTES :
- Trier par urgence puis par impact potentiel
- Grouper les actions géographiquement si possible
- Estimer la charge de travail pour chaque pilote
- Identifier les actions nécessitant un appui confédéral

FORMAT SORTIE :
Markdown structuré + fichier Todoist/Notion si souhaité
```

---

## 🎓 CATÉGORIE 6 : FORMATION ET DOCUMENTATION

### 6.1 Générer une documentation utilisateur personnalisée

```
CONTEXTE :
De nouveaux militants vont utiliser le tableau de bord. Je veux créer un guide adapté à notre UD.

FICHIERS :
- template_tableau_bord_ud.json
- GUIDE_TEMPLATE_UD.md (guide générique)
- data/TABLEAU_de_BORD_UD66.xlsx (notre fichier)

TÂCHE :
Génère un guide utilisateur "GUIDE_UD66.md" personnalisé :

# Guide Utilisateur - Tableau de Bord UD 66

## 1. Introduction
- Présentation de notre tableau spécifique
- Objectifs de l'outil pour notre UD
- Captures d'écran de nos feuilles

## 2. Accéder au tableau
- Où trouver le fichier (Drive, serveur...)
- Droits d'accès
- Sauvegardes

## 3. Utiliser chaque feuille

### Feuille "TDB 66"
- Quand l'utiliser
- Comment ajouter un événement
- Exemples concrets de notre UD

### Feuille "A CIBLE"
- Quand ajouter une entreprise
- Tutoriel pas-à-pas avec screenshots
- Champs obligatoires vs optionnels
- Exemples de NOTRE département

### Feuille "A CIBLE ABSENTE"
- Critères pour identifier une cible
- Comment prioriser
- Workflow de l'implantation à la présence

## 4. Cas d'usage fréquents

### Préparer une élection
1. Vérifier la date dans le tableau
2. Créer le PAP
3. Organiser la campagne
4. Mettre à jour après les résultats

### Syndicaliser une entreprise
[...]

### Produire un bilan pour le bureau
[...]

## 5. Erreurs courantes

### "Mon SIRET n'est pas reconnu"
- Vérification : [...]
- Correction : [...]

### "Je ne trouve pas une entreprise"
- Utiliser CTRL+F
- Vérifier l'orthographe
- Peut-être dans "A CIBLE ABSENTE"

## 6. Qui contacter

### Problème technique
- Responsable informatique UD : [NOM]

### Question sur une entreprise
- Voir la colonne PILOTE

### Appui confédéral
- Voir feuille COORDONNEES EVS

INSTRUCTIONS POUR LE GUIDE :
- Utiliser des exemples RÉELS de notre UD (anonymisés si besoin)
- Ajouter des captures d'écran (tu peux décrire où les placer)
- Ton simple et pédagogique
- Inclure des FAQ basées sur nos données
- Mettre des liens vers la documentation complète

FORMAT SORTIE :
- GUIDE_UD66.md
- Liste des screenshots à créer (emplacements + descriptions)
```

---

## 🔧 CATÉGORIE 7 : OPTIMISATION ET MAINTENANCE

### 7.1 Nettoyage et optimisation du fichier

```
CONTEXTE :
Mon fichier Excel devient lourd et lent. Je veux l'optimiser sans perdre de données.

FICHIER :
data/TABLEAU_de_BORD_UD66_lourd.xlsx (5 MB)

TÂCHE :
1. Analyse la structure actuelle :
   - Taille de chaque feuille
   - Nombre de lignes utilisées vs totales
   - Formules présentes
   - Mise en forme excessive

2. Optimisations à appliquer :
   - Supprimer les lignes vides excessives
   - Supprimer les colonnes inutilisées
   - Convertir les formules en valeurs là où approprié
   - Simplifier la mise en forme
   - Compresser les images si présentes

3. Archiver les données anciennes :
   - Extraire les lignes de DATE_SCRUTIN > 2 ans
   - Les déplacer vers un fichier "archives_ud66_20XX.xlsx"
   - Conserver uniquement les 2 dernières années dans le fichier principal

4. Générer un rapport d'optimisation :
   - Taille avant/après
   - Nombre de lignes nettoyées
   - Données archivées
   - Recommandations pour maintenir les performances

CONTRAINTES :
- NE JAMAIS supprimer de données
- Créer une sauvegarde avant toute modification
- Conserver l'historique des modifications

FORMAT SORTIE :
- TABLEAU_de_BORD_UD66_optimise.xlsx (fichier allégé)
- archives_ud66_2020_2022.xlsx (données archivées)
- rapport_optimisation.txt
```

---

## 💡 ASTUCES POUR UTILISER CES PROMPTS

### 1. Personnalisation
Remplacez systématiquement :
- `[NUMERO]` par votre numéro de département
- `[NOM_DEPARTEMENT]` par le nom de votre département
- `[DATE]` par la date du jour
- `[NOM]` par les noms réels de vos pilotes/militants

### 2. Itération
Si le résultat n'est pas parfait :
```
"Reprends la génération précédente et modifie :
- Point 1 : [ce que tu veux changer]
- Point 2 : [autre modification]
Conserve le reste à l'identique."
```

### 3. Demander des explications
```
"Avant d'exécuter la tâche, explique-moi :
1. Les étapes que tu vas suivre
2. Les transformations que tu vas appliquer
3. Les fichiers que tu vas créer
Attends ma validation avant de commencer."
```

### 4. Combiner plusieurs prompts
```
"Effectue successivement les tâches suivantes :
1. [Prompt 2.1 - Rapport mensuel]
2. [Prompt 5.1 - Alertes automatiques]
3. Génère un email récapitulatif combinant les deux résultats"
```

---

## 📚 Ressources Complémentaires

- **GUIDE_TEMPLATE_UD.md** : Documentation complète (60+ pages)
- **template_tableau_bord_ud.json** : Structure de référence
- **ud_automation.py** : Scripts Python prêts à l'emploi

---

**Version** : 1.0  
**Date** : Décembre 2024  
**Maintenance** : Ajouter vos propres prompts au fur et à mesure de vos besoins
