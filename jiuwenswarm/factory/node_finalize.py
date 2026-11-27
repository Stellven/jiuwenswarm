"""Preliminary and final node contracts: the strict check between them.

The planner writes a preliminary node contract: the node's goal, ports, dependencies, the criteria
it must keep, a ceiling on limits and authority, and *slots* the scheduler fills at run time. Just
before the node runs, the scheduler agent proposes the final contract from what it knows then
(accepted upstream outputs, failures so far, the machine's state, which capsules fit). This module
is the control code that admits or refuses that proposal. It never writes a contract.

The rule is strict: a final contract may be more concrete or stricter than its preliminary
contract, never weaker.

* Identity stays: node_id, kind, objective, predecessors, inputs and hands_to are unchanged.
* Every requirement id, output, criterion (verbatim), evidence obligation and verifier stays.
  Criteria, outputs with verifiers and evidence obligations may be added.
* A verifier keeps its capability and stage, and a review is never switched off or made weaker
  (none < advisory < blocking: an advisory review may become blocking, never the reverse). Each pinned
  verifier input stays equal, unless the preliminary contract declares a direction for it in
  ``bounds``: ``inside`` (a [low, high] range may only narrow), ``lower`` (the value may only go
  down) or ``higher`` (only up).
* node_limits never exceed the preliminary values; limits may be added. The authority ceiling's
  effects only shrink and its workspace access only narrows.
* Every slot is filled, within its declared range, and the final contract declares no slots.
* ``work.bound_ccs`` names the capsules the scheduler binds: known capsules, inside
  ``work.eligible_ccs`` when the preliminary contract lists them.

A preliminary contract that cannot be met as written is a matter for the planner (a new plan) or the
contract owner (a spec gap), never for the scheduler to relax.
"""
from __future__ import annotations

import copy
import hashlib
import json

PRELIMINARY, FINAL = 'preliminary', 'final'
IDENTITY = ('node_id', 'kind', 'objective', 'predecessors', 'inputs', 'hands_to')
DIRECTIONS = ('inside', 'lower', 'higher')
WORKSPACE_RANK = {'none': 0, 'read': 1, 'write': 2}
SLOT_KINDS = ('range', 'number', 'integer', 'text', 'ccs', 'criteria')
# A review only gets stricter: none, then advisory (recorded, decides nothing), then blocking (true).
REVIEW_RANK = {False: 0, 'advisory': 1, True: 2}


def is_preliminary(contract_node):
    return (contract_node or {}).get('stage') == PRELIMINARY


def digest(value):
    """sha256 of canonical JSON."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False).encode('utf-8')).hexdigest()


def _by(items, key):
    return {item[key]: item for item in items or []}


def resolve(node, path):
    """Value at a slot/bound path, or a KeyError. Paths:

    ``verifiers.<output>.inputs.<key>``, ``outputs.<output>.criteria``, ``node_limits.<key>``,
    ``work.bound_ccs``, ``work.capability``.
    """
    parts = path.split('.')
    if parts[0] == 'verifiers' and len(parts) == 4 and parts[2] == 'inputs':
        verifier = _by(node.get('verifiers'), 'output').get(parts[1])
        if verifier is None or parts[3] not in (verifier.get('inputs') or {}):
            raise KeyError(path)
        return verifier['inputs'][parts[3]]
    if parts[0] == 'outputs' and len(parts) == 3 and parts[2] == 'criteria':
        output = _by(node.get('outputs'), 'name').get(parts[1])
        if output is None:
            raise KeyError(path)
        return output.get('criteria', [])
    if parts[0] in ('node_limits', 'work') and len(parts) == 2:
        block = node.get(parts[0]) or {}
        if parts[1] not in block:
            raise KeyError(path)
        return block[parts[1]]
    raise KeyError(path)


def path_problems(node, path):
    """Problems with a slot/bound path against a preliminary contract's structure."""
    parts = path.split('.')
    if parts[0] == 'verifiers' and len(parts) == 4 and parts[2] == 'inputs':
        if parts[1] not in _by(node.get('verifiers'), 'output'):
            return [f'{path}: no verifier for output {parts[1]}']
        return []
    if parts[0] == 'outputs' and len(parts) == 3 and parts[2] == 'criteria':
        return [] if parts[1] in _by(node.get('outputs'), 'name') else [f'{path}: no output {parts[1]}']
    if parts[0] == 'node_limits' and len(parts) == 2 and parts[1] in ('time_s', 'turns', 'build_attempts', 'gpu_launches'):
        return []
    if path in ('work.bound_ccs', 'work.capability'):
        return []
    return [f'{path}: not a slot or bound path']


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _range(value):
    return isinstance(value, list) and len(value) == 2 and all(map(_number, value)) and value[0] <= value[1]


def preliminary_problems(node):
    """Structural problems of a preliminary contract's slots and bounds (beyond the schema)."""
    found = []
    ids = [s['id'] for s in node.get('slots', [])]
    if len(set(ids)) != len(ids):
        found.append(f'{node["node_id"]}/slots: slot ids must be unique')
    paths = [s['at'] for s in node.get('slots', [])]
    if len(set(paths)) != len(paths):
        found.append(f'{node["node_id"]}/slots: one slot per path')
    for slot in node.get('slots', []):
        found += [f'{node["node_id"]}/slots/{slot["id"]}: {p}' for p in path_problems(node, slot['at'])]
        within = slot.get('within')
        if within is not None and not _range(within):
            found.append(f'{node["node_id"]}/slots/{slot["id"]}: within must be [low, high]')
        if slot['kind'] == 'ccs' and slot['at'] != 'work.bound_ccs':
            found.append(f'{node["node_id"]}/slots/{slot["id"]}: a ccs slot fills work.bound_ccs')
        if slot['kind'] == 'criteria' and not slot['at'].startswith('outputs.'):
            found.append(f'{node["node_id"]}/slots/{slot["id"]}: a criteria slot fills outputs.<output>.criteria')
    for path, direction in (node.get('bounds') or {}).items():
        found += [f'{node["node_id"]}/bounds: {p}' for p in path_problems(node, path)]
        if not path.startswith('verifiers.'):
            found.append(f'{node["node_id"]}/bounds/{path}: bounds direct pinned verifier inputs only')
        if direction not in DIRECTIONS:
            found.append(f'{node["node_id"]}/bounds/{path}: direction must be one of {", ".join(DIRECTIONS)}')
    if node.get('stage') == FINAL and (node.get('slots') or node.get('bounds')):
        found.append(f'{node["node_id"]}: a final contract declares no slots or bounds')
    return found


def _slot_value_problems(slot, value, prelim):
    kind, name, within = slot['kind'], slot['id'], slot.get('within')
    if kind == 'range':
        if not _range(value):
            return [f'slot {name}: needs a [low, high] range of numbers']
        if within and (value[0] < within[0] or value[1] > within[1]):
            return [f'slot {name}: {value} is outside the allowed {within}']
    elif kind in ('number', 'integer'):
        if not _number(value) or (kind == 'integer' and not isinstance(value, int)):
            return [f'slot {name}: needs {"an integer" if kind == "integer" else "a number"}']
        if within and not within[0] <= value <= within[1]:
            return [f'slot {name}: {value} is outside the allowed {within}']
    elif kind == 'text':
        if not isinstance(value, str) or not value.strip():
            return [f'slot {name}: needs nonempty text']
    elif kind == 'ccs':
        if not isinstance(value, list) or not value:
            return [f'slot {name}: needs at least one bound capsule']
    elif kind == 'criteria':
        try:
            before = resolve(prelim, slot['at'])
        except KeyError:
            before = []
        if not isinstance(value, list) or len(value) <= len(before):
            return [f'slot {name}: add at least one concrete criterion to {slot["at"]}']
    return []


def _direction_problems(path, direction, before, after):
    if direction == 'inside':
        if not (_range(before) and _range(after)):
            return [f'{path}: an inside bound needs [low, high] ranges']
        if after[0] < before[0] or after[1] > before[1]:
            return [f'{path}: {after} widens {before}; a range may only narrow']
    elif direction == 'lower':
        if not (_number(before) and _number(after)) or after > before:
            return [f'{path}: {after} is above {before}; it may only go down']
    elif direction == 'higher':
        if not (_number(before) and _number(after)) or after < before:
            return [f'{path}: {after} is below {before}; it may only go up']
    return []


def check_final(prelim, final, *, known_ccs=None):
    """Every reason the proposed final contract may not replace the preliminary one; empty to admit."""
    found = []
    if not is_preliminary(prelim):
        return ['the node contract is not preliminary; it needs no finalization']
    if not isinstance(final, dict):
        return ['the final contract must be an object']
    if final.get('stage') != FINAL:
        found.append('the final contract must say stage: final')
    if final.get('slots') or final.get('bounds'):
        found.append('a final contract declares no slots or bounds')
    for field in IDENTITY:
        if final.get(field) != prelim.get(field):
            found.append(f'{field} must stay as the preliminary contract has it')
    missing = set(prelim.get('requirement_ids', [])) - set(final.get('requirement_ids', []))
    if missing:
        found.append('requirement ids dropped: ' + ', '.join(sorted(missing)))
    missing = set(prelim.get('evidence_obligations', [])) - set(final.get('evidence_obligations', []))
    if missing:
        found.append('evidence obligations dropped: ' + ', '.join(sorted(missing)))
    slots = {s['at']: s for s in prelim.get('slots', [])}
    bounds = prelim.get('bounds') or {}

    before_outputs, after_outputs = _by(prelim.get('outputs'), 'name'), _by(final.get('outputs'), 'name')
    for name, output in before_outputs.items():
        after = after_outputs.get(name)
        if after is None:
            found.append(f'output {name} dropped')
            continue
        if after.get('kind') != output.get('kind'):
            found.append(f'output {name}: kind must stay {output.get("kind")}')
        if output.get('required', True) and not after.get('required', True):
            found.append(f'output {name}: a required output stays required')
        lost = [c for c in output.get('criteria', []) if c not in after.get('criteria', [])]
        if lost:
            found.append(f'output {name}: criteria must be kept word for word; missing: ' + ' | '.join(lost))

    before_verifiers, after_verifiers = _by(prelim.get('verifiers'), 'output'), _by(final.get('verifiers'), 'output')
    for name, verifier in before_verifiers.items():
        after = after_verifiers.get(name)
        if after is None:
            found.append(f'verifier for {name} dropped')
            continue
        for field in ('verifier', 'stage', 'seal'):
            if verifier.get(field) and after.get(field) != verifier.get(field):
                found.append(f'verifier for {name}: {field} must stay {verifier[field]}')
        if REVIEW_RANK.get(after.get('review', False), -1) < REVIEW_RANK.get(verifier.get('review', False), 0):
            found.append(f'verifier for {name}: the review stays on' if not after.get('review') else
                         f'verifier for {name}: the review stays blocking (true); advisory would be weaker')
        before_inputs, after_inputs = verifier.get('inputs') or {}, after.get('inputs') or {}
        for key, value in before_inputs.items():
            path = f'verifiers.{name}.inputs.{key}'
            if key not in after_inputs:
                found.append(f'{path}: pinned input dropped')
            elif path in bounds:
                found += _direction_problems(path, bounds[path], value, after_inputs[key])
            elif after_inputs[key] != value:
                found.append(f'{path}: pinned input must stay {json.dumps(value)} (no direction declared)')
        for key in sorted(set(after_inputs) - set(before_inputs)):
            path = f'verifiers.{name}.inputs.{key}'
            if path not in slots:  # an unknown parameter could loosen the verifier's own default
                found.append(f'{path}: new verifier inputs come only through a slot')

    before_limits, after_limits = prelim.get('node_limits') or {}, final.get('node_limits') or {}
    for key, value in before_limits.items():
        if key not in after_limits:
            found.append(f'node_limits.{key}: dropped (a ceiling stays)')
        elif after_limits[key] > value:
            found.append(f'node_limits.{key}: {after_limits[key]} exceeds the ceiling {value}')

    before_ceiling, after_ceiling = prelim.get('authority_ceiling') or {}, final.get('authority_ceiling') or {}
    if 'effects' in before_ceiling:
        extra = set(after_ceiling.get('effects', before_ceiling['effects'])) - set(before_ceiling['effects'])
        if 'effects' not in after_ceiling:
            found.append('authority_ceiling.effects: must be stated')
        elif extra:
            found.append('authority_ceiling.effects: adds ' + ', '.join(sorted(extra)))
    if 'workspace' in before_ceiling:
        after_ws = after_ceiling.get('workspace')
        if after_ws is None or WORKSPACE_RANK[after_ws] > WORKSPACE_RANK[before_ceiling['workspace']]:
            found.append(f'authority_ceiling.workspace: may not be wider than {before_ceiling["workspace"]}')

    before_work, after_work = prelim.get('work') or {}, final.get('work') or {}
    if before_work.get('capability') and 'work.capability' not in slots and after_work.get('capability') != before_work['capability']:
        found.append(f'work.capability must stay {before_work["capability"]}')
    bound = after_work.get('bound_ccs')
    if not isinstance(bound, list) or not bound:
        found.append('work.bound_ccs: the final contract binds at least one capsule')
    else:
        eligible = before_work.get('eligible_ccs')
        if eligible:
            outside = [c for c in bound if c not in eligible]
            if outside:
                found.append('work.bound_ccs outside work.eligible_ccs: ' + ', '.join(outside))
        if known_ccs is not None:
            unknown = [c for c in bound if c not in known_ccs]
            if unknown:
                found.append('work.bound_ccs names unknown capsules: ' + ', '.join(unknown))
    if after_work.get('eligible_ccs') not in (None, before_work.get('eligible_ccs')):
        found.append('work.eligible_ccs stays as the planner set it')

    for path, slot in slots.items():
        try:
            value = resolve(final, path)
        except KeyError:
            found.append(f'slot {slot["id"]}: {path} is not filled')
            continue
        found += _slot_value_problems(slot, value, prelim)
    return found


def diff(before, after, path=''):
    """Flat list of changes between two JSON values: {path, before, after}."""
    if isinstance(before, dict) and isinstance(after, dict):
        changes = []
        for key in sorted(set(before) | set(after)):
            sub = f'{path}.{key}' if path else key
            if key not in before:
                changes.append(dict(path=sub, before=None, after=after[key]))
            elif key not in after:
                changes.append(dict(path=sub, before=before[key], after=None))
            else:
                changes += diff(before[key], after[key], sub)
        return changes
    if isinstance(before, list) and isinstance(after, list) and before and after \
            and all(isinstance(x, dict) for x in before + after):
        key = next((k for k in ('output', 'name', 'id') if all(k in x for x in before + after)), None)
        if key:
            return diff({x[key]: x for x in before}, {x[key]: x for x in after}, path)
    return [] if before == after else [dict(path=path, before=before, after=after)]


def draft_final(prelim):
    """A starting point for the scheduler: the preliminary contract as a final one with empty slots."""
    final = copy.deepcopy(prelim)
    final['stage'] = FINAL
    final.pop('slots', None)
    final.pop('bounds', None)
    return final
