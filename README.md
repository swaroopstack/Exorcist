# Exorcist — exorcise dead apps, safely

Terminal-first Windows cleanup tool. Finds:
1. **Orphaned app data** — folders in AppData/ProgramData left after uninstall.
2. **Useless files** — Temp, logs, cache, stale Downloads installers.

Never auto-deletes. Dry-run by default, deletes via Recycle Bin, hard blocklist for system paths.

## Quickstart (dev)

```powershell
cd E:\projects\exorcist
python -m venv .venv; .\.venv\Scripts\activate
pip install -e ".[dev]"
python -m exorcist.cli scan
python -m exorcist.cli scan --json report.json
python -m exorcist.cli clean --dry-run
pytest
```

## Build exe

```powershell
pip install -e ".[build]"
pyinstaller --name exorcist --onefile --console -p src src/exorcist/cli.py
```

> Requires code signing for SmartScreen trust before public release.
