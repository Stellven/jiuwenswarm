"""Node contracts: what each step of building an inference engine takes, produces and must pass.

A task contract (format 2) can carry its node contracts under
``extensions["factory.node-contracts"]`` (schema ``schemas/node-contract-1.schema.json``).
Field names follow the M1 Node Execution Contract where the meaning is the same.

Where node contracts sit in the pipeline::

    contract (with node contracts) -> planner (orders them into a task graph)
      -> factory: scheduler + capsules + a verifier per output, node by node
      -> lab manager (the deliver node's lab request) -> lab agent

This module only reads and checks them. ``planner.py`` turns them into a task graph,
``scheduler.py`` says which can run, ``node_check.py`` verifies their outputs.
"""
from __future__ import annotations

import json
from pathlib import Path

EXTENSION = 'factory.node-contracts'
FORMAT = 'factory.node-contracts/1'
SCHEMA = Path(__file__).with_name('schemas') / 'node-contract-1.schema.json'
_validator = None


def _schema_problems(document):
    global _validator
    if _validator is None:
        import jsonschema
        _validator = jsonschema.Draft202012Validator(json.loads(SCHEMA.read_text(encoding='utf-8')))
    return [f"{'/'.join(map(str, e.absolute_path)) or '(document)'}: {e.message}"
            for e in sorted(_validator.iter_errors(document), key=lambda e: list(e.absolute_path))]


def order(nodes):
    """Kahn order (ties by declaration order); raises on a cycle or a missing predecessor."""
    by_id = {n['node_id']: n for n in nodes}
    pending = {n['node_id']: set(n.get('predecessors', [])) for n in nodes}
    for key, deps in pending.items():
        missing = deps - set(by_id)
        if missing:
            raise ValueError(f'{key}: unknown predecessors {sorted(missing)}')
    done, result = set(), []
    while pending:
        ready = [n['node_id'] for n in nodes if n['node_id'] in pending and pending[n['node_id']] <= done]
        if not ready:
            raise ValueError('node contracts form a cycle: ' + ', '.join(sorted(pending)))
        for key in ready:
            result.append(key)
            done.add(key)
            del pending[key]
    return result


def problems(document, contract=None):
    """Schema and graph problems of a node-contracts document; empty when valid."""
    found = _schema_problems(document)
    if found:
        return found
    nodes = document['nodes']
    ids = [n['node_id'] for n in nodes]
    if len(set(ids)) != len(ids):
        return ['nodes: node_id values must be unique']
    by_id = {n['node_id']: n for n in nodes}
    try:
        order(nodes)
    except ValueError as exc:
        found.append(str(exc))
    contract_inputs = set((contract or {}).get('inputs') or {})
    known_requirements = set()
    if contract:
        from .contract_v2 import arm_ids, check_ids, metric_ids
        known_requirements = set(arm_ids(contract)) | set(check_ids(contract)) | set(metric_ids(contract))
    from .node_finalize import preliminary_problems
    for node in nodes:
        found += preliminary_problems(node)
        key = node['node_id']
        outputs = [o['name'] for o in node['outputs']]
        if len(set(outputs)) != len(outputs):
            found.append(f'{key}: output names must be unique')
        names = [i['name'] for i in node.get('inputs', [])]
        if len(set(names)) != len(names):
            found.append(f'{key}: input names must be unique')
        for item in node.get('inputs', []):
            source = item['from']
            if source.startswith('contract:'):
                if contract is not None and source[9:] not in contract_inputs:
                    found.append(f'{key}/inputs/{item["name"]}: the contract has no input {source[9:]}')
            elif not source.startswith('task:'):
                producer, _, port = source.partition('.')
                if producer not in by_id or port not in {o['name'] for o in by_id[producer]['outputs']}:
                    found.append(f'{key}/inputs/{item["name"]}: no node output {source}')
                elif producer not in node.get('predecessors', []):
                    found.append(f'{key}/inputs/{item["name"]}: {producer} must be a predecessor')
        checked = [v['output'] for v in node['verifiers']]
        if len(set(checked)) != len(checked):
            found.append(f'{key}: one verifier per output')
        for name in set(checked) - set(outputs):
            found.append(f'{key}/verifiers: no output {name}')
        for output in node['outputs']:
            if output.get('required', True) and output['name'] not in checked:
                found.append(f'{key}/outputs/{output["name"]}: a required output needs a verifier')
        for verifier in node['verifiers']:
            kind = next((o['kind'] for o in node['outputs'] if o['name'] == verifier['output']), None)
            if verifier.get('stage') and not verifier.get('verifier'):
                found.append(f'{key}/verifiers/{verifier["output"]}: a stage needs a verifier capability')
            if verifier.get('inputs') and not verifier.get('verifier'):
                found.append(f'{key}/verifiers/{verifier["output"]}: pinned inputs need a verifier capability')
            if set(verifier.get('inputs') or {}) & {'checkout', 'diff_path'}:
                found.append(f'{key}/verifiers/{verifier["output"]}: checkout and diff_path are set by the host')
            if kind == 'diff' and not verifier.get('verifier') and verifier.get('review') is not True:
                found.append(f'{key}/verifiers/{verifier["output"]}: a diff needs a capsule verifier, a blocking review or '
                             'both (an advisory review decides nothing)')
            if kind not in ('diff', 'evidence') and verifier.get('verifier'):
                found.append(f'{key}/verifiers/{verifier["output"]}: capsule verifiers check diff and evidence outputs')
            if verifier.get('review') and kind not in ('diff', 'evidence'):
                found.append(f'{key}/verifiers/{verifier["output"]}: reviews read diffs and evidence; '
                             f'{kind} outputs are checked by the host')
        if known_requirements:
            for requirement in set(node.get('requirement_ids', [])) - known_requirements:
                found.append(f'{key}/requirement_ids: the contract has no arm, check or metric {requirement}')
        target = node['hands_to']
        if target != 'lab_manager' and (target not in by_id or key not in by_id[target].get('predecessors', [])):
            found.append(f'{key}/hands_to: {target} must be a node that lists {key} as a predecessor')
    leaves = [n for n in nodes if not any(n['node_id'] in m.get('predecessors', []) for m in nodes)]
    delivers = [n for n in nodes if n['kind'] == 'deliver']
    if len(leaves) != 1 or len(delivers) != 1 or leaves[0] is not delivers[0]:
        found.append('nodes: exactly one leaf, the deliver node, which hands the engine to the lab manager')
    for node in delivers:
        if node['hands_to'] != 'lab_manager':
            found.append(f'{node["node_id"]}/hands_to: the deliver node hands to lab_manager')
        if not any(o['kind'] == 'lab_request' and o.get('required', True) for o in node['outputs']):
            found.append(f'{node["node_id"]}/outputs: the deliver node produces a required lab_request')
    for node in nodes:
        if node['hands_to'] == 'lab_manager' and node['kind'] != 'deliver':
            found.append(f'{node["node_id"]}/hands_to: only the deliver node hands to lab_manager')
    return found


def from_contract(contract):
    """The node-contracts document a format-2 contract carries, or None."""
    return ((contract or {}).get('extensions') or {}).get(EXTENSION)


def for_task(task):
    """The node contracts of a task's contract (validated), or None when it has none."""
    from .contract import load
    contract = load(task['contract_id'])
    document = from_contract(contract)
    if document is None:
        return None
    found = problems(document, contract)
    if found:
        raise ValueError(f'Contract {task["contract_id"]} node contracts are invalid: ' + '; '.join(found[:8]))
    return document


def node(document, node_id):
    for item in (document or {}).get('nodes', []):
        if item['node_id'] == node_id:
            return item
    return None


def check_spec(node_contract):
    """The task graph ``check`` a node contract implies: one entry per verified output."""
    kinds = {o['name']: o for o in node_contract['outputs']}
    outputs = []
    for verifier in node_contract['verifiers']:
        output = kinds[verifier['output']]
        entry = dict(name=output['name'], kind=output['kind'], required=output.get('required', True))
        for field in ('verifier', 'stage', 'inputs'):
            if verifier.get(field):
                entry[field] = verifier[field]
        if verifier.get('review'):
            entry['review'] = verifier['review']  # true (blocking) or "advisory"
        if output.get('criteria'):
            entry['criteria'] = list(output['criteria'])
        outputs.append(entry)
    return dict(outputs=outputs)
