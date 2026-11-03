from fastapi.testclient import TestClient
import pytest
import os

from app.main import create_app


@pytest.fixture(scope="session")
def managed_mongo(tmp_path_factory):
    executable = os.getenv("PRAMANA_TEST_MONGOD")
    if not executable:
        yield None
        return
    from backend.tests.local_mongo import LocalMongo
    service = LocalMongo(executable, tmp_path_factory.mktemp("pramana-disposable-mongo"))
    previous = os.environ.get("PRAMANA_TEST_MONGODB_URI")
    try:
        service.start()
        os.environ["PRAMANA_TEST_MONGODB_URI"] = service.uri
        yield service
    finally:
        service.stop()
        if previous is None:
            os.environ.pop("PRAMANA_TEST_MONGODB_URI", None)
        else:
            os.environ["PRAMANA_TEST_MONGODB_URI"] = previous


@pytest.fixture
def client() -> TestClient:
    with TestClient(create_app()) as test_client:
        yield test_client

