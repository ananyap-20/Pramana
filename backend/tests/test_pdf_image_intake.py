from dataclasses import replace
from io import BytesIO
import os
from pathlib import Path
import time

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from app.main import create_app
from app.intake_models import IntakeLimits
from app.services.document_intake import DocumentIntakeError, DocumentIntakeTooLargeError
from app.services.intake_process import run_extraction
from app.services.extraction_store import validate_upload
from backend.tests.intake_fixtures import PARAGRAPHS, image_bytes, pdf_bytes


@pytest.fixture
def intake_client(monkeypatch):
    monkeypatch.setenv("PRAMANA_ENABLE_LOCAL_INTAKE", "1")
    local = Path("tmp/ocr-runtime/tesseract/tesseract.exe").resolve()
    if local.is_file() and not os.getenv("TESSERACT_CMD"):
        monkeypatch.setenv("TESSERACT_CMD", str(local))
        monkeypatch.setenv("TESSDATA_DIR", str(local.parent / "tessdata"))
    with TestClient(create_app()) as client:
        yield client


def upload(client, content=None, name="draft.pdf", mime="application/pdf"):
    response = client.post("/api/intake", data={"brand_id": "lumadesk"},
                           files={"file": (name, pdf_bytes() if content is None else content, mime)})
    assert response.status_code == 202, response.text
    job = response.json()
    return job, {"Authorization": f"Bearer {job['access_token']}"}


def wait_extracted(client, job, headers):
    deadline = time.monotonic() + 75
    while time.monotonic() < deadline:
        response = client.get(f"/api/intake/{job['extraction_id']}", headers=headers)
        assert response.status_code == 200, response.text
        result = response.json()
        if result["state"] not in ("queued", "processing"):
            return result
        time.sleep(0.04)
    pytest.fail("Worker did not reach a terminal state before the test deadline.")


def confirmation(job, page_texts=None):
    current = job["current"]
    return {"version": current["version"], "text_sha256": current["text_sha256"],
            "page_texts": [p["text"] for p in current["pages"]] if page_texts is None else page_texts,
            "confirm_transcription": True}


def reference(job):
    return {key: job["current"][key] for key in ("version", "text_sha256")}


def test_real_pdf_confirmation_correction_receipts_and_private_decisions(intake_client):
    client = intake_client
    created, headers = upload(client)
    base = f"/api/intake/{created['extraction_id']}"
    extracted = wait_extracted(client, created, headers)
    assert extracted["state"] == "needs_confirmation", extracted
    assert all(text in extracted["current"]["text"] for text in PARAGRAPHS)
    assert extracted["current"]["pages"][0]["method"] == "pdf_text"
    assert client.post(base + "/analyze", json=reference(extracted), headers=headers).status_code == 409
    assert client.get(base).status_code == 404
    assert client.get(base, headers={"Authorization": "Bearer wrong"}).status_code == 404
    preview = client.get(base + "/pages/1/preview", headers=headers)
    assert preview.content.startswith(b"\x89PNG")
    assert preview.headers["cache-control"] == "no-store"
    assert client.get(base + "/original", headers=headers).content.startswith(b"%PDF-")
    corrected = "🧭 Café: Our dashboard helps teams.\nStarter plan supports 50 team members."
    request = confirmation(extracted, [corrected])
    ready = client.post(base + "/confirm", json=request, headers=headers).json()
    assert ready["state"] == "ready"
    assert ready["confirmation"]["actor"] is None
    assert ready["current"]["version"] == 2
    assert ready["current"]["human_edited"]
    assert ready["current"]["pages"][0]["regions"] == []
    assert ready["current"]["pages"][0]["coordinates"] == "none"
    assert client.post(base + "/confirm", json=request, headers=headers).json() == ready
    original_version = client.get(base + "/versions/1", headers=headers).json()
    assert original_version["text"] == extracted["current"]["text"]
    stale = client.post(base + "/analyze", json=reference(extracted), headers=headers)
    assert stale.status_code == 409
    tampered = {**reference(ready), "text_sha256": "0" * 64}
    assert client.post(base + "/analyze", json=tampered, headers=headers).status_code == 409
    analysis = client.post(base + "/analyze", json=reference(ready), headers=headers)
    assert analysis.status_code == 200, analysis.text
    result = analysis.json()
    assert result["draft_text"] == corrected
    assert result["document_provenance"]["text_sha256"] == ready["current"]["text_sha256"]
    assert result["document_provenance"]["actor"] is None
    for finding in result["findings"]:
        location = finding["location"]
        if location:
            assert corrected[location["start"]:location["end"]] == finding["flagged_text"]
        else:
            assert finding["flagged_text"] is None
    assert client.post(base + "/analyze", json=reference(ready), headers=headers).json() == result
    run_id = result["review_run_id"]
    assert client.get("/api/reviews/history/lumadesk").json() == []
    assert client.post(f"/api/reviews/{run_id}/decision", json={"decision": "approved"}).status_code == 404
    decision_url = base + f"/reviews/{run_id}/decision"
    assert client.post(decision_url, json={"decision": "approved"}).status_code == 404
    assert client.post(decision_url, json={"decision": "approved"}, headers=headers).status_code == 200
    revised = client.post(base + "/confirm", json=confirmation(ready, ["Changed workspace text."]), headers=headers)
    assert revised.status_code == 200
    assert client.post(decision_url, json={"decision": "approved"}, headers=headers).status_code == 409
    assert client.get(base + "/versions/2", headers=headers).json()["text"] == corrected
    client.post(base + "/cancel", headers=headers)
    assert client.get(base, headers=headers).json()["state"] == "expired"
    assert client.get(base + "/original", headers=headers).status_code == 410
    assert client.post(base + "/confirm", json=confirmation(ready), headers=headers).status_code == 410


@pytest.mark.parametrize("kind,name,mime", [("scan", "scan.pdf", "application/pdf"),
                                          ("mixed", "mixed.pdf", "application/pdf"),
                                          ("png", "scan.png", "image/png"),
                                          ("jpeg", "scan.jpg", "image/jpeg")])
def test_real_ocr_journey(intake_client, kind, name, mime):
    client = intake_client
    if not client.get("/api/intake/health").json()["ocr_ready"]:
        if os.getenv("REQUIRE_REAL_OCR") == "1":
            pytest.fail("Real OCR is required but Tesseract English data is unavailable.")
        pytest.skip("Install Tesseract English data; a skip does not verify OCR support.")
    content = (pdf_bytes(("scan",)) if kind == "scan" else pdf_bytes(("text", "scan", "hybrid"))
               if kind == "mixed" else image_bytes("PNG" if kind == "png" else "JPEG"))
    created, headers = upload(client, content, name, mime)
    job = wait_extracted(client, created, headers)
    assert job["state"] == "needs_confirmation", job
    assert "tesseract" in job["tools"]
    pages = job["current"]["pages"]
    for page in pages[:2] if kind == "mixed" else pages:
        for expected in PARAGRAPHS:
            assert expected in page["text"]
            assert page["text"].count(expected) == 1
    if kind == "mixed":
        assert [p["method"] for p in pages] == ["pdf_text", "ocr", "ocr"]
        assert "raster note" in pages[2]["text"]
    base = f"/api/intake/{created['extraction_id']}"
    assert client.post(base + "/analyze", json=reference(job), headers=headers).status_code == 409
    ready = client.post(base + "/confirm", json=confirmation(job), headers=headers).json()
    result = client.post(base + "/analyze", json=reference(ready), headers=headers)
    assert result.status_code == 200, result.text
    assert result.json()["draft_text"] == ready["current"]["text"]


@pytest.mark.parametrize("content,name,mime", [(b"", "x.pdf", "application/pdf"),
                                               (b"not a pdf", "x.pdf", "application/pdf"),
                                               (b"%PDF-1.7", "x.exe", "application/pdf"),
                                               (b"%PDF-1.7", "x.pdf", "image/png")])
def test_upload_validation(intake_client, content, name, mime):
    response = intake_client.post("/api/intake", data={"brand_id": "lumadesk"}, files={"file": (name, content, mime)})
    assert response.status_code == 422


@pytest.mark.parametrize("content", [b"%PDF-1.7\nbroken", pdf_bytes(encrypted=True), pdf_bytes(("blank",))], ids=["malformed", "encrypted", "blank"])
def test_bad_documents_fail_without_analysis(intake_client, content):
    created, headers = upload(intake_client, content)
    job = wait_extracted(intake_client, created, headers)
    assert job["state"] == "failed", job
    assert job["error"]
    assert job["current"] is None


def test_missing_ocr_and_timeout_cleanup(intake_client):
    client = intake_client
    store = client.app.state.intake
    store.settings = replace(store.settings, tesseract_cmd="definitely-missing-tesseract")
    created, headers = upload(client, image_bytes(), "x.png", "image/png")
    job = wait_extracted(client, created, headers)
    assert job["state"] == "failed" and "OCR is unavailable" in job["error"], job
    store.settings = replace(store.settings, intake_limits=IntakeLimits(timeout_seconds=0.01))
    created, headers = upload(client)
    job = wait_extracted(client, created, headers)
    assert job["state"] == "failed" and "timed out" in job["error"], job


def test_limits_and_expiration(intake_client):
    client = intake_client
    store = client.app.state.intake
    store.settings = replace(store.settings, intake_limits=IntakeLimits(max_pages=1))
    created, headers = upload(client, pdf_bytes(("text", "text")))
    job = wait_extracted(client, created, headers)
    assert job["state"] == "failed" and "page limit" in job["error"]
    store.settings = replace(store.settings, intake_limits=IntakeLimits())
    created, headers = upload(client)
    job = wait_extracted(client, created, headers)
    stored = store.jobs[job["extraction_id"]]
    stored.deadline = time.monotonic() - 1
    assert client.get(f"/api/intake/{job['extraction_id']}", headers=headers).json()["state"] == "expired"
    assert not stored.content and not stored.versions and not stored.previews


def test_capacity_is_bounded_and_health_stays_responsive(intake_client):
    client = intake_client
    first, headers = upload(client, pdf_bytes(("scan",) * 6))
    started = time.monotonic()
    assert client.get("/health").status_code == 200
    assert time.monotonic() - started < 1
    response = client.post("/api/intake", data={"brand_id": "lumadesk"}, files={"file": ("other.pdf", pdf_bytes(), "application/pdf")})
    assert response.status_code == 429
    client.post(f"/api/intake/{first['extraction_id']}/cancel", headers=headers)


def test_names_are_never_paths():
    assert validate_upload("../../secret\\draft.pdf", "application/pdf", b"%PDF-1.7", 100)[0] == "draft.pdf"
