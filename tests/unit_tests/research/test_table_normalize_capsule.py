import hashlib
import json
from types import SimpleNamespace

import pytest

from jiuwenswarm.research.capsule_extensions.table_normalize.worker import execute, normalize
from jiuwenswarm.research.capsule_extensions.table_normalize.checks import check
from jiuwenswarm.research.contracts import ResearchError


def packet(text, format='csv', columns=None):
    return {'schema_version': '1.0.0', 'data': {'table_request': {'file': 'input', 'format': format,
        'columns': columns or ['name', 'value'], 'delimiter': ',' if format == 'csv' else None}},
        'files': [{'path': 'input', 'text': text, 'sha256': hashlib.sha256(text.encode()).hexdigest()}],
        'trust': 'low', 'provenance': [{'id': 'generalist', 'sha256': 'a' * 64}], 'limitations': ['uncertain input']}


@pytest.mark.asyncio
@pytest.mark.parametrize('value,expected', [(packet('name,value\r\n"a,b",002\r\n'), [['a,b', '002']]),
    (packet('[{"value":2,"name":"a"},{"name":"b","value":null}]', 'json'), [['a', 2], ['b', None]])])
async def test_source_values_types_order_and_low_trust_are_preserved(value, expected):
    output = await execute(None, {'packet': value})
    result = json.loads(output['result'].data)
    assert result['data']['table']['rows'] == expected
    assert result['trust'] == 'low' and result['files'] == value['files']
    ctx = SimpleNamespace(output_refs={})
    assert all(r['outcome'] == 'PASS' for r in check(ctx, {'packet': value}, {'result': result}))
    result['data']['table']['rows'][0][0] = 'tampered'
    assert check(ctx, {'packet': value}, {'result': result})[-1]['outcome'] == 'FAIL'


@pytest.mark.parametrize('value', [packet('name,value\na\n'), packet('name,value\na,1,2\n'),
    packet('wrong,value\na,1\n'), packet('[{"name":"a","name":"b","value":1}]', 'json'),
    packet('[{"name":"a","value":NaN}]', 'json'), packet('[{"name":"a","value":{}}]', 'json')])
def test_ambiguous_malformed_and_nonfinite_tables_fail(value):
    with pytest.raises(ResearchError): normalize(value)
