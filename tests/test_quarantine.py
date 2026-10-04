import os

from exorcist import quarantine
from exorcist.cleaner import safe_delete


def test_quarantine_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    victim = tmp_path / "deadapp"
    victim.mkdir()
    (victim / "data.bin").write_bytes(b"x" * 1024)

    ok, msg = quarantine.quarantine_move(str(victim), kind="orphan")
    assert ok, msg
    assert not os.path.exists(str(victim))

    items = quarantine.list_quarantine()
    assert len(items) == 1
    assert items[0].original_path == os.path.abspath(str(victim))
    assert items[0].size_bytes >= 1024

    ok, msg = quarantine.restore_item(items[0])
    assert ok, msg
    assert os.path.isfile(str(victim / "data.bin"))


def test_restore_refuses_when_path_back(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    victim = tmp_path / "app"
    victim.mkdir()
    ok, _ = quarantine.quarantine_move(str(victim))
    assert ok
    # recreate original path meanwhile -> restore must refuse
    victim.mkdir()
    items = quarantine.list_quarantine()
    ok, msg = quarantine.restore_item(items[0])
    assert not ok and "exists again" in msg


def test_purge_old(tmp_path, monkeypatch):
    import time

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    victim = tmp_path / "old"
    victim.mkdir()
    ok, _ = quarantine.quarantine_move(str(victim))
    assert ok
    # backdate manifest beyond retention
    items = quarantine.list_quarantine()
    mf = os.path.join(os.path.dirname(items[0].quarantine_path), "manifest.json")
    import json

    with open(mf, encoding="utf-8") as fh:
        data = json.load(fh)
    data["moved_at"] = time.time() - 31 * 86400
    with open(mf, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    assert quarantine.purge_old() == 1
    assert quarantine.list_quarantine() == []


def test_safe_delete_routes_to_quarantine_when_bin_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr("exorcist.quarantine.is_bin_disabled",
                        lambda: (True, "disabled in test"))
    victim = tmp_path / "gone"
    victim.mkdir()
    (victim / "f.txt").write_text("hi")
    ok, msg = safe_delete(str(victim), dry_run=False, kind="orphan")
    assert ok and "quarantin" in msg, msg
    assert not os.path.exists(str(victim))
    assert len(quarantine.list_quarantine()) == 1


def test_bin_check_returns_tuple():
    disabled, reason = quarantine.is_bin_disabled()
    assert isinstance(disabled, bool) and isinstance(reason, str)
