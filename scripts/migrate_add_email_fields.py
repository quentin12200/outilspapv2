#!/usr/bin/env python3
"""
Script de migration pour ajouter les champs d'authentification par email.

Ce script ajoute les colonnes suivantes à la table users :
- email_verified : Boolean (indique si l'email a été vérifié)
- validation_token : String (token pour valider l'email)
- validation_token_expiry : DateTime (expiration du token de validation)
- reset_token : String (token pour réinitialiser le mot de passe)
- reset_token_expiry : DateTime (expiration du token de reset)

Usage:
    python scripts/migrate_add_email_fields.py
"""

import os
import sys
import sqlite3
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()


def get_db_path():
    """Récupère le chemin de la base de données depuis DATABASE_URL"""
    database_url = os.getenv("DATABASE_URL", "sqlite:///./papcse.db")

    # Extraire le chemin du fichier depuis l'URL SQLite
    if database_url.startswith("sqlite:///"):
        db_path = database_url.replace("sqlite:///", "")
        # Si le chemin est relatif (./)
        if db_path.startswith("./"):
            db_path = db_path[2:]
        return db_path
    else:
        raise ValueError(f"Format d'URL de base de données non supporté : {database_url}")


def column_exists(cursor, table_name, column_name):
    """Vérifie si une colonne existe dans une table"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns


def index_exists(cursor, index_name):
    """Vérifie si un index existe"""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name=?", (index_name,))
    return cursor.fetchone() is not None


def run_migration():
    """Exécute la migration"""
    print("=" * 70)
    print("🔄 MIGRATION : Ajout des champs d'authentification par email")
    print("=" * 70)
    print()

    # Récupérer le chemin de la base de données
    try:
        db_path = get_db_path()
        print(f"📁 Base de données : {db_path}")
    except Exception as e:
        print(f"❌ Erreur lors de la récupération du chemin de la base : {str(e)}")
        return False

    # Vérifier que le fichier existe
    if not os.path.exists(db_path):
        print(f"❌ Le fichier de base de données n'existe pas : {db_path}")
        return False

    # Connexion à la base de données
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        print("✅ Connexion à la base de données établie")
        print()
    except Exception as e:
        print(f"❌ Erreur de connexion à la base : {str(e)}")
        return False

    try:
        # Liste des colonnes à ajouter
        columns_to_add = [
            ("email_verified", "BOOLEAN DEFAULT 0 NOT NULL"),
            ("validation_token", "VARCHAR(255)"),
            ("validation_token_expiry", "DATETIME"),
            ("reset_token", "VARCHAR(255)"),
            ("reset_token_expiry", "DATETIME")
        ]

        # Ajouter chaque colonne si elle n'existe pas
        for col_name, col_type in columns_to_add:
            if column_exists(cursor, "users", col_name):
                print(f"⏭️  Colonne '{col_name}' existe déjà - ignorée")
            else:
                print(f"➕ Ajout de la colonne '{col_name}'...", end=" ")
                cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
                print("✅")

        print()

        # Créer les index
        indexes = [
            ("idx_users_validation_token", "users", "validation_token"),
            ("idx_users_reset_token", "users", "reset_token")
        ]

        for idx_name, table, column in indexes:
            if index_exists(cursor, idx_name):
                print(f"⏭️  Index '{idx_name}' existe déjà - ignoré")
            else:
                print(f"🔍 Création de l'index '{idx_name}'...", end=" ")
                cursor.execute(f"CREATE INDEX {idx_name} ON {table}({column})")
                print("✅")

        print()

        # Afficher les statistiques
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        print(f"📊 Nombre d'utilisateurs dans la base : {user_count}")

        if user_count > 0:
            print()
            print("⚠️  IMPORTANT : Les utilisateurs existants ont été migrés avec :")
            print("   - email_verified = False")
            print("   - validation_token = NULL")
            print()
            print("💡 Si vous voulez activer les comptes existants automatiquement,")
            print("   exécutez la requête suivante manuellement :")
            print()
            print("   UPDATE users SET email_verified = 1 WHERE is_active = 1;")
            print()

        # Valider les changements
        conn.commit()
        print("✅ Migration appliquée avec succès !")

        return True

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Erreur lors de la migration : {str(e)}")
        return False

    finally:
        conn.close()
        print()
        print("🔒 Connexion fermée")


def main():
    """Fonction principale"""
    success = run_migration()

    print()
    print("=" * 70)

    if success:
        print("✅ MIGRATION TERMINÉE AVEC SUCCÈS")
        print("=" * 70)
        print()
        print("📋 Prochaines étapes :")
        print("   1. Redémarrez l'application FastAPI")
        print("   2. Testez l'inscription avec validation email")
        print("   3. Vérifiez que les emails sont bien envoyés")
        print()
        return 0
    else:
        print("❌ ÉCHEC DE LA MIGRATION")
        print("=" * 70)
        print()
        print("💡 Vérifiez :")
        print("   - Que le chemin de la base de données est correct")
        print("   - Que vous avez les droits d'écriture sur le fichier")
        print("   - Que la base de données n'est pas corrompue")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())
