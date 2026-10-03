"""Scan tiers (quick/full) with Defender-style time estimates.

Estimates come from two sources:
1. perf history (%LOCALAPPDATA%\\Exorcist\\perf.json): last runs' throughput
2. live calibration: bytes walked in the first seconds of this run
Displayed as ranges ("1-3 min"), never fake precision.
"""
from __future__ import annotations

import json
import os
import time

HISTORY_FILE = "perf.json"


def _history_path() -> str:
    base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    d = os.path.join(base, "Exorcist")
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        pass
    return os.path.join(d, HISTORY_FILE)


def load_history() -> dict:
    try:
        with open(_history_path(), encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def record_run(scan_name: str, seconds: float, bytes_walked: int) -> None:
    if seconds <= 0:
        return
    hist = load_history()
    hist[scan_name] = {"seconds": seconds, "bytes": bytes_walked,
                       "mb_per_s": (bytes_walked / 1048576) / seconds,
                       "at": time.time()}
    try:
        with open(_history_path(), "w", encoding="utf-8") as fh:
            json.dump(hist, fh)
    except OSError:
        pass


def fmt_eta(seconds: float) -> str:
    if seconds < 0:
        seconds = 0
    if seconds < 60:
        return f"~{max(5, int(round(seconds / 5) * 5))} sec"
    lo = int(seconds * 0.7 / 30) * 30
    hi = int(seconds * 1.4 / 30 + 1) * 30
    if hi <= 60:
        return "~1 min"
    return f"{max(1, lo // 60)}-{max(1, hi // 60)} min"


def quote_estimate(scan_name: str, bytes_to_walk: int) -> str | None:
    """Return a pre-scan estimate string from history, or None if unknown."""
    entry = load_history().get(scan_name)
    if not entry or not entry.get("mb_per_s"):
        return None
    seconds = (bytes_to_walk / 1048576) / float(entry["mb_per_s"])
    return fmt_eta(seconds)


class Calibrator:
    """Live throughput tracker: feed bytes, read ETA for the remainder."""

    def __init__(self, total_bytes: int):
        self.total = max(1, total_bytes)
        self.start = time.time()
        self.done = 0

    def add(self, n_bytes: int) -> None:
        self.done += n_bytes

    def eta(self) -> str:
        elapsed = max(0.5, time.time() - self.start)
        rate = self.done / elapsed  # bytes/sec
        if rate <= 0:
            return "calculating..."
        remain = max(0, self.total - self.done)
        return fmt_eta(remain / rate)
