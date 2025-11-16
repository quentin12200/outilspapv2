#!/usr/bin/env python3
"""
Script de test pour le système d'envoi d'emails.

Ce script permet de tester :
- La connexion SMTP
- L'envoi d'emails de validation
- L'envoi d'emails de reset de mot de passe
- L'envoi d'emails de bienvenue

Usage:
    python test_email.py
"""

import os
import sys
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, str(Path(__file__).parent))

# Charger les variables d'environnement
from dotenv import load_dotenv
load_dotenv()

from app.email_service import (
    send_account_validation_email,
    send_reset_password_email,
    send_welcome_email,
    send_account_approved_email,
    test_smtp_connection,
    MAIL_SERVER,
    MAIL_PORT,
    MAIL_USE_SSL,
    MAIL_USERNAME,
    MAIL_DEFAULT_SENDER,
    APP_URL
)


def print_header():
    """Affiche l'en-tête du script"""
    print("=" * 70)
    print("🧪 SCRIPT DE TEST - SYSTÈME D'ENVOI D'EMAILS")
    print("=" * 70)
    print()


def print_config():
    """Affiche la configuration SMTP actuelle"""
    print("📋 Configuration SMTP actuelle :")
    print(f"  • Serveur       : {MAIL_SERVER}")
    print(f"  • Port          : {MAIL_PORT}")
    print(f"  • SSL           : {MAIL_USE_SSL}")
    print(f"  • Utilisateur   : {MAIL_USERNAME}")
    print(f"  • Expéditeur    : {MAIL_DEFAULT_SENDER}")
    print(f"  • URL App       : {APP_URL}")

    # Vérifier que le mot de passe est configuré
    if not os.getenv("MAIL_PASSWORD"):
        print()
        print("⚠️  ATTENTION : MAIL_PASSWORD n'est pas configuré dans .env")
        print("   L'envoi d'emails ne fonctionnera pas sans mot de passe.")

    print()


def test_connection():
    """Test de connexion SMTP"""
    print("\n" + "=" * 70)
    print("🔌 TEST 1 : Connexion SMTP")
    print("=" * 70)

    success, message = test_smtp_connection()
    print(message)

    if not success:
        print()
        print("💡 Conseils de dépannage :")
        print("  1. Vérifiez que MAIL_SERVER et MAIL_PORT sont corrects")
        print("  2. Vérifiez que MAIL_USERNAME et MAIL_PASSWORD sont corrects")
        print("  3. Vérifiez que MAIL_USE_SSL est configuré correctement")
        print("     - SSL (port 465) : MAIL_USE_SSL=True")
        print("     - STARTTLS (port 587) : MAIL_USE_SSL=False, MAIL_USE_TLS=True")
        print("  4. Vérifiez que votre pare-feu autorise la connexion sortante")
        return False

    return True


def test_validation_email():
    """Test d'envoi d'email de validation"""
    print("\n" + "=" * 70)
    print("📧 TEST 2 : Email de validation de compte")
    print("=" * 70)

    email = input("\n📮 Email destinataire (appuyez sur Entrée pour annuler) : ").strip()

    if not email:
        print("❌ Test annulé")
        return

    username = input("👤 Nom de l'utilisateur (défaut: 'Test User') : ").strip() or "Test User"
    token = "test-token-validation-123456789"

    print(f"\n📤 Envoi de l'email de validation à {email}...")

    success = send_account_validation_email(
        email=email,
        token=token,
        username=username
    )

    if success:
        print(f"✅ Email de validation envoyé avec succès à {email}")
        print(f"🔗 Lien de validation (pour test) : {APP_URL}/auth/validate-account?token={token}")
    else:
        print(f"❌ Échec de l'envoi de l'email de validation")


def test_reset_email():
    """Test d'envoi d'email de reset de mot de passe"""
    print("\n" + "=" * 70)
    print("🔒 TEST 3 : Email de réinitialisation de mot de passe")
    print("=" * 70)

    email = input("\n📮 Email destinataire (appuyez sur Entrée pour annuler) : ").strip()

    if not email:
        print("❌ Test annulé")
        return

    username = input("👤 Nom de l'utilisateur (défaut: 'Test User') : ").strip() or "Test User"
    token = "test-token-reset-123456789"

    print(f"\n📤 Envoi de l'email de reset à {email}...")

    success = send_reset_password_email(
        email=email,
        token=token,
        username=username
    )

    if success:
        print(f"✅ Email de reset envoyé avec succès à {email}")
        print(f"🔗 Lien de reset (pour test) : {APP_URL}/reset-password?token={token}")
    else:
        print(f"❌ Échec de l'envoi de l'email de reset")


def test_welcome_email():
    """Test d'envoi d'email de bienvenue"""
    print("\n" + "=" * 70)
    print("🎉 TEST 4 : Email de bienvenue")
    print("=" * 70)

    email = input("\n📮 Email destinataire (appuyez sur Entrée pour annuler) : ").strip()

    if not email:
        print("❌ Test annulé")
        return

    username = input("👤 Nom de l'utilisateur (défaut: 'Test User') : ").strip() or "Test User"

    print(f"\n📤 Envoi de l'email de bienvenue à {email}...")

    success = send_welcome_email(
        email=email,
        username=username
    )

    if success:
        print(f"✅ Email de bienvenue envoyé avec succès à {email}")
    else:
        print(f"❌ Échec de l'envoi de l'email de bienvenue")


def test_approved_email():
    """Test d'envoi d'email d'approbation"""
    print("\n" + "=" * 70)
    print("🎊 TEST 5 : Email d'approbation de compte")
    print("=" * 70)

    email = input("\n📮 Email destinataire (appuyez sur Entrée pour annuler) : ").strip()

    if not email:
        print("❌ Test annulé")
        return

    username = input("👤 Nom de l'utilisateur (défaut: 'Test User') : ").strip() or "Test User"

    print(f"\n📤 Envoi de l'email d'approbation à {email}...")

    success = send_account_approved_email(
        email=email,
        username=username
    )

    if success:
        print(f"✅ Email d'approbation envoyé avec succès à {email}")
    else:
        print(f"❌ Échec de l'envoi de l'email d'approbation")


def show_menu():
    """Affiche le menu principal"""
    print("\n" + "=" * 70)
    print("📋 MENU PRINCIPAL")
    print("=" * 70)
    print()
    print("  1. Tester la connexion SMTP")
    print("  2. Envoyer un email de validation de compte")
    print("  3. Envoyer un email de réinitialisation de mot de passe")
    print("  4. Envoyer un email de bienvenue")
    print("  5. Envoyer un email d'approbation de compte")
    print("  6. Exécuter tous les tests (avec email)")
    print("  0. Quitter")
    print()


def run_all_tests():
    """Exécute tous les tests"""
    print("\n" + "=" * 70)
    print("🚀 EXÉCUTION DE TOUS LES TESTS")
    print("=" * 70)

    email = input("\n📮 Email destinataire pour tous les tests : ").strip()

    if not email:
        print("❌ Tests annulés - email requis")
        return

    username = input("👤 Nom de l'utilisateur (défaut: 'Test User') : ").strip() or "Test User"

    # Test 1 : Connexion
    if not test_connection():
        print("\n⚠️  La connexion SMTP a échoué. Arrêt des tests.")
        return

    # Test 2 : Validation
    print("\n📧 Test 2/5 : Email de validation...")
    send_account_validation_email(email, "test-token-123", username)

    # Test 3 : Reset
    print("🔒 Test 3/5 : Email de reset...")
    send_reset_password_email(email, "test-token-456", username)

    # Test 4 : Bienvenue
    print("🎉 Test 4/5 : Email de bienvenue...")
    send_welcome_email(email, username)

    # Test 5 : Approbation
    print("🎊 Test 5/5 : Email d'approbation...")
    send_account_approved_email(email, username)

    print("\n✅ Tous les tests sont terminés !")
    print(f"📬 Vérifiez la boîte de réception de {email}")


def main():
    """Fonction principale"""
    print_header()
    print_config()

    while True:
        show_menu()

        try:
            choice = input("👉 Votre choix : ").strip()

            if choice == "0":
                print("\n👋 Au revoir !\n")
                break
            elif choice == "1":
                test_connection()
            elif choice == "2":
                test_validation_email()
            elif choice == "3":
                test_reset_email()
            elif choice == "4":
                test_welcome_email()
            elif choice == "5":
                test_approved_email()
            elif choice == "6":
                run_all_tests()
            else:
                print("❌ Choix invalide. Veuillez saisir un nombre entre 0 et 6.")

        except KeyboardInterrupt:
            print("\n\n👋 Interruption - Au revoir !\n")
            break
        except Exception as e:
            print(f"\n❌ Erreur inattendue : {str(e)}\n")


if __name__ == "__main__":
    main()
