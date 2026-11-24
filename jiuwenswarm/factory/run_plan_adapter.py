"""Map M1 frozen run-plan nodes, ports and dependencies to factory contracts.

Check pins, model routing and authority cannot carry over to this lighter format;
CC names are advice, not pinned execution assignments. Original source bindings
and renamed identifiers are retained as JSON data in output criteria, since the
schema has no metadata field. This conversion does not authorize execution.
"""

import json
from pathlib import Path
import re

from jsonschema import Draft202012Validator


_SCHEMA = json.loads(
    (Path(__file__).parent / 'schemas' / 'node-contract-1.schema.json').read_text(
        encoding='utf-8'))
_VALIDATOR = Draft202012Validator(_SCHEMA)
_ID = re.compile(_SCHEMA['$defs']['id']['pattern'])
_CC = re.compile(_SCHEMA['$defs']['capsule']['pattern'])


def _names(values):
    """Allocate collision-free names, reserving already valid identifiers first."""
    values = list(dict.fromkeys(values))
    result = {value: value for value in values if _ID.fullmatch(value)}
    used = set(result.values())
    for value in values:
        if value in result:
            continue
        base = re.sub('[^a-z0-9_]', '_', value.lower())
        if not base or not base[0].isalpha():
            base = 'n_' + base
        candidate = base[:32]
        suffix = 1
        while candidate in used:
            tail = f'_{suffix}'
            candidate = base[:32 - len(tail)] + tail
            suffix += 1
        result[value] = candidate
        used.add(candidate)
    return result


def _provenance(outputs, data):
    """Store JSON in ordered, bounded criteria entries without extra fields."""
    if not data:
        return
    encoded = json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    chunks = [encoded[i:i + 540] for i in range(0, len(encoded), 540)]
    if len(chunks) > 11 * len(outputs):
        raise ValueError('Original bindings exceed the output criteria capacity')
    for index, chunk in enumerate(chunks):
        outputs[index // 11]['criteria'].append(
            f'Adapter provenance JSON part {index + 1}/{len(chunks)} (data only): {chunk}')


def from_run_plan(run_plan: dict) -> dict:
    """Convert a run plan without modifying it; validate the result before use.

    Outputs without contract_id use their declared artifact_type as the contract
    description. Provenance JSON parts concatenate in output/criteria order.
    """
    source_nodes = run_plan['nodes']
    ids = [node['node_id'] for node in source_nodes]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate run plan node_id')
    referenced = [pred for node in source_nodes for pred in node.get('predecessors', [])]
    referenced += [port['future']['producer_node'] for node in source_nodes
                   for port in node.get('inputs', []) if port.get('future')]
    node_names = _names(ids + referenced)
    output_names = {}
    for node in source_nodes:
        ports = [port['name'] for port in node['outputs']]
        if len(set(ports)) != len(ports):
            raise ValueError(f"Duplicate output name in {node['node_id']}")
        output_names[node['node_id']] = ports
    for node in source_nodes:
        for port in node.get('inputs', []):
            if port.get('future'):
                future = port['future']
                output_names.setdefault(future['producer_node'], []).append(future['port'])
    output_names = {key: _names(values) for key, values in output_names.items()}
    rank = {name: index for index, name in enumerate(run_plan.get('topological_order', ids))}
    nodes = []
    for source in source_nodes:
        original_id = source['node_id']
        successors = [node['node_id'] for node in source_nodes
                      if original_id in node.get('predecessors', [])]
        successors.sort(key=lambda name: rank.get(name, len(rank)))
        input_names = _names(port['name'] for port in source.get('inputs', []))
        inputs = []
        original_bindings = []
        for port in source.get('inputs', []):
            future = port.get('future')
            if future:
                producer = future['producer_node']
                binding = f"{node_names[producer]}.{output_names[producer][future['port']]}"
            else:
                binding = 'task:source'
                original_bindings.append(port)
            inputs.append({'name': input_names[port['name']], 'from': binding,
                           'required': port.get('required', True)})
        outputs = []
        for port in source['outputs']:
            if port.get('contract_id'):
                criterion = f"Output must satisfy contract_id {port['contract_id']}."
            else:
                criterion = (f"Output must satisfy the {port['artifact_type']} artifact contract "
                             '(the run plan supplies no contract_id).')
            outputs.append({'name': output_names[original_id][port['name']],
                            'kind': 'evidence', 'criteria': [criterion],
                            'required': port.get('required', True)})
        node = {
            'node_id': node_names[original_id],
            'kind': 'investigate' if successors else 'deliver',
            'objective': source['objective'][:300],
            'requirement_ids': list(dict.fromkeys(
                source.get('requirement_ids', []) + source.get('deliverable_ids', []))),
            'predecessors': [node_names[pred] for pred in source.get('predecessors', [])],
            'inputs': inputs,
            'outputs': outputs,
            'verifiers': [{'output': port['name'], 'review': True} for port in outputs],
            'hands_to': node_names[successors[0]] if successors else 'lab_manager',
        }
        cc_name = source.get('cc', {}).get('cc_name', '')
        if _CC.fullmatch(cc_name):
            node['work'] = {'helpful_ccs': [cc_name]}
        if 'time_s' in source.get('limits', {}):
            node['node_limits'] = {'time_s': source['limits']['time_s']}
        nodes.append(node)
    return {'format': 'factory.node-contracts/1', 'nodes': nodes}


def validate(document) -> list[str]:
    """Return schema and graph problems, allowing task/contract source bindings."""
    problems = [f"{'/'.join(map(str, error.absolute_path)) or '(top)'}: {error.message}"
                for error in _VALIDATOR.iter_errors(document)]
    if problems:
        return problems
    nodes = {node['node_id']: node for node in document['nodes']}
    if len(nodes) != len(document['nodes']):
        problems.append('Duplicate node_id')
    dependencies = {}
    for node_id, node in nodes.items():
        predecessors = set(node.get('predecessors', []))
        dependencies[node_id] = predecessors & nodes.keys()
        for predecessor in sorted(predecessors - nodes.keys()):
            problems.append(f'{node_id}: predecessor {predecessor} does not exist')
        output_ids = [port['name'] for port in node['outputs']]
        if len(set(output_ids)) != len(output_ids):
            problems.append(f'{node_id}: duplicate output name')
        for port in node.get('inputs', []):
            binding = port['from']
            if binding.startswith(('task:', 'contract:')):
                continue
            producer, output = binding.split('.')
            if producer not in nodes or output not in {
                    item['name'] for item in nodes[producer]['outputs']}:
                problems.append(f'{node_id}: input {port["name"]} references missing output {binding}')
            if producer not in predecessors:
                problems.append(f'{node_id}: input producer {producer} is not a predecessor')
            if producer in nodes:
                dependencies[node_id].add(producer)
    ready = [node_id for node_id, deps in dependencies.items() if not deps]
    visited = set()
    while ready:
        node_id = ready.pop()
        visited.add(node_id)
        for successor, deps in dependencies.items():
            if node_id in deps:
                deps.remove(node_id)
                if not deps:
                    ready.append(successor)
    if len(visited) != len(nodes):
        problems.append('Node graph contains a cycle')
    return problems
