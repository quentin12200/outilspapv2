#!/bin/bash
# Script pour obtenir le SHA256 de la base de données
# Usage: ./scripts/get_db_sha256.sh

DB_FILE="pap.db"

if [ ! -f "$DB_FILE" ]; then
    echo "❌ Fichier $DB_FILE introuvable"
    echo "   Assurez-vous d'être à la racine du projet"
    exit 1
fi

echo "📊 Calcul du SHA256 pour $DB_FILE..."
echo ""

if command -v sha256sum &> /dev/null; then
    HASH=$(sha256sum "$DB_FILE" | awk '{print $1}')
elif command -v shasum &> /dev/null; then
    HASH=$(shasum -a 256 "$DB_FILE" | awk '{print $1}')
else
    echo "❌ Aucun outil SHA256 trouvé (sha256sum ou shasum)"
    exit 1
fi

echo "✅ SHA256: $HASH"
echo ""
echo "📋 Variable d'environnement Railway:"
echo "   DB_SHA256=$HASH"
echo ""
echo "💡 Ajoutez cette variable dans Railway → Variables"
