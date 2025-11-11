"""
Script de migration pour créer la table users pour l'authentification utilisateur.

Cette migration ajoute un système d'inscription utilisateur avec validation admin :
- Les utilisateurs peuvent s'inscrire via /signup
- Les demandes doivent être approuvées par un administrateur
- Les utilisateurs approuvés peuvent se connecter via /login

Usage:
    python scripts/migrate_add_users_table.py
"""

import sqlite3
import os
import sys

# Chemin vers la base de données
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "papcse.db")


def table_exists(cursor, table_name):
    """Vérifie si une table existe dans la base"""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return cursor.fetchone() is not None


def create_users_table(cursor):
    """Crée la table users avec tous les champs nécessaires"""

    create_table_sql = """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,

        -- Identifiants
        email VARCHAR(255) UNIQUE NOT NULL,
        hashed_password VARCHAR(255) NOT NULL,

        -- Informations personnelles
        first_name VARCHAR(255) NOT NULL,
        last_name VARCHAR(255) NOT NULL,
        phone VARCHAR(20),

        -- Informations syndicales
        organization VARCHAR(255),
        fd VARCHAR(80),
        ud VARCHAR(80),
        region VARCHAR(100),
        responsibility VARCHAR(255),

        -- Statut du compte
        is_approved BOOLEAN DEFAULT 0 NOT NULL,
        is_active BOOLEAN DEFAULT 1 NOT NULL,
        role VARCHAR(20) DEFAULT 'user' NOT NULL,

        -- Timestamps
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        approved_at DATETIME,
        approved_by VARCHAR(255),
        last_login DATETIME,

        -- Métadonnées de la demande
        registration_reason TEXT,
        registration_ip VARCHAR(45)
    )
    """

    cursor.execute(create_table_sql)

    # Créer les index
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_users_is_approved ON users(is_approved)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_user_email_approved ON users(email, is_approved)"
    )


def main():
    if not os.path.exists(DB_PATH):
        print(f"❌ Base de données non trouvée : {DB_PATH}")
        print("   La table sera créée automatiquement au premier démarrage de l'application.")
        return

    print(f"📦 Connexion à la base de données : {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("\n🔍 Vérification de la table users...")

    if table_exists(cursor, "users"):
        print("  ✓ La table 'users' existe déjà")
        print("\n✓ Aucune migration nécessaire.")
    else:
        try:
            print("  ➕ Création de la table 'users'...")
            create_users_table(cursor)
            conn.commit()
            print("  ✅ Table 'users' créée avec succès")

            print("\n" + "=" * 60)
            print("📊 RÉSUMÉ DE LA MIGRATION")
            print("=" * 60)
            print("✅ Table users créée avec succès")
            print("✅ Index créés : idx_users_email, idx_users_is_approved, idx_user_email_approved")

            print("\n🎉 Migration réussie !")
            print("\n💡 Système d'inscription utilisateur activé :")
            print("   • Inscription : /signup")
            print("   • Connexion : /login")
            print("   • Déconnexion : /logout")
            print("   • Gestion admin : /admin (section demandes d'inscription)")

        except sqlite3.Error as e:
            print(f"  ❌ Erreur lors de la création de la table : {e}")
            conn.rollback()
            sys.exit(1)

    conn.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ ERREUR : {e}")
        sys.exit(1)
