"""
Script pour réinitialiser le mot de passe d'un utilisateur.

Usage:
    python scripts/reset_user_password.py <email> [nouveau_mot_de_passe]

Si le mot de passe n'est pas fourni, un mot de passe aléatoire sera généré.

Exemples:
    python scripts/reset_user_password.py leyrat.quentin@gmail.com MyNewPassword123!
    python scripts/reset_user_password.py leyrat.quentin@gmail.com
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


def generate_secure_password(length=16):
    """Génère un mot de passe sécurisé aléatoire"""
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(random.choice(chars) for _ in range(length))


def reset_password(email: str, new_password: str = None):
    """
    Réinitialise le mot de passe d'un utilisateur.

    Args:
        email: L'email de l'utilisateur
        new_password: Le nouveau mot de passe (optionnel, généré si non fourni)

    Returns:
        True si succès, False sinon
    """
    session = SessionLocal()

    try:
        # Rechercher l'utilisateur
        user = session.query(User).filter(User.email == email).first()

        if not user:
            print(f"❌ Utilisateur non trouvé: {email}")
            return False

        # Générer un mot de passe si non fourni
        if not new_password:
            new_password = generate_secure_password()
            print(f"🔑 Mot de passe généré automatiquement")

        # Hacher le nouveau mot de passe
        user.hashed_password = hash_password(new_password)
        session.commit()

        print(f"\n✅ Mot de passe réinitialisé avec succès pour : {email}")
        print(f"   Nom: {user.full_name}")
        print(f"   Organisation: {user.organization or 'N/A'}")
        print(f"\n🔑 Nouveau mot de passe: {new_password}")
        print(f"\n⚠️  IMPORTANT : Communiquez ce mot de passe de manière sécurisée !")

        return True

    except Exception as e:
        print(f"❌ Erreur: {e}")
        session.rollback()
        return False
    finally:
        session.close()


def main():
    if len(sys.argv) < 2:
        print("❌ Usage: python scripts/reset_user_password.py <email> [nouveau_mot_de_passe]")
        print("\nExemples:")
        print("  python scripts/reset_user_password.py leyrat.quentin@gmail.com MyNewPassword123!")
        print("  python scripts/reset_user_password.py leyrat.quentin@gmail.com")
        sys.exit(1)

    email = sys.argv[1]
    new_password = sys.argv[2] if len(sys.argv) > 2 else None

    print(f"🔄 Réinitialisation du mot de passe pour : {email}")
    print("=" * 60)

    success = reset_password(email, new_password)

    if success:
        print("\n" + "=" * 60)
        print("✅ Opération terminée avec succès")
        sys.exit(0)
    else:
        print("\n" + "=" * 60)
        print("❌ Échec de l'opération")
        sys.exit(1)


if __name__ == "__main__":
    main()
