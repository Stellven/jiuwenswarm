import asyncio
import hashlib
import io
import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from jiuwenswarm.research.builder_testing import BuilderTestService
from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.executor import InvocationBinding, PreparedEnvironment, ReadonlyMount
from jiuwenswarm.research.state import json_bytes


class MemoryStore:
    def __init__(self):
        self.blobs, self.records, self.appended = {}, {}, []

    def put_blob(self, raw, **_):
        digest = hashlib.sha256(raw).hexdigest()
        ref = {'id': 'blob:' + digest, 'sha256': digest}
        self.blobs[digest] = bytes(raw)
        return ref

    def read_blob(self, ref):
        raw = self.blobs[ref['sha256']]
        assert hashlib.sha256(raw).hexdigest() == ref['sha256']
        return raw

    def put_record(self, contract_id, record, **_):
        ref = self.put_blob(json_bytes(record), media_type='application/json')
        self.records[(ref['id'], ref['sha256'])] = (contract_id, dict(record))
        return ref

    def read_record(self, ref, contract_id=None):
        # Match SQLiteRunStore: captured candidate JSON blobs are readable and
        # schema validation does not require a protected record-kind claim.
        record = json.loads(self.read_blob(ref))
        if contract_id:
            from jiuwenswarm.research.contracts import validate
            # This fixture deliberately uses partial declaration/lock records;
            # full manifest validation is exercised by the service itself.
            if contract_id == 'poc-manifest': validate(contract_id, record)
        return record

    def append_record(self, kind, record):
        ref = self.put_blob(json_bytes(record), media_type='application/json')
        self.records[(ref['id'], ref['sha256'])] = (kind, dict(record))
        self.appended.append((kind, dict(record), ref))
        return ref


def fixture(tmp_path):
    store = MemoryStore()
    blueprint = {'metrics': [{'metric_id': 'accuracy'}]}
    blueprint_ref = store.put_record('hypothesis-blueprint:field-contract:2', blueprint)
    requirements_ref = store.put_blob(b'')
    lock = {'requirements_ref': requirements_ref}
    lock_ref = store.put_record('environment-lock:field-contract:1', lock)
    public = {'schema': 'ai4r-classification-data:1', 'dataset_id': 'tiny',
        'feature_names': ['x'], 'classes': ['a', 'b'],
        'train': [{'id': 'tr-1', 'features': [0.0], 'label': 'a'}],
        'test': [{'id': 'te-1', 'features': [0.1]}]}
    data_ref = store.put_blob(json_bytes(public))
    validation = {'schema_version': '1.0.0', 'id': 'validation', 'kind': 'validation data',
        'origin': 'test', 'revision': data_ref['sha256'],
        'files': [{'path': 'data.json', 'artifact_ref': data_ref, 'media_type': 'application/json', 'audience': 'authorized researcher'}],
        'access': 'read-only', 'license': 'test', 'availability': 'available', 'environment_ref': lock_ref}
    validation_ref = store.put_record('resource-snapshot', validation)

    patch = b'def predict(train, test):\n    return ["a" for row in test]\n'
    harness = (b'import json\nimport poc_patch\n'
        b'data=json.load(open("/resources/validation/data.json", encoding="utf-8"))\n'
        b'labels=poc_patch.predict(data["train"], data["test"])\n'
        b'predictions=[{"id": row["id"], "label": label} for row,label in zip(data["test"],labels)]\n'
        b'print(json.dumps({"predictions": predictions}, allow_nan=False))\n')
    test_source = (b'import unittest\nimport poc_patch\n'
        b'class CandidateTests(unittest.TestCase):\n'
        b'    def test_predict_returns_one_label(self):\n'
        b'        self.assertEqual(poc_patch.predict([], [{"id":"x","features":[0]}]), ["a"])\n')
    files = {'requirements.txt': b'', 'poc_patch.py': patch, 'run_benchmark.py': harness}
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    bundle = archive.getvalue()
    bundle_ref = store.put_blob(bundle)
    file_refs = {name: store.put_blob(content) for name, content in files.items()}
    manifest = {'schema_version': '2.0.0', 'id': 'poc_manifest', 'blueprint_ref': blueprint_ref,
        'environment_ref': lock_ref, 'archive_ref': bundle_ref,
        'files': [{'path': name, 'artifact_ref': file_refs[name], 'media_type': 'text/plain', 'audience': 'authorized researcher'}
                  for name in files], 'dependencies': []}
    manifest_ref = store.put_record('poc-manifest', manifest)
    tests_ref = store.put_blob(test_source)
    declaration_ref = store.put_record('capsule-declaration', {'identity': {'name': 'research.builder', 'version_label': 'm1-13'},
        'ports': {'inputs': [{'name': name} for name in ('blueprint', 'lock', 'validation_resource')]}})
    contract = {'run_id': 'run-1', 'node_id': 'builder', 'attempt_id': 'builder-a1',
        'inputs': [{'name': 'blueprint', 'artifact_refs': [blueprint_ref]},
            {'name': 'lock', 'artifact_refs': [lock_ref]},
            {'name': 'validation_resource', 'artifact_refs': [validation_ref]}],
        'bindings': [{'declaration_ref': declaration_ref, 'limits': {'memory_mb': 256}}],
        'subnode_limits': {'time_s': 120, 'memory_mb': 256}}
    binding = InvocationBinding(contract_ref={'id': 'contract-1', 'sha256': 'a' * 64},
        invocation_id='inv-1', contract=contract, execution_id='exec-1')

    class Adapter:
        def __init__(self):
            self.profile = SimpleNamespace(memory_mb=256, pids_max=32)
            self.scorer = None
            self._prepared = {}
            self.provision_calls = []

        async def provisioner(self, contract_arg, inputs_arg, pins, *, binding, builder_manifest_ref):
            self.provision_calls.append((dict(pins), builder_manifest_ref))
            environment = PreparedEnvironment(Path(tmp_path), lock_ref)
            self._prepared[binding.invocation_id] = (environment, {}, dict(pins))
            return {'schema_version': '1.0.0', 'id': 'provisioning_receipt',
                'environment_lock_ref': lock_ref, 'poc_manifest_ref': builder_manifest_ref,
                'status': 'succeeded', 'python_version': '3.12.0', 'venv_path': '/workspace/poc/.venv',
                'runner_user': 'executor:10002', 'packages': [], 'network_policy_used': 'none',
                'network_allowlist': [], 'unlisted_network_requests': 0,
                'effects': [{'op': 'create_venv', 'target': '/workspace/poc/.venv', 'outcome': 'ok'}],
                'limits': {'wall_s_limit': 30, 'wall_s_used': 1}}

        def environment_verifier(self, environment):
            assert environment.ref == lock_ref

        def workspace_allocator(self, binding_arg, sequence, role):
            assert role == 'builder_test'
            return tmp_path / f'work-{sequence}'

        def _remaining(self, contract_arg, binding_arg, cap):
            return min(cap, 30)

        def _resource(self, resource, ref, target):
            return ReadonlyMount(tmp_path / ('asset-' + target.rsplit('/', 1)[-1]), target, ref)

    class Executor:
        uid = gid = 10002

        def __init__(self):
            self.jobs = []
            self.selftest_exit = 0
            self.smoke_output = None
            self.proof_ready = True

        async def run(self, job):
            self.jobs.append(job)
            proof = {'ready': self.proof_ready, 'executor_uid': self.uid, 'executor_gid': self.gid,
                'cap_effective': '0000000000000000', 'no_new_privileges': '1', 'network': 'none'}
            proof_ref = store.put_record('isolation-proof', proof)
            stdout = b'' if job.sequence % 2 else (self.smoke_output if self.smoke_output is not None else
                b'{"predictions":[{"id":"te-1","label":"a"}]}\n')
            stdout_ref, stderr_ref = store.put_blob(stdout), store.put_blob(b'')
            return {'job_id': job.job_id, 'contract_ref': dict(binding.contract_ref),
                'invocation_id': binding.invocation_id, 'observed_runtime': True,
                'exit_code': self.selftest_exit if job.sequence % 2 else 0,
                'termination_reason': 'completed', 'stdout_ref': stdout_ref,
                'stderr_ref': stderr_ref, 'observed_limits': {'isolation_probe_ref': proof_ref,
                    'memory_max': str(job.memory_mb * 1024 * 1024), 'pids_max': str(job.pids_max), 'network': 'none'}}

    adapter, executor, registrations = Adapter(), Executor(), []
    service = BuilderTestService(store, adapter, executor,
        authorize_binding=lambda supplied: supplied,
        register_job=lambda job, supplied: registrations.append((job, supplied)))
    inputs = {'blueprint': blueprint, 'lock': lock, 'validation_resource': validation}
    return (service, store, adapter, executor, registrations, contract, binding, inputs,
            manifest_ref, tests_ref)


@pytest.mark.asyncio
async def test_builder_test_runs_selftest_then_smoke_and_records_raw_unscored_evidence(tmp_path):
    (service, store, adapter, executor, registrations, contract, binding, inputs,
     manifest_ref, tests_ref) = fixture(tmp_path)
    result = await service.test(contract, inputs, binding=binding, manifest_ref=manifest_ref,
        tests_ref=tests_ref, ordinal=1)
    assert result['schema'] == 'ai4r-builder-test:1'
    assert result['status'] == 'passed'
    assert result['ordinal'] == 1 and len(result['runs']) == 2
    assert [job.sequence for job in executor.jobs] == [1, 2]
    assert [job.argv[1] for job in executor.jobs] == ['-I', '/resources/poc/run_benchmark.py']
    assert all(job.output_limit_bytes == 1024 * 1024 for job in executor.jobs)
    assert len(registrations) == 2 and len(adapter.provision_calls) == 1
    kernel=[row for row in store.appended if row[0]=='builder_kernel_execution']
    assert len(kernel)==2 and [row[1]['receipt'] for row in kernel]==result['runs']
    kind, recorded, recorded_ref = next(row for row in store.appended if row[0]=='builder_test_execution')
    assert kind == 'builder_test_execution' and recorded == {k: v for k, v in result.items() if k not in {'evidence_ref', 'report_ref'}}
    assert result['evidence_ref'] == result['report_ref'] == recorded_ref
    assert recorded['scoring_performed'] is False


@pytest.mark.asyncio
async def test_builder_test_rejects_invalid_utf8_test_source_before_provision_or_execution(tmp_path):
    (service, store, adapter, executor, registrations, contract, binding, inputs,
     manifest_ref, tests_ref) = fixture(tmp_path)
    bad_tests = store.put_blob(b'\xff')
    with pytest.raises(ResearchError, match='valid UTF-8 Python'):
        await service.test(contract, inputs, binding=binding, manifest_ref=manifest_ref,
            tests_ref=bad_tests, ordinal=1)
    assert adapter.provision_calls == [] and executor.jobs == [] and registrations == []


@pytest.mark.asyncio
async def test_builder_test_ordinals_increase_and_environment_is_provisioned_once(tmp_path):
    (service, store, adapter, executor, registrations, contract, binding, inputs,
     manifest_ref, tests_ref) = fixture(tmp_path)
    first = await service.test(contract, inputs, binding=binding, manifest_ref=manifest_ref,
        tests_ref=tests_ref, ordinal=1)
    second = await service.test(contract, inputs, binding=binding, manifest_ref=manifest_ref,
        tests_ref=tests_ref, ordinal=3)
    assert first['status'] == second['status'] == 'passed'
    assert len(adapter.provision_calls) == 1
    assert [job.sequence for job in executor.jobs] == [1, 2, 5, 6]
    with pytest.raises(ResearchError, match='ordinals must increase'):
        await service.test(contract, inputs, binding=binding, manifest_ref=manifest_ref,
            tests_ref=tests_ref, ordinal=3)


@pytest.mark.asyncio
async def test_builder_test_rejects_wrong_admitted_builder_release_before_effects(tmp_path):
    (service, store, adapter, executor, registrations, contract, binding, inputs,
     manifest_ref, tests_ref) = fixture(tmp_path)
    ref = contract['bindings'][0]['declaration_ref']
    declaration = store.read_record(ref)
    declaration['identity']['version_label'] = 'm1-12'
    contract['bindings'][0]['declaration_ref'] = store.put_record('capsule-declaration', declaration)
    with pytest.raises(ResearchError, match='m1-13'):
        await service.test(contract, inputs, binding=binding, manifest_ref=manifest_ref,
            tests_ref=tests_ref, ordinal=1)
    assert adapter.provision_calls == [] and executor.jobs == []


@pytest.mark.asyncio
async def test_builder_test_rejects_manifest_with_foreign_blueprint_ref_before_provision(tmp_path):
    (service, store, adapter, executor, registrations, contract, binding, inputs,
     manifest_ref, tests_ref) = fixture(tmp_path)
    manifest = store.read_record(manifest_ref)
    manifest['blueprint_ref'] = {'id': 'foreign', 'sha256': 'f' * 64}
    foreign_manifest_ref = store.put_record('poc-manifest', manifest)
    with pytest.raises(ResearchError, match='frozen blueprint and lock'):
        await service.test(contract, inputs, binding=binding, manifest_ref=foreign_manifest_ref,
            tests_ref=tests_ref, ordinal=1)
    assert adapter.provision_calls == [] and executor.jobs == []


@pytest.mark.asyncio
async def test_builder_test_records_failed_selftest_but_runs_independent_smoke(tmp_path):
    (service, store, adapter, executor, registrations, contract, binding, inputs,
     manifest_ref, tests_ref) = fixture(tmp_path)
    executor.selftest_exit = 1
    result = await service.test(contract, inputs, binding=binding, manifest_ref=manifest_ref,
        tests_ref=tests_ref, ordinal=1)
    assert result['status'] == 'failed'
    assert len(result['runs']) == 2 and [job.sequence for job in executor.jobs] == [1, 2]
    assert result['diagnostics']['selftest_exit_code'] == 1


@pytest.mark.asyncio
async def test_builder_test_rejects_invalid_smoke_predictions_without_scoring(tmp_path):
    (service, store, adapter, executor, registrations, contract, binding, inputs,
     manifest_ref, tests_ref) = fixture(tmp_path)
    executor.smoke_output = b'{"predictions":[{"id":"te-1","label":"not-a-class"}]}\n'
    result = await service.test(contract, inputs, binding=binding, manifest_ref=manifest_ref,
        tests_ref=tests_ref, ordinal=1)
    assert result['status'] == 'failed'
    assert result['diagnostics']['prediction_output_valid'] is False
    assert result['scoring_performed'] is False


@pytest.mark.asyncio
async def test_builder_test_fails_closed_when_kernel_isolation_proof_is_missing(tmp_path):
    (service, store, adapter, executor, registrations, contract, binding, inputs,
     manifest_ref, tests_ref) = fixture(tmp_path)
    executor.proof_ready = False
    with pytest.raises(ResearchError, match='isolation proof'):
        await service.test(contract, inputs, binding=binding, manifest_ref=manifest_ref,
            tests_ref=tests_ref, ordinal=1)
    assert len(executor.jobs) == 1 and len(registrations) == 1


@pytest.mark.asyncio
async def test_cancelled_kernel_receipt_cannot_launch_a_second_job(tmp_path):
    (service, store, adapter, executor, registrations, contract, binding, inputs,
     manifest_ref, tests_ref) = fixture(tmp_path)
    original = executor.run
    async def cancelled(job):
        raw = await original(job)
        return dict(raw, termination_reason='cancelled')
    executor.run = cancelled
    with pytest.raises(asyncio.CancelledError):
        await service.test(contract, inputs, binding=binding, manifest_ref=manifest_ref,
            tests_ref=tests_ref, ordinal=1)
    assert len(executor.jobs) == 1


@pytest.mark.asyncio
async def test_candidate_manifest_can_be_a_captured_json_blob(tmp_path):
    (service, store, adapter, executor, registrations, contract, binding, inputs,
     manifest_ref, tests_ref) = fixture(tmp_path)
    store.records.pop((manifest_ref['id'], manifest_ref['sha256']))
    result = await service.test(contract, inputs, binding=binding, manifest_ref=manifest_ref,
        tests_ref=tests_ref, ordinal=1)
    assert result['status'] == 'passed'
