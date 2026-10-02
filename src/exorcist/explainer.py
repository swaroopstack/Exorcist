"""Explain a folder: local known-DB lookup with fuzzy fallback.

No network, no model. Returns (what, source) where source is
'known-db' or '' when unknown. v0.3 will add optional local-AI
behind the same return shape.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class KnownInfo:
    what: str
    belongs_to: str
    verdict: str  # keep | remove | review
    note: str


def _db_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "data", "known_folders.yaml")


@lru_cache(maxsize=1)
def load_db() -> dict[str, KnownInfo]:
    path = _db_path()
    try:
        import yaml  # declared dependency
    except ImportError:
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
    except OSError:
        return {}
    out: dict[str, KnownInfo] = {}
    for key, val in raw.items():
        if not isinstance(val, dict):
            continue
        try:
            out[str(key).lower()] = KnownInfo(
                what=str(val.get("what", "")),
                belongs_to=str(val.get("belongs_to", "")),
                verdict=str(val.get("verdict", "review")),
                note=str(val.get("note", "")),
            )
        except Exception:
            continue
    return out


def explain(folder_name: str) -> tuple[str, str, KnownInfo | None]:
    """Return (display_text, source, info|None) for a folder base name."""
    from .installed import normalize_app_name

    norm = normalize_app_name(folder_name)
    db = load_db()
    if not norm:
        return "Unknown folder", "", None
    if norm in db:
        info = db[norm]
        label = info.what
        if info.belongs_to and info.belongs_to.lower() not in label.lower():
            label = f"{label} ({info.belongs_to})"
        return label, "known-db", info
    # fuzzy: 'mongodbcompass' -> 'mongodbcompass' key without separator
    squashed = norm.replace(" ", "")
    for key, info in db.items():
        if key.replace(" ", "") == squashed:
            return info.what, "known-db", info
    return "Unknown — needs review", "", None
