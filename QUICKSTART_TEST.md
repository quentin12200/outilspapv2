# 🚀 Guide de test rapide - Import PDF PAP

## ✅ Vérifications préliminaires

### 1. Toutes les dépendances sont installées

```bash
✅ pypdf version: 5.1.0
✅ cffi version: 2.0.0
✅ openai version: 1.54.3
✅ Tous les imports nécessaires fonctionnent correctement
```

### 2. Configuration OpenAI

Avant de tester, vérifiez votre fichier `.env` :

```bash
# Vérifier la configuration
cat .env | grep OPENAI

# Devrait afficher :
# OPENAI_API_KEY=sk-...
# OPENAI_MODEL=gpt-4o
```

Si la clé n'est pas configurée :

```bash
echo "OPENAI_API_KEY=sk-votre-cle-ici" >> .env
echo "OPENAI_MODEL=gpt-4o" >> .env
```

## 🧪 Tests recommandés

### Test 1 : Extraction PDF (sans ChatGPT)

Testez d'abord que pypdf peut extraire le texte de votre PDF :

```bash
python test_pdf_extraction.py /chemin/vers/votre/pap.pdf
```

**Résultat attendu :**
```
🔍 Test d'extraction PDF: /chemin/vers/pap.pdf
============================================================

1️⃣ Extraction du texte...
   Page 1: 1234 caractères extraits

   ✅ Total: 1234 caractères extraits depuis 1 page(s)

2️⃣ Extrait du contenu (500 premiers caractères):
------------------------------------------------------------
PROTOCOLE D'ACCORD PRÉ-ÉLECTORAL
Entreprise : ACME CORP
SIRET : 12345678901234
...
------------------------------------------------------------

3️⃣ Analyse des patterns PAP:
   ✅ SIRET trouvé(s): ['12345678901234']
   ✅ Date(s) trouvée(s): ['15/01/2024', '20/03/2024']
   ✅ Mots-clés PAP trouvés: PAP, protocole, élection, CSE

4️⃣ Statistiques:
   • Nombre de lignes: 45
   • Nombre de mots: 234
   • Taille en octets: 1456

============================================================
✅ PDF lisible avec des données extractibles détectées
   Le document semble compatible avec l'import PAP automatique
```

### Test 2 : Démarrer l'application

```bash
# Démarrer l'application en mode développement
uvicorn app.main:app --reload --log-level info
```

**Vérifier que l'application démarre sans erreur :**
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [12345] using StatReload
INFO:     Started server process [12346]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

### Test 3 : Tester l'interface admin

1. Ouvrez votre navigateur : `http://localhost:8000/admin`
2. Connectez-vous avec vos identifiants admin
3. Cherchez la section **"Importer PAP (Protocole d'Accord Pré-électoral)"**
4. Vérifiez que :
   - ✅ Le formulaire accepte `.pdf`
   - ✅ Le texte mentionne "extraction PDF (OCR + ChatGPT)"
   - ✅ Le bouton indique "Importer PDF et scanner"

### Test 4 : Import d'un PDF test

**Option A : Avec un vrai PDF PAP**

1. Cliquez sur "Sélectionnez le fichier PDF du PAP"
2. Choisissez votre fichier PDF
3. Cochez "Scan automatique multi-sources"
4. Cliquez sur "Importer PDF et scanner"
5. Attendez 10-30 secondes (selon la taille du PDF)

**Résultat attendu :**
```
✅ Import réussi !
• 3 invitations importées
• 2 enrichies automatiquement
• 0 erreurs lors de l'enrichissement
⚠️ 1 invitations nécessitent une complétion manuelle
```

**Option B : Créer un PDF de test**

Si vous n'avez pas de PDF PAP réel, créez un document texte avec ce contenu et sauvegardez-le en PDF :

```
PROTOCOLE D'ACCORD PRÉ-ÉLECTORAL - CYCLE 5

Entreprise : ACME CORPORATION SAS
SIRET : 85251548100018
Adresse : 123 Avenue de la République
Code Postal : 75011
Ville : Paris

Date d'invitation : 15/01/2024
Date de l'élection : 15/03/2024

Union Départementale : UD 75
Fédération : Métallurgie

Nombre de salariés : 150 personnes

---

Entreprise : BETA SERVICES SARL
SIRET : 53212345600012
Adresse : 45 Rue Victor Hugo
Code Postal : 69002
Ville : Lyon

Date d'invitation : 20/01/2024
Date de l'élection : 25/03/2024

Union Départementale : UD 69
Fédération : Commerce

Nombre de salariés : 85 personnes
```

### Test 5 : Vérifier les invitations importées

1. Allez sur `/invitations`
2. Vérifiez que les nouvelles invitations apparaissent
3. Vérifiez les champs :
   - ✅ SIRET (14 chiffres)
   - ✅ Dénomination (nom de l'entreprise)
   - ✅ Adresse, CP, Commune
   - ✅ Date d'invitation
   - ✅ UD et FD
   - ✅ Source = "Import PDF PAP"

### Test 6 : Enrichissement automatique

Si certaines données sont manquantes :

1. Retournez sur `/admin`
2. Cliquez sur "Scanner automatique" dans la section Campagne PAP
3. Attendez 1-2 minutes
4. Vérifiez que les données manquantes ont été enrichies (raison sociale, NAF, etc.)

### Test 7 : Génération d'emails

1. Sur `/admin`, section "Campagne PAP"
2. Cliquez sur "Génération d'emails"
3. Vérifiez l'alerte : **"IMPORTANT : Seules les invitations importées dans la dernière heure seront incluses"**
4. Confirmez

**Résultat attendu :**
```
✅ X emails générés

Aperçu des 10 premiers :
[Liste des emails avec lien PAP scanner]
```

### Test 8 : Export Excel

1. Allez sur `/invitations`
2. Cliquez sur "Copier pour Excel"
3. Attendez le message : "✅ Données copiées dans le presse-papiers !"
4. Ouvrez Excel/LibreOffice Calc
5. Collez (Ctrl+V / Cmd+V)
6. Vérifiez que les colonnes sont bien séparées

## 🐛 Problèmes courants et solutions

### Erreur : "Clé API OpenAI non configurée"

```bash
# Solution
echo "OPENAI_API_KEY=sk-votre-cle" >> .env
# Redémarrer l'application
```

### Erreur : "ModuleNotFoundError: No module named 'pypdf'"

```bash
# Solution
pip install pypdf==5.1.0 cffi
```

### Erreur : "Le PDF ne contient pas de texte extractible"

**Problème :** Votre PDF est une image scannée.

**Solutions :**
1. Utilisez un PDF avec du texte sélectionnable
2. Ajoutez un OCR (tesseract) au workflow
3. Convertissez le PDF avec un outil OCR en ligne

### Erreur : "Aucune invitation trouvée dans le PDF"

**Problème :** ChatGPT n'a pas trouvé de SIRET.

**Solutions :**
1. Vérifiez que le PDF contient bien des numéros SIRET (14 chiffres)
2. Testez avec `python test_pdf_extraction.py` pour voir ce qui est extrait
3. Ajustez le prompt ChatGPT dans `app/main.py:3674`

### L'import prend plus de 30 secondes

**Causes possibles :**
- Connexion internet lente (API ChatGPT, SIRENE, Pappers)
- PDF très long
- Rate limiting de l'API

**Solutions :**
1. Réduire la longueur du texte analysé : `pdf_text[:4000]` au lieu de `[:8000]`
2. Utiliser `gpt-4o-mini` au lieu de `gpt-4o`
3. Désactiver le scan automatique temporairement

## 📊 Vérification des logs

Pendant l'import, surveillez les logs dans le terminal :

```bash
# Logs attendus
INFO:     Extraction du texte depuis le PDF...
INFO:     Texte extrait: 1234 caractères
INFO:     Extraction des données structurées via ChatGPT...
INFO:     Données extraites: {'invitations': [{'siret': '...', ...}]}
INFO:     Import PDF: 2 invitations créées
INFO:     Début du scan automatique multi-sources...
INFO:     Scan terminé: 2 enrichies, 0 erreurs
```

## ✅ Checklist de validation

- [ ] pypdf installé et fonctionnel
- [ ] OpenAI API configurée
- [ ] Test d'extraction PDF réussi (`test_pdf_extraction.py`)
- [ ] Application démarre sans erreur
- [ ] Interface admin affiche le formulaire PDF
- [ ] Import d'un PDF test réussi
- [ ] Au moins 1 invitation créée
- [ ] Enrichissement automatique fonctionnel
- [ ] Génération d'emails réussie
- [ ] Export Excel fonctionne

## 🎯 Prochaines étapes

Une fois tous les tests validés :

1. **Testez avec vos vrais PDF PAP**
2. **Ajustez le prompt ChatGPT** si nécessaire (selon votre format de PDF)
3. **Configurez le monitoring** (logs, métriques)
4. **Formez vos utilisateurs** à utiliser la nouvelle interface
5. **Créez une pull request** pour merger ces changements

## 📞 Besoin d'aide ?

Si vous rencontrez des problèmes :

1. Vérifiez la documentation complète : `IMPORT_PDF_PAP.md`
2. Consultez les logs détaillés
3. Testez avec `test_pdf_extraction.py`
4. Créez un issue GitHub avec :
   - Logs d'erreur complets
   - Version Python
   - Exemple de PDF (anonymisé)

---

**Bonne chance avec vos tests !** 🚀
