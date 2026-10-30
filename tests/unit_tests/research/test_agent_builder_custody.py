"""End-to-end custody join for the agentic Builder host and independent checker.

The test uses the real workspace service and SQLite evidence store. Its model
actions and check executor are deterministic fixtures; no native SDK or kernel
execution is claimed here.
"""
from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import pytest

from jiuwenswarm.research.builder_agent_host import BuilderAgentHost
from jiuwenswarm.research.checks.builder_agent import AgentBuilderChecks
from jiuwenswarm.research.checks.engine import CheckContext
from jiuwenswarm.research.contracts import ResearchError, validate
from jiuwenswarm.research.capsules.assets import source_metadata
from jiuwenswarm.research.state import SQLiteRunStore, json_bytes


def _file_hash(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


@pytest.fixture
def store(tmp_path):
    value = SQLiteRunStore(tmp_path / 'agent-custody-store')
    yield value
    value.close()


def _classification_fixture(store):
    lock = {'schema_version': '1.0.0', 'id': 'unit-lock', 'platform': 'unit-platform',
            'requirements_ref': store.put_blob(b'# stdlib\n'), 'package_refs': [],
            'approval_ref': store.put_blob(b'unit approval')}
    lock_ref = store.put_record('environment-lock', lock)
    blueprint = {'schema_version': '1.0.0', 'id': 'hypothesis_blueprint',
                 'environment_ref': lock_ref, 'metrics': [{'metric_id': 'accuracy'}],
                 'seed': 42, 'repeat_count': 1,
                 'resource_refs': [], 'baseline_identity': {'resource_ref': store.put_blob(b'baseline'),
                     'revision': 'baseline-r1', 'entry_point': 'run.py'}}
    blueprint_ref = store.put_blob(json_bytes(blueprint))
    public = {'schema': 'ai4r-classification-data:1', 'dataset_id': 'public-fixture',
              'feature_names': ['x'], 'classes': ['yes', 'no'],
              'train': [{'id': 'train-1', 'features': [1.0], 'label': 'yes'}],
              'test': [{'id': 'test-1', 'features': [0.5]}]}
    public_ref = store.put_blob(json_bytes(public))
    inputs = {'blueprint': blueprint, 'lock': lock,
              'validation_resource': {'schema_version': '1.0.0', 'id': 'validation_resource',
                  'files': [{'path': 'data.json', 'artifact_ref': public_ref}]}}
    refs = {'blueprint': blueprint_ref, 'lock': lock_ref,
            'validation_resource': store.put_blob(json_bytes(inputs['validation_resource']))}
    declaration = {'schema_version': '1.0.0', 'id': 'research.builder:m1-15',
        'identity': {'name': 'research.builder', 'version_label': 'm1-17', 'carrier': {'ref': 'builder_agent.py'}},
        'ports': {'inputs': [{'name': name} for name in inputs]},
        'needs': {'model': {'tool_calling': False}},
        'budget': {'per_call': {'invocations': 20, 'tool_calls': 40}}}
    declaration_ref = store.put_blob(json_bytes(declaration))
    contract = {'run_id': 'run:builder-agent', 'node_id': 'builder', 'subnode_id': 'builder',
        'attempt_id': 'attempt:builder-agent',
        'inputs': [{'name': name, 'artifact_refs': [refs[name]],
                    'contract_id': 'fixture-input', 'version': '1.0.0'} for name in inputs],
        'outputs': [], 'subnode_limits': {'time_s': 600, 'memory_mb': 256},
        'bindings': [{'declaration_ref': declaration_ref, 'limits': {'time_s': 600, 'memory_mb': 256}}]}
    return inputs, refs, contract, declaration_ref, public_ref


@pytest.mark.asyncio
async def test_agent_actions_and_submitted_snapshot_pass_independent_custody_check(store):
    inputs, refs, contract, declaration_ref, public_ref = _classification_fixture(store)
    contract_ref = store.put_blob(json_bytes(contract))
    binding = SimpleNamespace(contract=contract, contract_ref=contract_ref,
                              invocation_id='invocation:builder-agent', execution_id='execution:builder-agent')
    host = object.__new__(BuilderAgentHost)
    host.store = store
    host.adapter = SimpleNamespace(scorer=SimpleNamespace(protocol='ai4r-classification:1'))
    host.sessions, host.actions = {}, {}
    import asyncio
    host._agent_lock = asyncio.Lock()

    async def authorize(exact_binding):
        return exact_binding
    host.authorize_binding = authorize

    async def fixture_check(check_contract, check_inputs, check_binding, phase, files, test_name):
        assert check_contract is contract
        assert check_binding is binding
        assert phase in {'unit', 'smoke'}
        stdout = (b'{"predictions":[{"id":"test-1","label":"yes"}]}\n'
                  if phase == 'smoke' else b'fixture unit tests passed\n')
        stdout_ref = store.put_blob(stdout)
        stderr_ref = store.put_blob(b'')
        tested_manifest, tested_manifest_ref, _ = host._manifest(check_contract, files)
        isolation_ref = store.append_record('isolation_probe', {'ready': True,
            'executor_uid': 10002, 'executor_gid': 10002, 'no_new_privileges': '1',
            'cap_effective': '0000000000000000', 'network': 'none'})
        raw = {'observed_runtime': True, 'exit_code': 0, 'termination_reason': 'completed',
               'contract_ref': contract_ref, 'invocation_id': binding.invocation_id,
               'execution_id': binding.execution_id, 'stdout_ref': stdout_ref,
               'stderr_ref': stderr_ref, 'subject_ref': tested_manifest['archive_ref'],
               'observed_limits': {'network': 'none', 'isolation_probe_ref': isolation_ref}}
        report = {'schema': 'ai4r-builder-agent-check:1', 'contract_ref': contract_ref,
                  'run_id': contract['run_id'], 'node_id': contract['node_id'],
                  'attempt_id': contract['attempt_id'], 'invocation_id': binding.invocation_id,
                  'execution_id': binding.execution_id, 'check': phase, 'passed': True,
                  'runs': [raw], 'manifest_ref': tested_manifest_ref}
        report_ref = store.append_record('builder_agent_check', report)
        return {'passed': True, 'report_ref': report_ref, 'evidence_ref': report_ref,
                'stdout_ref': stdout_ref, 'stderr_ref': stderr_ref,
                'stdout': stdout.decode(), 'stderr': ''}
    host._check = fixture_check

    async def issue(action, arguments, ordinal):
        # A scoped, completed call and its exact output precede each host action.
        claim_ref = store.append_record('model-call-claim', {'call_ordinal': ordinal})
        call_id = f'model-call:{ordinal}'
        output_ref = store.append_record('model-call-output', {'run_id': contract['run_id'],
            'call_id': call_id, 'invocation_id': binding.invocation_id,
            'text': json.dumps({'action': action, 'arguments': arguments}, separators=(',', ':'))})
        # Real model-call records (closed schema) carry no contract_ref.
        call_ref = store.append_record('model-call', {'id': call_id, 'run_id': contract['run_id'],
            'invocation_id': binding.invocation_id,
            'execution_id': binding.execution_id, 'outcome': 'completed',
            'observed_runtime': True, 'evidence_refs': [output_ref]})
        store.append_record('model-call-start', {'run_id': contract['run_id'],
            'contract_ref': contract_ref, 'invocation_id': binding.invocation_id,
            'execution_id': binding.execution_id, 'call_id': call_id,
            'call_claim_ref': claim_ref})
        result = await host.action(contract, inputs, binding=binding, action=action,
            arguments=arguments, ordinal=ordinal, model_ordinal=ordinal)
        return result, call_ref, output_ref

    initial = {'requirements.txt': '# stdlib\n', 'poc_patch.py': '', 'run_benchmark.py': ''}
    listed, _, _ = await issue('list_files', {}, 1)
    assert listed['ok'] is True
    source_files = {
        'poc_patch.py': ('def predict(train, test):\n'
                         '    label = train[0]["label"]\n'
                         '    return [label for _ in test]\n'),
        'run_benchmark.py': ('import json\n'
            'import random\n'
            'from pathlib import Path\n'
            'import poc_patch\n'
            'random.seed(42)\n'
            'data = json.loads(Path("/resources/validation/data.json").read_text())\n'
            'labels = poc_patch.predict(data["train"], data["test"])\n'
            'predictions = [{"id": row["id"], "label": label} for row, label in zip(data["test"], labels)]\n'
            'print(json.dumps({"predictions": predictions}, allow_nan=False))\n'),
        'tests.py': ('import unittest\n'
            'import poc_patch\n'
            'class TestPredict(unittest.TestCase):\n'
            '    def test_one_label_per_test_row(self):\n'
            '        train = [{"id": "a", "features": [0.0], "label": "yes"}]\n'
            '        test = [{"id": "b", "features": [1.0]}]\n'
            '        self.assertEqual(poc_patch.predict(train, test), ["yes"])\n')}
    for ordinal, (path, content) in enumerate(source_files.items(), 2):
        # Query the actual session state for a valid optimistic file precondition.
        current = host.sessions[binding.invocation_id].inspect()['files'][path]
        result, _, _ = await issue('write_file', {'path': path, 'content': content,
            'expected_sha256': _file_hash(current)}, ordinal)
        assert result['ok'] is True

    premature, _, _ = await issue('submit_candidate', {}, 5)
    assert premature.get('submitted') is not True
    assert premature['error'] == 'current_snapshot_lacks_compile_unit_smoke_passes'
    compile_result, _, _ = await issue('run_checks', {'check': 'compile'}, 6)
    unit_result, _, _ = await issue('run_checks', {'check': 'unit'}, 7)
    smoke_result, _, _ = await issue('run_checks', {'check': 'smoke'}, 8)
    assert compile_result['ok'] is True and unit_result['ok'] is True and smoke_result['ok'] is True
    submitted, _, _ = await issue('submit_candidate', {}, 9)
    assert submitted['submitted'] is True

    receipt_ref = submitted['build_receipt_ref']
    receipt = store.read_record(receipt_ref)
    assert receipt['schema_version'] == '4.0.0'
    assert receipt['trial_executed'] is True and receipt['development_only'] is True
    assert receipt['model_call_count'] == 9 and receipt['tool_operation_count'] == 9
    journal_ref = receipt['journal_ref']
    journal = store.read_record(journal_ref)
    assert store.record_kind(journal_ref) == 'builder_agent_execution'
    assert set(journal['initial_files']) == {'requirements.txt', 'poc_patch.py', 'run_benchmark.py', 'tests.py'}
    assert set(journal['files']) == set(journal['initial_files'])
    assert journal['actions'][4]['result']['error'] == 'current_snapshot_lacks_compile_unit_smoke_passes'

    proposal = {'run_id': contract['run_id'], 'node_id': contract['node_id'],
        'attempt_id': contract['attempt_id'], 'subnode_id': contract['subnode_id'],
        'invocation_id': binding.invocation_id, 'key': 'build_receipt', 'ref': receipt_ref,
        'contract_ref': contract_ref}
    store.append_record('host-record-proposal', proposal)
    manifest_ref = submitted['manifest_ref']
    bundle_ref = submitted['bundle_ref']
    manifest = store.read_record(manifest_ref)
    bundle = store.read_blob(bundle_ref)
    # Fail at the precise public-schema boundary before the aggregate checker
    # turns the first invalid contract into a generic FAIL result.
    for port in source_metadata()['builder']['declaration']['ports']['outputs']:
        value = {'manifest': manifest, 'bundle': bundle}[port['name']]
        if isinstance(value, dict):
            validate(port['schema_ref'], value)
    validate('urn:ai4r:prediction-build-receipt:4.0.0', receipt)
    output_refs = {'manifest': manifest_ref, 'bundle': bundle_ref}
    outputs = {'manifest': manifest, 'bundle': bundle}
    ctx = CheckContext(contract, store, inputs, outputs, output_refs,
        {'contract_ref': contract_ref, 'trace_refs': [
            call['model_call_ref'] for call in journal['actions']]})
    checks = AgentBuilderChecks('builder')
    # Keep a direct diagnostic call alongside the public result-list API so
    # the test reports the underlying contract/evidence failure precisely.
    await checks._builder(ctx, inputs, outputs)
    results = await checks(ctx, inputs, outputs)
    assert results and all(row['outcome'] == 'PASS' for row in results), results

    # A stale unit proof and an output substituted for the claimed model action
    # each fail the independent joins.
    class TamperedContext:
        def __init__(self, base, mutate):
            self.__dict__.update(base.__dict__)
            self._base, self._mutate = base, mutate
        def __getattr__(self, name):
            return getattr(self._base, name)
        def read_json(self, ref):
            return self._mutate(ref, self._base.read_json(ref))

    unit_report_ref = journal['checks']['unit']['report_ref']
    def stale_unit(ref, value):
        if ref == unit_report_ref:
            value = dict(value, snapshot_sha256='0' * 64)
        return value
    with pytest.raises((ResearchError, ValueError)):
        await checks._builder(TamperedContext(ctx, stale_unit), inputs, outputs)

    changed_output_ref = journal['actions'][1]['model_output_ref']
    def changed_model_output(ref, value):
        if ref == changed_output_ref:
            value = dict(value, text=json.dumps({'action': 'write_file', 'arguments': {'path': 'elsewhere'}}))
        return value
    with pytest.raises((ResearchError, ValueError)):
        await checks._builder(TamperedContext(ctx, changed_model_output), inputs, outputs)

    substituted = dict(outputs, bundle=b'not the submitted bundle')
    with pytest.raises((ResearchError, ValueError)):
        await checks._builder(ctx, inputs, substituted)
