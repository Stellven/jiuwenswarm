"""Executor-side code receives CustodyStore, not SQLiteRunStore; every store method it calls must exist there.

Unit fixtures use the real SQLite store directly, which hid missing proxy methods
(iter_records, record_ref) until a live Builder run.
"""
import ast
from pathlib import Path

import pytest

from jiuwenswarm.research.store_custody import CustodyStore

ROOT = Path(__file__).resolve().parents[3] / 'jiuwenswarm' / 'research'
EXECUTOR_SIDE = ('builder_agent_host', 'builder_agent_service', 'builder_agent_runtime', 'builder_testing',
                 'builder_launcher', 'builder_qualification', 'executor', 'executor_rpc', 'executor_bootstrap',
                 'evaluation_executor', 'execution_jobs', 'hardware', 'science_registration', 'science_start',
                 'trusted_scoring', 'trusted_pi', 'process_evidence', 'pi_protocol')


def _store_methods(path):
    tree = ast.parse(path.read_text('utf-8'))
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, (ast.Name, ast.Attribute)):
            owner = node.value.id if isinstance(node.value, ast.Name) else node.value.attr
            if owner in {'store', '_store'}:
                yield node.attr, node.lineno


@pytest.mark.parametrize('module', EXECUTOR_SIDE)
def test_executor_side_store_calls_exist_on_custody_proxy(module):
    path = ROOT / (module + '.py')
    if not path.exists():
        pytest.skip('module absent')
    missing = sorted({(name, line) for name, line in _store_methods(path) if not hasattr(CustodyStore, name)})
    assert not missing, f'{module} uses store attributes CustodyStore lacks: {missing}'
