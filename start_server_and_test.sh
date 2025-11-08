#!/bin/bash

echo "=============================================="
echo "🚀 Démarrage du serveur FastAPI"
echo "=============================================="
echo ""

# Vérifier si le serveur tourne déjà
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "⚠️  Un serveur tourne déjà sur le port 8000"
    echo ""
    read -p "Voulez-vous le tuer et redémarrer ? (o/N) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Oo]$ ]]; then
        echo "🔫 Arrêt du serveur existant..."
        kill $(lsof -t -i:8000) 2>/dev/null
        sleep 2
    else
        echo "❌ Annulé. Le serveur existant continue de tourner."
        echo ""
        echo "📍 Testez l'API ici :"
        echo "   http://localhost:8000/test-kpi"
        exit 0
    fi
fi

echo "📦 Vérification des dépendances Python..."
python -c "import fastapi, uvicorn" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ ERREUR: Les dépendances ne sont pas installées"
    echo ""
    echo "Installez-les avec :"
    echo "  pip install -r requirements.txt"
    echo ""
    exit 1
fi
echo "✅ Dépendances OK"
echo ""

echo "🚀 Démarrage du serveur..."
echo ""
echo "Le serveur va démarrer sur http://localhost:8000"
echo ""
echo "📍 Pages disponibles :"
echo "   🏠 Page d'accueil:      http://localhost:8000/"
echo "   🔍 Test API KPI:        http://localhost:8000/test-kpi"
echo "   📊 API directe:         http://localhost:8000/api/stats/enriched"
echo ""
echo "Pour arrêter le serveur : Ctrl+C"
echo "=============================================="
echo ""

# Démarrer le serveur
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
