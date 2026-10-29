"""Operational bootstrap authority/budget joins; never a model or admission."""
import base64
import asyncio
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace

import pytest

SOURCE = Path(__file__).parents[3] / 'deploy/m1/rsi_operational_bootstrap.py'
spec = importlib.util.spec_from_file_location('operational_bootstrap_test', SOURCE)
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


def pins():
    return {key: {'id': key, 'sha256': str(index) * 64} for index, key in enumerate(
        ('configuration_ref', 'model_selection_profile_ref', 'deployment_ref'), 1)}


def grant(value):
    return {'schema': 'ai4r-rsi-bootstrap-authorization:1', 'account_id': value['account_id'], **pins(),
            'operations': ['verifier_assets'], 'stage': 'screening', 'action_id': 'catalog-screening-once',
            'max_model_calls': 6, 'max_time_s': 600,
            'expires_at': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()}


@pytest.mark.parametrize('change', [{'account_id': 'foreign'}, {'stage': 'builder'},
    {'operations': ['verifier_assets', 'child_activate']}, {'max_model_calls': 13}, {'max_time_s': 0},
    {'expires_at': '2000-01-01T00:00:00Z'}, {'configuration_ref': {'id': 'foreign', 'sha256': 'f' * 64}},
    {'extra': 'not-closed'}])
def test_root_grant_cannot_expand_identity_stage_budget_or_operation(monkeypatch, change):
    value = {'account_id': 'actual-new-local-account', **pins()}
    approved = grant(value)
    approved.update(change)
    monkeypatch.setattr(bootstrap, 'protected_json', lambda *args, **kwargs: approved)
    with pytest.raises(ValueError):
        bootstrap.approval(value, 'screening', 'verifier_assets')


def test_matching_finite_root_grant_and_real_primary_identity(monkeypatch):
    value = {'account_id': 'actual-new-local-account', **pins()}
    approved = grant(value)
    monkeypatch.setattr(bootstrap, 'protected_json', lambda *args, **kwargs: approved)
    result = bootstrap.approval(value, 'screening', 'verifier_assets')
    account = SimpleNamespace(primary=lambda: {'account_id': value['account_id']})
    actor = bootstrap.actor_for(account, value, result)
    actor.require('verifier_assets', 'local')
    with pytest.raises(Exception):
        actor.require('library_standing')
    with pytest.raises(ValueError):
        bootstrap.actor_for(SimpleNamespace(primary=lambda: {'account_id': 'foreign'}), value, result)


def test_plan_only_reads_capture_and_reports_separate_budgets(monkeypatch):
    value = {'account_id': 'real-primary', 'configuration_ref': pins()['configuration_ref'],
        'stages': [{'stage': 'screening', 'model_calls_ceiling': 7, 'request_time_s_ceiling': 1800},
                   {'stage': 'verifier', 'model_calls_ceiling': 6, 'request_time_s_ceiling': 1800}]}
    monkeypatch.setattr(bootstrap, 'load', lambda: value)
    result = bootstrap.plan()
    assert result['total_model_calls_ceiling'] == 13
    assert result['total_request_time_s_ceiling'] == 3600
    assert result['status'] == 'CAPTURED_NOT_ADMITTED'
    assert 'exact_live_doctor' in result['remaining_session_gates']


def test_final_configuration_only_adds_actual_custodian_public_pin():
    pin = {'id': 'source', 'sha256': 'a' * 64}
    source = {'schema_version': '1.0.0', 'cc': {'plan_source': 'static', 'plan_policy_ref': pin,
        'static_template_ref': pin, 'evaluation_profile_ref': None,
        'router': {'enabled': False, 'deadline_s': 30, 'profile_ref': None}},
        'rsi': {'custodian_key_id': None, 'custodian_public_key': None},
        'codex': {'route_id': 'codex-cli-default'}, 'role_aliases': {}}
    approved = dict(source, rsi={'custodian_key_id': 'isolated-test-public',
                                 'custodian_public_key': base64.urlsafe_b64encode(bytes(32)).decode().rstrip('=')})
    result = bootstrap.final_operator(source, approved)
    assert result['rsi'] == approved['rsi']
    changed = dict(approved, codex={'route_id': 'foreign'})
    with pytest.raises(ValueError):
        bootstrap.final_operator(source, changed)


def test_cli_never_implicitly_selects_effectful_stage(monkeypatch):
    monkeypatch.setattr(bootstrap, 'calibrate', lambda *args: pytest.fail('No calibration without exact stage'))
    with pytest.raises(SystemExit) as error:
        bootstrap.main(['calibrate'])
    assert error.value.code == 2


@pytest.mark.parametrize('name', ['../escape', '/tmp/foreign', 'with/slash', 'UPPER', ''])
def test_generation_is_bounded_namespace_not_operator_path(name):
    with pytest.raises(ValueError):
        bootstrap.select_generation(name)


def test_root_generation_map_is_complete_and_pins_prior_history(monkeypatch):
    monkeypatch.setattr(bootstrap, 'ACTIVE_GENERATION', 'scope-v2')
    value = {'schema': 'ai4r-rsi-bootstrap-generation:1', 'generation': 'scope-v2',
             'profile_generations': {'screening': 'scope-v2', 'verifier': 'scope-v2'}, 'prior_namespaces': ['legacy']}
    monkeypatch.setattr(bootstrap, 'protected_json', lambda *args, **kwargs: value)
    assert bootstrap.profile_generations(['screening', 'verifier']) == (value['profile_generations'], ['legacy'])
    with pytest.raises(ValueError):
        bootstrap.profile_generations(['screening'])
    value['prior_namespaces'] = ['scope-v2']
    with pytest.raises(ValueError):
        bootstrap.profile_generations(['screening', 'verifier'])


@pytest.mark.parametrize('requested', ['gpt-6-luna', 'gpt-6.1-sol', 'Qwen3.8-27B-NVFP4'])
def test_protected_generation_model_is_finite_without_endpoint_or_factory_selection(monkeypatch, requested):
    monkeypatch.setattr(bootstrap, 'ACTIVE_GENERATION', 'fresh-model')
    value = {'schema': 'ai4r-rsi-bootstrap-generation:2', 'generation': 'fresh-model',
             'requested_model': requested, 'profile_generations': {'screening': 'fresh-model'},
             'prior_namespaces': ['legacy']}
    monkeypatch.setattr(bootstrap, 'protected_json', lambda *args, **kwargs: value)
    assert bootstrap.selected_model() == requested
    assert bootstrap.profile_generations(['screening']) == ({'screening': 'fresh-model'}, ['legacy'])
    for change in ({'requested_model': 'arbitrary'}, {'endpoint': 'http://foreign'},
                   {'factory': 'foreign.module'}, {'schema': 'ai4r-rsi-bootstrap-generation:1'}):
        candidate = dict(value, **change)
        monkeypatch.setattr(bootstrap, 'protected_json', lambda *args, **kwargs: candidate)
        with pytest.raises(Exception):
            bootstrap.selected_model()
    del value['requested_model']
    monkeypatch.setattr(bootstrap, 'protected_json', lambda *args, **kwargs: value)
    with pytest.raises(ValueError):
        bootstrap.selected_model()


def test_host_generation_explicitly_pins_same_model_backend_and_medium(monkeypatch):
    monkeypatch.setattr(bootstrap, 'ACTIVE_GENERATION', 'host-fresh')
    value = {'schema': 'ai4r-rsi-bootstrap-generation:3', 'generation': 'host-fresh',
        'requested_model': 'gpt-6.1-sol', 'model_backend': 'host-codex-app-server', 'reasoning_effort': 'medium',
        'profile_generations': {'screening': 'host-fresh'}, 'prior_namespaces': ['legacy']}
    monkeypatch.setattr(bootstrap, 'protected_json', lambda *args, **kwargs: value)
    assert bootstrap.selected_model() == 'gpt-6.1-sol'
    assert bootstrap.selected_backend() == 'host-codex-app-server'
    for change in ({'schema': 'ai4r-rsi-bootstrap-generation:2'}, {'model_backend': 'codex'},
                   {'reasoning_effort': 'high'}, {'requested_model': 'gpt-6-luna'}, {'endpoint': 'http://foreign'}):
        candidate = dict(value, **change)
        monkeypatch.setattr(bootstrap, 'protected_json', lambda *args, **kwargs: candidate)
        with pytest.raises(ValueError): bootstrap.selected_backend()


@pytest.mark.skipif(sys.platform != 'linux', reason='Linux private lease custody')
@pytest.mark.parametrize('state', ['active', 'uncertain', 'complete'])
def test_fresh_generation_cannot_bypass_old_native_lease(tmp_path, monkeypatch, state):
    from jiuwenswarm.research_rsi.native_lease import ProfileInUse
    base = tmp_path / 'operational-bootstrap'
    lease = base / 'native-leases'
    lease.mkdir(parents=True)
    (base / 'bootstrap.json').write_text('{}')
    database = lease / 'index.sqlite'
    db = sqlite3.connect(database)
    db.execute('CREATE TABLE native_effect_leases(scope TEXT,state TEXT,ref TEXT)')
    db.execute('INSERT INTO native_effect_leases VALUES(?,?,?)', ('old-profile', state, '{}'))
    db.commit();db.close()
    database.chmod(0o600)
    monkeypatch.setattr(bootstrap, 'BASE_ROOT', base)
    monkeypatch.setattr(bootstrap, 'ROOT', tmp_path / 'operational-bootstrap.scope-v2')
    if state == 'complete':
        bootstrap.prior_namespaces_available({'prior_namespaces': ['legacy']})
    else:
        with pytest.raises(ProfileInUse):
            bootstrap.prior_namespaces_available({'prior_namespaces': ['legacy']})


@pytest.mark.skipif(sys.platform != 'linux', reason='Native Linux custody and installed source-byte semantics')
@pytest.mark.parametrize('generation,model', [(None, 'gpt-6-luna'), ('scope-v2', 'gpt-6-luna'),
                                           ('spark-qwen-v1', 'Qwen3.8-27B-NVFP4')])
def test_actual_metadata_capture_rebinds_final_key_without_model_or_admission(tmp_path, monkeypatch, generation, model):
    from jiuwenswarm.research.state import SQLiteRunStore
    from jiuwenswarm.server.runtime.codex_subscription.service import SubscriptionService
    root = tmp_path / 'fresh-operational-bootstrap'
    public_key = base64.urlsafe_b64encode(bytes(32)).decode().rstrip('=')
    approved_rsi = {'custodian_key_id': 'controlled-public-test', 'custodian_public_key': public_key}
    original = bootstrap.final_operator
    monkeypatch.setattr(bootstrap, 'ROOT', root)
    monkeypatch.setattr(bootstrap, 'ACTIVE_GENERATION', generation)
    monkeypatch.setattr(bootstrap, 'custody', lambda: None)
    stages = ('intent', 'requirements', 'planner', 'verifier', 'search', 'screening',
              'hypothesis', 'builder', 'benchmark', 'evaluation', 'delivery')
    settings = {'schema': 'ai4r-rsi-bootstrap-generation:1', 'generation': generation,
                'profile_generations': {stage: generation for stage in stages}, 'prior_namespaces': ['legacy']}
    if model != 'gpt-6-luna':
        settings.update(schema='ai4r-rsi-bootstrap-generation:2', requested_model=model)
    monkeypatch.setattr(bootstrap, 'protected_json', lambda path, **kwargs: settings if path == bootstrap.GENERATION_CONFIG else {})
    monkeypatch.setattr(bootstrap, 'final_operator', lambda source, approved: original(source, dict(source, rsi=approved_rsi)))
    monkeypatch.setattr(SubscriptionService, '__init__', lambda *args, **kwargs: pytest.fail('Metadata capture cannot construct a native model owner'))
    result = bootstrap.capture()
    assert result['status'] == 'CAPTURED_NOT_ADMITTED'
    store = SQLiteRunStore(root / 'core', recover=False, input_root=root / 'input')
    try:
        assert store.read_record(result['configuration_ref'])['rsi'] == approved_rsi
        binding = bootstrap.validate_capture(store, result)
        assert result['model'] == model
        assert store.read_record(result['deployment_ref'])['requested_model'] == model
        assert store.read_record(binding['protected_options']['profile_ref'])['model'] == model
        with pytest.raises(ValueError):
            bootstrap.validate_capture(store, dict(result, model='foreign-model'))
        selection = store.read_record(result['model_selection_profile_ref'])
        swapped = dict(result, model_selection_profile_ref=store.put_record('model-selection-profile',
            dict(selection, id='foreign.selection')))
        with pytest.raises(ValueError):
            bootstrap.validate_capture(store, swapped)
        assert binding['protected_options']['development_builtin_catalog'] is False
        assert binding['protected_options']['integrated_workflows'] is False
        assert binding['protected_options']['paper_summary_workflow'] is False
        assert binding['protected_options']['isolated_helper_scope'] == 'rsi-screening-helper:1'
        assert not list(store.iter_records(kinds=('model-call-start', 'model-call', 'library-admission', 'library-activation')))
        assert {row['stage'] for row in result['stages']} == set(stages)
        assert not any('paper' in row['stage'] for row in result['stages'])
        assert all(row['model_calls_ceiling'] <= 12 for row in result['stages'])
        from jiuwenswarm.research.capsules.assets import build_research_assets
        from jiuwenswarm.research_records.original_bytes import OriginalBytes
        store.close()  # Original reader requires the real writer to be closed.
        reader = bootstrap.CapturedSourceReader(root / 'core')
        try:
            before = reader.connection.total_changes
            asset = build_research_assets(reader)['screening']
            exported, originals = bootstrap.parent_public_closure(reader, result, asset)
            assert reader.connection.total_changes == before == 0
            assert exported['status'] == 'NOT_ADMISSION'
            declaration = reader.read_record(exported['parent_declaration_ref'])
            assert set(exported['parent_body_refs']) == {row['path'] for row in declaration['identity']['body']}
            assert set(exported['external_refs']) == {'_common.py'}
            assert exported['required_test_refs'] == [asset['bundle_ref'], asset['profile_ref']]
            refs = exported['public_original_refs']
            assert all(ref not in refs for ref in [result['binding_ref'], result['deployment_ref'],
                result['calibration_runtime_ref'], result['model_selection_profile_ref'],
                *[row['profile_ref'] for row in result['stages']]])
            public = OriginalBytes(tmp_path / 'public', writable=True)
            for ref, raw in originals:
                public.put_ref(ref, raw)
            assert len(public.index()) == len(refs)
            assert public.get(exported['configuration_ref'])['rsi'] == approved_rsi
            assert public.read(asset['body_refs']['ranking_parent.txt']) == reader.read_blob(asset['body_refs']['ranking_parent.txt'])
            changed = dict(asset, declaration_ref=result['configuration_ref'])
            with pytest.raises(ValueError):
                bootstrap.parent_public_closure(reader, result, changed)
            # A release factory must reject source never captured in this generation.
            with pytest.raises(ValueError):
                reader.put_blob(b'uncaptured authored-source substitution')
            with pytest.raises(sqlite3.OperationalError):
                reader.connection.execute('DELETE FROM artifacts')
        finally:
            reader.close()
        store = SQLiteRunStore(root / 'core', recover=False, input_root=root / 'input')
        # Ordinary non-installing composition must not even request Paper
        # assets. It still refuses unadmitted core catalog entries normally.
        from jiuwenswarm.research.bootstrap_core import compose_core
        from jiuwenswarm.research.operator_config import OperatorConfiguration
        from jiuwenswarm.research.contracts import Principal
        from jiuwenswarm.research.capsules import paper_assets
        monkeypatch.setattr(paper_assets, 'build_paper_assets', lambda *args, **kwargs: pytest.fail('Unused Paper workflow must not be composed'))
        composition = asyncio.run(compose_core(store=store,
            operator=OperatorConfiguration.from_mapping(store.read_record(result['configuration_ref'])),
            model=None, executor=None, readiness=None, upload_manager=None,
            principal=Principal(result['account_id'], frozenset({'local'}), frozenset()),
            configuration_ref=result['configuration_ref'], model_selection_profile_ref=result['model_selection_profile_ref'],
            deployment_ref=result['deployment_ref'], workspace_id='local', initialize=False,
            protected_options=binding['protected_options']))
        assert composition.diagnostics
        assert not list(store.iter_records(kinds=('model-call-start', 'model-call', 'library-admission', 'library-activation')))
        if generation is not None:
            assert result['schema'] == bootstrap.GENERATION_SCHEMA
            assert result['prior_namespaces'] == ['legacy']
            assert all(':generation:' + generation in store.read_record(row['profile_ref'])['id'] for row in result['stages'])
    finally:
        store.close()


def source_database(root):
    """A real WAL-mode index and immutable public original; no app authority."""
    import hashlib
    (root / 'state').mkdir(parents=True)
    raw = b'{"public":"captured source"}'
    digest = hashlib.sha256(raw).hexdigest()
    path = root / 'artifacts/sha256' / digest[:2] / digest
    path.parent.mkdir(parents=True)
    path.write_bytes(raw)
    database = root / 'state/research.sqlite3'
    writer = sqlite3.connect(database)
    assert writer.execute('PRAGMA journal_mode=WAL').fetchone()[0] == 'wal'
    writer.execute('CREATE TABLE artifacts(id TEXT PRIMARY KEY,sha256 TEXT)')
    ref = {'id': 'blob:' + digest, 'sha256': digest}
    writer.execute('INSERT INTO artifacts VALUES(?,?)', (ref['id'], digest))
    writer.commit()
    return writer, ref, raw


def test_captured_source_reader_refuses_committed_wal_instead_of_ignoring_it(tmp_path):
    writer, ref, raw = source_database(tmp_path)
    wal = tmp_path / 'state/research.sqlite3-wal'
    original = wal.read_bytes()
    assert original
    try:
        with pytest.raises(ValueError):
            bootstrap.CapturedSourceReader(tmp_path)
        assert wal.read_bytes() == original
        assert writer.execute('SELECT sha256 FROM artifacts WHERE id=?', (ref['id'],)).fetchone()[0] == ref['sha256']
    finally:
        writer.close()
    reader = bootstrap.CapturedSourceReader(tmp_path)
    try:
        assert reader.read_blob(ref) == raw
        assert reader.connection.total_changes == 0
        with pytest.raises(sqlite3.OperationalError):
            reader.connection.execute('DELETE FROM artifacts')
    finally:
        reader.close()


def test_captured_source_reader_blocks_writer_after_immutable_open(tmp_path):
    writer, ref, _ = source_database(tmp_path)
    writer.close()
    reader = bootstrap.CapturedSourceReader(tmp_path)
    writer = sqlite3.connect(tmp_path / 'state/research.sqlite3')
    try:
        writer.execute('INSERT INTO artifacts VALUES(?,?)', ('new-original', 'f' * 64))
        writer.commit()
        with pytest.raises(ValueError):
            reader.read_blob(ref)
    finally:
        writer.close()
        reader.close()


@pytest.mark.skipif(sys.platform != 'linux' or not os.environ.get('AI4R_TEST_RO_CAPTURE_ROOT'),
                    reason='Explicit genuine read-only Linux bind supplied by offline verifier launcher')
def test_captured_source_reader_on_real_readonly_mount_without_wal_or_shm():
    root = Path(os.environ['AI4R_TEST_RO_CAPTURE_ROOT'])
    assert os.statvfs(root).f_flag & os.ST_RDONLY
    database = root / 'state/research.sqlite3'
    assert not database.with_name(database.name + '-wal').exists()
    assert not database.with_name(database.name + '-shm').exists()
    ref = json.loads((root / 'public-ref.json').read_bytes())
    before = {path.relative_to(root): path.read_bytes() for path in root.rglob('*') if path.is_file()}
    # Reproduce the actual failure: ordinary ro still needs an SHM on this mount.
    ordinary = sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)
    try:
        with pytest.raises(sqlite3.OperationalError):
            ordinary.execute('SELECT sha256 FROM artifacts').fetchall()
    finally:
        ordinary.close()
    reader = bootstrap.CapturedSourceReader(root)
    try:
        assert json.loads(reader.read_blob(ref)) == {'public': 'captured source'}
        assert reader.connection.total_changes == 0
    finally:
        reader.close()
    assert {path.relative_to(root): path.read_bytes() for path in root.rglob('*') if path.is_file()} == before
