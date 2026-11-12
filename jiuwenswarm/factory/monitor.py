"""Read-only stdlib live monitor. No model calls, reconciliation or Store initialization."""
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
from urllib.parse import parse_qs, urlsplit
from .store import FactoryError
from .redact import sanitize
from .story import load_source, build_events, chain_links, ACTIVE
from .telemetry import home_path, read_events


def tasks(home):
    # Copy WAL and DB using the same stable read discipline as story.
    paths = [home / 'factory.sqlite', home / 'factory.sqlite-wal']
    if not paths[0].exists():
        return []
    def stamps():
        return [(p.stat().st_size, p.stat().st_mtime_ns) if p.exists() else None for p in paths]
    for _ in range(5):
        before = stamps()
        with tempfile.TemporaryDirectory(prefix='factory-monitor-') as directory:
            for p in paths:
                if p.exists():
                    shutil.copyfile(p, Path(directory) / p.name)
            if before != stamps():
                continue
            with closing(sqlite3.connect(Path(directory) / 'factory.sqlite')) as db:
                db.row_factory = sqlite3.Row
                return [dict(row) for row in db.execute('SELECT task_id,objective,created FROM tasks ORDER BY created DESC')]
    raise ValueError('Store changed during read; retry')


STATES = {'integrate': 'integrating', 'build': 'building', 'measure': 'measuring',
          'keep_component': 'kept', 'revert_component': 'reverted'}


def engine_stack(data):
    """Base engine plus each component the agent named in a decision, in first-mention order.
    Speeds come from the component's A/B result (or, for a single-component task, its last lab run)."""
    task = data['tasks'][0]
    base = dict(name=task.get('source', {}).get('pre_integration_commit') or 'bare engine',
                state='base', ms_per_token=None, ratio=None)
    rows = {}
    for decision in sorted(data.get('decisions', []), key=lambda d: d['rev']):
        action = decision.get('action', {})
        name, kind = action.get('component'), action.get('type')
        if name and kind in STATES:
            row = rows.setdefault(name, dict(name=name, state=None, ms_per_token=None, ratio=None))
            row['state'] = STATES[kind]
            if kind in {'keep_component', 'revert_component'}:
                row.update(reason=action.get('reason'), ratio=action.get('ratio', row['ratio']))
    for obs in data.get('observations', []):
        values = obs.get('values', {})
        if obs.get('kind') == 'ab_result' and values.get('component'):
            row = rows.setdefault(values['component'], dict(name=values['component'], state='measuring',
                                                            ms_per_token=None, ratio=None))
            arms = values.get('per_arm_ms') or {}
            row.update(ms_per_token=arms.get('candidate'), gate=values.get('gate'))
            row['ratio'] = row['ratio'] or values.get('ratio')
            base['ms_per_token'] = base['ms_per_token'] or arms.get('base')
    if not rows and task.get('component_cc'):
        # Single-component task (the recorded demo): its outcome and last lab speed.
        evaluations = data.get('evaluations', [])
        speed = (evaluations[-1].get('inputs', {}).get('run', {}).get('details', {}).get('eval_ms_per_token')
                 if evaluations else None)
        outcome = data['_meta'].get('outcome')
        rows[task['component_cc']] = dict(name=task['component_cc'], ms_per_token=speed, ratio=None,
            state='kept' if outcome == 'accept' else 'reverted' if outcome in {'reject', 'report_inconclusive'}
            else 'integrating')
    stack = [base, *rows.values()]
    for row in stack[1:]:
        if row['ratio'] is None and base['ms_per_token'] and row['ms_per_token']:
            row['ratio'] = base['ms_per_token'] / row['ms_per_token']
    return stack


def tail(home, attempt):
    """Last lines of whatever the attempt is writing right now: its build log, lab stderr or jobq log."""
    aid = attempt['attempt_id']
    roots = [p for pattern in (f'builds/{aid}*', f'lab-spool/{aid}*') for p in home.glob(pattern)]
    qdir = attempt.get('resources', {}).get('jobq_dir')
    files = [p for root in roots for p in root.rglob('*')
             if p.is_file() and (p.suffix in {'.log', '.stdout', '.stderr'} or p.name == 'stderr.txt')]
    if qdir and attempt.get('jobq_id'):
        files.append(Path(qdir) / (Path(attempt['jobq_id']).name + '.log'))
    files = [p for p in files if p.is_file() and p.stat().st_size]
    if not files:
        return []
    newest = max(files, key=lambda p: p.stat().st_mtime)
    with newest.open('rb') as stream:
        stream.seek(max(0, newest.stat().st_size - 4096))
        lines = stream.read().decode(errors='replace').splitlines()[-14:]
    return [line[:160] for line in lines]


def job(home, attempt_id):
    for task in tasks(home):
        for attempt in load_source(task['task_id'], home).get('attempts', []):
            if attempt['attempt_id'] == attempt_id:
                return dict(attempt=attempt, state=attempt['state'], log=tail(home, attempt))
    raise ValueError('Attempt not found')


def make_handler(home=None):
    home = home_path(home)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            url = urlsplit(self.path)
            query = parse_qs(url.query)
            def arg(key):
                return query.get(key, [''])[0]
            try:
                if url.path == '/':
                    body, mime = HTML.encode(), 'text/html; charset=utf-8'
                else:
                    if url.path == '/api/tasks':
                        value = tasks(home)
                    elif url.path == '/api/story':
                        data = load_source(arg('task'), home)
                        value = dict(events=build_events(data), task=data['tasks'][0], meta=data['_meta'], chain=chain_links(data),
                                     engine_stack=engine_stack(data), latest_decision=max(data.get('decisions', []), key=lambda d: d['rev'], default=None),
                                     active_jobs=[a for a in data.get('attempts', []) if a['state'] in ACTIVE])
                    elif url.path == '/api/telemetry':
                        value = read_events(home, arg('task') or None, arg('since'))
                    elif url.path == '/api/job':
                        value = job(home, arg('attempt'))
                    else:
                        self.send_error(404)
                        return
                    body, mime = json.dumps(sanitize(value), ensure_ascii=False).encode(), 'application/json; charset=utf-8'
                self.send_response(200)
                self.send_header('Content-Type', mime)
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(body)
            except (FactoryError, ValueError, OSError, sqlite3.Error, KeyError) as exc:
                body = json.dumps(dict(error=sanitize(str(exc)))).encode()
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
    return Handler


def make_server(home=None, bind='127.0.0.1', port=8787):
    return ThreadingHTTPServer((bind, port), make_handler(home))


def serve(home=None, bind='127.0.0.1', port=8787):
    with make_server(home, bind, port) as server:
        print(f'Factory monitor listening on {server.server_address[0]}:{server.server_address[1]}', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


HTML = (Path(__file__).with_name('monitor.html')).read_text()
