import json
import urllib.request

import pytest

from exorcist import gui


@pytest.fixture()
def server():
    import threading

    srv = gui.run_server(0, open_browser=False)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield srv
    srv.shutdown()
    thread.join(timeout=5)


def _get(server, path):
    with urllib.request.urlopen(f"http://127.0.0.1:{server.server_port}{path}") as r:
        return json.load(r)


def _post(server, path, payload):
    req = urllib.request.Request(
        f"http://127.0.0.1:{server.server_port}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def test_index_serves_dashboard(server):
    with urllib.request.urlopen(f"http://127.0.0.1:{server.server_port}/") as r:
        body = r.read().decode()
    assert "Exorcist" in body and "fetch(" in body


def test_leftovers_api_empty(server):
    assert _get(server, "/api/leftovers?app=NoSuchAppXYZ123") == {"traces": []}


def test_unknown_route_404(server):
    import urllib.error

    with pytest.raises(urllib.error.HTTPError) as exc:
        _get(server, "/api/nope")
    assert exc.value.code == 404


def test_clean_dry_run_only_tmp(tmp_path, server):
    victim = tmp_path / "f.txt"
    victim.write_text("hi")
    out = _post(server, "/api/clean", {"paths": [str(victim)], "dry_run": True})
    assert out["results"][0]["ok"] is True
    assert victim.exists()  # dry run touches nothing


def test_clean_caps_at_100_paths(server):
    out = _post(server, "/api/clean", {"paths": [f"C:\\nope\\{i}" for i in range(150)], "dry_run": True})
    assert len(out["results"]) == 100
