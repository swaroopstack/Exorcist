"""Reporting: rich table + JSON."""
from __future__ import annotations

import json
from dataclasses import asdict

from rich.console import Console
from rich.table import Table

from .rules import Finding


def fmt_size(n: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return f"{n:.1f} TB"


def print_table(findings: list[Finding]) -> None:
    con = Console()
    if not findings:
        con.print("[green]No cleanup candidates found.[/green]")
        return
    t = Table(title=f"Exorcist — {len(findings)} candidates, {fmt_size(sum(f.size_bytes for f in findings))} reclaimable")
    t.add_column("Risk", style="bold")
    t.add_column("Kind")
    t.add_column("Size", justify="right")
    t.add_column("Unused")
    t.add_column("Reason")
    t.add_column("Path", overflow="fold")
    for f in sorted(findings, key=lambda x: x.size_bytes, reverse=True):
        style = "green" if f.risk == "Safe" else "yellow" if f.risk == "Review" else "red"
        t.add_row(f.risk, f.kind, fmt_size(f.size_bytes), f"{f.age_days:.0f}d", f.reason, f.path, style=style)
    con.print(t)
    con.print("[dim]Review each path. Run `exorcist clean --dry-run` first. Deletes go to Recycle Bin.[/dim]")


def write_json(findings: list[Finding], dest: str) -> None:
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump([asdict(f) for f in findings], fh, indent=2)
