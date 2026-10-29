"""Administrative metadata controls; no probe, fixtures, model or cases run."""
import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


SOURCE = Path(__file__).resolve().parents[3] / 'deploy/m1/rsi_session_setup.py'
spec = importlib.util.spec_from_file_location('session_metadata_controls', SOURCE)
setup = importlib.util.module_from_spec(spec); spec.loader.exec_module(setup)


def test_metadata_probe_has_fixed_image_program_and_finite_unprivileged_no_network_command():
    image = 'sha256:' + 'a' * 64
    plan = setup.probe_plan(image); command = plan['command']
    assert command[:3] == ['/usr/bin/docker', '--host', setup.host_module().SOCKET]
    for flag, value in (('--user', '12003:12003'), ('--network', 'none'), ('--memory', '128m'),
                        ('--memory-swap', '128m'), ('--pids-limit', '32'), ('--cpus', '2'), ('--cap-drop', 'ALL')):
        assert command[command.index(flag) + 1] == value
    assert '--read-only' in command and '--mount' not in command and '--volume' not in command
    assert command[-5:] == [image, '-I', '-B', '-c', setup.PROBE]
    assert plan['program_ref'] == setup.pin(setup.PROBE.encode())
    assert 'No candidate/fixture/product invocation' in plan['limitations']


@pytest.mark.parametrize('image', ['latest', 'repo:mutable', 'sha256:short', 'sha256:' + 'A' * 64, None])
def test_probe_plan_refuses_mutable_or_ambiguous_images(image):
    with pytest.raises(ValueError): setup.probe_plan(image)


def test_generation_preserves_legacy_paths_and_separates_all_host_metadata():
    image = 'sha256:' + 'a' * 64
    legacy = setup.probe_plan(image)
    current = setup.probe_plan(image, 'output-review-v3')
    assert legacy['context_file'] == str(setup.HOST_CONTEXT_FILE)
    assert legacy['approval_file'] == str(setup.HOST_APPROVAL_FILE)
    for key in ('context_file', 'approval_file', 'setup_file', 'records_root'):
        assert legacy[key] != current[key]
        assert 'output-review-v3' in current[key]
    assert legacy['command'] == current['command']
    assert legacy['program_ref'] == current['program_ref']


@pytest.mark.parametrize('generation', ['', '../escape', '/absolute', 'a/b', 'a\\b', 'A', 'a' * 65, 1])
def test_generation_refuses_path_or_ambiguous_names(generation):
    with pytest.raises(ValueError): setup.host_paths(generation)


def test_fixed_probe_parses_and_never_calls_helper_or_model_or_fixture_code():
    tree = ast.parse(setup.PROBE)
    names = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert 'worker_program' in names and 'registered_helper' in names  # introspection only
    assert not names & {'rank_opportunities', 'prepare_ranking', 'compile_helper_session', 'run_helper', 'invoke_governed'}
    assert "root.parent/'research/capsules/ranking.py'" in setup.PROBE
    assert "'candidate_executed':False" in setup.PROBE and "'normal_cc_invoked':False" in setup.PROBE


def test_changed_root_image_approval_refuses_before_any_probe_or_record_write(monkeypatch):
    image = 'sha256:' + 'a' * 64
    monkeypatch.setattr(setup.sys, 'platform', 'linux')
    monkeypatch.setattr(setup.os, 'geteuid', lambda: 0, raising=False)
    host = setup.host_module()
    monkeypatch.setattr(setup, 'host_module', lambda: SimpleNamespace(
        SOCKET=host.SOCKET, status=lambda: {}, run=lambda *args: pytest.fail('Unapproved image must not be inspected or run')))
    approval = {'schema': 'ai4r-rsi-helper-probe-approval:1', 'worker_image': 'sha256:' + 'b' * 64,
        'program_ref': setup.pin(setup.PROBE.encode()), 'parent_ref': setup.pin(b'negative-parent-control'),
        'parent_declaration_ref': setup.pin(b'negative-declaration-control'),
        'worker_bounds': {'memory_mb': 128, 'pids_max': 8, 'timeout_s': 2},
        'reviewed_by': 'controlled-root-review', 'reviewed_at': '2026-10-25T00:00:00Z'}
    monkeypatch.setattr(setup, 'protected', lambda _: approval)
    monkeypatch.setattr(setup.subprocess, 'run', lambda *args, **kwargs: pytest.fail('Probe must not run'))
    with pytest.raises(ValueError): setup.root_capture(image)


@pytest.mark.parametrize('value', [{}, {'id': 'missing'}, {'id': '', 'sha256': 'a' * 64},
    {'id': 'record', 'sha256': 'not-hash'}, {'id': 'record', 'sha256': 'a' * 64, 'approved': True}])
def test_only_exact_original_ref_shape_is_accepted(value):
    with pytest.raises(ValueError): setup.exact_ref(value)


def test_frozen_helper_tests_bind_disclosed_originals_and_sources_without_running_candidate(tmp_path, monkeypatch):
    from jiuwenswarm.research_rsi.records import RecordStore
    from jiuwenswarm.research_rsi.targets import ranking_preparation as preparation_module
    import jiuwenswarm.research_rsi as package
    store = RecordStore(tmp_path / 'records')
    try:
        parent_ref = store.put_bytes(b'controlled-original-parent-not-executed')
        preparation = {'parent_ref': parent_ref, 'generator_ref': store.put_bytes(
            (Path(package.__file__).parent / 'targets/ranking_preparation.py').read_bytes())}
        result = {'preparation_ref': store.put({'controlled': 'reviewed-preparation'})}
        review_ref = store.put({'controlled': 'independent-review'})
        monkeypatch.setattr(setup, 'reviewed_preparation', lambda value: (result, review_ref, preparation))
        disclosed = {'schema': 'ai4r-rsi-visible-ranking-cases:1', 'parent_ref': parent_ref,
            'cases': [{'id': 'controlled-development-case', 'inputs': {'scores': [dict(idea_id='one',
                novelty=1, feasibility=2, compute_alignment=3, eligible=True)]},
                'expected': {'ranking': [{'rank': 1, 'idea_id': 'one', 'total': 6}], 'selected_idea_id': 'one'}}]}
        def export(value, ref, *, approved_review_ref):
            assert value is store and ref == result['preparation_ref'] and approved_review_ref == review_ref
            return disclosed
        monkeypatch.setattr(preparation_module, 'development_export', export)
        capture = setup.helper_test_materials(store)
        definition = store.get(capture['required_test_refs'][0])
        assert definition['schema'] == 'ai4r-rsi-frozen-helper-test:1'
        assert definition['parent_ref'] == parent_ref and definition['execution_performed'] is False
        assert store.get(definition['input_ref']) == disclosed['cases'][0]['inputs']
        assert store.get(definition['expected_ref']) == disclosed['cases'][0]['expected']
        assert store.get(definition['development_export_ref']) == disclosed
        assert set(definition['source_refs']) == {'targets/__init__.py', 'targets/ranking.py', 'worker.py', 'fixed_resources.py'}
        visible = store.get(capture['visible_context_ref'])
        assert visible['mandatory_fixtures'] == capture['mandatory_fixtures']
        assert visible['required_test_refs'] == capture['required_test_refs']
        assert review_ref not in capture['public_original_refs'] and result['preparation_ref'] not in capture['public_original_refs']
        assert 'passed' not in definition
        preparation['generator_ref'] = store.put_bytes(b'changed-unreviewed-generator')
        with pytest.raises(ValueError): setup.helper_test_materials(store)
    finally:
        store.close()
