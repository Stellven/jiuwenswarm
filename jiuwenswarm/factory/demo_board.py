"""Factory demo board: a fixed, read-only view of one factory task graph run, in replay and live mode.

The board reads the same records as the monitor (``factory.sqlite`` through ``story.load_source``, the
telemetry log, the operator inbox) and turns them into one ordered list of plain-language events. Each
event carries the state of every graph node after it, so the page can step through the run event by
event (replay) or follow the newest event (live). Nothing here writes to the factory home.

    python -m jiuwenswarm.factory.demo_board --home <factory home> --task <task id> [--port 5175]

Records used (all written by the factory, none by this module):

* ``taskgraph_patch``: graph revisions (seed plan, scheduler finalize, operator hold/release/reopen/retire/revise,
  agent decisions). Node states come from replaying them (``taskgraph.replay``).
* ``node_contract_final`` / ``node_contract_refusal``: the scheduler's admitted final node contracts (with
  their diff from the preliminary contract) and the host's refusals.
* ``node_check``: capsule verifier and independent reviewer results per node output.
* attempts + ``capped_run``: durable jobs and what the capped runner recorded (recipe, memory cap, time,
  bytes written, error).
* ``operator_pause``, ``operator_halt``, ``attempt_excused``, ``operator_input``, the operator inbox: operator actions.
* telemetry ``cc.call`` and ``scheduler.turn``: capsule calls and scheduler agent turns.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import statistics

from .node_finalize import digest
from .story import replay_duration, replay_origin

DEFAULT_PORT = 5175

STATE_LABELS = {
    'waiting': 'Waiting for earlier steps',
    'ready': 'Ready: scheduler to finalize',
    'held': 'Paused at step checkpoint',
    'operator_hold': 'Held by the operator',
    'working': 'Agent working',
    'running': 'Running a capped job',
    'checking': 'Being checked',
    'fixing': 'Check failed: agent fixing',
    'halted': 'Halted for the operator',
    'done': 'Done: gate passed',
    'failed': 'Failed',
    'retired': 'Retired by the operator',
    'removed': 'Removed by a contract revision',
    'planned': 'In the new contract revision, not yet in the graph',
    'superseded': 'Replaced by another step',
}
ACTORS = {'planner': 'Planner', 'scheduler': 'Scheduler agent', 'agent': 'Worker agent', 'host': 'Factory host',
          'runner': 'Capped runner', 'checker': 'Checks', 'operator': 'Operator'}
OPERATOR_KINDS = {'hold', 'release', 'reopen', 'retire', 'excuse', 'note', 'input', 'halt', 'step_hold'}
RECIPE_WORDS = {'convert': 'conversion', 'quantize': 'quantization', 'serve': 'server load', 'build': 'engine build',
                'manifest': 'pack digest', 'accuracy': 'accuracy run'}
STEP_PREFIX = 'step checkpoint'
NOTE_ECHO = re.compile(r'^Operator (release|hold|reopen|retire) on plan node ')
NEVER_WEAKER = re.compile(r'may only (go down|go up|narrow)|is above|is below|weaker|must stay|was removed|is missing|'
                          r'exceeds|may not|not allowed|outside', re.I)


# -- formatting ----------------------------------------------------------------------------------------------

def human_bytes(n):
    """Decimal units, as the run's own reports use them: 528.9 GB, 10.8 GB, 6.3 KB."""
    if not isinstance(n, (int, float)) or isinstance(n, bool):
        return None
    for unit, size in (('TB', 1e12), ('GB', 1e9), ('MB', 1e6), ('KB', 1e3)):
        if abs(n) >= size:
            value = n / size
            return f'{value:.1f} {unit}' if value < 100 or unit == 'GB' else f'{value:.0f} {unit}'
    return f'{int(n)} B'


def human_seconds(s):
    """38 s, 18 min, 2 h 16 min."""
    if not isinstance(s, (int, float)) or isinstance(s, bool):
        return None
    s = max(0, float(s))
    if s < 90:
        return f'{s:.0f} s'
    minutes = round(s / 60)
    if minutes < 90:
        return f'{minutes} min'
    return f'{minutes // 60} h {minutes % 60:02d} min'


def short(value, n=8):
    return str(value or '?').removeprefix('sha256:')[:n]


def _clip(text, n=400):
    text = ' '.join(str(text or '').split())
    return text if len(text) <= n else text[:n - 1].rstrip() + '…'


def _scrub_paths(value):
    """Shared material carries no account names: /home/<user>/x -> ~/x."""
    if isinstance(value, str):
        return re.sub(r'/home/[^/\s"\']+/', '~/', value)
    if isinstance(value, list):
        return [_scrub_paths(v) for v in value]
    if isinstance(value, dict):
        return {k: _scrub_paths(v) for k, v in value.items()}
    return value


# -- preliminary contracts -----------------------------------------------------------------------------------

def _list_key(items):
    if items and all(isinstance(x, dict) for x in items):
        return next((k for k in ('output', 'name', 'id') if all(k in x for x in items)), None)
    return None


def _walk(container, parts):
    """(parent, key) of a node_finalize.diff path inside container; keys may contain dots."""
    parent, rest = container, list(parts)
    while True:
        if isinstance(parent, dict):
            for cut in range(len(rest), 0, -1):
                key = '.'.join(rest[:cut])
                if key in parent or cut == 1:
                    if cut == len(rest):
                        return parent, key
                    parent, rest = parent.get(key), rest[cut:]
                    break
        elif isinstance(parent, list):
            key_name = _list_key(parent)
            for cut in range(len(rest), 0, -1):
                key = '.'.join(rest[:cut])
                match = next((x for x in parent if key_name and x.get(key_name) == key), None)
                if match is not None or cut == 1:
                    if cut == len(rest):
                        return parent, key
                    if match is None:
                        raise KeyError('.'.join(parts))
                    parent, rest = match, rest[cut:]
                    break
        else:
            raise KeyError('.'.join(parts))


def rebuild_preliminary(final, changes):
    """The preliminary node contract from an admitted final and its recorded diff (before values)."""
    prelim = copy.deepcopy(final)
    for change in sorted(changes or [], key=lambda c: -len(str(c.get('path', '')))):
        parent, key = _walk(prelim, str(change['path']).split('.'))
        before = copy.deepcopy(change.get('before'))
        if isinstance(parent, dict):
            if before is None:
                parent.pop(key, None)
            else:
                parent[key] = before
        else:
            key_name = _list_key(parent)
            index = next((i for i, x in enumerate(parent) if x.get(key_name) == key), None)
            if before is None:
                if index is not None:
                    parent.pop(index)
            elif index is None:
                parent.append(before)
            else:
                parent[index] = before
    return prelim


def contract_documents(paths):
    """[(label, node-contracts document)] from contract JSON files (format 2 with the node-contracts extension)."""
    docs = []
    for path in paths:
        path = Path(path)
        files = sorted(path.glob('*.json')) if path.is_dir() else [path] if path.is_file() else []
        for item in files:
            try:
                value = json.loads(item.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                continue
            document = ((value or {}).get('extensions') or {}).get('factory.node-contracts')
            if isinstance(document, dict) and isinstance(document.get('nodes'), list):
                docs.append((item.name, document))
    return docs


def _as_run_document(docs, finals):
    """The contract document whose preliminary nodes match the most recorded finals (ties: the first listed)."""
    best, score = None, -1
    for label, document in docs:
        digests = {n.get('node_id'): digest(n) for n in document['nodes']}
        hits = sum(digests.get(f.get('node_contract')) == f.get('preliminary_digest') for f in finals)
        if hits > score:
            best, score = (label, document), hits
    return best


# -- contract view -------------------------------------------------------------------------------------------

def _value_at(doc, path):
    try:
        parent, key = _walk(doc, path.split('.'))
    except (KeyError, AttributeError, TypeError):
        return None
    if isinstance(parent, dict):
        return parent.get(key)
    key_name = _list_key(parent)
    return next((x for x in parent if x.get(key_name) == key), None)


def contract_view(contract):
    """What a non-specialist needs from a node contract: goal, outputs and criteria, checks, limits, capsules."""
    if not isinstance(contract, dict):
        return None
    work = contract.get('work') or {}
    verifiers = {v.get('output'): v for v in contract.get('verifiers') or []}
    outputs = []
    for output in contract.get('outputs') or []:
        v = verifiers.get(output.get('name')) or {}
        outputs.append(dict(name=output.get('name'), kind=output.get('kind'), criteria=list(output.get('criteria') or []),
                            verifier=v.get('verifier'), stage=v.get('stage'), review=v.get('review'),
                            verifier_inputs=v.get('inputs') or {}))
    return dict(node_id=contract.get('node_id'), stage=contract.get('stage'), kind=contract.get('kind'),
                objective=contract.get('objective'), predecessors=contract.get('predecessors') or [],
                hands_to=contract.get('hands_to'), outputs=outputs, node_limits=contract.get('node_limits') or {},
                bound_ccs=work.get('bound_ccs'), eligible_ccs=work.get('eligible_ccs') or work.get('helpful_ccs') or [],
                capability=work.get('capability'), slots=contract.get('slots') or [], bounds=contract.get('bounds') or {},
                briefing=contract.get('briefing'))


def _change_view(change):
    before, after = change.get('before'), change.get('after')
    view = dict(path=change.get('path'), before=before, after=after)
    if isinstance(before, list) and isinstance(after, list) and all(isinstance(x, str) for x in before + after):
        view.update(added=[x for x in after if x not in before], removed=[x for x in before if x not in after])
    return view


def slot_rationale(rationale, slot_id):
    """The scheduler's reasons for one slot: rationale[slot] when it is per slot, else the sentences naming the slot."""
    if isinstance(rationale, dict):
        return _clip(rationale.get(slot_id), 700) or None
    if not isinstance(rationale, str) or not slot_id:
        return None
    names = {slot_id, slot_id.replace('_', ' ')}
    sentences = re.split(r'(?<=[.;])\s+(?=[A-Z`(])', rationale)
    found = [s for s in sentences if any(re.search(r'\b' + re.escape(n) + r'\b', s, re.I) for n in names)]
    return _clip(' '.join(found), 700) or None


def final_view(record, prelim):
    final = record.get('final') or {}
    slots = []
    for slot in (prelim or {}).get('slots') or []:
        at = slot.get('at', '')
        before, after = _value_at(prelim, at), _value_at(final, at)
        filled = after
        if isinstance(before, list) and isinstance(after, list):
            filled = [x for x in after if x not in before] or after
        slots.append(dict(id=slot.get('id'), at=at, kind=slot.get('kind'), hint=slot.get('from'), value=filled,
                          why=slot_rationale(record.get('rationale'), slot.get('id'))))
    skip = {'slots', 'stage', 'bounds', 'work.bound_ccs'}
    changes = [_change_view(c) for c in record.get('diff') or [] if c.get('path') not in skip]
    bound = (final.get('work') or {}).get('bound_ccs') or []
    versions = record.get('cc_versions') or {}
    return dict(t=record.get('created'), digest=record.get('digest'), by=record.get('by'),
                bound_ccs=[dict(cc=cc, version=versions.get(cc)) for cc in bound], slots=slots, changes=changes,
                rationale=_clip(record.get('rationale'), 1600), contract=contract_view(final),
                dropped_bounds=(prelim or {}).get('bounds') or {})


def refusal_kind(problems):
    text = ' '.join(problems or [])
    if 'identical final' in text:
        return 'repeat rule: something must change before a retry'
    if NEVER_WEAKER.search(text):
        return 'never weaker: a final contract may only be stricter'
    return 'contract problem'


# -- checks and runs -----------------------------------------------------------------------------------------

def check_view(record):
    v = record['values']
    verifier, review = v.get('verifier') or {}, v.get('review') or {}
    out = dict(t=record.get('created'), id=record.get('obs_id'), output=v.get('output'), kind=v.get('kind'),
               state=v.get('state'), passed=bool(v.get('passed')), reason=_clip(v.get('reason'), 500),
               seconds=(v.get('seconds') or {}).get('total'), reused=bool(v.get('reused_from')))
    if verifier:
        checks = verifier.get('checks') or []
        failed = [c.get('name') for c in checks if c.get('status') not in ('pass', 'skip', 'skipped', None)]
        out['verifier'] = dict(cc=verifier.get('cc'), capability=verifier.get('capability'), passed=verifier.get('passed'),
                               stage=verifier.get('stage_reached'), checks=len(checks), failed=failed)
    elif v.get('kind') in {'source_bundle', 'image', 'lab_request'} and v.get('state') == 'finished':
        out['verifier'] = dict(cc='factory host', capability=v.get('kind') + ' record check', passed=bool(v.get('passed')),
                               stage='host check', checks=1, failed=[] if v.get('passed') else [v.get('kind')])
    if review and (review.get('verdict') or review.get('summary') or review.get('reason')):
        findings = review.get('findings') or []
        blockers = [_clip(f.get('problem'), 300) for f in findings if f.get('severity') == 'blocker']
        advisory = bool(review.get('advisory')) or (v.get('entry') or {}).get('review') == 'advisory'
        out['review'] = dict(verdict=review.get('verdict'), summary=_clip(review.get('summary') or review.get('reason'), 600),
                             blockers=blockers,
                             findings=len(findings), advisory=advisory,
                             notes=[_clip(f.get('problem'), 300) for f in findings if f.get('severity') != 'blocker'][:5])
    return out


def run_view(attempt, capped):
    """One durable job and its capped-run record (either may be missing)."""
    request = (attempt or {}).get('request') or (capped or {}).get('request') or {}
    result, error = (capped or {}).get('result') or {}, (capped or {}).get('error') or {}
    history = (attempt or {}).get('history') or []
    queued = next((h.get('created') for h in history if h.get('state') == 'queued'), None)
    started = next((h.get('created') for h in history if h.get('state') == 'running'), None) or (attempt or {}).get('started')
    ended = (attempt or {}).get('ended')
    seconds = (capped or {}).get('seconds')
    if capped and ended is None:
        ended = capped.get('_created')
    if started is None and ended is not None and isinstance(seconds, (int, float)):
        started = ended - seconds
    if seconds is None and started is not None and ended is not None:
        seconds = ended - started
    state = (attempt or {}).get('state') or ('succeeded' if (capped or {}).get('outcome') == 'ok' else 'failed')
    if capped and capped.get('outcome') not in (None, 'ok') and state == 'succeeded':
        state = 'failed'
    recipe = request.get('recipe') or (capped or {}).get('recipe')
    written = result.get('bytes') if recipe in {'convert', 'quantize', 'build'} else None
    source = (capped or {}).get('replayed_from') or request.get('replayed_from')
    origin = replay_origin(source)
    what = RECIPE_WORDS.get(recipe, recipe) or (attempt or {}).get('kind') or 'job'
    return dict(attempt_id=(attempt or {}).get('attempt_id') or (capped or {}).get('attempt_id'),
                node_id=request.get('node_id') or (capped or {}).get('node_id'), recipe=recipe,
                what=f'{what} replay verification' if origin else what, label=request.get('label') or request.get('name'),
                state=state, t_queued=queued, t_start=started, t_end=ended, seconds=seconds,
                memory_cap=(capped or {}).get('memory_cap'), peak_memory_bytes=(capped or {}).get('peak_memory_bytes'),
                min_available_bytes=(capped or {}).get('min_available_bytes'), bytes=None if origin else written,
                verified_bytes=written if origin and state == 'succeeded' else None,
                replayed_from=source, replay_source=origin,
                verification_duration=replay_duration(result.get('seconds', seconds)) if origin else None,
                bytes_read=result.get('bytes') if recipe == 'manifest' else None,
                probe=result.get('probe'), load_seconds=result.get('ready_s'), rows=result.get('rows'),
                commit=result.get('commit'), error=dict(code=error.get('code'), message=_clip(error.get('message'), 300)) if error else None,
                recorded=bool(capped))


# -- events --------------------------------------------------------------------------------------------------

def _graph_history(observations, task_id):
    return sorted([o['values'] for o in observations if o.get('kind') == 'taskgraph_patch'
                   and o.get('task_id', task_id) == task_id], key=lambda h: h['rev'])


NODE_DEFAULTS = dict(capability=None, inputs=[], depends_on=[], state='proposed', attempt_ids=[], evidence_ids=[], reason='')


def _apply_lenient(nodes, entry):
    """Apply one recorded graph patch the way taskgraph does, without validating it.

    A viewer must keep working on records written by newer factory code (an operator ``revise``, ops this
    module does not know yet): unknown operations are skipped and listed, never raised.
    """
    patch, origin, unknown = entry.get('patch') or {}, entry.get('origin'), []

    def restart(node, reason):
        node.update(state='proposed', reason=reason, evidence_ids=[])
        node.pop('final_contract', None)

    def descendants(key):
        out, frontier = [], [key]
        while frontier:
            parent = frontier.pop()
            for child, node in nodes.items():
                if parent in node.get('depends_on', []) and child not in out:
                    out.append(child)
                    frontier.append(child)
        return out

    for op, changes in patch.items():
        for change in changes if isinstance(changes, list) else []:
            key = change.get('node_id') if isinstance(change, dict) else None
            node = nodes.get(key)
            if op == 'add' and origin != 'operator':
                nodes[key] = copy.deepcopy(NODE_DEFAULTS) | copy.deepcopy(change)
            elif op == 'update' and node is not None:
                for field, value in change.items():
                    if field in {'attempt_ids', 'evidence_ids'}:
                        node[field] = list(dict.fromkeys(node.get(field, []) + list(value)))
                    elif field != 'node_id':
                        node[field] = value
            elif op in {'cancel', 'supersede'} and node is not None:
                node.update(state='cancelled' if op == 'cancel' else 'superseded', reason=change.get('reason', ''))
                if op == 'supersede':
                    node['superseded_by'] = change.get('by')
            elif op == 'finalize' and node is not None:
                node.update(final_contract=change.get('digest'), check=change.get('check'))
            elif op == 'hold' and node is not None:
                node['hold'] = change.get('reason', '')
            elif op == 'release' and node is not None:
                node.pop('hold', None)
            elif op == 'retire' and node is not None:
                node.update(state='cancelled', reason='retired by operator: ' + change.get('reason', ''))
                node.pop('hold', None)
                for other in nodes.values():
                    other['depends_on'] = [d for d in other.get('depends_on', []) if d != key]
            elif op == 'reopen' and node is not None:
                restart(node, 'reopened by operator: ' + change.get('reason', ''))
                for child in descendants(key):
                    if nodes[child]['state'] not in {'cancelled', 'superseded', 'proposed'}:
                        restart(nodes[child], f'upstream {key} reopened by operator')
            elif op == 'revise':
                action = change.get('action')
                if action == 'add' and isinstance(change.get('node'), dict):
                    nodes[key] = copy.deepcopy(NODE_DEFAULTS) | copy.deepcopy(change['node'])
                elif action == 'cancel' and node is not None:
                    node.update(state='cancelled', reason='retired by operator revise: ' + change.get('reason', ''))
                    node.pop('hold', None)
                elif action == 'update' and node is not None:
                    if 'depends_on' in change:
                        node['depends_on'] = list(change['depends_on'])
                    for field in ('title', 'kind', 'capability', 'check', 'resources'):
                        if field in change:
                            node[field] = change[field]
                    if change.get('unfinalize'):
                        node.pop('final_contract', None)
                    if change.get('state') == 'proposed':
                        node['state'] = 'proposed'
                else:
                    unknown.append(f'revise {action}')
            else:
                unknown.append(op)
    return unknown


def replay_graph(history):
    """{rev: {node_id: node}} for every recorded graph revision (rev 0 is the empty graph), and skipped ops."""
    graphs, nodes, skipped = {0: {}}, {}, {}
    for entry in sorted(history, key=lambda h: h['rev']):
        unknown = _apply_lenient(nodes, entry)
        if unknown:
            skipped[entry['rev']] = unknown
        graphs[entry['rev']] = copy.deepcopy(nodes)
    return graphs, skipped


def _clock_offset(observations):
    """Seconds to add to a record time for the run host's wall clock (from a host reading's local 'at')."""
    for o in observations:
        v = o.get('values') or {}
        if o.get('kind') == 'host_reading' and isinstance(v.get('at'), str) and o.get('created'):
            try:
                local = datetime.fromisoformat(v['at']).replace(tzinfo=timezone.utc).timestamp()
            except ValueError:
                continue
            return round((local - o['created']) / 900) * 900
    return 0


def build_replay(data, *, telemetry=(), notes=(), contracts=(), manifests=(), current=None, briefs=(), run_files=None):
    """The board document: task summary, nodes (static detail with times), events and per-event node states.

    data: a ``story.load_source`` result (or an equivalent Store dump). telemetry: factory.telemetry/1 records.
    notes: operator inbox notes. contracts: [(label, node-contracts document)]. manifests: [(name, pack manifest)].
    current: (label, task contract) the task runs against now (its latest revision); its node contracts that the
    graph lacks are shown as planned, graph nodes it no longer has as dropped. briefs: scheduler briefs read
    from the scheduler transcript (read_briefs). run_files: PAUSE.md / HALT.md / STEP.md text and controller state.
    Pure: reads nothing from disk.
    """
    task = data['tasks'][0]
    task_id = task['task_id']
    observations = [o for o in data.get('observations', []) if o.get('task_id', task_id) == task_id]
    by_kind = {}
    for o in sorted(observations, key=lambda o: (o.get('created') or 0, o.get('obs_id', ''))):
        by_kind.setdefault(o.get('kind'), []).append(o)
    history = _graph_history(observations, task_id)
    graphs, skipped_ops = replay_graph(history)
    finals = [o['values'] for o in by_kind.get('node_contract_final', [])]
    as_run = _as_run_document(contracts, finals) if contracts else None
    current_label, current_contract = current or (None, None)
    current_doc = ((current_contract or {}).get('extensions') or {}).get('factory.node-contracts') or {}
    current_nodes = {n.get('node_id'): n for n in current_doc.get('nodes') or []}

    # -- static node detail ------------------------------------------------------------------------------
    latest = graphs[history[-1]['rev']] if history else {}
    nodes = {}
    for key, g in latest.items():
        nodes[key] = dict(node_id=key, title=g.get('title') or key, kind=g.get('kind'), node_contract=g.get('node_contract'),
                          depends_on=g.get('depends_on', []), finals=[], refusals=[], checks=[], runs=[], preliminary=None,
                          preliminary_source=None, gate=[], briefs=[], planned=False, dropped=None)
    if current_nodes:
        for key, node in nodes.items():
            name = node['node_contract'] or key
            g = latest.get(key) or {}
            if name not in current_nodes and g.get('state') not in {'cancelled', 'superseded'}:
                node['dropped'] = (f'contract {current_label} no longer has this step; an operator revise retires it'
                                   + (' (its recorded work stays)' if g.get('state') == 'done' else ''))
        for name, contract in current_nodes.items():
            if name not in nodes and not any(n['node_contract'] == name for n in nodes.values()):
                nodes[name] = dict(node_id=name, title=contract.get('objective') or name, kind=contract.get('kind'),
                                   node_contract=name, depends_on=[d for d in contract.get('predecessors') or []],
                                   finals=[], refusals=[], checks=[], runs=[], preliminary=contract_view(contract),
                                   preliminary_source=f'contract {current_label} (planned; not in the live graph yet)',
                                   gate=[dict(output=o.get('name'), kind=o.get('kind'), required=True,
                                              review=next((v.get('review') for v in contract.get('verifiers') or []
                                                           if v.get('output') == o.get('name')), None))
                                         for o in contract.get('outputs') or []],
                                   briefs=[], planned=True, dropped=None)
    for o in by_kind.get('node_contract_final', []):
        v = o['values']
        node = nodes.get(v.get('node_id'))
        if node is None:
            continue
        prelim, source = None, None
        for label, document in contracts:
            match = next((n for n in document['nodes'] if n.get('node_id') == v.get('node_contract')
                          and digest(n) == v.get('preliminary_digest')), None)
            if match:
                prelim, source = match, f'contract file {label} (digest matches the final record)'
                break
        if prelim is None:
            try:
                rebuilt = rebuild_preliminary(v.get('final') or {}, v.get('diff'))
            except (KeyError, TypeError, AttributeError):
                rebuilt = None
            if rebuilt is not None and digest(rebuilt) == v.get('preliminary_digest'):
                prelim, source = rebuilt, "rebuilt from the final record's diff (digest matches)"
            elif rebuilt is not None:
                prelim, source = rebuilt, "rebuilt from the final record's diff (digest does NOT match)"
        if node['preliminary'] is None and prelim is not None:
            node['preliminary'], node['preliminary_source'] = contract_view(prelim), source
        node['finals'].append(final_view(v, prelim) | dict(preliminary=contract_view(prelim), preliminary_source=source))
    for key, node in nodes.items():
        name = node['node_contract'] or key
        if node['preliminary'] is None and not node['finals'] and name in current_nodes:
            node['preliminary'] = contract_view(current_nodes[name])
            node['preliminary_source'] = f'contract {current_label} (the revision the run follows now; not finalized yet)'
        if node['preliminary'] is None and as_run:
            match = next((n for n in as_run[1]['nodes'] if n.get('node_id') == (node['node_contract'] or key)), None)
            if match:
                node['preliminary'] = contract_view(match)
                node['preliminary_source'] = f'contract file {as_run[0]} (best match for this run; not finalized yet)'
    for o in by_kind.get('node_contract_refusal', []):
        v = o['values']
        if v.get('node_id') in nodes:
            nodes[v['node_id']]['refusals'].append(dict(t=o.get('created'), problems=v.get('problems') or [],
                                                        why=refusal_kind(v.get('problems')), rationale=_clip(v.get('rationale'), 900),
                                                        by=v.get('by')))
    for o in by_kind.get('node_check', []):
        v = o['values']
        if v.get('node_id') in nodes:
            nodes[v['node_id']]['checks'].append(check_view(o))
    capped = {}
    loose = []
    for o in by_kind.get('capped_run', []):
        value = dict(o['values'], _created=o.get('created'))
        if value.get('attempt_id'):
            capped[value['attempt_id']] = value
        else:
            loose.append(value)
    runs = []
    for attempt in sorted(data.get('attempts', []), key=lambda a: a.get('started') or 0):
        if attempt.get('task_id', task_id) != task_id:
            continue
        runs.append(run_view(attempt, capped.pop(attempt['attempt_id'], None)))
    runs += [run_view(None, value) for value in list(capped.values()) + loose]
    for run in runs:
        if run['node_id'] in nodes:
            nodes[run['node_id']]['runs'].append(run)

    # -- raw events ----------------------------------------------------------------------------------------
    events = []

    def add(t, kind, actor, title, node=None, detail='', tone='info', key=True, ref=None, graph_rev=None, **extra):
        events.append(dict(t=t or 0, kind=kind, actor=actor, who=ACTORS.get(actor, actor), title=title, node=node,
                           detail=_clip(detail, 900), tone=tone, key=key, ref=ref, graph_rev=graph_rev) | extra)

    final_by_digest = {(o['values'].get('node_id'), o['values'].get('digest')): o for o in by_kind.get('node_contract_final', [])}
    used_finals = set()
    for entry in history:
        rev, patch, origin, t = entry['rev'], entry.get('patch') or {}, entry.get('origin'), entry.get('created')
        before, after = graphs.get(rev - 1, {}), graphs[rev]
        if origin == 'seed':
            add(t, 'plan', 'planner', f'Plan loaded: {len(after)} steps, each with a preliminary contract',
                detail='The planner wrote the task graph. Each step has a preliminary contract the scheduler agent '
                       'finalizes just before the step runs.', ref=f'graph rev {rev}', graph_rev=rev)
        elif origin == 'scheduler':
            for change in patch.get('finalize', []):
                o = final_by_digest.get((change['node_id'], change['digest']))
                v = (o or {}).get('values') or {}
                bound = (v.get('final') or {}).get('work', {}).get('bound_ccs') or []
                filled = [c.get('path') for c in v.get('diff') or [] if c.get('path') not in {'slots', 'stage', 'bounds', 'work.bound_ccs'}]
                title = f"Scheduler finalized the contract of {change['node_id']}: binds {len(bound)} capsule{'s' if len(bound) != 1 else ''}"
                if filled:
                    title += f", fills {len(filled)} criterion slot{'s' if len(filled) != 1 else ''}"
                add((o or {}).get('created') or t, 'finalize', 'scheduler', title, node=change['node_id'],
                    detail='Bound: ' + ', '.join(bound) + (('. Filled: ' + ', '.join(filled)) if filled else ''),
                    tone='good', ref=(o or {}).get('obs_id'), graph_rev=rev,
                    final_index=sum(1 for k in used_finals if k[0] == change['node_id']))
                used_finals.add((change['node_id'], change['digest']))
        elif origin == 'operator':
            for op, changes in patch.items():
                if op == 'revise':
                    parts = {'cancel': [], 'add': [], 'update': []}
                    for change in changes:
                        parts.setdefault(change.get('action'), []).append(change.get('node_id'))
                    unfinal = [c.get('node_id') for c in changes if c.get('unfinalize')]
                    words = [f'removed {", ".join(parts["cancel"])}' if parts['cancel'] else '',
                             f'added {", ".join(parts["add"])}' if parts['add'] else '',
                             f'updated {", ".join(parts["update"])}' if parts['update'] else '',
                             f'cleared the final contract of {", ".join(unfinal)}' if unfinal else '']
                    reasons = list(dict.fromkeys(c.get('reason', '') for c in changes))
                    add(t, 'revise', 'operator', f'Operator applied a contract revision to the graph (graph rev {rev})',
                        node=(parts['add'] or parts['update'] or parts['cancel'] or [None])[0],
                        detail='; '.join(w for w in words if w) + ('. ' + '; '.join(r for r in reasons if r) if any(reasons) else ''),
                        tone='op', ref=f'graph rev {rev}', graph_rev=rev,
                        changes=[dict(node=c.get('node_id'), action=c.get('action'), reason=c.get('reason'),
                                      depends_on=c.get('depends_on'), unfinalize=bool(c.get('unfinalize'))) for c in changes])
                    continue
                for change in changes if isinstance(changes, list) else []:
                    node, reason = change['node_id'], change.get('reason', '')
                    if op == 'hold' and reason.startswith(STEP_PREFIX):
                        add(t, 'step_hold', 'host', f'Step checkpoint: {node} pauses before it runs', node=node,
                            detail='Step mode: the operator reads the final contract, then releases the step.',
                            tone='warn', ref=f'graph rev {rev}', graph_rev=rev)
                    elif op == 'release':
                        add(t, 'release', 'operator', f'Operator released {node}', node=node, detail=reason,
                            tone='op', ref=f'graph rev {rev}', graph_rev=rev)
                    elif op == 'reopen':
                        add(t, 'reopen', 'operator', f'Operator reopened {node}: it gets a new final contract', node=node,
                            detail=reason, tone='warn', ref=f'graph rev {rev}', graph_rev=rev)
                    elif op == 'retire':
                        add(t, 'retire', 'operator', f'Operator retired {node}', node=node, detail=reason, tone='warn',
                            ref=f'graph rev {rev}', graph_rev=rev)
                    elif op == 'hold':
                        add(t, 'hold', 'operator', f'Operator held {node}', node=node, detail=reason, tone='warn',
                            ref=f'graph rev {rev}', graph_rev=rev)
                    else:
                        add(t, 'operator', 'operator', f'Operator {op} on {node}', node=node, detail=reason, tone='op',
                            ref=f'graph rev {rev}', graph_rev=rev)
        else:
            done = [k for k, n in after.items() if n['state'] == 'done' and before.get(k, {}).get('state') != 'done']
            added = [k for k in after if k not in before]
            closed = [k for k, n in after.items() if n['state'] in {'cancelled', 'superseded'}
                      and before.get(k, {}).get('state') not in {'cancelled', 'superseded'}]
            if done:
                for k in done:
                    add(t, 'done', 'agent', f'{k} is done: every required output passed its check', node=k,
                        detail=after[k].get('reason', ''), tone='good', ref=f'graph rev {rev}', graph_rev=rev)
            elif added or closed:
                add(t, 'replan', 'agent', 'Agent changed the plan: ' + ', '.join(
                    [f'added {k}' for k in added] + [f'{after[k]["state"]} {k}' for k in closed]),
                    node=(added or closed)[0], tone='warn', ref=f'graph rev {rev}', graph_rev=rev)
            else:
                touched = [c.get('node_id') for ops in patch.values() for c in ops if isinstance(c, dict)]
                add(t, 'progress', 'agent', 'Agent recorded evidence on ' + ', '.join(touched or ['the plan']),
                    node=(touched or [None])[0], key=False, ref=f'graph rev {rev}', graph_rev=rev)
    for o in by_kind.get('node_contract_refusal', []):
        v = o['values']
        add(o.get('created'), 'refusal', 'host', f"Host refused the scheduler's contract for {v.get('node_id')}: "
            + refusal_kind(v.get('problems')).split(':')[0], node=v.get('node_id'),
            detail='; '.join(v.get('problems') or []) + (f" (proposal by {v.get('by')}: {_clip(v.get('rationale'), 200)})"
                                                         if v.get('by') not in (None, 'scheduler-agent') else ''),
            tone='bad', ref=o.get('obs_id'))
    for o in by_kind.get('node_check', []):
        view = check_view(o)
        node = o['values'].get('node_id')
        if view['state'] != 'finished':
            add(o.get('created'), 'check_start', 'checker', f"Checking {node} · {view['output']}", node=node, key=False,
                ref=o.get('obs_id'), output=view['output'], check_state='running')
            continue
        parts = []
        if view.get('verifier'):
            ver = view['verifier']
            parts.append(f"capsule verifier {'passed' if ver['passed'] else 'failed'}"
                         + (f" ({', '.join(ver['failed'])})" if ver['failed'] else '') + (f" at {ver['stage']}" if ver.get('stage') else ''))
        if view.get('review'):
            rv = view['review']
            parts.append(f"reviewer {rv['verdict'] or 'gave no verdict'}"
                         + (' (advisory: recorded, does not block)' if rv.get('advisory') else ' (blocking)')
                         + (f": {rv['blockers'][0]}" if rv['blockers'] else ''))
        add(o.get('created'), 'check', 'checker',
            f"Check {'passed' if view['passed'] else 'failed'}: {node} · {view['output']}", node=node,
            detail='; '.join(parts) or view['reason'], tone='good' if view['passed'] else 'bad', ref=o.get('obs_id'),
            output=view['output'], check_state='passed' if view['passed'] else 'failed')
    for run in runs:
        label = f" ({run['label']})" if run['label'] else ''
        cap = f" under a {run['memory_cap']} memory cap" if run['memory_cap'] else ''
        origin = run['replay_source']
        detail = f'Replay source {origin}' if origin else ''
        if origin and run['t_queued'] is not None:
            add(run['t_queued'], 'run_queued', 'runner', f"Queued {run['what']}{label} for {run['node_id']}",
                node=run['node_id'], detail=detail, ref=run['attempt_id'], attempt=run['attempt_id'], run_state='queued')
        if run['t_start'] is not None:
            add(run['t_start'], 'run_start', 'runner', f"Started {run['what']}{label} for {run['node_id']}{cap}",
                node=run['node_id'], detail=detail, ref=run['attempt_id'], attempt=run['attempt_id'], run_state='running')
        if run['t_end'] is not None:
            size = f", wrote {human_bytes(run['bytes'])}" if run['bytes'] and run['bytes'] > 1e6 else ''
            duration = run['verification_duration'] if origin else human_seconds(run['seconds'])
            took = f' in {duration}' if duration else ''
            if run['bytes_read']:
                size = f", hashed {human_bytes(run['bytes_read'])}"
            if run['probe']:
                label += ' (one-layer probe)'
            if run['state'] == 'succeeded':
                title, tone = f"{run['what'].capitalize()}{label} finished{took}{size}", 'good'
                if origin:
                    title += f', replayed from {origin}'
                    detail = f"Verified {human_bytes(run['verified_bytes'])}" if run['verified_bytes'] else 'Pack verified'
            elif run['state'] == 'cancelled':
                title, tone = f"{run['what'].capitalize()}{label} cancelled" + (f' after {duration}' if duration else ''), 'warn'
            else:
                code = (run['error'] or {}).get('code') or 'failed'
                title, tone = f"{run['what'].capitalize()}{label} stopped: {code}", 'bad'
            add(run['t_end'], 'run', 'runner', title, node=run['node_id'],
                detail=' · '.join(filter(None, (detail, (run['error'] or {}).get('message')))),
                tone=tone, ref=run['attempt_id'],
                attempt=run['attempt_id'], run_state=run['state'])
    for o in by_kind.get('operator_halt', []):
        v = o['values']
        add(o.get('created'), 'halt', 'host', f"Run halted for the operator ({v.get('node_id') or 'task'})",
            node=v.get('node_id'), detail=v.get('reason'), tone='bad', ref=o.get('obs_id'))
    for o in by_kind.get('operator_pause', []):
        v = o['values']
        if v.get('action') == 'pause':
            add(v.get('at') or o.get('created'), 'pause', 'operator', f"Operator paused the run (by {v.get('by') or 'operator'})",
                detail=(v.get('reason') or '') + (' Running jobs cancelled.' if v.get('cancel_jobs') else ' Running jobs left to finish.'),
                tone='warn', ref=o.get('obs_id'), pause=dict(reason=v.get('reason'), by=v.get('by'), at=v.get('at') or o.get('created')))
        elif v.get('action') == 'resume':
            add(v.get('at') or o.get('created'), 'resume', 'operator', f"Operator resumed the run (by {v.get('by') or 'operator'})",
                detail=v.get('reason') or '', tone='op', ref=o.get('obs_id'))
    for o in by_kind.get('attempt_excused', []):
        v = o['values']
        add(o.get('created'), 'excuse', 'operator', f"Operator excused run {short(v.get('attempt_id'))} as a host fault",
            node=v.get('node_id'), detail=v.get('reason'), tone='op', ref=o.get('obs_id'),
            detail_note='An excused run does not count against the step\'s limits.')
    for o in by_kind.get('operator_input', []):
        v = o['values']
        add(o.get('created'), 'input', 'operator', f"Operator supplied an input: {v.get('key') or v.get('artifact_id')}",
            detail=v.get('how') or '', tone='op', ref=o.get('obs_id'))
    for note in notes:
        if note.get('task_id', task_id) != task_id or NOTE_ECHO.match(str(note.get('text', ''))):
            continue
        add(note.get('created'), 'note', 'operator', 'Operator note to the agent', detail=note.get('text', ''),
            tone='op', ref=note.get('note_id'))
    for d in data.get('decisions', []):
        action = d.get('action') or {}
        step = action.get('operation') or action.get('next_operation') or action.get('next_bounded_operation') or action.get('type')
        add(d.get('created'), 'agent', 'agent', f"Agent: {_clip(step, 160)}", node=action.get('node_id'),
            detail=d.get('reason_for_change') or '', key=False, ref=f"decision rev {d.get('rev')}")
    calls = []
    for e in telemetry:
        if e.get('task_id', task_id) != task_id:
            continue
        if e.get('event') == 'scheduler.turn':
            add(e.get('ts'), 'scheduler_turn', 'scheduler',
                f"Scheduler agent worked {human_seconds((e.get('duration_ms') or 0) / 1000)} on {e.get('node_id')}"
                + (f" ({e.get('model')})" if e.get('model') else ''), node=e.get('node_id'), key=False,
                tone='info' if e.get('outcome') == 'ok' else 'bad', ref=f"telemetry {e.get('seq')}")
        elif e.get('event') == 'cc.call':
            calls.append(dict(t=e.get('ts'), capsule=e.get('capsule'), version=e.get('capsule_version'),
                              capability=e.get('capability'), ms=e.get('duration_ms'), outcome=e.get('outcome'),
                              error=e.get('error_code'), out_bytes=e.get('out_bytes')))

    order_kind = {'plan': 0, 'refusal': 1, 'finalize': 2, 'step_hold': 3, 'release': 4}
    events.sort(key=lambda e: (e['t'], order_kind.get(e['kind'], 5), str(e.get('ref'))))
    for i, e in enumerate(events):
        e['i'] = i

    # -- node states after each event ----------------------------------------------------------------------
    graph, sim = {}, {k: dict(running=set(), checking=set(), failed=set(), halted=False) for k in nodes}
    frames, run_states, paused, running_since = [], [], None, {}
    for e in events:
        node = e.get('node')
        if e.get('graph_rev') is not None:
            new = graphs[e['graph_rev']]
            for k, n in new.items():
                if k in graph and graph[k].get('final_contract') and not n.get('final_contract'):
                    sim[k].update(checking=set(), failed=set(), halted=False)  # reopened: a fresh start
            graph = new
        s = sim.get(node)
        if s is not None:
            if e['kind'] == 'run_start':
                s['running'].add(e['attempt'])
                s['halted'] = False
            elif e['kind'] == 'run':
                s['running'].discard(e['attempt'])
            elif e['kind'] == 'check_start':
                s['checking'].add(e['output'])
            elif e['kind'] == 'check':
                s['checking'].discard(e['output'])
                (s['failed'].add if e['check_state'] == 'failed' else s['failed'].discard)(e['output'])
            elif e['kind'] == 'halt':
                s['halted'] = True
            elif e['kind'] in {'excuse', 'release', 'reopen'}:
                s['halted'] = False
        if e['kind'] == 'pause':
            paused = e['pause']
        elif e['kind'] == 'resume':
            paused = None
        if e['kind'] == 'run_start':
            running_since[e['attempt']] = (e['t'], e['node'], e['title'])
        elif e['kind'] == 'run':
            running_since.pop(e['attempt'], None)
        frame = {k: node_state(graph.get(k), sim[k], graph) for k in nodes if k in graph}
        for k, n in nodes.items():
            if k not in graph and n['planned']:
                frame[k] = 'planned'
        frames.append(frame)
        run_states.append(run_state(frame, paused, running_since))
    for e, frame, rs in zip(events, frames, run_states):
        e['states'], e['run'] = frame, rs

    for key, node in nodes.items():
        spec = (latest.get(key) or {}).get('check') or {}
        for output in spec.get('outputs', []):
            node['gate'].append(dict(output=output.get('name'), kind=output.get('kind'),
                                     required=output.get('required', True), review=output.get('review')))
        if not node['gate'] and node['preliminary']:
            node['gate'] = [dict(output=o['name'], kind=o['kind'], required=True, review=o['review'])
                            for o in node['preliminary']['outputs']]
    for session in briefs:
        if session.get('node_id') in nodes:
            nodes[session['node_id']]['briefs'].append(session)

    products = []
    for run in runs:
        if run['state'] != 'succeeded':
            continue
        if run['recipe'] == 'convert' or (run['recipe'] == 'quantize' and not run['probe']):
            origin = run['replay_source']
            if run['recipe'] == 'convert':
                what = 'NVFP4 weight pack' if origin else 'NVFP4 weight pack (converted checkpoint)'
            else:
                what = '2-bit weight pack' if origin else 'New 2-bit weight pack'
            products.append(dict(t=run['t_end'], node=run['node_id'], what=what,
                                 size=human_bytes(run['verified_bytes'] if origin else run['bytes']),
                                 name=run['label'], replay_source=origin))
        elif run['recipe'] == 'build':
            products.append(dict(t=run['t_end'], node=run['node_id'], what='Engine build ' + str(run['label'] or ''),
                                 size=None, name=f"commit {short(run['commit'], 9)}" if run['commit'] else None))
    packs = [dict(name=name, files=len(m.get('files') or []), size=human_bytes(sum(f.get('bytes', 0) for f in m.get('files') or [])))
             for name, m in manifests]

    durations = [c['ms'] for c in calls if isinstance(c.get('ms'), (int, float))]
    meta = data.get('_meta') or {}
    state = meta.get('controller_state') or {}
    board = dict(
        schema='factory.demo-board/1', task=dict(task_id=task_id, objective=task.get('objective'),
                                                 contract_id=task.get('contract_id'), target=task.get('target')),
        started=events[0]['t'] if events else None, last=events[-1]['t'] if events else None,
        clock_offset_s=_clock_offset(observations), turns=(meta.get('budget_used') or {}).get('turns'),
        stop_reason=state.get('stop_reason'), outcome=meta.get('outcome'),
        graph_rev=history[-1]['rev'] if history else 0, nodes=list(nodes.values()), events=events, calls=calls,
        graph_dependencies={str(rev): {key: node['depends_on'] for key, node in graph.items()}
                            for rev, graph in graphs.items()},
        calls_p50_ms=statistics.median(durations) if durations else None, products=products, packs=packs,
        state_labels=STATE_LABELS, contracts_source=as_run[0] if as_run else None,
        contract=contract_summary(current_contract, current_label), skipped_ops=skipped_ops,
        run_files=run_files or dict(files={}, controller={}),
        commands=operator_commands(task_id, [k for k, n in nodes.items() if not n['planned']]))
    return _scrub_paths(board)


def contract_summary(contract, label):
    """The task contract the run follows now: version, title, arms and its node list."""
    if not isinstance(contract, dict):
        return None
    document = (contract.get('extensions') or {}).get('factory.node-contracts') or {}
    return dict(label=label, contract_id=contract.get('contract_id'), version=contract.get('version'),
                title=contract.get('title'), purpose=_clip(contract.get('purpose'), 900),
                arms=[dict(id=a.get('id'), role=a.get('role'), summary=a.get('summary'), source=a.get('from'))
                      for a in contract.get('arms') or [] if isinstance(a, dict)],
                nodes=[n.get('node_id') for n in document.get('nodes') or []],
                revisions=contract.get('revisions') or [])


def operator_commands(task_id, node_ids):
    """The exact operator commands for this run (the CLI the operator already uses); argv lists, no shell."""
    base = ['jiuwenswarm-factory']
    return dict(
        pause=base + ['pause', task_id, '<reason>'], resume=base + ['resume', task_id, '<reason>', '--no-run'],
        note=base + ['note', task_id, '<text>'], revise=base + ['revise', task_id, '<reason>', '--dry-run'],
        status=base + ['status', task_id, '--plain'],
        release={k: base + ['release', task_id, k, 'step checkpoint passed'] for k in node_ids},
        hold={k: base + ['hold', task_id, k, '<reason>'] for k in node_ids})


def run_state(frame, paused, running):
    """The run as one banner: paused, halted, step checkpoint, waiting on a job, working, or idle/finished."""
    if paused:
        return dict(state='paused', text=f"Paused by {paused.get('by') or 'operator'}: {paused.get('reason') or ''}",
                    since=paused.get('at'))
    halted = [k for k, s in frame.items() if s == 'halted']
    if halted:
        return dict(state='halted', text='Halted for the operator at ' + ', '.join(halted))
    held = [k for k, s in frame.items() if s == 'held']
    if held:
        return dict(state='step', text='Step checkpoint: ' + ', '.join(held) + ' waits for the operator to release it')
    if running:
        _, (since, node, title) = min(running.items(), key=lambda kv: kv[1][0])
        return dict(state='job', text=f'Waiting on a capped job for {node}: {title.removeprefix("Started ")}', since=since,
                    node=node, jobs=len(running))
    if frame and all(s in {'done', 'retired', 'removed', 'superseded', 'planned'} for s in frame.values()):
        return dict(state='finished', text='Every step is closed')
    active = [k for k, s in frame.items() if s in {'working', 'checking', 'fixing'}]
    if active:
        return dict(state='working', text='Agents working on ' + ', '.join(active))
    return dict(state='idle', text='Waiting for the next step')


def node_state(g, s, graph):
    """Board state of one graph node: its recorded graph state plus what is in flight for it."""
    if not g:
        return 'waiting'
    state = g.get('state')
    if state == 'done':
        return 'done'
    if state == 'cancelled':
        return 'removed' if 'revise' in str(g.get('reason', '')) else 'retired'
    if state in {'superseded', 'failed'}:
        return state
    if s['halted']:
        return 'halted'
    if g.get('hold'):
        return 'held' if str(g['hold']).startswith(STEP_PREFIX) else 'operator_hold'
    if s['running']:
        return 'running'
    if s['checking']:
        return 'checking'
    if s['failed']:
        return 'fixing'
    if g.get('final_contract'):
        return 'working'
    if all((graph.get(d) or {}).get('state') == 'done' for d in g.get('depends_on', [])):
        return 'ready'
    return 'waiting'


# -- reading a factory home (read-only) ----------------------------------------------------------------------

def read_telemetry(home, task_id):
    path = Path(home) / 'telemetry' / 'events.jsonl'
    out = []
    if path.is_file():
        with path.open(encoding='utf-8') as source:
            for line in source:
                if task_id not in line:
                    continue
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                if record.get('task_id') == task_id and record.get('event') in {'cc.call', 'scheduler.turn'}:
                    out.append(record)
    return out


BRIEF_SECTIONS = {'task': 'the task (title, purpose, scope)', 'plan': 'the plan with node states', 'neighbours': 'neighbouring steps',
                  'briefing': "the planner's notes for this step", 'preliminary': 'the preliminary contract',
                  'draft_final': 'a draft final contract', 'inputs': 'resolved inputs', 'upstream': 'accepted upstream evidence',
                  'failures': 'earlier failures of this step', 'earlier_finals': 'earlier finals of this step',
                  'capsules': 'capsule docs and capabilities', 'machine': 'machine state', 'constraints': 'operator constraints',
                  'resources': 'task resources', 'operator_inputs': 'operator inputs', 'refusals': 'earlier refusals',
                  'rule': 'the never-weaker rule'}


def _tool_text(result):
    """The text a cc tool returned, parsed as JSON when it is JSON."""
    try:
        value = json.loads(result) if isinstance(result, str) else result
        text = value['result']['content'][0]['text']
        return json.loads(text)
    except (ValueError, KeyError, IndexError, TypeError):
        return None


def read_briefs(home, task_id):
    """Per scheduler session: the briefs it read (sections and sizes), its proposals and its closing words.

    Source: sessions/<task>.scheduler.jsonl, the scheduler agent's transcript (tool calls and results)."""
    path = Path(home) / 'sessions' / f'{task_id}.scheduler.jsonl'
    if not path.is_file():
        return []
    sessions, calls, turn = {}, {}, {}
    with path.open(encoding='utf-8') as source:
        for line in source:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get('event') == 'turn.start':
                turn = dict(node_id=e.get('node_id'), model=e.get('model'), attempt=e.get('attempt'), t=e.get('t'))
                continue
            sid = e.get('session_id')
            if not sid:
                continue
            session = sessions.setdefault(sid, dict(session=sid, node_id=turn.get('node_id'), model=turn.get('model'),
                                                    attempt=turn.get('attempt'), t=e.get('t'), briefs=[], proposals=[], said=None))
            kind = e.get('event_type')
            if kind == 'chat.tool_call':
                call = e.get('tool_call') or {}
                calls[call.get('tool_call_id')] = call
            elif kind == 'chat.tool_result':
                call = calls.get(e.get('tool_call_id')) or {}
                args = call.get('arguments') or {}
                if call.get('name') != 'cc.cc_call':
                    continue
                value = _tool_text(e.get('result'))
                outputs = (value or {}).get('outputs') or {}
                if args.get('capability') == 'brief' and isinstance(outputs.get('brief'), dict):
                    brief = outputs['brief']
                    sections = [dict(name=k, label=BRIEF_SECTIONS.get(k, k), bytes=len(json.dumps(v, ensure_ascii=False)),
                                     items=len(v) if isinstance(v, (list, dict)) else None)
                                for k, v in brief.items() if k not in {'schema', 'task_id', 'node_id', 'state'} and v not in (None, [], {}, '')]
                    session['briefs'].append(dict(t=e.get('t'), schema=brief.get('schema'), bytes=len(json.dumps(brief, ensure_ascii=False)),
                                                  sections=sorted(sections, key=lambda s: -s['bytes'])))
                elif args.get('capability') == 'propose':
                    result = outputs.get('result') or {}
                    session['proposals'].append(dict(t=e.get('t'), admitted=result.get('admitted'), problems=result.get('problems') or [],
                                                     digest=result.get('digest'), state=(value or {}).get('state')))
            elif kind == 'chat.final':
                session['said'] = _clip(e.get('content'), 700)
    return [s for s in sessions.values() if s['node_id']]


def read_run_files(home, task_id):
    """PAUSE.md, HALT.md and STEP.md (what the factory tells a person) and the controller's state file."""
    home = Path(home)
    files = {}
    for name in ('PAUSE.md', 'HALT.md', 'STEP.md'):
        path = home / name
        try:
            text = path.read_text(encoding='utf-8', errors='replace')
            files[name] = dict(text=_clip(text, 1200), mtime=path.stat().st_mtime)
        except (FileNotFoundError, IsADirectoryError):  # the file may be absent or cleared during polling
            continue
    state = {}
    path = home / 'sessions' / f'{task_id}.state.json'
    if path.is_file():
        try:
            value = json.loads(path.read_text(encoding='utf-8'))
            state = {k: value.get(k) for k in ('outcome', 'stop_reason', 'tick', 'turns', 'started', 'stepped')}
        except (OSError, ValueError):
            pass
    return dict(files=files, controller=state)


def read_notes(home, task_id):
    directory = Path(home) / 'operator-inbox' / task_id
    notes = []
    for path in sorted(directory.glob('*.json')) if directory.is_dir() else []:
        try:
            notes.append(json.loads(path.read_text(encoding='utf-8')))
        except (OSError, ValueError):
            continue
    return notes


def read_manifests(home):
    found = []
    for path in sorted((Path(home) / 'packs').glob('*/*.manifest.json')):
        if path.name.endswith('-probe.manifest.json'):
            continue
        try:
            found.append((path.name.removesuffix('.manifest.json'), json.loads(path.read_text(encoding='utf-8'))))
        except (OSError, ValueError):
            continue
    return found


def contract_paths(home, contract_id, extra=()):
    from .contract import CONTRACTS

    paths = list(extra)
    for candidate in (Path(home) / 'contracts', Path(home).parent / 'contracts'):
        if candidate.is_dir():
            paths.append(candidate)
    if contract_id:
        path = Path(contract_id) if '/' in contract_id or contract_id.endswith('.json') else CONTRACTS / f'{contract_id}.json'
        paths.append(path)
    return paths


def current_contract(contract_id, value, override=None):
    """(label, contract JSON) of the task contract as it stands now (the revision a revise would apply)."""
    if override:
        try:
            value = json.loads(Path(override).read_text(encoding='utf-8'))
        except (OSError, ValueError, TypeError):
            return None
    if not isinstance(value, dict) or not value:
        return None
    version = value.get('version')
    name = value.get('contract_id') or Path(override or contract_id).stem
    return (f"{name} rev {version}" if version is not None else name), value


def load_board(home, task_id, contracts=(), contract=None):
    from .story import load_source
    from .redact import sanitize
    home = Path(home).expanduser().resolve()
    data = load_source(task_id, home)
    contract_id = data['tasks'][0].get('contract_id')
    docs = contract_documents(contract_paths(home, contract_id, contracts))
    board = build_replay(data, telemetry=read_telemetry(home, task_id), notes=read_notes(home, task_id),
                         contracts=docs, manifests=read_manifests(home),
                         current=current_contract(contract_id, data.get('_contract'), contract),
                         briefs=read_briefs(home, task_id), run_files=read_run_files(home, task_id))
    return sanitize(board)


# -- operator actions (only with --operator) -----------------------------------------------------------------

OPERATOR_ACTIONS = {'pause': ('reason',), 'resume': ('reason',), 'release': ('node', 'reason'), 'note': ('text',)}


def operator_argv(home, task_id, request):
    """The CLI call for one operator action from the board: the same command the operator would type."""
    import sys
    action = request.get('action')
    if action not in OPERATOR_ACTIONS:
        raise ValueError('The board offers pause, resume, release and note only')
    values = []
    for field in OPERATOR_ACTIONS[action]:
        value = request.get(field) or ('step checkpoint passed' if action == 'release' and field == 'reason' else '')
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f'{action} needs a {field}')
        if field == 'node' and not re.fullmatch(r'[A-Za-z0-9_.-]+', value):
            raise ValueError('Invalid node id')
        values.append(value.strip())
    # The launcher's environment and grants own step-mode execution. The board only clears the pause.
    flags = ['--no-run'] if action == 'resume' else []
    return [sys.executable, '-m', 'jiuwenswarm.factory.cli', '--home', str(home), action, task_id, *values, *flags]


def run_operator(argv, home):
    import subprocess
    done = subprocess.run(argv, capture_output=True, text=True, timeout=120, env=dict(os.environ, FACTORY_HOME=str(home)),
                          cwd=str(Path(__file__).resolve().parents[2]))
    return dict(argv=argv[2:], returncode=done.returncode, stdout=done.stdout[-4000:], stderr=done.stderr[-4000:])


# -- HTTP ----------------------------------------------------------------------------------------------------

HTML_PATH = Path(__file__).with_name('demo_board.html')
LOOPBACK = {'127.0.0.1', 'localhost', '::1'}


def board_payload(home, task_id, contracts=(), contract=None, *, operator=False):
    board = load_board(home, task_id, contracts, contract)
    return dict(board, operator_enabled=bool(operator))


def make_handler(home, task_id=None, contracts=(), contract=None, operator=False, runner=run_operator):
    """The monitor's read-only handler (/api/tasks, plan, story, telemetry, job) plus /, /api/board and, only
    with operator=True, POST /api/operator (pause, resume, release, note through the factory CLI)."""
    from .monitor import make_handler as monitor_handler
    base = monitor_handler(home)
    home = Path(home).expanduser().resolve()

    class Handler(base):
        def _send(self, status, body, mime='application/json; charset=utf-8'):
            if not isinstance(body, bytes):
                body = json.dumps(body, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)

        def _task(self, query):
            from urllib.parse import parse_qs
            task = parse_qs(query).get('task', [''])[0] or task_id
            if not task:
                from .monitor import tasks
                listed = tasks(home)
                if not listed:
                    raise ValueError('No task in this factory home')
                task = listed[0]['task_id']
            return task

        def do_GET(self):
            from urllib.parse import urlsplit
            url = urlsplit(self.path)
            if url.path == '/':
                return self._send(200, HTML_PATH.read_text(encoding='utf-8').encode('utf-8'), 'text/html; charset=utf-8')
            if url.path == '/api/board':
                try:
                    board = board_payload(home, self._task(url.query), contracts, contract, operator=operator)
                    return self._send(200, board)
                except Exception as exc:  # the board stays up; the page shows the error
                    return self._send(400, dict(error=f'{type(exc).__name__}: {exc}'))
            return super().do_GET()

        def do_POST(self):
            from urllib.parse import urlsplit
            url = urlsplit(self.path)
            if url.path != '/api/operator':
                return self._send(404, dict(error='not found'))
            if not operator:
                return self._send(403, dict(error='The board is read-only; start it with --operator to allow actions'))
            if self.client_address[0] not in LOOPBACK or self.headers.get('X-Board-Operator') != '1':
                return self._send(403, dict(error='Operator actions come only from the board page on this machine'))
            try:
                length = min(int(self.headers.get('Content-Length') or 0), 65536)
                request = json.loads(self.rfile.read(length) or b'{}')
                argv = operator_argv(home, self._task(url.query), request)
                return self._send(200, runner(argv, home))
            except Exception as exc:
                return self._send(400, dict(error=f'{type(exc).__name__}: {exc}'))
    return Handler


def make_server(home, task_id=None, bind='127.0.0.1', port=DEFAULT_PORT, contracts=(), contract=None, operator=False):
    from http.server import ThreadingHTTPServer
    if operator and bind not in LOOPBACK:
        raise ValueError('--operator binds to 127.0.0.1 only')
    return ThreadingHTTPServer((bind, port), make_handler(home, task_id, contracts, contract, operator))


def serve(home, task_id=None, bind='127.0.0.1', port=DEFAULT_PORT, contracts=(), contract=None, operator=False):
    with make_server(home, task_id, bind, port, contracts, contract, operator) as server:
        host, bound = server.server_address[:2]
        print(f'Factory demo board on http://{host}:{bound}/' + (f'?task={task_id}' if task_id else '')
              + (' (operator actions ON)' if operator else ' (read-only)'), flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python -m jiuwenswarm.factory.demo_board', description=__doc__.split('\n')[0])
    parser.add_argument('--home', default=os.environ.get('FACTORY_HOME', '~/.jiuwenswarm-factory'),
                        help='factory home to read (a live home or a local snapshot); never written')
    parser.add_argument('--task', default=None, help='task id (default: the newest task in the home)')
    parser.add_argument('--contracts', action='append', default=[],
                        help='extra contract JSON file or directory to find preliminary contracts in (repeatable)')
    parser.add_argument('--contract', default=None,
                        help='the task contract as it stands now (default: the package contract of the task)')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT)
    parser.add_argument('--bind', default='127.0.0.1')
    parser.add_argument('--operator', action='store_true',
                        help='allow pause, resume, release and note from the page (127.0.0.1 only, each confirmed)')
    args = parser.parse_args(argv)
    serve(Path(args.home).expanduser(), args.task, args.bind, args.port, args.contracts, args.contract, args.operator)


if __name__ == '__main__':
    main()
