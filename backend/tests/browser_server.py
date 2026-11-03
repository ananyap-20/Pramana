"""Test-only same-origin app server with a local encrypted-object transport."""
import os
from pathlib import Path

from fastapi.staticfiles import StaticFiles
from app.main import create_app


class LocalObjects:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def check_ready(self):
        return None

    def request(self, method, key, content=None):
        target = (self.root / key).resolve()
        if not target.is_relative_to(self.root):
            raise ValueError('Invalid test object path.')
        if method == 'PUT':
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        elif method == 'GET':
            return target.read_bytes()
        elif method == 'DELETE':
            target.unlink(missing_ok=True)


# Only this test server supplies the transport. Production storage code is unchanged.
from app.services.bunny_storage import BunnyStorage
BunnyStorage.from_environment = staticmethod(lambda: LocalObjects(os.environ['PRAMANA_TEST_OBJECTS']))
app = create_app()
app.mount('/', StaticFiles(directory=Path(__file__).resolve().parents[2] / 'frontend/dist', html=True))
