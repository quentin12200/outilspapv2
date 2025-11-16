"""
Module de service d'envoi d'emails pour l'authentification et la communication.

Ce module gère l'envoi des emails de :
- Validation de compte (inscription)
- Réinitialisation de mot de passe
- Bienvenue après validation

Configuration requise dans .env :
- RESEND_API_KEY : Clé API Resend (obligatoire)
- MAIL_DEFAULT_SENDER : Email d'envoi (ex: contact@pap-cse.org)
- MAIL_FROM_NAME : Nom de l'expéditeur (ex: PAP CSE Dashboard)
- APP_URL : URL de l'application (ex: https://app.pap-cse.org)
"""

import os
import logging
from typing import Optional

# Configuration du logger
logger = logging.getLogger(__name__)

# Configuration Resend depuis les variables d'environnement
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "contact@pap-cse.org")
MAIL_FROM_NAME = os.getenv("MAIL_FROM_NAME", "PAP CSE Dashboard")
APP_URL = os.getenv("APP_URL", "https://app.pap-cse.org")

# Import conditionnel de Resend
try:
    import resend
    resend.api_key = RESEND_API_KEY
    RESEND_AVAILABLE = True
except ImportError:
    RESEND_AVAILABLE = False
    logger.warning("Module 'resend' non installé. Installez-le avec: pip install resend")


def send_email(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: Optional[str] = None
) -> bool:
    """
    Envoie un email avec le contenu HTML et texte fourni via Resend API.

    Args:
        to_email: Adresse email du destinataire
        subject: Sujet de l'email
        html_content: Contenu HTML de l'email
        text_content: Contenu texte alternatif (optionnel)

    Returns:
        bool: True si l'envoi a réussi, False sinon
    """
    if not RESEND_AVAILABLE:
        logger.error("Resend n'est pas disponible. Installez-le avec: pip install resend")
        return False

    if not RESEND_API_KEY:
        logger.error("RESEND_API_KEY non configurée dans les variables d'environnement")
        return False

    try:
        # Préparer les paramètres de l'email
        params = {
            "from": f"{MAIL_FROM_NAME} <{MAIL_DEFAULT_SENDER}>",
            "to": [to_email],
            "subject": subject,
            "html": html_content,
        }

        # Ajouter le contenu texte si fourni
        if text_content:
            params["text"] = text_content

        # Envoyer l'email via Resend
        response = resend.Emails.send(params)

        logger.info(f"Email envoyé avec succès à {to_email} : {subject} (ID: {response.get('id', 'N/A')})")
        return True

    except Exception as e:
        logger.error(f"Erreur lors de l'envoi de l'email à {to_email} : {str(e)}")
        return False


def get_base_email_template(content: str) -> str:
    """
    Template HTML de base pour tous les emails.

    Args:
        content: Contenu HTML à insérer dans le template

    Returns:
        str: HTML complet avec le style et la structure
    """
    return f"""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PAP CSE Dashboard</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f4f4f4;
            margin: 0;
            padding: 0;
        }}
        .email-container {{
            max-width: 600px;
            margin: 20px auto;
            background-color: #ffffff;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .email-header {{
            background: linear-gradient(135deg, #d5001c 0%, #ab0015 100%);
            color: #ffffff;
            padding: 30px 20px;
            text-align: center;
        }}
        .email-header h1 {{
            margin: 0;
            font-size: 24px;
            font-weight: 600;
        }}
        .email-body {{
            padding: 40px 30px;
        }}
        .email-body h2 {{
            color: #d5001c;
            margin-top: 0;
            font-size: 20px;
        }}
        .email-body p {{
            margin: 15px 0;
            color: #555;
        }}
        .btn {{
            display: inline-block;
            padding: 14px 32px;
            background: linear-gradient(135deg, #d5001c 0%, #ab0015 100%);
            color: #ffffff !important;
            text-decoration: none;
            border-radius: 6px;
            font-weight: 600;
            margin: 20px 0;
            transition: transform 0.2s;
        }}
        .btn:hover {{
            transform: translateY(-2px);
        }}
        .info-box {{
            background-color: #f8f9fa;
            border-left: 4px solid #d5001c;
            padding: 15px;
            margin: 20px 0;
            border-radius: 4px;
        }}
        .warning-box {{
            background-color: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin: 20px 0;
            border-radius: 4px;
        }}
        .email-footer {{
            background-color: #f8f9fa;
            padding: 20px;
            text-align: center;
            font-size: 12px;
            color: #6c757d;
        }}
        .email-footer a {{
            color: #d5001c;
            text-decoration: none;
        }}
    </style>
</head>
<body>
    <div class="email-container">
        <div class="email-header">
            <h1>PAP CSE Dashboard</h1>
        </div>
        <div class="email-body">
            {content}
        </div>
        <div class="email-footer">
            <p>
                <strong>PAP CSE Dashboard</strong><br>
                Suivi ciblage PAP<br>
                <a href="{APP_URL}">{APP_URL}</a>
            </p>
            <p style="margin-top: 15px;">
                Cet email a été envoyé automatiquement. Merci de ne pas y répondre.
            </p>
        </div>
    </div>
</body>
</html>
"""


def send_account_validation_email(email: str, token: str, username: str) -> bool:
    """
    Envoie un email de validation de compte après inscription.

    Args:
        email: Adresse email du destinataire
        token: Token de validation unique
        username: Nom d'utilisateur (prénom + nom)

    Returns:
        bool: True si l'envoi a réussi, False sinon
    """
    validation_link = f"{APP_URL}/validate-account?token={token}"

    content = f"""
        <h2>Bienvenue sur le PAP CSE Dashboard ! 👋</h2>

        <p>Bonjour <strong>{username}</strong>,</p>

        <p>Merci de vous être inscrit sur le PAP CSE Dashboard. Pour activer votre compte et commencer à utiliser nos outils d'analyse, veuillez valider votre adresse email.</p>

        <div style="text-align: center; margin: 30px 0;">
            <a href="{validation_link}" class="btn">
                ✅ Valider mon compte
            </a>
        </div>

        <div class="info-box">
            <p style="margin: 0;"><strong>ℹ️ Ce lien est valide pendant 24 heures.</strong></p>
            <p style="margin: 8px 0 0 0;">Après validation, votre compte sera soumis à l'approbation d'un administrateur avant que vous puissiez accéder au dashboard.</p>
        </div>

        <p style="color: #6c757d; font-size: 14px; margin-top: 30px;">
            Si le bouton ne fonctionne pas, copiez et collez ce lien dans votre navigateur :<br>
            <a href="{validation_link}" style="color: #d5001c; word-break: break-all;">{validation_link}</a>
        </p>

        <p style="color: #6c757d; font-size: 14px; margin-top: 20px;">
            Si vous n'avez pas créé de compte, vous pouvez ignorer cet email.
        </p>
    """

    html = get_base_email_template(content)
    text = f"""
Bienvenue sur le PAP CSE Dashboard !

Bonjour {username},

Merci de vous être inscrit. Pour activer votre compte, veuillez cliquer sur le lien suivant :

{validation_link}

Ce lien est valide pendant 24 heures.

Après validation, votre compte sera soumis à l'approbation d'un administrateur.

Si vous n'avez pas créé de compte, vous pouvez ignorer cet email.

---
PAP CSE Dashboard
{APP_URL}
"""

    return send_email(
        to_email=email,
        subject="✅ Validez votre compte PAP CSE Dashboard",
        html_content=html,
        text_content=text
    )


def send_reset_password_email(email: str, token: str, username: str) -> bool:
    """
    Envoie un email de réinitialisation de mot de passe.

    Args:
        email: Adresse email du destinataire
        token: Token de réinitialisation unique
        username: Nom d'utilisateur (prénom + nom)

    Returns:
        bool: True si l'envoi a réussi, False sinon
    """
    reset_link = f"{APP_URL}/reset-password?token={token}"

    content = f"""
        <h2>Réinitialisation de votre mot de passe 🔒</h2>

        <p>Bonjour <strong>{username}</strong>,</p>

        <p>Vous avez demandé à réinitialiser votre mot de passe pour votre compte PAP CSE Dashboard.</p>

        <div style="text-align: center; margin: 30px 0;">
            <a href="{reset_link}" class="btn">
                🔑 Réinitialiser mon mot de passe
            </a>
        </div>

        <div class="warning-box">
            <p style="margin: 0;"><strong>⚠️ Ce lien est valide pendant 1 heure.</strong></p>
            <p style="margin: 8px 0 0 0;">Pour des raisons de sécurité, ce lien expire rapidement. Si vous ne réinitialisez pas votre mot de passe dans l'heure, vous devrez faire une nouvelle demande.</p>
        </div>

        <p style="color: #6c757d; font-size: 14px; margin-top: 30px;">
            Si le bouton ne fonctionne pas, copiez et collez ce lien dans votre navigateur :<br>
            <a href="{reset_link}" style="color: #d5001c; word-break: break-all;">{reset_link}</a>
        </p>

        <div class="info-box" style="margin-top: 30px;">
            <p style="margin: 0;"><strong>🛡️ Vous n'avez pas demandé cette réinitialisation ?</strong></p>
            <p style="margin: 8px 0 0 0;">Si vous n'êtes pas à l'origine de cette demande, vous pouvez ignorer cet email en toute sécurité. Votre mot de passe actuel reste inchangé.</p>
        </div>
    """

    html = get_base_email_template(content)
    text = f"""
Réinitialisation de votre mot de passe

Bonjour {username},

Vous avez demandé à réinitialiser votre mot de passe. Pour continuer, cliquez sur le lien suivant :

{reset_link}

Ce lien est valide pendant 1 heure.

Si vous n'avez pas demandé cette réinitialisation, vous pouvez ignorer cet email. Votre mot de passe actuel reste inchangé.

---
PAP CSE Dashboard
{APP_URL}
"""

    return send_email(
        to_email=email,
        subject="🔒 Réinitialisation de votre mot de passe PAP CSE",
        html_content=html,
        text_content=text
    )


def send_welcome_email(email: str, username: str) -> bool:
    """
    Envoie un email de bienvenue après validation du compte.

    Args:
        email: Adresse email du destinataire
        username: Nom d'utilisateur (prénom + nom)

    Returns:
        bool: True si l'envoi a réussi, False sinon
    """
    login_link = f"{APP_URL}/login"

    content = f"""
        <h2>Votre compte a été validé ! 🎉</h2>

        <p>Bonjour <strong>{username}</strong>,</p>

        <p>Excellente nouvelle ! Votre adresse email a été validée avec succès.</p>

        <div class="info-box">
            <p style="margin: 0;"><strong>📋 Prochaine étape : Approbation administrateur</strong></p>
            <p style="margin: 8px 0 0 0;">Votre compte est maintenant en attente d'approbation par un administrateur. Vous recevrez une notification par email dès que votre accès sera activé.</p>
        </div>

        <h3 style="color: #d5001c; margin-top: 30px;">🚀 Ce que vous pourrez faire une fois approuvé :</h3>

        <ul style="color: #555;">
            <li>📊 Consulter les statistiques détaillées des élections CSE</li>
            <li>🔍 Analyser les résultats par syndicat, région ou secteur</li>
            <li>📈 Visualiser les tendances et évolutions</li>
            <li>📥 Exporter les données pour vos analyses</li>
            <li>💬 Utiliser l'assistant IA pour vos questions</li>
        </ul>

        <div style="text-align: center; margin: 30px 0;">
            <a href="{login_link}" class="btn">
                🔐 Accéder à la page de connexion
            </a>
        </div>

        <p style="color: #6c757d; font-size: 14px; margin-top: 30px;">
            En attendant l'approbation, n'hésitez pas à préparer vos questions et à vous familiariser avec l'interface.
        </p>
    """

    html = get_base_email_template(content)
    text = f"""
Votre compte a été validé !

Bonjour {username},

Votre adresse email a été validée avec succès.

Prochaine étape : Votre compte est maintenant en attente d'approbation par un administrateur. Vous recevrez une notification dès que votre accès sera activé.

Ce que vous pourrez faire une fois approuvé :
- Consulter les statistiques détaillées des élections CSE
- Analyser les résultats par syndicat, région ou secteur
- Visualiser les tendances et évolutions
- Exporter les données pour vos analyses
- Utiliser l'assistant IA pour vos questions

Page de connexion : {login_link}

---
PAP CSE Dashboard
{APP_URL}
"""

    return send_email(
        to_email=email,
        subject="🎉 Votre compte PAP CSE a été validé",
        html_content=html,
        text_content=text
    )


def send_account_approved_email(email: str, username: str) -> bool:
    """
    Envoie un email de notification d'approbation du compte par un admin.

    Args:
        email: Adresse email du destinataire
        username: Nom d'utilisateur (prénom + nom)

    Returns:
        bool: True si l'envoi a réussi, False sinon
    """
    login_link = f"{APP_URL}/login"

    content = f"""
        <h2>Votre compte a été approuvé ! 🎊</h2>

        <p>Bonjour <strong>{username}</strong>,</p>

        <p>Nous avons le plaisir de vous informer que votre compte PAP CSE Dashboard a été approuvé par un administrateur.</p>

        <p><strong>Vous pouvez maintenant vous connecter et accéder à l'ensemble des fonctionnalités !</strong></p>

        <div style="text-align: center; margin: 30px 0;">
            <a href="{login_link}" class="btn">
                🔐 Se connecter maintenant
            </a>
        </div>

        <h3 style="color: #d5001c; margin-top: 30px;">🎯 Vous pouvez maintenant :</h3>

        <ul style="color: #555;">
            <li>📊 Accéder à l'ensemble des fonctionnalités du dashboard</li>
            <li>📈 Consulter les données et statistiques en temps réel</li>
            <li>🔍 Utiliser tous les outils d'analyse disponibles</li>
            <li>💬 Interagir avec l'assistant IA pour vos questions</li>
            <li>📥 Exporter les données pour vos analyses</li>
        </ul>

        <div class="info-box" style="margin-top: 30px;">
            <p style="margin: 0;"><strong>💡 Besoin d'aide ?</strong></p>
            <p style="margin: 8px 0 0 0;">N'hésitez pas à explorer l'interface et à utiliser toutes les fonctionnalités disponibles. L'assistant IA est là pour vous aider !</p>
        </div>
    """

    html = get_base_email_template(content)
    text = f"""
Votre compte a été approuvé !

Bonjour {username},

Nous avons le plaisir de vous informer que votre compte PAP CSE Dashboard a été approuvé par un administrateur.

Vous pouvez maintenant vous connecter et accéder à l'ensemble des fonctionnalités !

Se connecter : {login_link}

Vous pouvez maintenant :
- Accéder à l'ensemble des fonctionnalités du dashboard
- Consulter les données et statistiques en temps réel
- Utiliser tous les outils d'analyse disponibles
- Interagir avec l'assistant IA
- Exporter les données pour vos analyses

---
PAP CSE Dashboard
{APP_URL}
"""

    return send_email(
        to_email=email,
        subject="🎊 Votre compte PAP CSE a été approuvé",
        html_content=html,
        text_content=text
    )
