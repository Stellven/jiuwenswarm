"""Semantic edge cases as data reproduce Codex's supplementary oracle exactly."""
import json
from pathlib import Path

import pytest

from jiuwenswarm.research_rsi.targets.capsule_semantic_edges import (latest_version, semantic_edge_fixtures,
    semantic_parent_expectations, semantic_protocol)
from jiuwenswarm.research_rsi.targets.capsules import registered_capsule

EVIDENCE = Path(__file__).with_name('codex_evidence')


@pytest.mark.parametrize('name', ['utility.calculate', 'utility.table_normalize'])
def test_semantic_edges_bind_current_selected_contract_and_keep_historical_oracle(name):
    oracle = next(row for row in json.loads((EVIDENCE / 'capsule-supplementary-parent-oracles-r2.json').read_text())['targets']
                  if row['capsule_name'] == name)
    version = latest_version(name)
    assert version >= 2
    current = semantic_parent_expectations(name)
    assert len(current['rows']) == registered_capsule(name).semantic_edge_case_count == len(semantic_edge_fixtures(name))
    for case, row in zip(semantic_edge_fixtures(name), current['rows']):
        if case['malformed']:
            assert 'error' in row, case['id']
        else:
            assert row['baseline_checker_discrepancy'] == any(check['outcome'] != 'PASS' for check in row['original_checks'])
            assert {check['check_id'] for check in row['original_checks']} == set(registered_capsule(name).check_ids)
    v1 = semantic_edge_fixtures(name, 1)
    assert [case['id'] for case in v1] == [case['id'] for case in semantic_edge_fixtures(name)][:8]
    assert all(case['split'] == 'supplementary' for case in v1)
    assert semantic_protocol(name)['fixture_sha256'] == current['fixture_sha256']
    assert oracle['schema'].startswith('ai4r-rsi-supplementary-parent-expectations:')
    with pytest.raises(ValueError):
        semantic_edge_fixtures(name, version + 1)
    # The parent's own checker discrepancies are recorded, never "fixed" by the oracle.
    discrepancies = {row['id'] for row in oracle['rows'] if row.get('baseline_checker_discrepancy')}
    assert discrepancies  # the checker remains authoritative where the parent fails it


def test_semantic_parent_oracle_uses_the_selected_nonpacket_input(monkeypatch):
    from jiuwenswarm.research_rsi.targets import capsule_semantic_edges as edges
    from jiuwenswarm.research_rsi.targets.capsules import public_fixtures
    summary = public_fixtures('utility.summary_to_packet')[0]['packet']
    spec = {'schema': edges.SPEC_SCHEMA, 'capsule_name': 'utility.summary_to_packet',
            'input_name': 'summary', 'cases': [{'id': 'declared-summary-input', 'data': summary}]}
    monkeypatch.setattr(edges, 'semantic_edges_spec', lambda name: spec)
    actual = edges.semantic_parent_expectations('utility.summary_to_packet')
    assert actual['rows'][0]['baseline_checker_discrepancy'] is False
    assert edges.semantic_edge_fixtures('utility.summary_to_packet')[0]['packet'] == summary
    spec['input_name'] = 'packet'
    with pytest.raises(ValueError, match='SEMANTIC_INPUT_DIFFERS_FROM_SELECTED_DECLARATION'):
        edges.semantic_edge_fixtures('utility.summary_to_packet')
