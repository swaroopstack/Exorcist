"""Large personal files scan: Documents/Desktop/Downloads/Movies/Music/Pictures.

Skips managed libraries, hidden folders, and project/dependency dirs
(those belong to Dev/orphan logic - deleting one file from a dependency
tree only breaks the install).
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass


@dataclass
class LargeFile:
    path: str
    size_bytes: int
    age_days: float  # since last modification
    category: str  # video | audio | image | pdf | archive | document | aimodel | other
    source: str = ""  # e.g. model name for aimodel


# Dir names (lowercase) never descended into.
SKIP_DIRS = {
    "node_modules", "target", "deriveddata", "pods", ".gradle", ".git",
    "__pycache__", ".venv", "venv", ".tox",
    "photos library.photoslibrary", "iphoto library.photolibrary",
    "imovie library.imovielibrary", "music library.musiclibrary",
}

# Managed-library roots skipped wholesale (name match on any path part).
SKIP_ROOT_HINTS = {
    "photos library.photoslibrary", "imovie library.imovielibrary",
    "onedrive", "dropbox", "googledrive", "creative cloud files",
}

VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".mpg", ".mpeg", ".ts"}
AUDIO_EXTS = {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma", ".opus"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp", ".heic", ".raw", ".cr2", ".nef", ".svg"}
ARCHIVE_EXTS = {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso", ".cab", ".wim"}
DOC_EXTS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".md", ".csv", ".rtf", ".odt"}


def user_scan_roots() -> list[str]:
    home = os.path.expanduser("~")
    roots = []
    for leaf in ("Documents", "Desktop", "Downloads", "Videos", "Music", "Pictures"):
        p = os.path.join(home, leaf)
        # Localized Windows folders: Videos may be Movies, etc.
        if os.path.isdir(p):
            roots.append(p)
    movies = os.path.join(home, "Movies")
    if os.path.isdir(movies) and movies not in roots:
        roots.append(movies)
    return roots


def ollama_models() -> list[LargeFile]:
    """Decode Ollama's content-addressed storage into per-model rows.

    Shared blobs are counted once across the whole return (first model
    referencing a blob owns its bytes), so sizes reflect true reclaim.
    """
    import json as _json

    home = os.path.expanduser("~")
    manifests = os.path.join(home, ".ollama", "models", "manifests")
    blobs = os.path.join(home, ".ollama", "models", "blobs")
    if not os.path.isdir(manifests) or not os.path.isdir(blobs):
        return []
    blob_sizes: dict[str, int] = {}
    try:
        for name in os.listdir(blobs):
            if not name.startswith("sha256-"):
                continue
            try:
                blob_sizes[name] = os.path.getsize(os.path.join(blobs, name))
            except OSError:
                continue
    except OSError:
        return []
    models: list[LargeFile] = []
    claimed: set[str] = set()
    now = time.time()
    for root, _, files in os.walk(manifests):
        for fn in files:
            mp = os.path.join(root, fn)
            try:
                with open(mp, encoding="utf-8") as fh:
                    manifest = _json.load(fh)
            except (OSError, ValueError):
                continue
            rel = os.path.relpath(mp, manifests).replace(os.sep, "/")
            model_name = rel
            total = 0
            newest = 0.0
            try:
                newest = os.stat(mp).st_mtime
            except OSError:
                pass
            for layer in manifest.get("layers", []) + ([manifest.get("config")] if manifest.get("config") else []):
                if not isinstance(layer, dict):
                    continue
                digest = str(layer.get("digest", "")).replace(":", "-")
                if digest in blob_sizes and digest not in claimed:
                    claimed.add(digest)
                    total += blob_sizes[digest]
            if total > 0:
                models.append(LargeFile(
                    path=f"ollama:{model_name}", size_bytes=total,
                    age_days=(now - newest) / 86400 if newest else 9999,
                    category="aimodel", source=model_name))
    return sorted(models, key=lambda m: m.size_bytes, reverse=True)


def classify(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in VIDEO_EXTS:
        return "video"
    if ext in AUDIO_EXTS:
        return "audio"
    if ext in IMAGE_EXTS:
        return "image"
    if ext == ".pdf":
        return "pdf"
    if ext in ARCHIVE_EXTS:
        return "archive"
    if ext in DOC_EXTS:
        return "document"
    if ext in {".exe", ".msi", ".iso"}:
        return "installer"
    if ext in {".gguf", ".bin", ".safetensors", ".onnx", ".pt", ".pth", ".ckpt"}:
        return "aimodel"
    return "other"


def _skipped_dir(dirname: str) -> bool:
    low = dirname.lower()
    if low.startswith("."):
        return True
    return low in SKIP_DIRS


def walk_large_files(roots: list[str], min_bytes: int, older_than_days: float = 0,
                     max_depth: int = 0, progress_cb=None) -> list[LargeFile]:
    """Walk roots collecting files >= min_bytes. max_depth=0 means unlimited.

    progress_cb(files_seen, bytes_seen) is called periodically for ETA display.
    """
    now = time.time()
    out: list[LargeFile] = []
    seen = 0
    tick = 0
    for root in roots:
        if not os.path.isdir(root):
            continue
        base_depth = root.rstrip(os.sep).count(os.sep)
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            # prune skipped dirs in place
            dirnames[:] = [d for d in dirnames if not _skipped_dir(d)]
            if any(h in dirpath.lower() for h in SKIP_ROOT_HINTS):
                dirnames[:] = []
                continue
            if max_depth and (dirpath.rstrip(os.sep).count(os.sep) - base_depth) >= max_depth:
                dirnames[:] = []
                continue
            for fn in filenames:
                # skip reparse points / hidden files cheaply
                if fn.startswith("."):
                    continue
                fp = os.path.join(dirpath, fn)
                try:
                    if os.path.islink(fp):
                        continue
                    st = os.stat(fp)
                except OSError:
                    continue
                if st.st_size < min_bytes:
                    continue
                age = (now - st.st_mtime) / 86400
                if age < older_than_days:
                    continue
                out.append(LargeFile(path=fp, size_bytes=st.st_size,
                                     age_days=age, category=classify(fp)))
                seen += 1
                tick += 1
                if progress_cb and tick % 200 == 0:
                    progress_cb(seen, sum(f.size_bytes for f in out))
    if progress_cb:
        progress_cb(seen, sum(f.size_bytes for f in out))
    return sorted(out, key=lambda f: f.size_bytes, reverse=True)
