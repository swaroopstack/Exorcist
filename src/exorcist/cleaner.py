"""Safe deletion: blocklist + Recycle Bin (or quarantine fallback) + logging."""
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


def deletion_backend() -> tuple[str, str]:
    """Return ('recycle'|'quarantine', reason). Quarantine when the bin is disabled."""
    try:
        from .quarantine import is_bin_disabled
    except Exception:
        return "recycle", ""
    disabled, reason = is_bin_disabled()
    if disabled:
        return "quarantine", reason
    return "recycle", ""


def safe_delete(path: str, dry_run: bool = True, kind: str = "") -> tuple[bool, str]:
    """Returns (ok, message). Never deletes blocklisted paths."""
    if is_blocklisted(path):
        return False, f"BLOCKED (system path): {path}"
    if not os.path.exists(path):
        return False, f"missing: {path}"
    backend, why = deletion_backend()
    if dry_run:
        where = "quarantine" if backend == "quarantine" else "Recycle Bin"
        return True, f"[dry-run] would move to {where}: {path}"
    if backend == "quarantine":
        from .quarantine import quarantine_move

        log.warning("bin disabled (%s), quarantining %s", why, path)
        return quarantine_move(path, kind=kind)
    try:
        send2trash(path)
        log.info("recycled %s", path)
        return True, f"recycled: {path}"
    except Exception as exc:  # noqa: BLE001
        log.error("delete failed %s: %s", path, exc)
        return False, f"FAILED {path}: {exc}"
