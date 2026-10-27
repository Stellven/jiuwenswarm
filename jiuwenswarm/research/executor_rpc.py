"""Finite invocation-bound RPC for the root scientific execution broker.

The client passes captured identities and protocol selections, never a host
path, executable, UID, mount, shell command or caller-authored execution job.
"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import inspect
import json
import math
import os
import signal
import sqlite3
import stat
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from .bridge import BridgeError
from .contracts import ResearchError, validate
from .executor import ExecutorBlocked
from .private_rpc import PrivateRPCClient, PrivateRPCServer
from .state import json_bytes

PROTOCOL = "ai4r-executor-v1"


async def _await(value):
    return await value if inspect.isawaitable(value) else value


class ClaimLedger:
    """Durable pre-effect claims; an uncertain operation is never replayed."""
    def __init__(self, root):
        self.root = Path(root)
        if self.root.is_symlink():
            raise ExecutorBlocked("EXECUTOR_LEDGER_CUSTODY_INVALID")
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        meta = self.root.stat()
        path = self.root / "claims.sqlite3"
        if (meta.st_uid != os.geteuid() or stat.S_IMODE(meta.st_mode) != 0o700
                or path.is_symlink()):
            raise ExecutorBlocked("EXECUTOR_LEDGER_CUSTODY_INVALID")
        self.db = sqlite3.connect(path, isolation_level=None)
        path.chmod(0o600)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("CREATE TABLE IF NOT EXISTS claims (identity TEXT PRIMARY KEY, state TEXT NOT NULL, result TEXT)")

    @staticmethod
    def _completed_mapping(encoded):
        """Malformed completed data must never resemble a fresh claim."""
        try:
            value = json.loads(encoded)
        except (TypeError, ValueError):
            raise BridgeError("AUDIT_UNAVAILABLE") from None
        if not isinstance(value, dict):
            raise BridgeError("AUDIT_UNAVAILABLE")
        return value

    def claim(self, key):
        identity = hashlib.sha256(json_bytes(key)).hexdigest()
        try:
            self.db.execute("INSERT INTO claims VALUES (?, 'started', NULL)", (identity,))
        except sqlite3.IntegrityError:
            state, result = self.db.execute("SELECT state,result FROM claims WHERE identity=?", (identity,)).fetchone()
            if state == "completed":
                return identity, self._completed_mapping(result)
            raise BridgeError("DELIVERY_UNKNOWN") from None
        return identity, None

    def lookup(self, key):
        """Read one existing terminal claim; never issue or renew authority."""
        identity = hashlib.sha256(json_bytes(key)).hexdigest()
        row = self.db.execute("SELECT state,result FROM claims WHERE identity=?", (identity,)).fetchone()
        if row is None:
            return None
        state, result = row
        if state != "completed":
            raise BridgeError("DELIVERY_UNKNOWN")
        return self._completed_mapping(result)

    def complete(self, identity, value):
        encoded = json_bytes(value).decode()
        changed = self.db.execute("UPDATE claims SET state='completed',result=? WHERE identity=? AND state='started'", (encoded, identity))
        if changed.rowcount != 1:
            raise BridgeError("AUDIT_UNAVAILABLE")

    def close(self):
        self.db.close()


class ExecutionOperations:
    def __init__(self, *, backend, authorize, resolve_inputs, ledger, authorize_containment=None,
                 evaluation_adapter=None, attempt_broker=None):
        self.backend, self.authorize, self.resolve_inputs, self.ledger = backend, authorize, resolve_inputs, ledger
        self.bound, self.jobs, self.locks = {}, {}, {}
        self.authorize_containment = authorize_containment
        self.evaluation_adapter = evaluation_adapter
        self.active_tasks = {}
        self.attempt_broker = attempt_broker

    async def prepare_attempt_resources(self, payload):
        if self.attempt_broker is None:
            raise ExecutorBlocked('SCIENCE_START_BROKER_UNAVAILABLE')
        return await self.attempt_broker.prepare_attempt_resources(payload)

    async def activate_attempt_resources(self, payload):
        if self.attempt_broker is None:
            raise ExecutorBlocked('SCIENCE_START_BROKER_UNAVAILABLE')
        return await self.attempt_broker.activate_attempt_resources(payload)

    async def prerequisites(self, payload):
        if payload:
            raise ExecutorBlocked("INVALID_EXECUTOR_REQUEST")
        if self.backend is None:
            return {"ready": False, "builder_qualified": False, "reasons": ["SCIENCE_RUNTIME_BINDINGS_UNAVAILABLE"]}
        reasons = await _await(self.backend.prerequisites())
        from .executor import RestrictedExecutor
        if type(self.backend) is RestrictedExecutor:
            if self.attempt_broker is None:
                reasons = [*reasons, 'SCIENCE_START_BROKER_UNAVAILABLE']
            else:
                try:
                    self.attempt_broker.registration._current()
                    if self.attempt_broker.registration.definition.record['gpu_required']:
                        reasons = [*reasons, 'GPU_SCIENTIFIC_FACTORY_UNAVAILABLE']
                except (ExecutorBlocked, ResearchError, OSError, ValueError, KeyError):
                    reasons = [*reasons, 'SCIENCE_START_REGISTRATION_UNAVAILABLE']
        required = ("job_factory", "provisioner", "hardware_probe")
        tool_free_builder = getattr(self.backend, 'tool_free_builder', False) is True
        if not tool_free_builder:
            required += ('builder_collector', 'builder_observer')
        if any(getattr(self.backend, name, None) is None for name in required):
            reasons = [*reasons, "PROTECTED_EXECUTION_FACTORIES_UNAVAILABLE"]
        development = getattr(self.backend, 'builder_test_required', False) is True
        agentic = getattr(self.backend, 'builder_agent_required', False) is True
        if agentic and getattr(self.backend,'builder_agent_service',None) is None:
            reasons=[*reasons,'BUILDER_AGENT_SERVICE_UNAVAILABLE']
        if development and getattr(self.backend, 'builder_test_service', None) is None:
            reasons = [*reasons, 'BUILDER_TEST_SERVICE_UNAVAILABLE']
        builder_qualified = (tool_free_builder and (not development or getattr(self.backend, 'builder_test_service', None) is not None)
                             and (not agentic or getattr(self.backend,'builder_agent_service',None) is not None))
        launcher = getattr(self.backend, 'builder_launcher', None)
        if launcher is not None:
            try:
                # Recheck the exact installed binary/build, actual sandbox
                # qualification, current dedicated credential/budget/revocation
                # evidence and kernel prerequisites; package presence is not it.
                await _await(launcher._qualify())
                builder_qualified = True
            except (ExecutorBlocked, OSError, ValueError, KeyError):
                reasons = [*reasons, 'BUILDER_RUNTIME_QUALIFICATION_UNAVAILABLE']
        return {"ready": not reasons, "builder_qualified": builder_qualified,
                **({'execution_mode': 'm1_app_process'} if getattr(self.backend, 'execution_mode', None) == 'm1_app_process' else {}),
                "builder_mode": 'native_agent' if agentic else 'bounded_tests' if development else 'tool_free' if tool_free_builder else 'isolated_tools', "reasons": reasons}

    async def read_only_prerequisites(self, payload):
        """Observe the live broker only; this grants no scientific operation."""
        if payload:
            raise ExecutorBlocked("INVALID_EXECUTOR_REQUEST")
        ready = callable(self.authorize) and self.ledger is not None
        return {'ready': ready, 'scope': 'read_only',
                'reasons': [] if ready else ['PROTECTED_EXECUTOR_OWNER_UNAVAILABLE']}

    async def _binding(self, payload, extras, *, operation=None):
        fields = {"contract_ref", "invocation_id", "execution_id"}
        if not isinstance(payload, dict) or set(payload) != fields | extras:
            raise ExecutorBlocked("INVALID_EXECUTOR_REQUEST")
        validate("Ref", payload["contract_ref"])
        if any(not isinstance(payload[key], str) or not payload[key] for key in ('invocation_id', 'execution_id')):
            raise ExecutorBlocked("INVALID_EXECUTOR_REQUEST")
        request = {key: copy.deepcopy(payload[key]) for key in fields}
        # Reauthorize every operation against the live run/cancellation/deadline
        # owner. Previously issued tokens confer no continuing authority.
        actual = await _await(self.authorize(request))
        if (not isinstance(actual, dict) or actual.get("contract_ref") != request["contract_ref"]
                or actual.get("invocation_id") != request["invocation_id"]
                or actual.get("execution_id") != request["execution_id"]):
            raise ExecutorBlocked("EXECUTOR_AUTHORIZATION_MISMATCH")
        contract = actual.get("contract")
        if not isinstance(contract, dict):
            raise ExecutorBlocked("EXECUTOR_AUTHORIZATION_MISMATCH")
        private = (str(contract.get("schema", "")).startswith("ai4r-evaluation-")
                   or contract.get("invalid_for_product") is True)
        if self.evaluation_adapter is not None:
            from .evaluation_executor import EvaluationExecutorAdapter
            if (type(self.evaluation_adapter) is not EvaluationExecutorAdapter
                    or self.evaluation_adapter.backend is not self.backend):
                raise ExecutorBlocked("EVALUATION_EXECUTOR_ADAPTER_UNAVAILABLE")
            private = private or self.evaluation_adapter.is_private_reference(request['contract_ref'])
        if private:
            # A trusted IPC peer and compatible fields cannot register a private
            # execution. Only the installed adapter may reconstruct its indexed
            # context and durable owner. Generic binding is never a fallback.
            if self.evaluation_adapter is None:
                raise ExecutorBlocked("EVALUATION_EXECUTOR_ADAPTER_UNAVAILABLE")
            from .evaluation_executor import EvaluationExecutorAdapter
            if type(self.evaluation_adapter) is not EvaluationExecutorAdapter:
                raise ExecutorBlocked("EVALUATION_EXECUTOR_ADAPTER_UNAVAILABLE")
            contract = self.evaluation_adapter.validate_binding(request, actual)
            if operation is not None:
                self.evaluation_adapter.require_operation(operation, request, contract)
        if self.backend is None:
            raise ExecutorBlocked("SCIENCE_RUNTIME_BINDINGS_UNAVAILABLE")
        deadline = actual.get('execution_deadline_monotonic_s')
        if type(deadline) not in (int, float) or not math.isfinite(deadline) or deadline <= time.monotonic():
            raise ExecutorBlocked('PROTECTED_INVOCATION_DEADLINE_UNAVAILABLE')
        from .executor import RestrictedExecutor
        if type(self.backend) is RestrictedExecutor:
            from .science_start import ScienceAttemptBroker
            if type(self.attempt_broker) is not ScienceAttemptBroker or self.attempt_broker.registration.backend is not self.backend:
                raise ExecutorBlocked('ORIGINAL_ACTIVE_ATTEMPT_RESOURCES_REQUIRED')
            self.attempt_broker.require_effect(request, operation, contract)
        key = (request["contract_ref"]["sha256"], request["invocation_id"], request["execution_id"])
        if key not in self.bound:
            self.bound[key] = self.backend.bind_invocation(contract_ref=request["contract_ref"],
                invocation_id=request["invocation_id"], execution_id=request["execution_id"], contract=contract)
        return request, contract, self.bound[key], self.locks.setdefault(key, asyncio.Lock()), deadline

    async def perform(self, operation, payload):
        extras = {"selection"} if operation == "measure_job" else {"job_id", "job_token"} if operation == "run" else set()
        request, contract, bound, lock, deadline = await self._binding(payload, extras, operation=operation)
        task = asyncio.current_task()
        self.active_tasks[task] = contract['run_id']
        try:
            return await self._perform_bound(operation, payload, request, contract, bound, lock, deadline)
        finally:
            self.active_tasks.pop(task, None)

    async def _perform_bound(self, operation, payload, request, contract, bound, lock, deadline):
        async with asyncio.timeout_at(deadline), lock:
            inputs = await _await(self.resolve_inputs(contract))
            if operation == "measure_job":
                selection = payload["selection"]
                expected = {"role", "repeat_index", "seed", "sequence", "subject_ref", "hardware_ref"}
                if (not isinstance(selection, dict) or set(selection) not in (expected, expected|{'case_id'})
                        or ('case_id' in selection and type(selection['case_id']) is not str)):
                    raise ExecutorBlocked("INVALID_EXECUTOR_SELECTION")
                identity, previous = self.ledger.claim({**request, "operation": operation, "selection": selection})
                if previous is not None:
                    # Process restart loses the corresponding private job
                    # object. Do not recreate it from an untrusted token.
                    if previous["job_id"] not in self.jobs:
                        raise BridgeError("DELIVERY_UNKNOWN")
                    return previous
                job = await bound.measure_job(contract, inputs, **selection)
                token = __import__("secrets").token_urlsafe(32)
                self.jobs[job.job_id] = (request, token, job)
                result = {"job_id": job.job_id, "job_token": token}
            elif operation == "run":
                issued = self.jobs.get(payload["job_id"])
                if issued is None or issued[:2] != (request, payload["job_token"]):
                    raise ExecutorBlocked("UNISSUED_EXECUTION_JOB")
                identity, previous = self.ledger.claim({**request, "operation": operation, "job_id": payload["job_id"]})
                if previous is not None:
                    return previous
                result = await bound.run(issued[2])
            elif operation in {"provision", "hardware_inventory", "collect_builder", "builder_observation"}:
                identity, previous = self.ledger.claim({**request, "operation": operation})
                if previous is not None:
                    return previous
                if operation == "provision":
                    from .environment import validate_lock
                    environment = inputs["environment_lock"]
                    pins = validate_lock(environment, self.backend.read_blob, environment["platform"])
                    result = await bound.provision(contract, inputs, pins)
                else:
                    result = await getattr(bound, operation)(contract)
            else:
                raise ExecutorBlocked("INVALID_EXECUTOR_OPERATION")
            self.ledger.complete(identity, result)
            return result

    async def contain(self, payload):
        if (not isinstance(payload, dict) or set(payload) != {'run_id', 'request_id'}
                or self.authorize_containment is None):
            raise ExecutorBlocked('CONTAINMENT_AUTHORIZATION_REQUIRED')
        grant = await _await(self.authorize_containment(copy.deepcopy(payload)))
        if (not isinstance(grant, dict) or grant.get('authorized') is not True
                or any(grant.get(key) != value for key, value in payload.items())
                or not isinstance(grant.get('invocation_ids'), list)):
            raise ExecutorBlocked('CONTAINMENT_AUTHORIZATION_REQUIRED')
        identity, previous = self.ledger.claim({**payload, 'operation': 'contain'})
        if previous is not None:
            return previous
        tasks = [task for task, run in self.active_tasks.items() if run == payload['run_id']]
        for task in tasks:
            task.cancel()
        if tasks:
            async with asyncio.timeout(15):
                await asyncio.gather(*tasks, return_exceptions=True)
        if self.backend is not None:
            invocations = set(grant['invocation_ids'])
            if getattr(self.backend, 'execution_mode', None) == 'm1_app_process':
                from .m1_process import process_members
                for observation in self.backend.owned_groups.values():
                    if observation['invocation_id'] in invocations and process_members(observation['pgid']):
                        raise ExecutorBlocked('M1_PROCESS_CLEANUP_UNCONFIRMED')
            for observation in self.backend.owned_groups.values():
                if observation['invocation_id'] not in invocations:
                    continue
                if observation.get('execution_mode') == 'm1_app_process':
                    continue
                group = observation['path']
                if not group.exists():
                    continue
                if group.is_symlink() or group.parent != self.backend.cgroup_root or group.stat().st_ino != observation['inode']:
                    raise ExecutorBlocked('CONTAINMENT_GROUP_IDENTITY_INVALID')
                (group / 'cgroup.kill').write_text('1')
                await self.backend._wait_empty(group)
            if any(run == payload['run_id'] for run in self.active_tasks.values()):
                raise ExecutorBlocked('CONTAINMENT_OPERATION_STILL_ACTIVE')
        result = {'contained': True, **payload}
        self.ledger.complete(identity, result)
        return result

    async def builder_test(self, payload):
        fields = {'manifest_ref', 'tests_ref', 'ordinal'}
        request, contract, bound, lock, deadline = await self._binding(payload, fields, operation='builder_test')
        validate('Ref', payload['manifest_ref']); validate('Ref', payload['tests_ref'])
        if type(payload['ordinal']) is not int or not 1 <= payload['ordinal'] <= 3:
            raise ExecutorBlocked('INVALID_BUILDER_TEST_ORDINAL')
        service = getattr(self.backend, 'builder_test_service', None)
        if service is None:
            raise ExecutorBlocked('BUILDER_TEST_SERVICE_UNAVAILABLE')
        task = asyncio.current_task()
        self.active_tasks[task] = contract['run_id']
        try:
            async with asyncio.timeout_at(deadline), lock:
                # Ordinal is the effect identity: changed candidate bytes cannot
                # create additional jobs under the same development allowance.
                identity, previous = self.ledger.claim({**request, 'operation': 'builder_test', 'ordinal': payload['ordinal']})
                if previous is not None:
                    report = self.backend.read_blob(previous['report_ref'])
                    captured = json.loads(report)
                    if any(captured[key] != payload[key] for key in ('manifest_ref', 'tests_ref', 'ordinal')):
                        raise ExecutorBlocked('BUILDER_TEST_REPLAY_CHANGED')
                    return previous
                result = await service.test(contract, await _await(self.resolve_inputs(contract)),
                    binding=bound._binding, **{key: payload[key] for key in fields})
                self.ledger.complete(identity, result)
                return result
        finally:
            self.active_tasks.pop(task, None)

    async def builder_action(self, payload):
        fields = {'action','arguments','ordinal','model_ordinal'}
        request, contract, bound, lock, deadline = await self._binding(payload, fields, operation='builder_action')
        if (type(payload['ordinal']) is not int or not 1 <= payload['ordinal'] <= 40
                or type(payload['model_ordinal']) is not int or not 1 <= payload['model_ordinal'] <= 20
                or type(payload['action']) is not str or type(payload['arguments']) is not dict):
            raise ExecutorBlocked('INVALID_BUILDER_AGENT_ACTION')
        service = getattr(self.backend, 'builder_agent_service', None)
        if service is None:
            raise ExecutorBlocked('BUILDER_AGENT_SERVICE_UNAVAILABLE')
        task = asyncio.current_task()
        self.active_tasks[task] = contract['run_id']
        try:
            async with asyncio.timeout_at(deadline), lock:
                # Include the complete action digest, but claim by ordinal: a
                # changed retry can never acquire another effect allowance.
                identity, previous = self.ledger.claim({**request,'operation':'builder_action','ordinal':payload['ordinal']})
                selection = {key: payload[key] for key in fields}
                if previous is not None:
                    if previous['selection'] != selection:
                        raise ExecutorBlocked('BUILDER_ACTION_REPLAY_CHANGED')
                    return previous['result']
                result = await service.action(contract,await _await(self.resolve_inputs(contract)),
                    binding=bound._binding,**selection)
                self.ledger.complete(identity,{'selection':selection,'result':result})
                return result
        finally:
            self.active_tasks.pop(task,None)

    async def invoke_builder(self, payload):
        if (not isinstance(payload, dict) or set(payload) != {'protected', 'prompt', 'timeout_s'}
                or not isinstance(payload['protected'], dict)
                or not isinstance(payload['prompt'], str) or not payload['prompt']
                or type(payload['timeout_s']) not in (int, float)
                or not math.isfinite(payload['timeout_s']) or not 0 < payload['timeout_s'] <= 600):
            raise ExecutorBlocked('INVALID_BUILDER_REQUEST')
        protected = copy.deepcopy(payload['protected'])
        if (not {'contract_ref', 'invocation_id', 'execution_id', 'call_id', 'call_claim_ref'} <= set(protected)
                or not isinstance(protected['call_id'], str) or not protected['call_id']):
            raise ExecutorBlocked('INVALID_BUILDER_REQUEST')
        validate('Ref', protected['call_claim_ref'])
        request = {key: protected[key] for key in ('contract_ref', 'invocation_id', 'execution_id')}
        request, contract, _, lock, deadline = await self._binding(request, set(), operation='invoke_builder')
        launcher = getattr(self.backend, 'builder_launcher', None)
        if launcher is None:
            raise ExecutorBlocked('BUILDER_RUNTIME_BINDINGS_UNAVAILABLE')
        task = asyncio.current_task()
        self.active_tasks[task] = contract['run_id']
        try:
            async with asyncio.timeout_at(deadline), lock:
                # The identity excludes caller presentation fields. Changing
                # prompt, route or timeout can never create a second effect
                # for the same durable model-call claim.
                identity, previous = self.ledger.claim({**request, 'operation': 'invoke_builder',
                    'call_id': protected['call_id'], 'call_claim_ref': protected['call_claim_ref']})
                if previous is not None: return previous
                remaining = min(payload['timeout_s'], deadline - time.monotonic())
                if remaining <= 0: raise ExecutorBlocked('BUILDER_WALL_BUDGET_EXHAUSTED')
                result = await launcher.invoke(protected, payload['prompt'], timeout_s=remaining)
                self.ledger.complete(identity, result)
                return result
        finally:
            self.active_tasks.pop(task, None)

    def handlers(self):
        table = {"prerequisites": self.prerequisites,
                 'read_only_prerequisites': self.read_only_prerequisites,
                 'contain': self.contain, 'invoke_builder': self.invoke_builder, 'builder_test': self.builder_test,
                 'builder_action': self.builder_action,
                 'prepare_attempt_resources': self.prepare_attempt_resources,
                 'activate_attempt_resources': self.activate_attempt_resources}
        for operation in ("measure_job", "run", "provision", "hardware_inventory", "collect_builder", "builder_observation"):
            async def handler(payload, operation=operation):
                return await self.perform(operation, payload)
            table[operation] = handler
        return table


@dataclass(frozen=True)
class IssuedJob:
    job_id: str
    job_token: str


class ExecutorClient:
    def __init__(self, rpc):
        self.rpc = rpc

    async def prerequisites(self):
        return await self.rpc.call("prerequisites", {}, timeout_s=30)

    async def read_only_prerequisites(self):
        state = await self.rpc.call('read_only_prerequisites', {}, timeout_s=30)
        if (not isinstance(state, dict) or set(state) != {'ready', 'scope', 'reasons'}
                or type(state['ready']) is not bool or state['scope'] != 'read_only'
                or not isinstance(state['reasons'], list)):
            raise ExecutorBlocked('INVALID_EXECUTOR_READINESS_RESPONSE')
        return state

    async def _start_resources(self, operation, payload, fields, result_field):
        if type(payload) is not dict or set(payload) != fields:
            raise ExecutorBlocked('INVALID_EXECUTOR_PREPARATION_REQUEST')
        for field in fields:
            validate('Ref', payload[field])
        # A refusal, transport error, timeout or malformed response propagates
        # once. The prepared core owner permanently closes its start path.
        response = await self.rpc.call(operation, copy.deepcopy(payload), timeout_s=30)
        if type(response) is not dict or set(response) != {result_field}:
            raise ExecutorBlocked('INVALID_EXECUTOR_START_RESPONSE')
        validate('Ref', response[result_field])
        return copy.deepcopy(response)

    async def prepare_attempt_resources(self, payload):
        return await self._start_resources('prepare_attempt_resources', payload, {'preparation_ref'}, 'preflight_ref')

    async def activate_attempt_resources(self, payload):
        return await self._start_resources('activate_attempt_resources', payload,
            {'preparation_ref','preflight_ref'}, 'activation_ref')

    async def run_admission_self_test(self, job_ref):
        validate('Ref', job_ref)
        return await self.rpc.call('run_admission_self_test', {'job_ref': copy.deepcopy(job_ref)}, timeout_s=3600)

    async def contain_run(self, run_id, request_id):
        return await self.rpc.call('contain', {'run_id': run_id, 'request_id': request_id}, timeout_s=30)

    async def invoke_builder(self, protected, prompt, *, timeout_s):
        if type(timeout_s) not in (int, float) or not math.isfinite(timeout_s) or not 0 < timeout_s <= 600:
            raise ExecutorBlocked('INVALID_BUILDER_REQUEST')
        return await self.rpc.call('invoke_builder', {'protected': copy.deepcopy(protected),
            'prompt': prompt, 'timeout_s': timeout_s}, timeout_s=timeout_s + 20)

    def bind_invocation(self, *, contract_ref, invocation_id, contract, execution_id=None):
        return RemoteInvocation(self.rpc, contract_ref, invocation_id, contract, execution_id)


class RemoteInvocation:
    def __init__(self, rpc, contract_ref, invocation_id, contract, execution_id):
        self.rpc = rpc
        self.contract = copy.deepcopy(contract)
        self.binding = {"contract_ref": copy.deepcopy(contract_ref), "invocation_id": invocation_id, "execution_id": execution_id}
        self.jobs = {}

    def _request(self, contract):
        if contract != self.contract:
            raise ExecutorBlocked("INVOCATION_CONTRACT_MISMATCH")
        return copy.deepcopy(self.binding)

    async def measure_job(self, contract, inputs, **selection):
        value = await self.rpc.call("measure_job", {**self._request(contract), "selection": selection}, timeout_s=30)
        job = IssuedJob(**value)
        self.jobs[job.job_id] = job
        return job

    async def run(self, job):
        if not isinstance(job, IssuedJob) or self.jobs.get(job.job_id) != job:
            raise ExecutorBlocked("UNISSUED_EXECUTION_JOB")
        return await self.rpc.call("run", {**self.binding, "job_id": job.job_id, "job_token": job.job_token}, timeout_s=3600)

    async def provision(self, contract, inputs, lock_pins):
        return await self.rpc.call("provision", self._request(contract), timeout_s=3600)

    async def hardware_inventory(self, contract):
        return await self.rpc.call("hardware_inventory", self._request(contract), timeout_s=30)

    async def collect_builder(self, contract):
        return await self.rpc.call("collect_builder", self._request(contract), timeout_s=30)

    async def builder_observation(self, contract):
        return await self.rpc.call("builder_observation", self._request(contract), timeout_s=30)

    async def builder_test(self, contract, *, manifest_ref, tests_ref, ordinal):
        return await self.rpc.call('builder_test', {**self._request(contract),
            'manifest_ref': manifest_ref, 'tests_ref': tests_ref, 'ordinal': ordinal},
            timeout_s=min(600, contract['subnode_limits']['time_s']))

    async def builder_action(self, contract, *, action, arguments, ordinal, model_ordinal):
        return await self.rpc.call('builder_action',{**self._request(contract),'action':action,
            'arguments':arguments,'ordinal':ordinal,'model_ordinal':model_ordinal},
            timeout_s=min(600,contract['subnode_limits']['time_s']))


async def serve():
    if os.geteuid() != 0:
        raise ExecutorBlocked("PROTECTED_ROOT_BROKER_REQUIRED")
    from .bootstrap import _read_json
    from .native_ports import APP_UID, AUTH_PROTOCOL
    from .store_custody import CustodyStore
    from .executor_bootstrap import create_scientific_backend, decode_inputs
    session = _read_json("/run/ai4r/session.json", uid=APP_UID)
    root = Path("/run/ai4r-executor")
    root.mkdir(mode=0o710, exist_ok=True)
    root.chmod(0o710)
    os.chown(root, 0, APP_UID)
    auth = PrivateRPCClient("/run/ai4r/authorization.sock", protocol=AUTH_PROTOCOL, peer_uid=APP_UID, **session)
    async def authorize(payload):
        return await auth.call("authorize_executor_binding", payload)
    async def authorize_preparation(payload):
        return await auth.call('authorize_executor_preparation',payload)
    async def publish_scientific_receipt(kind,record,preparation_ref):
        return await auth.call('publish_scientific_start_receipt',
            {'kind':kind,'record':record,'preparation_ref':preparation_ref})
    async def authorize_containment(payload):
        return await auth.call('authorize_containment', payload)
    async def authorize_builder(protected):
        fields = ('execution_id', 'invocation_id', 'call_id', 'call_claim_ref', 'contract_ref')
        await auth.call('authorize_model_dispatch', {key: protected[key] for key in fields})
        return await authorize({key: protected[key] for key in ('contract_ref', 'invocation_id', 'execution_id')})
    ledger = ClaimLedger("/var/lib/ai4r-executor/ledger")
    store = CustodyStore(os.environ.get("JIUWENSWARM_M1_STATE", "/var/lib/ai4r"), "/run/ai4r-store",
        scientific_receipt_publisher=publish_scientific_receipt)
    from .native_profile import M1_REFUSAL_REASON
    backend = None if M1_REFUSAL_REASON else create_scientific_backend(store=store, authorize=authorize,
        authorize_builder=authorize_builder, environ=os.environ)
    from .evaluation_executor import EvaluationExecutorAdapter
    evaluation_adapter = EvaluationExecutorAdapter(store, backend) if backend is not None else None
    attempt_ledger=None;attempt_broker=None
    if backend is not None:
        from .science_start import AttemptLeaseLedger,ScienceAttemptBroker
        attempt_ledger=AttemptLeaseLedger('/var/lib/ai4r-executor/attempts',broker_instance_id='broker:'+uuid.uuid4().hex)
        async def inspect_attempt(payload):return await auth.call('inspect_scientific_attempt',payload)
        async def inspect_evaluation(payload):return await auth.call('inspect_scientific_evaluation',payload)
        attempt_broker=ScienceAttemptBroker(store=store,registration=backend.science_registration,ledger=attempt_ledger,
            authorize_preparation=authorize_preparation,publish_receipt=store.publish_scientific_start_receipt,
            inspect_attempt=inspect_attempt,inspect_evaluation=inspect_evaluation)
    operations = ExecutionOperations(backend=backend, authorize=authorize,
        resolve_inputs=lambda contract: decode_inputs(store, contract), ledger=ledger,
        authorize_containment=authorize_containment, evaluation_adapter=evaluation_adapter,attempt_broker=attempt_broker)
    if attempt_broker is not None:attempt_broker.active_operations=operations.active_tasks
    # IF013 uses a separate finite pre-admission authorization. It cannot
    # reconstruct an ordinary admitted execution grant or choose a command.
    from .admission_executor import AdmissionExecutor
    from .executor import RestrictedExecutor
    async def authorize_admission(job_ref):
        return await auth.call('authorize_admission_self_test', {'job_ref': job_ref})
    admission_kernel = RestrictedExecutor(workspace_root='/workspace/poc',
        cgroup_root=os.environ.get('AI4R_EXECUTOR_CGROUP_ROOT', '/unavailable-admission-delegation'),
        authorize_job=lambda job: (_ for _ in ()).throw(ExecutorBlocked('ORDINARY_GRANT_REQUIRED')),
        capture=store.put_blob)
    admission = AdmissionExecutor(store, admission_kernel, authorize=authorize_admission,
        ledger=ledger, staging_root='/workspace/poc/admission')
    async def run_admission(payload):
        if M1_REFUSAL_REASON or not isinstance(payload, dict) or set(payload) != {'job_ref'}:
            raise ExecutorBlocked('INVALID_ADMISSION_SELF_TEST_REQUEST')
        validate('Ref', payload['job_ref'])
        return await admission.run(payload['job_ref'])
    handlers = operations.handlers()
    handlers['run_admission_self_test'] = run_admission
    def record_fault(operation, payload, fault):
        # Protected diagnostic: class, code and in-package frame only. The RPC
        # reply stays masked; collection reads this record to name the cause.
        scope = {}
        try:
            contract = store.read_record(payload['contract_ref'])
            scope = {key: contract[key] for key in ('run_id', 'node_id', 'attempt_id') if isinstance(contract.get(key), str)}
        except Exception:
            pass
        store.append_record('executor-rpc-fault', {**scope, 'operation': operation,
            'invocation_id': payload.get('invocation_id') if isinstance(payload.get('invocation_id'), str) else None,
            **fault})
    server = PrivateRPCServer(root / "executor.sock", protocol=PROTOCOL, **session,
        handlers=handlers, allowed_uids={APP_UID}, socket_mode=0o660, directory_mode=0o710, group_id=APP_UID,
        fault_recorder=record_fault)
    stopped = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(signum, stopped.set)
    try:
        await server.start()
        while not stopped.is_set():
            if attempt_broker is not None:await attempt_broker.reconcile_completed()
            try:await asyncio.wait_for(stopped.wait(),timeout=1)
            except TimeoutError:pass
    finally:
        await server.close()
        ledger.close()
        if attempt_ledger is not None:attempt_ledger.close()
        store.close()


if __name__ == "__main__":
    asyncio.run(serve())
