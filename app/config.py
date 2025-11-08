from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./papcse.db")
IS_SQLITE = DATABASE_URL.startswith("sqlite")

# Si True, la table siret_summary sera reconstruite automatiquement au démarrage
# si elle est vide. Mettre à False pour éviter les timeouts au démarrage en production.
AUTO_BUILD_SUMMARY_ON_STARTUP = os.getenv("AUTO_BUILD_SUMMARY_ON_STARTUP", "false").lower() == "true"
