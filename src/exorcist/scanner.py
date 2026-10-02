"""Fast, safe directory walker."""
from __future__ import annotations

import os
import time
from dataclasses import dataclass


@dataclass
class ScannedEntry:
    path: str
    size_bytes: int
    mtime: float
    atime: float
    age_days: float


def dir_size_fast(path: str, max_entries: int = 200_000) -> tuple[int, float, float, int]:
    """Return (bytes, newest_mtime, newest_atime, file_count). Tolerant of permission errors."""
    total = 0
    latest_mtime = 0.0
    latest_atime = 0.0
    count = 0
    stack = [path]
    while stack:
        cur = stack.pop()
        try:
            with os.scandir(cur) as it:
                for e in it:
                    count += 1
                    if count > max_entries:
                        return total, latest_mtime, latest_atime, count
                    try:
                        # skip junctions / symlinks to avoid loops + system reparse points
                        if e.is_symlink():
                            continue
                        if e.is_dir(follow_symlinks=False):
                            stack.append(e.path)
                        elif e.is_file(follow_symlinks=False):
                            try:
                                st = e.stat(follow_symlinks=False)
                                total += st.st_size
                                if st.st_mtime > latest_mtime:
                                    latest_mtime = st.st_mtime
                                if st.st_atime > latest_atime:
                                    latest_atime = st.st_atime
                            except OSError:
                                continue
                    except OSError:
                        continue
        except OSError:
            continue
    return total, latest_mtime, latest_atime, count


def scan_folder(path: str) -> ScannedEntry | None:
    try:
        st = os.stat(path)
        base_mtime, base_atime = st.st_mtime, st.st_atime
    except OSError:
        return None
    size, mtime, atime, _ = dir_size_fast(path)
    mtime = max(mtime, base_mtime)
    atime = max(atime, base_atime)
    age = (time.time() - mtime) / 86400 if mtime else 9999
    return ScannedEntry(path=path, size_bytes=size, mtime=mtime, atime=atime, age_days=age)


def list_child_dirs(parent: str) -> list[str]:
    try:
        with os.scandir(parent) as it:
            return [e.path for e in it if e.is_dir(follow_symlinks=False) and not e.is_symlink()]
    except OSError:
        return []
