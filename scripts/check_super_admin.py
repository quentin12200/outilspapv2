"""
Script pour vérifier et réinitialiser le compte super admin.

Usage:
    python scripts/check_super_admin.py
"""

import sys
import os
import string
import random

# Ajouter le répertoire parent au PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import SessionLocal
from app.models import User
from app.user_auth import hash_password


def check_and_reset_super_admin():
    """
    Vérifie le compte super admin et propose de réinitialiser le mot de passe.
    """
    super_admin_email = os.getenv("SUPER_ADMIN_EMAIL", "leyrat.quentin@gmail.com")

    session = SessionLocal()

    try:
        # Rechercher le super admin
        user = session.query(User).filter(User.email == super_admin_email).first()

        if not user:
            print(f"❌ Compte super admin non trouvé : {super_admin_email}")
            print("\n📝 Création du compte...")

            # Générer un mot de passe sécurisé
            chars = string.ascii_letters + string.digits + "!@#$%^&*-_"
            new_password = ''.join(random.choice(chars) for _ in range(16))

            # Créer le super admin
            user = User(
                email=super_admin_email,
                hashed_password=hash_password(new_password),
                first_name="Quentin",
                last_name="Leyrat",
                phone=None,
                organization="CGT",
                fd=None,
                ud=None,
                region=None,
                responsibility="Super Administrateur",
                registration_reason="Compte super admin créé manuellement",
                registration_ip="127.0.0.1",
                is_approved=True,
                is_active=True,
                role="admin"
            )

            session.add(user)
            session.commit()

            print(f"\n✅ Compte super admin créé avec succès !")
            print(f"\n" + "=" * 70)
            print(f"📧 Email : {super_admin_email}")
            print(f"🔑 Mot de passe : {new_password}")
            print(f"=" * 70)
            print(f"\n⚠️  IMPORTANT : Notez ce mot de passe dans un endroit sûr !")
            print(f"    Vous pouvez maintenant vous connecter sur /login")

            return True

        # Le super admin existe
        print(f"✅ Compte super admin trouvé : {super_admin_email}")
        print(f"   Nom : {user.first_name} {user.last_name}")
        print(f"   Organisation : {user.organization or 'N/A'}")
        print(f"   Role : {user.role}")
        print(f"   Approuvé : {'Oui' if user.is_approved else 'Non'}")
        print(f"   Actif : {'Oui' if user.is_active else 'Non'}")

        # Vérifier que tout est correct
        if user.role != "admin" or not user.is_approved or not user.is_active:
            print(f"\n⚠️  Le compte a des paramètres incorrects. Correction en cours...")
            user.role = "admin"
            user.is_approved = True
            user.is_active = True
            session.commit()
            print(f"✅ Compte corrigé !")

        print(f"\n❓ Voulez-vous réinitialiser le mot de passe ? (o/n) : ", end="")
        response = input().strip().lower()

        if response in ['o', 'oui', 'y', 'yes']:
            # Générer un nouveau mot de passe
            chars = string.ascii_letters + string.digits + "!@#$%^&*-_"
            new_password = ''.join(random.choice(chars) for _ in range(16))

            user.hashed_password = hash_password(new_password)
            session.commit()

            print(f"\n✅ Mot de passe réinitialisé avec succès !")
            print(f"\n" + "=" * 70)
            print(f"📧 Email : {super_admin_email}")
            print(f"🔑 Nouveau mot de passe : {new_password}")
            print(f"=" * 70)
            print(f"\n⚠️  IMPORTANT : Notez ce mot de passe dans un endroit sûr !")
            print(f"    Vous pouvez maintenant vous connecter sur /login")
        else:
            print(f"\n💡 Le compte est opérationnel.")
            print(f"    Si vous avez oublié le mot de passe, relancez ce script.")

        return True

    except Exception as e:
        print(f"❌ Erreur : {e}")
        import traceback
        traceback.print_exc()
        session.rollback()
        return False
    finally:
        session.close()


def main():
    print("=" * 70)
    print("🔍 Vérification du compte Super Administrateur")
    print("=" * 70)
    print()

    success = check_and_reset_super_admin()

    if success:
        print("\n" + "=" * 70)
        print("✅ Opération terminée avec succès")
        print("=" * 70)
        sys.exit(0)
    else:
        print("\n" + "=" * 70)
        print("❌ Échec de l'opération")
        print("=" * 70)
        sys.exit(1)


if __name__ == "__main__":
    main()
