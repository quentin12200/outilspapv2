from dotenv import load_dotenv
import os
from pathlib import Path

from sqlalchemy.engine.url import make_url

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

raw_database_url = os.getenv("DATABASE_URL")
if raw_database_url:
    DATABASE_URL = raw_database_url
else:
    default_sqlite_path = BASE_DIR / "papcse.db"
    DATABASE_URL = f"sqlite:///{default_sqlite_path}"

url = make_url(DATABASE_URL)
IS_SQLITE = url.get_backend_name() == "sqlite"

if IS_SQLITE:
    database_path = Path(url.database or "").expanduser()
    if not database_path.is_absolute():
        database_path = (BASE_DIR / database_path).resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    url = url.set(database=str(database_path))
    DATABASE_URL = str(url)
