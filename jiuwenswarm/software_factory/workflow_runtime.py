"""Execute pinned Workflow Library parts and validate their actual file handoffs.

The Library is a definition store. A Task Graph contains invocation instances;
runtime attempts/events belong to this executor's separate owned run directory.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib
import json
from pathlib import Path
import re
import shutil
import sys
import threading
import traceback
import uuid

from jiuwenswarm.research.binding import kahn_order
from jiuwenswarm.research.contracts import ResearchError

from .contracts import StageBlocked, StageFailure
from .model_driver import CodexDriver, execute_process, redact, timestamp
from .workflow_library import LIBRARY_ENTRYPOINT_MODULES
from .workflow_scheduler import WorkflowScheduler


def _json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
    temporary.replace(path)


def _identity(value, label):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', value):
        raise StageFailure('invalid_identity', f'Invalid {label}')
    return value


def _file(path, *, owned=None):
    path = Path(path)
    if path.is_symlink():
        raise StageFailure('invalid_artifact', 'Artifact paths must not be symbolic links')
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise StageFailure('missing_artifact', f'Artifact file does not exist: {path}') from error
    if owned is not None and not resolved.is_relative_to(Path(owned).resolve()):
        raise StageFailure('artifact_escape', 'Published output is outside the node workspace')
    if not resolved.is_file() or not resolved.stat().st_size:
        raise StageFailure('invalid_artifact', f'Expected a nonempty regular file: {resolved}')
    raw = resolved.read_bytes()
    return resolved, hashlib.sha256(raw).hexdigest(), len(raw)


def _contract_file(path, contract):
    """Validate declared content constraints, not just the name of a schema."""
    schema = contract.get('json_schema') or contract.get('schema')
    if schema or contract.get('format') == 'json':
        try:
            value = json.loads(Path(path).read_text(encoding='utf-8'))
        except (ValueError, UnicodeDecodeError) as error:
            raise StageFailure('contract_invalid', f'{Path(path).name} is not valid JSON') from error
        if schema:
            import jsonschema
            try:
                jsonschema.validate(value, schema)
            except (jsonschema.ValidationError, jsonschema.SchemaError) as error:
                raise StageFailure('contract_invalid', f'Artifact content violates its declared schema: {error.message}') from error


def _executable(tool, parameters):
    """Resolve the same actual build tools the registered operations will use."""
    if not isinstance(tool, str) or not re.fullmatch(r'[A-Za-z0-9_.+-]+', tool):
        raise StageFailure('invalid_requirement', 'Executable requirements must name actual programs')
    resolved = shutil.which(tool)
    if resolved:
        return resolved
    if tool == 'python':
        return sys.executable
    if tool in {'cmake', 'ctest'}:
        from .library_operations import _cmake
        try:
            cmake = Path(_cmake(parameters))
            candidate = cmake if tool == 'cmake' else cmake.with_name('ctest')
            if candidate.is_file() and candidate.stat().st_mode & 0o111:
                return str(candidate)
        except RuntimeError:
            pass
    raise StageBlocked('missing_tool', f'Required executable is unavailable: {tool}')


class WorkflowContext:
    def __init__(self, execution, node, attempt, workspace):
        self.execution, self.node, self.attempt = execution, node, attempt
        self.workspace, self.run_dir = workspace, execution.directory

    def emit(self, kind, payload):
        return self.execution.emit(kind, {**payload, 'node_id': self.node['id']})

    def run_command(self, argv, cwd=None, timeout=300, env=None):
        directory = Path(cwd or self.workspace).resolve(strict=True)
        if not directory.is_relative_to(self.workspace.resolve()):
            raise StageFailure('command_escape', 'Commands must execute within their node workspace')
        index = len(self.attempt['commands']) + 1

        def observe(kind, payload):
            if kind == 'command.started':
                self.attempt['commands'].append(payload['command'])
            elif kind == 'command.finished':
                self.execution.publish_command_logs(self.node['id'], index, payload['command'])
                self.attempt['commands'][index - 1] = payload['command']
            self.emit(kind, {**payload, 'command_index': index})

        record = execute_process(argv, directory, self.workspace / '.commands' / str(index),
                                 emit=observe, timeout=timeout, env=env)
        if record['exit_code'] or record.get('timed_out') or record.get('stream_incomplete'):
            raise StageFailure('command_failed', f'Command exited {record["exit_code"]}: {record["argv"]}',
                               {'command': record})
        return record


class WorkflowBuilder:
    """Run the pinned Python/tool operation or the registered Agent instruction."""

    def __init__(self, driver, handlers):
        self.driver = driver
        self.handlers = handlers

    @staticmethod
    def required_executables(part):
        requirements = part.get('requirements', {})
        executables = requirements.get('executables')
        if executables is None:
            # Older cards described these host capabilities in the display-only
            # tools list. They have never been command names.
            executables = [tool for tool in requirements.get('tools', [])
                           if tool not in {'configured agent', 'filesystem'}]
        return executables

    def worker_info(self, part):
        implementation = part.get('implementation', {})
        worker_type = implementation.get('type')
        if worker_type == 'python':
            receipt = {'worker_type': 'python', 'builder': 'Python/tool builder',
                       'execution_reason': 'The pinned workflow uses a registered Python operation.'}
            if implementation.get('entrypoint'):
                receipt['entrypoint'] = implementation['entrypoint']
        elif worker_type == 'agent':
            receipt = {'worker_type': 'agent', 'builder': 'Agent builder',
                       'execution_reason': 'The pinned workflow uses a Markdown instruction executed by Codex.'}
            if implementation.get('prompt_path'):
                receipt['entrypoint'] = Path(implementation['prompt_path']).name
        else:
            return {'worker_type': 'unsupported', 'builder': 'Unsupported builder',
                    'execution_reason': 'The pinned workflow declares an unsupported implementation.'}
        executables = self.required_executables(part)
        if isinstance(executables, list) and executables and all(isinstance(tool, str) for tool in executables):
            receipt['required_tools'] = list(executables)
            receipt['execution_reason'] += ' Required tools: ' + ', '.join(executables) + '.'
        return receipt

    def invoke(self, part, context, inputs, parameters):
        implementation = part.get('implementation', {})
        executables = self.required_executables(part)
        if not isinstance(executables, list):
            raise StageFailure('invalid_requirement', 'Executable requirements must be a list')
        resolved = {tool: _executable(tool, parameters) for tool in executables}
        if resolved:
            context.attempt['resolved_tools'] = resolved
            context.emit('requirements.verified', {'executables': resolved})
        if implementation.get('type') == 'python':
            entrypoint = implementation.get('entrypoint', '')
            if self.handlers is not None and entrypoint in self.handlers:
                function = self.handlers[entrypoint]
            else:
                module, separator, function_name = entrypoint.partition(':')
                if (not separator or module not in LIBRARY_ENTRYPOINT_MODULES
                        or not re.fullmatch(r'[a-z][a-z0-9_]*', function_name)):
                    raise StageFailure('untrusted_entrypoint', 'Python entrypoint is not a registered library operation')
                function = getattr(importlib.import_module(module), function_name, None)
                if not callable(function):
                    raise StageFailure('missing_entrypoint', 'Registered library operation does not exist')
            return function(context, inputs, deepcopy(parameters))
        if implementation.get('type') != 'agent':
            raise StageFailure('unsupported_executor', 'A node requires a Python or Agent implementation')
        prompt_path = Path(implementation.get('prompt_path', ''))
        if not prompt_path.is_absolute() or not prompt_path.is_file():
            raise StageFailure('missing_prompt', 'The pinned Agent instruction file does not exist')
        instruction = prompt_path.read_text(encoding='utf-8')
        if (implementation.get('prompt_sha256')
                and hashlib.sha256(instruction.encode()).hexdigest() != implementation['prompt_sha256']):
            raise StageFailure('instruction_changed', 'Agent instruction bytes changed after definition resolution')
        expected = {port: spec for port, spec in part.get('outputs', {}).items()}
        prompt = ('Execute this registered Workflow Library part in the current workspace. '
                  'Read only the provided input copies and the local source/header/framework files '
                  'explicitly identified by those input manifests. Do not modify the referenced resources. '
                  'Do not access credentials or network services. '
                  'Keep every produced file inside the current workspace. Actually execute the required work; '
                  'do not invent execution results. Final response must be a JSON object only, '
                  'with format {"outputs": {"port": "relative/file/path"}}. '
                  'Every declared required output must exist and be nonempty.\n\n'
                  + instruction + '\n\nINPUT ARTIFACTS\n' + json.dumps(inputs, indent=2)
                  + '\n\nPARAMETERS\n' + json.dumps(parameters, indent=2)
                  + '\n\nOUTPUT CONTRACTS\n' + json.dumps(expected, indent=2))
        context.emit('agent.started', {'instruction_path': str(prompt_path),
                                      'instruction_sha256': hashlib.sha256(instruction.encode()).hexdigest()})
        agent_command_index = None

        def observe(kind, payload):
            nonlocal agent_command_index
            if kind == 'command.started':
                agent_command_index = len(context.attempt['commands'])
                context.attempt['commands'].append(payload['command'])
            elif kind == 'command.finished' and agent_command_index is not None:
                context.execution.publish_command_logs(context.node['id'], agent_command_index + 1, payload['command'])
                context.attempt['commands'][agent_command_index] = payload['command']
            context.emit(kind, payload)

        result = self.driver.run(prompt, context.workspace, emit=observe,
                                         model=implementation.get('model'),
                                         timeout=implementation.get('timeout', 300))
        context.attempt['model_invocation'] = result['invocation']
        response = result['text'].strip()
        if response.startswith('```json\n') and response.endswith('\n```'):
            response = response[8:-4]
        try:
            value = json.loads(response)
        except ValueError as error:
            raise StageFailure('agent_contract_invalid', 'Agent final response is not the required JSON object') from error
        if not isinstance(value, dict) or not isinstance(value.get('outputs'), dict):
            raise StageFailure('agent_contract_invalid', 'Agent response has no outputs object')
        context.emit('agent.finished', {'invocation': result['invocation']})
        return value['outputs']


class WorkflowExecutor:
    def __init__(self, library, root: Path, driver=None, *, handlers=None):
        self.library, self.root = library, Path(root).resolve()
        self.driver = driver or CodexDriver()
        # Explicit dependency injection is for isolated tests, never a path
        # supplied by a graph or an HTTP request.
        self.handlers = handlers
        self.builder = WorkflowBuilder(self.driver, self.handlers)

    def run(self, graph: dict | Path, *, run_id=None, emit=None):
        source = None
        if isinstance(graph, Path):
            source = (graph.name, graph.read_bytes())
            graph = json.loads(source[1])
        execution = _Run(self, graph, run_id or uuid.uuid4().hex, emit, source=source)
        return execution.run()


class _Run:
    def __init__(self, executor, graph, run_id, observer, *, source=None):
        self.executor, self.graph = executor, deepcopy(graph)
        self.observer, self.lock = observer, threading.RLock()
        self.directory = executor.root / _identity(run_id, 'run id')
        self.directory.mkdir(parents=True, exist_ok=False)
        self.parts, self.outputs = {}, {}
        self.snapshot = {'id': run_id, 'status': 'pending', 'created_at': timestamp(),
                         'updated_at': timestamp(), 'run_dir': str(self.directory),
                         'graph': deepcopy(graph), 'nodes': [], 'edges': [], 'artifacts': [],
                         'outputs': {}, 'sequence': 0, 'error': None}
        graph_path = self.directory / 'graph.json'
        if source is None:
            _json(graph_path, self.graph)
            source = (graph_path.name, graph_path.read_bytes())
        else:
            graph_path.write_bytes(source[1])
        self.graph_input = {'filename': source[0], 'sha256': hashlib.sha256(source[1]).hexdigest()}
        self._save()

    def _save(self):
        self.snapshot['updated_at'] = timestamp()
        _json(self.directory / 'run.json', self.snapshot)

    def emit(self, kind, payload):
        with self.lock:
            self.snapshot['sequence'] += 1
            event = {'sequence': self.snapshot['sequence'], 'time': timestamp(), 'type': kind,
                     'node_id': payload.get('node_id'), 'payload': deepcopy(payload)}
            with (self.directory / 'events.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + '\n')
            self._save()
            if self.observer:
                try:
                    self.observer(kind, deepcopy(event['payload']))
                except Exception:
                    # Loss of a subscriber cannot erase a real production run.
                    pass
            return event

    def validate(self):
        nodes = self.graph.get('nodes')
        if not isinstance(nodes, list) or not 1 <= len(nodes) <= 100:
            raise StageFailure('invalid_graph', 'A graph requires between one and 100 nodes')
        for node in nodes:
            identity = _identity(node.get('id'), 'node id')
            if identity in self.parts:
                raise StageFailure('invalid_graph', 'Node instance ids must be unique')
            workflow = node.get('workflow', {})
            if not all(isinstance(workflow.get(key), str) and workflow[key] for key in ('id', 'version')):
                raise StageFailure('invalid_graph', 'Every node must pin a library workflow id and version')
            part = self.executor.library.resolve(workflow['id'], workflow['version'], node.get('subworkflow'))
            self.parts[identity] = deepcopy(part)
            self.snapshot['nodes'].append({**deepcopy(node), 'name': part.get('name', node['subworkflow']),
                                           'status': 'pending', 'attempts': [], 'outputs': {}})
        by_id = {node['id']: node for node in nodes}
        dependencies = {}
        for node in nodes:
            part = self.parts[node['id']]
            bindings = node.get('bindings', {})
            if not isinstance(bindings, dict) or set(bindings) - set(part.get('inputs', {})):
                raise StageFailure('invalid_binding', 'Node binds an undeclared input port')
            dependencies[node['id']] = set()
            for port, contract in part.get('inputs', {}).items():
                if port not in bindings:
                    if contract.get('required', True):
                        raise StageFailure('missing_binding', f'{node["id"]}.{port} requires a binding')
                    continue
                binding = bindings[port]
                if not isinstance(binding, dict) or set(binding) != {'node', 'port'}:
                    raise StageFailure('invalid_binding', 'A binding identifies one producer instance and output port')
                producer, output = binding['node'], binding['port']
                if producer == '$input':
                    artifact = self.graph.get('inputs', {}).get(output)
                    if not isinstance(artifact, dict):
                        raise StageFailure('missing_artifact', f'Graph input {output} is absent')
                    kind = artifact.get('kind')
                else:
                    if producer not in by_id:
                        raise StageFailure('invalid_binding', f'Unknown producer node {producer}')
                    produced = self.parts[producer].get('outputs', {}).get(output)
                    if not produced:
                        raise StageFailure('invalid_binding', f'Unknown producer port {producer}.{output}')
                    kind = produced.get('semantic_type')
                    dependencies[node['id']].add(producer)
                    self.snapshot['edges'].append({'from': producer, 'output': output, 'to': node['id'],
                                                   'input': port, 'data': kind, 'status': 'pending'})
                if kind != contract.get('semantic_type'):
                    raise StageFailure('contract_mismatch', f'{node["id"]}.{port} requires {contract.get("semantic_type")}, received {kind}')
        try:
            kahn_order([{'node_id': key, 'predecessors': list(value)} for key, value in dependencies.items()])
        except ResearchError as error:
            raise StageFailure('dependency_cycle', 'Task Graph dependencies contain a cycle') from error
        self.dependency_check = f'{kahn_order.__module__}.{kahn_order.__name__}'
        if 'edges' in self.graph:
            fields = ('from', 'output', 'to', 'input', 'data')
            declared = self.graph['edges']
            if not isinstance(declared, list) or any(not isinstance(edge, dict) for edge in declared):
                raise StageFailure('invalid_edges', 'Task Graph edges must be a list of dependency links')
            expected = [{key: edge[key] for key in fields} for edge in self.snapshot['edges']]
            links = [{key: edge.get(key) for key in fields} for edge in declared]
            if len(links) != len(expected) or any(edge not in links for edge in expected):
                raise StageFailure('invalid_edges', 'Task Graph edges must match the pinned input bindings')
        for name, binding in self.graph.get('outputs', {}).items():
            if (not isinstance(binding, dict) or binding.get('node') not in self.parts
                    or binding.get('port') not in self.parts[binding['node']].get('outputs', {})):
                raise StageFailure('invalid_binding', f'Unknown graph output {name}')
        self.dependencies = dependencies

    def publish_command_logs(self, node_id, command_index, command):
        """Logs remain downloadable real artifacts even when the command fails."""
        for stream in ('stdout', 'stderr'):
            path = Path(command[stream + '_path'])
            if not path.is_file() or not path.stat().st_size:
                continue
            path, digest, size = _file(path, owned=self.directory)
            artifact = {'id': f'{self.snapshot["id"]}:{node_id}:command-{command_index}:{stream}',
                        'kind': 'execution.' + stream, 'path': str(path), 'sha256': digest,
                        'size': size, 'producer': node_id, 'port': stream}
            command[stream + '_artifact'] = artifact
            self.snapshot['artifacts'].append(artifact)
            self.emit('artifact.published', {'node_id': node_id, 'port': stream, 'artifact': artifact,
                                              'command_index': command_index, 'diagnostic': True})

    def inputs(self, node, attempt, workspace):
        inputs = {}
        for port, binding in node.get('bindings', {}).items():
            original = (self.graph['inputs'][binding['port']] if binding['node'] == '$input'
                        else self.outputs[binding['node']][binding['port']])
            path, digest, size = _file(original['path'])
            if digest != original.get('sha256') or size != original.get('size'):
                raise StageFailure('artifact_changed', f'Input {port} changed after publication')
            contract = self.parts[node['id']]['inputs'][port]
            if original.get('kind') != contract['semantic_type']:
                raise StageFailure('contract_mismatch', f'Input {port} has the wrong semantic type')
            _contract_file(path, contract)
            _identity(port, 'port')
            target_dir = workspace / 'inputs' / port
            target_dir.mkdir(parents=True)
            target = target_dir / path.name
            shutil.copyfile(path, target)
            if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise StageFailure('artifact_changed', f'Input {port} changed during delivery')
            target.chmod(0o444)
            inputs[port] = {**deepcopy(original), 'path': str(target), 'source_path': str(path)}
            attempt['inputs'][port] = inputs[port]
            self.emit('artifact.consumed', {'node_id': node['id'], 'port': port,
                                           'artifact': inputs[port], 'producer': binding['node']})
            for edge in self.snapshot['edges']:
                if edge['to'] == node['id'] and edge['input'] == port:
                    edge['status'] = 'verified'
                    self.emit('edge.updated', {'edge': deepcopy(edge)})
        return inputs

    def execute(self, node):
        part = self.parts[node['id']]
        attempt = {'number': len(node['attempts']) + 1, 'status': 'running', 'started_at': timestamp(),
                   'inputs': {}, 'outputs': {}, 'commands': [], 'error': None}
        node['status'] = 'running'
        node['attempts'].append(attempt)
        workspace = self.directory / 'nodes' / node['id'] / f'attempt-{attempt["number"]}'
        workspace.mkdir(parents=True)
        context = WorkflowContext(self, node, attempt, workspace)
        self.emit('node.started', {'node_id': node['id'], 'node': deepcopy(node)})
        try:
            part = self.current_part(node)
            inputs = self.inputs(node, attempt, workspace)
            defaults = deepcopy(part.get('default_parameters', {}))
            supplied = node.get('parameters', {})
            if not isinstance(supplied, dict):
                raise StageFailure('invalid_parameters', 'Node parameters must be an object')
            if set(supplied) - set(defaults):
                raise StageFailure('undeclared_parameter', 'Only registered part parameters may be supplied')
            for key in ('checkout', 'source_dir', 'revision', 'commit', 'repository'):
                if key in supplied and key in defaults and supplied[key] != defaults[key]:
                    raise StageFailure('source_pin_changed', f'Node cannot override the pinned source parameter {key}')
            produced = self.executor.builder.invoke(part, context, inputs, {**defaults, **deepcopy(supplied)})
            for port, artifact in inputs.items():
                _, digest, size = _file(artifact['path'], owned=workspace)
                if digest != artifact['sha256'] or size != artifact['size']:
                    raise StageFailure('input_mutated', f'Executor modified its delivered input {port}')
            contracts = part.get('outputs', {})
            if not isinstance(produced, dict) or set(produced) - set(contracts):
                raise StageFailure('contract_invalid', 'Executor returned undeclared output ports')
            verified = {}
            for port, contract in contracts.items():
                if port not in produced:
                    if contract.get('required', True):
                        raise StageFailure('missing_output', f'Required output {port} was not produced')
                    continue
                value = produced[port]
                if not isinstance(value, (str, Path)):
                    raise StageFailure('contract_invalid', 'An output must identify a real local file')
                candidate = Path(value)
                path, digest, size = _file(candidate if candidate.is_absolute() else workspace / candidate,
                                           owned=workspace)
                _contract_file(path, contract)
                verified[port] = {'id': f'{self.snapshot["id"]}:{node["id"]}:{attempt["number"]}:{port}',
                                  'kind': contract['semantic_type'], 'path': str(path), 'sha256': digest,
                                  'size': size, 'producer': node['id'], 'port': port}
            self.current_part(node)
            # Verify every output first. Partial output publication is not success.
            node['outputs'] = attempt['outputs'] = verified
            self.outputs[node['id']] = verified
            for port, artifact in verified.items():
                self.snapshot['artifacts'].append(artifact)
                self.emit('artifact.published', {'node_id': node['id'], 'port': port, 'artifact': artifact})
            node['status'] = attempt['status'] = 'verified'
            attempt['finished_at'] = timestamp()
            self.emit('node.verified', {'node_id': node['id'], 'node': deepcopy(node)})
        except Exception as error:
            node['status'] = attempt['status'] = 'blocked' if isinstance(error, StageBlocked) else 'failed'
            trace = redact(traceback.format_exc())
            (workspace / 'error.log').write_text(trace, encoding='utf-8')
            failure = {'code': getattr(error, 'code', 'execution_failed'), 'message': redact(str(error)),
                       'details': getattr(error, 'details', {}), 'traceback_path': str(workspace / 'error.log'),
                       'traceback': trace}
            attempt.update(error=failure, finished_at=timestamp())
            node['error'] = failure
            self.emit('node.' + node['status'], {'node_id': node['id'], 'node': deepcopy(node), 'error': failure})

    def current_part(self, node):
        """A long-running graph cannot inherit edited code or instructions."""
        ref = node['workflow']
        fresh = self.executor.library.resolve(ref['id'], ref['version'], node['subworkflow'])
        if fresh != self.parts[node['id']]:
            raise StageFailure('definition_changed', 'Pinned node definition changed during execution')
        return fresh

    def run(self):
        scheduler = None
        try:
            self.validate()
            self.snapshot['status'] = 'running'
            self.emit('graph.validated', {'graph': self.graph, 'nodes': self.snapshot['nodes'],
                                          'edges': self.snapshot['edges'],
                                          'checks': ['Pinned workflow versions', 'Input and output contracts',
                                                     'Dependency links']})
            nodes = self.snapshot['nodes']
            workers = {node['id']: self.executor.builder.worker_info(self.parts[node['id']]) for node in nodes}
            scheduler = WorkflowScheduler(self.graph, nodes, self.dependencies, workers, self.execute, self.emit,
                                          self.graph_input, self.dependency_check)
            scheduler.run()
            if all(node['status'] == 'verified' for node in nodes):
                self.snapshot['outputs'] = {port: self.outputs[binding['node']][binding['port']]
                                            for port, binding in self.graph.get('outputs', {}).items()}
                self.snapshot['status'] = 'verified'
            else:
                self.snapshot['status'] = 'failed' if any(node['status'] == 'failed' for node in nodes) else 'blocked'
        except Exception as error:
            self.snapshot['status'] = 'failed'
            self.snapshot['error'] = {'code': getattr(error, 'code', 'invalid_graph'), 'message': redact(str(error))}
        self.snapshot['finished_at'] = timestamp()
        if scheduler is not None:
            scheduler.finish(self.snapshot['status'])
        self.emit('run.' + self.snapshot['status'], {'status': self.snapshot['status'],
                                                    'outputs': self.snapshot['outputs'],
                                                    'error': self.snapshot['error']})
        return deepcopy(self.snapshot)
