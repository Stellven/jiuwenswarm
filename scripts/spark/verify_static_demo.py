"""Walk the extracted Runs 1–3 export and record Chromium request evidence."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from functools import partial
from hashlib import sha256
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
from threading import Thread
from urllib.parse import unquote, urlsplit

from playwright.sync_api import Error, expect, sync_playwright


RUNS = {
    1: {
        'node': 'wire_expert_scales',
        'node_count': 8,
        'capsule': 'weights.build_expert_scale_wiring',
        'diff': 'projections/prefill-arguments.diff',
        'report_link': 'Original lab handoff',
        'versions': ['8'],
    },
    2: {
        'node': 'plan_prefix_store',
        'node_count': 6,
        'capsule': 'engine.kv_reuse_lab',
        'diff': 'projections/prefix-reuse-arguments.diff',
        'report_link': 'Native release decision',
        'versions': ['9', '10', '11', '12'],
    },
    3: {
        'node': 'trace_dispatch',
        'node_count': 5,
        'capsule': 'engine.gpu_kernel_lab',
        'diff': 'evidence/30be3ad344c9fdddafc04d30deecdda7dbeb5466a681f3a12688817fc1ca9637.diff',
        'report_link': 'Pre-graph dispatch probe instrumentation diff',
        'versions': ['10'],
    },
}


class StaticHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@contextmanager
def local_fallback(root):
    handler = partial(StaticHandler, directory=root)
    with ThreadingHTTPServer(('127.0.0.1', 0), handler) as server:
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            yield f'http://127.0.0.1:{server.server_port}'
        finally:
            server.shutdown()
            worker.join()


class RequestEvidence:
    def __init__(self, context, page, root, origin):
        self.root = root
        self.origin = origin
        self.requests = []
        self.errors = []
        self.responses = []
        self.failures = []
        self.step = 'entry'
        cdp = context.new_cdp_session(page)
        cdp.send('Network.enable')
        cdp.on('Network.requestWillBeSent', lambda event: self.record(
            'chromium', event['request']['url'], event['request']['method'], event.get('type')))
        cdp.on('Network.webSocketCreated', lambda event: self.record(
            'chromium-websocket', event['url'], 'GET', 'WebSocket'))
        context.on('request', lambda request: self.record(
            'playwright', request.url, request.method, request.resource_type))
        context.on('requestfailed', lambda request: self.failures.append(
            {'url': self.display_url(request.url), 'failure': request.failure}))
        context.on('response', self.response)
        context.expose_binding('reportBlockedRequest', lambda _, url, directive: self.record(
            'csp', url, 'GET', directive))
        context.add_init_script("""addEventListener('securitypolicyviolation', ({ blockedURI, effectiveDirective }) => {
            if (/^(?:https?|wss?|file):/.test(blockedURI)) {
                void window.reportBlockedRequest(blockedURI, effectiveDirective);
            }
        });""")
        if hasattr(context, 'route_web_socket'):
            context.route_web_socket(re.compile(r'.*'), self.block_socket)
        context.route(re.compile(r'^https?://'), self.guard)
        page.on('pageerror', lambda error: self.errors.append(str(error)))

    def block_socket(self, socket):
        self.record('playwright-websocket', socket.url, 'GET', 'WebSocket')
        socket.close()

    def response(self, response):
        self.responses.append({'url': self.display_url(response.url), 'status': response.status})

    def display_url(self, url):
        if url.startswith('data:'):
            return url.split(',', 1)[0] + ',<embedded>'
        copy_url = self.root.as_uri() + '/'
        if url.startswith(copy_url):
            return 'file:///__extracted_copy__/' + url.removeprefix(copy_url)
        return url

    def classify(self, url, method):
        parsed = urlsplit(url)
        if parsed.scheme in ('about', 'data'):
            return 'embedded'
        if parsed.scheme == 'blob':
            return 'embedded' if url.startswith(('blob:null/', 'blob:file://', f'blob:{self.origin}/')) else 'outside'
        if method not in ('GET', 'HEAD'):
            return 'outside'
        if parsed.scheme == 'file' and not parsed.netloc and self.origin is None:
            path = Path(unquote(parsed.path)).resolve()
        elif self.origin and url.startswith(self.origin + '/'):
            path = (self.root / unquote(parsed.path).lstrip('/')).resolve()
        else:
            return 'outside'
        if path.is_relative_to(self.root) and (path.is_file() or path == self.root):
            return 'folder'
        return 'outside'

    def record(self, source, url, method, resource):
        self.requests.append({
            'step': self.step,
            'source': source,
            'url': self.display_url(url),
            'method': method,
            'resource': resource,
            'scope': self.classify(url, method),
        })

    def guard(self, route):
        request = route.request
        if self.classify(request.url, request.method) == 'folder':
            route.continue_()
        else:
            self.record('blocked', request.url, request.method, request.resource_type)
            route.abort('blockedbyclient')

    def summary(self):
        outside = [request for request in self.requests if request['scope'] == 'outside']
        origins = sorted({
            f'{parsed.scheme}://{parsed.netloc}' if parsed.netloc else f'{parsed.scheme}:'
            for request in self.requests
            if (parsed := urlsplit(request['url'])).scheme != 'data'
        })
        return {
            'request_origins': origins,
            'requests': self.requests,
            'outside_folder': outside,
            'failed_requests': self.failures,
            'responses': self.responses,
            'bad_responses': [response for response in self.responses if response['status'] >= 400],
            'page_errors': self.errors,
        }


def test(scope, name):
    return scope.get_by_test_id('factory-runs-' + name)


def variant(scope, name, value):
    return test(scope, name).and_(scope.locator(f'[data-variant={json.dumps(value)}]'))


class DemoWalk:
    def __init__(self, page, evidence, screenshots):
        self.page = page
        self.evidence = evidence
        self.screenshots = screenshots
        self.screenshots.mkdir(parents=True, exist_ok=True)
        self.run = None
        self.verified = {}

    def get(self, name):
        return test(self.page, name)

    def by_variant(self, name, value):
        return variant(self.page, name, value)

    def tab(self, name):
        tab = self.by_variant('panel-tab', name)
        tab.click()
        expect(tab).to_have_attribute('aria-pressed', 'true')

    def shot(self, name, anchor=None):
        label = f'run-{self.run}-{name}' if self.run else name
        if anchor is not None:
            anchor.scroll_into_view_if_needed()
        self.page.screenshot(path=self.screenshots / f'{label}.png', animations='disabled')

    def report(self, expected):
        self.evidence.step = f'run-{self.run}-report'
        self.get('attached-report').click()
        report = self.page.frame_locator('[data-testid="factory-runs-html-artifact"] iframe')
        title = report.locator('h1')
        report_type = 'Run report' if self.run == 3 else 'lab report'
        expect(title).to_contain_text(f'Run {self.run}')
        expect(title).to_contain_text(report_type)
        letters = report.locator('.arm-names')
        expect(letters).to_contain_text('What the names mean')
        for letter in 'AQBCD':
            expect(letters.get_by_text(letter, exact=True)).to_be_visible()
        expect(report.get_by_role('heading', name='Factory verification and capsule use')).to_be_visible()
        expect(report.get_by_role('table').filter(has_text='CC verifier').first).to_be_visible()
        self.shot('report', title)
        if self.run in (1, 2):
            expect(report.locator('.metric-charts .chart-bar').first).to_be_visible()
            expect(report.locator('.memory-chart').first).to_be_visible()
            self.shot('report-memory', report.locator('.memory-chart').first)
        else:
            expect(report.get_by_role('heading', name='Dispatch eligibility')).to_be_visible()
            expect(report.get_by_role('table').filter(has_text='CC verifier').first).to_contain_text('Not reached')
        report_link = report.get_by_role('link', name=expected['report_link'], exact=True)
        expect(report_link).to_have_attribute('data-artifact-href', re.compile(r'^\.\./'))
        report_link.click()
        expect(self.by_variant('panel-tab', 'artifacts')).to_have_attribute('aria-pressed', 'true')
        expect(self.get('file-title')).to_be_visible()
        viewer = self.get('diff-hunk').first if self.run == 3 else self.get('data-entry').first
        expect(viewer).to_be_visible()
        self.shot('report-source', viewer)

    def story(self):
        self.evidence.step = f'run-{self.run}-story'
        self.tab('overview')
        scrubber = self.get('scrubber')
        scrubber.press('Home')
        expect(self.get('curated-focus-title')).to_be_visible()
        initial = scrubber.input_value()
        self.get('step-next').click()
        expect(scrubber).not_to_have_value(initial)
        self.get('step-prev').click()
        expect(scrubber).to_have_value(initial)
        expect(self.get('curated-step').first).to_be_visible()
        self.shot('story', self.get('curated-focus-title'))
        self.get('curated-focus-key-file').first.click()
        expect(self.by_variant('panel-tab', 'artifacts')).to_have_attribute('aria-pressed', 'true')
        expect(self.get('file-title')).to_be_visible()
        expect(self.get('file-status')).to_have_count(0)

    def graph(self, expected):
        self.evidence.step = f'run-{self.run}-graph'
        self.tab('graph')
        self.get('scrubber').press('End')
        self.by_variant('demo-task-mode-option', 'run').click()
        chain = self.by_variant('demo-task-chain', 'run')
        expect(chain).to_be_visible()
        cards = test(chain, 'demo-task-card')
        expect(cards).to_have_count(expected['node_count'])
        node_count = cards.count()
        for card in cards.all():
            expect(test(card, 'demo-node-verifier')).to_be_visible()
            for fact in test(card, 'cc-facts').all():
                expect(test(fact, 'cc-use')).to_be_visible()
                expect(test(fact, 'cc-verifier')).to_be_visible()
        card = variant(chain, 'demo-task-card', expected['node'])
        fact = variant(card, 'cc-facts', expected['capsule'])
        expect(test(fact, 'cc-use')).to_have_attribute('data-variant', 'used')
        expect(test(fact, 'cc-verifier')).to_have_attribute('data-variant', 'pass')
        if self.run == 3:
            expect(self.by_variant('demo-verifier-status', 'not-reached').first).to_be_visible()
        self.shot('graph-run')
        test(card, 'demo-task-node').click()
        node_evidence = self.by_variant('node-evidence', expected['node'])
        expect(node_evidence).to_be_visible()
        expect(test(node_evidence, 'demo-node-verifier')).to_be_visible()
        self.shot('graph-node', node_evidence)
        capsule_url = variant(card, 'demo-task-node-cc-link', expected['capsule']).get_attribute('href')
        self.by_variant('demo-task-mode-option', 'plan').click()
        plan_card = variant(self.by_variant('demo-task-chain', 'plan'), 'demo-task-card', expected['node'])
        expect(test(plan_card, 'demo-task-draft')).to_be_visible()
        toggle = test(plan_card, 'plan-execution-toggle')
        toggle.click()
        expect(test(plan_card, 'demo-node-verifier')).to_be_visible()
        self.shot('graph-plan', toggle)
        self.verified[str(self.run)] = {'graph_nodes': node_count, 'capsule_url': capsule_url}

    def contracts(self, expected):
        self.evidence.step = f'run-{self.run}-contracts'
        self.tab('contract')
        revisions = self.get('contract-version')
        expect(revisions).to_have_count(len(expected['versions']))
        signatures = set()
        for revision in expected['versions']:
            button = self.by_variant('contract-version', revision)
            button.click()
            expect(button).to_have_attribute('aria-pressed', 'true')
            contract = self.get('replay-contract')
            viewer = test(contract, 'data-viewer')
            expect(test(viewer, 'data-entry').first).to_be_visible()
            signatures.add(sha256(viewer.inner_text().encode()).hexdigest())
            self.shot(f'contract-{revision}', button)
        assert len(signatures) == len(expected['versions']), 'Contract revisions rendered identical text'
        self.get('contract-open-file').click()
        expect(self.get('file-title')).to_be_visible()
        expect(self.get('data-entry').first).to_be_visible()
        self.tab('node-contracts')
        self.get('node-contract-selector').select_option(expected['node'])
        comparison = self.get('planner-comparison')
        expect(test(comparison, 'planner-draft')).to_be_visible()
        expect(test(comparison, 'planner-final')).to_be_visible()
        expect(test(comparison, 'planner-never-weaker')).to_have_attribute('data-variant', 'admitted')
        expect(test(comparison, 'planner-diff-field').first).to_be_visible()
        self.shot('node-contracts', comparison)
        self.verified[str(self.run)]['contract_revisions'] = expected['versions']

    def events_and_files(self, expected):
        self.evidence.step = f'run-{self.run}-events'
        self.tab('events')
        event = self.get('recorded-event').first
        test(event, 'recorded-event-toggle').click()
        expect(test(event, 'raw-source')).to_be_visible()
        self.shot('events', event)
        self.evidence.step = f'run-{self.run}-diff'
        self.tab('artifacts')
        self.get('file-filters').get_by_role('button', name='Diffs', exact=True).click()
        diff = self.by_variant('file', expected['diff'])
        if not diff.is_visible():
            self.get('files-search').fill(expected['diff'])
        diff.click()
        hunk = self.get('diff-hunk').first
        expect(hunk).to_contain_text('@@')
        expect(self.get('diff-file').first).to_be_visible()
        self.shot('diff', hunk)
        self.get('diff-mode-raw').click()
        expect(self.get('diff-raw')).to_contain_text('@@')
        self.verified[str(self.run)]['diff'] = expected['diff']

    def walk(self, entry):
        self.page.goto(entry)
        expect(self.get('static-copy')).to_have_text('Static copy · Nov 27, 2026 · Runs 1–3')
        logo = self.page.get_by_test_id('session-sidebar-logo').locator('img')
        expect(logo).to_be_visible()
        expect(logo).to_have_js_property('complete', True)
        assert logo.evaluate('image => image.naturalWidth > 0'), 'Sidebar logo failed to load'
        expect(self.get('demo-group')).to_be_visible()
        expect(self.get('run')).to_have_count(3)
        expect(self.page.get_by_role('button', name='All runs', exact=True)).not_to_be_visible()
        for control in ('launch-button', 'live', 'node-operator'):
            expect(self.get(control)).not_to_be_visible()
        self.shot('demo-list')
        for self.run, expected in RUNS.items():
            self.evidence.step = f'run-{self.run}-entry'
            item = self.get('run').filter(has_text=re.compile(rf'\bRun {self.run}\b'))
            item.click()
            expect(self.get('run-title')).to_contain_text(f'Run {self.run}')
            expect(item).to_have_attribute('aria-pressed', 'true')
            self.report(expected)
            self.story()
            self.graph(expected)
            self.contracts(expected)
            self.events_and_files(expected)
        self.run = None
        self.evidence.step = 'capsules'
        self.page.locator('[data-testid="session-sidebar-nav-item"][data-variant="capabilityCapsules"]').click()
        expect(self.get('capsule-catalog-title')).to_be_visible()
        self.shot('capsules')
        for number, result in self.verified.items():
            run_id = int(number)
            self.page.locator(f'a[href={json.dumps(result["capsule_url"])}]').first.click()
            activity = self.get('capsule-node-activity')
            row = variant(activity, 'capsule-node-activity-row', RUNS[run_id]['node']).filter(has_text=f'Run {run_id}')
            expect(row).to_be_visible()
            expect(test(row, 'cc-use')).to_have_attribute('data-variant', 'used')
            self.shot(f'capsules-run-{run_id}', row)
            back = self.get('capsule-back')
            back.click()
            expect(self.get('capsule-catalog-title')).to_be_visible()


def browser_walk(browser, root, entry, output, mode, *, origin=None, offline=True):
    context = browser.new_context(
        offline=offline, service_workers='block',
        viewport={'width': 1536, 'height': 1100}, locale='en-US',
    )
    page = context.new_page()
    evidence = RequestEvidence(context, page, root, origin)
    walk = DemoWalk(page, evidence, output / 'screenshots' / mode)
    result = {
        'chromium_version': browser.version,
        'offline_context': offline,
        'entry': evidence.display_url(entry),
        'package_sha256': {
            name: sha256((root / name).read_bytes()).hexdigest()
            for name in ('index.html', 'data.js')
        },
        'passed': False,
    }
    try:
        walk.walk(entry)
        audit = evidence.summary()
        for key in ('outside_folder', 'failed_requests', 'bad_responses', 'page_errors'):
            assert not audit[key], (key, audit[key])
        result['passed'] = True
    except Exception as error:
        result['error'] = str(error)
        result['failed_step'] = evidence.step
    finally:
        result.update(evidence.summary())
        result['surfaces'] = walk.verified
        (output / f'requests-{mode}.json').write_text(json.dumps(result, indent=2) + '\n')
        context.close()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('extracted', type=Path, help='Folder extracted from the final ZIP')
    parser.add_argument('evidence', type=Path, help='Output folder outside the extracted site')
    parser.add_argument('--mode', choices=('file', 'http', 'both'), default='both')
    args = parser.parse_args()
    root, output = args.extracted.resolve(), args.evidence.resolve()
    assert (root / 'index.html').is_file(), root
    assert not output.is_relative_to(root), 'Keep verification evidence outside the extracted copy'
    expect.set_options(timeout=12000)
    results = {}

    with sync_playwright() as playwright, local_fallback(root) as origin:
        browser = playwright.chromium.launch(channel='chromium', args=[
            '--disable-gpu', '--no-proxy-server', '--disable-background-networking',
            '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1',
        ])
        if args.mode in ('file', 'both'):
            results['file'] = browser_walk(browser, root, (root / 'index.html').as_uri(), output, 'file')
        if args.mode in ('http', 'both'):
            entry = origin + '/'
            offline_result = browser_walk(browser, root, entry, output, 'http-offline', origin=origin)
            if 'ERR_INTERNET_DISCONNECTED' in offline_result.get('error', ''):
                print('Chromium offline emulation blocks the loopback server. Repeating with the folder-only request guard.')
                results['http'] = browser_walk(browser, root, entry, output, 'http', origin=origin, offline=False)
            else:
                results['http'] = offline_result
        browser.close()

    for mode, result in results.items():
        print(f'{mode} {"PASS" if result["passed"] else "FAIL"} '
              f'({len(result["requests"])} request events, {len(result["outside_folder"])} outside the folder)')
        if 'error' in result:
            print(result['error'])
    return int(not all(result['passed'] for result in results.values()))


if __name__ == '__main__':
    raise SystemExit(main())
