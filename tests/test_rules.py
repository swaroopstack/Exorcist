from exorcist.installed import build_name_index, normalize_app_name
from exorcist.installed import InstalledApp
from exorcist.rules import folder_has_live_exe, is_blocklisted, looks_orphaned


def test_normalize():
    assert normalize_app_name("Discord Inc.") == "discord"
    assert normalize_app_name("Google Chrome (64-bit)") == "google chrome"


def test_orphan_detection():
    apps = [InstalledApp("Google Chrome", "google chrome")]
    idx = build_name_index(apps)
    assert not looks_orphaned("Chrome", idx)
    assert looks_orphaned("SomeDeadAppXYZ", idx)
    assert not looks_orphaned("Microsoft", idx)


def test_blocklist():
    assert is_blocklisted(r"C:\Windows\System32")
    assert is_blocklisted(r"C:\Windows")
    assert not is_blocklisted(r"C:\Users\Bob\AppData\Roaming\DeadApp")


def test_orphan_ignores_runtimes_and_vendors():
    idx: set[str] = set()
    for name in ["Dell", "chocolatey", "ms-playwright-go", "NVIDIA", "Cursor"]:
        assert not looks_orphaned(name, idx), name


def test_orphan_fuzzy_match():
    apps = [InstalledApp("MongoDB Compass", "mongodb compass")]
    idx = build_name_index(apps)
    assert not looks_orphaned("MongoDBCompass", idx)
    assert looks_orphaned("SomeDeadAppXYZ", idx)


def test_live_exe_veto(tmp_path):
    exe = tmp_path / "app.exe"
    exe.write_bytes(b"MZ")
    live, _ = folder_has_live_exe(str(tmp_path))
    assert live  # freshly created exe => alive, must not flag
    (tmp_path / "app.exe").unlink()
    (tmp_path / "notes.txt").write_text("hi")
    live2, _ = folder_has_live_exe(str(tmp_path))
    assert not live2
