"""Regression: value equality must not conceal changes in JSON primitive types."""
import copy
import hashlib
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from jiuwenswarm.research.capsule_extensions.catalog import candidates
from jiuwenswarm.research.checks.admission import declaration_checks
from jiuwenswarm.research.contracts import validate
from jiuwenswarm.research.state import SQLiteRunStore


@pytest.mark.asyncio
async def test_legacy_false_accepts_remain_reproducible_and_typed_candidates_reject():
    def packet(data, files=()):
        return {'schema_version': '1.0.0', 'data': data, 'files': list(files),
                'trust': 'low', 'provenance': [], 'limitations': []}
    text = '[{"value":1}]'
    values = [('table_normalize', packet({'table_request': {'file': 'source', 'format': 'json',
        'columns': ['value'], 'delimiter': None}}, [{'path': 'source', 'text': text,
            'sha256': hashlib.sha256(text.encode()).hexdigest()}])),
        ('calculate', packet({'table': {'columns': ['v'], 'rows': [['1']]},
            'calculation': {'columns': ['v'], 'operations': ['count', 'sum'], 'numeric_mode': 'decimal_strings'}})),
        ('markdown_report', packet({'values': [0], 'report': {'path': 'report.md', 'title': 'Report',
            'sections': [], 'data_keys': ['values']}}))]
    for module, source in values:
        package = 'jiuwenswarm.research.capsule_extensions.'
        worker = importlib.import_module(package + module + '.worker')
        legacy = importlib.import_module(package + module + '_v2.checks')
        typed = importlib.import_module(package + module + '_typed.checks')
        output = json.loads((await worker.execute(None, {'packet': source}))['result'].data)
        ctx = SimpleNamespace(output_refs={})
        assert all(r['outcome'] == 'PASS' for r in typed.check(ctx, {'packet': source}, {'result': output}))
        value = copy.deepcopy(output)
        if module == 'table_normalize':
            value['data']['table']['rows'][0][0] = True
        elif module == 'calculate':
            value['data']['calculation_result']['columns']['v']['count'] = True
        else:
            value['data']['values'][0] = False
        assert all(r['outcome'] == 'PASS' for r in legacy.check(ctx, {'packet': source}, {'result': value}))
        assert any(r['outcome'] == 'FAIL' for r in typed.check(ctx, {'packet': source}, {'result': value}))


def test_optional_candidates_have_immutable_complete_closures(tmp_path):
    store = SQLiteRunStore(tmp_path / 'store')
    try:
        values = candidates(store)
        for name in ('table_normalize', 'calculate', 'markdown_report'):
            asset, module = values['utility.' + name + '_typed']
            declaration = store.read_record(asset['declaration_ref'], contract_id='capsule-declaration')
            validate('capsule-declaration', declaration)
            assert declaration['identity']['version_label'] == 'm1-1'
            assert all(row['outcome'] == 'PASS' for row in declaration_checks(
                declaration, {key: store.read_blob(ref) for key, ref in asset['body_refs'].items()}))
            assert 'capsule_extensions/typed_values.py' in asset['dependency_refs']
    finally:
        store.close()
