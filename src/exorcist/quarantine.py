"""Quarantine fallback for machines with a disabled Recycle Bin.

When the bin is disabled, `send2trash` may permanently delete depending
on Windows config - unacceptable for this tool. Instead we move items to
%LOCALAPPDATA%\\Exorcist\\quarantine\\<timestamp>\\<name> with a manifest,
restorable via `exorcist restore`. Entries auto-purge after 30 days.
"""
from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import asdict, dataclass

RETENTION_DAYS = 30


@dataclass
class QuarantinedItem:
    original_path: str
    quarantine_path: str
    size_bytes: int
    moved_at: float
    kind: str = ""


def quarantine_root() -> str:
    base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    d = os.path.join(base, "Exorcist", "quarantine")
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        pass
    return d


def is_bin_disabled() -> tuple[bool, str]:
    """Check whether the Recycle Bin is disabled via policy registry.

    Returns (disabled, reason). Absent keys / non-Windows => not disabled.
    """
    try:
        import winreg
    except ImportError:
        return False, ""
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(hive,
                                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Explorer") as key:
                try:
                    val, _ = winreg.QueryValueEx(key, "NoRecycleFiles")
                    if int(val) == 1:
                        where = "HKCU" if hive == winreg.HKEY_CURRENT_USER else "HKLM"
                        return True, f"Recycle Bin disabled by policy ({where}\\...\\Explorer\\NoRecycleFiles=1)"
                except OSError:
                    continue
        except OSError:
            continue
    return False, ""


def _dir_size(path: str) -> int:
    total = 0
    if os.path.isfile(path):
        try:
            return os.path.getsize(path)
        except OSError:
            return 0
    for root, _, files in os.walk(path):
        for fn in files:
            try:
                total += os.path.getsize(os.path.join(root, fn))
            except OSError:
                continue
    return total


def quarantine_move(path: str, kind: str = "") -> tuple[bool, str]:
    """Move path into quarantine. Returns (ok, message)."""
    if not os.path.exists(path):
        return False, f"missing: {path}"
    stamp = time.strftime("%Y%m%d-%H%M%S")
    dest_dir = os.path.join(quarantine_root(), stamp)
    name = os.path.basename(path.rstrip(os.sep)) or "item"
    dest = os.path.join(dest_dir, name)
    # avoid collision inside the same second
    n = 1
    while os.path.exists(dest):
        n += 1
        dest = os.path.join(dest_dir, f"{name}-{n}")
    try:
        os.makedirs(dest_dir, exist_ok=True)
        size = _dir_size(path)
        shutil.move(path, dest)
    except (OSError, shutil.Error) as exc:
        return False, f"FAILED quarantine {path}: {exc}"
    manifest = QuarantinedItem(original_path=os.path.abspath(path),
                               quarantine_path=dest, size_bytes=size,
                               moved_at=time.time(), kind=kind)
    try:
        with open(os.path.join(dest_dir, "manifest.json"), "w", encoding="utf-8") as fh:
            json.dump(asdict(manifest), fh, indent=2)
    except OSError:
        pass
    return True, f"quarantined (bin disabled): {path} -> {dest}"


def list_quarantine() -> list[QuarantinedItem]:
    items: list[QuarantinedItem] = []
    root = quarantine_root()
    try:
        stamps = sorted(os.listdir(root))
    except OSError:
        return []
    for stamp in stamps:
        mf = os.path.join(root, stamp, "manifest.json")
        try:
            with open(mf, encoding="utf-8") as fh:
                data = json.load(fh)
            items.append(QuarantinedItem(**{k: data[k] for k in
                                            ("original_path", "quarantine_path",
                                             "size_bytes", "moved_at") if k in data},
                                         kind=data.get("kind", "")))
        except (OSError, ValueError, TypeError):
            continue
    return sorted(items, key=lambda i: i.moved_at, reverse=True)


def restore_item(item: QuarantinedItem) -> tuple[bool, str]:
    """Move a quarantined item back to its original location."""
    if not os.path.exists(item.quarantine_path):
        return False, f"quarantine entry gone: {item.quarantine_path}"
    dest = item.original_path
    if os.path.exists(dest):
        return False, f"refusing restore, path exists again: {dest}"
    try:
        parent = os.path.dirname(dest)
        if parent:
            os.makedirs(parent, exist_ok=True)
        shutil.move(item.quarantine_path, dest)
    except (OSError, shutil.Error) as exc:
        return False, f"FAILED restore {item.quarantine_path}: {exc}"
    return True, f"restored: {dest}"


def purge_old(max_age_days: float = RETENTION_DAYS) -> int:
    """Permanently delete quarantine entries older than retention. Returns count."""
    now = time.time()
    purged = 0
    for item in list_quarantine():
        if (now - item.moved_at) / 86400 > max_age_days:
            entry_dir = os.path.dirname(item.quarantine_path)
            try:
                if os.path.isdir(item.quarantine_path):
                    shutil.rmtree(item.quarantine_path, ignore_errors=True)
                else:
                    os.remove(item.quarantine_path)
                try:
                    os.remove(os.path.join(entry_dir, "manifest.json"))
                    os.rmdir(entry_dir)
                except OSError:
                    pass
                purged += 1
            except OSError:
                continue
    return purged
