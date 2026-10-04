"""Install watcher: fingerprint diff without a background service.

Each `scan` saves the installed-app name set to
%LOCALAPPDATA%\\Exorcist\\snapshot.json. The next scan diffs it:
apps present before but gone now are reported with their leftover
paths (matched from the current orphan findings).
"""
from __future__ import annotations

import json
import os
import time


def snapshot_path() -> str:
    base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    d = os.path.join(base, "Exorcist")
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        pass
    return os.path.join(d, "snapshot.json")


def load_snapshot() -> tuple[set[str], float]:
    try:
        with open(snapshot_path(), encoding="utf-8") as fh:
            data = json.load(fh)
        names = data.get("names", [])
        return set(names), float(data.get("at", 0))
    except (OSError, ValueError, TypeError, AttributeError):
        return set(), 0.0


def save_snapshot(names: set[str]) -> None:
    try:
        with open(snapshot_path(), "w", encoding="utf-8") as fh:
            json.dump({"at": time.time(), "names": sorted(names)}, fh)
    except OSError:
        pass


def vanished_apps(current: set[str]) -> tuple[set[str], float]:
    """Return (names gone since last scan, last scan time). First run: empty."""
    previous, at = load_snapshot()
    if not previous:
        return set(), 0.0
    return previous - current, at
