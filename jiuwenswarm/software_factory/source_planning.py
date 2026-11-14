"""Choose and compose executable implementation stages after reading source."""
from __future__ import annotations
import fnmatch
import hashlib
import json
from pathlib import Path
from .contracts import Stage, StageBlocked, StageFailure
from .task_contract import normalize_task


def compile_requirements(ctx, inputs):
    submitted = ctx.options.get('task')
    if submitted is None:
        aliases = {'router': 'routing', 'swiglu': 'activation', 'moe_combine': 'aggregation'}
        legacy = ctx.options.get('options', {}).get('core_algorithms')
        submitted = {'description': 'Construct a source-bound STRATA core project',
                     'capabilities': [aliases[v] for v in legacy] if legacy else ['routing', 'activation', 'aggregation'],
                     'acceptance': {'source_project': True, 'cpu_validation': True}}
    task = normalize_task(submitted)
    return {'requirements': ctx.write_json('engineering-requirements.json', {
        'schema': 'factory.engineering.requirements.v1', **task,
        'target_backend': ctx.options.get('target_backend', 'ascend'),
        'selection_authority': 'explicit acceptance contract and actual source discovery'})}


def discover_source(ctx, inputs):
    from .core_codegen import discover_operations
    inventory = inputs['inventory'].read_json()
    found = discover_operations(Path(inventory['source_dir']))
    operations = found.get('operations', []) if isinstance(found, dict) else found
    if not isinstance(operations, list) or not operations:
        raise StageFailure('no_source_operations', 'No actual source functions were discovered')
    return {'discovery': ctx.write_json('source-operations.json', {
        'schema': 'factory.source.operations.v1', 'source_dir': inventory['source_dir'],
        'commit_sha': inventory['commit_sha'], 'inventory_path': inputs['inventory'].path,
        'inventory_sha256': inputs['inventory'].sha256, 'operations': operations})}


def _path(operation):
    return operation.get('sourcefile') or operation.get('file') or operation.get('path', '')


def select_operations(discovery, requirements):
    available = [operation for operation in discovery['operations']
                 if operation.get('supported') and any(fnmatch.fnmatchcase(_path(operation), pattern)
                                                       for pattern in requirements['source_scope'])]
    if not available:
        raise StageBlocked('implementation_capability_missing', 'No executable lowering matches the inspected source scope',
                           {'source_scope': requirements['source_scope'], 'operations': discovery['operations']})
    categories = requirements['capabilities']
    if not categories:
        selected = available
    else:
        selected = []
        for category in categories:
            candidates = [v for v in available if category in {v.get('category'), v.get('operation'), v.get('name'), v.get('id')}]
            if not candidates:
                raise StageBlocked('implementation_capability_missing', f'No executable source implementation for {category}',
                                   {'capability': category, 'source_scope': requirements['source_scope']})
            # ABI coverage and supported structure determine selection. No known
            # filename or function identity is used as an implementation switch.
            def rank(value):
                features = value.get('features', {})
                signature = str(value.get('signature', ''))
                configurable = bool(features.get('configurable_experts') or ('n_expert' in signature and 'int k' in signature))
                return (not configurable if category == 'routing' else False,
                        value.get('cost', 1), len(value.get('body', value.get('source_code', ''))),
                        _path(value), value.get('function', value.get('name', '')))
            selected.append(sorted(candidates, key=rank)[0])
    if len(selected) > 32:
        raise StageFailure('task_scope_too_large', 'Refine the source scope; this executor admits at most 32 implementation instances')
    return selected


def bind_operation(ctx, inputs):
    discovery = inputs['discovery'].read_json()
    key = ctx.parameters['operation_id']
    descriptor = next((v for v in discovery['operations'] if (v.get('id') or v.get('name')) == key), None)
    if descriptor is None:
        raise StageFailure('source_operation_missing', key)
    return {'operator': ctx.write_json('source-operation.json', {
        'schema': 'factory.source.operation.v1', 'source_dir': discovery['source_dir'],
        'commit_sha': discovery['commit_sha'], 'descriptor': descriptor})}


def lower_operator(ctx, inputs):
    from .core_codegen import extract_core, validate_core
    operation = inputs['operator'].read_json()
    descriptor = operation['descriptor']
    expected = ctx.execution.stages[ctx.node['stage_id']].accepts['lowering_kind']
    if descriptor.get('lowering_kind') != expected:
        raise StageFailure('incompatible_lowering', 'Selected implementation cannot execute this source structure')
    core = extract_core(Path(operation['source_dir']), ctx.workspace/'lowered',
                        selected=[descriptor['id']])
    validate_core(core)
    return {'core': ctx.write_json('lowered-core.json', core)}


def compose_implementation(ctx, inputs):
    from .core_codegen import merge_core, validate_core
    discovery = inputs['discovery'].read_json()
    requirements = inputs['requirements'].read_json()
    selected = select_operations(discovery, requirements)
    products, decisions = [], []
    for descriptor in selected:
        operator_id = descriptor.get('id') or descriptor['name']
        extracted = ctx.execution.invoke_stage('source.bind_operation', {'discovery': inputs['discovery']},
                                               parameters={'operation_id': operator_id})['operator']
        candidates = sorted([stage for stage in ctx.execution.stages.values()
                             if stage.inputs == {'operator': 'source.operator'} and
                             stage.outputs == {'core': 'core.lowered'} and
                             stage.accepts.get('lowering_kind') == descriptor.get('lowering_kind')],
                            key=lambda stage: (stage.cost, stage.id))
        if not candidates:
            raise StageBlocked('implementation_capability_missing', 'No executable stage accepts this source structure', descriptor)
        stage = candidates[0]
        decision = {'operation_id': operator_id, 'sourcefile': _path(descriptor), 'features': descriptor.get('features'),
                    'lowering_kind': descriptor['lowering_kind'], 'selected_stage': stage.id,
                    'input_sha256': extracted.sha256}
        decisions.append(decision)
        ctx.execution.emit('implementation.selected', ctx.node['id'], decision)
        product = ctx.execution.invoke_stage(stage.id, {'operator': extracted})['core']
        products.append(product)
    core = merge_core([ctx.consume_json(product) for product in products])
    if requirements.get('oracle') is not None:
        core['task_oracle'] = requirements['oracle']
    validate_core(core)
    raw_path = Path(discovery['inventory_path'])
    if hashlib.sha256(raw_path.read_bytes()).hexdigest() != discovery['inventory_sha256']:
        raise StageFailure('artifact_changed', 'Source inventory changed during implementation composition')
    raw = json.loads(raw_path.read_text())
    # Descriptor adaptation does not claim a native operator migration. Source
    # generation consumes independently executed, source-bound lowerings below.
    operations = [{'file': v['file'], 'source_sha256': v['source_sha256'], 'source_id': v['id'],
                   'source_name': v['name'], 'implementation_status': 'not_migrated'} for v in raw['cuda_ops']]
    ctx.execution.graph_revision('Selected executable implementation instances from actual source features and engineering requirements')
    return {'inventory': ctx.write_json('native-core-inventory.json', {
        'schema': 'strata.ascend.inventory.v3', 'source_dir': discovery['source_dir'], 'commit_sha': discovery['commit_sha'],
        'files': raw['files'], 'ascend_ops': operations, 'core_ir': core, 'implementation_decisions': decisions,
        'consumed_lowerings': [product.serializable() for product in products], 'semantic_lowering_complete': False})}


def planning_stages():
    return [
        Stage('task.compile', 'Compile engineering acceptance requirements', 'task_preparation', 'requirements', {},
              {'requirements': 'task.requirements'}, compile_requirements),
        Stage('source.discover', 'Discover source operations and required execution structures', 'source_acquisition', 'semantic_discovery',
              {'inventory': 'operator.inventory'}, {'discovery': 'source.operations'}, discover_source),
        Stage('source.bind_operation', 'Extract a discovered source function', 'source_acquisition', 'function_extraction',
              {'discovery': 'source.operations'}, {'operator': 'source.operator'}, bind_operation, selection_only=True),
        Stage('lower.scalar', 'Lower source scalar computation', 'implementation', 'scalar_lowering',
              {'operator': 'source.operator'}, {'core': 'core.lowered'}, lower_operator,
              accepts={'lowering_kind': 'scalar'}, selection_only=True),
        Stage('lower.cooperative', 'Lower source shared-memory and collective computation', 'implementation', 'cooperative_lowering',
              {'operator': 'source.operator'}, {'core': 'core.lowered'}, lower_operator,
              accepts={'lowering_kind': 'cooperative'}, selection_only=True),
        Stage('metadata.compose_core', 'Compose implementations from source features', 'transformation', 'implementation_composition',
              {'discovery': 'source.operations', 'requirements': 'task.requirements'},
              {'inventory': 'operator.native_inventory'}, compose_implementation, dynamic_inputs=('core.lowered',)),
    ]
