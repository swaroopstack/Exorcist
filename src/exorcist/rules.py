"""Classification rules: orphan vs temp/cache + blocklist."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

from .installed import normalize_app_name

# Absolute paths that must NEVER be suggested for deletion.
BLOCKLIST_PREFIXES = [
    r"c:\windows",
    r"c:\boot",
    r"c:\$recycle.bin",
    r"c:\system volume information",
    r"c:\program files\windows",
    r"c:\program files (x86)\windows",
]

# Publishers / generic folders that are not apps — skip orphan flag to avoid false positives.
ORPHAN_IGNORE = {
    "microsoft", "windows", "common files", "internet explorer", "windows nt",
    "package cache", "modem", "drivers", "intel", "nvidia", "amd", "realtek",
    "packages", "appdata", "local", "roaming", "temp", "tmp",
}

JUNK_PATTERNS = [".tmp", ".log", ".bak", ".old", ".dmp", "thumbs.db", "desktop.ini"]


@dataclass
class Finding:
    path: str
    size_bytes: int
    age_days: float
    kind: str  # orphan | temp | cache | log | installer | recycle
    reason: str
    risk: str  # Safe | Review | Skip


def is_blocklisted(path: str) -> bool:
    p = os.path.normpath(path).lower()
    return any(p == b or p.startswith(b + os.sep) for b in BLOCKLIST_PREFIXES)


def looks_orphaned(folder_name: str, name_index: set[str]) -> bool:
    norm = normalize_app_name(folder_name)
    if not norm or norm in ORPHAN_IGNORE:
        return False
    if norm in name_index:
        return False
    # token match: all significant tokens missing => orphan
    toks = [t for t in norm.split() if len(t) >= 4]
    if not toks:
        return False
    return all(t not in name_index for t in toks)


def candidate_roots() -> dict[str, str]:
    """-kind- -> absolute path. Missing dirs are filtered by caller."""
    local = os.environ.get("LOCALAPPDATA", "")
    roaming = os.environ.get("APPDATA", "")
    windir = os.environ.get("WINDIR", r"C:\Windows")
    tmp = os.environ.get("TEMP", "")
    return {
        "roaming": roaming,
        "local": local,
        "programdata": r"C:\ProgramData",
        "temp_user": tmp,
        "temp_win": os.path.join(windir, "Temp"),
        "update_cache": os.path.join(windir, "SoftwareDistribution", "Download"),
        "delivery_opt": os.path.join(windir, "SoftwareDistribution", "DeliveryOptimization"),
        "prefetch": os.path.join(windir, "Prefetch"),
        "downloads": os.path.join(os.path.expanduser("~"), "Downloads"),
    }


def classify_stale_installer(path: str, age_days: float) -> Finding | None:
    low = path.lower()
    if low.endswith((".msi", ".exe", ".iso")) and "download" in low and age_days > 90:
        return None  # size filled by caller; handled in cli via make_finding
    return None


def make_finding(path: str, size: int, age: float, kind: str, reason: str) -> Finding:
    risk = "Safe" if kind in ("temp", "cache", "log", "recycle") else "Review"
    return Finding(path=path, size_bytes=size, age_days=age, kind=kind, reason=reason, risk=risk)


def junk_file_kind(filename: str) -> str | None:
    low = filename.lower()
    for pat in JUNK_PATTERNS:
        if low.endswith(pat):
            return "log" if pat in (".log", ".dmp") else "temp"
    return None
