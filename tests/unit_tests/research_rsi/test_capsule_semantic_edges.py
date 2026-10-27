"""Semantic edge cases as data reproduce Codex's supplementary oracle exactly."""
import json
from pathlib import Path

import pytest

from jiuwenswarm.research_rsi.targets.capsule_semantic_edges import (latest_version, semantic_edge_fixtures,
    semantic_parent_expectations, semantic_protocol)
from jiuwenswarm.research_rsi.targets.capsules import registered_capsule

EVIDENCE = Path(__file__).with_name('codex_evidence')


@pytest.mark.parametrize('name', ['utility.calculate', 'utility.table_normalize'])
def test_semantic_edges_from_data_match_codex_oracle_v2(name):
    oracle = next(row for row in json.loads((EVIDENCE / 'capsule-supplementary-parent-oracles-r2.json').read_text())['targets']
                  if row['capsule_name'] == name)
    assert latest_version(name) == 2
    assert semantic_parent_expectations(name, 2) == oracle
    assert registered_capsule(name).semantic_edge_case_count == len(semantic_edge_fixtures(name)) == 9
    v1 = semantic_edge_fixtures(name, 1)
    assert [case['id'] for case in v1] == [case['id'] for case in semantic_edge_fixtures(name)][:8]
    assert all(case['split'] == 'supplementary' for case in v1)
    assert semantic_protocol(name, 2)['fixture_sha256'] == oracle['fixture_sha256']
    with pytest.raises(ValueError):
        semantic_edge_fixtures(name, 3)
    # The parent's own checker discrepancies are recorded, never "fixed" by the oracle.
    discrepancies = {row['id'] for row in oracle['rows'] if row.get('baseline_checker_discrepancy')}
    assert discrepancies  # the checker remains authoritative where the parent fails it
