"""Fixed Root/UID12002 helper metadata owner, never ordinary CC authority.

Root reviews a pinned-image read-only metadata probe and seals its actual
observations and fixed helper envelope. UID12002 imports only those Root-owned
originals, retains the authentic fixture review, and compiles private draft
sessions. No candidate, fixture, model, signer, campaign or product run executes.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path('/var/lib/ai4r-rsi-codex')
PRIVATE = Path('/var/lib/ai4r-rsi-fixture-review')
SOURCE_CONFIG = Path('/run/ai4r-rsi/fixture-review-source.json')
SETUP_CONFIG = Path('/run/ai4r-rsi/session-setup.json')
CONTEXT_FILE = Path('/run/ai4r-rsi/session-context.json')
HOST_CONTEXT_FILE = ROOT / 'config/session-context.json'
HOST_APPROVAL_FILE = ROOT / 'config/session-probe-approval.json'
SOURCES = ('worker.py', 'process_policy.py', 'proposer.py', 'diagnosis.py', 'mutation.py',
           'statistics.py', 'assessment.py', 'oracle.py', 'custody.py', 'records.py',
           'targets/__init__.py', 'targets/ranking.py', 'targets/ranking_preparation.py')

# The only executable probe: installed source introspection and public kernel
# reads. It never loads fixture bytes, calls a helper, or imports a model owner.
PROBE = r'''import base64, hashlib, json, os, platform, re
from pathlib import Path
import jiuwenswarm.research_rsi as package
from jiuwenswarm.research_rsi.targets import registered_helper
from jiuwenswarm.research_rsi.worker import worker_program
from jiuwenswarm.research_rsi.process_policy import POLICY
root=Path(package.__file__).parent
names=%r
source={name:base64.b64encode((root/name).read_bytes()).decode() for name in names}
cpu={}
for line in Path('/proc/cpuinfo').read_text().splitlines():
    if ':' in line:
        key,value=line.split(':',1)
        if value.strip():cpu.setdefault(key.strip(),value.strip())
memory=next((int(line.split()[1]) for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemTotal:')),None)
model=cpu.get('model name') or cpu.get('Hardware') or cpu.get('Processor') or platform.processor()
if not model or memory is None:raise ValueError('Actual hardware facts unavailable')
helper=registered_helper('ranking-v1')
print(json.dumps({'schema':'ai4r-rsi-helper-metadata-probe:1',
 'hardware':{'cpu_model':model,'host_cpu_count':os.cpu_count(),'host_memory_mb':memory//1024,
 'kernel_release':platform.release(),'architecture':platform.machine(),'os':platform.system(),
 'scope':'read-only metadata container; not benchmark or qualified worker observation'},
 'helper':{'target_kind':helper.target_kind,'entrypoint':helper.entrypoint,'input_name':helper.input_name},
 'parent_source':base64.b64encode((root.parent/'research/capsules/ranking.py').read_bytes()).decode(),
 'worker_program':base64.b64encode(worker_program('ranking-v1',POLICY)).decode(),
 'sources':source,'candidate_executed':False,'fixture_executed':False,'normal_cc_invoked':False},sort_keys=True))
''' % (SOURCES,)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def pin(raw):
    digest = hashlib.sha256(raw).hexdigest()
    return {'id': digest + '.json', 'sha256': digest}


def need(value):
    if not value:
        raise ValueError('EXACT_HELPER_METADATA_ORIGINALS_REQUIRED')


def exact_ref(value):
    need(isinstance(value, dict) and set(value) == {'id', 'sha256'} and isinstance(value['id'], str) and value['id']
         and isinstance(value['sha256'], str) and re.fullmatch('[a-f0-9]{64}', value['sha256']))
    return value


def protected(path):
    path = Path(path)
    need(path.is_absolute() and not any(item.is_symlink() for item in (path, *path.parents)))
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        meta = os.fstat(descriptor)
        need(stat.S_ISREG(meta.st_mode) and meta.st_nlink == 1
             and (meta.st_uid, meta.st_gid, stat.S_IMODE(meta.st_mode)) == (0, 12002, 0o440)
             and 0 < meta.st_size <= 8 * 1024 * 1024)
        return json.loads(os.read(descriptor, 8 * 1024 * 1024 + 1))
    finally:
        os.close(descriptor)


def host_module():
    spec = importlib.util.spec_from_file_location('_session_native_host', Path(__file__).with_name('rsi_host.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def host_paths(generation=None):
    need(generation is None or isinstance(generation, str) and re.fullmatch('[a-z0-9][a-z0-9_.-]{0,63}', generation))
    suffix = '.' + generation if generation is not None else ''
    return {'approval': ROOT / ('config/session-probe-approval' + suffix + '.json'),
        'context': ROOT / ('config/session-context' + suffix + '.json'),
        'setup': ROOT / ('config/session-setup' + suffix + '.json'),
        'records': ROOT / ('helper-observations' + suffix)}


def probe_plan(image, generation=None):
    need(isinstance(image, str) and re.fullmatch(r'sha256:[a-f0-9]{64}', image))
    host = host_module()
    paths = host_paths(generation)
    return {'status': 'ROOT_REVIEW_REQUIRED', 'worker_image': image, 'program_ref': pin(PROBE.encode()),
        'generation': generation, 'approval_file': str(paths['approval']), 'context_file': str(paths['context']),
        'setup_file': str(paths['setup']),
        'records_root': str(paths['records']),
        'command': ['/usr/bin/docker', '--host', host.SOCKET, 'run', '--rm', '--pull', 'never',
            '--read-only', '--network', 'none', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
            '--user', '12003:12003', '--memory', '128m', '--memory-swap', '128m', '--pids-limit', '32', '--cpus', '2',
            '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=8m', '--entrypoint', '/opt/venv/bin/python',
            image, '-I', '-B', '-c', PROBE],
        'limitations': ['Read-only metadata probe only', 'No candidate/fixture/product invocation',
            'No performance or qualification claim', 'The image must be the final frozen worker image']}


def root_capture(image, generation=None):
    """Requires a distinct Root-owned exact review before running the probe."""
    need(sys.platform == 'linux' and os.geteuid() == 0)
    host = host_module(); actual_host = host.status(); plan = probe_plan(image, generation)
    paths = host_paths(generation)
    approval = protected(paths['approval'])
    need(set(approval) == {'schema', 'worker_image', 'program_ref', 'parent_ref', 'parent_declaration_ref',
                          'worker_bounds', 'reviewed_by', 'reviewed_at'}
         and approval['schema'] == 'ai4r-rsi-helper-probe-approval:1'
         and approval['worker_image'] == image and approval['program_ref'] == plan['program_ref']
         and isinstance(approval['reviewed_by'], str) and approval['reviewed_by'])
    exact_ref(approval['parent_ref']); exact_ref(approval['parent_declaration_ref'])
    bounds = approval['worker_bounds']
    need(isinstance(bounds, dict) and set(bounds) == {'memory_mb', 'pids_max', 'timeout_s'}
         and type(bounds['memory_mb']) is int and 0 < bounds['memory_mb'] <= 4096
         and type(bounds['pids_max']) is int and 0 < bounds['pids_max'] <= 256
         and type(bounds['timeout_s']) in (int, float) and 0 < bounds['timeout_s'] <= 300)
    need(not paths['context'].exists())
    inspection = json.loads(host.run(['/usr/bin/docker', '--host', host.SOCKET, 'image', 'inspect', image]))
    need(isinstance(inspection, list) and len(inspection) == 1 and inspection[0]['Id'] == image)
    began = datetime.now(timezone.utc).isoformat()
    result = subprocess.run(plan['command'], env=host.ENV, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30)
    ended = datetime.now(timezone.utc).isoformat()
    need(result.returncode == 0 and 0 < len(result.stdout) <= 4 * 1024 * 1024)
    observed = json.loads(result.stdout)
    need(observed.get('schema') == 'ai4r-rsi-helper-metadata-probe:1'
         and observed['candidate_executed'] is False and observed['fixture_executed'] is False
         and observed['normal_cc_invoked'] is False and set(observed['sources']) == set(SOURCES))
    parent_source = base64.b64decode(observed['parent_source'], validate=True)
    need(hashlib.sha256(parent_source).hexdigest() == approval['parent_ref']['sha256'])
    from jiuwenswarm.research_rsi.records import RecordStore
    store_root = paths['records']
    store_root.mkdir(mode=0o700, exist_ok=True)
    meta = store_root.stat(); need((meta.st_uid, stat.S_IMODE(meta.st_mode)) == (0, 0o700))
    store = RecordStore(store_root)
    originals = {}
    def keep(raw):
        ref = store.put_bytes(raw); originals[ref['id']] = {'ref': ref, 'bytes': base64.b64encode(raw).decode()}; return ref
    def record(value): return keep(encoded(value))
    try:
        source_refs = {name: keep(base64.b64decode(raw, validate=True)) for name, raw in observed['sources'].items()}
        program_ref = keep(PROBE.encode()); worker_program_ref = keep(base64.b64decode(observed['worker_program'], validate=True))
        parent_source_ref = keep(parent_source)
        observation_ref = keep(result.stdout)
        owner_source_ref = keep(Path(__file__).read_bytes())
        image_ref = record({key: inspection[0][key] for key in ('Id', 'Os', 'Architecture')})
        origin_ref = record({'schema': 'ai4r-rsi-root-helper-metadata-origin:1', 'approval': approval,
            'generation': generation,
            'probe_started_at': began, 'probe_ended_at': ended,
            'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            'host_limits': {key: actual_host[key] for key in ('memory_max', 'pids_max', 'cpu_max')},
            'program_ref': program_ref, 'owner_source_ref': owner_source_ref,
            'image_inspection_ref': image_ref, 'observation_ref': observation_ref})
        hardware_ref = record({'schema': 'ai4r-rsi-observed-helper-hardware:1', **observed['hardware'],
            'origin_ref': origin_ref, 'observation_ref': observation_ref,
            'qualification': 'NOT_ESTABLISHED', 'same_sandbox_hardware_observation': False})
        environment_ref = record({'image_id': image, 'image_digest': image,
            'platform': inspection[0]['Os'] + '/' + inspection[0]['Architecture'], 'origin_ref': origin_ref})
        interface_ref = record({'schema': 'ai4r-rsi-frozen-helper-interface:1', **observed['helper'],
            'parent_ref': approval['parent_ref'], 'parent_declaration_ref': approval['parent_declaration_ref'],
            'parent_source_ref': parent_source_ref,
            'registration_source_ref': source_refs['targets/__init__.py'],
            'reference_source_ref': source_refs['targets/ranking.py'], 'worker_program_ref': worker_program_ref,
            'source_refs': source_refs, 'execution_authorized': False})
        execution_contract_ref = record({'schema': 'ai4r-rsi-root-helper-execution-envelope:1',
            'purpose': 'pure_helper_trials_after_current_qualification', 'origin_ref': origin_ref,
            'parent_ref': approval['parent_ref'], 'parent_declaration_ref': approval['parent_declaration_ref'],
            'interface_ref': interface_ref, 'worker_program_ref': worker_program_ref, 'worker_image': image,
            'helper': observed['helper'], 'resource_bounds': bounds,
            'process_policy': 'single_process_seccomp_v1', 'execution_authorized': False,
            'product_subnode_contract': False, 'qualification_required_before_effects': True})
        improver_ref = record({'schema': 'ai4r-rsi-installed-improver-sources:1',
            'source_refs': {name: source_refs[name] for name in ('proposer.py', 'diagnosis.py', 'mutation.py')}})
        scoring_ref = record({'schema': 'ai4r-rsi-installed-scoring-sources:1',
            'source_refs': {name: source_refs[name] for name in ('statistics.py', 'assessment.py', 'oracle.py', 'custody.py', 'targets/ranking.py')}})
        context = {'schema': 'ai4r-rsi-root-helper-context:1', 'worker_image': image,
            'parent_ref': approval['parent_ref'], 'parent_declaration_ref': approval['parent_declaration_ref'],
            'interface_ref': interface_ref, 'execution_contract_ref': execution_contract_ref,
            'hardware_ref': hardware_ref, 'environment_ref': environment_ref,
            'improver_ref': improver_ref, 'scoring_adapter_ref': scoring_ref,
            'hash_profile_ref': source_refs['records.py'], 'source_refs': source_refs,
            'origin_ref': origin_ref, 'worker_bounds': bounds, 'originals': list(originals.values())}
        context_ref = record(context)
        raw = encoded(context)
        descriptor = os.open(paths['context'], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o440)
        with os.fdopen(descriptor, 'wb') as stream:
            os.fchown(stream.fileno(), 0, 12002); os.fchmod(stream.fileno(), 0o440)
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        return {'status': 'ACTUAL_HELPER_CONTEXT_CAPTURED_NOT_QUALIFIED', 'context_ref': context_ref,
            **{name: context[name] for name in ('hardware_ref', 'environment_ref', 'interface_ref', 'execution_contract_ref')}}
    finally:
        store.close()


def private_store():
    from jiuwenswarm.research_rsi.preparation_runtime import _private_root
    from jiuwenswarm.research_rsi.records import RecordStore
    from jiuwenswarm.research_rsi.targets.ranking_preparation import require_custodian_store
    store = RecordStore(_private_root(PRIVATE)); require_custodian_store(store); return store


def reviewed_preparation(store):
    """Resolve the actual generation and human capture; never reconstruct it."""
    from jiuwenswarm.research_rsi.session_policy import validate_private
    from jiuwenswarm.research_rsi.targets.ranking_preparation import _read_preparation
    row = store.db.execute("SELECT ref FROM jobs WHERE id='fixture-review-generation' AND state='prepared'").fetchone()
    need(row is not None); result = store.get(json.loads(row[0]))
    review = store.db.execute('SELECT ref FROM jobs WHERE id=? AND state=?',
        ('fixture-review:' + result['packet_ref']['sha256'], 'reviewed')).fetchone()
    need(review is not None); review_ref = json.loads(review[0]); document = store.get(review_ref)
    validate_private('urn:ai4r:private:rsi-ranking-review:1', document)
    need(document['preparation_ref'] == result['preparation_ref'])
    preparation = _read_preparation(store, result['preparation_ref'])
    return result, review_ref, preparation


def source_pins():
    """Useful now, before final image/probe; no target or session is invented."""
    store = private_store()
    try:
        result, review_ref, preparation = reviewed_preparation(store)
        import jiuwenswarm.research_rsi as package
        root = Path(package.__file__).parent
        need(store.read(preparation['generator_ref']) == (root / 'targets/ranking_preparation.py').read_bytes())
        source_refs = {name: store.put_bytes((root / name).read_bytes()) for name in SOURCES}
        capture = {'schema': 'ai4r-rsi-private-source-pins:1', 'preparation_ref': result['preparation_ref'],
            'review_ref': review_ref, 'parent_ref': preparation['parent_ref'],
            'parent_declaration_ref': preparation['parent_declaration_ref'], 'source_refs': source_refs,
            'execution_performed': False}
        capture_ref = store.put(capture)
        return {'status': 'ACTUAL_SOURCE_PINS_CAPTURED', 'source_capture_ref': capture_ref,
            'preparation_ref': result['preparation_ref'], 'review_ref': review_ref,
            'missing_facts': ['final_frozen_worker_image_and_Root_observation_context',
                'new_Core_configuration_and_guard_originals', 'Root_session_bounds_and_time_identity']}
    finally:
        store.close()


def helper_test_materials(store):
    """Freeze real disclosed helper checks, without running any candidate."""
    from jiuwenswarm.research_rsi.targets.ranking_preparation import development_export
    from jiuwenswarm.research_rsi.targets import registered_helper
    import jiuwenswarm.research_rsi as package
    result, review_ref, preparation = reviewed_preparation(store)
    root = Path(package.__file__).parent
    need(store.read(preparation['generator_ref']) == (root / 'targets/ranking_preparation.py').read_bytes())
    disclosed = development_export(store, result['preparation_ref'], approved_review_ref=review_ref)
    helper = registered_helper('ranking-v1')
    originals = {}
    def keep(raw):
        ref = store.put_bytes(raw); originals[ref['id']] = ref; return ref
    def record(value): return keep(encoded(value))
    sources = {name: keep((root / name).read_bytes()) for name in
               ('targets/__init__.py', 'targets/ranking.py', 'worker.py', 'fixed_resources.py')}
    parent_ref = preparation['parent_ref']; keep(store.read(parent_ref))
    export_ref = record(disclosed); tests = []; bindings = []
    need(disclosed['parent_ref'] == parent_ref and bool(disclosed['cases']))
    for row in disclosed['cases']:
        helper.validate_visible_inputs(row['inputs'])
        input_ref = record(row['inputs']); expected_ref = record(row['expected'])
        definition = {'schema': 'ai4r-rsi-frozen-helper-test:1', 'target_kind': helper.target_kind,
            'entrypoint': helper.entrypoint, 'input_name': helper.input_name,
            'parent_ref': parent_ref, 'development_export_ref': export_ref,
            'case_id': row['id'], 'input_ref': input_ref, 'expected_ref': expected_ref,
            'source_refs': sources,
            'assertion': {'termination_reason': 'completed', 'exit_code': 0,
                          'stdout_json': 'equals_registered_reference_and_frozen_expected'},
            'execution_performed': False}
        test_ref = record(definition); tests.append(test_ref)
        bindings.append({'input_ref': input_ref, 'test_ref': test_ref})
    visible_ref = record({'context': disclosed, 'required_test_refs': tests, 'mandatory_fixtures': bindings})
    provenance_ref = store.put({'schema': 'ai4r-rsi-private-helper-test-capture:1',
        'preparation_ref': result['preparation_ref'], 'review_ref': review_ref,
        'required_test_refs': tests, 'mandatory_fixtures': bindings,
        'public_original_refs': list(originals.values()), 'execution_performed': False})
    return {'capture_ref': provenance_ref, 'required_test_refs': tests,
            'mandatory_fixtures': bindings, 'visible_context_ref': visible_ref,
            'public_original_refs': list(originals.values())}


def capture_helper_tests():
    store = private_store()
    try:
        result = helper_test_materials(store)
        return {'status': 'FROZEN_HELPER_TESTS_CAPTURED_NOT_EXECUTED', **result}
    finally:
        store.close()


def compile_draft():
    """Private draft + distinct case/calibration sessions using actual owners."""
    from jiuwenswarm.research_rsi.targets.ranking_preparation import draft_target
    from jiuwenswarm.research_rsi.session_preparation import compile_helper_session, session_public_materials
    from jiuwenswarm.research_rsi.session_policy import _contracts
    from jiuwenswarm.research_rsi.worker import PublicBytes
    from jiuwenswarm.research_rsi.process_policy import POLICY
    config = protected(SETUP_CONFIG); context = protected(CONTEXT_FILE)
    need(set(config) == {'schema', 'worker_image', 'configuration_ref', 'public_roots', 'public_original_refs',
        'required_test_refs', 'parent_body_refs', 'session_prefix', 'started_by', 'frozen_at',
        'target_limits', 'limits', 'invocation_wall_s', 'evidence_wall_s', 'batch_iterations',
        'declared_noise_ceiling', 'custodian_public_pin'}
         and config['schema'] == 'ai4r-rsi-session-setup:1' and config['worker_image'] == context['worker_image'])
    need(context['schema'] == 'ai4r-rsi-root-helper-context:1' and set(context['source_refs']) == set(SOURCES)
         and isinstance(context['originals'], list) and 0 < len(context['originals']) <= 64)
    need(config['limits']['max_attempts'] == 1 and config['limits']['max_no_progress'] == 1
         and config['limits']['wall_s'] <= 3600 and config['target_limits']['model_calls'] == 2)
    need(re.fullmatch('[a-z][a-z0-9_.:-]{0,49}', config['session_prefix'])
         and isinstance(config['public_original_refs'], list) and len(config['public_original_refs']) <= 256
         and isinstance(config['public_roots'], list) and 0 < len(config['public_roots']) <= 4)
    store = private_store()
    try:
        result, review_ref, preparation = reviewed_preparation(store)
        helper_tests = helper_test_materials(store)
        need(config['required_test_refs'] == helper_tests['required_test_refs'])
        need(all(context[name] == preparation[name] for name in ('parent_ref', 'parent_declaration_ref')))
        originals = []
        for row in context['originals']:
            need(isinstance(row, dict) and set(row) == {'ref', 'bytes'})
            raw = base64.b64decode(row['bytes'], validate=True); need(pin(raw) == row['ref']); originals.append((row['ref'], raw))
        public = PublicBytes(config['public_roots'])
        need(all(not (path == PRIVATE or path.is_relative_to(PRIVATE) or PRIVATE.is_relative_to(path)) for path in public.roots))
        for ref in config['public_original_refs']:
            originals.append((ref, public.read(ref)))
        for ref, raw in originals: store.put_ref(ref, raw)
        import jiuwenswarm.research_rsi as package
        source_root = Path(package.__file__).parent
        for name, ref in context['source_refs'].items():
            need(name in SOURCES and store.read(ref) == (source_root / name).read_bytes())
        need(store.read(preparation['generator_ref']) == store.read(context['source_refs']['targets/ranking_preparation.py']))
        envelope = store.get(context['execution_contract_ref'])
        need(envelope['schema'] == 'ai4r-rsi-root-helper-execution-envelope:1'
             and envelope['product_subnode_contract'] is False and envelope['execution_authorized'] is False
             and envelope['qualification_required_before_effects'] is True
             and envelope['worker_image'] == context['worker_image']
             and envelope['interface_ref'] == context['interface_ref']
             and envelope['resource_bounds'] == context['worker_bounds'])
        interface = store.get(context['interface_ref'])
        need(interface['schema'] == 'ai4r-rsi-frozen-helper-interface:1'
             and interface['execution_authorized'] is False
             and store.read(interface['parent_source_ref']) == store.read(preparation['parent_ref']))
        parent = store.get(preparation['parent_declaration_ref']); _contracts().validate('capsule-declaration', parent)
        need(set(config['parent_body_refs']) == {row['path'] for row in parent['identity']['body']})
        for row in parent['identity']['body']:
            ref = config['parent_body_refs'][row['path']]; need(ref['sha256'] == row['sha256']); store.read(ref)
        need(config['required_test_refs'])
        for ref in config['required_test_refs']: store.read(ref)
        from jiuwenswarm.research.operator_config import OperatorConfiguration
        OperatorConfiguration.from_mapping(store.get(config['configuration_ref']))
        protected_refs = [ref for ref in config['parent_body_refs'].values() if ref != preparation['parent_ref']]
        protected_refs += [context[name] for name in ('interface_ref', 'improver_ref', 'scoring_adapter_ref', 'hash_profile_ref')]
        protected_refs += [config['configuration_ref'], *config['required_test_refs']]
        protected_refs = list({encoded(ref): ref for ref in protected_refs}.values())
        template = {'schema_version': '1.0.0', 'id': config['session_prefix'] + '.draft-target',
            'frozen_contract_ref': context['interface_ref'], 'required_test_refs': config['required_test_refs'],
            'protected_refs': protected_refs,
            'scoring': {'primary': 'passed_test_count', 'secondary': 'paired_time_at_equal_counts',
                        'warmup_batches': 5, 'paired_rounds': 7, 'min_relative_gain': .1, 'noise_multiplier': 3,
                        'batch_iterations': config['batch_iterations'],
                        # Existing source calibration treats this as a declared
                        # ceiling and rejects observed noise above it. It is
                        # policy, never a fabricated measured observation.
                        'calibrated_relative_noise': config['declared_noise_ceiling']},
            'session_query_limit': 30, 'lifetime_query_limit': 90,
            'limits': config['target_limits'], 'configuration_ref': config['configuration_ref'],
            'improver_ref': context['improver_ref'], 'scoring_adapter_ref': context['scoring_adapter_ref']}
        target, manifest = draft_target(store, result['preparation_ref'], template, review_ref=review_ref, validate=_contracts().validate)
        target_ref = store.put(target); manifest['target_ref'] = target_ref; manifest_ref = store.put(manifest)
        bounds = context['worker_bounds']
        worker = {'target_kind': 'ranking-v1', 'contract_ref': context['execution_contract_ref'],
            'environment_ref': context['environment_ref'], 'hardware_ref': context['hardware_ref'],
            **bounds, 'process_policy': POLICY}
        compiled = {}; materials = {}; kinds = {}
        approved_public = (config['public_original_refs'] + helper_tests['public_original_refs']
                           + [row['ref'] for row in context['originals']])
        for label in [*('RSIV-' + str(number) for number in range(1, 14)), 'calibration']:
            sid = config['session_prefix'] + ':' + label.lower()
            session = compile_helper_session(store, target_ref=target_ref, fixture_manifest_ref=manifest_ref,
                session_id=sid, started_by=config['started_by'], limits=config['limits'], worker=worker,
                hash_profile_ref=context['hash_profile_ref'], invocation_wall_s=config['invocation_wall_s'],
                evidence_wall_s=config['evidence_wall_s'], frozen_at=config['frozen_at'])
            compiled[label] = session
            kinds[session['session_ref']['id']] = 'rsi-session'; kinds[session['worker_profile_ref']['id']] = 'rsi-worker-profile'
            projection = session_public_materials(store, session_ref=session['session_ref'],
                worker_profile_ref=session['worker_profile_ref'], parent_body_refs=config['parent_body_refs'],
                approved_public_refs=approved_public, visible_context_ref=helper_tests['visible_context_ref'])
            need(not projection['required_original_refs'])
            for row in projection['materials']: materials[row['ref']['id']] = row
        kinds[target_ref['id']] = 'rsi-target-profile'; kinds[preparation['parent_declaration_ref']['id']] = 'capsule-declaration'
        for ref in helper_tests['public_original_refs']:
            materials[ref['id']] = {'ref': ref, 'bytes': store.read(ref)}
        # Worker profile context refs are nominated explicitly; no recursive
        # fixture, calibration, review, or oracle walk is permitted.
        for key in ('execution_contract_ref', 'environment_ref', 'hardware_ref'):
            ref = context[key]; materials[ref['id']] = {'ref': ref, 'bytes': store.read(ref)}
        rows = [{'ref': row['ref'], 'kind': kinds.get(row['ref']['id']), 'bytes': base64.b64encode(row['bytes']).decode()}
                for row in materials.values()]
        materials_ref = store.put({'schema': 'ai4r-rsi-private-security-materials:1', 'materials': rows})
        runtime = {'schema': 'ai4r-rsi-security-runtime-config:1', 'campaign_root': '/var/lib/ai4r-rsi-validation-campaign',
            **config['custodian_public_pin'], 'environment_ref': context['environment_ref'],
            'case_bindings': {case: {'session_ref': row['session_ref'], 'worker_profile_ref': row['worker_profile_ref']}
                              for case, row in compiled.items() if case != 'calibration'},
            'originals': [{'ref': row['ref'], 'kind': row['kind']} for row in rows]}
        packet_ref = store.put({'schema': 'ai4r-rsi-security-setup-input:1', 'runtime': runtime,
            'additional_profile_refs': [compiled['calibration']['worker_profile_ref']]})
        compilation_ref = store.put({'schema': 'ai4r-rsi-private-draft-compilation:1', 'preparation_ref': result['preparation_ref'],
            'review_ref': review_ref, 'target_ref': target_ref, 'fixture_manifest_ref': manifest_ref,
            'helper_test_capture_ref': helper_tests['capture_ref'], 'visible_context_ref': helper_tests['visible_context_ref'],
            'sessions': compiled, 'materials_ref': materials_ref, 'security_setup_input_ref': packet_ref})
        return {'status': 'PRIVATE_DRAFT_COMPILED_NOT_STARTED', 'compilation_ref': compilation_ref,
            'target_ref': target_ref, 'materials_ref': materials_ref, 'security_setup_input_ref': packet_ref}
    finally:
        store.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='operation', required=True)
    for name in ('probe-plan', 'capture-probe'):
        item = commands.add_parser(name); item.add_argument('--worker-image', required=True)
        item.add_argument('--generation')
    commands.add_parser('capture-source-pins'); commands.add_parser('capture-helper-tests'); commands.add_parser('compile-draft')
    args = parser.parse_args(argv)
    try:
        if args.operation == 'probe-plan': result = probe_plan(args.worker_image, args.generation)
        elif args.operation == 'capture-probe': result = root_capture(args.worker_image, args.generation)
        elif args.operation == 'capture-source-pins': result = source_pins()
        elif args.operation == 'capture-helper-tests': result = capture_helper_tests()
        else: result = compile_draft()
    except Exception:
        print(json.dumps({'status': 'BLOCKED', 'reason': 'ACTUAL_PRIVATE_OWNER_OR_REQUIRED_ORIGINALS_UNAVAILABLE'})); return 2
    print(json.dumps(result, sort_keys=True)); return 0


if __name__ == '__main__':
    raise SystemExit(main())
