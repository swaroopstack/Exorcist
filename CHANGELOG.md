# Changelog

## v0.3.0

- New `large-files` command: biggest personal files across
  Documents/Desktop/Downloads/Videos/Music/Pictures, with size/age
  filters, category labels (video, audio, installer, AI model...),
  and Ollama model decoding with shared-blob accounting
- New `dupes` command: byte-for-byte duplicate groups (blake2b, size
  pre-filter, 4GB hash cap) with keep-one suggestion and reclaim total
- Defender-style estimates: history-based quote upfront, live ETA with
  progress bar, perf recorded per scan; `--quick` (default, depth-capped)
  vs `--full`
- Risk labels renamed: Safe to Clean / Check First / Skipped
- Trust packaging: badges, Recycle-Bin banner, safety-label table in README

## v0.2.1

- MIT LICENSE; repo is legally reusable
- UTF-8 console output forced; ASCII-safe separators (no more `?` glyphs)
- Installed-app index cached 24h (`%LOCALAPPDATA%\Exorcist\`); `--refresh` rebuilds; rescan ~17s -> ~6s
- `clean --execute`: per-item y/N detail cards, typed folder-name gate over 500 MB, System Restore Point offer
- 13 tests passing

## v0.2.0

- 120+ entry `known_folders.yaml` + offline `explainer.py`
- "What is it?" column in scan table and JSON
- Unknown folders and `keep`-verdict folders demoted to Skip, hidden from `clean` by default (`--include-skip` to review)

## v0.1.1

- Start Menu + MS Store sources added to installed-app index
- Fuzzy name matching, vendor/runtime ignore list, live-`.exe` veto
- False positives eliminated on test machine (22 -> 16 candidates):
  Dell, MongoDBCompass, Adobe-Backup, ms-playwright-go, Cursor, chocolatey

## v0.1.0

- Initial MVP: orphan/temp/cache/installer scan, rich table + JSON report
- Dry-run `clean` to Recycle Bin, system blocklist, 5 tests
