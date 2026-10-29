"""Finite E3 custody checks. Unit fixtures are never live product evidence."""
import asyncio
import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from benchmarks.harbor_suite import evaluation as e
from benchmarks.harbor_suite.adapter import preflight_blockers
from benchmarks.harbor_suite.contracts import canonical, pin, read_json, resolve_cases_root, validate_bundle
from benchmarks.harbor_suite.prepare import prepare
from benchmarks.harbor_suite.evidence import normalize_single_cc

IMAGE = 'python:3.12-slim-bookworm@sha256:'+'1'*64
pytestmark = pytest.mark.usefixtures("benchmark_case_assets")


def overlay():
    criteria = read_json(resolve_cases_root()/'cc01-transfer/referee/criteria.json')
    variant = criteria['variants']['screen-missing']; capsule = variant['binding']
    scope = dict(run_id='unit-campaign__unit-case__baseline__r00', campaign_id='unit-campaign',
                 case_id='unit-case', case_version=1, config_id='baseline', repeat_index=0)
    request = dict(request_id='unit-request', campaign_id=scope['campaign_id'], case_id=scope['case_id'],
                   evaluation_profile_id='unit-profile', capsule_id=capsule['name'], capsule_version=capsule['version'],
                   capsule_declaration_sha256=capsule['declaration_ref']['sha256'],
                   inputs=[dict(port=p, sha256=r['sha256']) for p, r in variant['input_refs'].items()])
    binding = {k: scope[k] for k in ('campaign_id', 'run_id', 'case_id')}
    binding.update(variant_id='screen-missing', run_scope=scope, expected_request=request)
    return dict(schema='ai4r-harbor-evaluation-overlay:1', case_id='cc01-transfer', variant_id='screen-missing',
                binding=binding, criteria=criteria)


@pytest.fixture(scope='module')
def prepared(tmp_path_factory):
    root = tmp_path_factory.mktemp('finite-evaluation')
    source = root/'overlay.json'; source.write_bytes(canonical(overlay()))
    bundle = root/'bundle'
    prepare(bundle, python_image=IMAGE, case_ids=('cc01-transfer',), variant_ids=('screen-missing',), evaluation_overlay=source)
    return bundle, read_json(bundle/'task-index.json')['tasks'][0]


def test_one_prepared_variant_freezes_request_and_protected_criteria(prepared):
    bundle, task = prepared
    assert len(validate_bundle(bundle)['tasks']) == 1
    assert task['evaluation_binding'] == overlay()['binding']
    assert read_json(bundle/'tasks'/task['task_key']/'tests/criteria.json') == overlay()['criteria']
    assert task['protected_material_pins']['referee/evaluation-overlay.json'] == task['evaluation_overlay_pin']
    assert preflight_blockers(task, dict(mode='live', evaluation_config='protected.json')) == []
    assert preflight_blockers(task, dict(mode='live'))


def test_overlay_rejects_changed_request_input_and_capsule_pins():
    for field in ('capsule_version', 'inputs'):
        value = overlay()
        value['binding']['expected_request'][field] = 'other' if field == 'capsule_version' else []
        with pytest.raises(ValueError, match='frozen'):
            e.validate_overlay(value)


def test_changed_prepared_public_bytes_are_rejected(tmp_path):
    value = overlay(); source = tmp_path/'brief.json'; source.write_bytes(b'original prepared bytes')
    value['prepared_inputs'] = {'public/brief.json': {'path': str(source),
        'artifact_ref': {'id': 'unit-published', 'sha256': pin(source)['sha256']}}}
    e.validate_overlay(value)
    source.write_bytes(b'swapped after publication')
    with pytest.raises(ValueError, match='original public input bytes changed'):
        e.validate_overlay(value)


def configuration(tmp_path, prepared):
    bundle, task = prepared
    output = tmp_path/'output'; output.mkdir()
    cwd = tmp_path/'controller'; cwd.mkdir()
    results = tmp_path/'results'; results.mkdir()
    script = cwd/'runner.py'; script.write_text('# unit fixture: no product effects\n')
    command = [sys.executable, str(script)]
    value = dict(schema='ai4r-harbor-evaluation-config:1', task_key=task['task_key'], command=command,
                 cwd=str(cwd), result_root=str(results), control_files={name: pin(name) for name in command})
    path = tmp_path/'host-config.json'; path.write_bytes(canonical(value))
    suite = dict(bundle_root=bundle, output_root=output, evaluation_config=str(path), mode='live')
    return value, suite


def test_changed_or_unpinned_launcher_is_rejected(prepared, tmp_path):
    value, suite = configuration(tmp_path, prepared); task = prepared[1]
    e.load_config(suite['evaluation_config'], task, suite)
    Path(value['command'][1]).write_text('changed')
    with pytest.raises(ValueError, match='control file changed'):
        e.load_config(suite['evaluation_config'], task, suite)


def test_claimed_but_incomplete_attempt_never_relaunches(prepared, tmp_path, monkeypatch):
    value, suite = configuration(tmp_path, prepared); task = prepared[1]; launches = []
    monkeypatch.setattr(e, 'os', SimpleNamespace(name='posix'))
    async def create(*args, **kwargs):
        launches.append(args)
        async def wait(): return 0
        return SimpleNamespace(wait=wait)
    monkeypatch.setattr(e.asyncio, 'create_subprocess_exec', create)
    monkeypatch.setattr(e, 'snapshot', lambda *args: None)
    import benchmarks.harbor_suite.evidence as evidence
    def unresolved(*args): raise ValueError('original evaluation export incomplete')
    monkeypatch.setattr(evidence, 'normalize_single_cc', unresolved)
    for _ in range(2):
        with pytest.raises(ValueError, match='incomplete'):
            asyncio.run(e.dispatch(suite, task, 'same-harbor-trial'))
    assert len(launches) == 1
    assert (suite['output_root']/'.harbor-evaluation-active.json').is_file()
    with pytest.raises(ValueError, match='unresolved evaluation'):
        asyncio.run(e.dispatch(suite, task, 'another-harbor-trial'))
    assert len(launches) == 1


def test_original_evaluation_reader_receives_frozen_request_and_retained_inventory(prepared, tmp_path, monkeypatch):
    from benchmarks.harbor_suite.adapter import receipt
    from jiuwenswarm.research_sidecar.evaluation_records import EvaluationRecords
    task = prepared[1]; binding = task['evaluation_binding']; folder = tmp_path/'runs'/binding['run_id']; folder.mkdir(parents=True)
    request_file = folder/'evaluation-request.json'; request_file.write_bytes(canonical(binding['expected_request']))
    exports = [dict(path='evaluation-request.json', sha256=pin(request_file)['sha256'])]
    run = dict(schema='run-record:1', entry_mode='single_cc', **binding['run_scope'],
               request_id=binding['expected_request']['request_id'], launched=True, ended_at='unit-time', exports=exports)
    (folder/'run_record.json').write_bytes(canonical(run))
    (tmp_path/'suite-receipt.json').write_bytes(canonical(receipt(task, status='observed', launched=True,
        custody='live', campaign_id=binding['campaign_id'])))
    calls = []; complete = []
    def reader(path, **kwargs):
        calls.append((path, kwargs))
        return SimpleNamespace(request={'entry_point':'E3'}, terminal={'state':'completed'}, by_kind={},
                               require_complete=lambda: complete.append(True))
    monkeypatch.setattr(EvaluationRecords, 'from_frozen', reader)
    normalized = normalize_single_cc(tmp_path, task)
    assert normalized['execution']['terminal'] and complete == [True]
    assert calls[0][1]['expected_request'] == binding['expected_request']
    assert calls[0][1]['inventory'] == exports
    request_file.write_bytes(b'{}')
    with pytest.raises(ValueError, match='frozen request'):
        normalize_single_cc(tmp_path, task)
    assert len(calls) == 1
