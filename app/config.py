from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./papcse.db")
IS_SQLITE = DATABASE_URL.startswith("sqlite")

# Si True, la table siret_summary sera reconstruite automatiquement au démarrage
# si elle est vide. Mettre à False pour éviter les timeouts au démarrage en production.
AUTO_BUILD_SUMMARY_ON_STARTUP = os.getenv("AUTO_BUILD_SUMMARY_ON_STARTUP", "false").lower() == "true"

# Clé API OpenAI pour l'extraction automatique d'informations depuis les courriers PAP
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Modèle OpenAI à utiliser pour l'extraction (gpt-4o, gpt-4-turbo, etc.)
# gpt-4o est recommandé : bon équilibre performance/coût
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# Liste de modèles à essayer en ordre de priorité (fallback automatique)
# Si un modèle n'est pas accessible, le système essaiera automatiquement le suivant
OPENAI_MODEL_FALLBACK = [
    "gpt-4o",                    # Modèle standard GPT-4o
    "gpt-4o-2024-11-20",        # Version spécifique récente
    "gpt-4o-2024-08-06",        # Version août 2024
    "gpt-4o-2024-05-13",        # Version mai 2024
    "gpt-4o-mini",              # Version mini (plus économique)
    "gpt-4o-mini-2024-07-18",  # Version mini spécifique
    "gpt-4-turbo",              # GPT-4 Turbo
    "gpt-4-turbo-2024-04-09",  # Version spécifique Turbo
]
