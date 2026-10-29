"""Parse each arm's raw plan reply into the ONE neutral plan form that executor.py runs.

PARSER_VERSION is recorded in every run record; the parser is model-free, so a run can be rescored
with a newer version without new calls (only if the change is made before looking at scores, see README).

CC arm   : the reply is the pinned plan-proposal JSON (or one line "INFEASIBLE: ..."). Mapping is
           mechanical: node -> step, cc.cc_name -> capability, accepted_ref/run_input_key -> external,
           future_output -> step, predecessors -> depends_on, deliverable_ids (and coverage entries) ->
           covers, suggested_checks -> criteria. Pin and port errors are kept as ``issues`` (CC only,
           because only the CC arm is shown pins and port names).

Skill arm: the task asked for one JSON object (feasible, reason, steps[], final_step). The parser is
           deliberately tolerant about shape, never about content:
             1. "INFEASIBLE: ..." as the first line  -> infeasible.
             2. else collect every JSON object in the reply (whole text, fenced blocks, and any object
                found with raw_decode at each '{'); keep those that look like plans (have steps/plan/nodes
                or feasible); use the LAST one.
             3. accepted key aliases: steps|plan|nodes; id|step|step_id|name; capability|tool|skill|uses;
                inputs as {param: source} or [{name|param, source|from}] or [source,...];
                depends_on|dependencies|after; covers|deliverables|requirements; success_criteria|
                criteria|acceptance_criteria|checks; final_step|final.
             4. a source string is read as: input:KEY / external:KEY / supplied:KEY / `KEY` in the supplied
                inputs -> external; a step id, "step.out", "step:out" -> step; any other bare identifier ->
                external with that name (so an invented input is caught as fabricated, not hidden);
                prose that names nothing -> unresolved (the step cannot be bound).
             5. feasible false/"no"/"false"/"infeasible"/"blocked" -> infeasible (reason from reason|why|
                missing|blocked_by). feasible "partial"/"undetermined"/"conditional" -> plan with
                complete_claim=false (a structured caveat). Anything else -> complete claim.
           A reply with no readable object, no steps, or a step without id/capability is "unreadable".
           Unreadable plans are scored as not executable. No markdown-table reading is attempted.
"""
import sys
sys.dont_write_bytecode = True
import json
import re

PARSER_VERSION = 'planbench-parser-1'

PLAN_KEYS = ('steps', 'plan', 'nodes', 'workflow')
INFEAS = {'false', 'no', 'infeasible', 'blocked', 'impossible', 'cannot'}
PARTIAL = {'partial', 'undetermined', 'conditional', 'unknown', 'uncertain', 'maybe'}


def infeasible(reason):
    return {'kind': 'infeasible', 'reason': str(reason or '').strip()}


def unreadable(reason):
    return {'kind': 'unreadable', 'reason': reason}


# ---------------------------------------------------------------------------------------------
# CC arm
# ---------------------------------------------------------------------------------------------

def _dnum(raw):
    m = re.search(r'(?:^|:)d(\d+)$', str(raw))
    return 'D' + m.group(1) if m else 'D?:' + str(raw)


def normalize_cc(raw, task=None, library=None):
    if not isinstance(raw, str) or not raw.strip():
        return unreadable('empty reply')
    text = raw.strip()
    if text.startswith('INFEASIBLE:'):
        return infeasible(text[len('INFEASIBLE:'):])
    try:
        p = json.loads(text)
    except ValueError as exc:
        return unreadable('not JSON: %s' % exc)
    if not isinstance(p, dict) or not isinstance(p.get('nodes'), list) or not p['nodes']:
        return unreadable('no nodes')
    entries = {}
    if library:
        entries = {e['cc_name']: e for e in library['library_snapshot']['entries']}
    all_d = ['D' + str(i + 1) for i in range(len((task or {}).get('deliverables', [])))]
    steps, issues = [], []
    try:
        for n in p['nodes']:
            sid = n['node_id']
            ins = []
            for i in n.get('inputs', []):
                k = i.get('source_kind')
                if k == 'future_output' and i.get('future'):
                    src = {'step': i['future']['producer_node'], 'output': i['future']['port']}
                elif k == 'accepted_ref' and i.get('run_input_key'):
                    src = {'external': i['run_input_key']}
                else:
                    src = {'unresolved': '%s:%s' % (k, i.get('run_input_key'))}
                ins.append({'param': i['name'], 'src': src})
            steps.append({'id': sid, 'capability': n['cc']['cc_name'], 'inputs': ins,
                          'outputs': [o['name'] for o in n.get('outputs', [])],
                          'depends_on': list(n.get('predecessors', [])),
                          'covers': [_dnum(d) for d in n.get('deliverable_ids', [])],
                          'criteria': list(n.get('suggested_checks', []))})
            e = entries.get(n['cc']['cc_name'])
            if library and e is not None:
                if any(n['cc'].get(k) != e[k] for k in ('cc_version', 'declaration_sha256')):
                    issues.append({'class': 'fabricated_pin', 'step': sid, 'detail': n['cc']})
                for i in n.get('inputs', []):
                    if i['name'] not in {x['name'] for x in e['input_ports']}:
                        issues.append({'class': 'fabricated_port', 'step': sid, 'detail': 'input ' + i['name']})
                for o in n.get('outputs', []):
                    if o['name'] not in {x['name'] for x in e['output_ports']}:
                        issues.append({'class': 'fabricated_port', 'step': sid, 'detail': 'output ' + o['name']})
            elif library and e is None:
                issues.append({'class': 'fabricated_pin', 'step': sid, 'detail': 'unknown capability ' + str(n['cc'].get('cc_name'))})
        by = {s['id']: s for s in steps}
        for c in p.get('coverage', []):
            if c.get('item_kind') == 'deliverable' or c.get('selector') == 'all_deliverables':
                ds = all_d if c.get('selector') == 'all_deliverables' else [_dnum(c.get('item_id'))]
                for nid in c.get('node_ids', []):
                    if nid in by:
                        by[nid]['covers'] = sorted(set(by[nid]['covers']) | set(ds))
        used = {x for s in steps for x in s['depends_on']}
        sinks = [s['id'] for s in steps if s['id'] not in used]
    except (KeyError, TypeError, AttributeError) as exc:
        return unreadable('malformed proposal: %r' % exc)
    return {'kind': 'plan', 'complete_claim': True, 'steps': steps, 'final': sinks[0] if len(sinks) == 1 else None,
            'issues': issues, 'reason': ''}


# ---------------------------------------------------------------------------------------------
# Skill arm
# ---------------------------------------------------------------------------------------------

def _objects(text):
    """Every JSON object in the reply that looks like a plan, in order of appearance."""
    found, dec, i = [], json.JSONDecoder(), 0
    while True:
        j = text.find('{', i)
        if j < 0:
            break
        try:
            obj, end = dec.raw_decode(text, j)
        except ValueError:
            i = j + 1
            continue
        if isinstance(obj, dict) and (any(k in obj for k in PLAN_KEYS) or 'feasible' in obj):
            found.append(obj)
            i = end
        else:
            i = j + 1
    return found


def _as_list(v):
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def _first(d, keys):
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None


def parse_source(raw, step_ids, input_keys):
    if isinstance(raw, dict):
        if 'step' in raw or 'from_step' in raw:
            return {'step': str(_first(raw, ('step', 'from_step'))), 'output': _first(raw, ('output', 'port', 'name'))}
        k = _first(raw, ('input', 'external', 'key', 'source'))
        return parse_source(k, step_ids, input_keys) if isinstance(k, str) else {'unresolved': json.dumps(raw)[:80]}
    if not isinstance(raw, str):
        return {'unresolved': str(raw)[:80]}
    s = raw.strip().strip('`').strip()
    m = re.match(r'(?i)^(input|external|supplied|inputs|resource)\s*[:.]\s*`?([A-Za-z_][\w\-]*)`?$', s)
    if m:
        return {'external': m.group(2)}
    if s in step_ids:
        return {'step': s, 'output': None}
    m = re.match(r'^([A-Za-z_][\w\-]*)\s*[.:/]\s*([A-Za-z_][\w\-]*)$', s)
    if m and m.group(1) in step_ids:
        return {'step': m.group(1), 'output': m.group(2)}
    m = re.match(r'(?i)^(?:the )?(?:output|result) of (?:step )?`?([A-Za-z_][\w\-]*)`?$', s)
    if m and m.group(1) in step_ids:
        return {'step': m.group(1), 'output': None}
    if s in input_keys:
        return {'external': s}
    if re.fullmatch(r'[A-Za-z_][\w\-]*', s):
        return {'external': s}             # an invented bare name: the executor reports it as fabricated
    return {'unresolved': s[:80]}


def _inputs(step, step_ids, input_keys):
    raw = _first(step, ('inputs', 'input', 'source', 'sources'))
    out = []
    if isinstance(raw, dict) and not ({'step', 'from_step'} & set(raw)) and not (set(raw) <= {'input', 'external', 'key', 'source'} and len(raw) == 1):
        for k, v in raw.items():
            out.append({'param': str(k), 'src': parse_source(v, step_ids, input_keys)})
    else:
        for item in _as_list(raw):
            if isinstance(item, dict) and ('name' in item or 'param' in item or 'parameter' in item) and any(k in item for k in ('source', 'from', 'value', 'src')):
                out.append({'param': str(_first(item, ('name', 'param', 'parameter'))),
                            'src': parse_source(_first(item, ('source', 'from', 'value', 'src')), step_ids, input_keys)})
            else:
                out.append({'param': None, 'src': parse_source(item, step_ids, input_keys)})
    return out


def normalize_skill(raw, task=None):
    if not isinstance(raw, str) or not raw.strip():
        return unreadable('empty reply')
    text = raw.strip().lstrip('﻿')
    if re.match(r'(?i)^\s*INFEASIBLE\s*:', text):
        return infeasible(re.sub(r'(?i)^\s*INFEASIBLE\s*:', '', text.splitlines()[0]))
    objs = _objects(text)
    if not objs:
        return unreadable('no JSON plan object in the reply')
    obj = objs[-1]
    feasible = obj.get('feasible')
    reason = _first(obj, ('reason', 'why', 'missing', 'blocked_by', 'gap')) or ''
    if isinstance(reason, (list, dict)):
        reason = json.dumps(reason)
    key = next((k for k in PLAN_KEYS if isinstance(obj.get(k), list)), None)
    steps_raw = obj.get(key) if key else []
    if (feasible is False or str(feasible).strip().lower() in INFEAS):
        return infeasible(reason)
    if not steps_raw:
        return unreadable('feasible but no steps') if feasible else unreadable('no steps')
    complete = not (isinstance(feasible, str) and feasible.strip().lower() in PARTIAL)
    try:
        ids = []
        for i, s in enumerate(steps_raw):
            sid = _first(s, ('id', 'step_id', 'step', 'name'))
            ids.append(str(sid))
        input_keys = set((task or {}).get('inputs', {}))
        steps = []
        for s in steps_raw:
            cap = _first(s, ('capability', 'tool', 'skill', 'uses', 'use'))
            if not isinstance(cap, str):
                return unreadable('step %r has no capability' % s.get('id'))
            crit = _first(s, ('success_criteria', 'criteria', 'acceptance_criteria', 'checks'))
            steps.append({'id': str(_first(s, ('id', 'step_id', 'step', 'name'))), 'capability': cap,
                          'inputs': _inputs(s, set(ids), input_keys),
                          'outputs': [str(x) for x in _as_list(_first(s, ('outputs', 'output'))) if isinstance(x, (str, int))],
                          'depends_on': [str(x) for x in _as_list(_first(s, ('depends_on', 'dependencies', 'after')))],
                          'covers': [str(x) for x in _as_list(_first(s, ('covers', 'deliverables', 'requirements')))],
                          'criteria': [c if isinstance(c, str) else json.dumps(c) for c in _as_list(crit)]})
    except (AttributeError, TypeError) as exc:
        return unreadable('malformed step: %r' % exc)
    final = _first(obj, ('final_step', 'final', 'result_step'))
    if isinstance(final, list):
        final = final[-1] if final else None
    return {'kind': 'plan', 'complete_claim': complete, 'steps': steps,
            'final': str(final) if final is not None else None, 'issues': [], 'reason': str(reason)}


def normalize(arm, raw, task=None, library=None):
    return normalize_cc(raw, task, library) if arm == 'cc' else normalize_skill(raw, task)


# ---------------------------------------------------------------------------------------------
# fairness sampling: print raw skill replies beside what the parser made of them
# ---------------------------------------------------------------------------------------------

def sample(run_dir, n=5, seed=1):
    """python normalize.py sample runs/<label> [n]. Prints n skill replies and their parse for a human."""
    import random
    from pathlib import Path
    root = Path(run_dir)
    items = sorted(root.glob('skill/*/reply.txt'))
    random.Random(seed).shuffle(items)
    tasks = {t['id']: t for t in json.loads((Path(__file__).parent / 'tasks.json').read_text('utf-8'))}
    for p in items[:n]:
        raw = p.read_text('utf-8', 'replace')
        plan = normalize_skill(raw, tasks.get(p.parent.name))
        print('=' * 78, '\n', p.parent.name, '| parsed kind:', plan['kind'], '| steps:',
              [(s['id'], s['capability'], [(i['param'], i['src']) for i in s['inputs']]) for s in plan.get('steps', [])],
              '| reason:', plan.get('reason', '')[:120], '\n--- raw reply (first 1500 chars) ---\n', raw[:1500])


if __name__ == '__main__':
    if len(sys.argv) >= 3 and sys.argv[1] == 'sample':
        sample(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 5)
    else:
        print(__doc__)
