"""Real-host rehearsal: read sealed recordings; never submit a factory task."""
from __future__ import annotations
import hashlib
import io
import json
import os
from pathlib import Path
import urllib.request
import zipfile
from playwright.sync_api import sync_playwright, expect

BASE = os.environ.get('FACTORY_FRONTEND', 'http://127.0.0.1:5175')
REPOSITORY = Path(__file__).resolve().parents[5]
OUT = REPOSITORY / 'docs/code/Missions/software-factory/sf-001/evidence/monday-rehearsal'
OUT.mkdir(parents=True, exist_ok=True)
PREFIX = '/api/v1/factory'

def raw(path):
    with urllib.request.urlopen(BASE + PREFIX + path, timeout=60) as response:
        return response.read()

def get(path):
    return json.loads(raw(path))

summaries = get('/recordings')['recordings']
identifier = os.environ.get('FACTORY_PRIMARY_RECORDING') or next(
    item['id'] for item in summaries
    if item.get('provenance', {}).get('workflow_catalog_sha256')
    and 'construction.native_sources' in item['request']['goals'])
view = get('/recordings/' + identifier)
run, events, library = view['run'], view['events'], view['workflow_catalog']
assert view['read_only'] and run['request']['target_backend'] == 'ascend'
assert library['schema'] == 'factory.workflow.library.v1'
full_refs = {item['path'] for item in library['stage_refs']}
origins = [node['pool_origin'] for node in run['nodes'] if node.get('pool_origin')]
partial = [origin for origin in origins if origin['unselected_sibling_refs']]
assert len(partial) == 6
assert all(origin['full_ref'] in full_refs for origin in partial)
skipped = set(ref for origin in partial for ref in origin['unselected_sibling_refs'])
assert skipped.isdisjoint(origin['full_ref'] for origin in origins)

package = next(item for item in run['artifacts'] if item['kind'] == 'construction.native_sources')
package_bytes = raw(f'/recordings/{identifier}/artifacts/{package["id"]}')
assert hashlib.sha256(package_bytes).hexdigest() == package['sha256']
archive = zipfile.ZipFile(io.BytesIO(package_bytes))
diff_pairs = [pair for artifact in run['artifacts']
              if artifact['kind'] == 'construction.code_diff'
              for pair in get(f'/recordings/{identifier}/artifacts/{artifact["id"]}')['files']]
native_pair = next(pair for pair in diff_pairs if pair['generated_path'].startswith('src/ascend/'))
math_path = native_pair['generated_path']


def expected_nodes(cursor):
    graph = None
    for event in events[:cursor]:
        if event['type'] == 'graph.updated': graph = event['payload']
    return graph['nodes'] if graph else []


def verify_prefix(page, cursor):
    expected = expected_nodes(cursor)
    displayed = page.get_by_test_id('workflow-demo-node').evaluate_all('(nodes) => nodes.map(node => node.dataset.variant)')
    assert displayed == [item['id'] for item in expected], (cursor, displayed)
    selected = {item.get('pool_origin', {}).get('full_ref') or item.get('workflow_path') for item in expected}
    selected.discard(None)
    for button in page.get_by_test_id('workflow-demo-pool-card').all():
        assert button.get_attribute('data-selection') == ('selected' if button.get_attribute('data-variant') in selected else 'idle')
    for ref in skipped:
        assert page.locator(f'[data-testid="workflow-demo-pool-card"][data-variant="{ref}"]').get_attribute('data-selection') == 'idle'
    return {'cursor': cursor, 'node_count': len(displayed), 'selected_refs': sorted(selected)}


requests, errors, checkpoints = [], [], []
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path='/usr/bin/chromium', headless=True, args=['--no-sandbox'])
    page = browser.new_page(viewport={'width':1600, 'height':1000}, accept_downloads=True)
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('request', lambda request: requests.append({'method':request.method,'url':request.url}) if PREFIX in request.url else None)
    page.goto(f'{BASE}/?view=workflow&lng=en&recording={identifier}', wait_until='domcontentloaded')
    expect(page.get_by_test_id('workflow-demo-pool')).to_have_attribute('data-library-schema', library['schema'], timeout=60000)
    expect(page.get_by_test_id('workflow-demo-replay-timeline')).to_have_value('0')
    checkpoints.append(verify_prefix(page, 0))
    page.screenshot(path=str(OUT/'01-task-and-existing-pool.png'))
    choices = page.get_by_test_id('workflow-demo-replay-checkpoint').locator('option').evaluate_all(
        '(options) => options.filter(option => option.value).map(option => ({cursor:Number(option.value),label:option.textContent}))')
    assert choices
    page.get_by_test_id('workflow-demo-replay-speed').select_option('16')
    first = choices[0]['cursor']
    page.get_by_test_id('workflow-demo-replay-play-pause').click()
    expect(page.get_by_test_id('workflow-demo-replay-timeline')).to_have_value(str(first), timeout=60000)
    expect(page.get_by_test_id('workflow-demo-replay-play-pause')).to_have_attribute('aria-pressed','false')
    checkpoints.append(verify_prefix(page, first))
    composed = next(choice for choice in choices if 'composed' in choice['label'])
    page.get_by_test_id('workflow-demo-replay-checkpoint').select_option(str(composed['cursor']))
    checkpoints.append(verify_prefix(page, composed['cursor']))
    expect(page.get_by_test_id('workflow-demo-internal-row')).to_have_count(3)
    page.screenshot(path=str(OUT/'02-extracted-inner-stages.png'))
    code_checkpoint = next(choice for choice in choices if 'Ascend C++' in choice['label'])
    page.get_by_test_id('workflow-demo-replay-play-pause').click()
    expect(page.get_by_test_id('workflow-demo-replay-timeline')).to_have_value(str(code_checkpoint['cursor']), timeout=60000)
    expect(page.get_by_test_id('workflow-demo-replay-play-pause')).to_have_attribute('aria-pressed','false')
    checkpoints.append(verify_prefix(page, code_checkpoint['cursor']))
    page.locator('[data-testid="workflow-demo-evidence-tab"][data-variant="source"]').click()
    expect(page.get_by_test_id('workflow-demo-source-path')).to_have_text(math_path)
    expect(page.get_by_test_id('workflow-demo-source-code')).to_have_text(archive.read(math_path).decode(), use_inner_text=False)
    page.screenshot(path=str(OUT/'03-real-ascend-cpp.png'))
    page.locator('[data-testid="workflow-demo-evidence-tab"][data-variant="diff"]').click()
    diff = page.locator(f'[data-testid="workflow-demo-code-diff-file"][data-variant="{math_path}"]')
    expect(diff.get_by_test_id('workflow-demo-code-diff-original')).to_have_text(native_pair['source_code'])
    expect(diff.get_by_test_id('workflow-demo-code-diff-generated')).to_have_text(native_pair['generated_code'])
    expect(page.get_by_test_id('workflow-demo-code-diff-loading')).to_have_count(0)
    page.screenshot(path=str(OUT/'04-cuda-to-ascend-diff.png'))
    page.get_by_test_id('workflow-demo-replay-result').click()
    checkpoints.append(verify_prefix(page,len(events)))
    page.locator('[data-testid="workflow-demo-evidence-tab"][data-variant="log"]').click()
    expect(page.get_by_test_id('workflow-demo-log-worker-pid')).to_have_text(str(run['executor']['pid']))
    expect(page.get_by_test_id('workflow-demo-log-command')).to_have_count(sum(len(attempt['commands']) for node in run['nodes'] for attempt in node['attempts']))
    page.screenshot(path=str(OUT/'05-full-real-process-log.png'))
    test_node, test_attempt, test_index, test_command = next(
        (node, attempt, index, command)
        for node in run['nodes'] for attempt in node['attempts']
        for index, command in enumerate(attempt['commands'], 1)
        if command['argv'][0].endswith('/strata_core_test') and command.get('exit_code') == 0)
    command_key = f'{test_node["id"]}/{test_attempt["number"]}/{test_index}'
    page.locator(f'[data-testid="workflow-demo-log-command"][data-variant="{command_key}"]').click()
    expect(page.get_by_test_id('workflow-demo-log-pid')).to_have_text(str(test_command['pid']))
    expect(page.get_by_test_id('workflow-demo-log-exit')).to_have_text('0')
    expect(page.get_by_test_id('workflow-demo-log-stdout')).to_have_text(test_command['stdout'])
    expect(page.get_by_test_id('workflow-demo-log-stdout')).to_contain_text('352')
    page.get_by_test_id('workflow-demo-log-pid-label').evaluate('(node) => node.scrollIntoView({block:"start"})')
    page.screenshot(path=str(OUT/'05b-real-cpu-process-output.png'))
    page.get_by_test_id('workflow-demo-log-stdout-title').evaluate('(node) => node.scrollIntoView({block:"start"})')
    page.screenshot(path=str(OUT/'05c-real-cpu-stdout.png'))
    page.locator('[data-testid="workflow-demo-evidence-tab"][data-variant="build"]').click()
    expect(page.get_by_test_id('workflow-demo-cpu-evidence')).to_contain_text('352')
    page.screenshot(path=str(OUT/'06-validation-layers.png'))
    native_scope = page.get_by_test_id('workflow-demo-native-evidence')
    expect(native_scope).to_contain_text('NOT_RUN')
    expect(native_scope).to_contain_text('full_inference_validated')
    native_scope.get_by_test_id('workflow-demo-native-evidence-title').evaluate('(node) => node.scrollIntoView({block:"start"})')
    page.screenshot(path=str(OUT/'06b-native-validation-scope.png'))
    page.locator('[data-testid="workflow-demo-evidence-tab"][data-variant="downloads"]').click()
    link = page.locator(f'[data-testid="workflow-demo-artifact-download"][data-variant="{package["id"]}"]').first
    with page.expect_download(timeout=60000) as saved: link.click()
    saved.value.save_as(str(OUT/'ascend-generated-source.zip'))
    assert hashlib.sha256((OUT/'ascend-generated-source.zip').read_bytes()).hexdigest() == package['sha256']
    page.screenshot(path=str(OUT/'07-delivered-source-project.png'))
    page.get_by_test_id('workflow-demo-replay-checkpoint').select_option('')
    expect(page.get_by_test_id('workflow-demo-replay-timeline')).to_have_value('0')
    checkpoints.append(verify_prefix(page,0))
    page.locator('[data-testid="workflow-demo-evidence-tab"][data-variant="source"]').click()
    expect(page.get_by_test_id('workflow-demo-source-code')).to_have_count(0)
    for width,height in [(1366,768),(1920,1080)]:
        page.set_viewport_size({'width':width,'height':height})
        assert page.evaluate('document.documentElement.scrollHeight <= innerHeight && document.documentElement.scrollWidth <= innerWidth')
    assert not [request for request in requests if request['method'] != 'GET']
    assert not [request for request in requests if '/runs/' in request['url'] and '/stream' in request['url']]
    assert any('/replay?' in request['url'] and 'until=' in request['url'] for request in requests)
    assert not errors,errors
    browser.close()
report={'run_id':identifier,'status':run['status'],'workflow_catalog_sha256':run['workflow_catalog_sha256'],
        'selected_partial_calls':partial,'source_math_path':math_path,'package_sha256':package['sha256'],
        'checkpoints':checkpoints,'requests':requests,'page_errors':errors,
        'checks':['Actual host deep-link stays Workflow and English','Frozen multi-child library precedes execution',
                  'Exact full-ref selection; skipped siblings never blue','Every displayed node matches real graph.updated prefix',
                  'Backend-bounded SSE stops at actual publications','Native CPP and diff literal bytes from real published ZIP',
                  'Recorded worker and real subprocesses visible','CPU352 distinct from native-device/model NOT_RUN',
                  'Actual source ZIP downloads without workspace path dependency','Rewind removes future outputs','No POST, live run SSE or factory execution']}
(OUT/'results.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'run_id':identifier,'screenshots':str(OUT),'checks':len(report['checks']),'requests':len(requests),'errors':errors}))
