# Guide utilisateur — PAP/CSE Dashboard

## 1. Connexion

- Accéder à [https://outilspap.up.railway.app](https://outilspap.up.railway.app) ou à l'instance locale.
- L'accueil est public ; l'onglet **Administration** requiert les identifiants communiqués (HTTP Basic).

## 2. Tableau d'accueil

### 2.1 Zone de filtres
- **Recherche** : taper une raison sociale ou un SIRET (14 chiffres).
- **Fédération / Département / Présence** : sélectionner une ou plusieurs valeurs (Ctrl/Cmd + clic pour multi-sélection).
- **Organisation syndicale** : saisir plusieurs OS séparées par des virgules (ex. `CGT, CFDT`). Les alias sont normalisés (FO → CGT-FO, SUD → Solidaires...).
- **Dates** : définir une plage pour les invitations PAP (C5) ou les PV (C3/C4).
- **Résultats/page** : 25, 50, 100 ou 200 lignes par page.
- **Tri** : choisir la colonne de tri et l'ordre (décroissant par défaut sur la date PAP C5).
- **Afficher toutes les structures** : inclut les SIRET sans correspondance PAP ↔ PV.

Cliquer sur **Filtrer** pour appliquer les critères ou **Réinitialiser** pour revenir à l'état initial.

### 2.2 Carte de métriques
- Structures recensées : union des SIRET présents dans PAP ou PV.
- Invitations / PV : volume de lignes, avec tooltip mentionnant le nombre de SIRET distincts.
- Correspondances : SIRET ayant à la fois une invitation PAP et un PV C3 ou C4.

### 2.3 Tableau principal
- Colonnes affichées : SIRET (lien vers fiche), Raison sociale, Département, Fédération, Présence (C3/C4), OS & scores C3, OS & scores C4, dates du dernier PV et du prochain PAP.
- Les scores syndicaux sont formatés « OS 42,10% » avec virgule décimale.
- Pagination en bas de page ; utiliser les boutons « « » et les numéros pour naviguer.

## 3. Dashboard analytique

L'onglet **Dashboard** affiche :
- Un résumé chiffré (structures, implantations, invitations, correspondances).
- Trois graphiques Plotly interactifs (répartition présence, top départements, fédérations).

## 4. Fiche SIRET

Accessible via un clic sur un SIRET :
- Récapitulatif synthétique (PAP, PV, présence).
- Historique complet des PV (dates, inscrits, votants, voix CGT, payload brut).
- Historique des invitations PAP.

## 5. Administration

### 5.1 Importer des PV C3/C4
1. Cliquer sur **Administration** (authentification demandée).
2. Importer le fichier Excel (une feuille). Les colonnes clés recherchées : SIRET, Cycle, Date du PV, Inscrits, Votants, Voix CGT, FD, Département, etc.
3. Après validation, un message confirme le nombre de lignes insérées/mises à jour. La table de synthèse est reconstruite automatiquement.

### 5.2 Importer des invitations PAP C5
Procédure identique. Seules les lignes avec SIRET + date sont conservées.

### 5.3 Reconstruire le tableau
Bouton « Mettre à jour le tableau » → envoie une requête POST sur `/api/admin/rebuild-summary` et reconstruit `siret_summary`.

## 6. Exports

- **Exports filtrés** : liens disponibles dans la barre supérieure (bientôt via bouton dédié).
- `/exports/siret-summary/csv` ou `/excel` respectent les filtres passés dans l'URL.
- `/exports/pv-events/csv` et `/exports/invitations/csv` fournissent les données brutes.

## 7. Bonnes pratiques

- Importer les PV avant les invitations pour bénéficier des FD/départements les plus fiables.
- Vérifier régulièrement le log d'audit (`logs/audit.log`) pour suivre les opérations sensibles.
- Sauvegarder le fichier SQLite `papcse.db` avant de lancer des imports massifs.
- Utiliser les filtres de dates pour préparer une stratégie PAP (identification des protocoles imminents).

Bon usage !
