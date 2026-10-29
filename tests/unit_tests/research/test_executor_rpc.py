"""Finite privileged boundary, reauthorization and durable unknown outcomes."""
import copy
import time
from types import SimpleNamespace

import pytest

from jiuwenswarm.research.bridge import BridgeError
from jiuwenswarm.research.executor import ExecutorBlocked
from jiuwenswarm.research.executor_rpc import ClaimLedger, ExecutionOperations, ExecutorClient, IssuedJob

REF = {"id": "contract", "sha256": "a" * 64}
BINDING = {"contract_ref": REF, "invocation_id": "invocation", "execution_id": "execution"}
SELECTION = {"role": "baseline", "repeat_index": 0, "seed": 1, "sequence": 1, "subject_ref": REF, "hardware_ref": REF}


def test_claim_survives_reopen_and_does_not_repeat_unknown_effect(tmp_path):
    ledger = ClaimLedger(tmp_path / "ledger")
    key = {"invocation": "first", "operation": "run"}
    identity, previous = ledger.claim(key)
    assert previous is None
    ledger.close()
    ledger = ClaimLedger(tmp_path / "ledger")
    with pytest.raises(BridgeError, match="DELIVERY_UNKNOWN"):
        ledger.claim(key)
    ledger.complete(identity, {"observation": REF})
    assert ledger.claim(key) == (identity, {"observation": REF})
    ledger.close()


@pytest.mark.asyncio
async def test_builder_broker_reauthorizes_and_never_repeats_a_started_call(tmp_path):
    effects, active = [], True
    async def authorize(request):
        if not active: raise ExecutorBlocked('STOPPED')
        return {**request, 'contract': {'run_id': 'run'},
                'execution_deadline_monotonic_s': time.monotonic() + 30}
    class Launcher:
        async def invoke(self, protected, prompt, *, timeout_s):
            assert protected['call_claim_ref'] == REF and prompt == 'captured prompt'
            assert 0 < timeout_s <= 20
            effects.append(protected['call_id'])
            return {'text': 'captured reply'}
    backend = SimpleNamespace(bind_invocation=lambda **_: object(), builder_launcher=Launcher())
    ledger = ClaimLedger(tmp_path / 'builder-ledger')
    operations = ExecutionOperations(backend=backend, authorize=authorize, resolve_inputs=None, ledger=ledger)
    class RPC:
        async def call(self, operation, payload, **kwargs):
            assert operation == 'invoke_builder'
            return await operations.invoke_builder(payload)
    client = ExecutorClient(RPC())
    protected = {**BINDING, 'call_id': 'call', 'call_claim_ref': REF}
    assert await client.invoke_builder(protected, 'captured prompt', timeout_s=20) == {'text': 'captured reply'}
    assert await client.invoke_builder(protected, 'captured prompt', timeout_s=20) == {'text': 'captured reply'}
    assert effects == ['call']
    active = False
    with pytest.raises(ExecutorBlocked, match='STOPPED'):
        await client.invoke_builder(protected, 'captured prompt', timeout_s=20)
    assert effects == ['call']
    ledger.close()


@pytest.mark.asyncio
async def test_builder_captured_failure_envelope_crosses_rpc_and_replays_only_receipt(tmp_path):
    effects=[]
    terminal={'text':None,'outcome':'failed','terminal_reason':'budget_exceeded',
              'error_code':'budget_exceeded','evidence_refs':[REF],'observed_runtime':True}
    async def authorize(request):
        return {**request,'contract':{'run_id':'run'},'execution_deadline_monotonic_s':time.monotonic()+30}
    class Launcher:
        async def invoke(self,protected,prompt,*,timeout_s):
            effects.append(protected['call_id']);return copy.deepcopy(terminal)
    backend=SimpleNamespace(bind_invocation=lambda **_:object(),builder_launcher=Launcher())
    ledger=ClaimLedger(tmp_path/'terminal-ledger')
    operations=ExecutionOperations(backend=backend,authorize=authorize,resolve_inputs=None,ledger=ledger)
    class RPC:
        async def call(self,operation,payload,**kwargs):return await operations.invoke_builder(payload)
    client=ExecutorClient(RPC());protected={**BINDING,'call_id':'call','call_claim_ref':REF}
    assert await client.invoke_builder(protected,'captured prompt',timeout_s=20)==terminal
    assert await client.invoke_builder(protected,'captured prompt',timeout_s=20)==terminal
    assert effects==['call']
    ledger.close()


@pytest.mark.asyncio
async def test_builder_rpc_refuses_unbounded_timeout_or_command_fields_before_authorization(tmp_path):
    async def authorize(_): pytest.fail('invalid request reached authority')
    ledger = ClaimLedger(tmp_path / 'bad-builder-ledger')
    operations = ExecutionOperations(backend=None, authorize=authorize, resolve_inputs=None, ledger=ledger)
    for timeout in [0, -1, 601, float('inf'), True]:
        with pytest.raises(ExecutorBlocked):
            await operations.invoke_builder({'protected': BINDING, 'prompt': 'text', 'timeout_s': timeout})
    with pytest.raises(ExecutorBlocked):
        await operations.invoke_builder({'protected': BINDING, 'prompt': 'text', 'timeout_s': 20, 'argv': ['/bin/sh']})
    ledger.close()


@pytest.mark.asyncio
async def test_builder_readiness_requires_current_qualification_not_package_presence(tmp_path):
    class Launcher:
        valid = False
        def _qualify(self):
            if not self.valid: raise ExecutorBlocked('qualification unavailable')
    launcher = Launcher()
    backend = SimpleNamespace(prerequisites=lambda: [], builder_launcher=launcher,
        **{name: object() for name in ('job_factory', 'provisioner', 'hardware_probe', 'builder_collector', 'builder_observer')})
    ledger = ClaimLedger(tmp_path / 'readiness-ledger')
    operations = ExecutionOperations(backend=backend, authorize=None, resolve_inputs=None, ledger=ledger)
    assert (await operations.prerequisites({}))['builder_qualified'] is False
    launcher.valid = True
    assert await operations.prerequisites({}) == {'ready': True, 'builder_qualified': True, 'builder_mode': 'isolated_tools', 'reasons': []}
    launcher.valid = False
    assert (await operations.prerequisites({}))['ready'] is False
    ledger.close()


@pytest.mark.asyncio
async def test_paths_commands_and_swapped_authority_never_reach_backend(tmp_path):
    calls = []
    async def authorize(request):
        calls.append(request)
        return {**request, "contract": {"run_id": "run"}, 'execution_deadline_monotonic_s': time.monotonic()+30}
    ledger = ClaimLedger(tmp_path / "ledger")
    operations = ExecutionOperations(backend=None, authorize=authorize, resolve_inputs=None, ledger=ledger)
    assert (await operations.prerequisites({}))["ready"] is False
    with pytest.raises(ExecutorBlocked, match="INVALID_EXECUTOR_REQUEST"):
        await operations.perform("measure_job", {**BINDING, "selection": SELECTION, "argv": ["/bin/sh"]})
    assert not calls
    with pytest.raises(ExecutorBlocked, match="SCIENCE_RUNTIME_BINDINGS_UNAVAILABLE"):
        await operations.perform("hardware_inventory", BINDING)
    assert calls == [BINDING]
    ledger.close()


@pytest.mark.asyncio
async def test_private_job_never_serializes_paths_and_reauthorizes_before_every_effect(tmp_path):
    calls, effects = [], []
    active = True
    async def authorize(request):
        calls.append(copy.deepcopy(request))
        if not active:
            raise ExecutorBlocked("STOPPED")
        return {**request, "contract": {"run_id": "run"}, 'execution_deadline_monotonic_s': time.monotonic()+30}
    class Bound:
        async def measure_job(self, contract, inputs, **selection):
            assert contract == {"run_id": "run"} and inputs == {"captured": "inputs"}
            return SimpleNamespace(job_id="protected-job", cwd="/protected/not-exported", argv=["fixed"])
        async def run(self, job):
            effects.append(job)
            return {"receipt": REF, "observed_runtime": True}
    backend = SimpleNamespace(bind_invocation=lambda **_: Bound())
    ledger = ClaimLedger(tmp_path / "ledger")
    operations = ExecutionOperations(backend=backend, authorize=authorize,
        resolve_inputs=lambda _: {"captured": "inputs"}, ledger=ledger)
    class RPC:
        async def call(self, operation, payload, **kwargs):
            return await operations.perform(operation, payload)
    client = ExecutorClient(RPC()).bind_invocation(**BINDING, contract={"run_id": "run"})
    job = await client.measure_job({"run_id": "run"}, {"untrusted": "ignored"}, **SELECTION)
    assert set(vars(job)) == {"job_id", "job_token"}
    with pytest.raises(ExecutorBlocked, match="UNISSUED"):
        await client.run(IssuedJob(job.job_id, "swapped"))
    result = await client.run(job)
    assert await client.run(job) == result  # exact captured result, no second run
    assert len(effects) == 1
    active = False
    with pytest.raises(ExecutorBlocked, match="STOPPED"):
        await client.run(job)
    assert len(effects) == 1 and len(calls) == 4
    ledger.close()


# I032 controls prove local protocol/decoder/ledger mechanics, never a qualified scientific or GPU service.
@pytest.mark.asyncio
@pytest.mark.parametrize('operation,fields,result_field', [
    ('prepare_attempt_resources', {'preparation_ref': REF}, 'preflight_ref'),
    ('activate_attempt_resources', {'preparation_ref': REF, 'preflight_ref': REF}, 'activation_ref'),
], ids=('prepare', 'activate'))
async def test_scientific_start_client_exact_closed_transport_and_unknown(operation, fields, result_field):
    seen = []
    class RPC:
        fail = False
        async def call(self, name, payload, **options):
            seen.append((name, copy.deepcopy(payload), options))
            if self.fail: raise BridgeError('DELIVERY_UNKNOWN')
            return {result_field: copy.deepcopy(REF)}
    rpc = RPC(); client = ExecutorClient(rpc)
    method = getattr(client, operation)
    assert await method(copy.deepcopy(fields)) == {result_field: REF}
    assert seen == [(operation, fields, {'timeout_s': 30})]
    rpc.fail = True
    with pytest.raises(BridgeError, match='DELIVERY_UNKNOWN'):
        await method(copy.deepcopy(fields))
    assert len(seen) == 2  # no hidden retry after ambiguous delivery
    with pytest.raises(ExecutorBlocked):
        await method(fields | {'resource_key': 'caller-selected'})
    assert len(seen) == 2



def _i032_runtime_data():
    import sys
    return {'schema': 'ai4r-science-runtime:2', 'id': 'data-only-not-a-service', 'build_id': 'data-only',
        'profile': {'asset_root': '/var/lib/ai4r-executor/assets',
            'environment_root': '/var/lib/ai4r-executor/environments', 'memory_mb': 128, 'pids_max': 8,
            'run_timeout_s': 10, 'provision_timeout_s': 10, 'baseline_arguments': [], 'treatment_arguments': [],
            'uv_path': '/usr/local/bin/uv', 'python_path': sys._base_executable},
        'approved_environments': [], 'gpu_required': True, 'execution_bindings': []}



def test_science_runtime_v2_data_decoder_has_no_qualification_or_registration():
    from jiuwenswarm.research import executor_bootstrap
    decode = getattr(executor_bootstrap, 'decode_science_runtime_record')
    data = _i032_runtime_data(); original = copy.deepcopy(data)
    definition = decode(data)
    assert definition.record == original and data == original
    assert not hasattr(definition, 'authorize') and not hasattr(definition, 'backend')
    assert not hasattr(definition, 'qualified')  # decoding never makes a service



@pytest.mark.parametrize('invalid', [True, float('inf'), float('-inf'), float('nan'), 0, -1], ids=('boolean','infinity','negative_infinity','nan','zero','negative'))
def test_science_runtime_v2_decoder_rejects_nonfinite_boolean_or_nonpositive_profile(invalid):
    from jiuwenswarm.research import executor_bootstrap
    decode = getattr(executor_bootstrap, 'decode_science_runtime_record')
    for field in ('memory_mb', 'pids_max', 'run_timeout_s', 'provision_timeout_s'):
        value = _i032_runtime_data(); value['profile'][field] = invalid
        with pytest.raises(ExecutorBlocked): decode(value)



def test_science_runtime_v2_decoder_rejects_duplicate_semantic_mapping():
    from jiuwenswarm.research import executor_bootstrap
    decode = getattr(executor_bootstrap, 'decode_science_runtime_record')
    value = _i032_runtime_data()
    entry = {key: copy.deepcopy(REF) for key in ('configuration_ref', 'policy_ref', 'resource_inventory_ref',
                                                'declaration_ref', 'admission_ref')}
    entry.update(implementation_refs=[REF], dependency_refs=[], operations=['run'])
    value['execution_bindings'] = [entry, entry | {'operations': ['provision']}]
    with pytest.raises(ExecutorBlocked): decode(value)



def test_science_runtime_v1_decoder_is_historical_only_and_cannot_install_fresh():
    from jiuwenswarm.research import executor_bootstrap
    decode = getattr(executor_bootstrap, 'decode_science_runtime_record')
    value = _i032_runtime_data(); value['schema'] = 'ai4r-science-runtime:1'; del value['execution_bindings']
    with pytest.raises(ExecutorBlocked): decode(value)
    assert decode(value, historical=True).record == value



def test_attempt_ledger_preserves_held_unknown_ownership_after_restart(tmp_path):
    from jiuwenswarm.research.science_start import AttemptLeaseLedger
    first = AttemptLeaseLedger(tmp_path / 'attempt-ledger', broker_instance_id='first')
    lease = first.acquire(parent_ref=REF, parent_identity=('run', 'node', 'attempt'))
    assert first.inspect(lease)['state'] == 'held'
    first.close()
    second = AttemptLeaseLedger(tmp_path / 'attempt-ledger', broker_instance_id='second')
    try:
        assert second.inspect(lease)['state'] == 'quarantined'
        with pytest.raises(ExecutorBlocked):
            second.acquire(parent_ref=REF, parent_identity=('run', 'node', 'attempt'))
        with pytest.raises(ExecutorBlocked):
            second.acquire(parent_ref={'id': 'other-alias', 'sha256': 'b' * 64}, parent_identity=('other', 'node', 'attempt'))
    finally: second.close()



def test_attempt_ledger_never_releases_from_terminal_without_cessation(tmp_path):
    from jiuwenswarm.research.science_start import AttemptLeaseLedger
    ledger = AttemptLeaseLedger(tmp_path / 'held-ledger', broker_instance_id='original')
    try:
        lease = ledger.acquire(parent_ref=REF, parent_identity=('run', 'node', 'attempt'))
        assert ledger.inspect(lease)['state'] == 'held'
        assert not hasattr(ledger, 'release')  # no caller terminal/boolean release operation
        with pytest.raises(ExecutorBlocked):
            ledger.acquire(parent_ref={'id': 'different-profile-alias', 'sha256': 'b' * 64},
                           parent_identity=('other-account', 'node', 'attempt'))
        assert ledger.inspect(lease)['state'] == 'held'
    finally: ledger.close()

