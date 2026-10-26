"""Independent grading detects corruption and identical inputs reach both arms."""
import asyncio
import copy
import importlib.util
import json

import pytest

from benchmarks.harbor_suite.value_cases import ASSETS, bank, direct_cc, exact, freeze, grade, run_offline, supplemental_cases


def helper():
    spec = importlib.util.spec_from_file_location('ordinary_value_helper', ASSETS / 'native_skill' / 'helper.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bank_breadth_and_prerequisites():
    cases = bank()
    assert len(cases) == len({c['task']['id'] for c in cases}) == 80
    families = {c['task']['id'].split('/')[0] for c in cases}
    assert len(families) == 20
    assert all(sum(c['task']['id'].startswith(f + '/') for c in cases) == 4 for f in families)
    assert sum(c['readiness'] == 'offline_worker_runnable' for c in cases) == 16
    assert all(c['measurement_status'] == 'not_run' for c in cases)
    assert all(c['prerequisites'] for c in cases)
    assert any(len(c['task']['graph']) == 3 for c in cases)


def test_scalar_types_are_not_python_equality():
    assert not exact(True, 1)
    assert not exact({'x': [False]}, {'x': [0]})
    assert not exact(1, 1.0)
    assert exact({'b': None, 'a': [1]}, {'a': [1], 'b': None})


@pytest.mark.parametrize('case', [c for c in bank() if c['worker_module']], ids=lambda c: c['task']['id'])
def test_real_worker_and_ordinary_helper_use_same_frozen_inputs(case):
    original = copy.deepcopy(case)
    native = helper().solve(case['task'])
    cc, raw = asyncio.run(direct_cc(case))
    assert grade(case, native)['content_correct'], (case['task']['id'], native)
    assert grade(case, cc)['content_correct'], (case['task']['id'], cc, raw)
    assert case == original
    if cc['status'] == 'halt':
        assert not grade(case, cc)['productive_completion']
        assert grade(case, cc)['expected_halt_met']


def test_oracle_rejects_type_corruption_extra_claim_and_wrong_verdict():
    cases = {c['task']['id']: c for c in bank()}
    case = cases['utility.table_normalize/json-types']
    corrupted = copy.deepcopy(case['expected'])
    corrupted['content']['table']['rows'][0][0] = 1
    assert not grade(case, corrupted)['content_correct']
    case = cases['utility.markdown_report/clean']
    corrupted = copy.deepcopy(case['expected'])
    corrupted['content']['report_text'] += 'This proves scientific acceptance.\n'
    assert not grade(case, corrupted)['content_correct']
    case = cases['research.verifier/missing-evidence']
    corrupted = {'status': 'complete', 'content': {'disposition': 'PASS', 'defects': []}}
    assert not grade(case, corrupted)['content_correct']


def test_freeze_separates_answers_and_is_immutable(tmp_path):
    root = tmp_path / 'frozen'
    freeze(root)
    assert len(list((root / 'public').glob('*.json'))) == 80
    public = json.loads(next((root / 'public').glob('*.json')).read_text('utf-8'))
    assert 'expected' not in public and 'oracle' not in public
    assert (root / 'native_skill' / 'SKILL.md').is_file()
    with pytest.raises(FileExistsError):
        freeze(root)


def test_offline_retains_both_arms_and_design_denominator(tmp_path):
    root = tmp_path / 'observed'
    summary = run_offline(root)
    rows = [json.loads(x) for x in (root / 'observations.jsonl').read_text('utf-8').splitlines()]
    observed = [r for r in rows if r['status'] == 'observed']
    assert len(observed) == 32
    assert sum(r['status'] == 'not_run' for r in rows) == 64
    assert summary['model_calls'] == 0 and not summary['source_changed']
    assert all(r['grade']['content_correct'] for r in observed)
    assert all(not r['native_agent_measured'] and not r['protected_cc_unit_measured'] for r in observed)
    with pytest.raises(FileExistsError):
        run_offline(root)


@pytest.mark.parametrize('case', supplemental_cases(), ids=lambda c: c['task']['id'])
def test_public_source_adaptations_against_same_helper_and_real_workers(case):
    original = copy.deepcopy(case)
    assert grade(case, helper().solve(case['task']))['content_correct']
    for typed in (False, True):
        response, raw = asyncio.run(direct_cc(case, typed=typed))
        assert grade(case, response)['content_correct'], (response, raw)
    assert case == original
    assert case['source']['upstream_commit'] == '60403a5409ff2c3f3b07dd2ca91a7a3e096839c7'
    assert case['source']['official_benchmark_result'] is False
    assert case['source']['upstream_anchor']


def test_supplement_is_opt_in_and_freeze_retains_provenance(tmp_path):
    cases = supplemental_cases()
    assert len(cases) == 8 and len(bank()) == 80
    assert not {c['task']['id'] for c in cases} & {c['task']['id'] for c in bank()}
    root = tmp_path / 'source_freeze'
    manifest = freeze(root, cases=cases)
    assert len(manifest) == 8
    assert all(row['source']['kind'] == 'public_primary_source_adaptation' for row in manifest)
    assert len(list((root / 'public').glob('*.json'))) == 8
    # A wrong parser that splits physical lines loses the embedded LF and fails.
    case = next(c for c in cases if c['task']['id'].endswith('cpython-multiline'))
    bad = copy.deepcopy(case['expected'])
    bad['content']['table']['rows'][0][0] = 'ab'
    assert not grade(case, bad)['content_correct']
