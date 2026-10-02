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

# Vendors / runtimes / generic folders that are not apps — skip orphan flag to avoid false positives.
# v0.1.1: expanded with drivers, package managers, dev runtimes seen in the wild.
ORPHAN_IGNORE = {
    "microsoft", "windows", "common files", "internet explorer", "windows nt",
    "package cache", "modem", "drivers", "intel", "nvidia", "amd", "realtek",
    "packages", "appdata", "local", "roaming", "temp", "tmp",
    "dell", "hp", "hewlett packard", "lenovo", "asus", "acer", "logitech",
    "chocolatey", "scoop", "winget", "pip", "npm", "yarn", "pnpm",
    "playwright", "ms playwright", "ms playwright go", "chromium", "ffmpeg",
    "node", "nodejs", "python", "docker", "git", "vscode", "cursor",
    "eclipse", "jetbrains", "maven", "gradle",
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


def looks_orphaned(folder_name: str, name_index: set[str], fuzzy_cutoff: float = 0.85) -> bool:
    """True if folder matches no installed app.

    Guards against false positives:
    - exact normalized match or significant-token match => installed
    - close fuzzy match (typos, 'Cursor' vs 'Cursor Inc') => installed
    - vendor/runtime ignore list => never orphan
    """
    from difflib import SequenceMatcher

    norm = normalize_app_name(folder_name)
    if not norm or norm in ORPHAN_IGNORE:
        return False
    if norm in name_index:
        return False
    toks = [t for t in norm.split() if len(t) >= 4]
    if not toks:
        return False
    if all(t not in name_index for t in toks):
        # fuzzy: 'mongodbcompass' vs 'mongodb compass' etc.
        for t in toks:
            for known in name_index:
                if len(known) < 4:
                    continue
                if SequenceMatcher(None, t, known).ratio() >= fuzzy_cutoff:
                    return False
                # substring either way catches 'playwright' in 'ms-playwright-go'
                if len(t) >= 5 and (t in known or known in t):
                    return False
        return True
    return False


def folder_has_live_exe(folder: str, max_files: int = 60) -> tuple[bool, str]:
    """Check top 2 levels for an .exe that looks alive.

    Returns (True, reason) if the folder should NOT be flagged:
    - an .exe modified recently, or
    - an .exe whose stem matches a running process.
    Shallow + capped so scans stay fast.
    """
    try:
        running: set[str] = set()
        try:
            import psutil  # optional but declared dep

            for p in psutil.process_iter(["name"]):
                n = (p.info.get("name") or "").lower()
                if n.endswith(".exe"):
                    n = n[:-4]
                if n:
                    running.add(n)
        except Exception:
            running = set()

        checked = 0
        for root, dirs, files in os.walk(folder):
            depth = root[len(folder):].count(os.sep)
            if depth > 2:
                dirs[:] = []
                continue
            for f in files:
                if not f.lower().endswith(".exe"):
                    continue
                checked += 1
                stem = f[:-4].lower()
                fp = os.path.join(root, f)
                try:
                    import time

                    age_days = (time.time() - os.stat(fp).st_mtime) / 86400
                    if age_days < 30:
                        return True, f"live exe {f} used {age_days:.0f}d ago"
                except OSError:
                    pass
                if stem in running:
                    return True, f"exe {f} is running now"
                if checked >= max_files:
                    return False, ""
        return False, ""
    except Exception:
        return False, ""


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
