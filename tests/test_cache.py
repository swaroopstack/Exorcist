import json

from exorcist import cache


def test_cache_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert cache.load_cached_names() is None
    cache.save_cached_names(["Foo App", "Bar"])
    assert cache.load_cached_names() == ["Foo App", "Bar"]
    # expired with max_age=0
    assert cache.load_cached_names(max_age=0) is None
    assert cache.clear_cache() is True
    assert cache.load_cached_names() is None


def test_cache_corrupt_ignored(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    p = cache.cache_path()
    with open(p, "w", encoding="utf-8") as fh:
        fh.write("{not json")
    assert cache.load_cached_names() is None
