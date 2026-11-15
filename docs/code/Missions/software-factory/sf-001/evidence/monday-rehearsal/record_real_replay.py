"""Record the existing, sealed C5 replay through the unchanged built host UI.

No request interception, UI/style injection, source edits, or factory task submission.
Pauses are operator reading time after real backend publication checkpoints.
"""
from __future__ import annotations
import hashlib
import io
import json
import os
import time
import urllib.request
import zipfile
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

BASE = 'http://127.0.0.1:5175'
RUN_ID = '11a6ce02166b4618baea6db59aaf44ec'
OUT = Path('/workspace/software-factory-delivery/monday')
RAW = OUT / 'replay-video-raw'
RAW.mkdir(parents=True, exist_ok=True)
# Use the installed ffmpeg without modifying user/system Playwright caches.
playwright_cache = OUT / 'playwright-recording-cache'
ffmpeg_dir = playwright_cache / 'ffmpeg-1011'
ffmpeg_dir.mkdir(parents=True, exist_ok=True)
ffmpeg_binary = ffmpeg_dir / 'ffmpeg-linux'
if not ffmpeg_binary.exists(): ffmpeg_binary.symlink_to('/usr/bin/ffmpeg')
os.environ['PLAYWRIGHT_BROWSERS_PATH'] = str(playwright_cache)
PREFIX = '/api/v1/factory'

def raw(path):
    with urllib.request.urlopen(BASE + PREFIX + path, timeout=60) as response:
        return response.read()

def get(path):
    return json.loads(raw(path))

before = {item['id'] for item in get('/recordings')['recordings']}
view = get('/recordings/' + RUN_ID)
run, events, library = view['run'], view['events'], view['workflow_catalog']
assert view['read_only'] and run['request']['target_backend'] == 'ascend'
assert run['request']['goals'] == ['construction.native_sources', 'construction.cpu_validation']
assert library['schema'] == 'factory.workflow.library.v1'
package = next(item for item in run['artifacts'] if item['kind'] == 'construction.native_sources')
package_bytes = raw(f'/recordings/{RUN_ID}/artifacts/{package["id"]}')
assert hashlib.sha256(package_bytes).hexdigest() == package['sha256']
archive = zipfile.ZipFile(io.BytesIO(package_bytes))
diff_artifact = next(item for item in run['artifacts'] if item['kind'] == 'construction.code_diff')
diff = get(f'/recordings/{RUN_ID}/artifacts/{diff_artifact["id"]}')
math_pair = next(item for item in diff['files'] if item.get('target') == 'ASCEND' and item['generated_path'] in archive.namelist())
math_path = math_pair['generated_path']
math_text = archive.read(math_path).decode()
assert math_pair['generated_code'] in math_text
partial = [node['pool_origin'] for node in run['nodes'] if node.get('pool_origin', {}).get('unselected_sibling_refs')]
skipped = {ref for origin in partial for ref in origin['unselected_sibling_refs']}
assert len(partial) == 6

commands = [(node, attempt, index, command) for node in run['nodes'] for attempt in node['attempts'] for index, command in enumerate(attempt['commands'], 1)]
configure = next(item for item in commands if '-DSTRATA_CORE_BACKEND=CPU' in item[3]['argv'] and item[3].get('exit_code') == 0)
build = next(item for item in commands if item[3]['argv'][0].endswith('/make') and item[3].get('exit_code') == 0)
test = next(item for item in commands if item[3]['argv'][0].endswith('/strata_core_test') and item[3].get('exit_code') == 0)
assert '352' in test[3]['stdout']
requests, errors, scenes, prefixes = [], [], [], []
started = time.monotonic()

def note(label, **fields):
    item = {'elapsed_s': round(time.monotonic() - started, 3), 'scene': label, **fields}
    scenes.append(item)
    print(json.dumps(item), flush=True)

def verify_prefix(page):
    cursor = int(page.get_by_test_id('workflow-demo-replay-timeline').input_value())
    graph = next((event['payload'] for event in reversed(events[:cursor]) if event['type'] == 'graph.updated'), None)
    expected = graph['nodes'] if graph else []
    actual = page.get_by_test_id('workflow-demo-node').evaluate_all('(nodes) => nodes.map(node => node.dataset.variant)')
    assert actual == [node['id'] for node in expected]
    selected = {node.get('pool_origin', {}).get('full_ref') or node.get('workflow_path') for node in expected}
    for button in page.get_by_test_id('workflow-demo-pool-card').all():
        assert button.get_attribute('data-selection') == ('selected' if button.get_attribute('data-variant') in selected else 'idle')
    for ref in skipped:
        expect(page.locator(f'[data-testid="workflow-demo-pool-card"][data-variant="{ref}"]')).to_have_attribute('data-selection', 'idle')
    prefixes.append({'cursor': cursor, 'nodes': actual})
    return cursor

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/usr/bin/chromium', headless=True, args=['--no-sandbox'])
    context = browser.new_context(viewport={'width': 1600, 'height': 1000}, record_video_dir=str(RAW), record_video_size={'width':1600, 'height':1000}, accept_downloads=True)
    page = context.new_page()
    video = page.video
    page.on('request', lambda request: requests.append({'method':request.method, 'url':request.url}) if PREFIX in request.url else None)
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(f'{BASE}/?view=workflow&lng=en&recording={RUN_ID}', wait_until='domcontentloaded')
    expect(page.get_by_test_id('workflow-demo-pool')).to_have_attribute('data-library-schema', library['schema'], timeout=60000)
    expect(page.get_by_test_id('workflow-demo-replay-timeline')).to_have_value('0')
    expect(page.get_by_test_id('workflow-demo-recorded-target')).to_have_text('ASCEND')
    expect(page.get_by_test_id('workflow-demo-replay-speed')).to_have_value('4')
    choices = page.get_by_test_id('workflow-demo-replay-checkpoint').locator('option').evaluate_all('(options) => options.filter(option => option.value).map(option => ({cursor:Number(option.value),label:option.textContent}))')
    assert choices
    evidence = page.get_by_test_id('workflow-demo-evidence-content')
    def hold(seconds):
        page.wait_for_timeout(int(seconds * 1000))
    def tab(name):
        page.locator(f'[data-testid="workflow-demo-evidence-tab"][data-variant="{name}"]').click()
        evidence.evaluate('(element) => { element.scrollTop = 0; }')
    def continue_to(choice):
        old = int(page.get_by_test_id('workflow-demo-replay-timeline').input_value())
        note('Continue actual backend recording', after=old, until=choice['cursor'], publication=choice['label'])
        page.get_by_test_id('workflow-demo-replay-play-pause').click()
        expect(page.get_by_test_id('workflow-demo-replay-timeline')).to_have_value(str(choice['cursor']), timeout=60000)
        expect(page.get_by_test_id('workflow-demo-replay-play-pause')).to_have_attribute('aria-pressed', 'false', timeout=10000)
        verify_prefix(page)
    def show_command(item, label, read_seconds):
        node, attempt, index, command = item
        key = f'{node["id"]}/{attempt["number"]}/{index}'
        page.get_by_test_id('workflow-demo-log-console-title').scroll_into_view_if_needed()
        page.locator(f'[data-testid="workflow-demo-log-command"][data-variant="{key}"]').click()
        expect(page.get_by_test_id('workflow-demo-log-argv')).to_have_text(json.dumps(command['argv'], indent=2), use_inner_text=False)
        expect(page.get_by_test_id('workflow-demo-log-pid')).to_have_text(str(command['pid']))
        expect(page.get_by_test_id('workflow-demo-log-exit')).to_have_text(str(command['exit_code']))
        page.get_by_test_id('workflow-demo-log-argv').scroll_into_view_if_needed()
        note(label, command=key, pid=command['pid'], exit_code=command['exit_code'])
        hold(read_seconds)
    verify_prefix(page)
    note('Actual task and frozen existing pool; source-only Ascend target')
    hold(5)
    continue_to(choices[0])
    note('Source acquired; next stages still prefix-gated')
    hold(2)
    composed = next(item for item in choices if 'composed' in item['label'])
    continue_to(composed)
    expect(page.get_by_test_id('workflow-demo-internal-row')).to_have_count(3)
    note('Partial inner-stage selections with genuinely skipped siblings')
    hold(5)
    leaf = 'function_extraction/function_extraction/extract'
    page.locator(f'[data-testid="workflow-demo-pool-card"][data-variant="{leaf}"]').click()
    expect(page.get_by_test_id('workflow-demo-inspected-pool-ref')).to_have_text(leaf)
    note('Inspect exact selected leaf and its other existing sibling')
    hold(3)
    page.get_by_test_id('workflow-demo-production-chain').scroll_into_view_if_needed()
    note('Actual cross-parent typed dependency spine')
    hold(4)
    cpp_checkpoint = next(item for item in choices if 'Ascend C++' in item['label'])
    continue_to(cpp_checkpoint)
    tab('source')
    expect(page.get_by_test_id('workflow-demo-source-path')).to_have_text(math_path, timeout=30000)
    expect(page.get_by_test_id('workflow-demo-source-code')).to_have_text(math_text, use_inner_text=False, timeout=30000)
    note('Actual generated Ascend CANN math file', path=math_path, source_sha256=hashlib.sha256(math_text.encode()).hexdigest())
    hold(5)
    evidence.evaluate('(element) => { element.scrollTop = 230; }')
    note('CANN Softmax, stable Sort, weighting and normalization source')
    hold(4)
    tab('diff')
    first = page.get_by_test_id('workflow-demo-code-diff-file').first
    expect(first).to_have_attribute('data-variant', math_path)
    expect(first.get_by_test_id('workflow-demo-code-diff-generated').locator('code')).to_have_text(math_pair['generated_code'], use_inner_text=False)
    expect(first.get_by_test_id('workflow-demo-code-diff-original').locator('code')).to_have_text(math_pair['source_code'], use_inner_text=False)
    note('Literal original CUDA versus actual Ascend math Code Diff')
    hold(4)
    tab('log')
    expect(page.get_by_test_id('workflow-demo-log-worker-pid')).to_have_text(str(run['executor']['pid']))
    note('Recorded Python worker and genuine stage activity', worker_pid=run['executor']['pid'])
    hold(4)
    codegen = next(node for node in run['nodes'] if node['stage_id'] == 'construction.codegen')
    verified_event = next(event for event in events if event['type'] == 'stage.verified' and event.get('node_id') == codegen['id'])
    activity = page.locator(f'[data-testid="workflow-demo-log-activity-item"][data-variant="{verified_event["sequence"]}"]')
    activity.scroll_into_view_if_needed()
    note('Actual in-process generation event and published C++/ZIP files')
    hold(3)
    cpu_checkpoint = next(item for item in choices if 'CPU validation' in item['label'])
    continue_to(cpu_checkpoint)
    show_command(configure, 'Real CPU-reference CMake configuration argv', 3)
    page.get_by_test_id('workflow-demo-log-pid').scroll_into_view_if_needed()
    note('Actual recorded process PID, timestamps, duration and exit code')
    hold(3)
    show_command(build, 'Real make compilation command', 2)
    expect(page.get_by_test_id('workflow-demo-log-stdout')).to_have_text(build[3]['stdout'], use_inner_text=False)
    page.get_by_test_id('workflow-demo-log-stdout').scroll_into_view_if_needed()
    note('Complete actual compiler stdout')
    hold(3)
    show_command(test, 'Actual compiled CPU-reference test process', 3)
    expect(page.get_by_test_id('workflow-demo-log-stdout')).to_have_text(test[3]['stdout'], use_inner_text=False)
    page.get_by_test_id('workflow-demo-log-stdout').scroll_into_view_if_needed()
    note('Actual numeric test stdout: 352 outputs compared', pid=test[3]['pid'])
    hold(4)
    tab('build')
    expect(page.get_by_test_id('workflow-demo-cpu-reference-summary')).to_contain_text('352')
    page.get_by_test_id('workflow-demo-cpu-reference-summary').scroll_into_view_if_needed()
    note('CPU reference: 352 comparisons and per-function outcomes')
    hold(4)
    native_report = page.get_by_test_id('workflow-demo-native-evidence')
    expect(native_report).to_contain_text('NOT_RUN')
    native_report.scroll_into_view_if_needed()
    note('Separate actual native compilation/device/model NOT_RUN evidence')
    hold(4)
    outcome = choices[-1]
    continue_to(outcome)
    tab('downloads')
    package_link = page.locator(f'[data-testid="workflow-demo-artifact-download"][data-variant="{package["id"]}"]').first
    package_link.scroll_into_view_if_needed()
    note('Download the actual generated native source ZIP', package_sha256=package['sha256'])
    with page.expect_download(timeout=60000) as saved:
        package_link.click()
    downloaded = OUT / 'video-downloaded-native-source.zip'
    saved.value.save_as(str(downloaded))
    assert hashlib.sha256(downloaded.read_bytes()).hexdigest() == package['sha256']
    hold(3)
    tab('composition')
    page.get_by_test_id('workflow-demo-production-chain').scroll_into_view_if_needed()
    note('Final actual source-production composition; no new execution')
    hold(4)
    verify_prefix(page)
    assert not errors, errors
    assert all(item['method'] == 'GET' for item in requests)
    assert not any('/runs/' in item['url'] for item in requests)
    assert any('/replay?' in item['url'] and '&until=' in item['url'] for item in requests)
    assert before == {item['id'] for item in get('/recordings')['recordings']}
    page.screenshot(path=str(OUT / 'video-final-frame.png'))
    context.close()
    raw_path = str(video.path())
    browser.close()
report = {'recording_id': RUN_ID, 'read_only': True, 'raw_video': raw_path, 'capture_wall_seconds':round(time.monotonic()-started,3), 'viewport':{'width':1600,'height':1000}, 'math_path':math_path, 'package_sha256':package['sha256'], 'library_sha256':run['workflow_catalog_sha256'], 'scene_timeline':scenes, 'prefix_checks':prefixes, 'factory_requests':requests, 'page_errors':errors, 'checks':['Original built host UI, no source/style/DOM-content injection','Only real bounded backend replay SSE','Every observed graph matches actual event prefix','Exact full-ref partial selections and idle siblings','Exact native math and Code Diff bytes from actual published ZIP','Actual worker and command PIDs/argv/exit/stdout','CPU352 distinct from native NOT_RUN','Downloaded native source ZIP SHA matches publication','GET-only factory traffic and unchanged recording list; no production run']}
(OUT / 'monday-real-replay-recording.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'raw_video':raw_path,'duration_wall_s':report['capture_wall_seconds'],'checks':len(report['checks']),'page_errors':errors}), flush=True)
