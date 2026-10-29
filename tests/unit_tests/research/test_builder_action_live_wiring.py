"""First Builder action through executor_rpc into the real host, with the real model-call record shape."""
import asyncio
import json
import os
import time
from types import SimpleNamespace

import pytest

from jiuwenswarm.research.builder_agent_host import BuilderAgentHost
from jiuwenswarm.research.executor import InvocationBinding
from jiuwenswarm.research.executor_rpc import ClaimLedger, ExecutionOperations
from jiuwenswarm.research.private_rpc import PrivateRPCClient, PrivateRPCServer, fault_summary
from jiuwenswarm.research.router_client import PlatformIntegrityError
from jiuwenswarm.research.state import SQLiteRunStore, json_bytes

pytestmark = pytest.mark.skipif(os.name != 'posix', reason='Linux durable broker custody required')


def _fixture(store):
    lock = {'schema_version': '1.0.0', 'id': 'unit-lock', 'platform': 'p', 'requirements_ref': store.put_blob(b'# stdlib\n'),
            'package_refs': [], 'approval_ref': store.put_blob(b'a')}
    decl = {'schema_version': '1.0.0', 'id': 'research.builder:m1-18',
        'identity': {'name': 'research.builder', 'version_label': 'm1-18', 'carrier': {'ref': 'builder_agent.py'}},
        'ports': {'inputs': []}, 'needs': {'model': {'tool_calling': False}},
        'budget': {'per_call': {'invocations': 20, 'tool_calls': 40}}}
    contract = {'run_id': 'run:wiring', 'node_id': 'builder', 'subnode_id': 'builder', 'attempt_id': 'attempt:w',
        'subnode_limits': {'time_s': 600}, 'inputs': [],
        'bindings': [{'declaration_ref': store.put_blob(json_bytes(decl))}]}
    return {'lock': lock}, contract


@pytest.mark.asyncio
async def test_first_read_file_action_reaches_dispatch_with_real_call_record_shape(tmp_path):
    store = SQLiteRunStore(tmp_path / 'store')
    try:
        inputs, contract = _fixture(store)
        cref = store.put_blob(json_bytes(contract))
        request = {'contract_ref': cref, 'invocation_id': 'inv', 'execution_id': 'exec'}
        action = {'action': 'read_file', 'arguments': {'path': 'poc_patch.py'}}
        claim = store.append_record('model-call-claim', {'call_ordinal': 1})
        out = store.append_record('model-call-output', {'run_id': contract['run_id'], 'call_id': 'call:1',
            'invocation_id': 'inv', 'text': json.dumps(action)})
        # Real model-call records carry no contract_ref; the protected start does.
        store.append_record('model-call', {'id': 'call:1', 'invocation_id': 'inv', 'execution_id': 'exec',
            'outcome': 'completed', 'observed_runtime': True, 'evidence_refs': [out]})
        store.append_record('model-call-start', {'run_id': contract['run_id'], 'contract_ref': cref,
            'invocation_id': 'inv', 'execution_id': 'exec', 'call_id': 'call:1', 'call_claim_ref': claim})
        async def authorize(payload):
            return dict(payload, contract=contract, execution_deadline_monotonic_s=time.monotonic() + 600)
        host = object.__new__(BuilderAgentHost)
        host.store, host.adapter, host.sessions, host.actions = store, SimpleNamespace(scorer=None), {}, {}
        host._agent_lock = asyncio.Lock()
        async def authorize_binding(binding):
            return binding
        host.authorize_binding = authorize_binding
        backend = SimpleNamespace(builder_agent_service=host,
            bind_invocation=lambda **kw: SimpleNamespace(_binding=InvocationBinding(**kw)))
        operations = ExecutionOperations(backend=backend, authorize=authorize,
            resolve_inputs=lambda _: inputs, ledger=ClaimLedger(tmp_path / 'ledger'))
        result = await operations.builder_action(dict(request, ordinal=1, model_ordinal=1, **action))
        assert result['ok'] is True and result['path'] == 'poc_patch.py' and result['content'] == ''
    finally:
        store.close()


def test_fault_summary_names_class_code_and_in_package_frame_only():
    from jiuwenswarm.research.builder_agent_host import BuilderAgentHost
    from jiuwenswarm.research.contracts import ResearchError
    host = object.__new__(BuilderAgentHost)
    host.store = SimpleNamespace(iter_records=lambda **kw: [])
    binding = SimpleNamespace(contract={'run_id': 'r'}, contract_ref={'id': 'secret /etc/passwd'}, invocation_id='i', execution_id='e')
    with pytest.raises(ResearchError) as caught:
        host._model_action(binding, 'read_file', {}, 1)
    summary = fault_summary(caught.value)
    assert summary['exception_class'] == 'ResearchError' and summary['code'] == 'auth'
    assert summary['frame'].startswith('jiuwenswarm.research.builder_agent_host:_model_action:')
    assert 'secret' not in json.dumps(summary) and '/etc' not in json.dumps(summary)


@pytest.mark.asyncio
async def test_masked_fault_is_recorded_before_masking(tmp_path):
    from jiuwenswarm.research.contracts import ResearchError
    seen = []
    async def boom(payload):
        raise ResearchError('auth', 'hidden detail')
    server = PrivateRPCServer(tmp_path / 'd' / 's.sock', protocol='t:1', session_id='s', capability='c',
        handlers={'op': boom}, allowed_uids={os.geteuid()},
        fault_recorder=lambda op, payload, fault: seen.append((op, fault)))
    await server.start()
    try:
        client = PrivateRPCClient(server.path, protocol='t:1', session_id='s', capability='c', peer_uid=os.geteuid())
        with pytest.raises(PlatformIntegrityError):
            await client.call('op', {})
    finally:
        await server.close()
    assert len(seen) == 1 and seen[0][0] == 'op'
    assert seen[0][1]['exception_class'] == 'ResearchError' and seen[0][1]['code'] == 'auth'
    assert 'hidden' not in json.dumps(seen)
