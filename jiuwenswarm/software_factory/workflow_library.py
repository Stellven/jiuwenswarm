"""Versioned Workflow definitions, identity cards and instance-graph admission.

Definitions never contain run status. Python and Agent implementations share
artifact ports; only the executor chooses their concrete execution adapter.
"""
from __future__ import annotations

from copy import deepcopy
import ast
import hashlib
import json
from pathlib import Path
import re
import threading
from typing import Any

from .contracts import StageFailure

IDENTIFIER = re.compile(r'^[a-zA-Z][a-zA-Z0-9_.-]{0,95}$')
LIBRARY_ENTRYPOINT_MODULES = frozenset({
    'jiuwenswarm.software_factory.library_operations',
    'jiuwenswarm.software_factory.functional_operations',
})


def digest(value):
    raw = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def identifier(value):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise StageFailure('invalid_identity', 'Invalid workflow, part or instance identity')
    return value


def port_kind(port):
    return port if isinstance(port, str) else port.get('semantic_type', port.get('kind'))


def _implementation_files(source: Path, package_root: Path | None = None):
    """Pin local import and embedded-source dependencies, including lazy imports.

    This conservatively follows imports anywhere in the registered module, not
    only imports executed during one happy-path invocation. Native generation
    must therefore pin its native generator even during a CPU verification run.
    """
    root = (package_root or Path(__file__).parent).resolve()
    pending, records = [source.resolve(strict=True)], {}

    def local_module(path):
        for candidate in (path.with_suffix('.py'), path / '__init__.py'):
            if candidate.is_file():
                pending.append(candidate.resolve())
                return

    while pending:
        path = pending.pop()
        if not path.is_relative_to(root):
            raise StageFailure('untrusted_implementation', 'Implementation source escaped the factory package')
        relative = path.relative_to(root).as_posix()
        if relative in records:
            continue
        raw = path.read_bytes()
        records[relative] = digest(raw)
        try:
            tree = ast.parse(raw, filename=str(path))
        except SyntaxError as error:
            raise StageFailure('invalid_implementation', str(error)) from error
        for item in ast.walk(tree):
            if isinstance(item, ast.ImportFrom):
                if item.level:
                    base = path.parent
                    for _ in range(item.level - 1):
                        base = base.parent
                    if not base.is_relative_to(root):
                        continue
                    if item.module:
                        local_module(base.joinpath(*item.module.split('.')))
                    else:
                        for alias in item.names:
                            local_module(base / alias.name)
                elif item.module and item.module.startswith('jiuwenswarm.software_factory.'):
                    local_module(root.joinpath(*item.module.split('.')[2:]))
            elif isinstance(item, ast.Import):
                for alias in item.names:
                    if alias.name.startswith('jiuwenswarm.software_factory.'):
                        local_module(root.joinpath(*alias.name.split('.')[2:]))
            elif (isinstance(item, ast.Call) and isinstance(item.func, ast.Attribute)
                  and item.func.attr == 'with_name' and len(item.args) == 1
                  and isinstance(item.args[0], ast.Constant) and isinstance(item.args[0].value, str)):
                # core_codegen embeds native_build.py and oracle_validation.py
                # in the delivered engineering package instead of importing it.
                referenced = path.with_name(item.args[0].value)
                if referenced.suffix == '.py' and referenced.is_file():
                    pending.append(referenced.resolve())
    return dict(sorted(records.items()))


def _python_source(entrypoint):
    import importlib
    import inspect
    module_name, separator, function = entrypoint.partition(':')
    if (not separator or module_name not in LIBRARY_ENTRYPOINT_MODULES
            or not re.fullmatch('[a-z][a-z0-9_]*', function)):
        raise StageFailure('untrusted_entrypoint', entrypoint)
    target = getattr(importlib.import_module(module_name), function, None)
    if not callable(target):
        raise StageFailure('missing_entrypoint', entrypoint)
    source = inspect.getsourcefile(target)
    if not source:
        raise StageFailure('missing_implementation_source', entrypoint)
    return Path(source).resolve(strict=True)


def _verify_python_implementation(implementation):
    expected = implementation.get('source_files')
    if not isinstance(expected, dict) or not expected:
        raise StageFailure('implementation_unpinned', 'Re-register this workflow with its implementation dependency hashes')
    try:
        source = _python_source(implementation.get('entrypoint', ''))
        if digest(source.read_bytes()) != implementation.get('implementation_sha256'):
            raise StageFailure('implementation_changed', 'Registered Python implementation bytes changed')
        if _implementation_files(source) != expected:
            raise StageFailure('implementation_changed', 'Registered Python implementation dependency bytes changed')
    except OSError as error:
        raise StageFailure('implementation_changed', 'A pinned implementation dependency is missing or unreadable') from error


class WorkflowLibrary:
    def __init__(self, root: Path | str):
        self.root = Path(root).resolve()
        self.definitions = self.root / 'definitions'
        self.definitions.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        if not (self.root / 'index.json').exists():
            write_json(self.root / 'index.json', {'schema': 'factory.workflow-library.v1', 'workflows': []})

    def _canonical(self, bundle):
        value = deepcopy(bundle)
        value.pop('version', None)
        for part in value['subworkflows']:
            part['implementation'].pop('prompt_path', None)
        return value

    def register(self, supplied: dict) -> dict:
        """Publish a definition after checking real declared implementation bytes."""
        value = deepcopy(supplied)
        identifier(value.get('id'))
        if not isinstance(value.get('subworkflows'), list) or not value['subworkflows']:
            raise StageFailure('invalid_definition', 'Workflow must declare executable subworkflows')
        seen = set()
        prompts = {}
        for part in value['subworkflows']:
            name = identifier(part.get('id'))
            if name in seen:
                raise StageFailure('duplicate_part', name)
            seen.add(name)
            for side in ('inputs', 'outputs'):
                if not isinstance(part.get(side), dict):
                    raise StageFailure('invalid_ports', f'{name}.{side} must be named contracts')
                for key, port in part[side].items():
                    identifier(key)
                    if (not isinstance(port, dict) or not isinstance(port.get('semantic_type'), str)
                            or not port['semantic_type']):
                        raise StageFailure('invalid_ports', f'{name}.{key} requires an object with a semantic_type')
                    if 'required' in port and not isinstance(port['required'], bool):
                        raise StageFailure('invalid_ports', f'{name}.{key}.required must be boolean')
            if not part['outputs']:
                raise StageFailure('invalid_ports', f'{name} has no actual outputs')
            implementation = part.get('implementation', {})
            kind = implementation.get('type')
            if kind == 'python':
                entry = implementation.get('entrypoint', '')
                source = _python_source(entry)
                implementation['implementation_sha256'] = digest(source.read_bytes())
                implementation['source_path'] = str(source)
                implementation['source_sha256'] = implementation['implementation_sha256']
                implementation['source_files'] = _implementation_files(source)
            elif kind == 'agent':
                source = Path(implementation['prompt_path']).resolve(strict=True)
                allowed = Path(__file__).parent / 'workflow_prompts'
                if not source.is_relative_to(allowed.resolve()):
                    raise StageFailure('untrusted_prompt', 'Instruction must come from the factory prompt bundle')
                raw = source.read_bytes()
                if not raw.strip() or len(raw) > 128_000:
                    raise StageFailure('invalid_prompt', name)
                prompts[name] = raw
                implementation['prompt_sha256'] = digest(raw)
            elif kind == 'cc':
                raise StageFailure('unsupported_executor', 'CC declarations require a registered CC runtime adapter before execution')
            else:
                raise StageFailure('unknown_implementation', str(kind))
        if 'composition' in value:
            from .workflow_imports import validate_composition
            try:
                value['composition'] = validate_composition(value['subworkflows'], value['composition'])
            except ValueError as error:
                raise StageFailure('invalid_parent_composition', str(error)) from error
        value['schema'] = 'factory.workflow-bundle.v1'
        value['version'] = 'sha256:' + digest(self._canonical(value))
        target = self.definitions / value['id'] / value['version'].split(':')[1]
        with self.lock:
            target.mkdir(parents=True, exist_ok=True)
            for part in value['subworkflows']:
                if part['id'] in prompts:
                    path = target / (part['id'] + '.md')
                    path.write_bytes(prompts[part['id']])
                    part['implementation']['prompt_path'] = str(path)
            manifest = target / 'workflow.json'
            if manifest.exists() and json.loads(manifest.read_text()) != value:
                raise StageFailure('immutable_definition_conflict', value['id'])
            write_json(manifest, value)
            index = json.loads((self.root / 'index.json').read_text())
            index['workflows'] = [row for row in index['workflows'] if row['id'] != value['id']]
            index['workflows'].append({'id': value['id'], 'version': value['version']})
            write_json(self.root / 'index.json', index)
        return self.get(value['id'], value['version'])

    def get(self, workflow_id, version=None):
        identifier(workflow_id)
        if version is None:
            index = json.loads((self.root / 'index.json').read_text())
            row = next((r for r in index['workflows'] if r['id'] == workflow_id), None)
            if row is None:
                raise StageFailure('unknown_workflow', workflow_id)
            version = row['version']
        if not isinstance(version, str) or not re.fullmatch(r'sha256:[a-f0-9]{64}', version):
            raise StageFailure('invalid_version', str(version))
        path = self.definitions / workflow_id / version.split(':')[1] / 'workflow.json'
        if not path.is_file():
            raise StageFailure('unknown_workflow_version', workflow_id)
        value = json.loads(path.read_text())
        if 'sha256:' + digest(self._canonical(value)) != version:
            raise StageFailure('definition_changed', workflow_id)
        for part in value['subworkflows']:
            impl = part['implementation']
            if impl['type'] == 'python':
                _verify_python_implementation(impl)
            elif impl['type'] == 'agent':
                prompt = Path(impl['prompt_path']).resolve(strict=True)
                if not prompt.is_relative_to(path.parent) or digest(prompt.read_bytes()) != impl['prompt_sha256']:
                    raise StageFailure('instruction_changed', part['id'])
        return value

    def list(self):
        index = json.loads((self.root / 'index.json').read_text())
        return [self.get(row['id'], row['version']) for row in index['workflows']]

    def search(self, query: str):
        words = set(re.findall(r'[a-z0-9_]+', query.lower()))
        rows = []
        for workflow in self.list():
            text = json.dumps(workflow).lower()
            score = sum(word in text for word in words)
            rows.append((score, workflow))
        return [value for _, value in sorted(rows, key=lambda row: (-row[0], row[1]['id']))]

    def resolve(self, workflow_id, version, subworkflow_id):
        # Latest is a browser convenience, never an executable graph pin.
        if not isinstance(version, str) or not re.fullmatch(r'sha256:[a-f0-9]{64}', version):
            raise StageFailure('invalid_version', 'Task Graph nodes require an explicit immutable workflow version')
        bundle = self.get(workflow_id, version)
        result = next((part for part in bundle['subworkflows'] if part['id'] == subworkflow_id), None)
        if result is None:
            raise StageFailure('unknown_subworkflow', f'{workflow_id}/{subworkflow_id}')
        return deepcopy(result)

    def read_source(self, workflow_id, version, path):
        workflow = self.get(workflow_id, version)
        checkout = Path(workflow['source']['checkout']).resolve(strict=True)
        raw = Path(path)
        candidate = (raw if raw.is_absolute() else checkout / raw).resolve(strict=True)
        prompt_roots = [Path(part['implementation']['prompt_path']).resolve() for part in workflow['subworkflows']
                        if part['implementation']['type'] == 'agent']
        pinned_files = {}
        package = Path(__file__).parent.resolve()
        for part in workflow['subworkflows']:
            for relative, expected in part['implementation'].get('source_files', {}).items():
                pinned_files[(package / relative).resolve()] = expected
        source = workflow['source']
        if source.get('decomposition_path') and source.get('decomposition_sha256'):
            pinned_files[Path(source['decomposition_path']).resolve()] = source['decomposition_sha256']
        if not candidate.is_relative_to(checkout) and candidate not in prompt_roots and candidate not in pinned_files:
            raise StageFailure('source_scope_violation', 'File is outside the pinned source/instruction/implementation bundle')
        if candidate.is_relative_to(checkout) and '.git' in candidate.relative_to(checkout).parts:
            raise StageFailure('source_scope_violation', 'Git private metadata is not source evidence')
        decomposition = Path(source['decomposition_path']).resolve() if source.get('decomposition_path') else None
        limit = 2_000_000 if candidate == decomposition and candidate in pinned_files else 256_000
        if not candidate.is_file() or candidate.stat().st_size > limit:
            raise StageFailure('source_not_readable', 'Requested source exceeds its bounded read limit')
        if candidate.is_relative_to(checkout) and re.fullmatch(r'[a-f0-9]{40}',str(source.get('revision',''))):
            import subprocess
            relative = candidate.relative_to(checkout).as_posix()
            result = subprocess.run(['git','-C',str(checkout),'show',source['revision']+':'+relative],
                                    capture_output=True,timeout=30)
            if result.returncode:
                raise StageFailure('source_not_readable','File is not present at the registered source commit')
            raw = result.stdout
            if len(raw)>limit:
                raise StageFailure('source_not_readable','Pinned source exceeds its bounded read limit')
        else:
            raw = candidate.read_bytes()
        if candidate in pinned_files and digest(raw) != pinned_files[candidate]:
            raise StageFailure('implementation_changed', 'Pinned source bytes have changed')
        return {'path': str(candidate), 'content': raw.decode('utf-8'), 'sha256': digest(raw)}


def _check_reused_source(artifact, task):
    if artifact.get('kind') not in {'source.algorithm','source.project'}:
        return
    path = Path(artifact['path']).resolve(strict=True)
    raw = path.read_bytes()
    if digest(raw) != artifact['sha256']:
        raise StageFailure('artifact_changed', 'Reused source artifact changed after publication')
    try:
        value = json.loads(raw)
        if artifact['kind'] == 'source.algorithm':
            if value['schema'] != 'strata.core.ir.v1':
                raise ValueError('Invalid algorithm schema')
            records = [value['kernels'][identity] for identity in value['selected']]
            revision = value['commit_sha']
        else:
            from .library_operations import _checked_project
            source = _checked_project(value)
            if 'project.json' not in value['files']:
                raise ValueError('Project metadata is not hash-pinned')
            metadata = json.loads((source / 'project.json').read_text())
            records = metadata['operations']
            revision = value['source_commit']
        if not records or not all(isinstance(record,dict) for record in records):
            raise ValueError('Source operations must be nonempty typed records')
        provided = {record.get(key) for record in records
                    for key in ('id','source_id','name','operation','category') if record.get(key)}
        demands = task.get('parameters',{}).get('operations',[])
        if set(demands) - provided:
            raise StageFailure('task_operation_mismatch',
                               'Reused source does not implement required operations: ' + ', '.join(sorted(set(demands)-provided)))
        requested_revision = task.get('source',{}).get('revision') or task.get('revision')
        if requested_revision and requested_revision != revision:
            raise StageFailure('task_revision_mismatch','Reused source does not match the required source commit')
    except (ValueError,KeyError,TypeError) as error:
        raise StageFailure('invalid_reused_source','Reused source content is not a valid source-bound artifact') from error


def admit_graph(library: WorkflowLibrary, proposal: dict, task: dict, artifacts: list[dict] | None = None):
    """Resolve a model proposal to executable definitions; never trust model paths."""
    graph = deepcopy(proposal.get('graph', proposal))
    import jsonschema
    schema_path = Path(__file__).with_name('schemas') / 'task-graph-proposal.schema.json'
    try:
        jsonschema.validate(graph, json.loads(schema_path.read_text()))
    except jsonschema.ValidationError as error:
        raise StageFailure('invalid_graph', 'Invalid Task Graph proposal: ' + error.message) from error
    nodes = graph.get('nodes')
    if not isinstance(nodes, list) or not nodes or len(nodes) > 40:
        raise StageFailure('invalid_graph', 'Propose between 1 and 40 actual tasks')
    available = {a['id']: a for a in artifacts or []}
    external = {}
    for key, value in graph.get('inputs', {}).items():
        art_id = value if isinstance(value, str) else value.get('artifact_id', value.get('id'))
        if art_id not in available:
            raise StageFailure('unknown_input_artifact', str(art_id))
        _check_reused_source(available[art_id], task)
        external[key] = deepcopy(available[art_id])
    lookup, parts, edges = {}, {}, []
    for node in nodes:
        identifier(node.get('id'))
        if node['id'] in lookup:
            raise StageFailure('duplicate_task', node['id'])
        ref = node.get('workflow', {})
        part = library.resolve(ref.get('id'), ref.get('version'), node.get('subworkflow'))
        requested_source = task.get('source',{})
        source = library.get(ref['id'],ref['version']).get('source',{})
        if (requested_source.get('repository') == source.get('repository')
                and requested_source.get('revision') and requested_source['revision'] != source.get('revision')):
            raise StageFailure('task_revision_mismatch','Selected source Workflow does not match required commit')
        lookup[node['id']], parts[node['id']] = node, part
        node['name'] = part['name']
        node['implementation_type'] = part['implementation']['type']
        node['origin'] = {'workflow': ref['id'], 'subworkflow': part['id'], 'version': ref['version']}
        defaults = part.get('default_parameters', {})
        parameters = node.get('parameters', {})
        if set(parameters) - set(defaults):
            raise StageFailure('undeclared_parameter', 'Only declared part parameters may be supplied: ' + node['id'])
        for key in ('checkout','source_dir','revision','commit','repository'):
            if key in parameters and parameters[key] != defaults[key]:
                raise StageFailure('source_pin_changed', 'Task Graph cannot change pinned source defaults')
        requested_operations = task.get('parameters', {}).get('operations')
        if requested_operations and 'demands' in part.get('default_parameters', {}):
            selected_demands = node.get('parameters', {}).get('demands', part['default_parameters']['demands'])
            if selected_demands != requested_operations:
                raise StageFailure('task_operation_mismatch',
                                   'Bind the Task Contract operations to this source extractor demands parameter')
        bindings = node.get('bindings', {})
        required = {name for name, port in part['inputs'].items() if isinstance(port,str) or port.get('required',True)}
        if required - bindings.keys() or bindings.keys() - part['inputs'].keys():
            raise StageFailure('unbound_input', node['id'] + ': bind declared required inputs exactly')
    for node in nodes:
        part = parts[node['id']]
        for port, binding in node.get('bindings', {}).items():
            if not isinstance(binding, dict) or set(binding) != {'node','port'}:
                raise StageFailure('invalid_binding', node['id'])
            producer, output = binding['node'], binding['port']
            if producer == '$input':
                if output not in external:
                    raise StageFailure('unknown_input_artifact', output)
                kind = external[output]['kind']
            else:
                if producer not in parts or output not in parts[producer]['outputs']:
                    raise StageFailure('unknown_output', f'{producer}.{output}')
                kind = port_kind(parts[producer]['outputs'][output])
                edges.append({'from':producer,'to':node['id'],'output':output,'input':port,'data':kind})
            if kind != port_kind(part['inputs'][port]):
                raise StageFailure('incompatible_artifact', f'{node["id"]}.{port}: {kind} cannot satisfy {port_kind(part["inputs"][port])}')
    from jiuwenswarm.research.binding import kahn_order
    from jiuwenswarm.research.contracts import ResearchError

    predecessors = {node_id: [] for node_id in lookup}
    for edge in edges:
        predecessors[edge['to']].append(edge['from'])
    try:
        linear = kahn_order([{'node_id': node_id, 'predecessors': dependencies}
                             for node_id, dependencies in predecessors.items()])
    except ResearchError as error:
        raise StageFailure('graph_cycle', 'Task dependencies contain a cycle') from error
    # Preserve the factory's recorded level-by-level ordering and lexical ties.
    layers = {}
    for node_id in linear:
        layers[node_id] = 1 + max((layers[parent] for parent in predecessors[node_id]), default=-1)
    ordered = [lookup[node_id] for node_id in sorted(linear, key=lambda node_id: (layers[node_id], node_id))]
    outputs = graph.get('outputs', {})
    if not outputs:
        raise StageFailure('missing_goals', 'Expose actual output ports for the requested deliverables')
    provided=set()
    for name,binding in outputs.items():
        if binding.get('node') not in parts or binding.get('port') not in parts[binding['node']]['outputs']:
            raise StageFailure('unknown_goal_output', name)
        provided.add(port_kind(parts[binding['node']]['outputs'][binding['port']]))
    missing=set(task.get('required_outputs',[]))-provided
    if missing:
        raise StageFailure('uncovered_deliverables','Required outputs not exposed: '+', '.join(sorted(missing)))
    graph.update(schema='factory.task-graph.v1',graph_revision=0,nodes=ordered,edges=edges,inputs=external,
                 task_contract=deepcopy(task),outputs=outputs)
    return graph
