"""Real production-frontend journeys against real MongoDB and local object transport."""
import base64
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
from uuid import uuid4

from docx import Document
import httpx
from playwright.sync_api import sync_playwright, expect
from pymongo import MongoClient
import pytest


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope='module')
def web_app(managed_mongo, tmp_path_factory):
    if managed_mongo is None:
        if os.getenv('PRAMANA_REQUIRE_ACCEPTANCE') == '1':
            pytest.fail('Real browser acceptance requires PRAMANA_TEST_MONGOD.')
        pytest.skip('Configure a disposable native MongoDB for real browser acceptance.')
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    directory = tmp_path_factory.mktemp('pramana-browser')
    from backend.tests.intake_fixtures import write_demo_fixtures
    write_demo_fixtures(ROOT / 'tmp/ui-fixtures')
    database = 'pramana_browser_test_' + uuid4().hex
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(('PRAMANA_', 'MONGODB_', 'BUNNY_', 'FIREBASE_'))}
    env.update(MONGODB_URI=managed_mongo.uri, MONGODB_DB=database, PYTHONPATH=str(ROOT / 'backend'),
        CORS_ORIGINS=f'http://127.0.0.1:{port}', PRAMANA_ENABLE_LOCAL_INTAKE='1',
        PRAMANA_AUDIT_KEYS=json.dumps({'test':base64.b64encode(secrets.token_bytes(32)).decode()}),
        PRAMANA_AUDIT_ACTIVE_KEY='test', PRAMANA_TEST_OBJECTS=str(directory / 'objects'),
        TESSERACT_CMD=str(ROOT / 'tmp/ocr-runtime/tesseract/tesseract.exe'),
        TESSDATA_DIR=str(ROOT / 'tmp/ocr-runtime/tesseract/tessdata'))
    class Server:
        url = f'http://127.0.0.1:{port}'
        process = None
        def start(self):
            self.process = subprocess.Popen([sys.executable,'-m','uvicorn','backend.tests.browser_server:app',
                '--host','127.0.0.1','--port',str(port),'--no-access-log'],cwd=ROOT,env=env,
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            deadline=time.monotonic()+20
            while time.monotonic()<deadline:
                assert self.process.poll() is None, 'Test web server failed startup.'
                try:
                    if httpx.get(self.url+'/ready',timeout=1).status_code==200:
                        return
                except httpx.HTTPError:
                    pass
                time.sleep(.1)
            raise RuntimeError('Test web server did not become ready.')
        def stop(self):
            if self.process and self.process.poll() is None:
                self.process.terminate()
                self.process.wait(timeout=15)
        def restart(self):
            self.stop(); self.start()
    server=Server()
    try:
        server.start()
        yield server
    finally:
        server.stop()
        with MongoClient(managed_mongo.uri) as client:
            client.drop_database(database)  # Exact disposable namespace created above only.


@pytest.fixture(scope='module')
def browser():
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True,chromium_sandbox=True)
        yield browser
        browser.close()


def enter(browser,web_app,**options):
    context=browser.new_context(accept_downloads=True,**options)
    page=context.new_page()
    page.set_default_timeout(20000)
    page.goto(web_app.url)
    expect(page.locator('#main-content h1')).to_be_visible()
    if page.get_by_role('button',name='Skip tour',exact=True).count():
        page.get_by_role('button',name='Skip tour',exact=True).click()
    expect(page.get_by_role('heading',name='Review your draft.')).to_be_visible()
    return context,page


def human_decision(page):
    page.get_by_role('link',name='Human Review',exact=True).click()
    button=page.get_by_role('button',name='Request revision',exact=True)
    expect(button).to_be_disabled()
    page.get_by_role('checkbox').check()
    expect(button).to_be_enabled()
    with page.expect_response(lambda r:'/decision' in r.url and r.request.method=='POST') as saved:
        button.click()
    assert saved.value.status==200
    expect(page.get_by_role('list',name='Decision history')).to_contain_text('revision')


@pytest.mark.parametrize('reduced',['no-preference','reduce'])
def test_welcome_retry_handoff_focus_and_mobile_layout(browser,web_app,reduced):
    context=browser.new_context(viewport={'width':390,'height':844},reduced_motion=reduced)
    page=context.new_page()
    requests=[]
    page.on('request',lambda request:requests.append(request.url))
    page.route('**/ready',lambda route:route.fulfill(status=503,json={'detail':'Test unavailable'}))
    page.goto(web_app.url)
    expect(page.get_by_role('heading',name='Welcome to your desk.')).to_be_visible()
    logo=page.get_by_role('img',name='Pramana P brand mark')
    assert logo.evaluate('(e)=>e.naturalWidth>0 && e.width===e.height')
    expect(page.get_by_role('button',name='Retry',exact=True)).to_be_visible()
    if reduced=='reduce':
        assert page.locator('.welcome-layer').evaluate('(e)=>getComputedStyle(e).transitionDuration')=='0s'
    page.unroute('**/ready')
    page.get_by_role('button',name='Retry',exact=True).click()
    expect(page.locator('#main-content h1')).to_be_visible()
    if page.get_by_role('button',name='Skip tour',exact=True).count():
        page.get_by_role('button',name='Skip tour',exact=True).click()
    expect(page.get_by_role('heading',name='Review your draft.')).to_be_visible()
    expect(page.locator('#main-content')).to_be_focused()
    assert page.get_by_role('heading',name='Welcome to your desk.').count()==0
    assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1')
    assert not any('/auth/' in url or '/me' in url for url in requests)
    assert page.get_by_role('button',name='Sign in').count()==0
    context.close()


def test_text_docx_decision_history_and_app_restart(browser,web_app,tmp_path):
    context,page=enter(browser,web_app)
    errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    draft='\U0001f642 Our dashboard. Starter plan supports 50 team members.'
    page.get_by_label('Your working draft').fill(draft)
    with page.expect_response(lambda r:r.url.endswith('/reviews/analyze') and r.request.method=='POST') as result:
        page.get_by_role('button',name='Analyze draft',exact=True).click()
    analysis=result.value.json()
    assert analysis['draft_text']==draft
    for finding in analysis['findings']:
        if finding['location']:
            assert draft[finding['location']['start']:finding['location']['end']]==finding['flagged_text']
    human_decision(page)
    web_app.restart()
    page.reload()
    expect(page.get_by_role('list',name='Decision history')).to_contain_text('revision')
    page.get_by_role('link',name='Audit Trail',exact=True).click()
    page.get_by_label('Search loaded records').fill(analysis['review_run_id'])
    page.get_by_role('button',name=f"Inspect review {analysis['review_run_id']}",exact=True).click()
    expect(page.locator('.inspector-excerpt')).to_have_text(draft)
    page.get_by_role('button',name='Open saved review',exact=False).click()
    expect(page.get_by_role('list',name='Decision history')).to_contain_text('revision')
    page.get_by_role('link',name='Draft Studio',exact=True).click()
    document=Document();document.add_paragraph('Fictional dashboard document.')
    path=tmp_path/'draft.docx';document.save(path)
    page.locator('input[type=file]').set_input_files(path)
    with page.expect_response(lambda r:r.url.endswith('/analyze-document')) as docx:
        page.get_by_role('button',name='Analyze draft',exact=True).click()
    assert docx.value.status==200 and docx.value.json()['input_type']=='docx'
    human_decision(page)
    assert not errors
    context.close()


@pytest.mark.parametrize('name',['text.pdf','scan.pdf','image.png','image.jpg'])
def test_real_file_preview_confirmation_analysis_and_original(browser,web_app,name,tmp_path):
    context,page=enter(browser,web_app)
    path=ROOT/'tmp/ui-fixtures'/name
    page.locator('input[type=file]').set_input_files(path)
    page.get_by_role('button',name='Extract text',exact=True).click()
    confirm=page.get_by_role('button',name='Confirm transcription',exact=True)
    expect(confirm).to_be_visible(timeout=75000)
    expect(confirm).to_be_disabled()
    analyze=page.get_by_role('button',name='Analyse confirmed text',exact=True)
    expect(analyze).to_be_disabled()
    page.get_by_label('Check and correct page 1 text').fill('dashboard\nHuman-confirmed fictional transcription.')
    attestation=page.get_by_role('checkbox')
    expect(attestation).to_be_enabled(timeout=20000)
    attestation.check()
    with page.expect_response(lambda r:r.url.endswith('/confirm')) as confirmed:
        confirm.click()
    transcription=confirmed.value.json()['current']
    assert transcription['human_edited'] is True
    with page.expect_response(lambda r:'/intake/' in r.url and r.url.endswith('/analyze')) as analyzed:
        analyze.click()
    assert analyzed.value.status==200
    analysis=analyzed.value.json()
    assert analysis['draft_text']==transcription['text']
    assert analysis['document_provenance']['text_sha256']==transcription['text_sha256']
    human_decision(page)
    with page.expect_download() as download:
        page.get_by_role('button',name='Download retained original',exact=True).click()
    destination=tmp_path/'original.bin';download.value.save_as(destination)
    assert destination.read_bytes()==path.read_bytes()
    if name=='text.pdf':
        web_app.restart();page.reload()
        expect(page.get_by_role('list',name='Decision history')).to_contain_text('revision')
        with page.expect_download() as restarted:
            page.get_by_role('button',name='Download retained original',exact=True).click()
        restarted.value.save_as(destination)
        assert destination.read_bytes()==path.read_bytes()
    context.close()


def test_rendered_visual_checks_sample_failures_and_responsive_tabs(browser,web_app):
    context,page=enter(browser,web_app)
    page.get_by_role('link',name='Visual Checks',exact=True).click()
    page.get_by_role('button',name='Load fictional sample',exact=True).click()
    button=page.get_by_role('button',name='Run rendered visual checks',exact=True)
    expect(button).to_be_enabled()
    with page.expect_response(lambda r:r.url.endswith('/visual/analyze')) as response:
        button.click()
    result=response.value.json()
    assert response.value.status==200 and result['mode']=='rendered'
    assert all(f['evidence_status']=='Supported' for f in result['findings'])
    assert {f['check'] for f in result['findings']}=={'logo','palette','contrast','alt_text'}
    screenshots=ROOT/'tmp/acceptance-screenshots';screenshots.mkdir(exist_ok=True)
    page.screenshot(path=str(screenshots/'visual-rendered-desktop.png'),full_page=True)
    page.get_by_label('Viewport').select_option('390')
    page.get_by_label('CSS declarations').fill('main{background:#fff}.brand{color:#aaa;font-size:16px}')
    with page.expect_response(lambda r:r.url.endswith('/visual/analyze')) as bad:
        button.click()
    findings=bad.value.json()['findings']
    assert any(f['check']=='contrast' and f['evidence_status']=='Contradicted' for f in findings)
    page.get_by_label('Passive HTML').fill('<script>alert("never run")</script>')
    button.click()
    expect(page.get_by_role('alert')).to_contain_text('422')
    assert page.get_by_label('Passive HTML').input_value()=='<script>alert("never run")</script>'
    page.set_viewport_size({'width':390,'height':844})
    for tab in ['Draft Studio','Human Review','Evidence','Audit Trail','Active Policies','Visual Checks']:
        page.get_by_role('link',name=tab,exact=True).click()
        assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1'),tab
    page.screenshot(path=str(screenshots/'visual-mobile.png'),full_page=True)
    context.close()
