"""Reproducible fictional-fixture quality/timing report; no hosted claims."""

from datetime import UTC, datetime
from difflib import SequenceMatcher
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]

from fastapi.testclient import TestClient
from app.main import create_app
from backend.tests.intake_fixtures import HELD_OUT, PARAGRAPHS, image_bytes, pdf_bytes


def main():
    os.environ["PRAMANA_ENABLE_LOCAL_INTAKE"] = "1"
    local = ROOT / "tmp/ocr-runtime/tesseract/tesseract.exe"
    if local.exists() and not os.getenv("TESSERACT_CMD"):
        os.environ["TESSERACT_CMD"] = str(local)
        os.environ["TESSDATA_DIR"] = str(local.parent / "tessdata")
    cases = [(f"held-out-{i}.pdf", pdf_bytes(("text", "text"), text), list(text) * 2, "application/pdf")
             for i, text in enumerate(HELD_OUT, 1)]
    cases += [("scan.pdf", pdf_bytes(("scan",)), list(PARAGRAPHS), "application/pdf"),
              ("image.png", image_bytes(), list(PARAGRAPHS), "image/png"),
              ("image.jpg", image_bytes("JPEG"), list(PARAGRAPHS), "image/jpeg")]
    report = {"timestamp_utc": datetime.now(UTC).isoformat(), "environment": sys.version, "cases": []}
    with TestClient(create_app()) as client:
        report["readiness"] = client.get("/api/intake/health").json()
        assert report["readiness"]["ocr_ready"], "Real OCR is required for this report."
        for name, content, expected, mime in cases:
            started = time.perf_counter()
            response = client.post("/api/intake", data={"brand_id": "lumadesk"}, files={"file": (name, content, mime)})
            ack = time.perf_counter() - started
            assert response.status_code == 202, response.text
            job = response.json()
            headers = {"Authorization": f"Bearer {job['access_token']}"}
            base = f"/api/intake/{job['extraction_id']}"
            deadline = time.monotonic() + 75
            while job["state"] in ("queued", "processing") and time.monotonic() < deadline:
                time.sleep(0.03)
                job = client.get(base, headers=headers).json()
            assert job["state"] == "needs_confirmation", job
            actual = job["current"]["text"]
            cursor = 0
            recovered = 0
            for paragraph in expected:
                found = actual.find(paragraph, cursor)
                if found >= 0:
                    recovered += 1
                    cursor = found + len(paragraph)
            reference = " ".join(expected)
            normalized = " ".join(actual.split())
            confirmed = client.post(base + "/confirm", headers=headers, json={
                "version": job["current"]["version"], "text_sha256": job["current"]["text_sha256"],
                "page_texts": [p["text"] for p in job["current"]["pages"]], "confirm_transcription": True,
            }).json()
            started = time.perf_counter()
            analysis = client.post(base + "/analyze", headers=headers, json={key: confirmed["current"][key] for key in ("version", "text_sha256")})
            analysis_seconds = time.perf_counter() - started
            assert analysis.status_code == 200, analysis.text
            report["cases"].append({"file": name, "file_sha256": hashlib.sha256(content).hexdigest(),
                                    "paragraphs_expected": len(expected), "paragraphs_recovered_in_order": recovered,
                                    "normalized_text_exact": normalized == reference,
                                    "character_similarity": SequenceMatcher(None, reference, normalized).ratio(),
                                    "upload_ack_seconds": round(ack, 4), "extraction_seconds": job["extraction_seconds"],
                                    "analysis_seconds": round(analysis_seconds, 4), "tools": job["tools"]})
            client.post(base + "/cancel", headers=headers)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
