"""Installed C008 static release pins and unchanged overall source ceilings."""
import pytest

from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.planning import capture_static_template
from tests.unit_tests.research.test_budget_ceiling import installed_library


@pytest.mark.asyncio
async def test_authored_release_pins_current_workers_and_reserves_all_output_reviews(tmp_path):
    store, _, _, library, _, _ = await installed_library(tmp_path, scientific=True, scientific_memory=32768)
    ref = capture_static_template(store, library)
    assert capture_static_template(store, library) == ref
    value = store.read_record(ref, contract_id='static-template')
    entries = {entry['cc_name']: entry for entry in store.read_record(library.snapshot())['entries']}
    assert value['limits'] == {'time_s': 7200, 'model_calls': 60, 'memory_mb': 16384}
    assert len(value['nodes']) == 7
    for node in value['nodes']:
        entry = entries[node['cc']['cc_name']]
        assert node['cc'] == {key: entry[key] for key in ('cc_name', 'cc_version', 'declaration_sha256')}
        assert node['limits']['time_s'] == entry['max_limits']['time_s']
        assert node['limits']['model_calls'] == entry['max_limits']['model_calls']
        assert node['limits']['memory_mb'] <= entry['max_limits']['memory_mb']
    assert sum(node['limits']['time_s'] for node in value['nodes']) <= 7200
    assert sum(node['limits']['model_calls'] for node in value['nodes']) <= 60
    assert next(node for node in value['nodes'] if node['cc']['cc_name'] == 'research.benchmark')['limits']['model_calls'] == 3
    with pytest.raises(ResearchError, match='static_template_pin'):
        capture_static_template(store, library, expected_ref={'id': 'old-template', 'sha256': 'a' * 64})
