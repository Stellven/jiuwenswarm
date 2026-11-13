"""Offline ten-minute presentation over the existing story, telemetry and plan views.

Only presentation state is mutable. Evidence is read through story's snapshot API;
no Store, controller, job reconciliation, model, build or inference is started.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, unquote
from urllib.request import Request, urlopen

from .redact import sanitize, scrub_bytes
from .store import FactoryError
from .story import load_source, render_story
from .taskgraph import from_records
from .telemetry import home_path, read_events

ROOT = Path(__file__).resolve().parents[2]
RUN4 = 'factory-bd173c082bf34ae3b8471938c19b8068'
RUN5 = 'factory-53db494559954fc6a690a9a014afbf21'
PORT = 8790
DEFAULT_PACK = Path('~/.jiuwenswarm-factory/demo-pack').expanduser()
E2E = ('T=$(jiuwenswarm factory init jiuwenswarm/factory/tasks/expert-streaming-qwen36.json) '
       '&& jiuwenswarm factory run "$T" --grant process.exec --grant workspace.read '
       '--grant workspace.write --grant gpu.use')


def dump(value):
    return json.dumps(sanitize(value), indent=2, ensure_ascii=False)


def run_view(command, home, timeout=15):
    """Only caller-owned allowlisted view arguments, never shell input from HTTP."""
    allowed = (command == ['capsules', '--plain']
               or (len(command) == 3 and command[0] == 'story' and command[2] == '--plain'
                   and not command[1].startswith('-'))
               or (len(command) == 4 and command[0] == 'plan' and command[2:] == ['--rev', '13']
                   and not command[1].startswith('-')))
    if not allowed:
        raise ValueError('Demo permits only capsule inventory, story and revision-13 plan views')
    proc = subprocess.run([sys.executable, '-m', 'jiuwenswarm.factory.cli', '--home', str(home), *command],
                          stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout,
                          env=dict(os.environ, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE='1'))
    if proc.returncode:
        raise ValueError(scrub_bytes(proc.stderr).decode(errors='replace')[:500])
    return scrub_bytes(proc.stdout).decode(errors='replace')


def build(out=DEFAULT_PACK, home=None, *, root=ROOT, siminfeng=None, run4=RUN4, run5=RUN5):
    """Assemble evidence, disclosing missing inputs instead of inventing them.

    root/siminfeng/task overrides also allow a tiny disposable store fixture.
    Build into an external directory when factory home is read-only.
    """
    home, out, root = home_path(home), Path(out).expanduser().resolve(), Path(root).resolve()
    if out == home or home.is_relative_to(out):
        raise ValueError('Pack must not contain or replace the evidence store')
    if out.exists() and any(out.iterdir()) and not (out / 'sections.json').is_file():
        raise ValueError('Refusing to overwrite a non-pack directory')
    out.mkdir(parents=True, exist_ok=True)
    (out / 'assets').mkdir(exist_ok=True)
    lab = Path(siminfeng or os.environ.get('SIMINFENG_ROOT', '/home/muk/projects/siminfeng')) / 'experiments/jetson/OM'
    gaps, assets = [], {}
    d4, d5 = load_source(run4, home), load_source(run5, home)

    def write(name, value):
        path = out / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)
        assets[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        return name

    def file(path, name=None):
        path = Path(path)
        if not path.is_file():
            gaps.append(str(path))
            return None
        name = 'assets/' + (name or path.name)
        write(name, scrub_bytes(path.read_bytes()).decode(errors='replace'))
        return dict(path=str(path), asset=name, sha256=assets[name])

    def blob(data, artifact_id):
        record = next((a for a in data['artifacts'] if a['artifact_id'] == artifact_id), None)
        if record is None:
            gaps.append(f'{data["tasks"][0]["task_id"]}: artifact {artifact_id}')
            return '', {}
        path = home / record['location']
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != record['sha256']:
            raise ValueError('Artifact digest mismatch: ' + artifact_id)
        text = scrub_bytes(raw).decode(errors='replace')
        name = 'assets/' + record['sha256'] + '.txt'
        write(name, text)
        return text, dict(task_id=record['task_id'], record_id=artifact_id, path=str(path),
                          sha256=record['sha256'], asset=name)

    sections = []
    def add(key, title, seconds, label, explanation, text='', sources=(), frame=None, command=None):
        sections.append(dict(id=key, title=title, duration=seconds, label=label, explanation=explanation,
                             text=text, sources=[s for s in sources if s], frame=frame, command=command))

    for key, title in [('engine', 'The engine problem'), ('factory', 'A software factory that uses CCs')]:
        source = file(root / f'demo/assets/slides/{key}.html', f'{key}-section.html')
        frame = None
        if source:
            # Original single-section art remains untouched. Scale a 1920x1080 stage.
            frame = write(f'assets/{key}.html', '<!doctype html><meta charset="utf-8"><style>'
                          '*{box-sizing:border-box}body{margin:0;background:#F7F6F2;overflow:hidden}'
                          'p,h2{margin:0}section{width:1920px;height:1080px;position:absolute;transform-origin:0 0}'
                          'x-connector:before{content:"→";font:40px Arial}</style>'
                          + (out / source['asset']).read_text() + '<script>function fit(){let s=document.querySelector("section");'
                          'let z=Math.min(innerWidth/1920,innerHeight/1080);s.style.transform=`scale(${z})`;'
                          's.style.left=(innerWidth-1920*z)/2+"px";s.style.top=(innerHeight-1080*z)/2+"px"}'
                          'onresize=fit;fit()</script>')
        add(key, title, 30, 'SLIDE', 'Opening explanation; offline local slide with system font fallback.',
            sources=[source], frame=frame, command=['capsules', '--plain'])

    contract_source = file(root / 'jiuwenswarm/factory/contracts/qwen36-bare-greedy-v1.json')
    contract = json.loads((out / contract_source['asset']).read_text()) if contract_source else {}
    brief = file(root / 'jiuwenswarm/factory/tasks/expert-streaming-qwen36.json')
    reference = contract.get('reference', {})
    stdout_record = next((a for a in d4['artifacts'] if a['sha256'] == reference.get('stdout_sha256')), None)
    stdout, stdout_source = blob(d4, stdout_record['artifact_id']) if stdout_record else ('', {})
    if not stdout_record:
        gaps.append('Run 4 frozen reference stdout')
    single = [e for e in d4['evaluations'] if 'run' in e.get('inputs', {})]
    baseline = single[0] if single else {}
    task_source = dict(task_id=run4, record_id=run4, path=str(home / 'factory.sqlite'))
    add('baseline', 'Plain llama.cpp + the task contract', 30, 'RECORDED',
        'Plain cf34d311; frozen greedy continuation. The Run 4 task is historical; the current brief is also copied.',
        dump(reference) + '\n\nGenerated output (frozen reference):\n' + stdout
        + '\nRun 4 task:\n' + dump(d4['tasks'][0]) + '\nBare evaluation:\n' + dump(baseline)
        + '\nCurrent brief:\n' + ((out / brief['asset']).read_text() if brief else ''),
        [contract_source, brief, stdout_source, task_source,
         dict(task_id=run4, record_id=baseline.get('eval_id'), image_id=reference.get('image_id'))],
        command=['story', run4, '--plain'])

    telemetry = read_events(home, run4)
    materials = [e for e in telemetry if e['event'] == 'cc.material' and e.get('material')][:4]
    calls = [e for e in telemetry if e['event'] == 'cc.call' and e.get('capability') != 'evidence.read'][:4]
    session = home / 'sessions' / (run4 + '.jsonl')
    pairs, pending = [], {}
    if session.is_file():
        for line in session.open():
            event = json.loads(line)
            call = event.get('tool_call', {})
            if call.get('name', '').endswith(('cc_call', 'cc_material')):
                pending[call.get('tool_call_id')] = event
            key = event.get('tool_call_id') if event.get('event_type') == 'chat.tool_result' else None
            if key in pending:
                pairs.append(dict(request=pending.pop(key), result=event))
                if len(pairs) >= 3:
                    break
    if not materials or not calls:
        gaps.append('Run 4 capsule material/call telemetry')
    if not pairs:
        gaps.append('Run 4 request/result transcript pairs')
    compact_pairs = []
    for pair in pairs:
        result = json.loads(pair['result']['result'])
        texts = result.get('result', {}).get('content', [])
        receipts = []
        for item in texts:
            try:
                receipt = json.loads(item.get('text', ''))
            except (ValueError, TypeError):
                continue
            if isinstance(receipt, dict) and 'call' in receipt:
                receipts.append({key: receipt.get(key) for key in
                                 ('call', 'key', 'release', 'capability', 'attempt', 'state', 'completeness', 'reason', 'assessment')})
        compact_pairs.append(dict(request=pair['request']['tool_call'],
                                  tool_call_id=pair['result']['tool_call_id'], receipts=receipts,
                                  result_status=result.get('status')))
    cc_asset = write('assets/run4-cc-receipts.json', dump(dict(materials=materials, calls=calls, transcript_pairs=pairs)))
    add('capsules', 'JiuwenSwarm invokes Capability Capsules', 35, 'RECORDED',
        'Material reads and cc_call receipts from Run 4. Submission receipts and completed results are distinct evidence.',
        dump(dict(material_reads=materials, cc_call_receipts=compact_pairs, call_telemetry=calls)),
        [dict(task_id=run4, path=str(home / 'telemetry/events.jsonl'),
              record_ids=[e['seq'] for e in materials + calls], asset=cc_asset),
         dict(task_id=run4, path=str(session))], command=['story', run4, '--plain'])

    # Find integration builds by their recorded tag, then read the immutable request/receipt.
    diff_sources, diff_text = [], []
    for component in ('fill', 'pregate'):
        observation = next((o for o in d4['observations'] if o['kind'] == 'build_result'
                            and f'-{component}-' in o['values'].get('tag', '')), None)
        if not observation:
            gaps.append(f'Run 4 {component} build'); continue
        aid = observation['obs_id'].removesuffix(':build-result')
        request_text, request_source = blob(d4, aid + ':request')
        receipt, receipt_source = blob(d4, aid + ':receipt')
        build_record, build_source = blob(d4, aid + ':build-record')
        request = json.loads(request_text)['request']
        source = request['source']
        # Store requests pin the source; git show is strictly read-only. An existing
        # sanitized export is a portable fallback if the original checkout is gone.
        try:
            proc = subprocess.run(['git', '-C', source['path'], 'show', '--format=fuller', source['commit'], '--'],
                                  capture_output=True, timeout=10, env=dict(os.environ, GIT_OPTIONAL_LOCKS='0'))
            if proc.returncode:
                raise ValueError('source unavailable')
            diff = scrub_bytes(proc.stdout).decode(errors='replace')
            diff_path = source['path'] + '@' + source['commit']
        except (OSError, ValueError, subprocess.TimeoutExpired):
            exported = root / f'artifacts/factory/evidence/{run4}/source/{aid}.diff'
            if not exported.is_file():
                gaps.append(f'{component}: source diff {source["commit"]}'); continue
            diff, diff_path = exported.read_text(), str(exported)
            if not diff.startswith('commit ' + source['commit']):
                raise ValueError('Exported diff commit does not match store request')
        asset = write(f'assets/{component}.diff', diff)
        # Actual hunk headers and context around hook sites, plus the header interface.
        chunks = re.split(r'(?=^diff --git )', diff, flags=re.M)
        excerpts = []
        for chunk in chunks:
            if chunk.startswith('diff --git a/src/llama-context.cpp'):
                lines = chunk.splitlines()
                indices = [i for i, line in enumerate(lines) if re.search(r'ctx\.expert_fill_selected|ctx\.expert_pregate' , line)]
                selected = set(range(min(5, len(lines))))
                for i in indices[-3:]:
                    selected.update(range(max(0, i-4), min(len(lines), i+9)))
                excerpts.append('\n'.join(lines[i] for i in sorted(selected)))
            if chunk.startswith('diff --git a/src/llama-expert-fill.h'):
                lines = chunk.splitlines()
                selected = set(range(min(8, len(lines))))
                for i, line in enumerate(lines):
                    if re.search(r'class ExpertFiller|struct Range|void fill\(', line):
                        selected.update(range(max(0, i-1), min(len(lines), i+10)))
                excerpts.append('\n'.join(lines[i] for i in sorted(selected)))
        diff_text.append(f'{component}: {source["commit"]} → {observation["values"]["image_id"]}\n'
                         + '\n'.join(excerpts) + '\nBuild receipt:\n' + receipt)
        diff_sources.extend([request_source, receipt_source, build_source,
                             dict(task_id=run4, record_id=observation['obs_id'], commit=source['commit'],
                                  image_id=observation['values']['image_id'], path=diff_path, asset=asset)])
    add('source', 'Source changes → built image', 35, 'RECORDED',
        'Run 4 expert_fill and expert_pregate integration commits; hook excerpts and completed build receipts.',
        '\n\n'.join(diff_text), diff_sources, command=['story', run4, '--plain'])

    activity = file(lab / 'J-XS4-activity/activity.html', 'activity.html')
    activity_log = file(lab / 'J-XS4-activity/stderr.txt', 'activity-stderr.txt')
    activity_image = file(lab / 'J-XS4-activity/image.id', 'activity-image.id')
    activity_caption = 'Readiness counters unavailable'
    if activity_log:
        matches = re.findall(r'^expert_readiness: stats (.*)$', (out / activity_log['asset']).read_text(), re.M)
        counters = dict(re.findall(r'(\w+)=(\d+)', matches[-1])) if matches else {}
        if counters and int(counters.get('decode_selected', 0)):
            numbers = {k: int(v) for k, v in counters.items()}
            ready = lambda group: 100*numbers['decode_ready_bytes_'+group]/(numbers['decode_ready_bytes_'+group]+numbers['decode_missing_bytes_'+group])
            activity_caption = ('%.0f%% of predicted vs %.0f%% of unpredicted expert bytes ready before demand; %.0f%% predicted.'
                                % (ready('predicted'), ready('unpredicted'),
                                   100*numbers['decode_selected_predicted']/numbers['decode_selected']))
        else:
            gaps.append('J-XS4 readiness counters')
    add('activity', 'Selected vs predicted experts', 35, 'SEPARATE CAPTURE',
        'Separate unscored capture run (J-XS4), image factory/llamacpp:xs-trace. '
        + activity_caption,
        sources=[activity, activity_log, activity_image,
                 dict(image_tag='factory/llamacpp:xs-trace', capture='J-XS4, unscored',
                      image_id=(out / activity_image['asset']).read_text().strip() if activity_image else None)],
        frame=activity['asset'] if activity else None, command=['capsules', '--plain'])

    decision = next((d for d in d5['decisions'] if d['rev'] == 13), None)
    graphs, graph_sources = [], []
    for rev in (12, 13):
        try:
            graph = from_records(d5, rev)
            asset = write(f'assets/run5-plan-{rev}.json', dump(graph))
            graphs.append(f'BEFORE / graph rev {rev}' if rev == 12 else f'AFTER / graph rev {rev}')
            graphs.append('\n'.join(f'[{n["state"]}] {n["node_id"]}: {n["title"]}\n'
                                    + '  ← ' + (', '.join(n['depends_on']) or '(root)')
                                    for n in graph['nodes']))
            graph_sources.append(dict(task_id=run5, graph_rev=rev, asset=asset,
                                      record_ids=[f'{run5}:plan:{r["rev"]}' for r in graph['history']]))
        except (ValueError, FactoryError):
            gaps.append(f'{run5}: graph rev {rev}')
    if not decision:
        gaps.append(f'{run5}: decision 13')
    cited = [r for table in ('observations', 'artifacts') for r in d5[table]
             if (r.get('obs_id') or r.get('artifact_id')) in (decision or {}).get('evidence_ids', [])]
    add('revision', 'Evidence changes the plan', 40, 'RECORDED',
        'Run 5 excerpt; Run 5 was held for later and kept no component. CONFIG_MISSING on the router-only image '
        '→ integrate 03–08 switched off for strict reporting; router measure moves after the new build.',
        (dump((decision or {}).get('observations', '')) + '\n\nHypothesis: ' + (decision or {}).get('hypothesis', '')
         + '\n\nAction: ' + dump((decision or {}).get('action', {}))
         + '\n\nStop condition: ' + (decision or {}).get('stop_condition', '')
         + '\n\n' + '\n\n'.join(graphs)),
        [dict(task_id=run5, record_id=(decision or {}).get('decision_id'), path=str(home/'factory.sqlite')),
         *[dict(task_id=run5, record_id=r.get('obs_id', r.get('artifact_id')),
                path=str(home / r['location']) if r.get('location') else str(home/'factory.sqlite')) for r in cited],
         *graph_sources], command=['plan', run5, '--rev', '13'])

    report = file(lab / 'J-OM13/REPORT.md', 'J-OM13-REPORT.md')
    report_text = (out / report['asset']).read_text() if report else ''
    means = dict(re.findall(r'^\| (base|factory) \| ([\d.]+) \|', report_text, re.M))
    result = ('J-OM13: plain %.1f vs factory engine %.1f ms/token (%.2f×). 12-run ABBA; identical output.'
              % (float(means['base']), float(means['factory']), float(means['base'])/float(means['factory'])) if len(means)==2 else 'J-OM13 result unavailable')
    lab_values = [e.get('inputs', {}).get('run', {}).get('details', {}).get('eval_ms_per_token') for e in single]
    add('result', 'Result: same output, faster engine', 35, 'RECORDED', result,
        result + '\nRun 4 single lab runs (single-run, not ABBA): ' + ' → '.join(str(x) for x in lab_values)
        + '\n\nGenerated output:\n' + stdout + '\n\n' + report_text,
        [report, stdout_source, *[dict(task_id=run4, record_id=e['eval_id']) for e in single]],
        command=['story', run4, '--plain'])

    handoff = file(root / 'RSI-START-HERE.md')
    manifest = file(root / 'jiuwenswarm/factory/ccs/expert_streaming/cc.yaml', 'expert-streaming-cc.yaml')
    handoff_text = (out / handoff['asset']).read_text() if handoff else ''
    add('handoff', 'Handoff: engine.expert_streaming 2.0.0', 25, 'RECORDED',
        'Versioned capsule, evidence and RSI starting point; tag cc-rsi-v1.',
        handoff_text, [handoff, manifest], command=['capsules', '--plain'])

    backups = []
    for title, path in [('Source map', 'jiuwenswarm/factory/ccs/expert_streaming/SOURCE-MAP.md'),
                        ('Ontology', 'jiuwenswarm/factory/ccs/expert_streaming/ONTOLOGY.yaml'),
                        ('Design change', 'docs/architecture/factory/DESIGN-CHANGE-2026-11-12.md'),
                        ('Responsibility map', 'docs/architecture/factory/RESPONSIBILITIES.md')]:
        source = file(root / path)
        if source:
            backups.append(dict(title=title, **source))
    story_asset = write('assets/run4-full-story.txt', render_story(d4, plain=True))
    backups.append(dict(title='Run 4 full story', asset=story_asset, task_id=run4))
    for name, records in [('run4', d4), ('run5', d5)]:
        asset = write(f'assets/{name}-records.json', dump(records))
        for section in sections:
            for source in section['sources']:
                if source.get('task_id') == records['tasks'][0]['task_id'] and not source.get('asset'):
                    source['asset'] = asset
    # Capture the same read-only invocations used by live, with no shell or models.
    for section in sections:
        try:
            section['recorded_output'] = run_view(section['command'], home)
        except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
            gaps.append(f'{section["id"]}: recorded command capture: {sanitize(str(exc))}')
            section['recorded_output'] = section['text']
    pack = dict(schema='factory.demo/1', title='A software factory that uses CCs', budget=sum(s['duration'] for s in sections),
                home=str(home), task_ids=[run4, run5], end_to_end=E2E, sections=sections,
                backups=backups, gaps=gaps, assets=assets)
    write('index.html', Path(__file__).with_name('demo.html').read_text())
    # A single editable JSON owns durations and presentation content.
    (out / 'sections.json').write_text(dump(pack) + '\n')
    return pack


class DemoState:
    def __init__(self, pack, clock=time.monotonic):
        self.pack, self.clock = pack, clock
        self.lock = threading.RLock()
        self.index, self.elapsed, self.section_elapsed = 0, 0.0, 0.0
        self.paused, self.last, self.live_result = False, clock(), None

    def tick(self):
        now = self.clock()
        delta, self.last = max(0, now - self.last), now
        if self.paused:
            return
        self.elapsed += delta
        self.section_elapsed += delta
        while self.section_elapsed >= self.pack['sections'][self.index]['duration']:
            duration = self.pack['sections'][self.index]['duration']
            if self.index == len(self.pack['sections']) - 1:
                self.section_elapsed = duration
                self.paused = True
                break
            self.section_elapsed -= duration
            self.index += 1
            self.live_result = None

    def get(self):
        with self.lock:
            self.tick()
            return dict(section=self.index + 1, total=len(self.pack['sections']),
                        title=self.pack['sections'][self.index]['title'], paused=self.paused,
                        elapsed=round(self.elapsed, 2), budget=self.pack['budget'],
                        section_elapsed=round(self.section_elapsed, 2), live=self.live_result)

    def control(self, action, number=None):
        with self.lock:
            self.tick()
            if action in {'next', 'prev', 'goto'}:
                index = self.index + (1 if action == 'next' else -1) if action != 'goto' else int(number)-1
                if not 0 <= index < len(self.pack['sections']):
                    raise ValueError('Section out of range')
                self.index, self.section_elapsed, self.live_result = index, 0.0, None
            elif action in {'pause', 'resume'}:
                self.paused = action == 'pause'
            elif action != 'status':
                raise ValueError('Unknown control')
            return self.get()

    def live(self):
        with self.lock:
            self.tick()
            index = self.index
            section = self.pack['sections'][index]
        try:
            output = run_view(section['command'], self.pack['home'])
            result = dict(label='LIVE', evidence_label=section['label'], output=output,
                          caption='Current read-only invocation; historical run evidence remains RECORDED.')
        except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
            result = dict(label='RECORDED FALLBACK', output=section['recorded_output'], error=sanitize(str(exc)))
        with self.lock:
            if self.index == index:
                self.live_result = result
        return result


def load_pack(pack):
    value = json.loads((Path(pack) / 'sections.json').read_text())
    if not value['sections'] or any(type(s['duration']) not in (int, float) or s['duration'] <= 0 for s in value['sections']):
        raise ValueError('Section durations must be positive')
    return value


def make_handler(pack, state):
    pack = Path(pack).expanduser().resolve()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, value, status=200, mime='application/json; charset=utf-8'):
            body = value if isinstance(value, bytes) else dump(value).encode()
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; font-src 'self'; connect-src 'self'; frame-src 'self'")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = unquote(urlsplit(self.path).path)
            if path == '/api/state':
                self.reply(state.get()); return
            if path == '/api/pack':
                self.reply(state.pack); return
            target = (pack / (path.lstrip('/') or 'index.html')).resolve()
            if not target.is_relative_to(pack) or not target.is_file():
                self.reply(dict(error='Not found'), 404); return
            mime = 'text/html; charset=utf-8' if target.suffix == '.html' else 'text/plain; charset=utf-8'
            if target.suffix == '.json':
                mime = 'application/json; charset=utf-8'
            self.reply(target.read_bytes(), mime=mime)

        def do_POST(self):
            try:
                # Local UI/control only; reject browser cross-origin mutations.
                if self.headers.get('Origin') not in (None, f'http://{self.headers.get("Host")}'):
                    raise ValueError('Cross-origin control rejected')
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 4096:
                    raise ValueError('Invalid control body')
                command = json.loads(self.rfile.read(size))
                if self.path != '/api/control':
                    self.reply(dict(error='Not found'), 404); return
                value = state.live() if command.get('action') == 'live' else state.control(command['action'], command.get('section'))
                self.reply(value)
            except (ValueError, KeyError, TypeError) as exc:
                self.reply(dict(error=str(exc)), 400)
    return Handler


def make_server(pack=DEFAULT_PACK, bind='127.0.0.1', port=PORT):
    state = DemoState(load_pack(pack))
    server = ThreadingHTTPServer((bind, port), make_handler(pack, state))
    server.demo_state = state
    return server


def control(action, number=None, port=PORT):
    request = Request(f'http://127.0.0.1:{port}/api/control', data=json.dumps(dict(action=action, section=number)).encode(),
                      headers={'Content-Type': 'application/json'}, method='POST')
    with urlopen(request, timeout=20) as response:
        return json.load(response)


def preflight(pack=DEFAULT_PACK, home=None, port=PORT, images=False):
    checks = []
    def check(name, operation):
        try:
            operation()
            checks.append((True, name))
        except Exception as exc:
            checks.append((False, name + ': ' + sanitize(str(exc))))
    def require(value, message):
        if not value:
            raise ValueError(message)
    directory, home = Path(pack).expanduser(), home_path(home)
    check('pack built', lambda: require((directory/'index.html').is_file() and (directory/'sections.json').is_file(), 'run demo build'))
    try:
        data = load_pack(directory)
    except (OSError, ValueError, KeyError):
        data = {}
    def assets_present():
        require(data, 'pack unavailable')
        for name, digest in data['assets'].items():
            require(hashlib.sha256((directory/name).read_bytes()).hexdigest() == digest, name)
        require(not data['gaps'], 'missing evidence: ' + ', '.join(data['gaps']))
    check('assets and evidence present', assets_present)
    def free():
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', port))
    check(f'server port {port} free', free)
    check('store readable', lambda: require((home/'factory.sqlite').is_file() and os.access(home/'factory.sqlite', os.R_OK), 'store unavailable'))
    for task in data.get('task_ids', [RUN4, RUN5]):
        check('task exists ' + task, lambda task=task: load_source(task, home))
    check('real entrypoint command available', lambda: run_view(['capsules', '--plain'], home))
    check('jiuwenswarm executable available', lambda: require(shutil.which('jiuwenswarm'), 'add the runtime venv bin to PATH'))
    if images:
        ids = sorted({s['image_id'] for section in data.get('sections', []) for s in section['sources'] if s.get('image_id')})
        for image in ids:
            def inspect(image=image):
                proc = subprocess.run(['sg', 'docker', '-c', 'docker image inspect ' + shlex.quote(image)],
                                      stdin=subprocess.DEVNULL, capture_output=True, timeout=10)
                require(proc.returncode == 0, 'not available locally')
            check('local image ' + image, inspect)
    else:
        print('PASS local image inspection skipped (optional; enable --images)')
    for ok, message in checks:
        print(('PASS ' if ok else 'FAIL ') + message)
    return all(ok for ok, _ in checks)


def add_parser(sub):
    parser = sub.add_parser('demo', help=__doc__)
    actions = parser.add_subparsers(dest='demo_command', required=True)
    for action in ('preflight', 'build', 'serve', 'next', 'prev', 'pause', 'resume', 'goto', 'status', 'live', 'video'):
        p = actions.add_parser(action)
        p.add_argument('--pack', '--out', dest='pack', type=Path, default=DEFAULT_PACK)
        p.add_argument('--home', default=argparse.SUPPRESS)
        p.add_argument('--port', type=int, default=PORT)
        if action == 'goto':
            p.add_argument('section', type=int)
        if action == 'preflight':
            p.add_argument('--images', action='store_true')
        if action == 'build':
            p.add_argument('--siminfeng', type=Path)
        if action == 'serve':
            p.add_argument('--no-open', action='store_true')
        if action == 'video':
            p.add_argument('--video-out', type=Path, default=Path.home() / '.jiuwenswarm-factory/demo-video')
            p.add_argument('--chrome', default=shutil.which('google-chrome') or shutil.which('chromium') or 'google-chrome')
            p.add_argument('--ffmpeg')
            p.add_argument('--siminfeng-root', type=Path, default=Path.home() / 'projects/siminfeng')


def main(args):
    action = args.demo_command
    if action == 'video':
        from .demo_video import render, find_ffmpeg
        video, seconds = render(args.video_out, args.pack, args.siminfeng_root, args.chrome, find_ffmpeg(args.ffmpeg))
        print(f'Video: {video} ({seconds} s); scenes and frames in {args.video_out}; review list in {args.video_out}/REVIEW.md')
        return
    if action == 'build':
        data = build(args.pack, args.home, siminfeng=args.siminfeng)
        print(f'Pack: {args.pack} ({len(data["sections"])} sections, {sum(s["duration"] for s in data["sections"])} seconds)')
        for gap in data['gaps']:
            print('GAP ' + gap)
        return
    if action == 'preflight':
        if not preflight(args.pack, args.home, args.port, args.images):
            raise SystemExit(1)
        return
    if action == 'serve':
        with make_server(args.pack, port=args.port) as server:
            url = f'http://127.0.0.1:{server.server_port}'
            print(url, flush=True)
            if not args.no_open:
                try:
                    subprocess.Popen(['xdg-open', url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except OSError:
                    pass
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
        return
    print(dump(control(action, getattr(args, 'section', None), args.port)))
