import os

from exorcist import watcher
from exorcist.leftovers import find_app_traces, match_score


def test_match_score():
    assert match_score("discord", "discord")[0] == "exact"
    assert match_score("discord", "discord inc")[0] == "exact"
    assert match_score("photoshop", "adobe photoshop 2024")[0] == "exact"
    kind, score = match_score("xyzabc", "totally different name here")
    assert kind == "fuzzy" and score < 0.6
    assert match_score("", "foo")[0] == "none"


def test_find_traces_exact(tmp_path, monkeypatch):
    roaming = tmp_path / "Roaming"
    roaming.mkdir()
    target = roaming / "DeadApp"
    target.mkdir()
    (target / "data.bin").write_bytes(b"x" * 2048)
    other = roaming / "OtherLive"
    other.mkdir()
    (other / "f.bin").write_bytes(b"y" * 2048)
    roots = {"roaming": str(roaming), "local": "", "programdata": "",
             "downloads": ""}
    traces = find_app_traces("DeadApp", roots=roots)
    paths = [t.path for t in traces]
    assert str(target) in paths
    assert str(other) not in paths
    hit = next(t for t in traces if t.path == str(target))
    assert hit.match == "exact" and hit.checked is True
    assert hit.size_bytes >= 2048


def test_find_traces_fuzzy_unchecked(tmp_path):
    roaming = tmp_path / "Roaming"
    roaming.mkdir()
    target = roaming / "PhotoShop Helper"
    target.mkdir()
    (target / "f.bin").write_bytes(b"x" * 100)
    roots = {"roaming": str(roaming), "local": "", "programdata": "",
             "downloads": ""}
    traces = find_app_traces("Photoshop", roots=roots)
    assert any(t.match == "exact" and t.checked for t in traces)


def test_find_traces_downloads_installer(tmp_path):
    dl = tmp_path / "Downloads"
    dl.mkdir()
    inst = dl / "DeadApp-Setup-1.0.exe"
    inst.write_bytes(b"z" * 512)
    roots = {"roaming": "", "local": "", "programdata": "",
             "downloads": str(dl)}
    traces = find_app_traces("DeadApp", roots=roots)
    assert any(t.path == str(inst) and t.what == "Installer file" for t in traces)


def test_watcher_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert watcher.vanished_apps({"a", "b"}) == (set(), 0.0)  # first run
    watcher.save_snapshot({"a", "b"})
    gone, _at = watcher.vanished_apps({"a"})
    assert gone == {"b"}
    gone2, _ = watcher.vanished_apps({"a", "b", "c"})
    assert gone2 == set()


def test_watcher_corrupt_ignored(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    with open(watcher.snapshot_path(), "w", encoding="utf-8") as fh:
        fh.write("{broken")
    assert watcher.vanished_apps({"a"}) == (set(), 0.0)
