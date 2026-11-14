"""Read-only UI verification against published factory artifacts; no transport fixtures."""
import hashlib
import json
import os
import subprocess
from pathlib import Path
import urllib.request
import zipfile
from playwright.sync_api import sync_playwright, expect

ROOT = Path(os.environ.get('FACTORY_SOURCE_ROOT', str(Path(__file__).resolve().parents[5])))
OUT = ROOT / 'docs/code/Missions/software-factory/sf-001/evidence/code-diff-live'
API = os.environ.get('FACTORY_API', 'http://127.0.0.1:19000/api/v1/factory')
BASE = os.environ.get('FACTORY_FRONTEND', 'http://127.0.0.1:5175')
RUN = os.environ['FACTORY_RUN_ID']
OUT = OUT / RUN
REQUIRE_VALUE_REPORT = os.environ.get('VERIFY_VALUE_REPORT', '1') != '0'

def response(path):
    with urllib.request.urlopen(API + path, timeout=60) as value:
        return value.read(), value.headers.get('Content-Type', '')

def get(path):
    return json.loads(response(path)[0])

run = get('/runs/' + RUN)
artifacts = run['artifacts']
source_artifact = next(a for a in artifacts if a['kind'] == 'source.checkout')
source_raw, _ = response('/runs/' + RUN + '/artifacts/' + source_artifact['id'])
assert hashlib.sha256(source_raw).hexdigest() == source_artifact['sha256']
source = json.loads(source_raw)
source_root = Path(source['source_dir']).resolve()
assert source_root.is_relative_to(Path(os.environ.get('FACTORY_RUN_ROOT', '/workspace/factory-runs')) / RUN)
source_commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source_root, text=True).strip()
if run['request'].get('revision'): assert source_commit == run['request']['revision']
code_diff = next(a for a in reversed(artifacts) if a['kind'] == 'construction.code_diff')
package = next(a for a in reversed(artifacts) if a['kind'] == 'construction.package')
cpp = next(a for a in reversed(artifacts) if a['kind'] == 'construction.cpp')
value_report = next((a for a in reversed(artifacts) if a['kind'] == 'value.report'), None)
if REQUIRE_VALUE_REPORT: assert value_report is not None, 'This run has not published value.report'
raw, diff_mime = response('/runs/' + RUN + '/artifacts/' + code_diff['id'])
assert hashlib.sha256(raw).hexdigest() == code_diff['sha256']
manifest = json.loads(raw)
assert manifest['schema'] == 'strata.code.diff.v1'
assert manifest['files']
for file in manifest['files']:
    original = (source_root / file['source_path']).resolve()
    assert original.is_relative_to(source_root)
    assert file['source_code'] in original.read_text()
raw_cpp, cpp_mime = response('/runs/' + RUN + '/artifacts/' + cpp['id'])
assert hashlib.sha256(raw_cpp).hexdigest() == cpp['sha256']
assert any(item['generated_code'].encode() == raw_cpp for item in manifest['files']), 'Displayed generated C++ differs from published C++ artifact'
raw_value = None
if value_report:
    raw_value, value_mime = response('/runs/' + RUN + '/artifacts/' + value_report['id'])
    assert hashlib.sha256(raw_value).hexdigest() == value_report['sha256']
    assert raw_value.strip()
OUT.mkdir(parents=True, exist_ok=True)
(OUT / 'code_diff.json').write_bytes(raw)
(OUT / 'strata_core.cpp').write_bytes(raw_cpp)
if raw_value is not None: (OUT / 'value_report.md').write_bytes(raw_value)

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/usr/bin/chromium', headless=True, args=['--no-sandbox'])
    page = browser.new_page(viewport={'width':1440,'height':900}, accept_downloads=True)
    page.add_init_script("localStorage.setItem('i18nextLng','en');localStorage.setItem('ai4research.factory.last-run'," + json.dumps(RUN) + ")")
    errors, duplicate_keys = [], []
    page.on('console', lambda message: duplicate_keys.append(message.text) if 'same key' in message.text else None)
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(BASE, wait_until='domcontentloaded')
    page.locator('[data-testid="session-sidebar-nav-item"][data-variant="workflow"]').click(timeout=60000)
    panel = page.get_by_test_id('workflow-demo-code-diff')
    expect(panel).to_be_visible(timeout=30000)
    expect(panel).to_have_attribute('data-artifact', code_diff['id'])
    assert page.get_by_test_id('workflow-demo-backend').input_value() == run['request']['target_backend']
    for checkbox in page.get_by_test_id('workflow-demo-goal').all():
        assert checkbox.is_checked() == (checkbox.get_attribute('data-variant') in run['request']['goals'])
    expect(panel.get_by_test_id('workflow-demo-code-diff-file')).to_have_count(len(manifest['files']))
    for index, item in enumerate(manifest['files']):
        file_panel = panel.get_by_test_id('workflow-demo-code-diff-file').nth(index)
        expect(file_panel).to_have_attribute('data-variant', item['generated_path'])
        assert file_panel.get_by_test_id('workflow-demo-code-diff-original').locator('code').text_content() == item['source_code']
        assert file_panel.get_by_test_id('workflow-demo-code-diff-generated').locator('code').text_content() == item['generated_code']
        assert file_panel.locator('.wd-code-diff-path').all_text_contents() == [item['source_path'], item['generated_path']]
    assert not page.get_by_test_id('workflow-demo-code-diff-error').count()
    assert page.evaluate('document.documentElement.scrollHeight <= innerHeight')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.screenshot(path=str(OUT / 'code-diff.png'))
    if value_report:
        report_panel = page.get_by_test_id('workflow-demo-value-report')
        expect(report_panel).to_have_attribute('data-artifact', value_report['id'])
        expect(report_panel.get_by_test_id('workflow-demo-value-report-content')).to_have_text(raw_value.decode(), use_inner_text=False)
        assert report_panel.get_by_test_id('workflow-demo-value-report-content').text_content() == raw_value.decode()
        report_panel.scroll_into_view_if_needed()
        page.screenshot(path=str(OUT / 'value-report.png'))
        panel.scroll_into_view_if_needed()
    link = page.locator('[data-testid="workflow-demo-deliverables"] a').filter(has_text='huawei_native_strata.zip').first
    expect(link).to_be_visible()
    with page.expect_download(timeout=60000) as downloaded:
        link.click()
    assert downloaded.value.suggested_filename == 'huawei_native_strata.zip'
    zip_path = OUT / downloaded.value.suggested_filename
    downloaded.value.save_as(zip_path)
    assert hashlib.sha256(zip_path.read_bytes()).hexdigest() == package['sha256']
    with zipfile.ZipFile(zip_path) as archive:
        cpp_name = next(name for name in archive.namelist() if name == 'src/strata_core.cpp' or name.endswith('/src/strata_core.cpp'))
        assert archive.read(cpp_name) == raw_cpp
        archive_files = archive.namelist()
    page.set_viewport_size({'width':1366,'height':768})
    expect(panel).to_be_visible()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.screenshot(path=str(OUT / 'code-diff-compact.png'))
    assert not errors, errors
    assert not duplicate_keys, duplicate_keys
    result = {'run_id': RUN, 'run_status': run['status'], 'source_commit': source_commit, 'code_diff_artifact': code_diff['id'], 'code_diff_sha256': code_diff['sha256'], 'value_report_sha256': value_report['sha256'] if value_report else None, 'cpp_sha256': cpp['sha256'], 'package_sha256': package['sha256'], 'download_name': downloaded.value.suggested_filename, 'files_rendered': len(manifest['files']), 'source_paths': [item['source_path'] for item in manifest['files']], 'generated_paths': [item['generated_path'] for item in manifest['files']], 'archive_files': archive_files, 'page_errors': errors, 'duplicate_key_warnings': duplicate_keys, 'dependency_mode': 'Real host UI and existing real factory API, actual published source/artifact bytes; no network fixtures', 'checks': ['Sidebar host integration', 'actual run request hydration', 'duplicate source paths retain all code pairs without React key collisions', 'original CUDA snippets are verbatim in pinned acquired repository', 'actual Code Diff JSON SHA', 'literal original and generated source byte equality', 'actual published C++ equals displayed generated source', 'downloaded genuine ZIP SHA', 'ZIP source equals published C++', 'two viewports no outer horizontal scroll']}
    if value_report: result['checks'].append('actual Value Report SHA and exact literal report text')
    else: result['not_verified'] = ['Value Report: not published on this earlier construction-only run']
    (OUT / 'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))
    browser.close()
