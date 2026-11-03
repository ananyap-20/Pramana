"""Reproduce all three local acceptance gates; fail if any test is skipped."""
import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mongod',type=Path,required=True)
    parser.add_argument('--mongo-tools',type=Path,required=True)
    parser.add_argument('--browser-path',type=Path)
    parser.add_argument('--tesseract',type=Path)
    parser.add_argument('--tessdata',type=Path)
    args=parser.parse_args()
    output=ROOT/'tmp/mandatory-verification';output.mkdir(parents=True,exist_ok=True)
    env={key:value for key,value in os.environ.items() if not key.startswith(('PRAMANA_','MONGODB_','BUNNY_','FIREBASE_'))}
    env.update(PRAMANA_TEST_MONGOD=str(args.mongod.resolve(strict=True)),
        PRAMANA_TEST_MONGO_TOOLS=str(args.mongo_tools.resolve(strict=True)),
        PRAMANA_REQUIRE_ACCEPTANCE='1',REQUIRE_REAL_OCR='1',VITE_API_BASE_URL='/',
        PYTHONPATH=str(ROOT/'backend')+os.pathsep+str(ROOT))
    if args.browser_path:
        env['PLAYWRIGHT_BROWSERS_PATH']=str(args.browser_path.resolve(strict=True))
    if args.tesseract:
        env['TESSERACT_CMD']=str(args.tesseract.resolve(strict=True))
    if args.tessdata:
        env['TESSDATA_DIR']=str(args.tessdata.resolve(strict=True))
    npm=shutil.which('npm.cmd' if os.name=='nt' else 'npm')
    if not npm:
        raise SystemExit('Node/npm is required for frontend acceptance.')
    steps=[]
    def run(label,command,directory=ROOT):
        print(label,flush=True)
        subprocess.run(command,cwd=directory,env=env,check=True)
        steps.append(label)
    for step in ('build','lint','test'):
        run('Frontend '+step,[npm,'run',step],ROOT/'frontend')
    junit=output/'backend.xml'
    run('Full backend, real renderer, real MongoDB and browser acceptance',
        [sys.executable,'-m','pytest','-ra','--junitxml='+str(junit)])
    suites=ET.parse(junit).getroot()
    counts={key:sum(int(s.get(key,0)) for s in suites.iter('testsuite')) for key in ('tests','failures','errors','skipped')}
    if counts['skipped'] or counts['errors'] or counts['failures']:
        raise SystemExit('Mandatory acceptance did not pass with zero skips.')
    run('Independent PDF/OCR quality and exact quote-span gate',[sys.executable,'scripts/verify_intake.py'])
    run('Python compilation',[sys.executable,'-m','compileall','-q','backend','scripts'])
    report={'verified_at_utc':datetime.now(UTC).isoformat(),'scope':'local fictional fixtures only',
        'backend':counts,'completed_checks':steps,
        'intake':json.loads((ROOT/'tmp/intake-measurements.json').read_text(encoding='utf-8')),
        'database':'real disposable loopback MongoDB; actual restart and mongodump/mongorestore',
        'original_storage':'real encrypted local test transport; no Bunny provider claim',
        'browser':'managed Chromium; production frontend; desktop/mobile and reduced motion',
        'deployment_verified':False}
    (output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f"PASS: {counts['tests']} backend/acceptance tests, zero skipped. Report: tmp/mandatory-verification/results.json",flush=True)


if __name__=='__main__':
    main()
