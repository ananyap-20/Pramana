"""Exercise configured MongoDB through the API twice. Only fictional data is written."""

from pathlib import Path
import sys
from uuid import uuid4
import argparse
from io import BytesIO
from unittest.mock import patch
from contextlib import nullcontext
from docx import Document

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from fastapi.testclient import TestClient
from app.main import create_app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simulate-bunny", action="store_true", help="Test original retention against real MongoDB with simulated object transport, not the Bunny provider.")
    args = parser.parse_args()
    objects = {}
    class SimulatedStorage:
        def check_ready(self):
            pass
        def request(self, method, key, content=None):
            if method == "PUT":
                objects[key] = content
            elif method == "GET":
                return objects[key]
            elif method == "DELETE":
                objects.pop(key, None)
    transport = patch("app.audit_api.BunnyStorage.from_environment", lambda: SimulatedStorage()) if args.simulate_bunny else nullcontext()
    transport.__enter__()
    token_file = Path(".env.audit.access-key")
    if not token_file.exists():
        print("FAIL: private audit access-key file is missing.")
        return 1
    headers = {"Authorization": "Bearer " + token_file.read_text().strip(), "Idempotency-Key": str(uuid4())}
    run_id = None
    try:
        with TestClient(create_app()) as client:
            document = Document()
            document.add_paragraph("Fictional deployment check. Our dashboard is guaranteed to eliminate all errors.")
            buffer = BytesIO()
            document.save(buffer)
            original = buffer.getvalue()
            response = client.post("/api/audit/reviews/analyze-document", headers=headers,
                data={"brand_id": "lumadesk"}, files={"file": ("check.docx", original)})
            if response.status_code != 200:
                raise RuntimeError("Analysis failed")
            run_id = response.json()["review_run_id"]
            response = client.post(f"/api/audit/reviews/{run_id}/decision", headers={**headers, "Idempotency-Key": str(uuid4())},
                json={"decision": "revision", "expected_revision": 0})
            if response.status_code != 200:
                raise RuntimeError("Decision failed")
        with TestClient(create_app()) as client:
            review = client.get(f"/api/audit/reviews/{run_id}", headers=headers)
            snapshot = client.get(f"/api/audit/reviews/{run_id}/snapshot", headers=headers)
            if review.status_code != 200 or review.json()["current_decision"] != "revision" or snapshot.status_code != 200:
                raise RuntimeError("Restart verification failed")
            print("PASS: encrypted evidence and decision survived application restart using real MongoDB.")
            if client.app.state.audit.files:
                restored = client.get(f"/api/audit/reviews/{run_id}/original", headers=headers)
                if restored.status_code != 200 or restored.content != original:
                    raise RuntimeError("Original replay failed")
                print("PASS: original survived restart (SIMULATED Bunny transport)." if args.simulate_bunny else "PASS: original survived restart using Bunny Storage.")
            forbidden = client.get(f"/api/audit/reviews/{run_id}")
            if forbidden.status_code != 401:
                raise RuntimeError("Authentication check failed")
            print("PASS: anonymous access rejected.")
        return 0
    except Exception as error:
        print("FAIL: audit check stopped (" + type(error).__name__ + "). No credentials printed.")
        return 1
    finally:
        if run_id:
            try:
                with TestClient(create_app()) as client:
                    response = client.delete(f"/api/audit/reviews/{run_id}", headers=headers)
                    print("Removed this check's review." if response.status_code == 204 else "Check review cleanup manually.")
            except Exception:
                print("Check review cleanup manually.")
        transport.__exit__(None, None, None)


if __name__ == "__main__":
    raise SystemExit(main())
