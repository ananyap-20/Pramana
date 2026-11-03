from dataclasses import replace
from io import BytesIO
import os
import subprocess
import sys
from threading import Event
import time

from PIL import Image
import pytest

from app.intake_models import IntakeLimits
from app.services.document_intake import DocumentIntakeError
from app.services.intake_process import WindowsJob, _stop, run_extraction
from app.services.pdf_image_intake import _ocr
from backend.tests.intake_fixtures import image_bytes, pdf_bytes
from backend.tests.test_pdf_image_intake import intake_client, upload, wait_extracted, confirmation, reference


@pytest.mark.parametrize("overrides,fragment,kind", [
    ({"max_pixels": 10}, "pixel", "pdf"),
    ({"max_total_pixels": 10}, "pixel", "pdf"),
    ({"max_characters": 10}, "character", "pdf"),
    ({"max_output_bytes": 1024}, "output", "pdf"),
    ({"max_regions": 1}, "region", "png"),
    ({"max_pixels": 10}, "pixel", "png"),
    ({"max_total_pixels": 10}, "pixel", "png"),
])
def test_real_resource_limits(intake_client, overrides, fragment, kind):
    store = intake_client.app.state.intake
    store.settings = replace(store.settings, intake_limits=IntakeLimits(**overrides))
    content, name, mime = (pdf_bytes(), "x.pdf", "application/pdf") if kind == "pdf" else (image_bytes(), "x.png", "image/png")
    if "max_output_bytes" in overrides:
        content = pdf_bytes(("text", "text"))
    created, headers = upload(intake_client, content, name, mime)
    result = wait_extracted(intake_client, created, headers)
    assert result["state"] == "failed", result
    assert fragment in result["error"], result


def test_upload_body_limit_before_multipart_and_parser(intake_client):
    response = intake_client.post("/api/intake", content=b"x" * (5 * 1024 * 1024 + 16385),
                                  headers={"Content-Type": "multipart/form-data; boundary=missing"})
    assert response.status_code == 413
    assert intake_client.app.state.intake.jobs == {}


def test_configured_byte_limit(intake_client):
    store = intake_client.app.state.intake
    store.settings = replace(store.settings, intake_limits=IntakeLimits(max_bytes=20))
    response = intake_client.post("/api/intake", data={"brand_id": "lumadesk"}, files={"file": ("x.pdf", pdf_bytes(), "application/pdf")})
    assert response.status_code == 413


@pytest.mark.parametrize("kind", ["truncated", "animated", "wrong-parser-type"])
def test_image_parser_failures(intake_client, kind):
    if kind == "truncated":
        content = b"\x89PNG\r\n\x1a\nBAD"
    elif kind == "animated":
        output = BytesIO()
        a = Image.new("RGB", (30, 30), "white")
        b = Image.new("RGB", (30, 30), "black")
        a.save(output, "PNG", save_all=True, append_images=[b], duration=100)
        content = output.getvalue()
    else:
        content = b"\x89PNG\r\n\x1a\n" + image_bytes("JPEG")
    created, headers = upload(intake_client, content, "x.png", "image/png")
    result = wait_extracted(intake_client, created, headers)
    assert result["state"] == "failed"


def test_confirmation_schema_missing_pages_whitespace_and_version_limit(intake_client):
    client = intake_client
    store = client.app.state.intake
    store.settings = replace(store.settings, intake_limits=IntakeLimits(max_versions=2))
    created, headers = upload(client)
    job = wait_extracted(client, created, headers)
    url = f"/api/intake/{job['extraction_id']}/confirm"
    request = confirmation(job)
    for invalid in ({**request, "ready": True}, {**request, "confirm_transcription": False},
                    {**request, "page_texts": []}, {**request, "page_texts": ["   "]},
                    {**request, "page_texts": ["a", "b"]}, {**request, "page_texts": ["\x00"]}):
        assert client.post(url, json=invalid, headers=headers).status_code == 422
    assert client.post(url, json={**request, "page_texts": ["x" * 100001]}, headers=headers).status_code == 413
    ready = client.post(url, json=request, headers=headers).json()
    assert client.post(url, json=confirmation(ready, ["Changed"]), headers=headers).status_code == 409


def test_tokens_cannot_read_confirm_or_decide_other_extractions(intake_client):
    client = intake_client
    content = pdf_bytes()
    created_a, token_a = upload(client, content)
    a = wait_extracted(client, created_a, token_a)
    created_b, token_b = upload(client, content)
    b = wait_extracted(client, created_b, token_b)
    base = f"/api/intake/{a['extraction_id']}"
    for suffix in ("", "/original", "/versions/1", "/pages/1/preview"):
        assert client.get(base + suffix, headers=token_b).status_code == 404
    for suffix, body in (("/confirm", confirmation(a)), ("/analyze", reference(a)), ("/cancel", {})):
        assert client.post(base + suffix, json=body, headers=token_b).status_code == 404
    assert a["file_sha256"] == b["file_sha256"]  # Identical uploads still get separate capabilities and versions.
    assert a["extraction_id"] != b["extraction_id"]


def test_job_count_cap_and_reclamation(intake_client):
    client = intake_client
    store = client.app.state.intake
    store.settings = replace(store.settings, intake_limits=IntakeLimits(max_jobs=1))
    created, headers = upload(client)
    wait_extracted(client, created, headers)
    response = client.post("/api/intake", data={"brand_id": "lumadesk"}, files={"file": ("x.pdf", pdf_bytes(), "application/pdf")})
    assert response.status_code == 429
    client.post(f"/api/intake/{created['extraction_id']}/cancel", headers=headers)
    other, _ = upload(client)
    assert other["extraction_id"] != created["extraction_id"]
    assert len(store.jobs) == 1


@pytest.mark.parametrize("mode", ["success", "failure", "timeout", "cancel"])
def test_temporary_directory_cleanup(tmp_path, mode):
    cancelled = Event()
    limits = IntakeLimits(timeout_seconds=0.01) if mode == "timeout" else IntakeLimits()
    content = b"%PDF-1.7\nbroken" if mode == "failure" else pdf_bytes()
    if mode == "cancel":
        cancelled.set()
    if mode == "success":
        result, previews = run_extraction(content, "pdf", limits, "unused", None, cancelled, str(tmp_path))
        assert result.pages and previews
    else:
        with pytest.raises(DocumentIntakeError):
            run_extraction(content, "pdf", limits, "unused", None, cancelled, str(tmp_path))
    assert list(tmp_path.iterdir()) == []


def test_ocr_unknown_and_low_scores_are_preserved_as_uncertain(tmp_path, monkeypatch):
    # Failure-mode simulation only; real OCR is exercised in the integration suite.
    def simulated_process(command, **kwargs):
        if "--version" in command:
            return subprocess.CompletedProcess(command, 0, stdout=b"simulated OCR\n")
        (tmp_path / "ocr.tsv").write_text(
            "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
            "5\t1\t1\t1\t1\t1\t0\t0\t20\t10\t-1\tUnknown\n"
            "5\t1\t1\t1\t1\t2\t30\t0\t20\t10\t12\tword\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0)
    monkeypatch.setattr(subprocess, "run", simulated_process)
    text, regions, _ = _ocr(Image.new("RGB", (100, 40)), tmp_path, IntakeLimits(), "simulated", None)
    assert text == "Unknown word"
    assert [region.confidence for region in regions] == [None, 12]
    assert text[regions[1].start:regions[1].end] == "word"


def test_page_order_and_unchanged_page_coordinates_after_correction(intake_client):
    client = intake_client
    created, headers = upload(client, pdf_bytes(("text", "text")))
    job = wait_extracted(client, created, headers)
    pages = job["current"]["pages"]
    request = confirmation(job, ["🧭 A shorter first page.", pages[1]["text"]])
    ready = client.post(f"/api/intake/{job['extraction_id']}/confirm", json=request, headers=headers).json()
    new_pages = ready["current"]["pages"]
    assert new_pages[0]["regions"] == []
    assert new_pages[1]["regions"][0]["bounds"] == pages[1]["regions"][0]["bounds"]
    assert new_pages[1]["start"] == len(request["page_texts"][0]) + 2
    for page in new_pages:
        assert ready["current"]["text"][page["start"]:page["end"]] == page["text"]


def test_expiry_reaper_without_client_read(intake_client):
    client = intake_client
    created, headers = upload(client)
    wait_extracted(client, created, headers)
    stored = client.app.state.intake.jobs[created["extraction_id"]]
    stored.deadline = time.monotonic() - 1
    deadline = time.monotonic() + 2
    while stored.content and time.monotonic() < deadline:
        time.sleep(0.05)
    assert stored.state == "expired" and not stored.content and not stored.versions


@pytest.mark.skipif(os.name != "nt", reason="Windows Job Object containment is Windows-specific")
def test_windows_job_kills_descendant_process(tmp_path):
    # A child tries to create a marker after the entire job has been closed.
    marker = tmp_path / "escaped.txt"
    child = "import time,pathlib; time.sleep(1); pathlib.Path(" + repr(str(marker)) + ").write_text('escaped')"
    code = "import sys,subprocess,time; sys.stdin.read(1); subprocess.Popen([sys.executable,'-c'," + repr(child) + "]); print('spawned',flush=True); time.sleep(20)"
    process = subprocess.Popen([sys.executable, "-c", code], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    job = WindowsJob(process, 128)
    try:
        process.stdin.write("1")
        process.stdin.flush()
        assert process.stdout.readline().strip() == "spawned"
    finally:
        _stop(process, job)
    time.sleep(1.2)
    assert process.poll() is not None
    assert not marker.exists()


def test_intake_disabled_by_default(client):
    # Existing text/DOCX APIs remain available even when PDF/image opt-in is absent.
    if os.getenv("PRAMANA_ENABLE_LOCAL_INTAKE") == "1":
        return
    response = client.post("/api/intake", data={"brand_id": "lumadesk"}, files={"file": ("x.pdf", pdf_bytes(), "application/pdf")})
    assert response.status_code == 503
