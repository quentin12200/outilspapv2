#!/usr/bin/env python3
"""
Script de test pour vérifier l'intégration Resend
Usage: python test_resend.py votre-email@exemple.com
"""

import os
import sys
import asyncio
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

async def test_resend():
    """Test d'envoi d'email via Resend"""

    # Vérifier les variables d'environnement
    api_key = os.getenv("RESEND_API_KEY")
    from_email = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev")

    print("=" * 60)
    print("🧪 TEST RESEND EMAIL SERVICE")
    print("=" * 60)

    print(f"\n📋 Configuration:")
    print(f"   RESEND_API_KEY: {'✅ Configuré' if api_key else '❌ Manquant'}")
    if api_key:
        print(f"   API Key: {api_key[:8]}...{api_key[-4:]}")
    print(f"   RESEND_FROM_EMAIL: {from_email}")

    if not api_key:
        print("\n❌ ERREUR: RESEND_API_KEY non configuré")
        print("   Sur Railway: Settings > Variables > Add RESEND_API_KEY")
        return False

    # Email de destination
    to_email = sys.argv[1] if len(sys.argv) > 1 else None
    if not to_email:
        print("\n❌ ERREUR: Email de destination manquant")
        print("   Usage: python test_resend.py votre-email@exemple.com")
        return False

    print(f"\n📧 Test d'envoi:")
    print(f"   De: {from_email}")
    print(f"   À: {to_email}")

    try:
        # Importer le service
        from app.services.email_service import ResendEmailService

        # Initialiser le service
        service = ResendEmailService()

        # Envoyer un email de test
        result = await service.send_email(
            to=to_email,
            subject="🧪 Test Resend - PAP/CSE",
            html="""
            <html>
                <body style="font-family: Arial, sans-serif; padding: 20px;">
                    <h1 style="color: #4CAF50;">✅ Email de test Resend</h1>
                    <p>Si vous recevez cet email, l'intégration Resend fonctionne correctement !</p>
                    <hr>
                    <p style="color: #666; font-size: 12px;">
                        Envoyé depuis PAP/CSE - Tableau de bord<br>
                        Domaine: pap-cse.org<br>
                        Service: Resend API
                    </p>
                </body>
            </html>
            """,
            from_email=from_email
        )

        print(f"\n✅ SUCCESS!")
        print(f"   Email ID: {result.get('id')}")
        print(f"   Message: {result.get('message')}")

        print("\n📬 Vérifiez votre boîte email (et spam) pour l'email de test")
        print("   Dashboard Resend: https://resend.com/emails")

        return True

    except Exception as e:
        print(f"\n❌ ERREUR lors de l'envoi:")
        print(f"   {type(e).__name__}: {str(e)}")

        # Diagnostics supplémentaires
        if "401" in str(e) or "Unauthorized" in str(e):
            print("\n💡 Diagnostic: Clé API invalide")
            print("   → Vérifiez votre clé API sur https://resend.com/api-keys")
        elif "403" in str(e) or "Forbidden" in str(e):
            print("\n💡 Diagnostic: Domaine non vérifié")
            print("   → Vérifiez que pap-cse.org est vérifié sur https://resend.com/domains")
        elif "Domain not found" in str(e):
            print("\n💡 Diagnostic: Email expéditeur non autorisé")
            print(f"   → Utilisez un email du domaine vérifié: xxx@pap-cse.org")
            print(f"   → Ou utilisez: onboarding@resend.dev pour les tests")

        return False

if __name__ == "__main__":
    success = asyncio.run(test_resend())
    sys.exit(0 if success else 1)
