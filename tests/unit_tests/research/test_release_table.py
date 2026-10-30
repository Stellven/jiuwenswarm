"""One release table: every stage selects its versions through it and unknown names fail loudly."""
import json
from contextlib import closing
from importlib.resources import files
from pathlib import Path
from unittest.mock import patch

import pytest

from jiuwenswarm.research import releases
from jiuwenswarm.research.contracts import ResearchError, validate
from jiuwenswarm.research.local_profile import _require_science_resources, _static_template, capture_local_profile
from jiuwenswarm.research.state import SQLiteRunStore

ALL_VERSIONS = [(stage, version) for stage in releases.STAGES for version in releases.release_names(stage)]


@pytest.mark.parametrize('stage', releases.STAGES)
@pytest.mark.parametrize('bad', ['latest', 'm1-99', None, [], 6])
def test_unknown_release_fails_loudly(stage, bad):
    with pytest.raises(ResearchError, match='Unsupported explicit') as raised:
        releases.require_release(stage, bad, 'configuration_override')
    assert raised.value.code == 'configuration_override'


@pytest.mark.parametrize('stage,version', ALL_VERSIONS)
def test_every_listed_release_is_accepted(stage, version):
    assert releases.require_release(stage, version, 'x') == version


def test_implicit_release_is_frozen_and_listed():
    assert {s: releases.implicit_release(s) for s in releases.STAGES} == {
        'intent': 'm1-6', 'requirements': 'm1-8', 'screening': 'm1-4', 'delivery': 'm1-5'}
    assert all(releases.implicit_release(s) in releases.release_names(s) for s in releases.STAGES)
    assert releases.capture_default('intent') == 'm1-8'


def test_environment_selections_pass_only_what_is_set():
    assert releases.release_options_from_environment({}) == {}
    env = {'JIUWENSWARM_M1_INTENT_VERSION': 'm1-7', 'JIUWENSWARM_M1_DELIVERY_VERSION': 'm1-6', 'UNRELATED': 'x'}
    assert releases.release_options_from_environment(env) == {'intent_version': 'm1-7', 'delivery_version': 'm1-6'}
    # A bad value is carried through so capture_local_profile refuses it.
    with pytest.raises(ResearchError, match='Unsupported explicit Screening'):
        capture_local_profile(None, 'unused', **releases.release_options_from_environment({'JIUWENSWARM_M1_SCREENING_VERSION': 'bogus'}))


@pytest.mark.asyncio
@pytest.mark.parametrize('stage', releases.STAGES)
async def test_bootstrap_refuses_unknown_release(tmp_path, stage):
    from jiuwenswarm.research.bootstrap_core import compose_core
    with closing(SQLiteRunStore(tmp_path)) as store:
        with pytest.raises(ResearchError, match='Unsupported explicit') as raised:
            await compose_core(store=store, operator=None, model=None, executor=None, readiness=None, upload_manager=None,
                principal=None, configuration_ref=None, model_selection_profile_ref=None, deployment_ref=None,
                workspace_id='local', protected_options={stage + '_version': 'bogus'})
        assert raised.value.code == 'configuration_override'


def test_bootstrap_pins_every_non_implicit_selection():
    assets = {stage: {'declaration_ref': {'sha256': stage + '-' + releases.implicit_release(stage)}} for stage in releases.STAGES}
    chosen = {stage: releases.implicit_release(stage) for stage in releases.STAGES}
    assert releases.pinned_extras(chosen, assets, assets) == ()
    chosen.update(intent='m1-8', delivery='m1-6')
    assert releases.pinned_extras(chosen, assets, assets) == ('intent-m1-6', 'delivery-m1-5')
    chosen.update(requirements='m1-9', screening='m1-6')
    assert releases.pinned_extras(chosen, assets, assets) == tuple(assets[s]['declaration_ref']['sha256'] for s in releases.STAGES)


def _raw():
    return files('jiuwenswarm.research_assets').joinpath('planner/static-template.json').read_bytes()


def _node(template, name):
    return next(n for n in template['nodes'] if n['node_id'] == name)


@pytest.mark.parametrize('screening', releases.release_names('screening'))
@pytest.mark.parametrize('delivery', releases.release_names('delivery'))
def test_static_template_selects_each_release(tmp_path, screening, delivery):
    with closing(SQLiteRunStore(tmp_path)) as store:
        ref = _static_template(store, screening_version=screening, delivery_version=delivery)
        template = json.loads(store.read_blob(ref))
        validate('static-template', template)
        old = json.loads(_raw())
        # Screening m1-6 has its own contracts, so the pipeline node keeps its installed release.
        assert _node(template, 'screening')['cc']['cc_version'] == ('m1-4' if screening == 'm1-6' else screening)
        assert _node(template, 'delivery')['cc']['cc_version'] == delivery
        for before in old['nodes']:
            if before['node_id'] not in {'screening', 'delivery'}:
                assert _node(template, before['node_id']) == before
        if delivery == 'm1-6':
            node = _node(template, 'delivery')
            assert [(p['name'], p['artifact_type'], p['source_kind'], p['run_input_key']) for p in node['inputs']] == [
                ('evidence_bundle', 'delivery_evidence_bundle', 'accepted_ref', 'evidence_bundle')]
            assert [p['name'] for p in node['outputs']] == ['research_report']
        else:
            assert _node(template, 'delivery') == _node(old, 'delivery')
        if (screening, delivery) in {('m1-4', 'm1-5'), ('m1-6', 'm1-5')}:
            assert store.read_blob(ref) == _raw()


def test_static_template_rejects_unknown_release(tmp_path):
    with closing(SQLiteRunStore(tmp_path)) as store:
        for kwargs in ({'screening_version': 'm1-9'}, {'delivery_version': 'latest'}):
            with pytest.raises(ResearchError, match='Unsupported explicit'):
                _static_template(store, **kwargs)


def _capture(store, root, **options):
    inputs = root / 'input'
    inputs.mkdir(exist_ok=True)
    with patch('jiuwenswarm.research.local_profile.os.geteuid', return_value=inputs.stat().st_uid, create=True), \
         patch('jiuwenswarm.research.local_profile.stat.S_IMODE', return_value=0o700), \
         patch('jiuwenswarm.research.bootstrap_gateway._protected_file', side_effect=lambda p: Path(p).read_bytes()):
        return capture_local_profile(store, root / 'operator', input_root=inputs, **options)


def test_profile_freezes_each_delivery_release_and_rejects_drift(tmp_path):
    with closing(SQLiteRunStore(tmp_path / 'state')) as store:
        result = _capture(store, tmp_path, delivery_version='m1-6', allow_missing_science=True)
        binding = store.read_record(result['binding_ref'])
        assert binding['protected_options']['delivery_version'] == 'm1-6'
        template = store.read_record(store.read_record(binding['configuration_ref'])['cc']['static_template_ref'])
        assert _node(template, 'delivery')['cc']['cc_version'] == 'm1-6'
        assert _capture(store, tmp_path, delivery_version='m1-6', allow_missing_science=True) == result
        with pytest.raises(ResearchError, match='Frozen Delivery release changed'):
            _capture(store, tmp_path, allow_missing_science=True)


@pytest.mark.parametrize('stage', releases.STAGES)
def test_profile_refuses_unknown_release_before_custody(stage):
    with pytest.raises(ResearchError, match='Unsupported explicit'):
        capture_local_profile(None, 'unused', **{stage + '_version': 'bogus'})


def test_checking_only_refresh_cannot_move_delivery():
    with pytest.raises(ResearchError, match='Checking-only refresh'):
        capture_local_profile(None, 'unused', delivery_version='m1-6', legacy_checking_refresh=True)


def _inventory(store, keys):
    ref = store.put_blob(b'resource')
    rows = [{'resource_key': k, 'kind': 'file', 'available': True, 'quantity': 1, 'ref': ref} for k in keys]
    return store.put_record('resource-inventory', {'schema_version': '1.0.0', 'id': 'test_inventory', 'resources': rows})


def test_empty_inventory_is_refused_when_the_template_needs_science_resources(tmp_path):
    with closing(SQLiteRunStore(tmp_path)) as store:
        static = _static_template(store)
        with pytest.raises(ResearchError, match='JIUWENSWARM_M1_EXTERNAL_DATASET') as raised:
            _require_science_resources(store, static, _inventory(store, []))
        assert raised.value.code == 'local_profile_science_resources'
        assert raised.value.details['missing'] == ['baseline_resource', 'environment_lock', 'validation_resource']
        with pytest.raises(ResearchError, match='validation_resource'):
            _require_science_resources(store, static, _inventory(store, ['baseline_resource', 'environment_lock']))


def test_inventory_with_science_resources_is_accepted(tmp_path):
    with closing(SQLiteRunStore(tmp_path)) as store:
        static = _static_template(store)
        _require_science_resources(store, static, _inventory(store, ['baseline_resource', 'validation_resource', 'environment_lock', 'poc_workspace']))


def test_profile_capture_without_dataset_fails_unless_explicitly_allowed(tmp_path, monkeypatch):
    monkeypatch.delenv('JIUWENSWARM_M1_EXTERNAL_DATASET', raising=False)
    with closing(SQLiteRunStore(tmp_path / 'state')) as store:
        with pytest.raises(ResearchError, match='JIUWENSWARM_M1_EXTERNAL_DATASET'):
            _capture(store, tmp_path)
        assert not (tmp_path / 'operator' / 'bootstrap.json').exists()
        assert _capture(store, tmp_path, allow_missing_science=True)['binding_ref']


def _plan_source(store, result):
    return store.read_record(store.read_record(result['binding_ref'])['configuration_ref'])['cc']['plan_source']


def test_profile_plan_source_defaults_static_and_freezes(tmp_path):
    with closing(SQLiteRunStore(tmp_path / 'state')) as store:
        result = _capture(store, tmp_path, allow_missing_science=True)
        assert _plan_source(store, result) == 'static'
        assert _capture(store, tmp_path, allow_missing_science=True, plan_source='static') == result
        with pytest.raises(ResearchError, match='Frozen plan source changed'):
            _capture(store, tmp_path, allow_missing_science=True, plan_source='planned')


def test_profile_captures_planned_and_unnamed_recapture_adopts_it(tmp_path):
    with closing(SQLiteRunStore(tmp_path / 'state')) as store:
        result = _capture(store, tmp_path, allow_missing_science=True, plan_source='planned')
        assert _plan_source(store, result) == 'planned'
        assert _capture(store, tmp_path, allow_missing_science=True) == result
        with pytest.raises(ResearchError, match='Frozen plan source changed'):
            _capture(store, tmp_path, allow_missing_science=True, plan_source='static')


def test_profile_refuses_unknown_plan_source():
    with pytest.raises(ResearchError, match='Plan source must be static or planned'):
        capture_local_profile(None, 'unused', plan_source='dynamic')


def _main_options(tmp_path, environ, existing=False):
    from jiuwenswarm.research import local_profile
    directory = tmp_path / 'operator' / local_profile.PROFILE_NAME
    if existing:
        directory.mkdir(parents=True)
        (directory / 'config.json').write_text('{}')
    seen = {}
    environ = {'JIUWENSWARM_M1_LOCAL_RESEARCH': '1', 'JIUWENSWARM_M1_STATE': str(tmp_path), **environ}
    with patch.dict('os.environ', environ, clear=True), \
         patch('jiuwenswarm.research.local_profile.os.name', 'posix'), \
         patch('jiuwenswarm.research.local_profile.os.geteuid', return_value=10001, create=True), \
         patch('jiuwenswarm.research.local_profile.SQLiteRunStore'), \
         patch('jiuwenswarm.research.local_profile.capture_local_profile', side_effect=lambda store, path, **kw: seen.update(kw)):
        local_profile.main()
    return seen


def test_product_entry_captures_planned_and_benches_pin_static(tmp_path):
    assert _main_options(tmp_path / 'new', {})['plan_source'] == 'planned'
    assert 'plan_source' not in _main_options(tmp_path / 'old', {}, existing=True)
    assert _main_options(tmp_path / 'bench', {'JIUWENSWARM_M1_PLAN_SOURCE': 'static'}, existing=True)['plan_source'] == 'static'


def test_product_entry_selects_current_releases_for_new_profiles_only(tmp_path):
    new = _main_options(tmp_path / 'new', {})
    assert (new['requirements_version'], new['screening_version']) == ('m1-9', 'm1-5')
    old = _main_options(tmp_path / 'old', {}, existing=True)
    assert 'requirements_version' not in old and 'screening_version' not in old
    named = _main_options(tmp_path / 'named', {'JIUWENSWARM_M1_REQUIREMENTS_VERSION': 'm1-8',
                                               'JIUWENSWARM_M1_SCREENING_VERSION': 'm1-4'})
    assert (named['requirements_version'], named['screening_version']) == ('m1-8', 'm1-4')
