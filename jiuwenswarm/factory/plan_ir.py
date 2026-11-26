"""Plan IR (``factory.plan-ir/1``): autonomous step topology & CC Library bindings.

The host enumerates eligible capsules, features, hardware risks, interference and merge
options (``plan_select.context``) alongside the full CC Library declaration view; the model
autonomously chooses cohesive capsules and designs its own TaskGraph ``steps`` (id, kind,
objective, depends_on, capsules, optional limits/criteria/outputs).
``plan_compile`` deterministically derives ports, verifiers, authority ceilings, limits
and the execution graph for static checks and internal TLC formal verification.

    {"format": "factory.plan-ir/1",
     "selected_capsules": [{"capsule": "engine.build_expert_weight_cache", "why": "..."}],
     "units":     [{"id": "cache", "capsules": ["engine.build_expert_weight_cache"]}],  # optional
     "preflight": [{"unit": "cache", "add": true, "why": "..."}],                       # required per F1 risk
     "merge":     {"option": "M1" | "M2" | "M3", "why": "..."},                         # required iff >=2 diff units
     "priority":  [["predictor", "cache"]],                                             # optional ordering
     "steps": [
       {"id": "inspect_engine", "kind": "inspect", "objective": "...",
        "depends_on": [], "capsules": ["factory.source_workbench"]},
       ...
       {"id": "deliver_to_lab", "kind": "deliver", "objective": "...",
        "depends_on": ["build_candidate"], "capsules": ["factory.lab_manager"]}
     ],
     "criteria":  {"integrate_cache": ["..."]},                                         # optional extra criteria
     "limits":    {"integrate_cache": {"turns": 30}}}                                   # optional, tighten only

Or, when no eligible capsule can satisfy the task:

    {"format": "factory.plan-ir/1", "unrealizable": {"why": "..."}}
"""
from __future__ import annotations

import re

from . import plan_catalog

FORMAT = 'factory.plan-ir/1'
FIELDS = {
    'format', 'steps', 'selected_capsules', 'unrealizable', 'units',
    'preflight', 'merge', 'priority', 'criteria', 'limits',
}
STEP_KINDS = {
    'inspect', 'investigate', 'integrate', 'merge', 'build',
    'measure', 'decide', 'tune', 'accept', 'report', 'deliver',
}
STEP_FIELDS = {'id', 'kind', 'objective', 'depends_on', 'capsules', 'limits', 'criteria', 'outputs', 'workspace'}
OUTPUT_KINDS = {'diff', 'source_bundle', 'image', 'lab_request', 'evidence'}
ID = re.compile(r'^[a-z][a-z0-9_]{0,31}$')
UNIT_ID = re.compile(r'^[a-z][a-z0-9_]{0,19}$')
TEXT = 600


def _text(value):
    return isinstance(value, str) and value.strip() and len(value) <= TEXT


def units_of(ir, selection):
    """{unit id: {'capsules': [...], 'diff_capsules': [...], 'tool_capsules': [...]}}."""
    from .plan_select import unit_name
    by_cap = {c['capsule']: c for c in selection['candidates']}
    selected = [item['capsule'] for item in ir.get('selected_capsules', []) if isinstance(item, dict)]

    def build_entry(caps):
        return dict(
            capsules=list(caps),
            diff_capsules=[c for c in caps if by_cap.get(c, {}).get('kind') == 'builder'],
            tool_capsules=[c for c in caps if by_cap.get(c, {}).get('kind') != 'builder'],
        )

    if ir.get('units'):
        return {u['id']: build_entry(u['capsules'])
                for u in ir['units'] if isinstance(u, dict) and isinstance(u.get('capsules'), list)}
    return {unit_name(cap): build_entry([cap]) for cap in selected}


def diff_units(units):
    """Unit ids whose capsules produce code diffs."""
    return sorted(u for u, spec in units.items() if spec['diff_capsules'])


def options_for(units, selection):
    from .plan_select import interference, merge_options, unit_components
    diffs = diff_units(units)
    components = unit_components({u: units[u] for u in diffs})
    return merge_options(diffs, interference(components))


def toposort_steps(steps):
    """Order steps by ``depends_on`` (ties by declaration order); returns (ordered, cycle_problems)."""
    by_id = {s['id']: s for s in steps}
    pending = {s['id']: set(s.get('depends_on') or []) for s in steps}
    done, ordered = set(), []
    while pending:
        ready = [s['id'] for s in steps if s['id'] in pending and pending[s['id']] <= done]
        if not ready:
            return [], ['steps contain a dependency cycle: ' + ', '.join(sorted(pending))]
        for sid in ready:
            ordered.append(by_id[sid])
            done.add(sid)
            del pending[sid]
    return ordered, []


def _validate_step_limits(key, limits, found):
    if not isinstance(limits, dict) or set(limits) - {'turns', 'build_attempts', 'time_s'} \
            or not all(type(v) is int and v >= 0 for v in limits.values()):
        found.append(f'limits/{key}: only turns, build_attempts and time_s, as non-negative integers')


def _validate_steps(steps_raw, catalog_capsules, selected, found):
    if not isinstance(steps_raw, list) or not (1 <= len(steps_raw) <= 32):
        found.append('steps must be a non-empty list of 1..32 step objects')
        return
    step_ids = []
    seen_ids = set()
    valid_steps = []
    for idx, step in enumerate(steps_raw):
        if not isinstance(step, dict):
            found.append(f'steps[{idx}]: each step must be a JSON object')
            continue
        unknown = set(step) - STEP_FIELDS
        if unknown:
            found.append(f'steps[{idx}]: unknown field(s) {sorted(unknown)}')
        sid = step.get('id')
        if not isinstance(sid, str) or not ID.fullmatch(sid):
            found.append(f'steps[{idx}]/id: must match {ID.pattern}')
            continue
        if sid in seen_ids:
            found.append(f'steps/{sid}: duplicate step id')
            continue
        seen_ids.add(sid)
        step_ids.append(sid)
        kind = step.get('kind')
        if kind not in STEP_KINDS:
            found.append(f'steps/{sid}/kind: {kind!r} not in {sorted(STEP_KINDS)}')
        if not _text(step.get('objective')):
            found.append(f'steps/{sid}/objective: non-empty summary of at most {TEXT} chars required')
        deps = step.get('depends_on')
        if not isinstance(deps, list) or not all(isinstance(d, str) for d in deps):
            found.append(f'steps/{sid}/depends_on: must be a list of step ids')
        caps = step.get('capsules')
        if not isinstance(caps, list) or not all(isinstance(c, str) for c in caps):
            found.append(f'steps/{sid}/capsules: must be a list of CC Library capsule ids')
        else:
            for cid in caps:
                if cid not in catalog_capsules:
                    found.append(f'steps/{sid}/capsules: unknown CC Library capsule {cid!r}')
        if 'limits' in step:
            _validate_step_limits(sid, step['limits'], found)
        if 'criteria' in step:
            crit = step['criteria']
            if not isinstance(crit, list) or not all(_text(c) for c in crit):
                found.append(f'steps/{sid}/criteria: must be a list of short sentences')
        if 'outputs' in step:
            outs = step['outputs']
            if not isinstance(outs, list) or not outs:
                found.append(f'steps/{sid}/outputs: must be a non-empty list of {{name, kind}} objects')
            else:
                for o in outs:
                    oname = (o or {}).get('name') or (o or {}).get('port') if isinstance(o, dict) else None
                    okind = (o or {}).get('kind') if isinstance(o, dict) else None
                    if not isinstance(oname, str) or not ID.fullmatch(oname) or okind not in OUTPUT_KINDS:
                        found.append(f'steps/{sid}/outputs: invalid output spec {o!r}')
        if 'workspace' in step and step['workspace'] not in {'none', 'read', 'write'}:
            found.append(f'steps/{sid}/workspace: must be none, read, or write')
        valid_steps.append(step)

    if len(valid_steps) != len(steps_raw):
        return

    for step in valid_steps:
        sid = step['id']
        for dep in step['depends_on']:
            if dep == sid:
                found.append(f'steps/{sid}/depends_on: step cannot depend on itself')
            elif dep not in seen_ids:
                found.append(f'steps/{sid}/depends_on: unknown step {dep!r}')

    if not any('depends_on' in p or 'cycle' in p for p in found):
        _, cyc = toposort_steps(valid_steps)
        found.extend(cyc)

    delivers = [s for s in valid_steps if s.get('kind') == 'deliver']
    if len(delivers) != 1:
        found.append('steps: must contain exactly one deliver step')
    else:
        did = delivers[0]['id']
        if any(did in (s.get('depends_on') or []) for s in valid_steps):
            found.append(f'steps/{did}: deliver step must be the terminal leaf with no downstream steps')

    bound_caps = {c for s in valid_steps for c in (s.get('capsules') or [])}
    missing_selected = [c for c in selected if c not in bound_caps]
    if missing_selected:
        found.append(f'steps: selected_capsules {missing_selected} are not bound to any step')


def problems(ir, selection, catalog=None):
    """Every way the decisions leave the offered options or step rules; empty when valid."""
    if not isinstance(ir, dict) or ir.get('format') != FORMAT:
        return [f'the reply must be one JSON object with "format": "{FORMAT}"']
    found = [f'unknown field {k}' for k in sorted(set(ir) - FIELDS)]
    if 'unrealizable' in ir:
        unr = ir['unrealizable']
        if not isinstance(unr, dict) or set(unr) != {'why'} or not _text(unr.get('why')):
            found.append('unrealizable must be {"why": "..."}')
        if ir.get('selected_capsules'):
            found.append('unrealizable cannot be combined with selected_capsules')
        return found

    offered = {c['capsule']: c for c in selection['candidates']}
    selected_list = ir.get('selected_capsules')
    if not isinstance(selected_list, list) or not selected_list:
        return found + ['selected_capsules must list at least one {"capsule", "why"} from selection.candidates']

    selected = []
    seen = set()
    for item in selected_list:
        if not isinstance(item, dict) or set(item) != {'capsule', 'why'} or not _text(item.get('why')):
            found.append(f'selected_capsules {item!r}: needs exactly capsule and a why of at most {TEXT} characters')
            continue
        cap = item['capsule']
        if cap in seen:
            found.append(f'selected_capsules: {cap} is listed twice')
            continue
        if cap not in offered:
            found.append(f'selected_capsules: {cap} is not among offered candidates {sorted(offered)}')
            continue
        seen.add(cap)
        selected.append(cap)

    for pinned in selection.get('must_include') or []:
        if pinned not in seen:
            found.append(f'selected_capsules: required capsule {pinned} must be selected')
    if found:
        return found

    slices = {c['capsule']: set(c['features']['slices']) for c in selection['candidates']}
    if 'units' in ir:
        units_raw = ir['units']
        grouped = [c for u in units_raw if isinstance(u, dict) for c in u.get('capsules', [])] if isinstance(units_raw, list) else []
        if not isinstance(units_raw, list) or sorted(grouped) != sorted(selected):
            return ['units must place every selected capsule in exactly one unit']
        for unit in units_raw:
            if set(unit) != {'id', 'capsules'} or not isinstance(unit['id'], str) or not UNIT_ID.fullmatch(unit['id']):
                found.append(f'unit {unit!r}: needs an id matching {UNIT_ID.pattern} and capsules')
                continue
            caps = unit['capsules']
            if not caps or len(caps) > 2:
                found.append(f'unit {unit["id"]}: 1 or at most 2 capsules may share one integration step')
            if len(caps) == 2:
                a, b = caps
                if offered[a]['kind'] != 'builder' or offered[b]['kind'] != 'builder':
                    found.append(f'unit {unit["id"]}: tool capsules cannot share a unit with another capsule')
                elif not (slices[a] & slices[b]):
                    found.append(f'unit {unit["id"]}: {a} and {b} share no ontology slice, so they integrate separately')
        if len({u.get('id') for u in units_raw if isinstance(u, dict)}) != len(units_raw):
            found.append('unit ids must be unique')
        if found:
            return found

    units = units_of(ir, selection)
    risky_caps = {r['capsule'] for r in selection['risks']}
    risky_units = {u for u, spec in units.items() if set(spec['capsules']) & risky_caps}
    decided = {}
    pf = ir.get('preflight', [])
    if not isinstance(pf, list):
        found.append('preflight must be a list of {unit, add, why}')
    else:
        for item in pf:
            if not isinstance(item, dict) or set(item) != {'unit', 'add', 'why'} or not isinstance(item.get('add'), bool) \
                    or not _text(item.get('why')) or item.get('unit') not in units:
                found.append(f'preflight {item!r}: needs unit (one of {sorted(units)}), add (true/false) and why')
                continue
            decided[item['unit']] = item['add']
    for unit in sorted(risky_units - set(decided)):
        found.append(f'preflight {unit}: decide whether to add a preflight step for its hardware risk, and why')

    diffs = diff_units(units)
    if len(diffs) >= 2:
        merge = ir.get('merge')
        offered_merges = options_for(units, selection)
        if not isinstance(merge, dict) or set(merge) != {'option', 'why'} or not _text(merge.get('why')):
            found.append('merge must be {"option": ..., "why": ...}')
        elif merge['option'] not in offered_merges:
            found.append(f'merge option {merge["option"]} is not offered for these units; '
                         f'offered: {sorted(offered_merges)}')
    elif 'merge' in ir:
        found.append('merge: fewer than two code-diff units are selected, so there is nothing to merge')

    prio = ir.get('priority', [])
    if not isinstance(prio, list):
        found.append('priority must be a list of [unit_a, unit_b] pairs')
    else:
        for pair in prio:
            if not (isinstance(pair, list) and len(pair) == 2 and all(p in units for p in pair) and pair[0] != pair[1]):
                found.append(f'priority {pair!r}: must be [unit, unit] with two different units of {sorted(units)}')

    for key, items in (ir.get('criteria') or {}).items():
        if not isinstance(items, list) or not all(_text(i) for i in items):
            found.append(f'criteria/{key}: a list of sentences of at most {TEXT} characters')
    for key, limits in (ir.get('limits') or {}).items():
        _validate_step_limits(key, limits, found)

    catalog_capsules = (catalog or plan_catalog.load())['capsules']
    steps_raw = ir.get('steps')
    _validate_steps(steps_raw, catalog_capsules, selected, found)
    if not found and isinstance(steps_raw, list):
        # Cross-check preflight add=true decisions against declared steps
        for unit, add in decided.items():
            if not add:
                continue
            unit_caps = set(units[unit]['capsules'])
            has_preflight = any(
                s['kind'] in {'inspect', 'investigate'}
                and s['depends_on']
                and (s['id'] == f'preflight_{unit}' or bool(unit_caps & set(s['capsules'])))
                for s in steps_raw
            )
            if not has_preflight:
                found.append(
                    f'preflight/{unit}: add=true requires an applicability inspect/investigate step (e.g. preflight_{unit}) in steps'
                )
        # Cross-check multi-diff merge step presence
        if len(diffs) >= 2 and isinstance(ir.get('merge'), dict):
            has_merge_step = any(s['kind'] == 'merge' or s['id'] in {'combine', 'merge_1'} for s in steps_raw)
            if not has_merge_step:
                found.append('steps: >=2 diff units require merge step(s) (e.g. kind="merge" / id="combine") before build')
    return found
