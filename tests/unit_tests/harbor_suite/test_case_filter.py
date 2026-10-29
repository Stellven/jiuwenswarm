"""Case selection changes bundle scope without changing selected authored tasks."""
import json

import pytest

from benchmarks.harbor_suite import prepare as generator
from benchmarks.harbor_suite.contracts import load_cases


IMAGE = "python:3.12-slim-bookworm@sha256:" + "1" * 64
pytestmark = pytest.mark.usefixtures("benchmark_case_assets")
CASE = "pipeline01-experiment"


def test_selected_case_preserves_all_variants_and_authored_policy(tmp_path):
    authored = next(case for case in load_cases() if case['id'] == CASE)
    destination = tmp_path / 'selected'
    manifest = generator.prepare(destination, python_image=IMAGE, case_ids=(CASE,))
    tasks = json.loads((destination / 'task-index.json').read_bytes())['tasks']
    assert manifest['case_count'] == 1
    assert manifest['task_count'] == len(authored['variants'])
    assert {task['case_id'] for task in tasks} == {CASE}
    assert {task['variant_id'] for task in tasks} == {v['id'] for v in authored['variants']}
    assert all(task['case'] == authored and task['repeat'] == 1 for task in tasks)
    assert all(task['variant'] in authored['variants'] for task in tasks)
    assert all(not row['path'].startswith('inputs/') or row['path'].startswith('inputs/' + CASE + '/')
               for row in manifest['files'])


@pytest.mark.parametrize('selection', [('',), (CASE, CASE), ('unknown-case',),
    ('../pipeline01-experiment',), (' ' + CASE,), (None,), ([],), CASE, None])
def test_invalid_selection_is_rejected_before_bundle_creation(tmp_path, selection):
    destination = tmp_path / 'invalid'
    with pytest.raises(ValueError, match='case selection'):
        generator.prepare(destination, python_image=IMAGE, case_ids=selection)
    assert not destination.exists()


def test_cli_repeated_case_flags_and_default_are_forwarded_without_generation(tmp_path, monkeypatch, capsys):
    calls = []
    def prepare(**kwargs):
        calls.append(kwargs)
        return dict(case_count=1, task_count=3, profile='smoke', expected_model='fixture')
    monkeypatch.setattr(generator, 'prepare', prepare)
    base = ['--destination', str(tmp_path / 'unused'), '--python-image', IMAGE]
    assert generator.main(base) == 0
    assert calls[-1]['case_ids'] == []
    assert generator.main(base + ['--case', CASE, '--case', 'pipeline02-recovery']) == 0
    assert calls[-1]['case_ids'] == [CASE, 'pipeline02-recovery']
    assert not (tmp_path / 'unused').exists()


def test_default_api_keeps_all_loaded_cases_without_writing_a_bundle(tmp_path, monkeypatch):
    cases = load_cases()
    visited = []
    # Stop before any payload construction or filesystem publication. This
    # checks full default selection without creating unrelated frozen outputs.
    class ObservedCases(list):
        def __iter__(self):
            for case in super().__iter__():
                visited.append(case['id'])
                yield case
    monkeypatch.setattr(generator, 'load_cases', lambda _: ObservedCases(cases))
    def stop_before_payloads(*args, **kwargs):
        raise RuntimeError('selection observed')
    monkeypatch.setattr(generator, 'regular', stop_before_payloads)
    with pytest.raises(RuntimeError, match='selection observed'):
        generator.prepare(tmp_path / 'unused', python_image=IMAGE)
    assert visited == [case['id'] for case in cases]
    assert len(visited) == 10
    assert not (tmp_path / 'unused').exists()
