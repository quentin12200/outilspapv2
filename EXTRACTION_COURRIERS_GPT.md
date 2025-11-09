# Extraction automatique de courriers PAP via GPT-4 Vision

## 📋 Description

Cette fonctionnalité permet d'extraire automatiquement les informations clés depuis des courriers PAP (Protocoles d'Accord Préélectoral, invitations C5, etc.) en utilisant l'intelligence artificielle GPT-4 Vision d'OpenAI.

**Avantages :**
- ⚡ **Gain de temps** : Plus besoin de saisir manuellement les informations
- 🎯 **Précision** : Extraction fiable des données structurées (SIRET, dates, adresses, etc.)
- 📸 **Flexibilité** : Fonctionne avec des photos prises au téléphone ou des scans
- 🔄 **Sauvegarde automatique** : Création directe d'invitations dans la base de données

## 🚀 Configuration

### 1. Obtenir une clé API OpenAI

1. Créez un compte sur [OpenAI Platform](https://platform.openai.com/)
2. Ajoutez des crédits à votre compte (généralement ~$5-10 pour commencer)
3. Générez une clé API depuis [API Keys](https://platform.openai.com/api-keys)

### 2. Configurer la clé API

**⚠️ SÉCURITÉ : Ne JAMAIS partager ou commiter votre clé API**

Ajoutez votre clé dans le fichier `.env` à la racine du projet :

```bash
# .env
OPENAI_API_KEY=sk-proj-VOTRE_CLE_ICI

# Optionnel: Modèle OpenAI à utiliser (par défaut: gpt-4o)
# Options: gpt-4o, gpt-4-turbo, gpt-4o-mini
OPENAI_MODEL=gpt-4o
```

### 3. Installer les dépendances

```bash
pip install -r requirements.txt
```

Les nouvelles dépendances installées :
- `openai==1.54.3` - Client officiel OpenAI
- `pillow==10.4.0` - Traitement d'images
- `pdf2image==1.17.0` - Conversion de PDF en images

### 4. Redémarrer l'application

```bash
# En développement
uvicorn app.main:app --reload

# Ou avec le script fourni
./run.sh
```

## 📖 Utilisation

### Interface web

1. Accédez à la page **"Extraction automatique"** depuis le menu "Données PAP"
2. Uploadez une ou plusieurs images de courriers PAP
3. (Optionnel) Cochez "Sauvegarder automatiquement" pour créer directement des invitations
4. Cliquez sur "Extraire les informations"
5. Consultez les résultats extraits et affinez si nécessaire

### API REST

#### Extraire un seul document

```bash
curl -X POST "http://localhost:8000/api/extract/document" \
  -F "file=@courrier_pap.jpg" \
  -F "auto_save=true"
```

Réponse :
```json
{
  "success": true,
  "data": {
    "siret": "12345678901234",
    "raison_sociale": "ENTREPRISE EXAMPLE SAS",
    "adresse": "123 Rue de la République",
    "code_postal": "75001",
    "ville": "Paris",
    "date_invitation": "2024-01-15",
    "date_election": "2024-02-20",
    "effectif": 150,
    "idcc": "1234",
    "confidence": "high",
    ...
  },
  "metadata": {
    "auto_saved": true,
    "invitation_id": 42
  }
}
```

#### Extraire plusieurs documents (batch)

```bash
curl -X POST "http://localhost:8000/api/extract/batch" \
  -F "files=@courrier1.jpg" \
  -F "files=@courrier2.jpg" \
  -F "files=@courrier3.jpg" \
  -F "auto_save=true"
```

#### Vérifier l'état du service

```bash
curl http://localhost:8000/api/extract/health
```

### Formats de documents supportés

- **JPG / JPEG** ✅
- **PNG** ✅
- **WEBP** ✅
- **PDF** ✅ (première page extraite automatiquement)

**Taille maximale recommandée :** 10 MB par fichier

**Note sur les PDF :** Les PDF sont automatiquement convertis en image (première page) avant l'extraction. Pour les PDF multipages, seule la première page est traitée.

## 📊 Informations extraites

Le système extrait automatiquement :

### Informations entreprise
- SIRET / SIREN
- Raison sociale
- Enseigne commerciale
- Adresse complète (rue, CP, ville)

### Dates importantes
- Date du courrier / invitation
- Date de l'élection
- Date limite de candidature

### Informations électorales
- Type de scrutin (CSE, DP, CE, etc.)
- Collèges électoraux
- Nombre de sièges à pourvoir
- Syndicats invités

### Convention collective
- Code IDCC
- Nom de la convention

### Contacts
- Nom, fonction
- Email, téléphone

### Métadonnées
- Niveau de confiance (high/medium/low)
- Texte brut complet extrait
- Notes et informations complémentaires

## 💰 Coûts

Le service utilise par défaut **GPT-4o** (modèle performant et largement accessible) :

**Tarif approximatif avec gpt-4o :** ~$0.01 - 0.03 par document

- Une extraction coûte environ 1 à 3 centimes de dollar
- Pour 100 documents : ~$1-3
- Pour 1000 documents : ~$10-30

**Tarifs selon le modèle :**
- `gpt-4o` (défaut) : ~$0.01-0.03/doc - ⭐ Recommandé : bon équilibre performance/coût et large accessibilité
- `gpt-4o-mini` : ~$0.001-0.003/doc - Plus économique mais accès limité selon votre plan OpenAI
- `gpt-4-turbo` : ~$0.02-0.05/doc - Ancien modèle, plus cher

💡 **Astuce :** Les images sont automatiquement optimisées pour réduire les coûts sans perte de précision.

## 🔧 Intégration dans le workflow

### Workflow recommandé

1. **Réception du courrier PAP**
   - Photo ou scan du document

2. **Upload sur la plateforme**
   - Via l'interface web ou l'API

3. **Extraction automatique**
   - GPT-4 Vision analyse le document

4. **Vérification manuelle**
   - Revue des informations extraites
   - Niveau de confiance indiqué

5. **Sauvegarde**
   - Automatique ou manuelle
   - Création de l'invitation dans la base

6. **Enrichissement**
   - Ajout de UD/FD si nécessaire
   - Enrichissement via API Sirene

## ⚙️ Configuration avancée

### Modifier le modèle utilisé

Par défaut, `gpt-4o` est utilisé. Vous pouvez changer le modèle de deux façons :

**1. Via variable d'environnement (recommandé) :**

```bash
# Dans le fichier .env
OPENAI_MODEL=gpt-4o  # ou gpt-4o-mini, gpt-4-turbo
```

**2. Via le code (pour un usage ponctuel) :**

```python
# app/services/document_extractor.py
extractor = DocumentExtractor(model="gpt-4o")
extracted_data = extractor.extract_from_document(
    document_data,
    is_pdf=False,
    temperature=0.1
)
```

### Personnaliser le prompt

Le prompt d'extraction peut être personnalisé dans :
`app/services/document_extractor.py` → méthode `extract_from_image()`

## 🛡️ Sécurité et confidentialité

### Protection de la clé API

✅ **FAIRE :**
- Stocker la clé dans le fichier `.env`
- Ajouter `.env` au `.gitignore`
- Utiliser des variables d'environnement en production

❌ **NE JAMAIS :**
- Commiter la clé dans le code source
- Partager la clé publiquement
- Afficher la clé dans les logs

### Confidentialité des données

⚠️ **Important :** Les images sont envoyées à l'API OpenAI pour traitement.

- OpenAI ne conserve pas les images pour entraîner ses modèles (politique API)
- Les données ne sont pas utilisées pour améliorer les modèles OpenAI
- Voir [OpenAI Data Usage Policy](https://openai.com/policies/usage-policies)

**Pour des documents ultra-sensibles :** Envisager une solution d'OCR locale (Tesseract + extraction par règles).

## 🐛 Dépannage

### Erreur "Clé API non configurée"

```
Clé API OpenAI manquante. Veuillez configurer OPENAI_API_KEY dans le fichier .env
```

**Solution :**
1. Vérifiez que le fichier `.env` existe à la racine
2. Vérifiez que `OPENAI_API_KEY=sk-...` est présent
3. Redémarrez l'application

### Erreur "Invalid API key"

**Solution :**
1. Vérifiez que la clé est valide sur [OpenAI Platform](https://platform.openai.com/api-keys)
2. Vérifiez qu'il n'y a pas d'espaces avant/après la clé
3. Générez une nouvelle clé si nécessaire

### Faible niveau de confiance (confidence: low)

**Causes possibles :**
- Image floue ou de mauvaise qualité
- Document mal cadré
- Informations incomplètes sur le document

**Solutions :**
- Reprendre la photo avec une meilleure qualité
- S'assurer que tout le texte est lisible
- Vérifier manuellement les informations extraites

### Extraction incorrecte du SIRET

**Solution :**
1. Vérifiez la qualité de l'image
2. Si le problème persiste, ajustez le prompt pour insister sur la précision du SIRET
3. Revérifiez manuellement avant sauvegarde

## 📚 Architecture technique

### Structure des fichiers

```
app/
├── services/
│   └── document_extractor.py      # Service d'extraction GPT
├── routers/
│   └── api_document_extraction.py # Endpoints API
├── templates/
│   └── extraction.html             # Interface web
└── config.py                       # Configuration (clé API)
```

### Schémas de données

```python
class ExtractionResult(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]]
    error: Optional[str]
    metadata: Optional[Dict[str, Any]]
```

### Endpoints disponibles

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/extract/document` | POST | Extrait un seul document |
| `/api/extract/batch` | POST | Extrait plusieurs documents |
| `/api/extract/save-invitation` | POST | Sauvegarde manuellement une invitation |
| `/api/extract/health` | GET | Vérifie l'état du service |
| `/extraction` | GET | Interface web |

## 🔮 Améliorations futures

- [x] ~~Support des PDF~~ ✅ Implémenté (première page)
- [ ] Support des PDF multipages (traiter toutes les pages)
- [ ] Extraction de courriers manuscrits
- [ ] Détection automatique du type de document
- [ ] Export des résultats en Excel
- [ ] Validation automatique des données extraites
- [ ] Interface de correction en masse
- [ ] Statistiques d'utilisation et de coûts

## 📞 Support

Pour toute question ou problème :
1. Consultez cette documentation
2. Vérifiez les logs de l'application
3. Consultez la [documentation OpenAI](https://platform.openai.com/docs)

---

**Version :** 1.0
**Dernière mise à jour :** 8 novembre 2024
