# Exorcist - exorcise dead apps, safely

<p>
  <a href="https://github.com/swaroopstack/Exorcist/blob/main/LICENSE"><img src="https://img.shields.io/github/license/swaroopstack/Exorcist?color=blue" alt="License: MIT" /></a>
  <a href="https://github.com/swaroopstack/Exorcist/releases/latest"><img src="https://img.shields.io/github/v/release/swaroopstack/Exorcist?label=latest&color=red" alt="Latest release" /></a>
  <a href="https://github.com/swaroopstack/Exorcist/stargazers"><img src="https://img.shields.io/github/stars/swaroopstack/Exorcist?color=yellow" alt="GitHub stars" /></a>
</p>

**Free up your Windows drive. Safely.**

Your PC quietly fills up with leftovers from apps you already uninstalled,
stale installers, and caches you never asked for. Exorcist finds them,
explains what each one is, and recycles what you approve.

> **Nothing is ever deleted permanently. Everything moves to the Recycle Bin,
> so anything can come back.**

You do not need to understand any of it to use it. But if you ever want to
check, every item carries a plain-English explanation and a safety label,
so nothing gets touched that you cannot see and verify first.

## Safety labels

| Label | Meaning |
|-------|---------|
| Safe to Clean | Known temp/cache, safe to remove |
| Check First | Likely a leftover, confirm before recycling |
| Skipped | Unknown or live software - hidden from clean unless you ask |

Unidentified folders never auto-delete. Exorcist only offers what it can explain.

## Safety first

- Dry-run by default; `clean --execute` confirms **per item**
- Items over 500 MB require typing the folder name - no blind `all`
- Deletes go to the **Recycle Bin** (`send2trash`), plus an optional
  **System Restore Point** offer before any deletion
- Unknown folders and live software default to **Skipped** and stay hidden
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
python -m exorcist.cli large-files --min-mb 100 --older-than 180d
python -m exorcist.cli large-files --full --include-models
python -m exorcist.cli dupes --min-mb 50
pytest
```

## How it decides

1. **Installed index** - registry Uninstall + Program Files + Start Menu +
   MS Store (+ optional winget), cached 24h in `%LOCALAPPDATA%\Exorcist\`
2. **Orphan rules** - exact, token, and fuzzy name matching; live-`.exe`
   veto (recent or running); vendor/runtime ignore list
3. **Explainer** - 120+ entry local `known_folders.yaml` answers
   "What is it?"; unknowns become Skip, never auto-flagged
4. **Risk** - Safe to Clean (temp/cache) / Check First (known leftover) / Skipped (unknown or keep)

## Build exe

```powershell
pip install -e ".[build]"
pyinstaller --name exorcist --onefile --console -p src src/exorcist/cli.py
```

> Requires code signing for SmartScreen trust before public release.

## Changelog

See [CHANGELOG.md](CHANGELOG.md).
