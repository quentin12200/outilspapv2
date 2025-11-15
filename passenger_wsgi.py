#!/usr/bin/env python3
# passenger_wsgi.py
# Point d'entrée WSGI pour Passenger (cPanel/o2switch)

import os
import sys

# Ajouter le répertoire de l'application au PYTHONPATH
INTERP = os.path.join(os.environ['HOME'], '.local', 'share', 'virtualenvs', 'outilspapv2', 'bin', 'python3')
if sys.executable != INTERP:
    os.execl(INTERP, INTERP, *sys.argv)

# Ajouter le répertoire actuel au path
sys.path.insert(0, os.path.dirname(__file__))

# Charger les variables d'environnement depuis .env
from dotenv import load_dotenv
load_dotenv()

# Importer l'application FastAPI
from app.main import app as application

# Pour Passenger, l'application doit s'appeler 'application'
# FastAPI est compatible ASGI, mais Passenger peut le gérer via uvicorn.workers
