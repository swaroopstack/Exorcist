from exorcist import timing
from exorcist.dupes import find_duplicates
from exorcist.largefiles import classify, ollama_models, user_scan_roots, walk_large_files


def test_classify():
    assert classify("movie.mp4") == "video"
    assert classify("song.flac") == "audio"
    assert classify("pic.heic") == "image"
    assert classify("doc.pdf") == "pdf"
    assert classify("a.zip") == "archive"
    assert classify("sheet.xlsx") == "document"
    assert classify("setup.exe") == "installer"
    assert classify("model.gguf") == "aimodel"
    assert classify("random.xyz") == "other"


def test_walk_filters(tmp_path):
    big = tmp_path / "big.iso"
    big.write_bytes(b"x" * (2 * 1024 * 1024))
    small = tmp_path / "small.txt"
    small.write_bytes(b"y")
    node = tmp_path / "node_modules"
    node.mkdir()
    (node / "dep.js").write_bytes(b"z" * (3 * 1024 * 1024))
    hidden = tmp_path / ".cache"
    hidden.mkdir()
    (hidden / "h.bin").write_bytes(b"w" * (3 * 1024 * 1024))

    found = walk_large_files([str(tmp_path)], min_bytes=1024 * 1024)
    paths = [f.path for f in found]
    assert str(big) in paths
    assert str(small) not in paths
    # node_modules + hidden dirs pruned
    assert not any("node_modules" in p or ".cache" in p for p in paths)


def test_walk_older_than(tmp_path):
    import os
    import time

    f = tmp_path / "old.bin"
    f.write_bytes(b"x" * 1024)
    old = time.time() - 200 * 86400
    os.utime(f, (old, old))
    assert len(walk_large_files([str(tmp_path)], min_bytes=1, older_than_days=100)) == 1
    assert walk_large_files([str(tmp_path)], min_bytes=1, older_than_days=300) == []


def test_dupes_grouping(tmp_path):
    a = tmp_path / "a.bin"
    b = tmp_path / "sub" / "b.bin"
    b.parent.mkdir()
    c = tmp_path / "c.bin"
    a.write_bytes(b"same-content")
    b.write_bytes(b"same-content")
    c.write_bytes(b"different!!")
    groups, too_big = find_duplicates([str(a), str(b), str(c)])
    assert len(groups) == 1
    g = groups[0]
    assert set(g.paths) == {str(a), str(b)}
    assert g.reclaimable_bytes == len(b"same-content")
    assert g.keeper in (str(a), str(b))
    assert too_big == []


def test_dupes_size_mismatch_no_hash(tmp_path):
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    a.write_bytes(b"1234")
    b.write_bytes(b"12345")
    groups, _ = find_duplicates([str(a), str(b)])
    assert groups == []


def test_eta_format():
    assert timing.fmt_eta(10).endswith("sec")
    assert "min" in timing.fmt_eta(300)
    cal = timing.Calibrator(1000)
    assert isinstance(cal.eta(), str)


def test_ollama_no_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    # expanduser uses HOME on posix / USERPROFILE on win; force via HOME too
    monkeypatch.setenv("HOME", str(tmp_path))
    assert ollama_models() == []


def test_user_roots_type():
    assert isinstance(user_scan_roots(), list)
