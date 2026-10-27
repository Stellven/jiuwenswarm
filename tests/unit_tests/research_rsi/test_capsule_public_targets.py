"""Real carrier interoperability on public synthetic inputs; no runtime grants."""
import asyncio
import copy
from dataclasses import FrozenInstanceError

import pytest

from jiuwenswarm.research_rsi.targets.capsules import (
    capsule_catalog, evaluate_public_capsule, public_fixtures, registered_capsule,
)


@pytest.mark.parametrize('name,count', [('utility.calculate', 4), ('utility.table_normalize', 5)])
def test_actual_carrier_and_independent_checks_preserve_complete_public_packets(name, count):
    result = asyncio.run(evaluate_public_capsule(name))
    assert result['task_count'] == result['task_successes'] == count
    assert all(row['input_unmodified'] and row['packet_preserved'] for row in result['rows'])
    assert all(row['carrier_wall_s'] >= 0 and row['output_bytes'] > 0 for row in result['rows'])
    assert all(len(row['output_sha256']) == 64 for row in result['rows'])
    assert len(result['source_sha256']) == 3
    assert result['governed_execution'] is False and result['improvement_claimed'] is False
    assert result['library_admission'] == 'UNKNOWN' and result['operational_rsi_available'] is False


def test_catalog_is_finite_and_truthful_about_source_declarations_and_builder():
    rows = {row['capsule_name']: row for row in capsule_catalog()}
    assert set(rows) == {'utility.calculate', 'utility.table_normalize', 'research.builder'}
    for name in ('utility.calculate', 'utility.table_normalize'):
        assert rows[name]['source_evolution_rsi'] == 'none'
        assert rows[name]['source_evolution_may_change'] == []
        assert rows[name]['public_evaluation_available'] is True
    builder = rows['research.builder']
    assert builder['public_evaluation_available'] is False
    assert builder['scope'] == 'full native agent and artifact build loop'
    assert {'task_success', 'artifact_correctness', 'model_tokens', 'invocation_wall_s'} <= set(builder['metrics'])
    assert all(row['measured_results'] is None and row['operational_rsi_available'] is False for row in rows.values())
    with pytest.raises(ValueError): asyncio.run(evaluate_public_capsule('research.builder'))
    with pytest.raises(ValueError): registered_capsule('module:arbitrary')
    with pytest.raises(FrozenInstanceError): registered_capsule('utility.calculate').scope = 'helper'


@pytest.mark.parametrize('name', ['utility.calculate', 'utility.table_normalize'])
def test_public_fixture_calls_return_independent_fresh_packet_and_expected_bytes(name):
    original = public_fixtures(name)
    untouched = copy.deepcopy(original)
    changed = public_fixtures(name)
    changed[0]['packet']['limitations'].clear()
    changed[0]['expected_task_output'].clear()
    assert public_fixtures(name) == untouched == original


@pytest.mark.parametrize('name,module,key', [
    ('utility.calculate', 'calculate', 'calculation_result'),
    ('utility.table_normalize', 'table_normalize', 'table'),
])
def test_independent_original_input_checks_reject_corrupted_production_output(name, module, key):
    import importlib
    from types import SimpleNamespace
    worker = importlib.import_module(f'jiuwenswarm.research.capsule_extensions.{module}.worker')
    checker = importlib.import_module(f'jiuwenswarm.research.capsule_extensions.{module}.checks')
    import json
    packet = public_fixtures(name)[0]['packet']
    result = json.loads(asyncio.run(worker.execute(None, {'packet': packet}))['result'].data)
    result['data'][key] = {}
    rows = checker.check(SimpleNamespace(output_refs={}), {'packet': packet}, {'result': result})
    assert next(row for row in rows if row['check_id'] == 'packet_integrity')['outcome'] == 'FAIL'


# Historical proofs pin these exact public packets/expected outputs; the
# data-driven fixture definitions must reproduce them byte for byte.
PUBLIC_BASELINE_SHA256 = {
    'utility.calculate': '09814c84b224a12715a2ed4597c40c24b390b1f174f56d035066040a971cf8f6',
    'utility.table_normalize': '6a6108db666c3b0e774e0180ce211fea0fbba69317cf3d2ac2e3e393e1cbb497',
}


@pytest.mark.parametrize('name', sorted(PUBLIC_BASELINE_SHA256))
def test_data_driven_public_baseline_is_byte_identical_to_historical_definitions(name):
    import hashlib
    from jiuwenswarm.research_rsi.records import encoded
    assert hashlib.sha256(encoded(public_fixtures(name))).hexdigest() == PUBLIC_BASELINE_SHA256[name]


def test_catalog_targets_are_discovered_from_fixture_manifests_with_objective_metrics():
    from pathlib import Path
    from jiuwenswarm.research_rsi.targets import capsules
    discovered = {path.parent.parent.name for path in capsules._manifest_paths()}
    assert discovered == {'calculate', 'table_normalize'}
    rows = {row['capsule_name']: row for row in capsule_catalog()}
    for name in ('utility.calculate', 'utility.table_normalize'):
        row, target = rows[name], registered_capsule(name)
        assert row['objective'] == target.objective == 'correctness_then_latency_above_noise'
        assert row['held_out_case_count'] == len(capsules.fixture_set(name, 'held_out')) >= 5
        assert row['public_extended_case_count'] == len(capsules.fixture_set(name, 'public_extended')) >= 5
        assert row['fixture_sets'] == ['public', 'public_extended', 'held_out']
        assert target.metrics == ('task_success', 'carrier_wall_s', 'output_bytes')
        assert Path(capsules.__file__).resolve().parents[2].joinpath(target.carrier_path).is_file()
    assert rows['research.builder']['held_out_case_count'] == 0 and rows['research.builder']['objective'] is None
    with pytest.raises(ValueError):
        capsules.fixture_set('research.builder', 'public')
    with pytest.raises(ValueError):
        capsules.fixture_set('utility.calculate', 'private')


def test_fixture_tree_is_a_runtime_forbidden_path_and_outside_release_closures():
    from jiuwenswarm.research_rsi.targets import capsules
    from jiuwenswarm.research_rsi.targets.capsule_runtime import _path
    for path in capsules._manifest_paths():
        relative = 'source/jiuwenswarm/' + path.relative_to(capsules._EXTENSIONS.parents[1]).as_posix()
        with pytest.raises(ValueError):
            _path(relative)
        # Release closures and asset bodies glob only the capsule directory's own *.py files.
        assert not list(path.parent.glob('*.py'))


@pytest.mark.parametrize('name', ['utility.calculate', 'utility.table_normalize'])
@pytest.mark.parametrize('fixture_set', ['public_extended', 'held_out'])
def test_new_fixture_expected_outputs_are_accepted_by_the_independent_checker(name, fixture_set):
    import importlib
    import json
    from types import SimpleNamespace
    from jiuwenswarm.research.state import json_bytes
    from jiuwenswarm.research_rsi.targets import capsules
    stem = capsules._STEMS[name]
    checker = importlib.import_module(f'jiuwenswarm.research.capsule_extensions.{stem}.checks')
    key = registered_capsule(name).task_output_key
    cases = capsules.fixture_set(name, fixture_set)
    assert len({case['id'] for case in cases}) == len(cases)
    for case in cases:
        expected = copy.deepcopy(case['packet'])
        expected['data'][key] = case['expected_task_output']
        rows = checker.check(SimpleNamespace(output_refs={}), {'packet': case['packet']},
                             {'result': json.loads(json_bytes(expected))})
        assert [row['outcome'] for row in rows] == ['PASS', 'PASS'], case['id']
        wrong = json.loads(json_bytes(expected)); wrong['data'][key] = {}
        rows = checker.check(SimpleNamespace(output_refs={}), {'packet': case['packet']}, {'result': wrong})
        assert rows[1]['outcome'] == 'FAIL', case['id']
