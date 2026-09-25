"""Tests for operational health routes."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def anyio_backend() -> str:
    """Use the asyncio backend provided by the production ASGI stack."""

    return "asyncio"


@pytest.mark.anyio
async def test_health_returns_service_metadata() -> None:
    """The liveness endpoint should be stable and require no dependencies."""

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "api",
        "version": "0.1.0",
    }
