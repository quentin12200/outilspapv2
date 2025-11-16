# Intégration Resend - Documentation

Ce document explique l'intégration de Resend pour l'envoi d'emails dans l'application PAP/CSE.

## Vue d'ensemble

L'application utilise [Resend](https://resend.com) comme service d'envoi d'emails. Resend est une API moderne d'envoi d'emails conçue pour les développeurs, offrant :

- API simple et fiable
- Templates HTML personnalisables
- Tracking des emails (envoi, ouverture, clics)
- Dashboard pour monitorer les envois
- Support des pièces jointes

## Configuration

### 1. Obtenir une clé API Resend

1. Créez un compte sur [resend.com](https://resend.com)
2. Allez dans **API Keys** dans le dashboard
3. Créez une nouvelle clé API
4. Copiez la clé (elle commence par `re_`)

### 2. Configurer les variables d'environnement

Ajoutez les variables suivantes dans votre fichier `.env` :

```bash
# === Resend API (envoi d'emails) ===
RESEND_API_KEY=re_votre_cle_api_resend
RESEND_FROM_EMAIL=onboarding@resend.dev  # En développement
RESEND_FROM_NAME=PAP/CSE - Tableau de bord
```

**En production**, vous devez :
1. Vérifier votre domaine dans Resend
2. Utiliser une adresse email de votre domaine vérifié (ex: `noreply@votredomaine.com`)

```bash
RESEND_FROM_EMAIL=noreply@votredomaine.com
```

### 3. Installer les dépendances

La dépendance Resend est déjà dans `requirements.txt` :

```bash
pip install -r requirements.txt
```

## Architecture

### Structure des fichiers

```
app/
├── services/
│   └── email_service.py          # Service Resend
├── routers/
│   └── api_email.py               # Endpoints API
├── email_templates/               # Templates HTML
│   ├── base.html
│   ├── test.html
│   ├── invitation.html
│   ├── user_approved.html
│   └── user_registration_admin.html
├── models.py                      # Modèle EmailLog
└── config.py                      # Configuration Resend
```

### Service Email (`app/services/email_service.py`)

Le service `ResendEmailService` gère toutes les interactions avec l'API Resend :

```python
from app.services.email_service import get_resend_service

# Récupérer le service
resend_service = get_resend_service()

# Envoyer un email
result = await resend_service.send_email(
    to="user@example.com",
    subject="Test Email",
    html="<h1>Hello World</h1>"
)
```

**Fonctionnalités :**
- `send_email()` : Envoie un email simple
- `send_batch_emails()` : Envoie plusieurs emails en lot
- `get_email()` : Récupère les informations d'un email envoyé

### Modèle EmailLog (`app/models.py`)

La table `email_logs` enregistre tous les emails envoyés :

```python
class EmailLog(Base):
    __tablename__ = "email_logs"

    # Informations de l'email
    to_email: str
    subject: str
    from_email: str

    # Statut
    status: str  # pending, sent, delivered, failed, bounced, opened, clicked
    resend_id: str
    error_message: str

    # Timestamps
    created_at: datetime
    sent_at: datetime
    delivered_at: datetime
    opened_at: datetime

    # Métadonnées
    context_type: str  # invitation, notification, test, etc.
    user_id: int
    siret: str
    metadata: dict
```

### API Endpoints (`app/routers/api_email.py`)

L'API expose plusieurs endpoints pour gérer les emails :

#### 1. Envoyer un email personnalisé

```http
POST /api/email/send
Content-Type: application/json

{
    "to": "user@example.com",
    "subject": "Test Email",
    "html": "<h1>Hello</h1>",
    "context_type": "test"
}
```

#### 2. Envoyer un email depuis un template

```http
POST /api/email/send-template
Content-Type: application/json

{
    "to": "user@example.com",
    "template_name": "test",
    "subject": "Email de test",
    "template_data": {
        "timestamp": "2024-03-15 10:30:00",
        "recipient_email": "user@example.com"
    }
}
```

#### 3. Envoyer un email de test

```http
POST /api/email/send-test?to=user@example.com
```

#### 4. Récupérer les logs d'emails

```http
GET /api/email/logs?limit=20&status=sent&days=7
```

Paramètres :
- `limit` : Nombre de logs (défaut: 50)
- `offset` : Pagination
- `status` : Filtrer par statut
- `to_email` : Filtrer par destinataire
- `context_type` : Filtrer par type
- `days` : Filtrer par période (7 derniers jours)

#### 5. Récupérer les statistiques

```http
GET /api/email/stats?days=30
```

Retourne :
```json
{
    "total": 150,
    "sent": 145,
    "failed": 5,
    "pending": 0,
    "delivered": 140,
    "opened": 85,
    "clicked": 23,
    "bounced": 2
}
```

#### 6. Lister les templates disponibles

```http
GET /api/email/templates
```

## Templates d'emails

Les templates sont des fichiers HTML dans `app/email_templates/`.

### Templates disponibles

1. **test.html** : Email de test pour vérifier la configuration
2. **invitation.html** : Notification d'invitation électorale
3. **user_approved.html** : Notification d'approbation de compte
4. **user_registration_admin.html** : Notification admin pour nouvelle demande

### Utiliser un template

```python
from app.routers.api_email import send_template_email

# Préparer les données
template_data = {
    "first_name": "Jean",
    "email": "jean@example.com",
    "login_url": "https://app.example.com/login"
}

# Envoyer
await send_template_email(
    request=request,
    email_data=SendTemplateEmailRequest(
        to="jean@example.com",
        template_name="user_approved",
        subject="Votre compte a été approuvé",
        template_data=template_data
    ),
    db=db
)
```

### Créer un nouveau template

1. Créez un fichier HTML dans `app/email_templates/`
2. Utilisez des variables avec la syntaxe `{{ variable }}`
3. Exemple :

```html
<!DOCTYPE html>
<html>
<body>
    <h1>Bonjour {{ first_name }} !</h1>
    <p>Votre email est {{ email }}</p>
</body>
</html>
```

## Utilisation dans le code

### Exemple 1 : Envoyer un email simple

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import get_session
from app.services.email_service import get_resend_service

@router.post("/send-notification")
async def send_notification(email: str, db: Session = Depends(get_session)):
    resend = get_resend_service()

    result = await resend.send_email(
        to=email,
        subject="Nouvelle notification",
        html="<h1>Vous avez une nouvelle notification</h1>"
    )

    return {"success": True, "id": result.get("id")}
```

### Exemple 2 : Envoyer avec un template

```python
from app.routers.api_email import load_email_template

@router.post("/send-invitation")
async def send_invitation(
    siret: str,
    email: str,
    db: Session = Depends(get_session)
):
    # Récupérer les données de l'entreprise
    entreprise = db.query(SiretSummary).filter_by(siret=siret).first()

    # Charger le template
    html = load_email_template("invitation", {
        "siret": siret,
        "raison_sociale": entreprise.raison_sociale,
        "ville": entreprise.ville,
        "cp": entreprise.cp,
        "dashboard_url": "https://app.example.com/dashboard"
    })

    # Envoyer
    resend = get_resend_service()
    result = await resend.send_email(
        to=email,
        subject=f"Invitation électorale - {entreprise.raison_sociale}",
        html=html
    )

    return {"success": True}
```

### Exemple 3 : Envoyer en batch

```python
from app.services.email_service import get_resend_service

@router.post("/send-batch")
async def send_batch_notifications(emails: List[str]):
    resend = get_resend_service()

    batch_emails = [
        {
            "to": email,
            "subject": "Notification importante",
            "html": "<h1>Message important</h1>"
        }
        for email in emails
    ]

    result = await resend.send_batch_emails(batch_emails)
    return result
```

## Monitoring et debug

### Vérifier les logs d'emails

Via l'API :
```bash
curl http://localhost:8000/api/email/logs?limit=10
```

Via la base de données :
```sql
SELECT * FROM email_logs ORDER BY created_at DESC LIMIT 10;
```

### Tester l'envoi d'emails

```bash
curl -X POST "http://localhost:8000/api/email/send-test?to=votre@email.com"
```

### Dashboard Resend

1. Connectez-vous sur [resend.com](https://resend.com)
2. Allez dans **Emails** pour voir tous les emails envoyés
3. Cliquez sur un email pour voir les détails (statut, ouvertures, clics)

## Limites et quotas

### Plan gratuit Resend
- 100 emails/jour
- 3 000 emails/mois
- Idéal pour le développement et les tests

### Plans payants
- **Pro** : 50 000 emails/mois à partir de $20/mois
- **Business** : Volumes personnalisés

Voir [resend.com/pricing](https://resend.com/pricing) pour plus de détails.

## Bonnes pratiques

1. **Validation des emails** : Utilisez `EmailStr` de Pydantic pour valider les adresses
2. **Gestion d'erreurs** : Toujours gérer les exceptions `ResendEmailError`
3. **Logging** : Tous les emails sont automatiquement loggés dans `email_logs`
4. **Templates** : Utilisez des templates HTML pour la cohérence
5. **Rate limiting** : Attention aux limites de votre plan Resend
6. **Domaine vérifié** : En production, vérifiez toujours votre domaine

## Dépannage

### Erreur : "RESEND_API_KEY not configured"

Vérifiez que la variable d'environnement est définie :
```bash
echo $RESEND_API_KEY
```

### Erreur : "Email sending failed"

1. Vérifiez que votre clé API est valide
2. Vérifiez que vous n'avez pas dépassé vos quotas
3. Consultez les logs : `GET /api/email/logs?status=failed`

### Emails non reçus

1. Vérifiez les spams/courrier indésirable
2. En production, vérifiez que votre domaine est vérifié dans Resend
3. Consultez le dashboard Resend pour voir le statut de l'email

### Performance lente

- Utilisez `send_batch_emails()` pour envoyer plusieurs emails
- Vérifiez votre connexion réseau
- Consultez les temps de réponse dans les logs

## Migration de base de données

La table `email_logs` sera créée automatiquement au démarrage de l'application via SQLAlchemy.

Pour créer la table manuellement :

```python
from app.db import Base, engine
from app.models import EmailLog

# Créer toutes les tables
Base.metadata.create_all(bind=engine)
```

## Support

- Documentation Resend : [resend.com/docs](https://resend.com/docs)
- API Reference : [resend.com/docs/api-reference](https://resend.com/docs/api-reference)
- Support : [resend.com/support](https://resend.com/support)

## Changelog

### Version 1.0.0 (2024-11-16)
- ✅ Intégration initiale de Resend
- ✅ Service `ResendEmailService`
- ✅ Modèle `EmailLog` pour tracking
- ✅ API endpoints (`/api/email/*`)
- ✅ Templates d'emails (test, invitation, user_approved, user_registration_admin)
- ✅ Configuration via variables d'environnement
- ✅ Documentation complète
