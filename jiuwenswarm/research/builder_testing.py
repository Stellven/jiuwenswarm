"""Bounded host-owned smoke testing for a prediction Builder candidate.

This service checks a candidate package in the already approved offline
environment. It never invokes the trusted scorer or treats producer-authored
test claims as evidence of scientific quality.
"""
from __future__ import annotations

import copy
import asyncio
import hashlib
import inspect
import json
import uuid
from pathlib import Path

from .checks.prediction_bundle import CheckError, inspect_bundle
from .contracts import ResearchError, validate
from .environment import parse_requirements
from .executor import ExecutionJob, InvocationBinding, ReadonlyMount
from .state import json_bytes
from .trusted_scoring import parse_predictions, parse_public_dataset
from .process_evidence import validate_process_evidence


SCHEMA = 'ai4r-builder-test:1'
BUILDER_DECLARATION = 'capsule-declaration'
TEST_LIMIT = 64 * 1024
OUTPUT_LIMIT = 1024 * 1024


async def _await(value):
    return await value if inspect.isawaitable(value) else value


def _input_ref(contract, name):
    rows = [row for row in contract.get('inputs', []) if row.get('name') == name]
    if len(rows) != 1 or len(rows[0].get('artifact_refs', [])) != 1:
        raise ResearchError('builder_test_input', f'Expected one exact {name} input')
    ref = rows[0]['artifact_refs'][0]
    validate('Ref', ref)
    return copy.deepcopy(ref)


def _resource_file(store, resource, path):
    rows = [row for row in resource.get('files', []) if row.get('path') == path]
    if len(rows) != 1:
        raise ResearchError('builder_test_resource', f'Expected one {path} resource file')
    raw = store.read_blob(rows[0]['artifact_ref'])
    return rows[0]['artifact_ref'], raw


def _ref_equal(left, right):
    return type(left) is dict and type(right) is dict and left == right


class BuilderTestService:
    """Run one isolated self-test and one prediction smoke test per ordinal."""

    def __init__(self, store, adapter, executor, authorize_binding, register_job):
        self.store, self.adapter, self.executor = store, adapter, executor
        self.authorize_binding, self.register_job = authorize_binding, register_job
        self._last_ordinal = {}
        self._provisioned = set()
        self._provision_cache = {}
        self._test_lock = asyncio.Lock()

    def _declaration(self, contract):
        rows = contract.get('bindings', [])
        if len(rows) != 1 or not isinstance(rows[0].get('declaration_ref'), dict):
            raise ResearchError('builder_test_declaration', 'One exact Builder declaration is required')
        ref = rows[0]['declaration_ref']
        declaration = self.store.read_record(ref, contract_id=BUILDER_DECLARATION)
        identity = declaration.get('identity', {})
        if identity.get('name') != 'research.builder' or identity.get('version_label') != 'm1-13':
            raise ResearchError('builder_test_declaration', 'Builder testing requires the admitted research.builder m1-13 declaration')
        ports = declaration.get('ports', {})
        names = {row.get('name') for row in ports.get('inputs', []) if isinstance(row, dict)}
        if not {'blueprint', 'lock', 'validation_resource'} <= names:
            raise ResearchError('builder_test_declaration', 'Builder declaration must pin blueprint, lock and public validation inputs')
        return declaration

    def _candidate(self, manifest_ref, blueprint_ref, lock_ref, inputs):
        manifest = self.store.read_record(manifest_ref, contract_id='poc-manifest')
        validate('poc-manifest', manifest)
        if (manifest.get('schema_version') != '2.0.0'
                or not _ref_equal(manifest.get('blueprint_ref'), blueprint_ref)
                or not _ref_equal(manifest.get('environment_ref'), lock_ref)):
            raise ResearchError('builder_test_manifest', 'Candidate manifest does not match the frozen blueprint and lock')
        archive_ref = manifest.get('archive_ref')
        validate('Ref', archive_ref)
        bundle = self.store.read_blob(archive_ref)
        lock = inputs['lock']
        lock_pins = parse_requirements(self.store.read_blob(lock['requirements_ref']))
        blueprint = inputs['blueprint']
        metric_ids = [metric['metric_id'] for metric in blueprint.get('metrics', [])]
        try:
            checked = inspect_bundle(bundle, metric_ids, lock_pins, output_protocol='ai4r-predictions:1')
        except (CheckError, ValueError, TypeError) as exc:
            raise ResearchError('builder_test_bundle', 'Candidate bundle failed its frozen prediction package checks') from exc
        files = checked['files']
        if set(files) != {'requirements.txt', 'poc_patch.py', 'run_benchmark.py'}:
            raise ResearchError('builder_test_bundle', 'Candidate bundle file set is not exact')
        manifest_files = manifest.get('files')
        if type(manifest_files) is not list or len(manifest_files) != 3:
            raise ResearchError('builder_test_manifest', 'Manifest must describe exactly three files')
        by_name = {}
        for row in manifest_files:
            if type(row) is not dict or row.get('path') in by_name:
                raise ResearchError('builder_test_manifest', 'Manifest file rows are invalid or duplicated')
            by_name[row['path']] = row
        if set(by_name) != set(files):
            raise ResearchError('builder_test_manifest', 'Manifest file names differ from the candidate archive')
        refs = {}
        for name, content in files.items():
            ref = by_name[name].get('artifact_ref')
            validate('Ref', ref)
            actual = self.store.read_blob(ref)
            if actual != content:
                raise ResearchError('builder_test_manifest', 'Manifest file bytes differ from the candidate archive')
            refs[name] = ref
        # requirements.txt must be a subset of the complete, frozen lock.
        candidate_pins = parse_requirements(files['requirements.txt'])
        if any(lock_pins.get(name) != version for name, version in candidate_pins.items()):
            raise ResearchError('builder_test_dependencies', 'Candidate dependencies are outside the frozen lock')
        expected_dependencies = [{'name': name, 'version': version} for name, version in candidate_pins.items()]
        if manifest.get('dependencies') != expected_dependencies:
            raise ResearchError('builder_test_dependencies', 'Manifest dependencies differ from candidate requirements')
        return manifest, bundle, files, refs, lock_pins

    def _mount(self, resource, ref, target):
        mount = self.adapter._resource(resource, ref, target)
        if not isinstance(mount, ReadonlyMount) or mount.target != target:
            raise ResearchError('builder_test_mount', 'Protected read-only resource mounting failed')
        return mount

    def _receipt_ok(self, raw, binding, job):
        if (type(raw) is not dict or raw.get('observed_runtime') is not True
                or raw.get('contract_ref') != dict(binding.contract_ref)
                or raw.get('invocation_id') != binding.invocation_id
                or raw.get('job_id') != job.job_id):
            raise ResearchError('builder_test_runtime', 'Kernel receipt is not joined to this exact test invocation')
        limits = raw.get('observed_limits', {})
        if raw.get('execution_mode') == 'm1_app_process':
            if not validate_process_evidence(self.store, raw, expected_uid=self.executor.uid,
                    expected_gid=self.executor.gid, contract_ref=dict(binding.contract_ref),
                    invocation_id=binding.invocation_id, job_id=job.job_id,
                    expected_runtime_ref=getattr(self.adapter, 'runtime_ref', None)):
                raise ResearchError('builder_test_process', 'M1 process evidence is not joined to its frozen runtime and invocation')
            return self.store.read_record(limits['process_observation_ref'])
        proof_ref = limits.get('isolation_probe_ref')
        proof = self.store.read_record(proof_ref) if isinstance(proof_ref, dict) else None
        try:
            memory_max, pids_max = int(limits['memory_max']), int(limits['pids_max'])
        except (KeyError, TypeError, ValueError):
            memory_max = pids_max = 0
        try:
            no_capabilities = int(proof.get('cap_effective', '-1'), 16) == 0 if isinstance(proof, dict) else False
        except (TypeError, ValueError):
            no_capabilities = False
        if (not isinstance(proof, dict) or proof.get('ready') is not True
                or proof.get('executor_uid') != self.executor.uid or proof.get('executor_gid') != self.executor.gid
                or not no_capabilities or proof.get('no_new_privileges') != '1'
                or limits.get('network') != 'none' or proof.get('network') != 'none'
                or not 0 < memory_max <= job.memory_mb * 1024 * 1024
                or not 0 < pids_max <= job.pids_max):
            raise ResearchError('builder_test_isolation', 'Observed kernel isolation proof is missing or outside test limits')
        return proof

    async def _run(self, contract, inputs, binding, *, sequence, ordinal, role, argv, mounts,
                   environment, subject_ref, validation_ref, hardware_ref):
        cwd = self.adapter.workspace_allocator(binding, sequence, 'builder_test')
        cwd = await _await(cwd)
        timeout = self.adapter._remaining(contract, binding, 30)
        memory = min(self.adapter.profile.memory_mb, contract['subnode_limits']['memory_mb'],
                     contract['bindings'][0]['limits']['memory_mb'])
        job = ExecutionJob(job_id='builder-test-' + uuid.uuid4().hex,
            invocation_id=binding.invocation_id, contract_ref=binding.contract_ref,
            run_id=contract['run_id'], node_id=contract['node_id'], attempt_id=contract['attempt_id'],
            sequence=sequence, role='builder_test', repeat_index=ordinal, seed=0,
            argv=tuple(argv), cwd=Path(cwd), timeout_s=min(timeout, 30), memory_mb=memory,
            pids_max=self.adapter.profile.pids_max, baseline_ref=subject_ref,
            validation_ref=validation_ref, environment_ref=environment.ref,
            subject_ref=subject_ref, hardware_ref=hardware_ref,
            readonly_mounts=tuple(mounts), environment=environment, output_limit_bytes=1024 * 1024)
        await _await(self.register_job(job, binding))
        raw = await self.executor.run(job)
        # Retain the complete drained receipt even when cancellation or a
        # containment failure prevents a development report from completing.
        self.store.append_record('builder_kernel_execution',{
            'run_id':contract['run_id'],'node_id':contract['node_id'],'attempt_id':contract['attempt_id'],
            'contract_ref':dict(binding.contract_ref),'invocation_id':binding.invocation_id,'receipt':raw})
        self._receipt_ok(raw, binding, job)
        if raw.get('termination_reason') == 'cancelled':
            # The shared kernel runner retains a drained cancellation receipt.
            # Preserve task cancellation instead of launching a smoke job.
            raise asyncio.CancelledError()
        return job, raw

    async def test(self, contract, inputs, *, binding, manifest_ref, tests_ref, ordinal) -> dict:
        # Prevent duplicate ordinals racing before the per-invocation monotonic
        # counter and single provision cache are updated.
        async with self._test_lock:
            return await self._test_locked(contract, inputs, binding=binding,
                manifest_ref=manifest_ref, tests_ref=tests_ref, ordinal=ordinal)

    async def _test_locked(self, contract, inputs, *, binding, manifest_ref, tests_ref, ordinal) -> dict:
        if type(ordinal) is not int or not 1 <= ordinal <= 3:
            raise ResearchError('builder_test_ordinal', 'Builder test ordinal must be an integer from one to three')
        authorized = await _await(self.authorize_binding(binding))
        if authorized != binding:
            raise ResearchError('builder_test_binding', 'Protected owner returned another invocation binding')
        if (not isinstance(binding, InvocationBinding) or binding.contract != contract
                or not binding.invocation_id):
            raise ResearchError('builder_test_binding', 'Exact protected invocation binding is required')
        previous = self._last_ordinal.get(binding.invocation_id, 0)
        if ordinal <= previous:
            raise ResearchError('builder_test_ordinal', 'Builder test ordinals must increase within an invocation')
        self._last_ordinal[binding.invocation_id] = ordinal
        declaration = self._declaration(contract)
        blueprint_ref, lock_ref = _input_ref(contract, 'blueprint'), _input_ref(contract, 'lock')
        if ('blueprint' not in inputs or 'lock' not in inputs
                or self.store.read_record(blueprint_ref) != inputs['blueprint']
                or self.store.read_record(lock_ref) != inputs['lock']):
            raise ResearchError('builder_test_input', 'Passed blueprint/lock differ from the exact invocation inputs')
        if (type(manifest_ref) is not dict or type(tests_ref) is not dict):
            raise ResearchError('builder_test_refs', 'Candidate and test suite refs must be immutable Refs')
        validate('Ref', manifest_ref); validate('Ref', tests_ref)
        manifest, bundle, files, candidate_refs, pins = self._candidate(manifest_ref, blueprint_ref, lock_ref, inputs)
        test_source = self.store.read_blob(tests_ref)
        if not 0 < len(test_source) <= TEST_LIMIT:
            raise ResearchError('builder_test_source', 'Producer test source must be nonempty and at most 64 KiB')
        try:
            test_text = test_source.decode('utf-8', errors='strict')
            compile(test_text, '<producer-selftest>', 'exec')
        except (UnicodeError, SyntaxError, ValueError) as exc:
            raise ResearchError('builder_test_source', 'Producer test source must be valid UTF-8 Python') from exc

        validation_ref = _input_ref(contract, 'validation_resource')
        validation = inputs['validation_resource']
        if self.store.read_record(validation_ref) != validation:
            raise ResearchError('builder_test_validation', 'Validation resource differs from the frozen public input')
        _, public_raw = _resource_file(self.store, validation, 'data.json')
        public = parse_public_dataset(public_raw)
        if any(row['path'] != 'data.json' for row in validation.get('files', [])):
            raise ResearchError('builder_test_validation', 'Only the closed public data.json may enter the test sandbox')

        if binding.invocation_id not in self._provisioned:
            provisioning = await self.adapter.provisioner(contract, inputs, pins, binding=binding,
                builder_manifest_ref=manifest_ref)
            validate('provisioning-receipt', provisioning)
            if provisioning.get('status') != 'succeeded':
                raise ResearchError('builder_test_provision', 'Candidate environment provisioning did not succeed')
            provisioning_ref = self.store.put_record('provisioning-receipt', provisioning,
                scope={'run_id': contract['run_id'], 'node_id': contract['node_id'], 'attempt_id': contract['attempt_id']})
            self._provisioned.add(binding.invocation_id)
            self._provision_cache[binding.invocation_id] = (copy.deepcopy(provisioning), provisioning_ref)
        provisioning, provisioning_ref = self._provision_cache[binding.invocation_id]
        prepared = self.adapter._prepared.get(binding.invocation_id)
        if not prepared or prepared[0].ref != lock_ref:
            raise ResearchError('builder_test_environment', 'Prepared environment does not match the exact frozen lock')
        environment = prepared[0]
        if self.adapter.environment_verifier is not None:
            self.adapter.environment_verifier(environment)
        candidate_resource = {'schema_version': '1.0.0', 'id': 'builder-test-candidate', 'kind': 'development candidate',
            'origin': 'exact Builder manifest archive', 'revision': manifest['archive_ref']['sha256'],
            'files': [{'path': name, 'artifact_ref': candidate_refs[name], 'media_type': 'text/plain',
                       'audience': 'authorized researcher'} for name in sorted(candidate_refs)],
            'access': 'read-only', 'license': 'not stated in candidate manifest',
            'availability': 'available', 'environment_ref': lock_ref}
        candidate_resource_ref = self.store.put_record('resource-snapshot', candidate_resource)
        candidate_mount = self._mount(candidate_resource, candidate_resource_ref, '/resources/poc')
        validation_mount = self._mount(validation, validation_ref, '/resources/validation')
        test_resource = {'schema_version': '1.0.0', 'id': 'builder-test-suite', 'kind': 'producer self-test',
            'origin': 'captured Builder test source', 'revision': tests_ref['sha256'],
            'files': [{'path': 'test_candidate.py', 'artifact_ref': tests_ref, 'media_type': 'text/x-python',
                       'audience': 'authorized researcher'}], 'access': 'read-only',
            'license': 'not stated', 'availability': 'available', 'environment_ref': lock_ref}
        tests_resource_ref = self.store.put_record('resource-snapshot', test_resource)
        tests_mount = self._mount(test_resource, tests_resource_ref, '/resources/selftest')
        hardware_ref = self.store.put_blob(json_bytes({'kind': 'builder-test-limits', 'profile': 'restricted'}),
                                           media_type='application/json')
        subject_ref = manifest['archive_ref']
        sequence = ordinal * 2 - 1
        runner = ('import runpy,sys,types,unittest\n'
                  'sys.path.insert(0,"/resources/poc")\n'
                  'namespace=runpy.run_path("/resources/selftest/test_candidate.py",run_name="builder_candidate_tests")\n'
                  'module=types.ModuleType("builder_candidate_tests")\n'
                  'module.__dict__.update(namespace)\n'
                  'suite=unittest.defaultTestLoader.loadTestsFromModule(module)\n'
                  'count=suite.countTestCases()\n'
                  'if count == 0:\n'
                  '    raise SystemExit("producer self-test suite is empty")\n'
                  'result=unittest.TextTestRunner().run(suite)\n'
                  'raise SystemExit((not result.wasSuccessful()) or result.testsRun == 0)\n')
        self_job, self_raw = await self._run(contract, inputs, binding, sequence=sequence, ordinal=ordinal,
            role='selftest', argv=('/environment/bin/python', '-I', '-c', runner),
            mounts=(candidate_mount, validation_mount, tests_mount), environment=environment,
            subject_ref=subject_ref, validation_ref=validation_ref, hardware_ref=hardware_ref)
        smoke_job, smoke_raw = await self._run(contract, inputs, binding, sequence=sequence + 1, ordinal=ordinal,
            role='smoke', argv=('/environment/bin/python', '/resources/poc/run_benchmark.py'),
            mounts=(candidate_mount, validation_mount), environment=environment,
            subject_ref=subject_ref, validation_ref=validation_ref, hardware_ref=hardware_ref)
        stdout = self.store.read_blob(smoke_raw['stdout_ref'])
        prediction_ok = True
        try:
            parse_predictions(stdout, public, max_stdout_bytes=OUTPUT_LIMIT)
        except ResearchError:
            prediction_ok = False
        passed = (self_raw.get('exit_code') == 0 and self_raw.get('termination_reason') == 'completed'
                  and smoke_raw.get('exit_code') == 0 and smoke_raw.get('termination_reason') == 'completed'
                  and prediction_ok)
        runs = [copy.deepcopy(self_raw), copy.deepcopy(smoke_raw)]
        report = {'schema': SCHEMA, 'contract_ref': dict(binding.contract_ref),
            'invocation_id': binding.invocation_id, 'execution_id': binding.execution_id,
            'manifest_ref': copy.deepcopy(manifest_ref), 'tests_ref': copy.deepcopy(tests_ref),
            'ordinal': ordinal, 'provisioning_ref': provisioning_ref, 'runs': runs,
            'status': 'passed' if passed else 'failed',
            'diagnostics': {'selftest_exit_code': self_raw.get('exit_code'),
                'selftest_termination': self_raw.get('termination_reason'),
                'smoke_exit_code': smoke_raw.get('exit_code'),
                'smoke_termination': smoke_raw.get('termination_reason'),
                'prediction_output_valid': prediction_ok,
                'selftest_stdout': self.store.read_blob(self_raw['stdout_ref'])[:2048].decode('utf-8', errors='replace'),
                'selftest_stderr': self.store.read_blob(self_raw['stderr_ref'])[:2048].decode('utf-8', errors='replace'),
                'smoke_stdout': stdout[:2048].decode('utf-8', errors='replace'),
                'smoke_stderr': self.store.read_blob(smoke_raw['stderr_ref'])[:2048].decode('utf-8', errors='replace')}}
        report.update({'run_id': contract['run_id'], 'node_id': contract['node_id'], 'attempt_id': contract['attempt_id'],
            'candidate_archive_ref': subject_ref, 'candidate_resource_ref': candidate_resource_ref,
            'tests_resource_ref': tests_resource_ref, 'candidate_file_refs': candidate_refs,
            'declaration_ref': contract['bindings'][0]['declaration_ref'],
            'registered_builder_version': declaration['identity']['version_label'],
            'test_jobs': [self_job.job_id, smoke_job.job_id], 'scoring_performed': False,
            'producer_test_source_sha256': hashlib.sha256(test_source).hexdigest()})
        evidence_ref = self.store.append_record('builder_test_execution', report)
        report_ref = evidence_ref
        return {**report, 'evidence_ref': evidence_ref, 'report_ref': report_ref}
