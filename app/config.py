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
    raw_path = url.database or ""
    candidates = []

    def add_candidate(path_like):
        if not path_like:
            return
        path_obj = Path(path_like).expanduser()
        candidates.append(path_obj)

    if raw_path:
        raw_candidate = Path(raw_path)
        if raw_candidate.is_absolute():
            add_candidate(raw_candidate)
        else:
            # Préserver le comportement historique : d'abord le chemin tel quel
            add_candidate(raw_candidate)
            add_candidate((BASE_DIR / raw_candidate).resolve())
            add_candidate((BASE_DIR / raw_candidate.name).resolve())
            cwd = Path.cwd()
            add_candidate((cwd / raw_candidate).resolve())
            add_candidate((cwd / raw_candidate.name).resolve())
    else:
        add_candidate(BASE_DIR / "papcse.db")

    # Éliminer les doublons tout en conservant l'ordre d'évaluation
    seen = set()
    ordered_candidates = []
    for candidate in candidates:
        try:
            key = candidate.resolve()
        except FileNotFoundError:
            key = candidate
        if key in seen:
            continue
        ordered_candidates.append(candidate)
        seen.add(key)

    if not ordered_candidates:
        ordered_candidates.append(BASE_DIR / "papcse.db")

    resolved_path = next((c for c in ordered_candidates if c.exists()), ordered_candidates[0])
    resolved_path = resolved_path.expanduser()
    if not resolved_path.is_absolute():
        resolved_path = (BASE_DIR / resolved_path).resolve()

    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    url = url.set(database=str(resolved_path))
    DATABASE_URL = str(url)
