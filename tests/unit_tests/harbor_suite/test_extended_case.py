import importlib.util
from pathlib import Path

from benchmarks.harbor_suite.contracts import EXPECTED, EXTENDED, load_cases, task_key
from benchmarks.harbor_suite.prepare import prepare

ROOT = Path(__file__).resolve().parents[3] / 'benchmarks/harbor_suite/additional_cases'


def test_extension_is_explicit_and_default_registry_stays_ten():
    assert len(EXPECTED) == 10 and 'cc03-typed-table' not in EXPECTED
    cases = load_cases(ROOT, case_ids=['cc03-typed-table'])
    assert len(cases[0]['variants']) == 4
    assert cases[0]['classification'] == 'extended_performance'
    assert task_key('cc03-typed-table', 'json-types', 1).startswith('cc03-typed-table-')


def test_extension_freezes_real_e3_task_but_not_fabricated_binding(tmp_path):
    result = prepare(tmp_path / 'bundle', cases_root=ROOT, case_ids=['cc03-typed-table'],
                     variant_ids=['json-types'], python_image='python:3.12@sha256:' + '1' * 64)
    assert result['case_count'] == result['task_count'] == 1
    import json
    task = json.loads((tmp_path / 'bundle/task-index.json').read_bytes())['tasks'][0]
    assert task['entrypoint'] == 'single_cc' and 'evaluation_binding' not in task
    assert task['case']['classification'] == 'extended_performance'
