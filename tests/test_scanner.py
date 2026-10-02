import os
from exorcist.scanner import dir_size_fast, scan_folder


def test_dir_size_fast(tmp_path):
    f = tmp_path / "a.bin"
    f.write_bytes(b"x" * 1024)
    total, _, _, _ = dir_size_fast(str(tmp_path))
    assert total >= 1024
    entry = scan_folder(str(tmp_path))
    assert entry is not None and entry.size_bytes >= 1024


def test_missing_returns_none():
    assert scan_folder(os.path.join("Z:", "nope", "missing")) is None
