"""CLI: scan / clean. Dry-run by default."""
from __future__ import annotations

import argparse
import os
import sys

from .cleaner import safe_delete, setup_logging
from .installed import build_name_index, get_installed_apps_cached
from .reporter import print_table, write_json
from .rules import (
    candidate_roots,
    folder_has_live_exe,
    is_blocklisted,
    looks_orphaned,
    make_finding,
    Finding,
)
from .scanner import list_child_dirs, scan_folder


def collect(roots: dict[str, str] | None = None, use_winget: bool = False,
            min_mb: float = 10, orphan_days: float = 30, refresh: bool = False) -> list[Finding]:
    roots = roots or candidate_roots()
    apps = get_installed_apps_cached(use_winget=use_winget, refresh=refresh)
    index = build_name_index(apps)
    min_bytes = int(min_mb * 1024 * 1024)
    out: list[Finding] = []

    # 1. Orphan scan: child dirs of roaming/local/programdata
    for key in ("roaming", "local", "programdata"):
        parent = roots.get(key, "")
        if not parent or not os.path.isdir(parent):
            continue
        for child in list_child_dirs(parent):
            if is_blocklisted(child):
                continue
            entry = scan_folder(child)
            if not entry or entry.size_bytes < min_bytes:
                continue
            name = os.path.basename(child.rstrip(os.sep))
            if entry.age_days >= orphan_days and looks_orphaned(name, index):
                live, why = folder_has_live_exe(child)
                if live:
                    continue  # exe alive/running => not orphan, skip
                from .explainer import explain

                what, source, info = explain(name)
                verdict = info.verdict if info else "unknown"
                if verdict == "keep":
                    risk = "Skipped"
                    reason = (f"'{name}' looks like live software ({what}) - skipped. "
                              f"Unused {entry.age_days:.0f}d but DB says keep.")
                elif verdict == "unknown":
                    risk = "Skipped"
                    reason = (f"'{name}' matches no registry/StartMenu/Store app, "
                              f"unused {entry.age_days:.0f}d - unknown, needs review")
                else:
                    risk = "Check First"
                    reason = (f"'{name}' matches no registry/StartMenu/Store app, "
                              f"unused {entry.age_days:.0f}d")
                    if info and info.note:
                        reason += f". {info.note}"
                f = make_finding(child, entry.size_bytes, entry.age_days, "orphan",
                                 reason, what=what, source=source)
                f.risk = risk
                out.append(f)

    # 2. Temp / cache: whole-folder size if over threshold
    for key, kind in [("temp_user", "temp"), ("temp_win", "temp"),
                      ("update_cache", "cache"), ("delivery_opt", "cache"),
                      ("prefetch", "cache")]:
        p = roots.get(key, "")
        if not p or not os.path.isdir(p) or is_blocklisted(p):
            continue
        entry = scan_folder(p)
        if entry and entry.size_bytes >= min_bytes:
            out.append(make_finding(
                p, entry.size_bytes, entry.age_days, kind,
                "safe to empty: temp/update cache" if kind in ("temp", "cache")
                else "stale cache",
            ))

    # 3. Stale installers in Downloads (>90d, .msi/.exe/.iso)
    dl = roots.get("downloads", "")
    if dl and os.path.isdir(dl):
        for fname in os.listdir(dl):
            fp = os.path.join(dl, fname)
            low = fname.lower()
            if not low.endswith((".msi", ".exe", ".iso")):
                continue
            try:
                st = os.stat(fp)
            except OSError:
                continue
            import time
            age = (time.time() - st.st_mtime) / 86400
            if age > 90 and st.st_size >= min_bytes:
                out.append(make_finding(fp, st.st_size, age, "installer",
                                        f"stale installer in Downloads, unused {age:.0f}d"))
    return sorted(out, key=lambda f: f.size_bytes, reverse=True)


def cmd_scan(args: argparse.Namespace) -> int:
    setup_logging(args.verbose)
    findings = collect(use_winget=args.winget, min_mb=args.min_mb,
                       orphan_days=args.orphan_days, refresh=args.refresh)
    if args.json:
        write_json(findings, args.json)
        print(f"Wrote {len(findings)} findings to {args.json}")
    print_table(findings)
    return 0


def _measure_roots(roots: list[str], max_depth: int) -> int:
    """Fast byte total for ETA calibration (prunes the same skip dirs)."""
    from .largefiles import SKIP_DIRS, SKIP_ROOT_HINTS

    total = 0
    for root in roots:
        if not os.path.isdir(root):
            continue
        base_depth = root.rstrip(os.sep).count(os.sep)
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            dirnames[:] = [d for d in dirnames
                           if not (d.startswith(".") or d.lower() in SKIP_DIRS)]
            if any(h in dirpath.lower() for h in SKIP_ROOT_HINTS):
                dirnames[:] = []
                continue
            if max_depth and (dirpath.rstrip(os.sep).count(os.sep) - base_depth) >= max_depth:
                dirnames[:] = []
                continue
            for fn in filenames:
                if fn.startswith("."):
                    continue
                try:
                    st = os.stat(os.path.join(dirpath, fn))
                    if not fn.startswith("~"):
                        total += st.st_size
                except OSError:
                    continue
    return total


def cmd_large_files(args: argparse.Namespace) -> int:
    import time as _time

    from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

    from .largefiles import ollama_models, user_scan_roots, walk_large_files
    from .reporter import fmt_size
    from .timing import Calibrator, quote_estimate, record_run

    setup_logging(args.verbose)
    full = args.full
    max_depth = 0 if full else 3
    min_bytes = int(args.min_mb * 1024 * 1024)
    scan_name = "large-files-full" if full else "large-files-quick"

    roots = user_scan_roots()
    if not roots:
        print("No user folders found to scan.")
        return 0

    print(f"Estimating {'full' if full else 'quick'} scan over {len(roots)} folders...")
    total_bytes = _measure_roots(roots, max_depth)
    quoted = quote_estimate(scan_name, total_bytes)
    if quoted:
        print(f"Estimated time: {quoted} (based on your last scans)")
    else:
        print(f"Estimated time: unknown on first run - {fmt_size(total_bytes)} to walk")

    calib = Calibrator(total_bytes)
    walked = {"n": 0}
    start = _time.time()
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  BarColumn(), TextColumn("{task.completed} files"), TimeElapsedColumn()) as prog:
        task = prog.add_task("Scanning", total=None)

        def cb(n_files: int, n_bytes: int) -> None:
            walked["n"] = n_files
            calib.add(n_bytes - getattr(cb, "last", 0))
            cb.last = n_bytes  # type: ignore[attr-defined]
            prog.update(task, completed=n_files,
                        description=f"Scanning - ETA {calib.eta()}")

        cb.last = 0  # type: ignore[attr-defined]
        files = walk_large_files(roots, min_bytes,
                                 older_than_days=args.older_than,
                                 max_depth=max_depth, progress_cb=cb)
    elapsed = _time.time() - start
    record_run(scan_name, elapsed, total_bytes)

    entries = list(files)
    if full or args.include_models:
        for m in ollama_models():
            if m.size_bytes >= min_bytes:
                entries.append(m)
        entries.sort(key=lambda f: f.size_bytes, reverse=True)

    if args.category:
        entries = [f for f in entries if f.category == args.category]
    entries = entries[: args.limit]

    if args.json:
        import json as _json

        with open(args.json, "w", encoding="utf-8") as fh:
            _json.dump([{"path": f.path, "size_bytes": f.size_bytes,
                         "age_days": round(f.age_days, 1), "category": f.category,
                         "source": f.source} for f in entries], fh, indent=2)
        print(f"Wrote {len(entries)} entries to {args.json}")

    from rich.console import Console
    from rich.table import Table

    con = Console()
    if not entries:
        con.print("[green]No large files found.[/green]")
        return 0
    reclaim = sum(f.size_bytes for f in entries)
    t = Table(title=f"Exorcist large files - {len(entries)} items, {fmt_size(reclaim)}")
    t.add_column("Size", justify="right")
    t.add_column("Last used")
    t.add_column("Category")
    t.add_column("Path", overflow="fold")
    for f in entries:
        t.add_row(fmt_size(f.size_bytes), f"{f.age_days:.0f}d",
                  f.source or f.category, f.path)
    con.print(t)
    return 0


def cmd_dupes(args: argparse.Namespace) -> int:
    import time as _time

    from rich.console import Console
    from rich.table import Table

    from .dupes import find_duplicates
    from .largefiles import user_scan_roots, walk_large_files
    from .reporter import fmt_size
    from .timing import record_run

    setup_logging(args.verbose)
    min_bytes = int(args.min_mb * 1024 * 1024)
    roots = user_scan_roots()
    print(f"Walking {len(roots)} folders for files over {fmt_size(min_bytes)}...")
    start = _time.time()
    files = walk_large_files(roots, min_bytes, max_depth=0 if args.full else 4)
    print(f"Hashing {len(files)} same-size candidates (byte-for-byte)...")
    groups, too_big = find_duplicates([f.path for f in files], min_bytes)
    record_run("dupes-full" if args.full else "dupes-quick", _time.time() - start,
               sum(f.size_bytes for f in files))

    if args.json:
        import json as _json

        with open(args.json, "w", encoding="utf-8") as fh:
            _json.dump([{"size_bytes": g.size_bytes, "hash": g.hash,
                         "keeper": g.keeper, "paths": g.paths,
                         "reclaimable_bytes": g.reclaimable_bytes} for g in groups], fh, indent=2)
        print(f"Wrote {len(groups)} groups to {args.json}")

    con = Console()
    if not groups:
        con.print("[green]No duplicates found.[/green]")
        return 0
    reclaim = sum(g.reclaimable_bytes for g in groups)
    t = Table(title=f"Exorcist duplicates - {len(groups)} groups, {fmt_size(reclaim)} reclaimable")
    t.add_column("Reclaim")
    t.add_column("Keep (suggested)")
    t.add_column("Recycle the rest", overflow="fold")
    for g in groups[: args.limit]:
        rest = [p for p in g.paths if p != g.keeper]
        shown = "\n".join(rest[:5]) + (f"\n... +{len(rest) - 5} more" if len(rest) > 5 else "")
        t.add_row(fmt_size(g.reclaimable_bytes), g.keeper, shown)
    con.print(t)
    if too_big:
        con.print(f"[dim]{len(too_big)} files over 4GB skipped for hashing.[/dim]")
    con.print("[dim]Recycle duplicates from Explorer or clean --execute; nothing deleted by this command.[/dim]")
    return 0


def cmd_clean(args: argparse.Namespace) -> int:
    setup_logging(args.verbose)
    findings = collect(use_winget=args.winget, min_mb=args.min_mb,
                       orphan_days=args.orphan_days, refresh=args.refresh)
    if args.only:
        findings = [f for f in findings if f.kind in args.only]
    if not args.include_skip:
        skipped = [f for f in findings if f.risk == "Skipped"]
        findings = [f for f in findings if f.risk != "Skipped"]
        if skipped:
            print(f"({len(skipped)} skipped items hidden - re-run with --include-skip to review them)")
    print_table(findings)
    if not findings:
        return 0
    if args.dry_run:
        print(f"\nDry-run: {len(findings)} items, nothing deleted. Re-run with --execute to recycle.")
        for f in findings:
            ok, msg = safe_delete(f.path, dry_run=True)
            print(f"  {msg}")
        return 0
    # --execute: per-item confirm with detail cards.
    # Large items (>500MB) require typing the folder name: no blind 'all'.
    from .reporter import fmt_size

    offer_restore_point()
    print("\nAnswer y/N for each item. 'q' quits. Items over 500MB ask for the folder name.")
    recycled = 0
    for f in findings:
        name = os.path.basename(f.path.rstrip(os.sep))
        print(f"\n--- {f.path}")
        print(f"    kind={f.kind} risk={f.risk} size={fmt_size(f.size_bytes)} unused={f.age_days:.0f}d")
        if f.what:
            print(f"    what: {f.what}")
        print(f"    why: {f.reason}")
        if f.size_bytes >= 500 * 1024 * 1024:
            answer = input(f"    Type the folder name '{name}' to recycle, else Enter to skip: ").strip()
            if answer != name:
                print("    skipped.")
                continue
        else:
            answer = input("    Recycle this to Recycle Bin? [y/N/q]: ").strip().lower()
            if answer == "q":
                break
            if answer != "y":
                print("    skipped.")
                continue
        ok, msg = safe_delete(f.path, dry_run=False)
        print(f"    {msg}")
        if ok:
            recycled += 1
    print(f"\nRecycled {recycled} item(s) to Recycle Bin.")
    return 0


def offer_restore_point() -> None:
    """Offer a Windows System Restore Point before any deletion."""
    try:
        answer = input("Create a System Restore Point first? [Y/n]: ").strip().lower()
    except EOFError:
        return
    if answer not in ("", "y", "yes"):
        print("Skipping restore point (your choice - Recycle Bin still allows undo).")
        return
    import subprocess

    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Checkpoint-Computer -Description 'Exorcist cleanup' -RestorePointType MODIFY_SETTINGS"],
            capture_output=True, text=True, timeout=120,
        )
        if out.returncode == 0:
            print("Restore point created.")
        else:
            print("Could not create restore point (needs admin?). Continuing - Recycle Bin still allows undo.")
    except Exception:
        print("Could not create restore point. Continuing - Recycle Bin still allows undo.")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="exorcist", description="Exorcist - exorcise dead apps safely. Find orphaned app data + junk on Windows.")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="scan and report (no deletion)")
    s.add_argument("--json", default="", help="write JSON report to file")
    s.add_argument("--min-mb", type=float, default=10, help="minimum folder size in MB (default 10)")
    s.add_argument("--orphan-days", type=float, default=30, help="min unused days to flag orphan (default 30)")
    s.add_argument("--winget", action="store_true", help="also use winget list (slower)")
    s.add_argument("--refresh", action="store_true", help="rebuild installed-app cache (skips 24h cache)")
    s.set_defaults(func=cmd_scan)

    c = sub.add_parser("clean", help="interactive recycle (dry-run default)")
    c.add_argument("--execute", dest="dry_run", action="store_false", help="allow real recycle (still confirms)")
    c.add_argument("--dry-run", dest="dry_run", action="store_true", default=True)
    c.add_argument("--only", nargs="*", default=None, help="filter kinds: orphan temp cache installer")
    c.add_argument("--include-skip", action="store_true", help="also offer skipped items (unknown/keep) for review")
    c.add_argument("--min-mb", type=float, default=10)
    c.add_argument("--orphan-days", type=float, default=30)
    c.add_argument("--winget", action="store_true")
    c.add_argument("--refresh", action="store_true", help="rebuild installed-app cache (skips 24h cache)")
    c.set_defaults(func=cmd_clean)

    lf = sub.add_parser("large-files", help="find large personal files (Documents/Desktop/Downloads/...)")
    lf.add_argument("--min-mb", type=float, default=100, help="minimum file size in MB (default 100)")
    lf.add_argument("--older-than", type=float, default=0, help="only files unused for N days (default 0 = all)")
    lf.add_argument("--category", default="", help="filter: video audio image pdf archive document installer aimodel other")
    lf.add_argument("--limit", type=int, default=50, help="max rows shown (default 50)")
    lf.add_argument("--json", default="", help="write JSON report to file")
    lf.add_argument("--full", action="store_true", help="unlimited depth (default quick: 3 levels)")
    lf.add_argument("--include-models", action="store_true", help="include Ollama model storage (implied by --full)")
    lf.set_defaults(func=cmd_large_files)

    dp = sub.add_parser("dupes", help="find byte-identical duplicate files")
    dp.add_argument("--min-mb", type=float, default=50, help="minimum file size in MB (default 50)")
    dp.add_argument("--limit", type=int, default=30, help="max groups shown (default 30)")
    dp.add_argument("--json", default="", help="write JSON report to file")
    dp.add_argument("--full", action="store_true", help="unlimited depth (default quick: 4 levels)")
    dp.set_defaults(func=cmd_dupes)
    return p


def main(argv: list[str] | None = None) -> int:
    # Windows consoles default to cp1252, which mangles em-dashes in tables.
    try:
        if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if sys.stderr is not None and hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
