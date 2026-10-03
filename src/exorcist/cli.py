"""CLI: scan / clean. Dry-run by default."""
from __future__ import annotations

import argparse
import os
import sys

from .cleaner import safe_delete, setup_logging
from .installed import build_name_index, get_installed_apps
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
            min_mb: float = 10, orphan_days: float = 30) -> list[Finding]:
    roots = roots or candidate_roots()
    apps = get_installed_apps(use_winget=use_winget)
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
                    risk = "Skip"
                    reason = (f"'{name}' looks like live software ({what}) - skipped. "
                              f"Unused {entry.age_days:.0f}d but DB says keep.")
                elif verdict == "unknown":
                    risk = "Skip"
                    reason = (f"'{name}' matches no registry/StartMenu/Store app, "
                              f"unused {entry.age_days:.0f}d - unknown, needs review")
                else:
                    risk = "Review"
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
    findings = collect(use_winget=args.winget, min_mb=args.min_mb, orphan_days=args.orphan_days)
    if args.json:
        write_json(findings, args.json)
        print(f"Wrote {len(findings)} findings to {args.json}")
    print_table(findings)
    return 0


def cmd_clean(args: argparse.Namespace) -> int:
    setup_logging(args.verbose)
    findings = collect(use_winget=args.winget, min_mb=args.min_mb, orphan_days=args.orphan_days)
    if args.only:
        findings = [f for f in findings if f.kind in args.only]
    if not args.include_skip:
        skipped = [f for f in findings if f.risk == "Skip"]
        findings = [f for f in findings if f.risk != "Skip"]
        if skipped:
            print(f"({len(skipped)} Skip-risk items hidden - re-run with --include-skip to review them)")
    print_table(findings)
    if not findings:
        return 0
    if args.dry_run:
        print(f"\nDry-run: {len(findings)} items, nothing deleted. Re-run with --execute to recycle.")
        for f in findings:
            ok, msg = safe_delete(f.path, dry_run=True)
            print(f"  {msg}")
        return 0
    # --execute: interactive confirm
    print("\nType the NUMBER to recycle, 'all' for all, or 'q' to quit.")
    for i, f in enumerate(findings):
        print(f"  [{i}] {f.path} ({f.kind}, {f.risk})")
    choice = input("> ").strip().lower()
    targets: list[Finding] = []
    if choice == "all":
        confirm = input(f"Recycle ALL {len(findings)} items to Recycle Bin? Type YES: ").strip()
        if confirm != "YES":
            print("Aborted.")
            return 1
        targets = findings
    elif choice == "q":
        return 0
    else:
        try:
            targets = [findings[int(choice)]]
        except (ValueError, IndexError):
            print("Invalid choice.")
            return 1
    for f in targets:
        ok, msg = safe_delete(f.path, dry_run=False)
        print(msg)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="exorcist", description="Exorcist - exorcise dead apps safely. Find orphaned app data + junk on Windows.")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="scan and report (no deletion)")
    s.add_argument("--json", default="", help="write JSON report to file")
    s.add_argument("--min-mb", type=float, default=10, help="minimum folder size in MB (default 10)")
    s.add_argument("--orphan-days", type=float, default=30, help="min unused days to flag orphan (default 30)")
    s.add_argument("--winget", action="store_true", help="also use winget list (slower)")
    s.set_defaults(func=cmd_scan)

    c = sub.add_parser("clean", help="interactive recycle (dry-run default)")
    c.add_argument("--execute", dest="dry_run", action="store_false", help="allow real recycle (still confirms)")
    c.add_argument("--dry-run", dest="dry_run", action="store_true", default=True)
    c.add_argument("--only", nargs="*", default=None, help="filter kinds: orphan temp cache installer")
    c.add_argument("--include-skip", action="store_true", help="also offer Skip-risk items (unknown/keep) for review")
    c.add_argument("--min-mb", type=float, default=10)
    c.add_argument("--orphan-days", type=float, default=30)
    c.add_argument("--winget", action="store_true")
    c.set_defaults(func=cmd_clean)
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
