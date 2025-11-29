# 📄 Import PDF PAP - Documentation

## Vue d'ensemble

Ce système permet d'importer des **fichiers PDF de Protocoles d'Accord Pré-électoral (PAP)** directement depuis l'interface admin. Le workflow est entièrement automatisé :

```
PDF Upload → Extraction texte → Analyse ChatGPT → Enrichissement SIRENE/Pappers → Génération emails
```

## 🚀 Fonctionnalités

### 1. **Extraction automatique depuis PDF**
- Extraction du texte via `pypdf`
- Analyse intelligente via GPT-4o pour identifier :
  - ✅ Numéros SIRET (14 chiffres)
  - ✅ Raisons sociales des entreprises
  - ✅ Adresses complètes (rue, CP, ville)
  - ✅ Dates (invitation, élection, signature)
  - ✅ Union Départementale (UD)
  - ✅ Fédération (FD)
  - ✅ Effectifs si mentionnés

### 2. **Enrichissement multi-sources**
- **API SIRENE** (données officielles INSEE)
- **API Pappers** (informations juridiques et financières)
- **Mapping IDCC → FD** automatique

### 3. **Génération d'emails ciblée**
- ⚠️ **IMPORTANT** : Seules les invitations importées dans **la dernière heure** reçoivent des emails
- Évite les doublons pour les anciens PAP
- Emails avec lien PAP scanner : `https://app.pap-cse.org/siret/{SIRET}`

## 📋 Prérequis

### Configuration requise

1. **Clé API OpenAI** configurée dans `.env` :
   ```bash
   OPENAI_API_KEY=sk-...
   OPENAI_MODEL=gpt-4o  # Recommandé
   ```

2. **Dépendances installées** :
   ```bash
   pip install pypdf==5.1.0 cffi
   pip install -r requirements.txt
   ```

3. **Base de données à jour** avec les champs :
   - `invitations.created_at` (DateTime)
   - `invitations.updated_at` (DateTime)

## 🎯 Workflow d'utilisation

### Étape 1 : Import du PDF

1. Connectez-vous à l'interface admin : `/admin`
2. Section **"Importer PAP (Protocole d'Accord Pré-électoral)"**
3. Cliquez sur **"Sélectionnez le fichier PDF du PAP"**
4. Cochez **"Scan automatique multi-sources"** (recommandé)
5. Cliquez sur **"Importer PDF et scanner"**

### Étape 2 : Vérification du résultat

Après l'import, vous verrez :
```
✅ Import réussi !
• X invitations importées
• Y enrichies automatiquement
• Z erreurs lors de l'enrichissement
⚠️ W invitations nécessitent une complétion manuelle
```

### Étape 3 : Complétion manuelle (si nécessaire)

Si certaines données sont manquantes :

1. Cliquez sur **"Compléter manuellement"**
2. Vous serez redirigé vers `/invitations`
3. Utilisez le bouton **"Scanner automatique"** pour ré-enrichir
4. Ou complétez manuellement via la fiche SIRET de chaque entreprise

### Étape 4 : Génération des emails

1. Retournez sur `/admin`
2. Section **"Campagne PAP - Cycle 5"**
3. Cliquez sur **"Génération d'emails"**
4. ⚠️ **IMPORTANT** : Seules les invitations importées dans la dernière heure seront incluses
5. Téléchargez ou copiez les emails générés

### Étape 5 : Export Excel

1. Allez sur `/invitations`
2. Filtrez les invitations si nécessaire
3. Cliquez sur **"Copier pour Excel"**
4. Les données sont copiées au format TSV (tabulé)
5. Collez dans Excel avec Ctrl+V / Cmd+V

## 🧪 Tests

### Test manuel avec un PDF de démonstration

```bash
# Créer un PDF de test simple
python test_pdf_extraction.py /chemin/vers/votre/pap.pdf
```

Ce script va :
- ✅ Extraire le texte du PDF
- ✅ Détecter les SIRET (14 chiffres)
- ✅ Détecter les dates
- ✅ Vérifier la présence de mots-clés PAP
- ✅ Afficher des statistiques

### Test de l'API

Utilisez curl ou Postman :

```bash
curl -X POST "http://localhost:8000/api/invitations/import-pap-pdf" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@/chemin/vers/pap.pdf" \
  -F "auto_scan=on"
```

Réponse attendue :
```json
{
  "success": true,
  "inserted": 5,
  "enrichies": 4,
  "erreurs": 1,
  "incomplets": 1,
  "message": "5 invitations importées depuis le PDF, 4 enrichies automatiquement. 1 nécessitent une complétion manuelle."
}
```

## 🔧 Configuration avancée

### Ajuster la période pour les "nouveaux PAP"

Par défaut, seules les invitations créées dans **la dernière heure** reçoivent des emails.

Pour modifier cette période, éditez `app/main.py:3896` :

```python
# De 1 heure à 24 heures
one_hour_ago = datetime.now() - timedelta(hours=24)
```

### Améliorer le prompt ChatGPT

Le prompt d'extraction se trouve dans `app/main.py:3674-3713`.

Si vos PDF ont un format spécifique, ajustez le prompt pour :
- Extraire des champs supplémentaires
- Gérer des formats de date particuliers
- Détecter des patterns spécifiques

Exemple d'ajout d'un champ :
```python
{{
    "invitations": [
        {{
            ...
            "commentaire": "texte libre du PAP",
            "nombre_salaries": 150
        }}
    ]
}}
```

### Limiter la longueur du texte analysé

Par défaut, seuls les **8000 premiers caractères** sont envoyés à ChatGPT :

```python
{pdf_text[:8000]}  # Limite à 8000 caractères
```

Augmentez si nécessaire (attention aux coûts API).

## ⚠️ Limitations connues

### 1. PDF scannés (images)

Si le PDF contient des **images scannées** plutôt que du texte :
- L'extraction `pypdf` ne fonctionnera pas
- **Solution** : Ajouter un OCR (tesseract-ocr, Google Vision API)

### 2. Formats de PDF complexes

Certains PDF avec des mises en page complexes peuvent mal s'extraire.
- **Solution** : Pré-traiter le PDF ou utiliser `pdfplumber` à la place de `pypdf`

### 3. Coût de l'API ChatGPT

Chaque PDF importé coûte environ :
- **GPT-4o** : ~0.01-0.05 USD par PDF (selon la taille)
- **GPT-4o-mini** : ~0.001-0.005 USD par PDF

Pour réduire les coûts :
- Utilisez `gpt-4o-mini` dans `.env`
- Limitez la longueur du texte analysé

### 4. Rate limiting

L'API OpenAI a des limites de requêtes :
- **Tier 1** : 500 requêtes/minute, 10,000 tokens/minute
- **Tier 2+** : Limites plus élevées

Pour éviter les erreurs :
- Importez les PDF un par un
- Attendez quelques secondes entre chaque import

## 🐛 Dépannage

### Erreur : "Clé API OpenAI non configurée"

```bash
# Vérifier la configuration
cat .env | grep OPENAI_API_KEY

# Ajouter la clé si manquante
echo "OPENAI_API_KEY=sk-..." >> .env
```

### Erreur : "Le PDF ne contient pas de texte extractible"

Le PDF est probablement une image scannée. Solutions :
1. Utiliser un PDF avec du texte sélectionnable
2. Ajouter un OCR au workflow
3. Utiliser un service externe (Adobe, Google Vision)

### Erreur : "Aucune invitation trouvée dans le PDF"

ChatGPT n'a pas réussi à extraire de SIRET. Vérifiez :
1. Le PDF contient bien des SIRET (14 chiffres)
2. Le format du PDF n'est pas trop complexe
3. Ajustez le prompt ChatGPT si nécessaire

### Performances lentes

Si l'import prend plus de 30 secondes :
1. Vérifiez votre connexion internet (API ChatGPT/SIRENE/Pappers)
2. Réduisez la longueur du texte analysé (`pdf_text[:4000]`)
3. Utilisez `gpt-4o-mini` au lieu de `gpt-4o`

## 📊 Monitoring

### Logs

Les logs détaillés sont dans la console :

```bash
# Démarrer l'application avec logs
uvicorn app.main:app --reload --log-level info

# Rechercher les logs d'import
grep "Import PDF" logs/app.log
```

### Métriques

Vous pouvez tracker :
- Nombre d'imports PDF par jour
- Taux d'enrichissement réussi
- Nombre d'invitations incomplètes
- Coût API ChatGPT

## 🔐 Sécurité

### Validation des fichiers

Le système valide :
- ✅ Type MIME : `application/pdf`
- ✅ Extension : `.pdf`
- ✅ Taille maximale : définie par FastAPI (par défaut : 10 MB)

### Authentification

L'endpoint `/api/invitations/import-pap-pdf` nécessite :
- ✅ Authentification utilisateur (`Depends(get_current_user)`)
- ✅ Rôle admin (si configuré)

## 📞 Support

En cas de problème :

1. **Consultez les logs** : `uvicorn` affiche les erreurs détaillées
2. **Testez avec le script** : `python test_pdf_extraction.py`
3. **Vérifiez la configuration** : clés API, dépendances, base de données
4. **Créez un issue GitHub** avec :
   - Version Python
   - Logs d'erreur complets
   - Exemple de PDF anonymisé (si possible)

## 🎓 Exemples

### Exemple de PDF PAP bien formaté

```
PROTOCOLE D'ACCORD PRÉ-ÉLECTORAL

Entreprise : ACME CORP
SIRET : 12345678901234
Adresse : 123 Rue de la République, 75001 Paris

Date d'invitation : 15/01/2024
Date d'élection : 20/03/2024

Union Départementale : UD 75
Fédération : Métallurgie

Nombre de salariés : 150
```

### Exemple de résultat d'extraction

```json
{
  "invitations": [
    {
      "siret": "12345678901234",
      "denomination": "ACME CORP",
      "adresse": "123 Rue de la République",
      "code_postal": "75001",
      "commune": "Paris",
      "date_invit": "2024-01-15",
      "date_election": "2024-03-20",
      "ud": "UD 75",
      "fd": "Métallurgie",
      "effectif_connu": 150,
      "source": "Import PDF PAP"
    }
  ]
}
```

## ✅ Checklist de mise en production

- [ ] Clé API OpenAI configurée et testée
- [ ] Dépendances installées (`pypdf`, `cffi`, `openai`)
- [ ] Base de données migrée (champs `created_at`, `updated_at`)
- [ ] Test avec au moins 3 PDF PAP réels
- [ ] Vérification de l'enrichissement SIRENE/Pappers
- [ ] Test de génération d'emails
- [ ] Export Excel fonctionnel
- [ ] Logs activés et monitoring en place
- [ ] Documentation accessible aux utilisateurs

---

**Version** : 1.0
**Date** : 2025-01-29
**Auteur** : Claude AI Assistant
