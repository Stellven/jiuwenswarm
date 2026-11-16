"""Opt-in real browser/CC smoke test. No model or GPU qualification claim.

Run with a frontend npm install, FastAPI, uvicorn and Playwright available.
All generated bundles, stores, logs and screenshots live under --out.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--browser', default=None)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    frontend = root / 'jiuwenswarm/channels/web/frontend'
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    bundle = out / 'cpu-cc'
    bundle.mkdir(exist_ok=True)
    (bundle / 'cc.yaml').write_text(json.dumps(dict(cc='2', id='test.cpu', version='1.0.0',
        bindings={'default': {'kind': 'native', 'command': ['{python}', '{bundle}/run.py']}},
        capabilities={'double': {'does': 'CPU transport check', 'takes': {'value': 'json'}, 'gives': {'value': 'json'}}})), encoding='utf-8')
    (bundle / 'run.py').write_text("import json,sys\np=json.load(sys.stdin)\nprint(json.dumps({'outcome':'ok','outputs':{'value':2*p['inputs']['value']}}))\n", encoding='utf-8')
    from jiuwenswarm.software_factory.cc_prepare import prepare
    config = out / 'config.json'
    prepare(config, 'browser-cpu-check', [bundle])
    cache = frontend / 'node_modules/.cache/cc-browser'
    cache.mkdir(parents=True, exist_ok=True)
    entry = cache / 'main.tsx'
    entry.write_text("import React from 'react'; import {createRoot} from 'react-dom/client';\n"
        "import {CCWorkflowPanel} from '../../../src/features/workflowDemo/CCWorkflowPanel';\n"
        "import '../../../src/i18n'; import '../../../src/styles/themes/default/light.css';\n"
        "createRoot(document.getElementById('root')!).render(<CCWorkflowPanel/>);\n", encoding='utf-8')
    esbuild = frontend / ('node_modules/.bin/esbuild.cmd' if os.name == 'nt' else 'node_modules/.bin/esbuild')
    subprocess.run([str(esbuild), str(entry), '--bundle', '--jsx=automatic', '--define:process.env.NODE_ENV="production"',
                    '--outfile=' + str(out / 'main.js')], cwd=frontend, check=True)
    (out / 'index.html').write_text('<!doctype html><html lang="en" data-theme="default" data-color-mode="light">'
        '<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<link rel="stylesheet" href="/main.css"><div id="root"></div><script src="/main.js"></script></html>', encoding='utf-8')
    server = out / 'server.py'
    server.write_text("from fastapi import FastAPI\nfrom fastapi.staticfiles import StaticFiles\n"
        "from jiuwenswarm.software_factory.cc_service import CCService\n"
        "from jiuwenswarm.software_factory.cc_api import create_cc_router\nimport uvicorn\n"
        f"app=FastAPI();app.include_router(create_cc_router(CCService.from_config({str(config)!r})))\n"
        f"app.mount('/',StaticFiles(directory={str(out)!r},html=True))\n"
        "uvicorn.run(app,host='127.0.0.1',port=5175)\n", encoding='utf-8')
    log = (out / 'server.log').open('w', encoding='utf-8')
    process = subprocess.Popen([sys.executable, str(server)], cwd=root,
        env={**os.environ, 'PYTHONPATH': str(root)}, stdout=log, stderr=log)
    try:
        for _ in range(100):
            if process.poll() is not None:
                raise RuntimeError('Validation server failed; inspect server.log')
            try:
                urllib.request.urlopen('http://127.0.0.1:5175/api/v1/cc-workflows/catalog', timeout=1).close()
                break
            except OSError:
                time.sleep(.1)
        from playwright.sync_api import sync_playwright, expect
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, executable_path=args.browser)
            page = browser.new_page(viewport={'width': 1280, 'height': 900}, locale='en-US')
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto('http://127.0.0.1:5175')
            page.get_by_test_id('workflow-demo-cc-objective').fill('Verify native CC execution and recorded replay')
            page.get_by_test_id('workflow-demo-cc-selection').select_option('test-cpu-double')
            page.get_by_test_id('workflow-demo-cc-inputs').fill('{"value":21}')
            page.get_by_test_id('workflow-demo-cc-create').click()
            expect(page.get_by_test_id('workflow-demo-cc-status')).to_contain_text('ready')
            page.get_by_test_id('workflow-demo-cc-advance').click()
            expect(page.get_by_test_id('workflow-demo-cc-status')).to_contain_text('completed', timeout=30000)
            page.get_by_test_id('workflow-demo-cc-node').click()
            expect(page.get_by_test_id('workflow-demo-cc-evidence')).to_contain_text('42')
            page.screenshot(path=str(out / 'native-workflow-desktop.png'), full_page=True)
            page.get_by_test_id('workflow-demo-cc-replay').fill('1')
            expect(page.get_by_test_id('workflow-demo-cc-node')).to_contain_text('pending')
            expect(page.get_by_test_id('workflow-demo-cc-advance')).to_be_disabled()
            page.screenshot(path=str(out / 'native-workflow-replay.png'), full_page=True)
            page.set_viewport_size({'width': 390, 'height': 844})
            page.screenshot(path=str(out / 'native-workflow-mobile.png'), full_page=True)
            assert not errors, errors
            browser.close()
        # Replay must not have created a second CC execution.
        from jiuwenswarm.ccv2.ccv2 import Host
        with Host(out / 'ccstore').db() as db:
            assert db.execute('SELECT count(*) FROM calls').fetchone()[0] == 1
        print('PASS: real native CC result, browser graph/evidence, read-only replay; desktop and narrow screenshots retained')
    finally:
        process.terminate()
        process.wait(timeout=15)
        log.close()


if __name__ == '__main__':
    main()
