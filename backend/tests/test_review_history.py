"""Tests for the review history endpoint and repository retrieval."""

from fastapi.testclient import TestClient


ALL_ISSUES_DRAFT = (
    "Our dashboard is guaranteed to eliminate all errors. "
    "Starter plan supports 50 team members. Features launch this quarter."
)


def test_review_history_starts_empty(client: TestClient) -> None:
    response = client.get("/api/reviews/history/lumadesk")

    assert response.status_code == 200
    assert response.json() == []


def test_review_history_returns_prior_runs_after_analysis(client: TestClient) -> None:
    # Run two analyses to populate history
    clean = client.post(
        "/api/reviews/analyze",
        json={"brand_id": "lumadesk", "draft_text": "A clean workspace draft."},
    ).json()
    issues = client.post(
        "/api/reviews/analyze",
        json={"brand_id": "lumadesk", "draft_text": ALL_ISSUES_DRAFT},
    ).json()

    response = client.get("/api/reviews/history/lumadesk")
    assert response.status_code == 200
    runs = response.json()

    assert len(runs) == 2
    # Most recent first
    assert runs[0]["evaluated_at"] >= runs[1]["evaluated_at"]
    assert all(run["brand_id"] == "lumadesk" for run in runs)
    assert all("review_run_id" in run for run in runs)
    assert all("draft_id" in run for run in runs)
    counts = {run["review_run_id"]: run["finding_count"] for run in runs}
    assert counts[clean["review_run_id"]] == 0
    assert counts[issues["review_run_id"]] == 4
    assert all(run["current_decision"] is None for run in runs)


def test_review_history_returns_404_for_unknown_brand(client: TestClient) -> None:
    response = client.get("/api/reviews/history/nonexistent")
    assert response.status_code == 404
