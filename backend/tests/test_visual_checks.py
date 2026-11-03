"""Labeled fictional fixtures for the supported static scope and failure boundaries."""

import asyncio
import base64
import hashlib
from io import BytesIO
import json
from pathlib import Path
import socket
import subprocess
import sys

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from app.domain import EvidenceStatus as S
from app.main import create_app
from app.repositories.visual_manifest import VisualManifestRepository, validate_manifest
from app.services.visual_checks import analyze_visual, VisualInputError
from app.services.visual_process import run_visual, VisualProblem
from app.visual_api import VisualBodyLimitMiddleware
from app.visual_models import VisualManifest, VisualRequest


STYLE = "color:#000;background-color:#fff;font-size:16px;font-weight:400"


def png(color="red"):
    stream = BytesIO()
    Image.new("RGB", (2, 2), color).save(stream, "PNG")
    return stream.getvalue()


@pytest.fixture
def manifest():
    return validate_manifest(VisualManifest(
        brand_id="fictional", version="visual-v1", approved=True, active=True,
        source_id="fixture-guide", source_version="1", source_text="Approved fictional fixture palette and exact logo.",
        source_excerpt="fictional fixture palette", logo_selectors=("#logo",),
        logo_sha256=(hashlib.sha256(png()).hexdigest(),),
        palette=({"selector": ".brand", "property": "color", "colors": ("#000",)},),
        text_exemptions=({"selector": ".wordmark", "reason": "logotype"},
                         {"selector": ".decoration", "reason": "pure_decoration"})))


def request(html=None, css="", content=None, **kwargs):
    return VisualRequest(brand_id="fictional", draft_id="draft-1", draft_version="v1",
        html=html or f'<p class="brand" style="{STYLE}">Fictional draft</p>', css=css,
        assets=({"asset_id": "image", "media_type": "image/png",
                 "content_base64": base64.b64encode(content).decode()},) if content is not None else (), **kwargs)


def checks(response, kind):
    return [f for f in response.findings if f.check == kind and f.result != "configured_target_absent"]


def test_supported_pair_and_configured_palette_and_provenance(manifest):
    req = request()
    result = analyze_visual(req, manifest)
    assert checks(result, "contrast")[0].evidence["ratio"] == 21
    assert checks(result, "contrast")[0].evidence_status == S.SUPPORTED
    assert checks(result, "palette")[0].result == "approved_color"
    assert result.draft_version == "v1" and result.source_excerpt in manifest.source_text
    assert result.input_sha256 == analyze_visual(req, manifest).input_sha256
    assert result.input_sha256 != analyze_visual(request(req.html + " "), manifest).input_sha256
    assert result.manifest_sha256 != analyze_visual(req, manifest.model_copy(update={"version": "visual-v2"})).manifest_sha256
    assert checks(result, "contrast")[0].evidence["html_start_tag"] in req.html


@pytest.mark.parametrize("color,expected", [("#767676", S.SUPPORTED), ("#777777", S.CONTRADICTED),
    ("rgb(118,118,118)", S.SUPPORTED), ("rgb(118,119,118)", S.CONTRADICTED)])
def test_near_normal_threshold_without_rounding(manifest, color, expected):
    req = request(f'<p style="{STYLE.replace("#000", color)}">Text</p>')
    finding = checks(analyze_visual(req, manifest), "contrast")[0]
    assert finding.evidence_status == expected
    assert finding.evidence["threshold"] == 4.5


@pytest.mark.parametrize("size,weight,threshold", [("24px", "400", 3), ("23.99px", "400", 4.5),
    ("14pt", "bold", 3), ("18.66px", "700", 4.5), ("18.67px", "700", 3), ("14pt", "600", 4.5)])
def test_large_text_threshold(manifest, size, weight, threshold):
    style = f"color:#949494;background-color:#fff;font-size:{size};font-weight:{weight}"
    finding = checks(analyze_visual(request(f'<p style="{style}">Text</p>'), manifest), "contrast")[0]
    assert finding.evidence["threshold"] == threshold
    assert finding.evidence_status == (S.SUPPORTED if threshold == 3 else S.CONTRADICTED)


@pytest.mark.parametrize("css", ["color:rgba(0,0,0,0.5)", "background-color:#ffffff80",
    "background-image:linear-gradient(white,black)", "opacity:0.5", "background:url(https://example.test/x)",
    "mix-blend-mode:multiply", "font-size:1rem", "color:var(--ink)", "filter:opacity(0.5)",
    "text-shadow:0 0 2px black", "transform:scale(0.5)"])
def test_uncertain_styles_never_pass(manifest, css):
    f = checks(analyze_visual(request(f'<p style="{STYLE};{css}">Text</p>'), manifest), "contrast")[0]
    assert f.evidence_status == S.INDETERMINATE and f.evidence["ratio"] is None


def test_inherited_compositing_and_missing_declarations_are_indeterminate(manifest):
    for html in [f'<div style="opacity:0.5"><p style="{STYLE}">Text</p></div>',
                 f'<div style="background-image:linear-gradient(white,black)"><p style="{STYLE}">Text</p></div>',
                 '<p>Unstyled</p>']:
        assert checks(analyze_visual(request(html), manifest), "contrast")[0].evidence_status == S.INDETERMINATE


@pytest.mark.parametrize("html,reason", [('<button disabled>Disabled</button>', "inactive_control"),
    ('<p hidden>Hidden</p>', "hidden_attribute"), ('<p class="wordmark">Brand</p>', "logotype"),
    ('<p class="decoration">Decoration</p>', "pure_decoration")])
def test_exemptions(manifest, html, reason):
    f = checks(analyze_visual(request(html), manifest), "contrast")[0]
    assert f.result == "exempt" and f.evidence["exemption"] == reason and f.evidence["ratio"] is None


def test_aria_hidden_is_not_a_visual_contrast_exemption(manifest):
    f = checks(analyze_visual(request(f'<p aria-hidden="true" style="{STYLE.replace("#000", "#ccc")}">Text</p>'), manifest), "contrast")[0]
    assert f.evidence_status == S.CONTRADICTED


def test_css_cascade_and_palette_only_targets(manifest):
    css = 'p {color:white} .brand {color:#f00} #target {color:black;background-color:white;font-size:12pt;font-weight:normal}'
    result = analyze_visual(request('<p id="target" class="brand">Text</p><p style="color:#f00">Other</p>', css), manifest)
    assert len(checks(result, "palette")) == 1
    assert checks(result, "palette")[0].result == "approved_color"
    assert checks(result, "contrast")[0].evidence["ratio"] == 21
    result = analyze_visual(request(f'<p class="brand" style="{STYLE.replace("#000", "#f00")}">Text</p>'), manifest)
    assert checks(result, "palette")[0].evidence_status == S.CONTRADICTED


@pytest.mark.parametrize("css", ['@import "https://example.test/x";', 'p:hover {color:#fff}',
    '@media print {p {color:white}}', r'p {c\6flor:white}', '/* comment */ p {color:white}'])
def test_unsupported_stylesheet_is_explicitly_indeterminate(manifest, css):
    result = analyze_visual(request(css=css), manifest)
    assert checks(result, "contrast")[0].evidence_status == S.INDETERMINATE
    assert checks(result, "palette")[0].evidence_status == S.INDETERMINATE


@pytest.mark.parametrize("attrs,result", [('alt="Chart: sales grew"', "description_present_quality_unverified"),
    ('alt=""', "declared_decorative"), ('alt="" role="presentation"', "declared_decorative"),
    ('', "missing_description"), ('alt="  "', "missing_description"),
    ('role="presentation"', "semantics_need_review"), ('aria-label="Chart"', "semantics_need_review")])
def test_alt_semantics(manifest, attrs, result):
    response = analyze_visual(request(f'<img src="asset:image" {attrs}>', content=png()), manifest)
    assert checks(response, "alt_text")[0].result == result


def test_empty_alt_interactive_is_not_automatically_decorative(manifest):
    r = analyze_visual(request('<a href="#x"><img src="asset:image" alt=""></a>', content=png()), manifest)
    assert checks(r, "alt_text")[0].result == "missing_description"


def test_logo_digest_exact_only_and_photos_not_logo_or_palette(manifest):
    for content, expected in [(png(), "exact_digest_match"), (png("blue"), "digest_not_listed")]:
        r = analyze_visual(request('<img id="logo" src="asset:image" alt="Fictional logo">', content=content), manifest)
        assert checks(r, "logo")[0].result == expected
    r = analyze_visual(request('<img src="asset:image" alt="Photograph">', content=png()), manifest)
    assert not checks(r, "logo") and not checks(r, "palette")
    assert any(f.result == "configured_target_absent" for f in r.findings)


@pytest.mark.parametrize("content", [b"not an image", b"<svg onload='evil()'></svg>", png()[:20]])
def test_invalid_assets(manifest, content):
    with pytest.raises(VisualInputError, match="Invalid asset"):
        analyze_visual(request('<img src="asset:image" alt="X">', content=content), manifest)


def test_asset_size_and_type_and_missing_reference(manifest):
    content = BytesIO()
    Image.new("RGB", (1001, 1000)).save(content, "PNG")
    with pytest.raises(VisualInputError):
        analyze_visual(request(content=content.getvalue()), manifest)
    req = request(content=png())
    bad = req.model_copy(update={"assets": (req.assets[0].model_copy(update={"media_type": "image/jpeg"}),)})
    with pytest.raises(VisualInputError):
        analyze_visual(bad, manifest)
    with pytest.raises(VisualInputError):
        analyze_visual(request('<img src="asset:absent" alt="X">'), manifest)


@pytest.mark.parametrize("html", ['<script>fetch("https://example.test")</script>', '<p onclick="evil()">X</p>',
    '<img src="https://example.test/x">', '<iframe src="https://example.test"></iframe>',
    '<svg><script>evil()</script></svg>', '<object data="file:///secret"></object>',
    '<a href="javascript:evil()">X</a>', '<style>p{color:red}</style>', '<p id="a" id="b">X</p>',
    '<p><div>X</p></div>', '<?execute evil?>', '<!DOCTYPE html SYSTEM "file:///secret">'])
def test_active_or_ambiguous_html_rejected(manifest, html):
    with pytest.raises(VisualInputError):
        analyze_visual(request(html), manifest)


def test_dom_depth_and_node_limits(manifest):
    for html in ['<div>' * 33 + 'X' + '</div>' * 33, '<p>X</p>' * 1001]:
        with pytest.raises(VisualInputError, match="DOM limit"):
            analyze_visual(request(html), manifest)


@pytest.fixture
def client(monkeypatch, tmp_path, manifest):
    path = tmp_path / "manifest.json"
    path.write_text(manifest.model_dump_json(), encoding="utf-8")
    monkeypatch.setenv("PRAMANA_VISUAL_MANIFEST_PATH", str(path))
    monkeypatch.delenv("MONGODB_URI", raising=False)
    with TestClient(create_app()) as c:
        yield c


def test_real_worker_api_contract_and_private_response(client):
    req = request('<img id="logo" src="asset:image" alt="Logo">' + request().html, content=png())
    response = client.post('/api/visual/analyze', json=req.model_dump(mode="json"))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["schema_version"] == "1.0" and body["mode"] == "static_declarations"
    assert {f["check"] for f in body["findings"]} == {"logo", "palette", "contrast", "alt_text"}
    assert response.headers["cache-control"] == "no-store"
    assert body["assets_sha256"]["image"] == hashlib.sha256(png()).hexdigest()


def test_api_validation_and_body_limit(client):
    assert client.post('/api/visual/analyze', json={}).status_code == 422
    req = request().model_dump(mode="json")
    req["approved"] = True
    assert client.post('/api/visual/analyze', json=req).status_code == 422
    req.pop("approved")
    req["brand_id"] = "unknown"
    assert client.post('/api/visual/analyze', json=req).status_code == 404
    assert client.post('/api/visual/analyze', content=b'x' * (768 * 1024 + 1)).status_code == 413
    assert "PRIVATE" not in client.post('/api/visual/analyze', content=b'PRIVATE invalid JSON').text
    schema = client.get('/openapi.json').json()
    assert schema["paths"]["/api/visual/analyze"]["post"]["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith("/VisualRequest")
    assert schema["paths"]["/api/visual/analyze"]["post"]["responses"]["422"]["content"]["application/json"]["schema"]["$ref"].endswith("/VisualError")


def test_worker_safe_error_and_actual_deadline(manifest, monkeypatch):
    with pytest.raises(VisualProblem) as error:
        run_visual(request('<script>evil()</script>'), manifest)
    assert error.value.status == 422 and "evil" not in str(error.value)
    children = []
    original = subprocess.Popen
    def tracked(*args, **kwargs):
        child = original(*args, **kwargs)
        children.append(child)
        return child
    monkeypatch.setattr("app.services.visual_process.subprocess.Popen", tracked)
    with pytest.raises(VisualProblem) as error:
        run_visual(request(), manifest, timeout=0.000001)
    assert error.value.status == 408
    assert children[0].poll() is not None
    assert children[0].stdin.closed and children[0].stdout.closed
    # A timed-out process must release resources and allow a fresh real analysis.
    assert run_visual(request(), manifest).mode == "static_declarations"


def test_real_worker_unicode_jpeg_and_image_background(manifest):
    buffer = BytesIO()
    Image.new("RGB", (3, 3), "blue").save(buffer, "JPEG")
    req = request('<img src="asset:image" alt="चित्र">' + f'<p title="नमस्ते" style="{STYLE};background-image:url(asset:image)">Text</p>', content=buffer.getvalue())
    req = req.model_copy(update={"assets": (req.assets[0].model_copy(update={"media_type": "image/jpeg"}),)})
    result = run_visual(req, manifest)
    assert checks(result, "alt_text")[0].evidence["alt"] == "चित्र"
    assert checks(result, "contrast")[0].evidence_status == S.INDETERMINATE


def test_actual_worker_audit_guard_blocks_io():
    backend = str(Path(__file__).resolve().parents[1])
    code = f"""
import sys, socket, subprocess, os
sys.path.insert(0, {backend!r})
from app.services.visual_worker import forbid_io
sys.addaudithook(forbid_io)
for operation in (lambda: socket.socket(), lambda: open('never-created', 'w'),
                  lambda: subprocess.Popen([sys.executable, '-V']), lambda: os.system('echo blocked')):
    try:
        operation()
    except PermissionError:
        continue
    raise AssertionError('I/O guard failed')
print('blocked all four')
"""
    result = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, timeout=5)
    assert result.returncode == 0, result.stderr.decode()
    assert result.stdout.strip() == b"blocked all four"


@pytest.mark.parametrize("color,status", [("#949494", S.SUPPORTED), ("#959595", S.CONTRADICTED)])
def test_large_threshold_no_rounding(manifest, color, status):
    style = STYLE.replace("#000", color).replace("16px", "24px")
    finding = checks(analyze_visual(request(f'<p style="{style}">Text</p>'), manifest), "contrast")[0]
    assert finding.evidence_status == status and finding.evidence["threshold"] == 3


def test_hidden_attribute_overridden_by_css_not_exempt(manifest):
    result = analyze_visual(request(f'<p hidden style="{STYLE};display:block">Visible</p>'), manifest)
    assert checks(result, "contrast")[0].result != "exempt"


def test_result_limit(manifest):
    many_targets = manifest.model_copy(update={"palette": manifest.palette * 32})
    with pytest.raises(VisualInputError, match="1000-result"):
        analyze_visual(request('<p class="brand" style="color:#000">Text</p>' * 40), many_targets)


def test_no_active_manifest_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("PRAMANA_VISUAL_MANIFEST_PATH", raising=False)
    monkeypatch.delenv("MONGODB_URI", raising=False)
    with TestClient(create_app()) as client:
        assert client.post('/api/visual/analyze', json=request().model_dump(mode="json")).status_code == 404


def test_manifest_approval_and_grounding(tmp_path, manifest):
    path = tmp_path / "manifest.json"
    for changes in [{"approved": False}, {"active": False}]:
        path.write_text(manifest.model_copy(update=changes).model_dump_json())
        assert VisualManifestRepository(str(path)).get("fictional") is None
    for changes in [{"source_excerpt": "invented"}, {"logo_sha256": ("bad",)},
                    {"logo_selectors": ("p:hover",)}]:
        with pytest.raises(ValueError):
            validate_manifest(manifest.model_copy(update=changes))


def test_no_network_or_subprocess_during_static_analysis(monkeypatch, manifest):
    def forbidden(*args, **kwargs):
        pytest.fail("Static analysis attempted an external operation")
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    r = analyze_visual(request(css='@import "https://example.test";'), manifest)
    assert checks(r, "contrast")[0].evidence_status == S.INDETERMINATE


def test_chunked_body_timeout_and_capacity(monkeypatch):
    async def run():
        messages = []
        async def send(message):
            messages.append(message)
        async def receive():
            return {"type": "http.request", "body": b"x" * (768 * 1024 + 1)}
        async def unused(*args):
            pytest.fail("Oversized input reached the application")
        middleware = VisualBodyLimitMiddleware(unused)
        scope = {"type": "http", "path": "/api/visual/analyze", "method": "POST"}
        await middleware(scope, receive, send)
        assert messages[0]["status"] == 413 and middleware.active == 0
        messages.clear()
        middleware.active = 1
        await middleware(scope, receive, send)
        assert messages[0]["status"] == 429
        middleware.active = 0
        messages.clear()
        async def timeout_receive():
            raise TimeoutError()
        await middleware(scope, timeout_receive, send)
        assert messages[0]["status"] == 408 and middleware.active == 0
    asyncio.run(run())
