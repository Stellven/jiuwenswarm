"""Compose and build with real STRATA and GoogleTest source functions."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .contracts import StageFailure
from .core_codegen import _choose
from .cuda_lowering import balanced, discover_operations
from .functional_operations import pinned_checkout
from .functional_project_catalog import build_catalog
from .workflow_library import WorkflowLibrary, write_json
from .workflow_planner import compose_contract
from .workflow_runtime import WorkflowExecutor


STRATA_URL = 'https://github.com/niko1221/strata'
GOOGLETEST_URL = 'https://github.com/google/googletest'
MODULE = 'jiuwenswarm.software_factory.functional_operations:'
BUILD_ACTION_SCOPE = 'construction'
POLICY = """# Compose Policy

## requested-results | Start with the files and results the task asks for
Read `required_outputs` in the order listed in the task JSON. Here the task asks
for the C++ project, a CPU executable, the selected expert IDs and weights, an
activation result, and the combined expert output. Each requested result gives
the Planner a type to look up.

The task's `inputs` already contain the expert scores, the two activation
vectors, and the vectors to combine. Copy those values into the corresponding
STRATA steps as parameters.

## exact-contract | Find the part or build action that supplies what we need
Compare the needed type with the outputs of registered steps. The Workflow
Library supplies reusable parts from STRATA and GoogleTest. The factory supplies
its own built-in actions for writing C++ source and compiling it. Schedule a
build action when the task or a downstream step needs that action's output.
Keep the specific matching output. Stop if no output matches or several match.

> The C++ generator needs a list of STRATA function names. GoogleTest's name
> matcher declares that list as its output, so the Planner picks it.

In the graph, both sides of this connection declare `strata.operation_selection`.
The same lookup also works when the two port names differ. For example,
`Select experts.result` supplies `Combine expert outputs.routing` because both
declare `strata.result.routing`.

## dependencies | Connect each step's required inputs to their sources
Open the selected step's input contract. Find a provider for each required
input, and resolve that provider's inputs in turn. Add a node once its required
providers are resolved. Record each connection from the provider's node and
named output to the receiving node's named input.

> Combine expert outputs needs the CPU executable from Compile the STRATA
> program and the expert IDs and weights from Select experts. Its expert
> vectors and shared vector are already supplied by the task.

Likewise, the compiler receives the C++ project from the generator. The
generator receives the function list from the matcher. Stop if resolving an
input leads back to the same unresolved type.

## reuse | Share one compile step across the three STRATA operations
Reuse a step already included in the graph by its pinned identity. Connect the
same output to every consumer that asks for it. Here expert
selection, activation, and combination all consume the same CPU executable.
Leave a Library part out if no requested result or required input uses its
output. The worker-assignment step stays in the Library for this task.

## source-filter | Pass the selected STRATA function names to GoogleTest
After selecting the operations, take their original source names
(`router_top10_kernel`, `swiglu_kernel`, and `moe_combine_kernel`). Derive the
name pattern and pass it to GoogleTest's matcher. When the task runs, the matcher
returns the selected names to the C++ generator.

## admission | Check the connections and order producers before consumers
Check the pinned Library parts and build actions, their parameters and ports,
and the requested deliverables. Reject a cycle. Place each
producer before the steps that need its output. If multiple steps can go next,
order them by node ID. In this graph, source generation precedes compilation,
and expert selection precedes combination.
"""
OPERATIONS = {
    'routing': ('Select experts', 'Expert scores and K', 'Expert IDs and routing weights'),
    'activation': ('Apply the expert activation', 'Gate vector and up vector', 'Gated vector'),
    'aggregation': ('Combine expert outputs', 'Expert outputs, routing weights, and a shared output', 'Combined output vector'),
}


def port(kind, name, **options):
    return {'semantic_type': kind, 'name': name, **options}


def part(identity, name, function, inputs, outputs, parameters=None, *, source=None, tools=()):
    definition = {'id': identity, 'name': name, 'inputs': inputs, 'outputs': outputs,
                  'implementation': {'type': 'python', 'entrypoint': MODULE + function},
                  'requirements': {'executables': list(tools)}, 'default_parameters': parameters or {}}
    if source:
        definition['upstream_function'] = source
    return definition


def source_function(checkout, relative_path, signature, name):
    text = (checkout / relative_path).read_text()
    start = text.index(signature)
    opening = text.index('{', start)
    return {'name': name, 'path': relative_path, 'line': text.count('\n', 0, start) + 1,
            'code': text[start:balanced(text, opening) + 1]}


class FactoryPlanResolver:
    """Keep imported workflow lookup separate from pinned internal build actions."""

    def __init__(self, library, action_store, action_version):
        self.library = library
        self.action_store = action_store
        self.action_version = action_version

    def list(self):
        # The legacy recording indexes the two catalogs together. Project only
        # its imported entries here without changing the recorded bytes.
        refs = json.loads((self.library.root / 'index.json').read_text())['workflows']
        return [self.library.get(ref['id'], ref['version']) for ref in refs
                if ref['id'] != BUILD_ACTION_SCOPE]

    def build_definition(self):
        return self.action_store.get(BUILD_ACTION_SCOPE, self.action_version)

    def build_actions(self):
        definition = self.build_definition()
        return [{'id': BUILD_ACTION_SCOPE + '.' + action['id'], 'version': definition['version'],
                 **{key: action[key] for key in ('name', 'inputs', 'outputs')}}
                for action in definition['subworkflows']]

    def _store(self, scope, version):
        if scope != BUILD_ACTION_SCOPE:
            return self.library
        if version != self.action_version:
            raise StageFailure('unknown_build_action_version', str(version))
        return self.action_store

    def get(self, scope, version):
        return self._store(scope, version).get(scope, version)

    def resolve(self, scope, version, component):
        return self._store(scope, version).resolve(scope, version, component)


def register(library, strata, gtest):
    strata_root = pinned_checkout(strata)
    gtest_root = pinned_checkout(gtest)
    discovery = discover_operations(strata_root)
    strata_parts, candidates = [], []
    binary = port('strata.binary', 'Built STRATA program')
    routing = port('strata.result.routing', 'Expert IDs and routing weights', format='json')
    for category, (name, input_name, output_name) in OPERATIONS.items():
        operation = _choose(discovery, category)
        candidates.append({'id': operation['id'], 'name': operation['name']})
        source = {'name': operation['name'], 'path': operation['path'], 'line': operation['line'],
                  'code': operation['source_code']}
        inputs = {'binary': binary}
        parameters = {'operation': operation['id'], 'numeric_input': ''}
        if category == 'aggregation':
            inputs['routing'] = routing
            parameters.update(expert_outputs={}, shared_output=[])
        strata_parts.append(part(category, name, 'compute', inputs,
                                  {'result': port('strata.result.' + category, output_name, format='json')},
                                  parameters, source=source))
        strata_parts[-1]['numerical_input'] = input_name
    selection = port('strata.operation_selection', 'Selected STRATA functions', format='json')
    candidate_filter = part('match_names', 'Match names to a pattern', 'match_names', {},
                            {'selection': selection}, {**gtest, 'candidates': candidates, 'pattern': '*'},
                            source=source_function(gtest_root, 'googletest/src/gtest.cc',
                                                   'class UnitTestFilter {', 'UnitTestFilter::MatchesName'),
                            tools=('c++',))
    shard = part('assign_shard', 'Assign work to one worker', 'assign_to_shard', {'selection': selection},
                 {'shard': port('work.shard', 'Work assigned to one worker', format='json')},
                 {**gtest, 'count': 1, 'index': 0},
                 source=source_function(gtest_root, 'googletest/src/gtest.cc',
                                        'bool ShouldRunTestOnShard(int total_shards', 'ShouldRunTestOnShard'),
                 tools=('c++',))
    for identity, name, source, parts in [
        ('strata', 'STRATA', {**strata, 'repository': STRATA_URL}, strata_parts),
        ('googletest', 'GoogleTest', {**gtest, 'repository': GOOGLETEST_URL}, [candidate_filter, shard]),
    ]:
        library.register({'id': identity, 'name': name, 'source': source, 'subworkflows': parts})


def register_build_actions(store, strata):
    selection = port('strata.operation_selection', 'Selected STRATA functions', format='json')
    source = port('strata.source', 'STRATA C++ project')
    binary = port('strata.binary', 'Built STRATA program')
    actions = [
        part('generate', 'Generate the STRATA C++ project', 'generate_source', {'selection': selection},
             {'source': source}, strata),
        part('compile', 'Compile the STRATA program', 'build_source', {'source': source},
             {'binary': binary}, tools=('cmake',)),
    ]
    return store.register({'id': BUILD_ACTION_SCOPE, 'name': 'Built-in C++ actions',
                           'source': {'repository': 'file:jiuwenswarm'}, 'subworkflows': actions})


def compose(resolver, task, *, emit=None):
    """Add the pinned construction actions and STRATA operation parameters."""

    def parameters_for(scope, component):
        return task.get('inputs', {}).get(component['id'], {}) if scope['id'] == 'strata' else {}

    def finalize_nodes(nodes, record):
        if 'googletest.match_names' in nodes:
            names = [resolver.resolve(node['workflow']['id'], node['workflow']['version'], node['subworkflow'])
                     ['upstream_function']['name'] for node in nodes.values() if node['workflow']['id'] == 'strata']
            if names:
                pattern = ':'.join('STRATA.' + name for name in names)
                nodes['googletest.match_names']['parameters']['pattern'] = pattern
                record('set_filter', 'source-filter', node='googletest.match_names', functions=names, pattern=pattern)

    return compose_contract(
        resolver, task, emit=emit,
        extra_catalogs=((resolver.build_definition(), 'build_action'),),
        parameters_for=parameters_for, finalize_nodes=finalize_nodes,
    )


def prepare_project_library(root, strata, gtest):
    """Register executable contracts and extract the pinned source catalog."""
    library_root = root / 'library'
    index = library_root / 'index.json'
    if index.is_file() and any(ref['id'] == BUILD_ACTION_SCOPE
                               for ref in json.loads(index.read_text())['workflows']):
        # Keep a legacy index available for the runs that pinned its entries.
        library_root = root / 'imported-workflows'
    library = WorkflowLibrary(library_root)
    register(library, strata, gtest)
    build_catalog(library, root / 'module-library.json')
    return library


def run(root, strata, gtest, task):
    library = prepare_project_library(root, strata, gtest)
    action_store = WorkflowLibrary(root / 'build-actions')
    definitions = register_build_actions(action_store, strata)
    resolver = FactoryPlanResolver(library, action_store, definitions['version'])
    graph, selections = compose(resolver, task)
    (root / 'composer_policy.md').write_text(POLICY)
    write_json(root / 'task_contract.json', task)
    write_json(root / 'task_graph.json', graph)
    write_json(root / 'selections.json', selections)
    return WorkflowExecutor(resolver, root / 'runs').run(graph)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ['workspace', 'strata', 'googletest', 'task']:
        parser.add_argument('--' + option, required=True, type=Path)
    for option in ['strata-revision', 'googletest-revision']:
        parser.add_argument('--' + option, required=True)
    args = parser.parse_args()
    task = json.loads(args.task.read_bytes())
    run_root = args.workspace.resolve()
    run_root.mkdir(parents=True, exist_ok=True)
    summary = run(run_root, {'checkout': str(args.strata.resolve()), 'revision': args.strata_revision},
                  {'checkout': str(args.googletest.resolve()), 'revision': args.googletest_revision}, task)
    print(summary['id'], summary['status'])
    for node in summary['nodes']:
        if node.get('error'):
            print(node['id'], node['error']['message'])
    raise SystemExit(summary['status'] != 'verified')
