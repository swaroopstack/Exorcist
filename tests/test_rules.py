from exorcist.installed import build_name_index, normalize_app_name
from exorcist.installed import InstalledApp
from exorcist.rules import is_blocklisted, looks_orphaned


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
