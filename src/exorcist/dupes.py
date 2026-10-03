"""Byte-for-byte duplicate finder.

Two-phase: group by size (free), then blake2b-hash only same-size
candidates. Files over HASH_CAP_BYTES are reported as unhashable
rather than read fully into a stall.
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field

HASH_CHUNK = 1024 * 1024
HASH_CAP_BYTES = 4 * 1024 * 1024 * 1024  # 4 GiB


@dataclass
class DupeGroup:
    size_bytes: int
    paths: list[str] = field(default_factory=list)
    hash: str = ""
    reclaimable_bytes: int = 0  # size * (n-1): keep one, recycle rest

    @property
    def keeper(self) -> str:
        # Prefer shortest path, then alphabetical: stable suggestion.
        return sorted(self.paths, key=lambda p: (len(p), p))[0] if self.paths else ""


def hash_file(path: str) -> str | None:
    h = hashlib.blake2b()
    try:
        with open(path, "rb") as fh:
            while True:
                chunk = fh.read(HASH_CHUNK)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def find_duplicates(files: list[str], min_bytes: int = 0) -> tuple[list[DupeGroup], list[str]]:
    """files: candidate paths. Returns (groups, too_big).

    too_big lists paths skipped for exceeding HASH_CAP_BYTES.
    """
    by_size: dict[int, list[str]] = {}
    for fp in files:
        try:
            sz = os.path.getsize(fp)
        except OSError:
            continue
        if sz < min_bytes:
            continue
        by_size.setdefault(sz, []).append(fp)

    groups: list[DupeGroup] = []
    too_big: list[str] = []
    for size, paths in by_size.items():
        if len(paths) < 2:
            continue
        if size > HASH_CAP_BYTES:
            too_big.extend(paths)
            continue
        by_hash: dict[str, list[str]] = {}
        for fp in paths:
            digest = hash_file(fp)
            if digest is None:
                continue
            by_hash.setdefault(digest, []).append(fp)
        for digest, same in by_hash.items():
            if len(same) < 2:
                continue
            groups.append(DupeGroup(size_bytes=size, paths=sorted(same), hash=digest,
                                    reclaimable_bytes=size * (len(same) - 1)))
    groups.sort(key=lambda g: g.reclaimable_bytes, reverse=True)
    return groups, too_big
