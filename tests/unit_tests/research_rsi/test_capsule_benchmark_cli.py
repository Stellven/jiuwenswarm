"""Real catalog baselines use selected release closures and no model service."""
import asyncio
import json
import os
from pathlib import Path

import pytest

from jiuwenswarm.research_rsi.targets import capsule_benchmark_cli as cli
from jiuwenswarm.research_rsi.targets.capsules import capsule_catalog


def test_inventory_reports_every_selected_release_without_invented_coverage():
    inventory = cli.benchmark_inventory()
    assert {row['capsule_name'] for row in inventory} == {row['capsule_name'] for row in capsule_catalog()}
    ready = {row['capsule_name'] for row in inventory if row['status'] == 'ready'}
    assert {'utility.calculate', 'utility.table_normalize', 'utility.markdown_report',
            'utility.calculate_typed', 'utility.table_normalize_typed', 'utility.markdown_report_typed',
            'utility.packet_report', 'utility.summary_to_packet'} <= ready
    skipped = [row for row in inventory if row['status'] == 'skipped']
    assert skipped and all(row['reason'] for row in skipped)
    assert all('benchmark' not in row for row in skipped)


@pytest.mark.skipif(os.name != 'posix', reason='Real LocalDispatcher requires POSIX (Linux/WSL)')
def test_catalog_command_captures_current_release_and_measures_real_a_a(tmp_path):
    output = tmp_path / 'baselines'
    overrides = {'repetitions': 1, 'warmups': 0, 'bootstrap_resamples': 100,
                 'batch_iterations': {'small': 1, 'large': 1}}
    report = asyncio.run(cli.run_catalog(output_root=output, overrides=overrides))
    assert report['counts']['error'] == 0, [(row['capsule_name'], row['reason']) for row in report['rows']]
    tested = [row for row in report['rows'] if row['status'] == 'tested']
    assert {'utility.calculate', 'utility.table_normalize', 'utility.markdown_report',
            'utility.calculate_typed', 'utility.table_normalize_typed', 'utility.markdown_report_typed',
            'utility.packet_report', 'utility.summary_to_packet'} <= {row['capsule_name'] for row in tested}
    manifest = json.loads((output / 'runtime-manifest.json').read_text())
    assert manifest['target_bindings']
    assert all('fixtures' not in Path(row['path']).parts for row in manifest['files'])
    for row in tested:
        benchmark = row['benchmark']
        assert benchmark['scope'] == 'local_unprotected' and benchmark['model_calls'] == 0
        assert benchmark['correctness_passed'], benchmark['correctness']
        assert benchmark['self_comparison'] and benchmark['objective_met'] is False
        assert benchmark['parent_sha256'] == benchmark['candidate_sha256']
        assert benchmark['samples'] and benchmark['protected_jobs'] == benchmark['planned_jobs']
        assert row['release_binding'] == manifest['target_bindings'][row['capsule_name']]
        assert row['improvement_claimed'] is False
        assert (Path(row['evidence_directory']) / 'result.json').is_file()
    assert json.loads((output / 'report.json').read_text()) == report
    assert report['counts']['skipped'] > 0
    with pytest.raises(FileExistsError):
        asyncio.run(cli.run_catalog(output_root=output, overrides=overrides))


def test_failing_parent_is_error_and_never_claims_tested(tmp_path, monkeypatch):
    from jiuwenswarm.research_rsi.targets import capsule_local_dispatcher
    class FailingParentDispatcher:
        def __init__(self, **kwargs):
            self.parent = b'parent body'
            self.parent_ref = kwargs['captures'].put_bytes(self.parent)
        async def evaluate(self, *args, **kwargs):
            return {'passed_count': 0, 'case_count': 1, 'rows': [{'task_success': False}]}
        async def benchmark(self, *args, **kwargs):
            raise AssertionError('Failing parent must not be benchmarked')
        def close(self):
            pass
    monkeypatch.setattr(capsule_local_dispatcher, 'LocalDispatcher', FailingParentDispatcher)
    monkeypatch.setattr(cli, 'local_grant', lambda *args: {'local_test_grant': True})
    result = asyncio.run(cli.run_baseline('utility.calculate', runtime_root=tmp_path,
        manifest={}, output_root=tmp_path / 'failed-parent'))
    assert result['status'] == 'error' and result['benchmark'] is None
    assert 'parent correctness' in result['reason']
    assert result['parent_correctness']['passed_count'] == 0


def test_declared_nonpacket_benchmark_inputs_remain_raw_and_deterministic():
    from jiuwenswarm.research_rsi.targets.capsule_benchmark import benchmark_fixtures, build_cases
    from jiuwenswarm.research_rsi.targets.capsules import fixture_inputs
    cases = benchmark_fixtures('utility.summary_to_packet')
    raw = cases[0]['packet']
    assert raw['id'] == 'paper_summary' and 'trust' not in raw and 'data' not in raw
    assert fixture_inputs('utility.summary_to_packet', cases[0]) == {'summary': raw}
    assert benchmark_fixtures('utility.summary_to_packet') == cases
    with pytest.raises(ValueError, match='TABLE_GENERATOR_REQUIRES_PACKET_INPUT'):
        build_cases([{'id': 'wrong-generator', 'table': {}}], split='visible', input_name='summary')
