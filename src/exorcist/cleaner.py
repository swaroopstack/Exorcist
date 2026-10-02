"""Safe deletion: blocklist + Recycle Bin + logging."""
from __future__ import annotations

import logging
import os

from send2trash import send2trash

from .rules import is_blocklisted

log = logging.getLogger("exorcist")


def setup_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def safe_delete(path: str, dry_run: bool = True) -> tuple[bool, str]:
    """Returns (ok, message). Never deletes blocklisted paths."""
    if is_blocklisted(path):
        return False, f"BLOCKED (system path): {path}"
    if not os.path.exists(path):
        return False, f"missing: {path}"
    if dry_run:
        return True, f"[dry-run] would recycle: {path}"
    try:
        send2trash(path)
        log.info("recycled %s", path)
        return True, f"recycled: {path}"
    except Exception as exc:  # noqa: BLE001
        log.error("delete failed %s: %s", path, exc)
        return False, f"FAILED {path}: {exc}"
