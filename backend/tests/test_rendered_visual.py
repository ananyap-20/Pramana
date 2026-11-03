"""Real Chromium measurements; no declaration-only substitute or optional skip."""
import base64
import hashlib
from io import BytesIO

from PIL import Image
import pytest

from app.domain import EvidenceStatus as S
from app.services.visual_process import run_visual, VisualProblem
from app.visual_models import VisualManifest, VisualRequest


@pytest.fixture
def manifest():
    return VisualManifest(brand_id='fixture', version='v1', approved=True, active=True,
        source_id='fixture-guide', source_version='1', source_text='Fictional colors are black and white.',
        source_excerpt='Fictional colors are black and white.',
        palette=({'selector': '.brand', 'property': 'color', 'colors': ('#000',)},))


def request(html='<div style="color:#000;background:#fff"><p class="brand">Text</p></div>', **kwargs):
    return VisualRequest(brand_id='fixture', draft_id='exact-draft', draft_version='v2',
        mode='rendered', html=html, **kwargs)


def contrast(result):
    return next(f for f in result.findings if f.check=='contrast')


def test_real_inheritance_palette_geometry_and_exact_provenance(manifest):
    req=request()
    result=run_visual(req,manifest)
    finding=contrast(result)
    assert finding.evidence['ratio']==21
    assert finding.evidence['bounds_width']>0
    assert finding.evidence['html_start_tag'] in req.html
    assert result.rendering['scripts_enabled'] is False
    assert result.rendering['outbound_requests_blocked'] is True
    assert result.rendering['browser_version']
    assert result.draft_id==req.draft_id and result.draft_version==req.draft_version
    assert next(f for f in result.findings if f.check=='palette').result=='approved_color'
    assert result.input_sha256 != run_visual(req.model_copy(update={'viewport_width':390}),manifest).input_sha256


@pytest.mark.parametrize('color,size,weight,status,threshold', [
    ('#767676','16px',400,S.SUPPORTED,4.5),('#777777','16px',400,S.CONTRADICTED,4.5),
    ('#949494','24px',400,S.SUPPORTED,3),('#959595','24px',400,S.CONTRADICTED,3),
    ('#949494','14pt',700,S.SUPPORTED,3),('#949494','18px',700,S.CONTRADICTED,4.5),
])
def test_browser_computed_contrast_near_threshold(manifest,color,size,weight,status,threshold):
    result=run_visual(request(f'<p style="color:{color};background:#fff;font-size:{size};font-weight:{weight}">Text</p>'),manifest)
    assert contrast(result).evidence_status==status
    assert contrast(result).evidence['threshold']==threshold


@pytest.mark.parametrize('css', ['div{opacity:.5}', 'div{background:linear-gradient(white,black)!important}',
    'div{filter:blur(1px)}', 'p::before{content:"generated"}', 'p{transform:rotate(2deg)}',
    'p{-webkit-text-fill-color:white}', 'p{transition:color 1s}',
    'p{clip-path:circle(40%)}'])
def test_unresolved_compositing_never_passes(manifest,css):
    result=run_visual(request(css=css),manifest)
    assert contrast(result).evidence_status==S.INDETERMINATE
    assert contrast(result).evidence['ratio'] is None


def test_transparency_is_composited_without_rounding(manifest):
    result=run_visual(request('<div style="background:#000"><p style="color:rgba(255,255,255,.5);background:transparent">Text</p></div>'),manifest)
    assert contrast(result).evidence['ratio']==pytest.approx(5.2808228096)


def test_css_cascade_media_and_hidden_measurements(manifest):
    req=request(css='p {color:#777} @media(max-width:500px){p{color:#000}}',viewport_width=390)
    assert contrast(run_visual(req,manifest)).evidence_status==S.SUPPORTED
    hidden=request('<p style="display:none">Text</p>')
    assert contrast(run_visual(hidden,manifest)).result=='exempt'


@pytest.mark.parametrize('html,css', [('<script>fetch("https://example.com")</script>',''),
    ('<p onclick="alert(1)">Text</p>',''),('<p>Text</p>','@import "https://example.com";'),
    ('<p>Text</p>','p{background:url(file:///private)}')])
def test_hostile_input_is_rejected_before_rendering(manifest,html,css):
    with pytest.raises(VisualProblem) as error:
        run_visual(request(html,css=css),manifest)
    assert error.value.status==422


def test_asset_identity_alt_and_dangerous_overlay(manifest):
    output=BytesIO()
    Image.new('RGB',(8,8),'red').save(output,format='PNG')
    asset=output.getvalue()
    manifest=manifest.model_copy(update={'logo_selectors':('#logo',),'logo_sha256':(hashlib.sha256(asset).hexdigest(),)})
    req=request('<div><p style="color:#000;background:#fff">Text</p><img id="logo" src="asset:logo" alt="Fictional mark"></div>',
        assets=({'asset_id':'logo','media_type':'image/png','content_base64':base64.b64encode(asset).decode()},))
    result=run_visual(req,manifest)
    assert next(f for f in result.findings if f.check=='logo').result=='exact_digest_match'
    assert next(f for f in result.findings if f.check=='alt_text').result=='description_present_quality_unverified'
    overlay=request('<div><p style="color:#000;background:#fff">Text</p><div style="position:absolute;inset:0;background:#000"></div></div>')
    assert contrast(run_visual(overlay,manifest)).evidence_status==S.INDETERMINATE


def test_render_worker_has_actual_deadline(manifest):
    with pytest.raises(VisualProblem) as error:
        run_visual(request(),manifest,timeout=.01)
    assert error.value.status==408
