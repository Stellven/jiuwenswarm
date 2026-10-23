"""Optional combined-branch checks; these are evaluator trials, not admission."""
import copy
import hashlib
import json
from contextlib import closing

import pytest

from jiuwenswarm.research.capsule_extensions.catalog import candidates
from jiuwenswarm.research.checks import CheckContext, CheckRegistry
from jiuwenswarm.research.state import SQLiteRunStore


@pytest.mark.asyncio
async def test_actual_utility_pipeline_checked_artifacts_and_retained_input(tmp_path):
    text = 'item,value\na,2\nb,4\n'
    packet = {'schema_version': '1.0.0', 'data': {
        'table_request': {'file': 'input.csv', 'format': 'csv', 'columns': ['item', 'value'], 'delimiter': ','},
        'calculation': {'columns': ['value'], 'operations': ['count', 'sum', 'mean'], 'numeric_mode': 'decimal_strings'},
        'report': {'path': 'report.md', 'title': 'Trial', 'sections': [], 'data_keys': ['calculation_result']}},
        'files': [{'path': 'input.csv', 'text': text, 'sha256': hashlib.sha256(text.encode()).hexdigest()}],
        'trust': 'low', 'provenance': [], 'limitations': ['Synthetic test input, not a research conclusion']}
    original = copy.deepcopy(packet)
    with closing(SQLiteRunStore(tmp_path)) as store:
        assets = candidates(store)
        registry = CheckRegistry()
        for name in ['utility.table_normalize', 'utility.calculate', 'utility.markdown_report']:
            asset, module = assets[name]
            output = (await module.execute(None, {'packet': packet}))['result']
            result = json.loads(output.data)
            ref = store.put_blob(output.data, media_type=output.media_type)
            bundle = store.read_record(asset['bundle_ref'])
            ids = [c['check_id'] for c in bundle['checks']]
            registry.register_bundle(bundle['bundle_id'], ids, module.check,
                implementation_ref=asset['runner_ref'], profile_ref=asset['profile_ref'])
            plan = {'runner_refs': [asset['runner_ref']], 'profile_ref': asset['profile_ref'], 'mandatory_deterministic': ids}
            context = CheckContext({}, store, {'packet': packet}, {'result': result}, {'result': ref}, {})
            checked = await registry.run(plan, context, bundle_id=bundle['bundle_id'])
            assert all(r['outcome'] == 'PASS' for r in checked)
            packet = result
        assert original['files'][0]['text'] == text
        assert packet['files'][0] == original['files'][0]
        assert packet['data']['calculation_result']['columns']['value'] == {'count': 2, 'sum': '6', 'mean': '3'}
        assert packet['files'][-1]['path'] == 'report.md'
        assert 'Trust: low' in packet['files'][-1]['text']
        assert packet['data']['report_manifest']['input_files'][0]['sha256'] == original['files'][0]['sha256']
        assert packet['trust'] == 'low'
