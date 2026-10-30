import httpx2
import pytest


@pytest.fixture(autouse=True)
def block_model_network(monkeypatch):
    """Never spend credits in tests, even if a developer has a real key exported."""
    monkeypatch.delenv("MODEL_API_KEY", raising=False)

    def blocked(*args, **kwargs):
        raise AssertionError("Real model HTTP is forbidden in tests; use MockTransport.")

    monkeypatch.setattr(httpx2.HTTPTransport, "handle_request", blocked)


@pytest.fixture(autouse=True)
def isolated_inbox(tmp_path, monkeypatch):
    monkeypatch.setenv("INSPECTOR_DB_PATH", str(tmp_path / "inbox.sqlite3"))
    monkeypatch.setenv("INSPECTOR_REPOSITORIES", "{}")
    monkeypatch.setenv("INSPECTOR_API_URL", "http://127.0.0.1:8000")
    monkeypatch.setenv("INSPECTOR_WEB_URL", "http://127.0.0.1:5173")
