from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./papcse.db")
IS_SQLITE = DATABASE_URL.startswith("sqlite")
