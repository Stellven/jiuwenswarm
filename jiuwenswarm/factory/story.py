"""Read-only factory evidence views, shared by live stores and exported bundles."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys
import shutil
import tempfile
import textwrap
import time

from .export import snapshot

TERMINAL = {'accept', 'reject', 'report_inconclusive', 'partial'}
ACTIVE = {'queued', 'running', 'cancel_requested', 'unknown'}


def wrap(value, indent=''):
    return textwrap.wrap(' '.join(str(value).splitlines()), width=100, initial_indent=indent,
                         subsequent_indent=indent, break_long_words=True, break_on_hyphens=False) or [indent]


def paint(line, plain=False):
    if plain or not sys.stdout.isatty() or 'NO_COLOR' in os.environ:
        return line
    color = '31' if '✗' in line else '32' if '✓' in line else '2'
    return f'\033[{color}m{line}\033[0m'


def short(value):
    return str(value or '?').removeprefix('sha256:').removeprefix('factory-')[:8]


def duration(seconds):
    seconds = max(0, int(seconds))
    return f'{seconds // 60:02d}:{seconds % 60:02d}'


def load_source(source, home=None):
    path = Path(source).expanduser()
    bundle = path.is_dir()
    home = Path(home or os.environ.get('FACTORY_HOME', '~/.jiuwenswarm-factory')).expanduser().resolve()
    if bundle:
        data = {p.stem: json.loads(p.read_text()) for p in sorted((path / 'records').glob('*.json'))}
        if not data.get('tasks'):
            raise ValueError('Bundle has no task records')
    else:
        # SQLite may create -shm even with mode=ro on a WAL database. Read a
        # stable copy so viewing evidence never creates files in factory home.
        for retry in range(5):
            paths = [home / 'factory.sqlite', home / 'factory.sqlite-wal']
            def stamps():
                return [(p.stat().st_size, p.stat().st_mtime_ns) if p.exists() else None for p in paths]
            before = stamps()
            with tempfile.TemporaryDirectory(prefix='factory-view-') as temporary:
                for p in paths:
                    if p.exists():
                        shutil.copyfile(p, Path(temporary) / p.name)
                if before != stamps():
                    continue
                data = snapshot(Path(temporary), source)
                break
        else:
            raise ValueError('Factory evidence changed during read; retry the view')
    task = data['tasks'][0]
    transcript = path / 'session.jsonl' if bundle else home / 'sessions' / (task['task_id'] + '.jsonl')
    turns, started, finished = 0, None, None
    turn_ends = []
    if transcript.is_file():
        for line in transcript.read_text().splitlines():
            event = json.loads(line)
            turns = max(turns, event.get('turn', 0))
            if event.get('event') == 'turn.start':
                try:
                    remaining = json.loads(event['query'])['remaining_budget']['wall_clock_s']
                    started = event['t'] - (task['budget']['wall_clock_s'] - remaining)
                except (KeyError, TypeError, ValueError):
                    pass
            if event.get('event') == 'turn.end':
                finished = event['t']
                turn_ends.append(finished)
    contract_id = task.get('contract_id')
    if contract_id:
        if bundle:
            contracts = [json.loads(p.read_text()) for p in (path / 'contracts').glob('*.json')]
            data['_contract'] = next((c for c in contracts if c.get('contract_id') == contract_id), {})
        else:
            from .contract import load
            try:
                data['_contract'] = dict(load(contract_id))
            except (ValueError, OSError, AttributeError):
                data['_contract'] = {}
    latest = max(data.get('decisions', []), key=lambda d: d['rev'], default={})
    outcome = latest.get('action', {}).get('type')
    data['_meta'] = dict(outcome=outcome if outcome in TERMINAL else None,
                         budget_used=dict(turns=turns, wall_clock_s=(finished - started)
                         if finished is not None and started is not None else 0))
    state = dict(turns=0, started=None, outcome=None)
    if not bundle:
        state_path = home / 'sessions' / (task['task_id'] + '.state.json')
        if state_path.is_file():
            state = json.loads(state_path.read_text())
            data['_meta'] = dict(outcome=state.get('outcome'), budget_used=dict(
                turns=state.get('turns', 0), wall_clock_s=max(0, (state.get('finished') or time.time())
                - state['started']) if state.get('started') is not None else 0))
    data['_meta']['controller_state'] = state
    data['_meta']['turn_ends'] = turn_ends
    return data


def flatten(value):
    result = {}
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, dict):
                result.update(flatten(item))
            elif key not in {'type', 'next_bounded_operation'}:
                result[key] = item
    return result


def evaluation_summary(record):
    inputs = record.get('inputs', {})
    if 'ab_result' in inputs:
        ab = inputs['ab_result']
        return (f"{record.get('contract_id')} · {record.get('correctness')} · "
                f"{record.get('execution_outcome')} · gate {ab.get('gate')} · "
                f"ratio {ab.get('ratio')} · output {ab.get('output_class')}")
    run = inputs.get('run', inputs)
    details = run.get('details', inputs.get('details', {}))
    checks = details.get('engagement_checks', {})
    contract = record.get('contract', {})
    contract = contract.get('snapshot', contract)
    candidate = run.get('stdout_sha256', '?')
    reference = (contract.get('reference') or {}).get('stdout_sha256', '?')
    relation = '==' if candidate == reference and candidate != '?' else 'vs'
    return (f"{record.get('contract_id', '?')} · {record.get('correctness', '?')} · "
            f"{record.get('execution_outcome', '?')} · {record.get('evidence_completeness', '?')} · "
            f"stdout {short(candidate)} {relation} reference {short(reference)}"
            + (f" · engagement {sum(v is True for v in checks.values())}/{len(checks)}" if checks else ''))


def build_events(data):
    events = []

    def add(created, key, kind, summary, mark='·', rev=None):
        events.append(dict(created=created or 0, id=key, kind=kind, summary=summary, mark=mark, rev=rev))

    previous = flatten(data['tasks'][0].get('initial_run_config', {}))
    previous_action = {}
    # Observed requested config is useful even when decisions use prose actions.
    configs = sorted([(r.get('created', 0), flatten(r.get('values', {}).get('requested', {})))
                      for r in data.get('observations', []) if r.get('values', {}).get('requested')])
    decisions = sorted(data.get('decisions', []), key=lambda d: d['rev'])
    for i, d in enumerate(decisions):
        action = d.get('action', {})
        current = flatten(action)
        prose = str(action.get('next_bounded_operation', ''))
        for key in previous:
            match = re.search(re.escape(key) + r'\s+(?:changed?\s+to|[=:]|from\s+\S+\s+to)\s*[\"\']?([\w.-]+)', prose)
            if match:
                current[key] = match.group(1).rstrip('.')
        end = decisions[i + 1]['created'] if i + 1 < len(decisions) else float('inf')
        for at, config in configs:
            if d['created'] <= at < end:
                current.update(config)
        # Only run-config switches (ENV_STYLE names) count as a replan diff, not prose fields.
        changes = [f'{k} {previous[k]} → {v}' for k, v in current.items()
                   if k in previous and previous[k] != v and re.fullmatch(r'[A-Z][A-Z0-9_]*', k)]
        kind = action.get('type', 'decide')
        failure = next((e for e in d.get('evidence_ids', []) if any(
            o.get('obs_id') == e and o.get('error') for o in data.get('observations', []))), None)
        step = str(action.get('next_operation') or action.get('next_bounded_operation') or '')
        step = re.split(r'(?<=[.;])\s', step, maxsplit=1)[0].rstrip('.;')
        summary = '; '.join(changes) or step or d.get('reason_for_change', '').split(';')[0]
        if action.get('component') and kind not in {'keep_component', 'keep_dormant', 'revert_component'}:
            summary = f"{action['component']} · {summary}"
        if failure:
            summary += ' · because ' + short(failure)
        if kind in {'keep_component', 'keep_dormant', 'revert_component'}:
            changes = []
            ratio = action.get('ratio')
            summary = {'keep_component': f"keep {action.get('component')} · "
                                         f"{ratio:.2f}× · image {short(str(action.get('image')))}"
                                         if isinstance(ratio, (int, float)) else f"keep {action.get('component')}",
                       'keep_dormant': f"dormant {action.get('component')} · switch off · needed by "
                                       + ', '.join(action.get('needed_by') or []),
                       'revert_component': f"revert {action.get('component')} · {action.get('reason')}"}[kind]
        if kind in {'keep_component', 'revert_component'}:
            acceptance = decision_acceptance(data, d)
            summary += f" · acceptance {acceptance['type']} {acceptance['verdict']}"
        if kind in TERMINAL:
            changes = []
            summary = d.get('reason_for_change', '')
        add(d['created'], d['decision_id'], ('replan/' + kind) if changes or failure else kind,
            summary, rev=d['rev'])
        previous.update(current)
    for r in data.get('observations', []):
        v = r.get('values', {})
        error = r.get('error') or {}
        failed = bool(error.get('code') or v.get('code') or v.get('state') == 'failed')
        kind, summary = r.get('kind', 'observation'), ''
        mark = '✗' if failed else '·'
        if failed:
            if kind.startswith('inspector.'):
                kind = 'inspect'
            summary = f"{error.get('code', v.get('code', 'FAILED'))} {error.get('message', v.get('message', ''))}"
        elif kind == 'ab_result':
            mark = '✓' if v.get('gate') == 'improved' else '·'
            summary = (f"{v.get('component')} · acceptance {v.get('acceptance', {}).get('type')} {v.get('acceptance', {}).get('verdict')} · gate {v.get('gate')} · ratio {v.get('ratio')} · "
                       f"A/A {v.get('aa_gap')} · output {v.get('output_class')} · ms/token {v.get('per_arm_ms')}")
        elif kind == 'build_result':
            kind, mark = 'build', '✓' if v.get('status') == 'success' else '✗'
            summary = (f"{short(r.get('host_run', {}).get('attempt_id'))} · "
                       f"{round(v['build_wall_seconds']) if isinstance(v.get('build_wall_seconds'), (int, float)) else '?'} s → image {short(v.get('image_id'))}")
        elif kind == 'inspector.inspect':
            source = v.get('source', {})
            kind, mark = 'integrate', '✓' if source.get('commit') else '·'
            patches = ', '.join(p.get('name', '?') for p in source.get('applied_patches', []))
            summary = f"commit {short(source.get('commit'))} · {patches}"
        elif kind == 'lab_result':
            kind, mark = 'lab', '✓' if v.get('execution_outcome') == 'ok' else '✗'
            details = v.get('details', {})
            contract = data.get('_contract', {})
            argv = contract.get('workload', {}).get('argv', [])
            tokens = argv[argv.index('-n') + 1] if '-n' in argv and argv.index('-n') + 1 < len(argv) else '?'
            speed = details.get('eval_ms_per_token', '?')
            summary = (f"{tokens} tokens · {speed} ms/token · "
                       f"{v.get('execution_outcome', '?')} · {details.get('worker', {}).get('cleanup', '?')}")
            nsys = details.get('nsys') or {}
            if details.get('traced'):
                kernels = (nsys.get('kernels') or {}).get('total_ms')
                top = ((nsys.get('os_runtime') or {}).get('top') or [{}])[0].get('name')
                summary = (f"{tokens} tokens · TRACED (timing perturbed) · GPU kernels {kernels} ms"
                           f" · top OS call {top} · {v.get('execution_outcome', '?')}")
        elif kind.startswith('inspector.'):
            kind, mark = 'inspect', '✓'
            effective = v.get('effective', {})
            from .effective_config import ENV_KEYS, DEFAULTS
            requested = {ENV_KEYS.get(k, k) for k in v.get('requested', {})}
            priority = ['k', 'pregate', 'fill']
            keys = priority + [k for k in effective if k not in priority]
            settings = [f'{k}={effective[k]}' for k in keys if k in effective
                        and (k in requested or str(effective[k]) != DEFAULTS.get(k))]
            shown = []
            for setting in settings:
                if len('effective ' + ' · '.join([*shown, setting]) + ' · … · matches request') > 74:
                    shown.append('…')
                    break
                shown.append(setting)
            summary = 'effective ' + ' · '.join(shown) + ' · matches request' if effective else r['kind']
        else:
            summary = v.get('message', r.get('limitations', '') or kind)
        add(r.get('created'), r['obs_id'], kind, summary, mark)
    for a in data.get('attempts', []):
        history = a.get('history', []) or [dict(state=a.get('state'), created=a.get('started'))]
        for index, h in enumerate(history):
            state = h.get('state', 'unknown')
            mark = '✓' if state == 'succeeded' else '✗' if state in {'failed', 'cancelled'} else '·'
            survived = state == 'succeeded' and any(
                (history[0].get('created') or 0) < end < (h.get('created') or 0)
                for end in data.get('_meta', {}).get('turn_ends', []))
            suffix = ' · survived turn end' if survived else ''
            add(h.get('created'), a['attempt_id'] + ':' + str(index), a.get('kind', 'job'),
                f"{short(a['attempt_id'])} {state} · durable job{suffix}", mark)
        admission = a.get('request', {}).get('admission')
        if admission:
            add(history[0].get('created'), a['attempt_id'] + ':admission', 'admit',
                f"{short(str(admission.get('admission_id', '?')).removeprefix('admission:'))} · image {short(admission.get('image', {}).get('id'))}"
                f" · target {admission.get('target_profile', '?')}", '✓')
    for r in data.get('uploads', []):
        add(r.get('created'), r['upload_id'], 'upload', r.get('ack_state', '?'),
            '✓' if r.get('ack_state') == 'durable' else '·')
    for r in data.get('evaluations', []):
        add(r.get('created'), r['eval_id'], 'contract', evaluation_summary(r),
            '✓' if r.get('correctness') == 'pass' else '✗')
    for kind, records in data.items():
        if kind in {'tasks', 'decisions', 'observations', 'attempts', 'uploads', 'evaluations', 'artifacts', 'events', '_meta', '_contract'}:
            continue
        if isinstance(records, list):
            for i, r in enumerate(records):
                add(r.get('created'), f'{kind}:{i}', kind, r.get('message', 'record'))
    for r in data.get('events', []):
        if r.get('type', r.get('kind')) not in {'task', 'decision', 'observation', 'attempt', 'upload', 'evaluation', 'artifact'}:
            add(r.get('created'), 'event:' + str(r.get('cursor')), r.get('kind', 'unknown'), 'record')
    return sorted(events, key=lambda e: (e['created'], e['id']))


def event_lines(event, created):
    badge = f"rev {event['rev']}" if event['rev'] is not None else event['mark']
    prefix = f" {duration(event['created'] - created)}  {badge:5} {event['kind']:10} "
    content = ' '.join(str(event['summary']).split())
    lines = textwrap.wrap(prefix + content, width=100, subsequent_indent=' ' * 25,
                          break_long_words=False, break_on_hyphens=False)
    if event['kind'] in TERMINAL and len(lines) > 3:
        lines = lines[:3]
        lines[-1] = textwrap.shorten(lines[-1].strip(), width=74, placeholder='…') + '…'
        lines[-1] = ' ' * 25 + lines[-1]
    return lines


def header(data):
    task, meta = data['tasks'][0], data['_meta']
    contract = data.get('_contract') or next((a.get('request', {}).get('contract') for a in data.get('attempts', [])
                     if a.get('request', {}).get('contract')), {})
    if not contract and data.get('evaluations'):
        contract = data['evaluations'][-1].get('contract', {})
        contract = contract.get('snapshot', contract)
    name = Path(contract.get('model', {}).get('path', 'model unknown')).stem
    name = re.sub(r'-(?:UD-)?(?:I?Q\d.*|F(?:16|32)|BF16)$', '', name, flags=re.I)
    used = meta['budget_used']
    return wrap(f" factory · {short(task['task_id'])} · {name} on {task.get('target', '?')} · "
                f"{(meta['outcome'] or 'in progress').upper()} · {used['turns']} turns · "
                f"{duration(round(used['wall_clock_s']))}") + [' ' + '─' * 98]


def chain_links(data):
    """The evidence chain component → … → evaluation as (link, mark) pairs; mark is ✓, ✗ or ·."""
    task = data['tasks'][0]
    attempts = data.get('attempts', [])
    builds = [a for a in attempts if a.get('kind') == 'build']
    labs = [a for a in attempts if a.get('kind') == 'lab']
    values = [o.get('values', {}) for o in data.get('observations', [])]
    def jobmark(jobs):
        return '✓' if any(a.get('state') == 'succeeded' for a in jobs) else '✗' if any(a.get('state') in {'failed', 'cancelled'} for a in jobs) else '·'
    links = [('component', '✓' if task.get('component_cc') else '·'),
             ('commit', '✓' if any(v.get('source', {}).get('commit') for v in values) or any(a.get('request', {}).get('source', {}).get('commit') for a in builds) else '·'),
             ('build', jobmark(builds)),
             ('image', '✓' if any(v.get('image_id') for v in values) else '·'),
             ('admission', '✓' if any(a.get('request', {}).get('admission') for a in labs) else '·'),
             ('lab', jobmark(labs)),
             ('evaluation', '✓' if any(e.get('correctness') == 'pass' for e in data.get('evaluations', [])) else '✗' if data.get('evaluations') else '·')]
    return links


def footer(data):
    stack = []
    if any(d.get('action', {}).get('type') in {'keep_component', 'keep_dormant', 'revert_component'}
           for d in data.get('decisions', [])):
        stack = wrap('engine stack: ' + ' → '.join(decision_stack(data)))
    links = chain_links(data)
    artifacts = data.get('artifacts', [])
    count = sum(len(v) for k, v in data.items() if isinstance(v, list) and k != 'events')
    return stack + wrap('chain: ' + ' → '.join(f'{name} {mark}' for name, mark in links)) + wrap(
        f"evidence: {count} records · {len(artifacts)} artifacts · {sum(a.get('size', 0) for a in artifacts)} bytes")


def decision_acceptance(data, decision):
    refs = decision.get('evidence_ids', [])
    for observation in data.get('observations', []):
        if observation.get('obs_id') in refs and observation.get('kind') == 'ab_result':
            result = observation.get('values', {}).get('acceptance')
            if result:
                return result
    for evaluation in data.get('evaluations', []):
        if evaluation.get('eval_id') in refs:
            result = evaluation.get('inputs', {}).get('acceptance')
            if result:
                return result
    from .components import load
    try:
        kind = load(decision['action']['component'])['acceptance']['type']
    except (ValueError, KeyError):
        kind = 'unknown'
    return dict(type=kind, verdict='not_measured')


def decision_stack(data):
    stack = [data['tasks'][0].get('source', {}).get('pre_integration_commit') or 'bare']
    for d in sorted(data.get('decisions', []), key=lambda d: d['rev']):
        action = d.get('action', {})
        name = action.get('component')
        if action.get('type') == 'keep_component' and name not in stack:
            stack.append(name)
        elif action.get('type') == 'keep_dormant' and name not in stack:
            stack.append(name + ' (off)')
        elif action.get('type') == 'revert_component' and name in stack[1:]:
            stack.remove(name)
    return stack


def render_story(data, plain=False):
    lines = header(data)
    for event in build_events(data):
        lines.extend(event_lines(event, data['tasks'][0]['created']))
    from .taskgraph import from_records, render_text
    graph = from_records(data)
    if graph['rev']:
        lines.extend(render_text(graph).splitlines())
    return '\n'.join(paint(line, plain) for line in lines + footer(data))


def show_story(source, home=None, plain=False, as_json=False, follow=False):
    if follow and Path(source).expanduser().is_dir():
        raise ValueError('--follow requires a live task id')
    if follow and as_json:
        raise ValueError('--follow and --json cannot be combined')
    seen = set()
    first = True
    while True:
        data = load_source(source, home)
        events = build_events(data)
        if as_json:
            print(json.dumps(events, indent=2, ensure_ascii=False))
            return
        lines = header(data) if first else []
        for event in events:
            if event['id'] not in seen:
                lines.extend(event_lines(event, data['tasks'][0]['created']))
                seen.add(event['id'])
        if not follow or data['_meta']['outcome']:
            lines.extend(footer(data))
        for line in lines:
            print(paint(line, plain), flush=True)
        if not follow or data['_meta']['outcome']:
            return
        first = False
        time.sleep(2)
