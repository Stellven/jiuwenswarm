"""Explicit finite live Builder tool qualification, outside ordinary dispatch.

M1-I013. Missing dedicated external credential evidence blocks before launch.
Only the normal governed bridge may dispatch the one fixed probe. This module
does not register a provider, grant a Capsule effect or manufacture a runtime.
"""
from __future__ import annotations

import asyncio
import copy
from dataclasses import dataclass, replace
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import shlex
import socket
import stat
import time

from .bridge import GovernedBridge
from .builder_launcher import (BuilderCredentialLease, BuilderEvents, BuilderKernelJob, BuilderLauncher,
                               BuilderStage, _custody, _not_expired, _read, _record)
from .contracts import validate
from .executor import ExecutorBlocked, RestrictedExecutor
from .state import SQLiteRunStore, json_bytes


PROBE_COMMAND = '/usr/local/bin/python3 -I /resources/qualification_probe.py /resources/probe_inputs.json'
PROBE_PROMPT = ('This is an explicitly authorized infrastructure sandbox qualification with synthetic canaries, '
    'not a research experiment. Execute exactly one tool command, exactly as written below. '
    'Do not inspect files, run another command, install packages, edit files, request permission or use another tool. '
    'The fixed read-only probe writes one harmless marker in its authorized workspace and tests controlled denials. '
    'After the command, report its result concisely.\n' + PROBE_COMMAND + '\n')
PREFIX = 'AI4R_BUILDER_TOOL_PROBE:'
PROBE_PATH = Path(__file__).with_name('_builder_tool_probe.py')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def command_is_probe(command):
    if not isinstance(command, str):
        return False
    try:
        argv = shlex.split(command)
        expected = shlex.split(PROBE_COMMAND)
        return argv == expected or (len(argv) == 3 and argv[:2] in [
            ['/bin/bash', '-lc'], ['/bin/sh', '-c'], ['bash', '-lc'], ['sh', '-c']]
            and shlex.split(argv[2]) == expected)
    except ValueError:
        return False


class QualificationEvents(BuilderEvents):
    """Only an actual completed exact command event can contain probe evidence."""
    def __init__(self, tool_limit, nonce):
        super().__init__(tool_limit)
        self.nonce, self.probe_result = nonce, None

    @staticmethod
    def _classify(item):
        return ('qualification_probe', True) if item.get('type') == 'command_execution' and command_is_probe(item.get('command')) else ('prohibited_qualification_tool', False)

    def feed(self, line):
        reason = super().feed(line)
        if reason:
            return reason
        event = json.loads(line)
        item = event.get('item', {})
        if event.get('type') == 'item.completed' and item.get('type') == 'command_execution':
            if self.probe_result is not None or item.get('exit_code') != 0 or item.get('status') != 'completed':
                return self._stop('invalid_output')
            output = item.get('aggregated_output')
            if not isinstance(output, str) or not output.strip().startswith(PREFIX) or len(output.strip().splitlines()) != 1:
                return self._stop('invalid_output')
            try:
                value = json.loads(output.strip()[len(PREFIX):])
                validate_probe(value, self.nonce)
            except (ValueError, TypeError, KeyError, ExecutorBlocked):
                return self._stop('invalid_output')
            self.probe_result = value
        return self.stop_reason


def validate_probe(value, nonce):
    fields = {'schema', 'nonce', 'uid', 'gid', 'cap_eff', 'no_new_privs', 'workspace_write', 'denied_paths', 'network'}
    if (not isinstance(value, dict) or set(value) != fields or value['schema'] != 'ai4r-builder-tool-probe-result:1'
            or value['nonce'] != nonce or value['uid'] != 10002 or value['gid'] != 10002
            or value['cap_eff'] != '0000000000000000' or value['no_new_privs'] != '1' or value['workspace_write'] is not True
            or not isinstance(value['denied_paths'], dict) or set(value['denied_paths']) != {'run_state', 'main_credential', 'fixture', 'library'}
            or not all(v is True for v in value['denied_paths'].values()) or set(value['network']) != {'ipv4', 'ipv6'}):
        raise ExecutorBlocked('BUILDER_TOOL_PROBE_FAILED')
    for result in value['network'].values():
        if (not isinstance(result, dict) or set(result) != {'denied', 'errno'} or result['denied'] is not True
                or type(result['errno']) is not int or result['errno'] not in {1, 13, 99, 100, 101, 113}):
            raise ExecutorBlocked('BUILDER_TOOL_NETWORK_NOT_DENIED')


@dataclass(frozen=True)
class QualificationBinding:
    job_id: str
    build_id: str
    codex_path: Path
    codex_sha256: str
    codex_version: str
    workspace_root: Path
    credential_source: Path
    credential_sha256: str
    credential_budget_ref: dict
    credential_revocation_ref: dict
    authorization_ref: dict
    model_selection_profile_ref: dict
    deployment_ref: dict
    memory_mb: int
    pids_max: int
    time_s: float
    tool_limit: int
    max_event_bytes: int
    probe_sha256: str
    prompt_sha256: str

    @classmethod
    def load(cls, store, ref, *, build_id):
        value = _record(store, ref)
        if set(value) != set(cls.__dataclass_fields__) | {'schema'} or value.pop('schema') != 'ai4r-builder-qualification-binding:1':
            raise ExecutorBlocked('BUILDER_QUALIFICATION_BINDING_INVALID')
        if not re.fullmatch(r'ai4r-builder-qual-[a-z0-9-]{1,64}', value['job_id']) or value['build_id'] != build_id or value['codex_version'] != '0.144.4':
            raise ExecutorBlocked('BUILDER_QUALIFICATION_IDENTITY_INVALID')
        for field in ('codex_sha256', 'credential_sha256', 'probe_sha256', 'prompt_sha256'):
            if not isinstance(value[field], str) or not re.fullmatch('[a-f0-9]{64}', value[field]):
                raise ExecutorBlocked('BUILDER_QUALIFICATION_HASH_INVALID')
        if value['probe_sha256'] != sha(PROBE_PATH.read_bytes()) or value['prompt_sha256'] != sha(PROBE_PROMPT.encode()):
            raise ExecutorBlocked('BUILDER_QUALIFICATION_FIXED_PROBE_CHANGED')
        for field in ('memory_mb', 'pids_max', 'max_event_bytes'):
            if type(value[field]) is not int or value[field] <= 0:
                raise ExecutorBlocked('BUILDER_QUALIFICATION_LIMIT_INVALID')
        if (type(value['time_s']) not in (int, float) or not math.isfinite(value['time_s']) or not 0 < value['time_s'] <= 600
                or type(value['tool_limit']) is not int or not 2 <= value['tool_limit'] <= 40):
            raise ExecutorBlocked('BUILDER_QUALIFICATION_LIMIT_INVALID')
        for field in ('codex_path', 'workspace_root', 'credential_source'):
            value[field] = Path(value[field])
        if (value['workspace_root'] != Path('/var/lib/ai4r-executor/qualification')
                or value['codex_path'] != Path('/usr/local/bin/codex')
                or not value['credential_source'].is_relative_to('/var/lib/ai4r-builder-credentials')
                or value['credential_source'] == Path('/var/lib/ai4r-builder-credentials')):
            raise ExecutorBlocked('BUILDER_QUALIFICATION_PATH_INVALID')
        for field in ('credential_budget_ref', 'credential_revocation_ref', 'authorization_ref', 'model_selection_profile_ref', 'deployment_ref'):
            _read(store, value[field])
        authority = _metadata(store, value['authorization_ref'], 'builder_qualification_authorization')
        if (authority.get('kind') != 'builder-qualification-authorization1' or authority.get('operation') != 'fixed_builder_tool_probe'
                or not _not_expired(authority) or any(authority.get(key) != value[key] for key in
                    ('job_id', 'build_id', 'codex_sha256', 'credential_sha256', 'probe_sha256', 'prompt_sha256'))):
            raise ExecutorBlocked('BUILDER_QUALIFICATION_AUTHORIZATION_UNAVAILABLE')
        return cls(**value)


class PositiveControls:
    def __init__(self, parent, nonce):
        self.parent, self.nonce = parent, nonce
        self.sockets, self.paths, self.hashes = {}, {}, {}

    def __enter__(self):
        outside = self.parent / 'protected-canaries'; outside.mkdir(mode=0o700)
        for role, uid in [('run_state', 10001), ('main_credential', 10001), ('fixture', 12002), ('library', 0)]:
            path = outside / role
            raw = ('synthetic-positive-control:' + role + ':' + self.nonce).encode()
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'wb') as output: output.write(raw)
            os.chown(path, uid, uid)
            self.paths[role], self.hashes[role] = str(path), sha(raw)
        try:
            for kind, family, address in [('ipv4', socket.AF_INET, '127.0.0.1'), ('ipv6', socket.AF_INET6, '::1')]:
                listener = socket.socket(family)
                listener.bind((address, 0)); listener.listen(4); listener.settimeout(2)
                self.sockets[kind] = listener
            self.verify()
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def verify(self):
        for role, path in self.paths.items():
            if sha(Path(path).read_bytes()) != self.hashes[role]:
                raise ExecutorBlocked('BUILDER_CANARY_POSITIVE_CONTROL_CHANGED')
        for listener in self.sockets.values():
            with socket.socket(listener.family) as client:
                client.settimeout(2); client.connect(listener.getsockname())
                address = client.getsockname()
                accepted, peer = listener.accept()
                accepted.close()
                if peer != address:
                    raise ExecutorBlocked('BUILDER_UNEXPECTED_TOOL_CONNECTION')
        return {'canaries': dict(self.hashes), 'live_listeners': {k: True for k in self.sockets},
                'network_namespace': os.readlink('/proc/self/ns/net')}

    def inputs(self):
        return {'schema': 'ai4r-builder-tool-probe-input:1', 'nonce': self.nonce, 'canaries': self.paths,
                'listeners': {k: s.getsockname()[1] for k, s in self.sockets.items()}}

    def consume_parent_positive(self):
        observed = {}
        for kind, listener in self.sockets.items():
            accepted, _ = listener.accept()
            with accepted:
                accepted.settimeout(2)
                data = accepted.recv(128)
            if data != b'AI4R_PARENT_POSITIVE:' + self.nonce.encode('ascii'):
                raise ExecutorBlocked('BUILDER_NATIVE_PARENT_POSITIVE_CONTROL_FAILED')
            observed[kind] = True
        return observed

    def __exit__(self, *_):
        for listener in self.sockets.values(): listener.close()


def add_parent_controls(command, controls):
    """Bind fixed positive controls into the trusted before-exec probe frame."""
    command = list(command)
    probe_index = next(i for i, part in enumerate(command) if part == '/builder-probe.py' and command[i - 1] == '-I')
    expected = json.loads(command[probe_index + 1])
    expected['qualification_connectivity'] = {'nonce': controls.nonce, **controls.inputs()['listeners']}
    command[probe_index + 1] = json.dumps(expected)
    return command


class FixedQualificationLauncher:
    """Constructed only by the explicit operator procedure below, never registered."""
    def __init__(self, *, store, executor, binding, binding_ref, authorize, stage, controls):
        self.store, self.executor, self.binding, self.binding_ref = store, executor, binding, binding_ref
        self.authorize, self.stage, self.controls = authorize, stage, controls
        self.issued, self.observation_ref, self.probe_result = False, None, None

    async def invoke(self, protected, prompt, *, timeout_s):
        if self.issued or prompt != PROBE_PROMPT:
            raise ExecutorBlocked('BUILDER_QUALIFICATION_FIXED_CALL_ONLY')
        facts = self.authorize(protected, revalidate=True)
        for field in ('contract_ref', 'route_ref', 'model_call_start_ref', 'input_ref'):
            _read(self.store, protected[field])
        start = _record(self.store, protected['model_call_start_ref'])
        incoming = _record(self.store, protected['input_ref'])
        route = _record(self.store, protected['route_ref'])
        if (any(start.get(k) != protected[k] for k in ('contract_ref', 'invocation_id', 'execution_id', 'call_id', 'route_ref', 'input_ref'))
                or incoming.get('prompt') != PROBE_PROMPT or incoming.get('call_id') != protected['call_id']
                or route.get('route_id') != start.get('route_id') or route.get('invocation_id') != protected['invocation_id']):
            raise ExecutorBlocked('BUILDER_QUALIFICATION_GOVERNED_JOIN_INVALID')
        self.issued = True
        wall = min(timeout_s, self.binding.time_s, facts['execution_deadline_monotonic_s'] - time.monotonic())
        if wall <= 0:
            raise ExecutorBlocked('BUILDER_QUALIFICATION_DEADLINE')
        state = QualificationEvents(self.binding.tool_limit, self.controls.nonce)
        argv = (str(self.binding.codex_path), '--ask-for-approval', 'never', '--sandbox', 'workspace-write',
            '-c', 'web_search="disabled"', '-c', 'sandbox_workspace_write.network_access=false',
            '-c', 'sandbox_workspace_write.writable_roots=["/workspace/poc"]',
            'exec', '--json', '--ephemeral', '--ignore-user-config', '--ignore-rules', '--skip-git-repo-check', '-')
        job = BuilderKernelJob(self.stage.job_id, protected['contract_ref'], protected['invocation_id'], argv,
                               wall, self.binding.memory_mb, self.binding.pids_max)
        lease = BuilderCredentialLease(self.binding, self.store, self.stage)
        result = None
        try:
            home = lease.open()
            command = BuilderLauncher(store=self.store, executor=self.executor, runtime=None, authorize=None)._command(self.stage, home, argv)
            command = add_parent_controls(command, self.controls)
            remaining = min(wall, facts['execution_deadline_monotonic_s'] - time.monotonic())
            if remaining <= 0:
                raise ExecutorBlocked('BUILDER_QUALIFICATION_DEADLINE')
            job = replace(job, timeout_s=remaining)
            result = await self.executor._run_kernel(job, command, output_parent=self.stage.parent,
                stdin_bytes=PROBE_PROMPT.encode(), stdout_line_observer=state.feed, stdout_line_limit=self.binding.max_event_bytes)
            if result['termination_reason'] != 'isolation_failure':
                try:
                    self.controls.consume_parent_positive()
                except (OSError, ExecutorBlocked) as error:
                    result = dict(result, termination_reason='isolation_failure', qualification_control_error=type(error).__name__)
        except (ExecutorBlocked, OSError, asyncio.CancelledError) as error:
            if self.stage.job_id not in getattr(self.executor, 'owned_groups', {}):
                raise
            partial = {}
            directory = self.stage.parent / (self.stage.job_id + '.capture')
            for name in ('stdout', 'stderr'):
                try:
                    fd = os.open(directory / name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                except FileNotFoundError:
                    continue
                with os.fdopen(fd, 'rb') as source:
                    meta = os.fstat(source.fileno())
                    if not stat.S_ISREG(meta.st_mode) or meta.st_uid != 0:
                        raise ExecutorBlocked('BUILDER_QUALIFICATION_PARTIAL_CUSTODY') from None
                    partial[name + '_ref'] = self.store.put_blob(source.read(), media_type='text/plain')
            result = {'termination_reason': 'containment_unknown', 'exit_code': None, 'identity': {},
                      'contract_ref': protected['contract_ref'], 'invocation_id': protected['invocation_id'],
                      'observed_runtime': True, 'containment_error': type(error).__name__, **partial}
        finally:
            lease.close()
            if result is not None:
                terminal = result['termination_reason']
                if terminal == 'completed':
                    terminal = state.stop_reason or ('completed' if result['exit_code'] == 0 and state.success and state.probe_result is not None else 'invalid_output')
                observed = {**{k: protected[k] for k in ('run_id', 'node_id', 'contract_ref', 'invocation_id', 'execution_id', 'call_id',
                    'route_ref', 'model_call_start_ref', 'input_ref')}, 'qualification_binding_ref': self.binding_ref,
                    'event_refs': [self.store.put_blob(line, media_type='application/x-ndjson') for line in state.events],
                    'output_refs': [result[k] for k in ('stdout_ref', 'stderr_ref') if k in result],
                    'tool_events': state.tools, 'tool_count': state.tool_count, 'terminal_reason': terminal,
                    'identity': result['identity'], 'kernel_receipt': result, 'credential_removed': not lease.home.exists(),
                    'trial_executed': True, 'packages_installed': False, 'observed_runtime': True}
                self.observation_ref = self.store.append_record('builder_execution', observed)
                self.probe_result = state.probe_result
        if result is None:
            raise ExecutorBlocked('BUILDER_QUALIFICATION_OUTCOME_UNKNOWN')
        terminal = _record(self.store, self.observation_ref)['terminal_reason']
        success = terminal == 'completed'
        uncertain = terminal == 'containment_unknown'
        return {'text': state.text if success else None, 'identity': {'effective': None, 'basis': 'CLI effective model not reported'},
                'usage': state.usage, 'provider_request_id': None, 'observed_runtime': True,
                'evidence_refs': [self.observation_ref], 'outcome': 'completed' if success else 'outcome_unknown' if uncertain else 'failed',
                'terminal_reason': terminal, 'error_code': None if success else 'CONTAINMENT_UNCERTAIN' if uncertain else terminal if terminal in {'timeout', 'cancelled', 'budget_exceeded'} else 'invalid_output'}


def _metadata(store, ref, kind):
    lookup = getattr(store, 'record_kind', None)
    if lookup is None or lookup(ref) != kind:
        raise ExecutorBlocked('BUILDER_QUALIFICATION_PROTECTED_PROVENANCE_REQUIRED')
    return _record(store, ref)


def validate_tool_qualification(store, proof, runtime):
    """Read-only validation of protected provenance; no effect reauthorization."""
    if hasattr(runtime, 'qualification_ref') and _metadata(store, runtime.qualification_ref, 'builder_tool_qualification_result') != proof:
        raise ExecutorBlocked('BUILDER_QUALIFICATION_FINAL_RECORD_CHANGED')
    if proof.get('producer_ref') not in proof.get('evidence_refs', []):
        raise ExecutorBlocked('BUILDER_QUALIFICATION_PROTECTED_PROVENANCE_REQUIRED')
    producer = _metadata(store, proof.get('producer_ref'), 'builder_tool_qualification')
    if producer.get('schema') != 'ai4r-builder-tool-qualification-producer:1' or producer.get('build_id') != runtime.build_id or producer.get('codex_sha256') != runtime.codex_sha256:
        raise ExecutorBlocked('BUILDER_QUALIFICATION_PRODUCER_MISMATCH')
    binding = _record(store, producer['binding_ref'])
    if (binding.get('schema') != 'ai4r-builder-qualification-binding:1' or binding.get('build_id') != runtime.build_id
            or binding.get('codex_sha256') != runtime.codex_sha256 or binding.get('probe_sha256') != sha(PROBE_PATH.read_bytes())
            or binding.get('prompt_sha256') != sha(PROBE_PROMPT.encode())):
        raise ExecutorBlocked('BUILDER_QUALIFICATION_PROBE_CHANGED')
    call = _metadata(store, producer['model_call_ref'], 'model-call')
    observed = _metadata(store, producer['builder_execution_ref'], 'builder_execution')
    if (call.get('outcome') != 'completed' or call.get('observed_runtime') is not True or observed.get('terminal_reason') != 'completed'
            or observed.get('credential_removed') is not True or observed.get('qualification_binding_ref') != producer['binding_ref']
            or producer['builder_execution_ref'] not in call.get('evidence_refs', [])
            or call.get('id') != observed.get('call_id') or any(call.get(k) != observed.get(k) for k in ('invocation_id', 'execution_id'))):
        raise ExecutorBlocked('BUILDER_QUALIFICATION_CALL_JOIN_INVALID')
    start = _metadata(store, observed['model_call_start_ref'], 'model-call-start')
    route = _metadata(store, observed['route_ref'], 'route-record')
    incoming = _metadata(store, observed['input_ref'], 'model-call-input')
    if (any(start.get(k) != observed.get(k) for k in ('contract_ref', 'invocation_id', 'execution_id', 'call_id', 'route_ref', 'input_ref'))
            or route.get('route_id') != start.get('route_id') or incoming.get('prompt') != PROBE_PROMPT):
        raise ExecutorBlocked('BUILDER_QUALIFICATION_START_JOIN_INVALID')
    inputs = _record(store, producer['probe_inputs_ref'])
    state = QualificationEvents(binding['tool_limit'], inputs['nonce'])
    raw_events = [_read(store, ref) for ref in observed['event_refs']]
    for raw in raw_events: state.feed(raw)
    kernel = observed['kernel_receipt']
    if (not state.success or state.tool_count != 1 or state.probe_result is None
            or b''.join(raw_events) != _read(store, kernel['stdout_ref'])
            or kernel.get('termination_reason') != 'completed' or kernel.get('exit_code') != 0
            or kernel.get('contract_ref') != observed['contract_ref'] or kernel.get('invocation_id') != observed['invocation_id']):
        raise ExecutorBlocked('BUILDER_QUALIFICATION_RAW_EVENT_PROOF_INVALID')
    limits = kernel.get('observed_limits', {})
    parent_probe = _record(store, limits['isolation_probe_ref'])
    if (parent_probe.get('ready') is not True or parent_probe.get('profile') != 'builder-parent'
            or parent_probe.get('executor_uid') != 10002 or parent_probe.get('executor_gid') != 10002
            or parent_probe.get('cap_effective') != '0000000000000000' or parent_probe.get('no_new_privileges') != '1'
            or parent_probe.get('parent_connectivity') != {'ipv4': True, 'ipv6': True}
            or parent_probe.get('network') is not None
            or not 0 < int(limits['memory_max']) <= binding['memory_mb'] * 1024 * 1024
            or not 0 < int(limits['pids_max']) <= binding['pids_max']):
        raise ExecutorBlocked('BUILDER_QUALIFICATION_NATIVE_PARENT_PROOF_INVALID')
    for ref in (producer['positive_before_ref'], producer['positive_after_ref']):
        control = _record(store, ref)
        if (set(control.get('canaries', {})) != {'run_state', 'main_credential', 'fixture', 'library'}
                or control.get('live_listeners') != {'ipv4': True, 'ipv6': True}):
            raise ExecutorBlocked('BUILDER_QUALIFICATION_POSITIVE_CONTROL_REQUIRED')
    if _record(store, producer['positive_before_ref']) != _record(store, producer['positive_after_ref']):
        raise ExecutorBlocked('BUILDER_QUALIFICATION_CONTROLS_CHANGED')
    if parent_probe.get('network_namespace') != _record(store, producer['positive_before_ref'])['network_namespace']:
        raise ExecutorBlocked('BUILDER_QUALIFICATION_PARENT_NAMESPACE_CHANGED')
    validate_probe(state.probe_result, inputs['nonce'])
    return producer


async def qualify_builder_tools(*, store, executor, binding_ref, build_id):
    """One explicit real probe. No credential or complete binding => no model call."""
    if os.name != 'posix' or os.geteuid() != 0:
        raise ExecutorBlocked('BUILDER_QUALIFICATION_ROOT_CONTROLLER_REQUIRED')
    from .store_custody import CustodyStore
    if (type(store) not in {SQLiteRunStore, CustodyStore} or type(executor) is not RestrictedExecutor
            or getattr(executor._run_kernel, '__func__', None) is not RestrictedExecutor._run_kernel):
        raise ExecutorBlocked('BUILDER_QUALIFICATION_ACTUAL_KERNEL_AND_STORE_REQUIRED')
    from .native_ports import verify_installed_build
    if verify_installed_build() != build_id:
        raise ExecutorBlocked('BUILDER_QUALIFICATION_INSTALLED_BUILD_CHANGED')
    binding = QualificationBinding.load(store, binding_ref, build_id=build_id)
    _custody(binding.codex_path, owner=0)
    if binding.codex_path.stat().st_mode & 0o022 or sha(binding.codex_path.read_bytes()) != binding.codex_sha256:
        raise ExecutorBlocked('BUILDER_QUALIFICATION_CLI_CHANGED')
    BuilderCredentialLease.validate(binding, store)
    failures = executor.prerequisites()
    if failures:
        raise ExecutorBlocked(';'.join(failures))
    from .trajectory import capture_healthy
    if not capture_healthy():
        raise ExecutorBlocked('BUILDER_QUALIFICATION_NATIVE_CAPTURE_UNAVAILABLE')
    # Read the source-pinned policy records rather than inventing model policy.
    validate('model-selection-profile', _record(store, binding.model_selection_profile_ref))
    if not _record(store, binding.deployment_ref):
        raise ExecutorBlocked('BUILDER_QUALIFICATION_DEPLOYMENT_UNAVAILABLE')
    root = binding.workspace_root
    if not root.exists(): root.mkdir(mode=0o711, parents=True)
    _custody(root, owner=0, mode=0o711, directory=True)
    key = sha(json_bytes(binding_ref))[:48]
    parent = root / key; parent.mkdir(mode=0o711)
    descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(descriptor)
    finally: os.close(descriptor)
    workspace = parent / 'work'; workspace.mkdir(mode=0o700); os.chown(workspace, 10002, 10002)
    resources = parent / 'resources'; resources.mkdir(mode=0o755)
    nonce = secrets.token_hex(32)
    stage = BuilderStage('builder-qual-' + key, parent, workspace, resources)
    run_id = binding.job_id
    store.append_record('builder-qualification-started', {'run_id': run_id, 'purpose': 'fixed_builder_tool_qualification', 'binding_ref': binding_ref})
    contract_ref = store.append_record('builder-qualification-contract', {'schema': 'ai4r-builder-qualification-contract:1',
        'binding_ref': binding_ref, 'run_id': run_id, 'purpose': 'fixed_builder_tool_probe'})
    context = {'run_id': run_id, 'node_id': run_id + ':node', 'subnode_id': run_id + ':probe', 'attempt_id': run_id + ':attempt',
        'invocation_id': run_id + ':invocation', 'execution_id': run_id + ':execution', 'call_ordinal': 1, 'contract_ref': contract_ref,
        'cc_name': 'research.builder', 'call_function': 'worker', 'model_selection_profile_ref': binding.model_selection_profile_ref,
        'deployment_ref': binding.deployment_ref, 'limits': {'time_s': binding.time_s, 'model_calls': 1, 'memory_mb': binding.memory_mb},
        'execution_deadline_monotonic_s': time.monotonic() + binding.time_s,
        'router': {'enabled': False, 'deadline_s': 30, 'profile_ref': None}}
    current = None
    def authorize(request, revalidate=False):
        nonlocal current
        if not _not_expired(_record(store, binding.authorization_ref)):
            raise ExecutorBlocked('BUILDER_QUALIFICATION_AUTHORIZATION_EXPIRED')
        if current is None:
            if request != {'qualification_binding_ref': binding_ref}:
                raise ExecutorBlocked('BUILDER_QUALIFICATION_AUTHORITY_SCOPE')
            current = copy.deepcopy(context)
            # A separate finite test authority, not an ordinary Runner grant.
            # The exact root-owned once file and parent are durable before any
            # route/provider effect. Existing job/claim is never reopened.
            fd = os.open(parent / 'call.claim', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            try:
                with os.fdopen(fd, 'wb', closefd=False) as claim:
                    claim.write(json_bytes({'binding_ref': binding_ref, 'run_id': run_id})); claim.flush(); os.fsync(fd)
            finally:
                os.close(fd)
            directory = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
            try: os.fsync(directory)
            finally: os.close(directory)
            call_id = 'call:qualification:' + key
            claim_ref = store.append_record('builder-qualification-call-claim', {**current,
                'id': call_id + ':claim', 'call_id': call_id, 'purpose': 'fixed_builder_tool_probe', 'binding_ref': binding_ref})
            current.update(call_id=call_id, call_claim_ref=claim_ref)
        else:
            keys = ('execution_id', 'invocation_id', 'call_id', 'call_claim_ref', 'contract_ref')
            if not revalidate or any(request.get(k) != current[k] for k in keys):
                raise ExecutorBlocked('BUILDER_QUALIFICATION_REPLAY_DENIED')
        return copy.deepcopy(current)
    with PositiveControls(parent, nonce) as controls:
        before = store.put_blob(json_bytes(controls.verify()), media_type='application/json')
        probe_inputs = controls.inputs()
        inputs_ref = store.put_blob(json_bytes(probe_inputs), media_type='application/json')
        (resources / 'qualification_probe.py').write_bytes(PROBE_PATH.read_bytes())
        (resources / 'probe_inputs.json').write_bytes(json_bytes(probe_inputs))
        for path in resources.iterdir(): path.chmod(0o444)
        resources.chmod(0o555)
        launcher = FixedQualificationLauncher(store=store, executor=executor, binding=binding, binding_ref=binding_ref,
                                               authorize=authorize, stage=stage, controls=controls)
        bridge = GovernedBridge(persist=store.append_record, authorize=authorize,
            revalidate=lambda request: authorize(request, revalidate=True), subscription_service=None,
            builder_launcher=launcher, validate_record=validate, read_evidence=store.read_blob, health_check=capture_healthy)
        try:
            result = await bridge.call({'qualification_binding_ref': binding_ref}, PROBE_PROMPT)
        except BaseException:
            store.append_record('builder-qualification-halted', {'run_id': run_id, 'binding_ref': binding_ref,
                'reason': 'builder_qualification_failed_or_unknown'})
            raise
        after = store.put_blob(json_bytes(controls.verify()), media_type='application/json')
        if set(path.name for path in workspace.iterdir()) != {'qualification-write'}:
            raise ExecutorBlocked('BUILDER_QUALIFICATION_UNEXPECTED_WORKSPACE_CHANGE')
        marker = workspace / 'qualification-write'
        info = marker.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != 10002 or marker.read_bytes() != nonce.encode():
            raise ExecutorBlocked('BUILDER_QUALIFICATION_WORKSPACE_PROOF_INVALID')
        producer = store.append_record('builder_tool_qualification', {'schema': 'ai4r-builder-tool-qualification-producer:1',
            'run_id': run_id, 'build_id': build_id, 'codex_sha256': binding.codex_sha256, 'binding_ref': binding_ref,
            'model_call_ref': result['call_ref'], 'builder_execution_ref': launcher.observation_ref,
            'positive_before_ref': before, 'positive_after_ref': after, 'probe_inputs_ref': inputs_ref})
        proof = {'kind': 'builder-tool-sandbox-qualification1', 'build_id': build_id, 'codex_sha256': binding.codex_sha256,
            'observed_runtime': True, 'executor_uid': 10002, 'executor_gid': 10002, 'sandbox': 'workspace-write',
            'approvals': 'never', 'tool_network': 'none', 'denied_paths': {'run_state': True, 'main_credential': True, 'fixture': True},
            'producer_ref': producer, 'evidence_refs': [producer, result['call_ref'], launcher.observation_ref, before, after, inputs_ref],
            'credential_read_residual_risk': 'A tool command can read the dedicated Builder credential; its external budget and revocation bound the accepted source risk.'}
        validate_tool_qualification(store, proof, binding)
        proof_ref = store.append_record('builder_tool_qualification_result', proof)
        store.append_record('builder-qualification-completed', {'run_id': run_id, 'binding_ref': binding_ref, 'qualification_ref': proof_ref})
        return {'qualification_ref': proof_ref, 'producer_ref': producer, 'model_call_ref': result['call_ref']}
