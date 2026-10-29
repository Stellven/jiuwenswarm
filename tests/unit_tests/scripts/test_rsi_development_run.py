"""Development orchestration controls; synthetic models, no operational evidence."""
import asyncio
import copy
from datetime import datetime, timedelta, timezone
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

PATH = Path(__file__).resolve().parents[3]/'deploy/m1/rsi_development_run.py'
spec = importlib.util.spec_from_file_location('development_admin_under_test', PATH)
d = importlib.util.module_from_spec(spec); spec.loader.exec_module(d)


def ref(label):
    return {'id': label, 'sha256': d.digest(label.encode())}


def authorization():
    value = {key: '/isolated/'+key for key in d.FIELDS}
    value.update(schema=d.AUTH_SCHEMA, id='synthetic-development',
        expires_at=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),
        limits={'max_attempts': 1, 'max_no_progress': 1, 'wall_s': 3600, 'per_call_s': 120,
                'session_query_limit': 2, 'lifetime_query_limit': 2}, target_kind='ranking-v1',
        work_capsule_refs={'intent': ref('intent'), 'verifier': ref('verifier')},
        worker={'contract_ref': ref('worker'), 'environment_ref': ref('env'), 'hardware_ref': ref('hw'),
                'memory_mb': 256, 'pids_max': 16, 'timeout_s': 5},
        principal={'account_id': 'synthetic', 'workspace_ids': ['unit'], 'operations': ['status'], 'audiences': []},
        exact_binding_refs={**{key: ref(key) for key in ('configuration_ref', 'model_selection_profile_ref', 'deployment_ref')},
                            'workspace_id': 'unit', 'protected_options': {'development_builtin_catalog': False}},
        run_contexts={'diagnosis-run': {}, 'proposal-run': {}}, forbidden_roots=['/live'],
        public_original_refs=[ref('approved-public-document')],
        observed_symptom='Synthetic visible control', authorized_component='helper.py', host_id='synthetic-host',host_binding_ref=ref('original-host-binding'))
    value.update(seed_receipt={'path': '/root/seed.json', 'sha256': 'a'*64},
                 launch_guard_receipt={'path': '/root/guard.json', 'sha256': 'b'*64})
    for key in ('diagnosis_contract_ref', 'proposal_contract_ref', 'native_scope_ref', 'parent_declaration_ref',
                'target_profile_ref', 'visible_context_ref', 'preparation_ref'): value[key] = ref(key)
    return value


@pytest.mark.parametrize('fault', ['extra', 'three-calls', 'two-attempts', 'bool-limit', 'same-contract', 'verifier-only', 'tools-profile', 'expired', 'worker-memory'])
def test_closed_authorization_never_widens_development_scope(fault):
    value = authorization(); assert d.validate_authorization(value) == value
    if fault == 'extra': value['security_qualification_ref'] = ref('fake')
    elif fault == 'three-calls': value['limits']['session_query_limit'] = 3
    elif fault == 'two-attempts': value['limits']['max_attempts'] = 2
    elif fault == 'bool-limit': value['limits']['max_attempts'] = True
    elif fault == 'same-contract': value['proposal_contract_ref'] = value['diagnosis_contract_ref']
    elif fault == 'verifier-only': del value['work_capsule_refs']['intent']
    elif fault == 'tools-profile': value['exact_binding_refs']['protected_options']['development_builtin_catalog'] = True
    elif fault == 'expired': value['expires_at'] = '2020-01-01T00:00:00Z'
    elif fault == 'worker-memory': value['worker']['memory_mb'] = 257
    with pytest.raises(ValueError): d.validate_authorization(value)


def test_immutable_claim_and_bounded_json_pipe(tmp_path, monkeypatch):
    if not hasattr(d.os, 'O_NOFOLLOW'): monkeypatch.setattr(d.os, 'O_NOFOLLOW', 0, raising=False)
    claim = tmp_path/'claim.json'; d.exclusive(claim, {'original': True})
    with pytest.raises(FileExistsError): d.exclusive(claim, {'replacement': True})
    assert claim.read_bytes() == d.encoded({'original': True})
    stream = io.BytesIO(); d.write_frame(stream, {'role': 'parent'}); stream.seek(0)
    assert d.read_frame(stream) == {'role': 'parent'} and d.read_frame(stream) is None
    with pytest.raises(ValueError): d.read_frame(io.BytesIO(b'{"role":1,"role":2}\n'))
    with pytest.raises(ValueError): d.read_frame(io.BytesIO(b'x'*(d.MAX_BYTES+2)))


@pytest.mark.parametrize('idle',[True,False])
def test_root_status_runs_readonly_canonical_client_as_controller_without_exporting_session(monkeypatch,idle):
    monkeypatch.setattr(d.os,'geteuid',lambda:0,raising=False)
    monkeypatch.setattr(d.os,'name','posix')
    fact={'binding_sha256':'a'*64,'policy_sha256':'b'*64,'status_sha256':'c'*64,'active':not idle,'unresolved':False}
    calls=[]
    class Process:
        returncode=0
        async def communicate(self):return d.encoded(fact),b''
    async def create(*args,**kwargs):calls.append((args,kwargs));return Process()
    monkeypatch.setattr(d.asyncio,'create_subprocess_exec',create)
    if idle:assert asyncio.run(d.relay_idle_fact('/fixed/own/accounts'))==fact
    else:
        with pytest.raises(ValueError):asyncio.run(d.relay_idle_fact('/fixed/own/accounts'))
    args,kwargs=calls[0]
    assert args[1:4]==('-I','-B','-c') and args[-1]=='/fixed/own/accounts'
    assert 'owner.relay_status()' in args[4] and '.invoke(' not in args[4] and '.login(' not in args[4]
    assert 'capability' not in d.encoded(fact).decode() and callable(kwargs['preexec_fn'])


@pytest.mark.parametrize('fault', [None, 'private', 'parent', 'cases', 'qualification'])
def test_public_preparation_cannot_import_hidden_fixture_scope_or_claim_qualification(fault):
    value = authorization(); tests = [ref('visible-' + str(i)) for i in range(12)]
    prep = {'schema': 'ai4r-rsi-development-public-preparation:1',
        **{key: value[key] for key in ('parent_declaration_ref', 'target_profile_ref', 'visible_context_ref')},
        'required_test_refs': tests, 'development_export_ref': ref('public-export'),
        'security_campaigns': 'DEFERRED', 'qualification': False}
    if fault == 'private': prep['partitions'] = {'hidden': ref('private')}
    elif fault == 'parent': prep['parent_declaration_ref'] = ref('foreign')
    elif fault == 'cases': prep['required_test_refs'] = tests[:-1]
    elif fault == 'qualification': prep['qualification'] = True
    if fault:
        with pytest.raises(ValueError): d.validate_public_preparation(prep, value, tests)
    else: assert d.validate_public_preparation(prep, value, tests) == prep


def test_maximum_run_id_uses_distinct_canonical_bounded_job_ids():
    value = authorization(); value['id'] = 'a'*80
    d.validate_authorization(value)
    ids = {d.development_job_id(value['id'], role, index) for role in ('parent', 'candidate') for index in range(12)}
    assert len(ids) == 24 and all(len(ident) <= 64 for ident in ids)
    assert d.development_job_id(value['id'], 'parent', 0) == d.development_job_id(value['id'], 'parent', 0)
    for reserved in ('.', '..'):
        value['id'] = reserved
        with pytest.raises(ValueError, match='RUN_ID'): d.validate_authorization(value)


def test_persistent_evaluator_plan_ignores_only_namespace_mount_id(tmp_path, monkeypatch):
    root = tmp_path/'evaluator'; root.mkdir()
    original = Path.read_text
    state = {'id': '100', 'device': '8:32', 'root': '/retained/evaluator', 'mode': 'rw', 'fs': 'ext4'}
    def read(path, *args, **kwargs):
        if path.as_posix() == '/proc/self/mountinfo':
            escaped = str(root).replace('\\', '\\134').replace(' ', '\\040')
            return f"{state['id']} 1 {state['device']} {state['root']} {escaped} {state['mode']} - {state['fs']} /dev/sda rw\n"
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', read)
    expected = d.persistent_evaluator_mount(root)
    state['id'] = '900'
    assert d.persistent_evaluator_mount(root) == expected
    for key, changed in (('device', '8:99'), ('root', '/different/source')):
        previous = state[key]; state[key] = changed
        assert d.persistent_evaluator_mount(root) != expected
        state[key] = previous
    for key, changed in (('mode', 'ro'), ('fs', 'tmpfs')):
        previous = state[key]; state[key] = changed
        with pytest.raises(ValueError): d.persistent_evaluator_mount(root)
        state[key] = previous
    root.rename(tmp_path/'old-evaluator'); root.mkdir()
    assert d.persistent_evaluator_mount(root) != expected


@pytest.mark.parametrize('fault', [None, 'root', 'account', 'lease-path', 'extra'])
def test_original_bootstrap_scope_compatibility_is_exact_not_new_scope_authority(fault):
    value = authorization(); value.update(core_root='/isolated/bootstrap/core', native_lease_root='/isolated/bootstrap/native-leases')
    scope = {'schema': 'ai4r-rsi-bootstrap-native-scope:1', 'root': '/isolated/bootstrap', 'account_root': value['account_root']}
    if fault == 'root': scope['root'] = '/another-bootstrap'
    elif fault == 'account': scope['account_root'] = '/another-account'
    elif fault == 'lease-path': value['native_lease_root'] = '/new-empty-lease-root'
    elif fault == 'extra': scope['complete'] = True
    if fault:
        with pytest.raises(ValueError): d.validate_native_scope(value, scope, allow_bootstrap=True)
    else:
        d.validate_native_scope(value, scope, allow_bootstrap=True)
        with pytest.raises(ValueError): d.validate_native_scope(value, scope)


@pytest.mark.parametrize('available', [23, 24])
def test_group_budget_accounts_for_complete_schedule_and_dying_groups(tmp_path, available):
    group = tmp_path/'groups'; group.mkdir()
    (group/'cgroup.max.descendants').write_text(str(available+5))
    (group/'cgroup.stat').write_text('nr_descendants 3\nnr_dying_descendants 2\n')
    before = {p.name: p.read_bytes() for p in group.iterdir()}
    if available == 23:
        with pytest.raises(ValueError, match='GROUP_BUDGET'): d.cgroup_capacity(group)
    else: assert d.cgroup_capacity(group)[0]['dying'] == 2
    assert before == {p.name: p.read_bytes() for p in group.iterdir()}


@pytest.mark.parametrize('parts', [[b'{"ok":true}\n'], [b'{"a":1}\n{"b":2}\n'], [b'{"a":1}', b'']])
def test_inherited_pipe_has_finite_reads_and_rejects_extra_or_partial_frames(monkeypatch, parts):
    chunks = iter(parts)
    monkeypatch.setattr(d.select, 'select', lambda *args: ([123], [], []))
    monkeypatch.setattr(d.os, 'read', lambda *args: next(chunks))
    stream = SimpleNamespace(fileno=lambda: 123)
    if parts == [b'{"ok":true}\n']:
        assert d.read_frame_deadline(stream, d.time.monotonic()+1) == {'ok': True}
    else:
        with pytest.raises(ValueError): d.read_frame_deadline(stream, d.time.monotonic()+1)
    with pytest.raises(ValueError, match='DEADLINE'): d.read_frame_deadline(stream, 0)


@pytest.mark.parametrize('history', [None, 'empty-table', 'complete', 'uncertain'])
def test_fresh_scope_has_truthful_empty_state_and_never_imports_fake_completion(tmp_path, monkeypatch, history):
    import sqlite3
    root = tmp_path/'leases'; root.mkdir(); value = authorization(); value['native_lease_root'] = str(root)
    if history is not None:
        connection = sqlite3.connect(root/'index.sqlite')
        connection.execute('CREATE TABLE native_effect_leases(scope TEXT,state TEXT,ref TEXT)')
        if history != 'empty-table': connection.execute('INSERT INTO native_effect_leases VALUES(?,?,?)', ('scope', history, '{}'))
        connection.commit(); connection.close()
    before = {p.name: p.read_bytes() for p in root.iterdir()}
    monkeypatch.setattr(d, 'protected', lambda path, **kwargs: Path(path))
    if history in {'complete', 'uncertain'}:
        with pytest.raises(ValueError, match='NO_EFFECT_HISTORY'): d.empty_native_scope(value)
    else: assert d.empty_native_scope(value)['state'] == 'EMPTY'
    assert before == {p.name: p.read_bytes() for p in root.iterdir()}


@pytest.mark.parametrize('fault', [None, 'destination', 'old-uncertain', 'not-frozen', 'relay-active', 'seed-mismatch'])
def test_root_receipts_bind_fresh_scope_and_frozen_original_guards(tmp_path, monkeypatch, fault):
    value = authorization()
    destination = {key: value[key] for key in ('isolation_root', 'core_root', 'input_root', 'account_root',
                    'record_root', 'native_lease_root', 'work_root', 'parent_directory', 'native_scope_ref')}
    seed = {'id': value['id'], 'destination': destination, 'zero_dispatch': True}
    guard = {'id': value['id'], 'seed_receipt_sha256': value['seed_receipt']['sha256'],
             'bootstrap_operations_frozen': True, 'relay_idle': True, 'source_guards_sha256': 'd'*64}
    if fault == 'destination': seed['destination']['core_root'] = '/another-core'
    elif fault == 'old-uncertain': seed['zero_dispatch'] = False
    elif fault == 'not-frozen': guard['bootstrap_operations_frozen'] = False
    elif fault == 'relay-active': guard['relay_idle'] = False
    elif fault == 'seed-mismatch': guard['seed_receipt_sha256'] = 'e'*64
    helper = SimpleNamespace(read_completed_seed=lambda ref: seed, read_launch_guard=lambda ref, seed_ref: guard)
    monkeypatch.setattr(d, 'seed_module', lambda: helper)
    monkeypatch.setattr(d.inspect, 'getsourcefile', lambda _: str(PATH))
    if fault:
        with pytest.raises(ValueError): d.seed_facts(value)
    else: assert d.seed_facts(value)['source_guards_sha256'] == guard['source_guards_sha256']


class LeaseDouble:
    def __init__(self): self.events = []
    def start(self, run, contract): self.events.append(('start', contract)); return ref('lease')
    def complete(self, start, proof): self.events.append(('complete', proof))
    def uncertain(self, start, proof): self.events.append(('uncertain', proof))


@pytest.mark.parametrize('known', [False, True])
def test_normal_proposal_entrypoint_once_only_and_unknown_lease_stops(monkeypatch, known):
    from jiuwenswarm.research_rsi import native_lease
    entries = []
    class CoreDouble:
        def iter_records(self, **kwargs): return list(entries)
    class ResourcesDouble:
        store = CoreDouble()
        async def propose_once(self, contract, prompt):
            entries.append({'kind': 'model-call-start', 'ref': ref('start'), 'record': {'contract_ref': contract}})
            entries.append({'kind': 'model-call', 'ref': ref('call'), 'record': {'outcome': 'completed', 'identity': {'effective': 'synthetic'}}})
            return 'synthetic'
    monkeypatch.setattr(native_lease, 'native_completion_proof', lambda store, starts: (known, {'synthetic': True}))
    lease = LeaseDouble(); model = d.DevelopmentModel(ResourcesDouble(), lease, ref('work'), 'run')
    if known: assert asyncio.run(model('approved visible text')) == 'synthetic'
    else:
        with pytest.raises(ValueError, match='CONTAINMENT_UNCERTAIN'): asyncio.run(model('approved visible text'))
    assert [e[0] for e in lease.events] == ['start', 'complete' if known else 'uncertain']
    assert model.last_model_calls == 1 and model.last_generating_model == 'synthetic'
    with pytest.raises(ValueError, match='ALREADY_USED'): asyncio.run(model('no replay'))
    assert len(lease.events) == 2


class MemoryRecords:
    def __init__(self): self.data = {}; self.reads = []
    def put_bytes(self, raw):
        pin = {'id': d.digest(raw)+'.json', 'sha256': d.digest(raw)}; self.data[pin['id']] = raw; return pin
    def put(self, value): return self.put_bytes(d.encoded(value))
    def read(self, pin): self.reads.append(pin); return self.data[pin['id']]
    def get(self, pin): return json.loads(self.read(pin))


@pytest.mark.parametrize('fault', [None, 'parent-fails', 'eleven-tests', 'bad-diagnosis', 'bad-proposal', 'wrong-path', 'unchanged'])
def test_existing_parsers_assessment_and_two_call_schedule_without_hidden_data(tmp_path, monkeypatch, fault):
    from jiuwenswarm.research_rsi import mutation
    store = MemoryRecords(); value = authorization()
    source = b'def rank_opportunities(rows):\n    return {}\n'; body = store.put_bytes(source)
    parent = {'identity': {'name': 'synthetic.helper', 'version_label': 'unit', 'carrier': 'python',
                          'body': [{'path': 'helper.py', 'sha256': body['sha256']}]}}
    value['parent_declaration_ref'] = store.put(parent)
    target = {'parent_ref': body, 'mutable_paths': ['helper.py'], 'improver_ref': store.put({'synthetic': 'improver'}),
              'required_test_refs': [store.put({'public-test': i}) for i in range(12)]}
    value['target_profile_ref'] = store.put(target)
    visible = {'context': {'public': 'only permitted development evidence'},
               'required_test_refs': target['required_test_refs'],
               'mandatory_fixtures': [{'test_ref': p, 'input_ref': store.put({'public-input': i})} for i, p in enumerate(target['required_test_refs'])]}
    if fault == 'eleven-tests': visible['mandatory_fixtures'].pop()
    value['visible_context_ref'] = store.put(visible)
    hidden = store.put({'private_sentinel': 'must never be read or sent to models'})
    parent_root = tmp_path/'parent'; parent_root.mkdir(); (parent_root/'helper.py').write_bytes(source)
    work = tmp_path/'work'; work.mkdir(); value.update(parent_directory=str(parent_root), work_root=str(work))
    prompts = []; evaluated = []
    class ModelDouble:
        def __init__(self, resources, lease, contract, run):
            self.role = 'diagnosis' if contract == value['diagnosis_contract_ref'] else 'proposal'
            self.last_evidence = []; self.last_model_calls = None; self.last_generating_model = None; self.last_unavailable_reasons = []
        async def __call__(self, prompt):
            prompts.append((self.role, prompt)); self.last_model_calls = 1; self.last_generating_model = 'synthetic-model'
            self.last_evidence = [store.put({'synthetic-call': self.role})]
            if self.role == 'diagnosis':
                if fault == 'bad-diagnosis': return 'invalid diagnosis'
                content = json.loads(prompt)
                return json.dumps({'schema': 'ai4r-rsi-diagnosis:1', 'observed_symptom': 'Synthetic control',
                    'supporting_visible_evidence': [content['visible_evidence'][0]['ref']], 'suspected_mechanism': 'Synthetic',
                    'alternative_causes': ['Synthetic alternative'], 'authorized_component': value['authorized_component'],
                    'proposed_change_direction': 'Synthetic proposal', 'expected_effect': 'Unmeasured hypothesis',
                    'visible_falsification_checks': ['Run public cases'], 'uncertainties': ['No hidden evaluation']})
            if fault == 'bad-proposal': return 'not JSON'
            return json.dumps({'path': 'outside.py' if fault == 'wrong-path' else 'helper.py',
                               'body': source.decode() + ('' if fault == 'unchanged' else '# synthetic child\n'), 'rationale': 'Synthetic'})
    async def evaluate(candidate, tests, role):
        evaluated.append(role)
        return {'passed': fault != 'parent-fails', 'evidence_refs': [store.put({'synthetic-receipt': role, 'i': i}) for i in range(12)],
                'visible_selection_time_s': 0.25, 'executions': 12, 'passed_count': 0 if fault == 'parent-fails' else 12}
    def declaration(original, *, body_hashes, version_label, **kwargs):
        result = copy.deepcopy(original); result['identity']['version_label'] = version_label
        result['identity']['body'][0]['sha256'] = body_hashes['helper.py']; return result
    monkeypatch.setattr(d, 'DevelopmentModel', ModelDouble)
    monkeypatch.setattr(mutation, 'child_declaration', declaration)
    async def ready(): pass  # explicit controlled transport, not runtime evidence
    runtime = SimpleNamespace(store=store, resources=None, lease=None, evaluate=evaluate, before_model=ready)
    if fault:
        with pytest.raises(ValueError): asyncio.run(d.execute(value, runtime))
    else:
        result = asyncio.run(d.execute(value, runtime))
        assert result['security'] == 'UNQUALIFIED' and result['security_campaigns'] == 'DEFERRED'
        assert result['model_calls'] == 2 and result['candidate']['mandatory_passed'] is True
        assert result['hidden_evaluation'] == result['final_evaluation'] == 'NOT_RUN'
        assert all(result[k] is None for k in ('qualification_ref', 'package_ref', 'admission_ref', 'activation_ref'))
        assert store.read(result['candidate']['child_ref']) != source
        assert (parent_root/'helper.py').read_bytes() == source
        assert evaluated == ['parent', 'candidate']
        result['evaluator_exit_code'] = 0
        assert d.validate_result(result) == result
        for field, replacement in (('security', 'QUALIFIED'), ('qualification_ref', ref('fake-proof')),
                                   ('model_calls', 3), ('hidden_evaluation', 'PASS')):
            tampered = copy.deepcopy(result); tampered[field] = replacement
            with pytest.raises(ValueError): d.validate_result(tampered)
    expected = 0 if fault in {'parent-fails', 'eleven-tests'} else 1 if fault == 'bad-diagnosis' else 2
    assert len(prompts) == expected
    assert hidden not in store.reads and all('private_sentinel' not in prompt for _, prompt in prompts)


@pytest.mark.parametrize('fault', [None, 'authority', 'admission', 'checking-pair', 'missing-real-calibration'])
def test_real_contract_factory_library_runner_and_governed_wire_closure(tmp_path, fault):
    """Controlled admission/transport setup; canonical validators are NOT mocked."""
    async def scenario():
        from jiuwenswarm.research.state import SQLiteRunStore
        from jiuwenswarm.research.runner import Registry, CapsuleRunner
        from jiuwenswarm.research.checks import CheckRegistry
        from jiuwenswarm.research.compiler import register_compiler_capsules
        from jiuwenswarm.research.contracts import Principal, ResearchError
        from jiuwenswarm.research.intake import qualify_intake
        from tests.unit_tests.research.controlled_assets import ControlledLibraryService
        from jiuwenswarm.research.bridge import GovernedBridge
        from jiuwenswarm.research.isolated_resources import IsolatedResources, owned_model_evidence
        from jiuwenswarm.server.runtime.codex_subscription.service import SubscriptionService
        from tests.unit_tests.runtime.test_codex_governed_trace import WireTransport
        core = SQLiteRunStore(tmp_path/'core')
        registry, checks = Registry(), CheckRegistry()
        library = ControlledLibraryService(core)
        actor = Principal('synthetic-operator', frozenset({'unit'}), frozenset({'verifier_assets', 'library_admit', 'library_standing', 'ingest'}))
        installed = await register_compiler_capsules(registry, checks, library, core, actor, activate=True)
        opaque = core.put_blob(b'explicit synthetic metadata')
        policy = core.put_record('plan-policy', {'schema_version': '1.0.0', 'id': 'development-unit-policy', 'max_nodes': 4,
            'allowed_effect_classes': ['pure', 'read'], 'allow_network': False, 'required_stages': [],
            'aggregate_limits': {'time_s': 240, 'model_calls': 2, 'memory_mb': 256}, 'max_attempts_per_node': 1})
        final = core.put_record('node-finalization-profile', {'schema_version': '2.0.0', 'id': 'unit-final',
            'mandatory_deterministic': ['internal_acceptance', 'external_output', 'aggregate_limits'],
            'semantic_assessment_reuse': 'accepted_requirements', 'additional_model_calls': 0})
        selection = core.put_record('model-selection-profile', {'schema_version': '1.0.0', 'id': 'unit-selection',
            'policy_mode': 'fixed_baseline', 'approved_model_ids': ['codex-cli-default'], 'extra_requirements': {},
            'selection_allowance': {'enabled': False, 'deployment_ref': None, 'model_calls': 0, 'time_s': 0, 'output_tokens': 0, 'disclosure_scope': []},
            'alternate_model_id': None, 'policy_ref': policy})
        exact = {'configuration_ref': opaque, 'model_selection_profile_ref': selection, 'deployment_ref': opaque,
                 'workspace_id': 'unit', 'protected_options': {'finalization_profile_ref': final, 'compiler_template_ref': opaque}}
        settings = {'cc': {'plan_policy_ref': policy, 'router': {'enabled': False, 'deadline_s': 30, 'profile_ref': None}}}
        operator = SimpleNamespace(snapshot=lambda: settings)
        intake = qualify_intake(core, actor, 'Synthetic visible helper performance question.', [], workspace_id='unit',
                                profile_ref=opaque, workspace_ref=opaque, input_directory_ref=opaque)
        service = SubscriptionService(tmp_path/'native', transport=WireTransport())
        service.set_governed_trace_writer(core.append_record, core.put_blob)
        bridge = GovernedBridge(persist=core.append_record, authorize=lambda _: (_ for _ in ()).throw(ValueError()),
                                subscription_service=service, read_evidence=core.read_blob)
        runner = CapsuleRunner(core, registry, checks, model=bridge, check_assets=library.check_assets)
        bridge.authorize = runner.authorize_model_context; bridge.revalidate = runner.authorize_model_dispatch
        captured = d.prepare_work_contexts(core=core, library=library, runner=runner, operator=operator, exact=exact,
            intake_ref=intake, action_id='synthetic-once', account_id=actor.account_id,
            work_capsule_refs={stage: installed[stage]['declaration_ref'] for stage in ('intent', 'verifier')})
        original = captured['proposal_contract_ref']; contract = core.read_record(original)
        assert contract['bindings'][0]['role'] == 'work'
        assert core.read_record(contract['bindings'][0]['declaration_ref'])['identity']['name'] == 'intent.compiler'
        assert len(captured['run_contexts']) == 2 and not list(core.iter_records(kinds=('model-call',)))
        resources = IsolatedResources(core, operator, SimpleNamespace(runner=runner), bridge, None, actor, exact)
        if fault:
            modified = copy.deepcopy(contract)
            if fault == 'authority': modified['bindings'][0]['effective_authority']['tools'] = ['shell']
            elif fault == 'admission': modified['bindings'][0]['admission_ref'] = opaque
            elif fault == 'checking-pair': modified['checking_profile_ref'] = opaque
            if fault == 'missing-real-calibration':
                from jiuwenswarm.research.checks.assets import CheckAssetAdmissions
                # Drop the deliberate test authority. Actual production guard
                # must reject this fixture because it has no measured admission.
                runner.check_assets = CheckAssetAdmissions(core)
                changed = original
            else: changed = core.put_record('subnode-execution-contract', modified, record_id='synthetic-forged-work')
            with pytest.raises((ResearchError, ValueError, KeyError)):
                await resources.propose_once(changed, 'synthetic approved visible context')
            assert not list(core.iter_records(kinds=('model-call-start',)))
        else:
            assert await resources.propose_once(original, 'synthetic approved visible context') == 'Hello'
            call = next(core.iter_records(kinds=('model-call',)))
            closure = owned_model_evidence(core, call['ref'])
            assert {'native-governed-trace', 'native-governed-trace-event', 'native-governed-packet'} <= {r['kind'] for r in closure}
            assert all(r['bytes'] for r in closure)
            assert core.get_attempt(*(contract[k] for k in ('run_id', 'node_id', 'subnode_id', 'attempt_id')))['state'] == 'observed'
            with pytest.raises(ResearchError): await resources.propose_once(original, 'never replay')
            assert len(list(core.iter_records(kinds=('model-call',)))) == 1
            assert not list(core.iter_records(kinds=('gate-decision', 'acceptance-commit')))
        await service.transport.close(); core.close()
    asyncio.run(scenario())


@pytest.mark.parametrize('bad_candidate_stdout', [False, True])
def test_finite_evaluator_preserves_opaque_public_inputs_and_collects_actual_24_receipts(tmp_path, monkeypatch, bad_candidate_stdout):
    """Executor transport double only; no process or confinement claim is made."""
    import base64
    from jiuwenswarm.research import executor as module
    from jiuwenswarm.research_rsi.targets import registered_helper
    value = authorization(); value['id'] = 'x'*80
    group_root = tmp_path/'groups'; group_root.mkdir(); value['cgroup_root'] = str(group_root)
    root = tmp_path/'root'; root.mkdir()
    source = b'def rank_opportunities(rows): return {}\n'
    parent_ref = {'id': 'opaque-original-parent', 'sha256': d.digest(source)}
    child = source+b'# byte-distinct synthetic child\n'; child_ref = {'id': d.digest(child)+'.json', 'sha256': d.digest(child)}
    rows = []
    for index in range(12):
        inputs = {'scores': [{'idea_id': str(index), 'novelty': 1, 'feasibility': 2, 'compute_alignment': 3, 'eligible': True}]}
        raw = json.dumps(inputs, indent=2).encode()  # deliberately noncanonical bytes
        rows.append({'test_ref': ref('test-'+str(index)), 'input_ref': {'id': 'public-input-'+str(index), 'sha256': d.digest(raw)},
                     'input_raw': raw, 'inputs': inputs})
    requests = io.BytesIO(); responses = io.BytesIO()
    for role, body, body_ref in (('parent', source, parent_ref), ('candidate', child, child_ref)):
        d.write_frame(requests, {'role': role, 'candidate_ref': body_ref, 'body_base64': base64.b64encode(body).decode()})
    requests.seek(0); jobs = []
    class ExecutorDouble:
        def __init__(self, **kwargs):
            self.options = kwargs
            assert kwargs['executor_uid'] == kwargs['executor_gid'] == 12003
        def prerequisites(self): return []
        async def run(self, job):
            jobs.append(job); assert self.options['authorize_job'](job) == job
            assert job.argv == ('/usr/local/bin/python3', '-I', '/resources/worker.py')
            for mount in job.readonly_mounts: self.options['verify_mount'](mount)
            raw = next(m.source.read_bytes() for m in job.readonly_mounts if m.target == '/resources/input.json')
            assert raw == rows[job.repeat_index]['input_raw']
            group = group_root/job.job_id; group.mkdir()
            (group/'cgroup.events').write_text('populated 0\n'); (group/'cgroup.procs').write_text('')
            result = registered_helper('ranking-v1').reference(json.loads(raw))
            output = b'not JSON' if bad_candidate_stdout and len(jobs)>12 else d.encoded(result)
            capture = self.options['capture']
            return {'termination_reason': 'completed', 'exit_code': 0, 'observed_runtime': True,
                'stdout_ref': capture(output), 'stderr_ref': capture(b''), 'wall_time_s': 0.125,
                'observed_limits': {'isolation_probe_ref': capture(b'{"synthetic_probe":true}')},
                'baseline_ref': job.baseline_ref, 'subject_ref': job.subject_ref, 'validation_ref': job.validation_ref}
    monkeypatch.setattr(module, 'RestrictedExecutor', ExecutorDouble)
    monkeypatch.setattr(d, 'read_frame_deadline', lambda stream, deadline: d.read_frame(stream))
    monkeypatch.setattr(d.os, 'chown', lambda *args, **kwargs: None, raising=False)
    asyncio.run(d.evaluator(value, {'parent': source, 'parent_ref': parent_ref, 'tests': rows}, requests, responses, root))
    assert len(jobs) == 24 and len({job.job_id for job in jobs}) == 24 and all(len(j.job_id)<=64 for j in jobs)
    responses.seek(0); assert d.read_frame(responses)['maximum_executions'] == 24
    parent_result, child_result = d.read_frame(responses), d.read_frame(responses)
    assert parent_result['passed_count'] == 12
    assert child_result['passed_count'] == (0 if bad_candidate_stdout else 12)
    assert parent_result['visible_selection_time_s'] == child_result['visible_selection_time_s'] == 1.5
    for packet in parent_result['evidence']+child_result['evidence']:
        raw = base64.b64decode(packet['bytes_base64']); proof = json.loads(raw)
        assert (root/'captures'/(packet['ref']['sha256']+'.json')).read_bytes() == raw
        assert proof['input_ref'] in [row['input_ref'] for row in rows] and proof['group_empty'] is True
        assert proof['candidate_ref'] in (parent_ref, child_ref)
        for capture in packet['captures']:
            assert d.digest(base64.b64decode(capture['bytes_base64'])) == capture['ref']['sha256']
