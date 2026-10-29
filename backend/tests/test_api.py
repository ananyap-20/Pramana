from io import BytesIO

from docx import Document
from fastapi.testclient import TestClient


ALL_ISSUES_DRAFT = (
    "Our dashboard is guaranteed to eliminate all errors. "
    "Starter plan supports 50 team members. Features launch this quarter."
)


def _docx_bytes(*paragraphs: str) -> bytes:
    document = Document()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    stream = BytesIO()
    document.save(stream)
    return stream.getvalue()


def test_health_and_demo_configuration(client: TestClient) -> None:
    health = client.get("/health")
    config = client.get("/api/demo/config/lumadesk")

    assert health.status_code == 200
    assert health.json() == {"status": "ok", "persistence": "in_memory_demo_not_durable"}
    assert config.status_code == 200
    assert len(config.json()["rules"]) == 4
    assert "source_excerpt" not in config.json()


def test_analyze_all_issues_returns_only_versioned_validated_receipts(client: TestClient) -> None:
    response = client.post(
        "/api/reviews/analyze",
        json={"brand_id": "lumadesk", "draft_text": ALL_ISSUES_DRAFT},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["persistence"] == "in_memory_demo_not_durable"
    assert [finding["category"] for finding in payload["findings"]] == [
        "terminology",
        "prohibited_phrase",
        "conflicting_fact",
        "required_disclaimer",
    ]
    assert all(finding["validation_outcome"] == "validated" for finding in payload["findings"])
    assert all(finding["rule_version"] == "v1" for finding in payload["findings"])
    assert all(finding["source_version"] == "v1" for finding in payload["findings"])
    assert payload["findings"][2]["evidence_status"] == "Contradicted"
    assert payload["findings"][3]["flagged_text"] is None
    assert payload["findings"][3]["location"] is None
    assert payload["draft_text"] == ALL_ISSUES_DRAFT


def test_clean_draft_returns_zero_findings(client: TestClient) -> None:
    response = client.post(
        "/api/reviews/analyze",
        json={
            "brand_id": "lumadesk",
            "draft_text": "Our workspace helps teams coordinate project conversations.",
        },
    )

    assert response.status_code == 200
    assert response.json()["findings"] == []


def test_client_cannot_select_an_unapproved_brand_or_bypass_input_validation(
    client: TestClient,
) -> None:
    unknown_brand = client.post(
        "/api/reviews/analyze",
        json={"brand_id": "unapproved-brand", "draft_text": "A draft."},
    )
    empty_draft = client.post(
        "/api/reviews/analyze",
        json={"brand_id": "lumadesk", "draft_text": ""},
    )

    assert unknown_brand.status_code == 404
    assert unknown_brand.json()["detail"] == "No approved configuration exists for this brand."
    assert empty_draft.status_code == 422


def test_docx_analysis_uses_the_same_validated_pipeline(client: TestClient) -> None:
    response = client.post(
        "/api/reviews/analyze-document",
        data={"brand_id": "lumadesk"},
        files={
            "file": (
                "draft.docx",
                _docx_bytes(
                    "Our dashboard is guaranteed to eliminate all errors.",
                    "Starter plan supports 50 team members.",
                    "Features launch this quarter.",
                ),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["input_type"] == "docx"
    assert payload["paragraph_count"] == 3
    assert len(payload["findings"]) == 4
    assert all(finding["validation_outcome"] == "validated" for finding in payload["findings"])


def test_document_analysis_rejects_empty_malformed_and_unsupported_uploads(
    client: TestClient,
) -> None:
    empty = client.post(
        "/api/reviews/analyze-document",
        data={"brand_id": "lumadesk"},
        files={"file": ("empty.docx", _docx_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    malformed = client.post(
        "/api/reviews/analyze-document",
        data={"brand_id": "lumadesk"},
        files={"file": ("broken.docx", b"not a DOCX", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    unsupported = client.post(
        "/api/reviews/analyze-document",
        data={"brand_id": "lumadesk"},
        files={"file": ("draft.txt", b"plain text", "text/plain")},
    )

    assert empty.status_code == 422
    assert "readable paragraph text" in empty.json()["detail"]
    assert malformed.status_code == 422
    assert "not a valid" in malformed.json()["detail"]
    assert unsupported.status_code == 422
    assert "Only .docx" in unsupported.json()["detail"]


def test_document_analysis_rejects_extracted_text_over_analysis_limit(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/reviews/analyze-document",
        data={"brand_id": "lumadesk"},
        files={
            "file": (
                "large.docx",
                _docx_bytes("x" * 100_001),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert response.status_code == 413
    assert "100,000-character" in response.json()["detail"]


def test_review_decision_is_recorded_and_returned_in_history(client: TestClient) -> None:
    analysis = client.post(
        "/api/reviews/analyze",
        json={"brand_id": "lumadesk", "draft_text": ALL_ISSUES_DRAFT},
    ).json()
    run_id = analysis["review_run_id"]

    decision = client.post(
        f"/api/reviews/{run_id}/decision",
        json={"decision": "revision"},
    )
    history = client.get("/api/reviews/history/lumadesk")

    assert decision.status_code == 200
    assert decision.json()["review_run_id"] == run_id
    assert decision.json()["decision"] == "revision"
    assert history.status_code == 200
    record = next(item for item in history.json() if item["review_run_id"] == run_id)
    assert record["finding_count"] == 4
    assert record["current_decision"] == "revision"
    assert record["decision_history"][0]["decision"] == "revision"
    assert "draft_text" not in record


def test_review_decision_can_be_updated_and_invalid_or_unknown_requests_fail(
    client: TestClient,
) -> None:
    analysis = client.post(
        "/api/reviews/analyze",
        json={"brand_id": "lumadesk", "draft_text": "A clean workspace draft."},
    ).json()
    run_id = analysis["review_run_id"]

    updated = client.post(
        f"/api/reviews/{run_id}/decision",
        json={"decision": "approved"},
    )
    revision = client.post(
        f"/api/reviews/{run_id}/decision",
        json={"decision": "revision"},
    )
    invalid = client.post(
        f"/api/reviews/{run_id}/decision",
        json={"decision": "auto_publish"},
    )
    unknown = client.post(
        "/api/reviews/missing-run/decision",
        json={"decision": "rejected"},
    )

    assert updated.status_code == 200
    assert revision.status_code == 200
    assert invalid.status_code == 422
    assert unknown.status_code == 404
    record = next(
        item
        for item in client.get("/api/reviews/history/lumadesk").json()
        if item["review_run_id"] == run_id
    )
    assert record["finding_count"] == 0
    assert [event["decision"] for event in record["decision_history"]] == [
        "approved",
        "revision",
    ]
    assert record["current_decision"] == "revision"

