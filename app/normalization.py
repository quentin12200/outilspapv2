import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

_DATA_PATH = Path(__file__).resolve().parent / "static" / "fd_aliases.json"


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _normalize_key(value: str) -> str:
    if not value:
        return ""
    value = _strip_accents(value)
    value = value.upper()
    value = re.sub(r"[^A-Z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


@lru_cache(maxsize=1)
def _alias_map() -> dict[str, str]:
    if not _DATA_PATH.exists():
        return {}
    with _DATA_PATH.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)
    mapping: dict[str, str] = {}
    for canonical, aliases in raw.items():
        canonical_clean = canonical.strip()
        norm_canonical = _normalize_key(canonical_clean)
        if norm_canonical:
            mapping[norm_canonical] = canonical_clean
        for alias in aliases:
            norm_alias = _normalize_key(alias)
            if norm_alias:
                mapping[norm_alias] = canonical_clean
    return mapping


def normalize_fd_label(value: str | None) -> str | None:
    if value is None:
        return None
    value_str = str(value).strip()
    if not value_str:
        return None
    norm = _normalize_key(value_str)
    if not norm:
        return value_str
    mapping = _alias_map()
    return mapping.get(norm, value_str)
