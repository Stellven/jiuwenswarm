"""Captured cache family selection and unfavorable scientific results remain honest."""
import asyncio
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from jiuwenswarm.research.cache_protocol import PROTOCOL,parse_cache_dataset,recompute_cache_results
from jiuwenswarm.research.capsules import hypothesis
from jiuwenswarm.research.capsules.builder_agent import _public_task
from jiuwenswarm.research.metric_contract import metric_protocol,protocol_for_resource,validate_metric_declarations
from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.science import classify_metric


def public_data():
    return {'capacity_entries':1,'replacement':'LRU','traces':{'thrash':['a','b','a','b']},
            'units':{'hits':'requests','misses':'requests','miss_ratio':'fraction'},'source_id':'synthetic-study'}


def test_cache_family_selected_from_captured_bytes_and_bound_in_hypothesis(monkeypatch):
    raw=json.dumps(public_data()).encode()
    ref={'id':'public','sha256':'a'*64}
    resource={'availability':'available','environment_ref':ref,'files':[{'path':'data.json','artifact_ref':ref}]}
    assert protocol_for_resource(resource,lambda _:raw)==PROTOCOL
    assert protocol_for_resource({'files':[]},lambda _:raw) is None
    fixture=Path(hypothesis.__file__).parents[1]/'resources/calibration/hypothesis_blueprint.json'
    reply=json.loads(fixture.read_bytes())
    reply.pop('ext',None)
    reply.pop('dependent_variables')
    reply['metrics']=[dict(metric_protocol(PROTOCOL)['metrics'][0],aggregation='median',target_id=None)]
    reply['outcome_rules']=[dict(reply['outcome_rules'][0],metric_id='miss_ratio')]
    async def answer(*args,**kwargs):
        assert args[3]['measurement_protocol']==metric_protocol(PROTOCOL)
        assert kwargs['reply_schema']['properties']['metrics']['prefixItems'][0]['properties']['metric_id']=={'const':'miss_ratio'}
        assert len(json.dumps(kwargs['reply_schema']).encode()) < 8192
        assert 'MetricDeclaration' not in kwargs['reply_schema'].get('$defs',{})
        return copy.deepcopy(reply)
    monkeypatch.setattr(hypothesis,'ask',answer)
    ctx=SimpleNamespace(store=SimpleNamespace(read_blob=lambda _:raw),input_ref=lambda _:ref)
    result=asyncio.run(hypothesis.execute(ctx,{'baseline_resource':resource,'validation_resource':resource}))
    assert json.loads(result['blueprint'].data)['dependent_variables']==['miss_ratio']
    with pytest.raises(ResearchError):validate_metric_declarations(reply['metrics'])


def test_cache_builder_context_and_unfavorable_result_do_not_become_success():
    public=public_data()
    task=_public_task({'blueprint':{},'lock':{}},public,cache=True)
    assert task['contract']['interface']=='simulate_cache(data)'
    assert task['contract']['protocol']==PROTOCOL
    assert task['public_validation']==public
    counts=recompute_cache_results(parse_cache_dataset(json.dumps(public).encode()))['thrash']
    assert counts=={'hits':0,'misses':4,'unbounded_misses':2}
    rule={'metric_id':'miss_ratio','success':{'operand':'treatment','comparator':'lt','reference':'baseline','factor':1,'offset':0},
          'falsification':{'operand':'treatment','comparator':'ge','reference':'baseline','factor':1,'offset':0},
          'middle':'INCONCLUSIVE','conditional_rule':None,'conditional_meaning':None}
    assert classify_metric(counts['unbounded_misses']/4,counts['misses']/4,rule)[0]=='FAIL'

def test_delivery_reads_bound_artifacts_without_host_record_api(monkeypatch):
    import hashlib
    from jiuwenswarm.research.capsules import delivery
    from tests.unit_tests.research.test_delivery_content import DeliveryContentTests,SOURCE
    inputs,refs,_,_=DeliveryContentTests().fixture()
    inputs['run_configuration']=json.loads((SOURCE/'run_configuration.json').read_bytes())
    score={'schema':'ai4r-cache-scoring-receipt:1','source_id':'synthetic-study','status':'scored',
           'role':'treatment','repeat_index':0,'unit':'requests',
           'observations':{'thrash':{'hits':0,'misses':4,'unbounded_misses':2}}}
    raw=json.dumps(score).encode()
    score_ref={'id':'synthetic-cache-score','sha256':hashlib.sha256(raw).hexdigest()}
    blobs={score_ref['id']:raw}
    inputs['benchmark_payload']['raw_evidence_refs']=[score_ref]
    def read(ref):
        return blobs[ref['id']] if ref['id'] in blobs else (SOURCE/ref['id']).read_bytes()
    def put(raw,**kwargs):
        digest=hashlib.sha256(raw).hexdigest()
        ref={'id':'blob:'+digest,'sha256':digest}
        blobs[ref['id']]=raw
        return ref
    async def answer(*args,**kwargs):
        return dict(title='Synthetic negative cache study',objective='Exercise delivery.',
                    opportunity_and_citations='Preserve supplied citations.',method_and_poc='Synthetic cache test.')
    monkeypatch.setattr(delivery,'ask',answer)
    ctx=SimpleNamespace(store=SimpleNamespace(read_blob=read,put_blob=put),input_ref=lambda name:refs[name])
    result=asyncio.run(delivery.execute(ctx,inputs))
    report=result['research_report'].data.decode()
    assert 'Classification: FAIL' in report
    assert 'Source IDs: synthetic-study' in report
    assert 'LRU misses=4, unbounded misses=2 requests' in report
    assert 'do not establish elapsed-time speedup' in report
