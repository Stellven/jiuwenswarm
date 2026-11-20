"""Acquire pinned projects, compose the requested build, and publish its real Product."""
from __future__ import annotations

from copy import deepcopy
import math
import os
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory
from threading import Lock
from typing import Callable

from .functional_factory import (
    GOOGLETEST_URL, POLICY, STRATA_URL, FactoryPlanResolver, compose,
    prepare_project_library, register_build_actions,
)
from .functional_operations import pinned_checkout
from .guided_replay import build_guided_replay, public_task_graph
from .model_driver import redact
from .workflow_imports import STRATA_PIN, import_project
from .workflow_library import WorkflowLibrary, write_json
from .workflow_runtime import WorkflowExecutor


_SOURCES = (
    ('strata', 'STRATA', STRATA_URL, STRATA_PIN, 'JIUWENSWARM_FACTORY_STRATA_CHECKOUT'),
    ('googletest', 'GoogleTest', GOOGLETEST_URL, '52eb8108c5bdec04579160ae17225d66034bd723',
     'JIUWENSWARM_FACTORY_GOOGLETEST_CHECKOUT'),
)
_OPERATION_OUTPUTS = {
    'strata.result.routing': 'routing',
    'strata.result.activation': 'activation',
    'strata.result.aggregation': 'aggregation',
}
_OUTPUTS = {'strata.source', 'strata.binary', *_OPERATION_OUTPUTS}
_NUMERIC = re.compile(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[Ee][+-]?[0-9]+)?')
_source_lock = Lock()


def _number(value):
    # The generated CPU project reads these inputs as float and uses them in products.
    if type(value) not in (int, float) or not -1_000_000 <= value <= 1_000_000 or not math.isfinite(value):
        raise ValueError('Task vectors must contain finite numbers between -1000000 and 1000000')


def _numeric_parameters(part, parameters):
    value = parameters.get('numeric_input')
    if (set(parameters) != {'numeric_input'} or not isinstance(value, str) or not value.isascii()
            or not 1 <= len(value) <= 65536):
        raise ValueError(f'{part} requires numeric_input with the documented dimensions and vectors')
    tokens = value.split()
    header = 2 if part == 'routing' else 1
    if len(tokens) < header or any(not re.fullmatch(r'[0-9]{1,4}', item) for item in tokens[:header]):
        raise ValueError(f'{part} requires integer dimensions before the numeric values')
    size = int(tokens[0])
    if part == 'routing':
        if not 1 <= size <= 512 or not 1 <= int(tokens[1]) <= size:
            raise ValueError('Routing requires 1 to 512 experts and a selection count within that range')
        expected = size
    else:
        if not 1 <= size <= 2048:
            raise ValueError('Activation requires two vectors of the same size, between 1 and 2048')
        expected = 2 * size
    if len(tokens) != expected + header:
        raise ValueError(f'{part} dimensions do not match the supplied values')
    for item in tokens[header:]:
        if not _NUMERIC.fullmatch(item):
            raise ValueError(f'{part} inputs must be decimal numbers')
        _number(float(item))
    return size


def _aggregation_parameters(parameters, expert_count):
    if set(parameters) != {'expert_outputs', 'shared_output'}:
        raise ValueError('Aggregation requires expert_outputs and shared_output')
    experts, shared = parameters['expert_outputs'], parameters['shared_output']
    if not isinstance(experts, dict) or set(experts) != {str(index) for index in range(expert_count)}:
        raise ValueError('Aggregation requires one output vector per routing expert, keyed by its zero-based index')
    if not isinstance(shared, list) or not 1 <= len(shared) <= 512 or expert_count * len(shared) > 65536:
        raise ValueError('Aggregation vectors must fit the supported dimensions')
    for row in [shared, *experts.values()]:
        if not isinstance(row, list) or len(row) != len(shared):
            raise ValueError('All expert output vectors must match the shared output vector size')
        for value in row:
            _number(value)


def validate_live_task(task: dict) -> dict:
    """Validate a bounded Task Contract before creating an owned run."""
    if not isinstance(task, dict) or set(task) - {'description', 'required_outputs', 'inputs'}:
        raise ValueError('Submit a Task Contract with description, required_outputs, and inputs')
    description = task.get('description')
    if not isinstance(description, str) or not description.strip() or len(description) > 4096:
        raise ValueError('Task description must contain 1 to 4096 characters')
    outputs = task.get('required_outputs')
    if (not isinstance(outputs, list) or not 1 <= len(outputs) <= len(_OUTPUTS)
            or any(not isinstance(kind, str) or kind not in _OUTPUTS for kind in outputs)
            or len(set(outputs)) != len(outputs)):
        raise ValueError('Request distinct supported outputs from source, binary, routing, activation, and aggregation')
    inputs = task.get('inputs', {})
    if (not isinstance(inputs, dict) or set(inputs) - set(_OPERATION_OUTPUTS.values())
            or any(not isinstance(parameters, dict) for parameters in inputs.values())):
        raise ValueError('Task inputs must contain only the routing, activation, and aggregation parameter objects')
    required = {_OPERATION_OUTPUTS[kind] for kind in outputs if kind in _OPERATION_OUTPUTS}
    if 'aggregation' in required or 'aggregation' in inputs:
        required.add('routing')
    if missing := required - inputs.keys():
        raise ValueError('Missing numeric input for ' + ', '.join(sorted(missing)))
    counts = {part: _numeric_parameters(part, inputs[part]) for part in ('routing', 'activation') if part in inputs}
    if 'aggregation' in inputs:
        _aggregation_parameters(inputs['aggregation'], counts['routing'])
    return deepcopy(task)


def _validated_source(path, repository, revision):
    checkout = pinned_checkout({'checkout': path, 'revision': revision})
    origin = subprocess.check_output(['git', '-C', str(checkout), 'remote', 'get-url', 'origin'],
                                     text=True, timeout=30).strip()
    if origin.rstrip('/').removesuffix('.git') != repository:
        raise ValueError('Source checkout origin does not match the pinned upstream repository')
    return checkout


def _source(source_root, project, emit):
    identity, name, repository, revision, variable = project
    source = {'id': identity, 'name': name, 'repository': repository, 'revision': revision}
    configured = os.environ.get(variable)
    checkout = Path(configured) if configured else source_root / identity
    with _source_lock:
        cached = bool(configured) or checkout.exists()
        emit('source.started', {**source, 'cached': cached})
        if cached:
            checkout = _validated_source(checkout, repository, revision)
        else:
            source_root.mkdir(parents=True, exist_ok=True)

            def observation(kind, payload):
                if kind.startswith('import.command.'):
                    if 'text' in payload:
                        payload = {**payload, 'text': redact(payload['text'])}
                    emit(kind.replace('import.', 'source.', 1), {**source, **payload})

            with TemporaryDirectory(dir=source_root, prefix='.acquire-') as directory:
                bundle = import_project(Path(directory), repository, revision=revision, emit=observation)
                acquired = _validated_source(bundle['source']['checkout'], repository, revision)
                acquired.rename(checkout)
            checkout = checkout.resolve(strict=True)
        emit('source.ready', {**source, 'cached': cached})
    return {'checkout': str(checkout), 'revision': revision}


def run_live_workflow(workspace: Path, task: dict, *, run_id: str,
                      emit: Callable, source_root: Path | None = None) -> dict:
    """Build a new Product and its replay from this run's verified artifacts."""
    task = validate_live_task(task)
    workspace = workspace.resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    sources = source_root.resolve() if source_root is not None else workspace / 'sources'
    strata, googletest = [_source(sources, project, emit) for project in _SOURCES]
    emit('catalog.started', {})
    library = prepare_project_library(workspace, strata, googletest)
    action_store = WorkflowLibrary(workspace / 'build-actions')
    action_definition = register_build_actions(action_store, strata)
    resolver = FactoryPlanResolver(library, action_store, action_definition['version'])
    workflows = [
        {**{key: value[key] for key in ('id', 'name', 'version')},
         'source': {key: value['source'][key] for key in ('repository', 'revision')},
         'subworkflows': [{key: part[key] for key in ('id', 'name', 'inputs', 'outputs')}
                          for part in value['subworkflows']]}
        for value in resolver.list()
    ]
    build_actions = resolver.build_actions()
    emit('catalog.ready', {'workflows': workflows, 'build_actions': build_actions})
    decisions = []

    def observe(decision):
        decisions.append(decision)
        emit('planner.decision', decision)

    graph, selections = compose(resolver, task, emit=observe)
    composition = {
        'task': task, 'policy': POLICY, 'library': workflows, 'events': decisions,
        'build_actions': build_actions, 'graph': graph, 'selections': selections,
        'construction_run': run_id,
    }
    compose_path = workspace / 'compose-replay.json'
    write_json(compose_path, composition)
    graph_path = workspace / 'task_graph.json'
    write_json(graph_path, graph)
    public_graph = public_task_graph(graph, composition)
    emit('planner.graph_created', {'graph': public_graph, 'selections': selections,
                                   'build_actions': build_actions, 'policy': POLICY, 'graph_path': graph_path.name})

    run = WorkflowExecutor(resolver, workspace / 'runs').run(graph_path, run_id=run_id, emit=emit)
    if run['status'] == 'verified':
        product = build_guided_replay(workspace, workspace / 'runs' / run_id,
                                      workspace / 'module-library.json', compose_path)
        write_json(workspace / 'guided-replay.json', product)
    result = {key: run[key] for key in ('id', 'status', 'nodes', 'outputs', 'error')}
    return {**result, 'graph': public_graph, 'product_ready': run['status'] == 'verified'}
