"""Validate a frozen workflow library as data, without importing its executor.

Historical recordings must never consult today's workflow registry. This checks
parent membership, typed bindings and complete stage references against the
canonical stage declarations retained in the same immutable recipe.
"""
from __future__ import annotations

import hashlib
import json
import re


def canonical_workflow_bytes(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


def workflow_library_sha256(value) -> str:
    return hashlib.sha256(canonical_workflow_bytes(value)).hexdigest()


def validate_workflow_library(library, catalog) -> None:
    """Raise ValueError for inconsistent frozen registry data or port custody."""
    def require(condition, message):
        if not condition:
            raise ValueError('Invalid frozen workflow library: ' + message)

    def identifier(value):
        require(isinstance(value, str) and re.fullmatch(r'[a-zA-Z0-9_-]+', value),
                'invalid local identifier')

    def mapping(value):
        require(isinstance(value, dict), 'expected a port mapping')
        require(all(isinstance(name, str) and name and isinstance(kind, str) and kind
                    for name, kind in value.items()), 'invalid typed port')
        return value

    def unique(rows, label):
        require(isinstance(rows, list), f'invalid {label} list')
        result = {}
        for row in rows:
            require(isinstance(row, dict), f'invalid {label} record')
            identifier(row.get('id'))
            require(row['id'] not in result, f'duplicate {label} identity')
            result[row['id']] = row
        return result

    def resolve(binding, available):
        require(isinstance(binding, dict) and set(binding) == {'source', 'port'}, 'invalid binding')
        source, port = binding['source'], binding['port']
        require(isinstance(source, str) and isinstance(port, str) and
                source in available and port in available[source], 'unknown or forward binding')
        return available[source][port]

    def inputs(required, bindings, available):
        require(isinstance(bindings, dict) and set(required) == set(bindings), 'bound input names differ')
        require(all(resolve(bindings[name], available) == kind for name, kind in required.items()),
                'bound input types differ')

    def outputs(bindings, available):
        require(isinstance(bindings, dict) and bindings, 'parent has no outputs')
        require(all(isinstance(name, str) and name for name in bindings), 'invalid output name')
        return {name: resolve(binding, available) for name, binding in bindings.items()}

    require(isinstance(library, dict) and library.get('schema') == 'factory.workflow.library.v1',
            'unsupported schema')
    require(isinstance(catalog, list), 'invalid canonical stage catalog')
    stages = {}
    for stage in catalog:
        require(isinstance(stage, dict) and isinstance(stage.get('id'), str) and stage['id'] and
                stage['id'] not in stages and isinstance(stage.get('entrypoint'), str) and
                stage['entrypoint'], 'invalid canonical stage declaration')
        ports = {}
        for direction in ('inputs', 'outputs'):
            rows = stage.get(direction)
            require(isinstance(rows, list), 'invalid canonical stage ports')
            typed = {}
            for port in rows:
                require(isinstance(port, dict) and isinstance(port.get('name'), str) and port['name'] and
                        port['name'] not in typed and isinstance(port.get('kind'), str) and port['kind'],
                        'invalid canonical stage port')
                typed[port['name']] = port['kind']
            ports[direction] = typed
        stages[stage['id']] = {**ports, 'entrypoint': stage['entrypoint']}
    subworkflows = unique(library.get('subworkflows'), 'subworkflow')
    workflows = unique(library.get('workflows'), 'workflow')
    sub_outputs = {}
    for definition in subworkflows.values():
        available = {'$input': mapping(definition.get('inputs'))}
        children = definition.get('stages')
        require(isinstance(children, list) and children, 'subworkflow has no child stages')
        for child in children:
            require(isinstance(child, dict), 'invalid child stage')
            identifier(child.get('id'))
            require(child['id'] not in available and child.get('stage_id') in stages,
                    'duplicate or unknown child stage')
            stage = stages[child['stage_id']]
            inputs(stage['inputs'], child.get('bindings'), available)
            available[child['id']] = stage['outputs']
        sub_outputs[definition['id']] = outputs(definition.get('outputs'), available)

    expected = []
    for workflow in workflows.values():
        available = {'$input': mapping(workflow.get('inputs'))}
        children = workflow.get('subworkflows')
        require(isinstance(children, list) and children, 'workflow has no child subworkflows')
        for reference in children:
            require(isinstance(reference, dict), 'invalid subworkflow reference')
            identifier(reference.get('id'))
            require(reference['id'] not in available and reference.get('definition') in subworkflows,
                    'duplicate or unknown subworkflow reference')
            definition = subworkflows[reference['definition']]
            inputs(definition['inputs'], reference.get('bindings'), available)
            available[reference['id']] = sub_outputs[definition['id']]
            parent = workflow['id'] + '/' + reference['id']
            full_refs = [parent + '/' + child['id'] for child in definition['stages']]
            for child, path in zip(definition['stages'], full_refs):
                stage = stages[child['stage_id']]
                siblings = [value for value in full_refs if value != path]
                origin = {'schema': 'factory.pool.origin.v1', 'full_ref': path,
                          'parent_ref': parent, 'canonical_stage_id': child['stage_id'],
                          'parent_definition_id': definition['id'],
                          'parent_definition_hash': workflow_library_sha256(definition),
                          'selected_refs': [path], 'all_sibling_refs': siblings,
                          'unselected_sibling_refs': siblings}
                expected.append({'path': path, 'stage_id': child['stage_id'],
                                 'entrypoint': stage['entrypoint'], 'inputs': stage['inputs'],
                                 'outputs': stage['outputs'], 'pool_origin': origin})
        outputs(workflow.get('outputs'), available)
    require(library.get('stage_refs') == expected, 'stage references or parent origins differ from frozen parents')


def validate_recorded_pool_origins(library, nodes) -> None:
    """Check selected subsets against the complete frozen immediate parents."""
    references = {entry['path']: entry for entry in library['stage_refs']}
    for node in nodes:
        origin = node.get('pool_origin')
        if origin is None:
            if node.get('workflow_path') in references:
                raise ValueError('Recorded full workflow reference has no pool origin')
            continue
        if not isinstance(origin, dict) or origin.get('full_ref') not in references:
            raise ValueError('Invalid recorded pool origin reference')
        retained = references[origin['full_ref']]['pool_origin']
        selected = origin.get('selected_refs')
        allowed = [retained['full_ref'], *retained['all_sibling_refs']]
        if (not isinstance(selected, list) or not all(isinstance(value, str) for value in selected) or
                len(set(selected)) != len(selected) or
                retained['full_ref'] not in selected or any(value not in allowed for value in selected)):
            raise ValueError('Invalid recorded pool selected references')
        expected = {**retained, 'selected_refs': selected,
                    'unselected_sibling_refs': [value for value in retained['all_sibling_refs'] if value not in selected]}
        if (origin != expected or node.get('stage_id') != retained['canonical_stage_id'] or
                node.get('workflow_path') != retained['full_ref']):
            raise ValueError('Recorded pool origin differs from frozen workflow library')


def validate_recorded_workflow_selections(library, nodes, events, library_sha256) -> None:
    """Bind multi-child selection claims to recorded expansion graphs and nodes."""
    references = {entry['path']: entry for entry in library['stage_refs']}
    actual = {node['id']: node for node in nodes}
    attested = []
    for event in events:
        if event['type'] != 'workflow.expanded':
            continue
        payload = event['payload']
        graph = payload.get('graph')
        if (not isinstance(graph, dict) or payload.get('workflow_catalog_sha256') != library_sha256 or
                graph.get('path') != payload.get('path') or
                graph.get('instance_id') != payload.get('instance_id')):
            raise ValueError('Recorded workflow expansion has no matching frozen library receipt')
        path = graph['path']
        if not isinstance(path, str) or len(path.split('/')) not in {1, 2, 3}:
            raise ValueError('Invalid recorded workflow selection path')
        expected = [ref for ref in references if ref == path or ref.startswith(path + '/')]
        declared = graph.get('nodes')
        if (not expected or not isinstance(declared, list) or
                [node.get('workflow_path') for node in declared] != expected):
            raise ValueError('Recorded workflow selection differs from its frozen child scope')
        validate_recorded_pool_origins(library, declared)
        receipts = payload.get('pool_origins')
        if not isinstance(receipts, list) or len(receipts) != len(declared):
            raise ValueError('Recorded workflow selection has incomplete node receipts')
        for node, receipt in zip(declared, receipts):
            origin = node['pool_origin']
            parent_selected = [ref for ref in expected if ref.rsplit('/', 1)[0] == origin['parent_ref']]
            if origin['selected_refs'] != parent_selected:
                raise ValueError('Recorded selected siblings differ from the actual expansion scope')
            if not isinstance(receipt, dict) or receipt.get('node_id') not in actual:
                raise ValueError('Workflow selection receipt has no actual node')
            target = actual[receipt['node_id']]
            if ({key: value for key, value in receipt.items() if key != 'node_id'} != origin or
                    target.get('workflow_path') != node['workflow_path'] or
                    target.get('stage_id') != node['stage_id']):
                raise ValueError('Workflow selection receipt differs from its actual node')
            selection = {'path': path, 'instance_id': graph['instance_id'], 'pool_origin': origin}
            if selection not in target.get('workflow_selections', []):
                raise ValueError('Actual node has no matching workflow selection receipt')
            attested.append((target['id'], selection))
    for node in nodes:
        for selection in node.get('workflow_selections', []):
            if (node['id'], selection) not in attested:
                raise ValueError('Node workflow selection has no recorded expansion event')
        origin = node.get('pool_origin')
        if origin and origin['all_sibling_refs'] and not any(
                node_id == node['id'] and selection['pool_origin'] == origin
                for node_id, selection in attested):
            raise ValueError('Partial or whole multi-child selection has no actual recorded expansion scope')
