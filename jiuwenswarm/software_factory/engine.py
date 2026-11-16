"""Artifact-goal planner and real, durable stage execution.

Stage selection is a backward contract search; the graph is not a task template.
Only a real failed attempt can trigger a search of repair declarations.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import threading
import time
import uuid
from copy import deepcopy

from .contracts import Artifact, Stage, StageBlocked, StageFailure, inspect_file


def now():
    return datetime.now(timezone.utc).isoformat()


def process_identity(pid):
    try:
        # Linux start ticks distinguish an owned process from a reused PID.
        return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[19]
    except (OSError, IndexError):
        return None


def atomic_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    temporary.replace(path)


class Context:
    def __init__(self, execution, node, attempt, inputs):
        self.execution, self.node, self.attempt = execution, node, attempt
        self.workspace = execution.directory / 'stages' / node['id'] / str(attempt['number'])
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.options = dict(execution.snapshot['request'])
        self.parameters = deepcopy(node.get('parameters', {}))
        for artifact in inputs.values():
            if artifact.kind == 'toolchain.cmake':
                toolchain = artifact.read_json()
                self.options.update({key: toolchain[key] for key in ('cmake', 'ninja', 'ctest')})

    def write_json(self, name: str, obj):
        path = self.workspace / name
        if not path.resolve().is_relative_to(self.workspace.resolve()):
            raise StageFailure('invalid_path', 'Stage output escaped its own workspace')
        atomic_json(path, obj)
        return path

    def consume_json(self, artifact):
        """Read a runtime-selected input and retain the actual delivery receipt."""
        stage = self.execution.stages[self.node['stage_id']]
        if artifact.kind not in stage.dynamic_inputs or self.execution.artifacts.get(artifact.id) != artifact:
            raise StageFailure('contract_invalid', 'Undeclared or unpublished dynamic input')
        producer = next(n for n in self.execution.snapshot['nodes'] if n['id'] == artifact.producer)
        if producer['status'] != 'verified':
            raise StageFailure('missing_artifact', 'Dynamic input producer has not verified its output')
        value = artifact.read_json()
        if not any(v['id'] == artifact.id for v in self.attempt['inputs']):
            self.attempt['inputs'].append(artifact.serializable())
        self.execution.add_edge(artifact.producer, self.node['id'], artifact.kind)
        self.execution.emit('artifact.consumed', self.node['id'], {'artifact': artifact.serializable(),
                            'attempt': self.attempt['number'], 'dynamic': True})
        return value

    def run_command(self, argv, cwd=None, timeout=300, env=None):
        if not argv or not isinstance(argv, (list, tuple)) or not all(isinstance(a, str) for a in argv):
            raise StageFailure('invalid_command', 'Commands must be a nonempty argv list; shell execution is disabled')
        directory = Path(cwd or self.workspace).resolve()
        from .provenance import verify_recipe, command_recipe
        verify_recipe(self.execution.recipe)
        index = len(self.attempt['commands']) + 1
        stdout_path, stderr_path = self.workspace / f'command-{index}.stdout', self.workspace / f'command-{index}.stderr'
        stdout_path.write_bytes(b'')
        stderr_path.write_bytes(b'')
        record = {'argv': list(argv), 'cwd': str(directory), 'started_at': now(), 'exit_code': None,
                  'stdout_path': str(stdout_path), 'stderr_path': str(stderr_path), 'stdout': '', 'stderr': ''}
        record['recipe'] = command_recipe(argv, self.execution.recipe, cwd=directory,
                                           env={**os.environ, **(env or {})})
        self.attempt['commands'].append(record)
        self.execution.emit('command.started', self.node['id'], {'command': record})
        started = time.monotonic()
        def capture(pipe, path, stream_name):
            with path.open('wb') as destination:
                while True:
                    chunk = pipe.read1(4096)
                    if not chunk:
                        break
                    destination.write(chunk)
                    destination.flush()
                    self.execution.emit('command.output', self.node['id'],
                        {'stream': stream_name, 'text': chunk.decode('utf-8', errors='replace'), 'command_index': index})
            pipe.close()
        try:
            process = subprocess.Popen(list(argv), cwd=directory, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       env={**os.environ, **(env or {})}, start_new_session=True)
            record['pid'] = process.pid
            readers = [threading.Thread(target=capture, args=(process.stdout, stdout_path, 'stdout'), daemon=True),
                       threading.Thread(target=capture, args=(process.stderr, stderr_path, 'stderr'), daemon=True)]
            for reader in readers:
                reader.start()
            try:
                record['exit_code'] = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                import signal
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                record['exit_code'] = process.returncode
                record['timeout'] = True
            for reader in readers:
                reader.join(timeout=10)
            if any(reader.is_alive() for reader in readers):
                raise StageFailure('process_pipe_incomplete', 'Process descendants kept output pipes open after exit')
        except FileNotFoundError as error:
            record['exit_code'] = 127
            stderr_path.write_text(str(error))
        record.update(finished_at=now(), duration_s=round(time.monotonic() - started, 6))
        record['stdout'] = stdout_path.read_text(errors='replace')[-16000:]
        record['stderr'] = stderr_path.read_text(errors='replace')[-16000:]
        for stream in ('stdout', 'stderr'):
            self.execution.publish_log(Path(record[f'{stream}_path']), self.node['id'], stream)
        self.execution.emit('command.finished', self.node['id'], {'command': record})
        if record['exit_code']:
            code = 'missing_toolchain' if record['exit_code'] == 127 and Path(argv[0]).name in {'cmake', 'ctest', 'ninja'} else 'command_failed'
            raise StageFailure(code, f'Command exited {record["exit_code"]}: {argv!r}', {'command': record})
        return record


class Execution:
    def __init__(self, directory: Path, request: dict, stages: list[Stage], run_id=None):
        self.directory = directory.resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.stages = {s.id: s for s in stages}
        self.artifacts: dict[str, Artifact] = {}
        self.lock = threading.RLock()
        self.changed = threading.Condition(self.lock)
        from .provenance import capture_recipe
        self.recipe = capture_recipe(self.directory, list(stages), request)
        recipe_digest = hashlib.sha256(json.dumps([(v['relative_path'], v['sha256']) for v in self.recipe['files']],
                                                  sort_keys=True).encode()).hexdigest()
        self.snapshot = {'id': run_id or directory.name, 'status': 'created', 'request': request,
                         'recipe': self.recipe, 'recipe_digest': recipe_digest,
                         'created_at': now(), 'updated_at': now(), 'executor': {'pid': os.getpid(), 'start_ticks': process_identity(os.getpid())}, 'nodes': [], 'edges': [], 'artifacts': [],
                         'graph_revisions': [], 'error': None, 'sequence': 0}
        self.events_path = self.directory / 'events.jsonl'
        self.save()

    def save(self):
        self.snapshot['updated_at'] = now()
        atomic_json(self.directory / 'run.json', self.snapshot)

    def emit(self, kind, node_id=None, payload=None):
        with self.lock:
            self.snapshot['sequence'] += 1
            event = {'sequence': self.snapshot['sequence'], 'time': now(), 'type': kind,
                     'node_id': node_id, 'payload': deepcopy(payload or {})}
            with self.events_path.open('a') as stream:
                stream.write(json.dumps(event, ensure_ascii=False) + '\n')
            self.save()
            self.changed.notify_all()
        return event

    def result(self):
        with self.lock:
            return deepcopy(self.snapshot)

    def graph_revision(self, reason):
        graph = {'revision': len(self.snapshot['graph_revisions']) + 1, 'time': now(), 'reason': reason,
                 'nodes': deepcopy(self.snapshot['nodes']), 'edges': deepcopy(self.snapshot['edges'])}
        self.snapshot['graph_revisions'].append(graph)
        self.emit('graph.updated', payload=graph)

    def compatible(self, stage):
        return not stage.backends or self.snapshot['request'].get('target_backend', 'ascend') in stage.backends

    def plan_kind(self, kind, visiting=None):
        visiting = set(visiting or ())
        if kind in visiting:
            raise StageFailure('contract_cycle', f'Capability contract cycle for {kind}')
        candidates = sorted((s for s in self.stages.values() if kind in s.outputs.values() and not s.repairs
                             and not s.selection_only and self.compatible(s)), key=lambda s: (s.cost, s.id))
        if not candidates:
            raise StageFailure('no_capability', f'No executable stage can produce {kind}')
        errors = []
        for stage in candidates:
            before_nodes, before_edges = deepcopy(self.snapshot['nodes']), deepcopy(self.snapshot['edges'])
            try:
                parents = [self.plan_kind(required, visiting | {kind}) for required in stage.inputs.values()]
                bindings = {name: {'node_id': parent['id'], 'kind': required,
                                   'port': next(key for key, value in self.stages[parent['stage_id']].outputs.items() if value == required)}
                            for (name, required), parent in zip(stage.inputs.items(), parents)}
                node = self.add_node(stage, input_bindings=bindings)
                for parent, required in zip(parents, stage.inputs.values()):
                    self.add_edge(parent['id'], node['id'], required)
                return node
            except StageFailure as error:
                self.snapshot['nodes'], self.snapshot['edges'] = before_nodes, before_edges
                errors.append(str(error))
        raise StageFailure('no_compatible_path', f'Cannot produce {kind}: {errors}')

    def add_node(self, stage, input_bindings=None, parameters=None, instance_id=None):
        bindings, parameters = deepcopy(input_bindings or {}), deepcopy(parameters or {})
        canonical = {}
        for name, binding in bindings.items():
            parent = next((n for n in self.snapshot['nodes'] if n['id'] == binding['node_id']), None)
            ports = [port for port, kind in self.stages[parent['stage_id']].outputs.items() if kind == binding['kind']] if parent else []
            canonical[name] = {'node_id': binding['node_id'], 'kind': binding['kind'],
                               'port': binding.get('port') or (ports[0] if len(ports) == 1 else None)}
            if len(ports) != 1:
                canonical[name]['artifact_id'] = binding.get('artifact_id')
        identity = hashlib.sha256(json.dumps({'stage': stage.serializable(), 'bindings': canonical,
                                             'recipe': self.snapshot.get('recipe_digest'),
                                             'parameters': parameters}, sort_keys=True).encode()).hexdigest()
        existing = next((n for n in self.snapshot['nodes'] if n.get('instance_key') == identity), None)
        if existing:
            return existing
        node = {'id': f'n{len(self.snapshot["nodes"]) + 1}', 'stage_id': stage.id, 'name': stage.name,
                'workflow_id': stage.workflow_id, 'subworkflow_id': stage.subworkflow_id,
                'status': 'pending', 'attempts': [], 'instance_key': identity,
                'instance_id': instance_id, 'input_bindings': bindings, 'parameters': parameters}
        self.snapshot['nodes'].append(node)
        return node

    def invoke_stage(self, stage_id, inputs, parameters=None, instance_id=None):
        """Compose and execute one real stage using exact verified input artifacts."""
        stage = self.stages[stage_id]
        if set(inputs) != set(stage.inputs):
            raise StageFailure('contract_invalid', f'{stage_id}: input ports do not match the executable declaration')
        bindings = {}
        for name, kind in stage.inputs.items():
            artifact = inputs[name]
            if self.artifacts.get(artifact.id) != artifact or artifact.kind != kind:
                raise StageFailure('contract_invalid', f'{stage_id}.{name}: unpublished or incompatible input')
            bindings[name] = {'node_id': artifact.producer, 'artifact_id': artifact.id, 'kind': kind,
                              'port': artifact.metadata.get('output_port')}
        node = self.add_node(stage, bindings, parameters, instance_id)
        from .workflow_definitions import WorkflowRegistry
        registry = WorkflowRegistry(list(self.stages.values()))
        origins = [v for v in registry.export_stage_refs() if v['stage_id'] == stage.id]
        if origins:
            selected = registry.expand(origins[0]['path'], instance_id=node['id'])
            node['workflow_path'] = origins[0]['path']
            node['workflow_selection'] = selected.serializable()
        for artifact in inputs.values():
            self.add_edge(artifact.producer, node['id'], artifact.kind)
        if node['status'] == 'verified':
            self.emit('stage.reused', node['id'], {'stage_id': stage.id, 'input_artifact_ids': [v.id for v in inputs.values()]})
        else:
            self.graph_revision(f'Composed {stage.id} from inspected input identities and parameters')
        self.execute_node(node)
        return {name: next(a for a in self.artifacts.values() if a.producer == node['id'] and a.kind == kind
                          and a.metadata.get('output_port') == name)
                for name, kind in stage.outputs.items()}

    def import_workflow(self, path, external_inputs=None, instance_id='main', parameters=None, registry=None):
        """Execute a registered parent or extract its nested executable stages."""
        from .workflow_definitions import WorkflowRegistry
        registry = registry or WorkflowRegistry(list(self.stages.values()))
        graph = registry.expand(path, instance_id=instance_id).serializable()
        external_inputs = dict(external_inputs or {})
        producers = {}
        for name, kind in graph['inputs'].items():
            if name in external_inputs:
                artifact = external_inputs[name]
                if artifact.kind != kind or self.artifacts.get(artifact.id) != artifact:
                    raise StageFailure('contract_invalid', f'Workflow external input {name} is not a published {kind}')
                producers[name] = {'node_id': artifact.producer, 'kind': kind, 'artifact_id': artifact.id,
                                   'port': artifact.metadata.get('output_port')}
            else:
                producer = self.plan_kind(kind)
                ports = [port for port, output_kind in self.stages[producer['stage_id']].outputs.items() if output_kind == kind]
                if len(ports) != 1:
                    raise StageFailure('ambiguous_output_port', f'External input {name} needs an explicit output port')
                producers[name] = {'node_id': producer['id'], 'kind': kind, 'port': ports[0]}
        imported = {}
        for declared in graph['nodes']:
            stage = self.stages[declared['stage_id']]
            bindings = {}
            for name, binding in declared['input_bindings'].items():
                bindings[name] = ({'node_id': imported[binding['node_id']]['id'], 'kind': binding['kind'], 'port': binding['port']}
                                  if binding['node_id'] else dict(producers[binding['port']]))
            node = self.add_node(stage, bindings, parameters=parameters, instance_id=declared['id'])
            node['workflow_path'] = path
            imported[declared['id']] = node
            for binding in bindings.values():
                self.add_edge(binding['node_id'], node['id'], binding['kind'])
        self.graph_revision(f'Expanded executable workflow selection {path}')
        outputs = {}
        for name, output in graph['outputs'].items():
            node = imported[output['node_id']]
            self.execute_node(node)
            outputs[name] = next(a for a in self.artifacts.values() if a.producer == node['id'] and a.kind == output['kind']
                                 and a.metadata.get('output_port') == output['port'])
        return outputs

    def add_edge(self, source, target, data):
        edge = {'from': source, 'to': target, 'data': data}
        if edge not in self.snapshot['edges']:
            self.snapshot['edges'].append(edge)

    def publish_log(self, path, producer, stream):
        raw = path.read_bytes()
        artifact = Artifact(f'a{len(self.artifacts)+1}', f'process.{stream}', str(path.resolve()),
                            hashlib.sha256(raw).hexdigest(), len(raw), producer, {'stream': stream})
        self.artifacts[artifact.id] = artifact
        self.snapshot['artifacts'].append(artifact.serializable())

    def inputs_for(self, stage, node):
        inputs = {}
        incoming = [e for e in self.snapshot['edges'] if e['to'] == node['id']]
        for name, kind in stage.inputs.items():
            binding = node.get('input_bindings', {}).get(name)
            producers = [binding['node_id']] if binding else [e['from'] for e in incoming if e['data'] == kind]
            candidates = [a for a in self.artifacts.values() if a.kind == kind and a.producer in producers
                          and (not binding or not binding.get('artifact_id') or binding['artifact_id'] == a.id)
                          and (not binding or not binding.get('port') or a.metadata.get('output_port') == binding['port'])]
            if len(candidates) != 1:
                raise StageFailure('missing_artifact', f'{stage.id} requires exactly one edge-bound actual artifact {kind}')
            artifact = candidates[0]
            producer = next(n for n in self.snapshot['nodes'] if n['id'] == artifact.producer)
            declaration = self.stages[producer['stage_id']]
            output_name = artifact.metadata.get('output_port')
            if output_name is None:
                ports = [key for key, output_kind in declaration.outputs.items() if output_kind == kind]
                if len(ports) != 1:
                    raise StageFailure('ambiguous_output_port', f'{artifact.id} has no unique output port')
                output_name = ports[0]
            if declaration.outputs.get(output_name) != kind:
                raise StageFailure('contract_invalid', f'{artifact.id}: output port identity does not match its declared contract')
            digest, _, _ = inspect_file(Path(artifact.path), kind, declaration.validators.get(output_name))
            if digest != artifact.sha256:
                raise StageFailure('artifact_changed', f'Input {artifact.id} changed since verification')
            inputs[name] = artifact
        # Recovery dependencies supply real products; never borrow newest global state.
        for edge in incoming:
            if edge['data'] == 'toolchain.cmake':
                candidates = [a for a in self.artifacts.values() if a.kind == edge['data'] and a.producer == edge['from']]
                if len(candidates) != 1:
                    raise StageFailure('missing_artifact', 'Recovery toolchain artifact is absent or ambiguous')
                artifact = candidates[0]
                digest, _, _ = inspect_file(Path(artifact.path), artifact.kind,
                    self.stages[next(n['stage_id'] for n in self.snapshot['nodes'] if n['id'] == artifact.producer)].validators.get('toolchain'))
                if digest != artifact.sha256:
                    raise StageFailure('artifact_changed', artifact.id)
                inputs['toolchain'] = artifact
        return inputs

    def execute_node(self, node):
        if node['status'] == 'verified':
            return
        if node['status'] == 'blocked' and node.get('dependency_error'):
            previous = node['dependency_error']
            raise StageBlocked(previous['code'], previous['message'], previous.get('details'))
        if node['status'] in {'failed', 'blocked'} and node['attempts']:
            previous = node['attempts'][-1]['error']
            failure = StageBlocked if node['status'] == 'blocked' else StageFailure
            raise failure(previous['code'], previous['message'], previous.get('details'))
        unavailable = []
        for edge in list(self.snapshot['edges']):
            if edge['to'] == node['id']:
                parent = next(n for n in self.snapshot['nodes'] if n['id'] == edge['from'])
                try:
                    self.execute_node(parent)
                except StageFailure as error:
                    unavailable.append((parent, error))
        if unavailable:
            parent, error = unavailable[0]
            dependency_error = {'code': error.code, 'message': str(error),
                                'details': {'blocked_by': parent['id'], 'upstream': error.details}}
            node.update(status='blocked', blocked_by=[p['id'] for p, _ in unavailable],
                        dependency_error=dependency_error)
            # This is a real scheduling decision, not an execution attempt.
            # No command, attempt number, timestamped exit or success is invented.
            self.emit('stage.blocked', node['id'], {'reason': 'upstream_dependency_unavailable',
                      'blocked_by': node['blocked_by'], 'error': dependency_error, 'executed': False})
            raise StageBlocked(error.code, str(error), dependency_error['details'])
        stage = self.stages[node['stage_id']]
        while len(node['attempts']) < 2:
            attempt = {'number': len(node['attempts']) + 1, 'status': 'running', 'started_at': now(),
                       'finished_at': None, 'commands': [], 'inputs': [], 'outputs': [], 'error': None, 'verification': None}
            node['attempts'].append(attempt)
            node['status'] = 'running'
            self.emit('stage.started', node['id'], {'attempt': attempt['number'], 'stage': stage.serializable()})
            try:
                from .provenance import verify_recipe
                verify_recipe(self.recipe)
                inputs = self.inputs_for(stage, node)
                attempt['inputs'] = [a.serializable() for a in inputs.values()]
                context = Context(self, node, attempt, inputs)
                outputs = stage.execute(context, inputs)
                if set(outputs) != set(stage.outputs):
                    raise StageFailure('contract_invalid', f'{stage.id}: declared output names {list(stage.outputs)}, got {list(outputs)}')
                inspected = []
                for name, kind in stage.outputs.items():
                    path = Path(outputs[name]).resolve(strict=True)
                    if not path.is_relative_to(self.directory):
                        raise StageFailure('invalid_path', f'Stage output escaped the run directory: {path}')
                    digest, size, metadata = inspect_file(path, kind, stage.validators.get(name))
                    artifact = Artifact(f'a{len(self.artifacts)+len(inspected)+1}', kind, str(path), digest, size, node['id'],
                                        {**metadata, 'output_port': name})
                    inspected.append(artifact.serializable())
                # Publish atomically only after every declared output passed validation.
                for value in inspected:
                    artifact = Artifact(**value)
                    self.artifacts[artifact.id] = artifact
                    self.snapshot['artifacts'].append(value)
                attempt.update(outputs=inspected, status='verified', finished_at=now(),
                               verification={'outcome': 'pass', 'checks': ['actual file', 'sha256 integrity'] + (['declared content contract'] if all(stage.validators.get(name) for name in stage.outputs) else [])})
                node['status'] = 'verified'
                self.emit('stage.verified', node['id'], {'attempt': attempt['number'], 'outputs': inspected})
                return
            except Exception as caught:
                error = caught if isinstance(caught, StageFailure) else StageFailure('stage_exception', f'{type(caught).__name__}: {caught}')
                attempt.update(status='blocked' if isinstance(error, StageBlocked) else 'failed', finished_at=now(),
                               error={'code': error.code, 'message': str(error), 'details': error.details},
                               verification={'outcome': 'blocked' if isinstance(error, StageBlocked) else 'fail'})
                node['status'] = attempt['status']
                self.emit('stage.' + attempt['status'], node['id'], {'attempt': attempt['number'], 'error': attempt['error']})
                if error.code == 'schema_mismatch':
                    self.graph_revision(f'Observed real schema mismatch in {stage.id}; original input binding retained')
                    self.emit('schema.mismatch', node['id'], {'error': attempt['error']})
                remedies = sorted((s for s in self.stages.values() if error.code in s.repairs and self.compatible(s)
                                   and not any(n['stage_id'] == s.id and n['status'] != 'verified' for n in self.snapshot['nodes'])), key=lambda s: (s.cost, s.id))
                if len(node['attempts']) >= 2 or not remedies:
                    raise error
                # Retrieval uses the real failure code and matching repair contracts.
                repair = remedies[0]
                self.emit('recovery.retrieved', node['id'], {'failure': attempt['error'], 'stage': repair.serializable()})
                parents = [self.plan_kind(required) for required in repair.inputs.values()]
                remedy_bindings = {name: {'node_id': parent['id'], 'kind': required}
                                    for (name, required), parent in zip(repair.inputs.items(), parents)}
                remedy = self.add_node(repair, input_bindings=remedy_bindings)
                for parent, required in zip(parents, repair.inputs.values()):
                    self.add_edge(parent['id'], remedy['id'], required)
                for produced in repair.outputs.values():
                    if produced in stage.inputs.values():
                        # A checked adapter replaces this consumer's input binding;
                        # the original producer remains connected to the adapter.
                        self.snapshot['edges'] = [edge for edge in self.snapshot['edges']
                            if not (edge['to'] == node['id'] and edge['data'] == produced)]
                        for name, kind in stage.inputs.items():
                            if kind == produced:
                                node.setdefault('input_bindings', {})[name] = {'node_id': remedy['id'], 'kind': kind}
                    self.add_edge(remedy['id'], node['id'], produced)
                self.emit('adapter.injected' if any(kind in stage.inputs.values() for kind in repair.outputs.values()) else 'recovery.inserted',
                    node['id'], {'stage_id': repair.id, 'repair_node_id': remedy['id'], 'failure_code': error.code})
                self.graph_revision(f'Real attempt {attempt["number"]} failed ({error.code}); bound checked recovery stage {repair.id}')
                self.execute_node(remedy)
        raise StageFailure('retry_exhausted', stage.id)

    def run(self):
        self.snapshot['status'] = 'planning'
        self.snapshot['goal_results'] = {}
        self.emit('run.planning', payload={'goals': self.snapshot['request']['goals']})
        goals, errors = [], []
        for kind in self.snapshot['request']['goals']:
            try:
                goals.append((kind, self.plan_kind(kind)))
            except StageFailure as error:
                errors.append(error)
                self.snapshot['goal_results'][kind] = {'status': 'failed', 'error': {'code': error.code, 'message': str(error)}}
                self.emit('goal.failed', payload={'goal': kind, 'error': self.snapshot['goal_results'][kind]['error']})
        # Observational assessment stages read the settled outcomes of all work
        # goals, including failures. They have no success dependency on blocked
        # work, so a missing device cannot suppress an honest value assessment.
        goals.sort(key=lambda item: self.stages[item[1]['stage_id']].defer_until_goals_settle)
        self.graph_revision('Selected executable stages by requested output contracts')
        self.snapshot['status'] = 'running'
        self.emit('run.started')
        for kind, node in goals:
            try:
                self.execute_node(node)
                self.snapshot['goal_results'][kind] = {'status': 'verified', 'node_id': node['id']}
                self.emit('goal.verified', node['id'], {'goal': kind})
            except Exception as caught:
                error = caught if isinstance(caught, StageFailure) else StageFailure('execution_exception', str(caught))
                errors.append(error)
                status = 'blocked' if isinstance(error, StageBlocked) else 'failed'
                self.snapshot['goal_results'][kind] = {'status': status, 'error': {'code': error.code, 'message': str(error), 'details': error.details}}
                self.emit('goal.' + status, node['id'], {'goal': kind, 'error': self.snapshot['goal_results'][kind]['error']})
        # A stream reader must never observe a terminal status before its final
        # durable event. Otherwise it can close after goal.verified and drop the
        # real run.completed/run.failed frame. Publish both under the same lock.
        with self.lock:
            if errors:
                status = 'failed' if any(not isinstance(e, StageBlocked) for e in errors) else 'blocked'
                self.snapshot['status'] = status
                self.snapshot['error'] = {'code': 'goals_incomplete', 'message': 'One or more requested goals did not verify.',
                                          'details': {'goals': self.snapshot['goal_results']}}
                self.emit('run.' + status, payload={'error': self.snapshot['error']})
            else:
                self.snapshot['status'] = 'completed'
                self.emit('run.completed', payload={'goals': self.snapshot['request']['goals']})
        return self.result()


class FactoryService:
    def __init__(self, root: str | Path, stages: list[Stage] | None = None):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        if stages is None:
            from .catalog import stage_catalog
            stages = stage_catalog()
        self.stages = stages
        self.executions = {}
        self.lock = threading.RLock()
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='software-factory')

    def catalog(self):
        from .workflow_definitions import WorkflowRegistry
        registry = WorkflowRegistry(self.stages)
        stages = [s.serializable() for s in self.stages]
        parents = {}
        for s in self.stages:
            parents.setdefault((s.workflow_id, s.subworkflow_id), []).append(s.serializable())
        return {'groups': [{'id': value, 'name': value.replace('_', ' ').title()} for value in sorted({s.workflow_id for s in self.stages})],
                'subworkflows': [{'id': sub, 'name': sub.replace('_', ' ').title(), 'workflow_id': workflow, 'stages': members}
                                 for (workflow, sub), members in parents.items()], 'stages': stages,
                'workflows': registry.export(), 'workflow_stage_refs': registry.export_stage_refs(),
                'goals': sorted({kind for s in self.stages if not s.repairs and not s.selection_only for kind in s.outputs.values()})}

    def create(self, request: dict, background=True):
        from .task_contract import compile_goals
        request = compile_goals(deepcopy(request))
        identifier = uuid.uuid4().hex
        execution = Execution(self.root / identifier, request, self.stages, identifier)
        self.executions[identifier] = execution
        if background:
            self.pool.submit(execution.run)
            return execution.result()
        return execution.run()

    def get(self, run_id):
        self._validate_id(run_id)
        if run_id in self.executions:
            return self.executions[run_id].result()
        with self.lock:
            path = self.root / run_id / 'run.json'
            run = json.loads(path.read_text())
            executor = run.get('executor', {})
            alive = executor.get('start_ticks') is not None and process_identity(executor.get('pid')) == executor.get('start_ticks')
            if run['status'] in {'created', 'planning', 'running'} and not alive:
                # A new service cannot claim that an old worker is still managed.
                # Child PIDs may remain alive or be reused: neither kill nor replay blindly.
                error = {'code': 'executor_state_unknown', 'message':
                         'Service restarted without this execution worker. Reconcile recorded processes before rerunning.',
                         'details': {'process_exit_status': 'unknown'}}
                run['status'], run['error'], run['updated_at'] = 'blocked', error, now()
                for node in run['nodes']:
                    if node['status'] == 'running':
                        node['status'] = 'blocked'
                        if node['attempts']:
                            node['attempts'][-1].update(status='blocked', error=error)
                run['sequence'] += 1
                event = {'sequence': run['sequence'], 'time': now(), 'type': 'service.recovery_required',
                         'node_id': None, 'payload': {'error': error}}
                with (path.parent / 'events.jsonl').open('a') as stream:
                    stream.write(json.dumps(event) + '\n')
                atomic_json(path, run)
            return run

    @staticmethod
    def _validate_id(run_id):
        if len(run_id) != 32 or any(c not in '0123456789abcdef' for c in run_id):
            raise FileNotFoundError('Unknown run')

    def events(self, run_id, after=0):
        execution = self.executions.get(run_id)
        lock = execution.lock if execution else threading.RLock()
        with lock:
            run = self.get(run_id)
            path = self.root / run_id / 'events.jsonl'
            events = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
            return {'events': [e for e in events if e['sequence'] > after], 'sequence': run['sequence'], 'status': run['status']}

    def wait_events(self, run_id, after=0, timeout=10):
        execution = self.executions.get(run_id)
        if execution:
            with execution.changed:
                execution.changed.wait_for(lambda: execution.snapshot['sequence'] > after or
                    execution.snapshot['status'] in {'completed', 'blocked', 'failed'}, timeout=timeout)
                return self.events(run_id, after)
        batch = self.events(run_id, after)
        if not batch['events'] and batch['status'] not in {'completed', 'blocked', 'failed'}:
            # Another live CLI process may own this durable run. Wait for actual
            # JSONL additions; this produces no synthetic execution events.
            threading.Event().wait(min(timeout, 1))
            batch = self.events(run_id, after)
        return batch

    def artifact_path(self, run_id, artifact_id):
        run = self.get(run_id)
        artifact = next((a for a in run['artifacts'] if a['id'] == artifact_id), None)
        if not artifact:
            raise FileNotFoundError('Unknown artifact')
        path = Path(artifact['path']).resolve(strict=True)
        if not path.is_relative_to(self.root / run_id) or not path.is_file():
            raise FileNotFoundError('Artifact escaped run directory')
        if hashlib.sha256(path.read_bytes()).hexdigest() != artifact['sha256']:
            raise StageFailure('artifact_changed', 'Artifact changed since verification')
        return path
