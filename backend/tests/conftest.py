import httpx2
import pytest


@pytest.fixture(autouse=True)
def block_model_network(monkeypatch):
    """Never spend credits in tests, even if a developer has a real key exported."""
    monkeypatch.delenv("MODEL_API_KEY", raising=False)

    def blocked(*args, **kwargs):
        raise AssertionError("Real model HTTP is forbidden in tests; use MockTransport.")

    monkeypatch.setattr(httpx2.HTTPTransport, "handle_request", blocked)
