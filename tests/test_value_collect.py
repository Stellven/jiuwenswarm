import json

from benchmarks.harbor_suite.value_collect import native, offline
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
    data.append('health', {'summary': 'Current qualification blocker remains visible'})
    retained = json.loads((data.root / record['value']['source']['path']).read_bytes())
    assert retained['original_text'].encode() == raw
    result = render(data.root, tmp_path / 'report', selected_records=[record['id']], charts=False)
    assert result['rows'] == 2
    text = (tmp_path / 'report' / 'report.md').read_text('utf-8')
    assert 'Matched ordinary helpers' in text and '1/1' in text
    assert 'not a native JiuwenSwarm' in text
    assert 'Current qualification blocker remains visible' in text


def test_native_identity_requires_exact_broker_request_join(tmp_path):
    from benchmarks.harbor_suite.value_cases import bank
    from benchmarks.harbor_suite.contracts import canonical
    case = bank()[0]
    source = tmp_path / 'native'
    (source / 'project').mkdir(parents=True)
    (source / 'evidence').mkdir()
    broker = tmp_path / 'broker'
    broker.mkdir()
    (source / 'project/task.json').write_bytes(canonical(case['task']))
    (source / 'result.json').write_text(json.dumps({'status': 'completed', 'variant': 'native-skills',
        'model_calls': 1, 'selected_tool_calls': 0}))
    packet = {'messages': [{'role': 'user', 'content': 'public task'}], 'tools': []}
    response = {'request_id': 'a' * 32, 'status': 'completed', 'identity': {'effective': 'gpt-6.1-sol'},
                'reasoning_effort': 'medium', 'text': 'answer'}
    (source / 'evidence/completion-001-request.json').write_bytes(canonical(packet))
    (source / 'evidence/completion-001-response.json').write_bytes(canonical(response))
    (broker / ('a' * 32 + '.response.json')).write_bytes(canonical(response))
    request = {'request_id': 'a' * 32, 'model': 'gpt-6.1-sol', 'reasoning_effort': 'medium',
               'prompt': 'wire instructions\n' + json.dumps(packet)}
    path = broker / ('a' * 32 + '.request.json')
    path.write_bytes(canonical(request))
    result = native(tmp_path / 'data', source, case_id=case['task']['id'], image='fixture-image', broker=broker)
    assert result['value']['rows'][0]['model_and_effort_verified'] is True
    assert result['value']['rows'][0]['correct'] is None
    request['prompt'] = 'instructions\n' + json.dumps({'messages': [], 'tools': []})
    path.write_bytes(canonical(request))
    result = native(tmp_path / 'different-data', source, case_id=case['task']['id'], image='fixture-image', broker=broker)
    assert result['value']['rows'][0]['model_and_effort_verified'] is False
