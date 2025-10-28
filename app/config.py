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

    def add_directory(dir_like):
        if not dir_like:
            return
        dir_path = Path(dir_like).expanduser()
        directories.append(dir_path)

    search_name = "papcse.db"
    directories = []

    env_hint_dirs = []
    hints_env = os.getenv("DATABASE_SEARCH_PATHS")
    if hints_env:
        env_hint_dirs.extend(Path(p.strip()) for p in hints_env.split(os.pathsep) if p.strip())

    extra_env = {
        "DATABASE_PATH": os.getenv("DATABASE_PATH"),
        "DATABASE_FILE": os.getenv("DATABASE_FILE"),
    }
    for value in extra_env.values():
        if value:
            add_candidate(value)

    env_directories = {
        "DATABASE_DIR": os.getenv("DATABASE_DIR"),
        "RAILWAY_VOLUME_PATH": os.getenv("RAILWAY_VOLUME_PATH"),
    }
    for value in env_directories.values():
        if value:
            env_hint_dirs.append(Path(value))

    if raw_path:
        raw_candidate = Path(raw_path)
        if raw_candidate.name:
            search_name = raw_candidate.name
        if raw_candidate.is_absolute():
            add_candidate(raw_candidate)
            add_directory(raw_candidate.parent)
        else:
            # Préserver le comportement historique : d'abord le chemin tel quel
            add_candidate(raw_candidate)
            add_directory(raw_candidate.parent)
            add_candidate((BASE_DIR / raw_candidate).resolve())
            add_candidate((BASE_DIR / raw_candidate.name).resolve())
            add_directory((BASE_DIR / raw_candidate).resolve().parent)
            add_directory((BASE_DIR / raw_candidate.name).resolve().parent)
            cwd = Path.cwd()
            add_candidate((cwd / raw_candidate).resolve())
            add_candidate((cwd / raw_candidate.name).resolve())
            add_directory((cwd / raw_candidate).resolve().parent)
            add_directory((cwd / raw_candidate.name).resolve().parent)
    else:
        default_candidate = BASE_DIR / search_name
        add_candidate(default_candidate)
        add_directory(default_candidate.parent)

    # Ajouter quelques emplacements communs rencontrés sur les déploiements existants
    common_roots = [
        BASE_DIR,
        BASE_DIR / "app",
        BASE_DIR / "data",
        BASE_DIR.parent,
        BASE_DIR.parent / "data",
        Path.cwd(),
        Path.cwd() / "app",
        Path.cwd() / "data",
        Path("/app"),
        Path("/app/data"),
        Path("/data"),
    ]

    directories.extend(common_roots)
    directories.extend(env_hint_dirs)

    base_stem = Path(search_name).stem or search_name
    alt_names = {
        search_name,
        "papcse.db",
        "papcse.sqlite",
        "papcse.sqlite3",
    }
    if base_stem:
        alt_names.add(base_stem)
        alt_names.add(f"{base_stem}.db")
        alt_names.add(f"{base_stem}.sqlite")
        alt_names.add(f"{base_stem}.sqlite3")

    for directory in directories:
        if not directory:
            continue
        dir_path = Path(directory).expanduser()
        for name in alt_names:
            if not name:
                continue
            add_candidate(dir_path / name)
        if dir_path.exists() and base_stem:
            for pattern in [
                f"*{base_stem}*.db",
                f"*{base_stem}*.sqlite",
                f"*{base_stem}*.sqlite3",
            ]:
                for match in dir_path.glob(pattern):
                    if match.is_file():
                        add_candidate(match)

    # Éliminer les doublons tout en conservant l'ordre d'évaluation
    seen = set()
    ordered_candidates = []
    for candidate in candidates:
        if not candidate:
            continue
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
    if resolved_path.is_dir():
        resolved_path = resolved_path / "papcse.db"
    if not resolved_path.is_absolute():
        resolved_path = (BASE_DIR / resolved_path).resolve()

    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    url = url.set(database=str(resolved_path))
    DATABASE_URL = str(url)
