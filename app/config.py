from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = (
    os.getenv("DATABASE_URL")
    or os.getenv("SQLALCHEMY_DATABASE_URL")
    or os.getenv("RAILWAY_DATABASE_URL")
    or "sqlite:///./papcse.db"
)

IS_SQLITE = DATABASE_URL.startswith("sqlite")
