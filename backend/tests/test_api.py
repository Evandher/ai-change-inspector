import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.diff_parser import MAX_DIFF_BYTES
from tests.test_parser import SIMPLE

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://127.0.0.1:8000"
    ) as session:
        yield session


async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_parse(client):
    response = await client.post("/api/diff/parse", json={"diff": SIMPLE})
    assert response.status_code == 200
    result = response.json()
    assert result["additions"] == result["deletions"] == 1
    file = result["files"][0]
    assert file["file_id"].startswith("file_")
    assert file["hunks"][0]["hunk_id"].startswith("hunk_")
    assert file["hunks"][0]["lines"][1]["new_line"] == 1


async def test_parser_error(client):
    response = await client.post("/api/diff/parse", json={"diff": "garbage"})
    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "invalid_header",
            "message": "Expected a diff --git header at the start.",
            "line": 1,
        }
    }


async def test_oversized_diff(client):
    response = await client.post("/api/diff/parse", json={"diff": "é" * (MAX_DIFF_BYTES // 2 + 1)})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "diff_too_large"


async def test_invalid_requests(client):
    for body in [{}, {"diff": 123}, {"diff": None}, {"diff": SIMPLE, "extra": True}, []]:
        response = await client.post("/api/diff/parse", json=body)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "invalid_request"
    response = await client.post(
        "/api/diff/parse",
        content="{bad",
        headers={
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


async def test_openapi_documents_contract(client):
    schema = (await client.get("/openapi.json")).json()
    operation = schema["paths"]["/api/diff/parse"]["post"]
    assert operation["responses"]["422"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ErrorResponse",
    }
