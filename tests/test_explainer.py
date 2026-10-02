from exorcist.explainer import explain, load_db


def test_db_loads():
    db = load_db()
    assert len(db) >= 50
    assert "perplexity" in db
    assert db["dell"].verdict == "keep"


def test_explain_known():
    what, source, info = explain("Perplexity")
    assert source == "known-db"
    assert info is not None and info.verdict == "review"
    assert "Perplexity" in what


def test_explain_unknown():
    what, source, info = explain("SomeDeadAppXYZ123")
    assert source == ""
    assert info is None
    assert "Unknown" in what
