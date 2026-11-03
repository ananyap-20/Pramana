from fastapi.testclient import TestClient
import pytest

from app.main import create_app


@pytest.fixture(autouse=True)
def legacy_api_harness(request, monkeypatch):
    """Historical engine/intake/audit tests exercise their original inner API.

    Identity acceptance tests run the actual outer middleware. There is no
    environment switch or application setting that disables authentication.
    """
    if request.module.__name__.rsplit(".", 1)[-1].startswith("test_identity"):
        return
    async def inner_api(self, scope, receive, send):
        return await self.app(scope, receive, send)
    monkeypatch.setattr("app.identity_api.IdentityMiddleware.__call__", inner_api)


@pytest.fixture
def client() -> TestClient:
    with TestClient(create_app()) as test_client:
        yield test_client

