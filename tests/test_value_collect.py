import json

from benchmarks.harbor_suite.value_collect import offline
from benchmarks.harbor_suite.value_data import Dataset
from benchmarks.harbor_suite.value_report import render


def test_retain_original_bytes_and_unrun_denominator(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    rows = [{'id': 'utility/task', 'arm': 'ordinary_python_helper', 'status': 'observed',
             'grade': {'content_correct': True, 'productive_completion': True}},
            {'id': 'research/task', 'status': 'not_run'}]
    raw = b''.join((json.dumps(r) + '\r\n').encode() for r in rows)
    (source / 'observations.jsonl').write_bytes(raw)
    (source / 'summary.json').write_text(json.dumps({'schema': 'ai4r-value-offline-observation:1',
        'rows': 2, 'model_calls': 0, 'source_changed': [], 'quality_credit_valid': True}))
    record = offline(tmp_path / 'dataset', source)
    assert record['value']['rows'][0]['correct'] is True
    assert record['value']['rows'][1]['correct'] is None
    data = Dataset(tmp_path / 'dataset')
    retained = json.loads((data.root / record['value']['source']['path']).read_bytes())
    assert retained['original_text'].encode() == raw
    result = render(data.root, tmp_path / 'report', charts=False)
    assert result['rows'] == 2
    text = (tmp_path / 'report' / 'report.md').read_text('utf-8')
    assert 'Matched ordinary helpers' in text and '1/1' in text
    assert 'not a native JiuwenSwarm' in text
