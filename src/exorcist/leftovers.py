"""Per-app leftover sheets: every trace one app left behind.

Matches the query against installed names AND on-disk folders with
exact-then-fuzzy logic. Exact matches arrive checked; fuzzy ones arrive
unchecked for the user to confirm. Shared vendor folders are never
offered - strict matching only.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from difflib import SequenceMatcher


@dataclass
class Trace:
    path: str
    size_bytes: int
    age_days: float
    match: str  # exact | fuzzy
    what: str = ""
    checked: bool = False


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def match_score(query_norm: str, candidate_norm: str) -> tuple[str, float]:
    """Return (match_kind, score). exact on equality/substring, else fuzzy."""
    if not query_norm or not candidate_norm:
        return "none", 0.0
    if query_norm == candidate_norm:
        return "exact", 1.0
    if len(query_norm) >= 4 and (query_norm in candidate_norm or candidate_norm in query_norm):
        return "exact", 0.95
    return "fuzzy", _similarity(query_norm, candidate_norm)


def find_app_traces(query: str, roots: dict[str, str] | None = None,
                    fuzzy_cutoff: float = 0.6) -> list[Trace]:
    """Collect on-disk traces resembling query. No deletion, read-only."""
    from .installed import normalize_app_name
    from .rules import candidate_roots, is_blocklisted
    from .scanner import list_child_dirs, scan_folder

    roots = roots or candidate_roots()
    qnorm = normalize_app_name(query)
    if not qnorm:
        return []
    out: list[Trace] = []
    search_parents: list[str] = []
    for key in ("roaming", "local", "programdata"):
        parent = roots.get(key, "")
        if parent and os.path.isdir(parent):
            search_parents.append(parent)
    for var in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(var, "")
        if base and os.path.isdir(base):
            search_parents.append(base)

    for parent in search_parents:
        for child in list_child_dirs(parent):
            if is_blocklisted(child):
                continue
            name = os.path.basename(child.rstrip(os.sep))
            kind, _score = match_score(qnorm, normalize_app_name(name))
            if kind == "none":
                continue
            if kind == "fuzzy" and _score < fuzzy_cutoff:
                continue
            entry = scan_folder(child)
            if not entry:
                continue
            from .explainer import explain

            what, _src, _info = explain(name)
            out.append(Trace(path=child, size_bytes=entry.size_bytes,
                             age_days=entry.age_days, match=kind, what=what,
                             checked=(kind == "exact")))
    # stale installers in Downloads mentioning the query
    dl = roots.get("downloads", "")
    if dl and os.path.isdir(dl):
        try:
            names = os.listdir(dl)
        except OSError:
            names = []
        for fname in names:
            if not fname.lower().endswith((".msi", ".exe", ".iso")):
                continue
            kind, score = match_score(qnorm, normalize_app_name(os.path.splitext(fname)[0]))
            if kind == "none" or (kind == "fuzzy" and score < fuzzy_cutoff):
                continue
            fp = os.path.join(dl, fname)
            try:
                st = os.stat(fp)
            except OSError:
                continue
            import time

            out.append(Trace(path=fp, size_bytes=st.st_size,
                             age_days=(time.time() - st.st_mtime) / 86400,
                             match=kind, what="Installer file",
                             checked=(kind == "exact")))
    return sorted(out, key=lambda t: t.size_bytes, reverse=True)
