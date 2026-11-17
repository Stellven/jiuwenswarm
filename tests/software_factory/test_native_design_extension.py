import copy
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from test_interconnect import connected

from jiuwenswarm.software_factory.cc_service import CCService, binding_map
from jiuwenswarm.factory.throughput_campaign import judge


def test_shared_catalog_exposes_components_and_real_connected_scopes(connected):
    runtime,registry,host,caps=connected
    service=CCService(runtime,registry)
    run=service.create(dict(workflow='connected',inputs={'request':{}},objective='Exercise connected components'))
    for _ in range(10):
        run=service.tick(run['id'])
        if run['status']=='completed':break
    assert run['status']=='completed' and run['scopes']
    schema=json.loads((Path(__file__).parents[2]/'jiuwenswarm/software_factory/shared-capability.schema.json').read_text())
    pool=service.shared_pool()
    Draft202012Validator(schema).validate(pool)
    assert any(entry['kind']=='composite' for entry in pool['entries'])
    assert any(entry.get('execution_profile',{}).get('lifecycle') for entry in pool['entries'])
    assert binding_map({'x':{'node':'producer','port':'output'}})['x'].source=='producer'


def suite_cell(arm,rate):
    rows=[]
    for index in range(4):
        rows.append(dict(ids=[index,10],finish='length',decode_tps=rate,generated_tokens=2,decode_ms=2000/rate))
    return dict(arm=arm,placement={'layers':'fixed'},requests=rows)


def test_suite_judge_preserves_each_case_and_uses_total_tokens_over_time():
    cells=[suite_cell('A',10),suite_cell('B',12),suite_cell('B',12),suite_cell('A',10)]
    result=judge('confirm',cells,.1,.05,suite=True)
    assert result['verdict']=='target_met' and result['measured_cases']==3
    assert result['baseline_tokens_s']==10 and result['candidate_tokens_s']==12
    changed=copy.deepcopy(cells);changed[1]['requests'][2]['ids']=[999]
    assert judge('confirm',changed,.1,.05,suite=True)['verdict']=='inconclusive'
    changed=copy.deepcopy(cells)
    for cell in changed:
        if cell['arm']=='B':cell['requests'][2].update(decode_tps=9,decode_ms=2000/9)
    assert not judge('confirm',changed,.1,.05,suite=True)['gates']['suite_case_regression_bound']


def test_paired_warmup_suite_excludes_all_three_warmups():
    cells=[]
    for arm,rate in [('A',10),('B',12),('B',12),('A',10)]:
        cell=suite_cell(arm,rate)
        measured=copy.deepcopy(cell['requests'][1:])
        cell['requests']=copy.deepcopy(measured)+measured
        for row in cell['requests'][:3]:row.update(decode_ms=999999,decode_tps=.001)
        cells.append(cell)
    report=judge('confirm',cells,.1,.05,suite=True,warmup_requests=3)
    assert report['verdict']=='target_met' and report['warmup_requests']==3
    assert report['baseline_tokens_s']==10 and report['candidate_tokens_s']==12
    changed=copy.deepcopy(cells)
    for cell in changed:cell['requests'][0]['ids']=[999]
    assert judge('confirm',changed,.1,.05,suite=True,warmup_requests=3)['verdict']=='inconclusive'


def test_history_report_payload_is_verified_and_not_silently_truncated(tmp_path):
    from jiuwenswarm.factory.store import Store
    from jiuwenswarm.factory.experiment_library import ExperimentLibrary
    home=tmp_path/'factory'
    with Store(home) as store:
        store.create_task(dict(task_id='history',objective='Report discovery check',constraints={},allowed_effects=[]))
        text='Report context '+('x'*8000)+' final source identity'
        metadata=store.put_artifact('history','final-report',text.encode(),'text/markdown',None)
    library=ExperimentLibrary(tmp_path/'index',[home/'factory.sqlite'])
    matches=library.search('final source identity',20)['matches']
    report=next(item for item in matches if item['table']=='artifacts')
    value=json.loads(library.read(report['id'],limit=24000)['text'])
    assert value['text']==text and value['text_complete'] and value['preview_status']=='verified_text'
    path=home/metadata['location'];path.write_bytes(b'changed')
    library.refresh()
    record=library._artifact(home/'factory.sqlite',metadata)
    assert record['preview_status']=='unavailable_or_changed' and 'text' not in record
    outside={**metadata,'location':str(tmp_path/'outside')}
    assert 'text' not in library._artifact(home/'factory.sqlite',outside)
