import os
import gzip
import pickle
from pathlib import Path
from django.conf import settings

CACHE_DIR = Path(settings.BASE_DIR) / "var" / "stat_cache"

def _ensure_dir() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

def cache_path(scope: str, ym: str | None = None, y: int | None = None) -> Path:
    _ensure_dir()
    if scope == "month":
        return CACHE_DIR / f"month_{ym}.pkl.gz"
    if scope == "year":
        return CACHE_DIR / f"year_{int(y)}.pkl.gz"
    return CACHE_DIR / "all.pkl.gz"

def save_cache(path: Path, payload: dict) -> None:
    tmp = Path(str(path) + ".tmp")
    with gzip.open(tmp, "wb") as f:
        pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(tmp, path)  # atomické přepsání

def load_cache(path: Path) -> dict | None:
    if not path.exists():
        return None
    with gzip.open(path, "rb") as f:
        return pickle.load(f)