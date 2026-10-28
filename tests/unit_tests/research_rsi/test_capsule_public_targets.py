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
