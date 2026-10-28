"""Fixed deterministic plan executor and referee comparison. No model, no network, no Docker.

Input: a plan in the neutral form (normalize.py) and the task record (tasks.json).
It binds every step from the supplied inputs or from named earlier steps, runs the
real deterministic capability body, and reports every binding fault by class.

Neutral plan form (what normalize.py emits)::

    {"kind": "plan", "complete_claim": true,
     "steps": [{"id": "s1", "capability": "utility.table_normalize",
                "inputs": [{"param": "packet", "src": {"external": "sales"}}],
                "outputs": ["result"], "depends_on": [], "covers": ["D1"],
                "criteria": ["data.table is present"]}],
     "final": "s2", "issues": []}

``src`` is one of {"external": key}, {"step": id, "output": name|null}, {"unresolved": raw}.

Error classes (fatal = the plan cannot run end to end):
  fabricated_capability, non_executable_capability, fabricated_input, missing_source,
  type_mismatch, unbound_required_input, unknown_parameter, cycle, duplicate_step,
  body_rejected                                   (fatal)
  name_alias, param_alias, output_name_alias, undeclared_dependency, unknown_dependency,
  unused_step, multiple_sinks, bad_final, wrong_input_choice   (not fatal; recorded)
"""
import sys
sys.dont_write_bytecode = True
import copy
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import caps

FATAL = {'fabricated_capability', 'non_executable_capability', 'fabricated_input', 'missing_source',
         'type_mismatch', 'unbound_required_input', 'unknown_parameter', 'cycle', 'duplicate_step',
         'body_rejected'}
STOP = {'result', 'results', 'data', 'value', 'values', 'output', 'outputs', 'input', 'inputs', 'step',
        'file', 'files', 'text', 'path', 'check', 'checks', 'the', 'and', 'with', 'from', 'that', 'this'}


def _err(res, cls, step, detail):
    res['errors'].append({'class': cls, 'step': step, 'detail': str(detail)[:300], 'fatal': cls in FATAL})


def _canon(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


def execute(plan, task, decoys=(), checks=None):
    """Run a neutral plan. Returns a result dict; never raises on a bad plan."""
    res = {'executed': False, 'errors': [], 'outputs': {}, 'ran': [], 'final': None, 'order': [],
           'criteria': {'total': 0, 'path_checkable': 0, 'check_id': 0, 'checkable': 0, 'steps_without': 0}}
    if plan.get('kind') != 'plan':
        _err(res, 'unreadable', None, plan.get('reason', ''))
        return res
    steps = plan.get('steps') or []
    if not steps:
        _err(res, 'missing_source', None, 'plan has no steps')
        return res
    byid, canon = {}, {}
    for s in steps:
        if s['id'] in byid:
            _err(res, 'duplicate_step', s['id'], 'duplicate step id')
        byid[s['id']] = s
    # 1. capability resolution
    for s in steps:
        name, how = caps.resolve(s.get('capability'))
        if name is None:
            _err(res, 'fabricated_capability', s['id'], s.get('capability'))
            continue
        if how == 'alias':
            _err(res, 'name_alias', s['id'], '%s -> %s' % (s.get('capability'), name))
        if caps.body(name) is None:
            _err(res, 'non_executable_capability', s['id'], name)
            continue
        canon[s['id']] = name
    # 2. bindings (static)
    bound = {}      # step id -> parameter value descriptor
    for s in steps:
        sid = s['id']
        given = s.get('inputs') or []
        if sid not in canon:
            # unknown or non-executable capability: its sources are still checked for invented references
            for g in given:
                src = g['src']
                if 'external' in src and src['external'] not in task['inputs']:
                    _err(res, 'fabricated_input', sid, src['external'])
                elif 'step' in src and src['step'] not in byid:
                    _err(res, 'missing_source', sid, 'no step %r' % src['step'])
            continue
        _, pname, pkind = caps.PARAM[canon[sid]]
        pick = None
        for g in given:
            if g['param'] == pname:
                pick = g
        if pick is None and len(given) == 1:
            pick = given[0]
            _err(res, 'param_alias', sid, '%s -> %s' % (pick['param'], pname))
        elif pick is None:
            _err(res, 'unbound_required_input' if not given else 'unknown_parameter', sid,
                 'needs %s; given %s' % (pname, [g['param'] for g in given]))
            continue
        extra = [g['param'] for g in given if g is not pick]
        if extra:
            _err(res, 'unknown_parameter', sid, 'unexpected inputs %s' % extra)
        src = pick['src']
        if 'external' in src:
            key = src['external']
            inp = task['inputs'].get(key)
            if inp is None:
                _err(res, 'fabricated_input', sid, key)
                continue
            if key in decoys:
                _err(res, 'wrong_input_choice', sid, key)
            kind = caps.KIND_OF_TYPE.get(inp['artifact_type'], 'other')
            if kind != pkind:
                _err(res, 'type_mismatch', sid, '%s is a %s, capability takes a %s' % (key, kind, pkind))
                continue
            bound[sid] = ('external', key)
        elif 'step' in src:
            prev = src['step']
            if prev not in byid:
                _err(res, 'missing_source', sid, 'no step %r' % prev)
                continue
            if prev == sid:
                _err(res, 'cycle', sid, 'step feeds itself')
                continue
            if src.get('output') not in (None, caps.OUTPUT):
                _err(res, 'output_name_alias', sid, '%s.%s' % (prev, src['output']))
            if prev in canon and caps.OUTPUT_KIND != pkind:
                _err(res, 'type_mismatch', sid, 'output of %s is a %s, capability takes a %s' % (prev, caps.OUTPUT_KIND, pkind))
                continue
            bound[sid] = ('step', prev)
        else:
            _err(res, 'missing_source', sid, src.get('unresolved'))
    # 3. order (dependencies come from the bindings, not from the declared depends_on)
    deps = {s['id']: set() for s in steps}
    for sid, b in bound.items():
        if b[0] == 'step':
            deps[sid] = {b[1]}
    for s in steps:                      # a step that cannot be bound still orders its dependents
        for g in (s.get('inputs') or []):
            if 'step' in g['src'] and g['src']['step'] in byid and s['id'] not in bound:
                deps[s['id']].add(g['src']['step'])
    for s in steps:
        declared = set(s.get('depends_on') or [])
        for d in declared - set(byid):
            _err(res, 'unknown_dependency', s['id'], d)
        actual = deps.get(s['id'], set())
        if actual - declared:
            _err(res, 'undeclared_dependency', s['id'], sorted(actual - declared))
    order, remaining = [], {k: set(v) for k, v in deps.items()}
    while remaining:
        ready = [k for k, v in remaining.items() if not (v - set(order))]
        if not ready:
            _err(res, 'cycle', None, sorted(remaining))
            break
        for k in ready:
            order.append(k)
            remaining.pop(k)
    res['order'] = order
    # final step
    sinks = [s['id'] for s in steps if not any(b == ('step', s['id']) for b in bound.values())]
    final = plan.get('final')
    if final is not None and final not in byid:
        _err(res, 'bad_final', None, final)
        final = None
    if final is None:
        if len(sinks) == 1:
            final = sinks[0]
        elif sinks:
            final = [s['id'] for s in steps if s['id'] in sinks][-1]
            _err(res, 'multiple_sinks', None, sinks)
    res['final'] = final
    # 4. run
    values = {}
    for sid in order:
        if sid not in bound:
            continue                          # could not be bound (reported above)
        kind, ref = bound[sid]
        if kind == 'step':
            if ref not in values:
                continue                      # a producer failed; this step cannot run
            arg = values[ref]
        else:
            arg = copy.deepcopy(task['inputs'][ref]['content'])
        try:
            values[sid] = caps.body(canon[sid])(arg)
            res['ran'].append(sid)
        except Exception as exc:              # the body rejected its input: a real precondition fault
            _err(res, 'body_rejected', sid, '%s: %s' % (type(exc).__name__, exc))
    res['outputs'] = values
    if final is not None:
        anc, todo = set(), [final]
        while todo:
            x = todo.pop()
            if x in anc:
                continue
            anc.add(x)
            todo += list(deps.get(x, ()))
        for s in steps:
            if s['id'] not in anc:
                _err(res, 'unused_step', s['id'], 'not used by the final step')
    res['executed'] = (not any(e['fatal'] for e in res['errors']) and final in values
                       and len(res['ran']) == len(steps))
    # 5. acceptance criteria (machine-checkable = a deterministic checker can decide it)
    for s in steps:
        crit = s.get('criteria') or []
        if not crit:
            res['criteria']['steps_without'] += 1
        out = values.get(s['id'])
        ids = (checks or {}).get(canon.get(s['id']), [])
        keys = _key_paths(out) if out is not None else set()
        for c in crit:
            res['criteria']['total'] += 1
            toks = re.findall(r'[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*', c if isinstance(c, str) else json.dumps(c))
            by_path = any(t.lower() not in STOP and len(t) >= 5 and _suffix_ok(t, keys) for t in toks)
            by_id = any(t in ids for t in toks)
            res['criteria']['path_checkable'] += int(by_path)
            res['criteria']['check_id'] += int(by_id)
            res['criteria']['checkable'] += int(by_path or by_id)
    return res


def _key_paths(value, prefix=''):
    out = set()
    if isinstance(value, dict):
        for k, v in value.items():
            p = prefix + '.' + k if prefix else k
            out.add(p)
            out |= _key_paths(v, p)
    return out


def _suffix_ok(token, keys):
    """A dotted token resolves if it is a suffix of some real key path."""
    return any(k == token or k.endswith('.' + token) for k in keys)


# ---------- referee comparison --------------------------------------------------------------

def _walk(packet, locator):
    cur = packet
    for part in locator:
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return False, None
    return True, cur


def deliverable_ok(d, packet):
    if packet is None:
        return False
    if d['kind'] == 'value':
        found, value = _walk(packet, d['locator'])
        return found and _canon(value) == _canon(d['expected'])
    if d['kind'] == 'file':
        for f in packet.get('files', []):
            if f['path'] == d['path']:
                return hashlib.sha256(f['text'].encode('utf-8')).hexdigest() == d['sha256']
        return False
    raise ValueError(d['kind'])


def evaluate(plan, res, gold):
    """Compare the executed plan with the referee. A plan that did not execute earns nothing."""
    out = {'final_correct': False, 'deliverables': {}}
    final_packet = res['outputs'].get(res['final']) if res['executed'] else None
    for d in gold['deliverables']:
        ok = deliverable_ok(d, final_packet)
        covering = [s['id'] for s in plan.get('steps', []) if d['id'] in (s.get('covers') or [])]
        traced = bool(res['executed']) and any(deliverable_ok(d, res['outputs'].get(sid)) for sid in covering)
        out['deliverables'][d['id']] = {'correct': ok, 'traced': traced, 'covered_by': covering}
    out['final_correct'] = bool(res['executed']) and all(v['correct'] for v in out['deliverables'].values())
    return out
