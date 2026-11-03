"""Public entry and retained review behavior through the actual application."""
import base64
import json
from uuid import uuid4

from fastapi.testclient import TestClient
import mongomock
import pytest

from app.main import create_app


def test_fresh_visitor_uses_real_routes_without_session(client):
    assert client.get('/ready').json()['status'] == 'ok'
    assert client.get('/api/demo/config/lumadesk').status_code == 200
    response = client.post('/api/reviews/analyze', json={'brand_id': 'lumadesk', 'draft_text': '🙂 dashboard'})
    assert response.status_code == 200
    result = response.json()
    assert result['draft_text'] == '🙂 dashboard'
    assert client.post(f"/api/reviews/{result['review_run_id']}/decision", json={'decision': 'revision'}).status_code == 200
    paths = client.get('/openapi.json').json()['paths']
    assert not any('/auth/' in path for path in paths)
    assert client.get('/api/auth/session').status_code == 404
    assert not response.cookies


@pytest.mark.parametrize('text', [' ', '\x00dashboard', '\ud800'])
def test_invalid_text_returns_safe_error_without_echoing_input(client, text):
    response = client.post('/api/reviews/analyze', content=json.dumps({'brand_id': 'lumadesk', 'draft_text': text}),
                           headers={'Content-Type': 'application/json'})
    assert response.status_code == 422
    assert 'dashboard' not in response.text


def test_shared_retained_reviews_preserve_evidence_decisions_and_old_partitions(monkeypatch):
    database = mongomock.MongoClient(tz_aware=True)
    monkeypatch.setenv('MONGODB_URI', 'mongodb://localhost:27017')
    monkeypatch.setenv('MONGODB_DB', 'no_auth_test')
    monkeypatch.setenv('PRAMANA_AUDIT_KEYS', json.dumps({'test': base64.b64encode(b'x' * 32).decode()}))
    monkeypatch.setenv('PRAMANA_AUDIT_ACTIVE_KEY', 'test')
    monkeypatch.setattr('app.repositories.mongodb_repository.MongoClient', lambda *a, **k: database)
    monkeypatch.setattr('app.repositories.audit_repository.MongoClient', lambda *a, **k: database)
    database.no_auth_test.identity_reviews_v1.insert_one({'_id': 'old-private-run'})
    with TestClient(create_app()) as client:
        assert client.get('/ready').json()['audit'] is True
        headers = {'Idempotency-Key': str(uuid4())}
        response = client.post('/api/audit/reviews/analyze', headers=headers,
            json={'brand_id': 'lumadesk', 'draft_text': '🙂 dashboard'})
        assert response.status_code == 200, response.text
        result = response.json()
        run = result['review_run_id']
        assert client.post('/api/audit/reviews/analyze', headers=headers,
            json={'brand_id': 'lumadesk', 'draft_text': '🙂 dashboard'}).json() == result
        assert client.get(f'/api/audit/reviews/{run}').json()['current_decision'] is None
        decision = client.post(f'/api/audit/reviews/{run}/decision', headers={'Idempotency-Key': str(uuid4())},
            json={'decision': 'revision', 'expected_revision': 0})
        assert decision.status_code == 200, decision.text
        assert decision.json()['actor_id'] == 'anonymous_reviewer'
        assert client.get('/api/audit/reviews/old-private-run/snapshot').status_code == 404
        assert client.delete(f'/api/audit/reviews/{run}').status_code == 405
    with TestClient(create_app()) as restarted:
        assert restarted.get(f'/api/audit/reviews/{run}/snapshot').json()['analysis'] == result
        assert restarted.get(f'/api/audit/reviews/{run}').json()['current_decision'] == 'revision'
    assert database.no_auth_test.identity_reviews_v1.count_documents({}) == 1


def test_public_json_body_is_bounded_before_parsing(client):
    response = client.post('/api/reviews/analyze', content=b'x' * (416 * 1024 + 1))
    assert response.status_code == 413
    assert response.headers['cache-control'] == 'no-store'


def test_low_confidence_ocr_stays_visible_without_changing_text(tmp_path, monkeypatch):
    from PIL import Image
    from app.intake_models import IntakeLimits, TextRegion
    from app.services.pdf_image_intake import extract_pdf_image
    image = tmp_path / 'input.png'
    Image.new('RGB', (120, 40), 'white').save(image)
    text = 'uncertain dashboard'
    monkeypatch.setattr('app.services.pdf_image_intake._ocr', lambda *args: (
        text, (TextRegion(start=0, end=len(text), bounds=(0, 0, 120, 40), confidence=12),), 'test-ocr'))
    result = extract_pdf_image(image, 'png', tmp_path, IntakeLimits(), '', None)
    assert result.pages[0].text == text
    assert result.pages[0].regions[0].confidence == 12
    assert any('low or missing OCR confidence' in warning for warning in result.pages[0].warnings)
