"""List installed apps on Windows (source of truth for orphan detection)."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class InstalledApp:
    name: str
    normalized: str


def normalize_app_name(name: str) -> str:
    n = name.lower().strip()
    # remove version numbers like 1.2.3, (64-bit), - x64
    n = re.sub(r"\b\d+(\.\d+)+\b", " ", n)
    n = re.sub(r"\(.*?\)", " ", n)
    n = re.sub(r"\b(x64|x86|64-bit|32-bit|64 bit)\b", " ", n)
    for token in [" inc", " inc.", " corporation", " corp", " technologies", " technology", " labs", " llc", " gmbh"]:
        n = n.replace(token, " ")
    n = re.sub(r"[^a-z0-9]+", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n


def _from_registry() -> list[str]:
    names: list[str] = []
    try:
        import winreg
    except ImportError:
        return names  # non-Windows (dev/tests)
    roots = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    for hive, key_path in roots:
        try:
            with winreg.OpenKey(hive, key_path) as key:
                for i in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        sub = winreg.EnumKey(key, i)
                        with winreg.OpenKey(key, sub) as sk:
                            try:
                                disp, _ = winreg.QueryValueEx(sk, "DisplayName")
                                if disp and isinstance(disp, str) and disp.strip():
                                    names.append(disp.strip())
                            except OSError:
                                continue
                    except OSError:
                        continue
        except OSError:
            continue
    return names


def _from_program_files() -> list[str]:
    names: list[str] = []
    for base in [
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
    ]:
        try:
            if os.path.isdir(base):
                names.extend(d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d)))
        except OSError:
            continue
    return names


def _from_winget(timeout: int = 15) -> list[str]:
    if not shutil.which("winget"):
        return []
    try:
        out = subprocess.run(
            ["winget", "list", "--source", "winget"],
            capture_output=True, text=True, timeout=timeout,
        )
        if out.returncode != 0:
            return []
        # winget table: Name ... only take first 40 chars loosely
        lines = out.stdout.splitlines()
        names = []
        for line in lines[1:]:
            line = line.strip()
            if not line or line.startswith("-"):
                continue
            # heuristic: name is leading text before 2+ spaces
            parts = re.split(r"\s{2,}", line)
            if parts:
                names.append(parts[0].strip())
        return names
    except Exception:
        return []


def get_installed_apps(use_winget: bool = False) -> list[InstalledApp]:
    raw: list[str] = []
    raw.extend(_from_registry())
    raw.extend(_from_program_files())
    if use_winget:
        raw.extend(_from_winget())
    seen: set[str] = set()
    apps: list[InstalledApp] = []
    for r in raw:
        norm = normalize_app_name(r)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        apps.append(InstalledApp(name=r, normalized=norm))
    return apps


def build_name_index(apps: list[InstalledApp]) -> set[str]:
    idx: set[str] = set()
    for a in apps:
        idx.add(a.normalized)
        # also add first significant token so "Discord Inc" folder "discord" matches
        for tok in a.normalized.split():
            if len(tok) >= 4:
                idx.add(tok)
    return idx
