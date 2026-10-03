"""Cache the installed-app index so scans skip the slow Store query.

Cache lives in %LOCALAPPDATA%\\Exorcist\\app_index.json with a TTL.
Corrupt/expired cache is ignored silently — scan just rebuilds it.
"""
from __future__ import annotations

import json
import os
import time

CACHE_TTL_SECONDS = 24 * 3600
CACHE_FILENAME = "app_index.json"


def cache_dir() -> str:
    base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    d = os.path.join(base, "Exorcist")
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        pass
    return d


def cache_path() -> str:
    return os.path.join(cache_dir(), CACHE_FILENAME)


def load_cached_names(max_age: int = CACHE_TTL_SECONDS) -> list[str] | None:
    try:
        with open(cache_path(), encoding="utf-8") as fh:
            payload = json.load(fh)
        if time.time() - float(payload.get("saved_at", 0)) > max_age:
            return None
        names = payload.get("names", [])
        return [str(n) for n in names] if isinstance(names, list) else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def save_cached_names(names: list[str]) -> None:
    try:
        with open(cache_path(), "w", encoding="utf-8") as fh:
            json.dump({"saved_at": time.time(), "names": names}, fh)
    except OSError:
        pass


def clear_cache() -> bool:
    try:
        os.remove(cache_path())
        return True
    except OSError:
        return False
