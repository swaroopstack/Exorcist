# Exorcist - exorcise dead apps, safely

Terminal-first Windows cleanup tool. It finds **orphaned app data**
(folders in AppData/ProgramData left behind after uninstall) and
**useless files** (Temp, update caches, stale Downloads installers),
explains what each folder is, and lets you recycle it - never auto-deletes.

## Safety first

- Dry-run by default; `clean --execute` confirms **per item**
- Items over 500 MB require typing the folder name - no blind `all`
- Deletes go to the **Recycle Bin** (`send2trash`), plus an optional
  **System Restore Point** offer before any deletion
- Unknown folders and live software default to **Skip** and stay hidden
  from `clean` unless you pass `--include-skip`
- Hard blocklist: `C:\Windows`, Boot, and other system paths are never offered

## Install (dev)

```powershell
cd E:\projects\exorcist
python -m venv .venv; .\.venv\Scripts\activate
pip install -e ".[dev]"
```

## Use

```powershell
python -m exorcist.cli scan --min-mb 50
python -m exorcist.cli scan --min-mb 50 --json report.json
python -m exorcist.cli scan --refresh        # rebuild installed-app cache
python -m exorcist.cli clean --dry-run
python -m exorcist.cli clean --execute       # interactive, per-item confirm
pytest
```

## How it decides

1. **Installed index** - registry Uninstall + Program Files + Start Menu +
   MS Store (+ optional winget), cached 24h in `%LOCALAPPDATA%\Exorcist\`
2. **Orphan rules** - exact, token, and fuzzy name matching; live-`.exe`
   veto (recent or running); vendor/runtime ignore list
3. **Explainer** - 120+ entry local `known_folders.yaml` answers
   "What is it?"; unknowns become Skip, never auto-flagged
4. **Risk** - Safe (temp/cache) / Review (known leftover) / Skip (unknown or keep)

## Build exe

```powershell
pip install -e ".[build]"
pyinstaller --name exorcist --onefile --console -p src src/exorcist/cli.py
```

> Requires code signing for SmartScreen trust before public release.

## Changelog

See [CHANGELOG.md](CHANGELOG.md).
