-- Migration pour ajouter les champs d'authentification par email
-- Base de données : SQLite
-- Date : 2025-11-15
-- Description : Ajoute les champs email_verified, validation_token, validation_token_expiry,
--               reset_token, reset_token_expiry à la table users

-- Vérifier d'abord si les colonnes existent déjà (SQLite ne supporte pas IF NOT EXISTS pour ALTER TABLE)
-- Cette migration devra être exécutée manuellement ou via un script Python

-- 1. Ajouter le champ email_verified (indique si l'email a été vérifié)
ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT 0 NOT NULL;

-- 2. Ajouter le champ validation_token (token pour valider l'email)
ALTER TABLE users ADD COLUMN validation_token VARCHAR(255);

-- 3. Ajouter le champ validation_token_expiry (date d'expiration du token de validation)
ALTER TABLE users ADD COLUMN validation_token_expiry DATETIME;

-- 4. Ajouter le champ reset_token (token pour réinitialiser le mot de passe)
ALTER TABLE users ADD COLUMN reset_token VARCHAR(255);

-- 5. Ajouter le champ reset_token_expiry (date d'expiration du token de reset)
ALTER TABLE users ADD COLUMN reset_token_expiry DATETIME;

-- 6. Créer des index pour améliorer les performances
CREATE INDEX IF NOT EXISTS idx_users_validation_token ON users(validation_token);
CREATE INDEX IF NOT EXISTS idx_users_reset_token ON users(reset_token);

-- 7. Mettre à jour is_active à 0 par défaut pour les nouveaux utilisateurs
-- (nécessite validation email avant activation)
-- Note: Cela ne change pas les utilisateurs existants

-- Afficher un message de confirmation
SELECT 'Migration réussie : Champs email ajoutés à la table users' AS status;
