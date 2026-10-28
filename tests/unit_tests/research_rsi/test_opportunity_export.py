"""Controlled export captures; never runtime security/model qualification."""
import asyncio
import base64
import hashlib
import json

import pytest

from jiuwenswarm.research_rsi.ports import JobPort
from jiuwenswarm.research_rsi.records import RecordStore, encoded


def fixture(tmp_path, *, valid=True, indexed=True, extra_capture=False):
    store=RecordStore(tmp_path)
    secret=store.put({'hidden_fixture':'must never be read/exported'})
    preparation=store.put({'private_worker_capture_ref':secret})
    review=store.put({'private_fixture_ref':secret})
    target=store.put({'unit':'target metadata'})
    configuration=store.put({'unit':'configuration'})
    parent={'cc_name':'unit.helper','cc_version':'1.0.0','declaration_sha256':'a'*64}
    session=store.put({'session_id':'unit:s','target_profile_ref':target,'parent':parent,'configuration_ref':configuration})
    prompt=store.put_bytes(b'Only independently approved visible context; no private fixture content.')
    diagnosis={'schema':'ai4r-rsi-diagnosis:1','observed_symptom':'unit visible symptom',
        'supporting_visible_evidence':[review],'suspected_mechanism':'unit hypothesis',
        'alternative_causes':['unit alternative'],'authorized_component':'helper.py',
        'proposed_change_direction':'unit bounded change','expected_effect':'unit hypothesis only',
        'visible_falsification_checks':['unit visible check'],'uncertainties':[]}
    # Identical response and canonical diagnosis bytes deliberately exercise
    # the two explicit roles of one exact artifact.
    response=store.put_bytes(encoded(diagnosis) if valid else b'controlled malformed response')
    diagnosis_ref=store.put(diagnosis) if valid else None
    model_input=store.put({'unit_model_input':'visible controlled bytes'})
    call=store.put({'evidence_refs':[model_input],'unit_only':'no actual model call'})
    captures={encoded(call):{'kind':'model-call','bytes':store.read(call)},
              encoded(model_input):{'kind':'model-call-input','bytes':store.read(model_input)}}
    capture={'schema':'ai4r-rsi-diagnosis-capture:1','target_profile_ref':target,'parent':parent,
        'configuration_ref':configuration,'preparation_ref':preparation,'prompt_ref':prompt,
        'response_ref':response,'diagnosis_ref':diagnosis_ref,'generation_evidence_refs':[call],
        'generating_model':'unit:controlled-model','model_calls':1,'unavailable_reasons':[],
        'status':'validated' if valid else 'invalid'}
    capture_ref=store.put(capture)
    alternate=store.put(dict(capture,unavailable_reasons=['different controlled capture'])) if extra_capture else None
    opportunity={'schema_version':'1.0.0','id':'unit:opportunity','target_profile_ref':target,'parent':parent,
        'trigger':'operator_selected','selected_by':'unit:operator','evidence_refs':[preparation,review,capture_ref]+([alternate] if alternate else []),
        'attribution':'implementation','symptom_reproduced':True,'parent_mandatory_passed':True,
        'headroom':.1,'headroom_minimum':.05,'diagnosis_ref':diagnosis_ref,
        'decision':'START' if valid else 'NEEDS_REVIEW','reason':'unit decision text must not enter inspect',
        'decided_at':'2026-10-25T00:00:00Z'}
    opportunity_ref=store.put(opportunity)
    if indexed:store.record_opportunity('unit:s',session,opportunity_ref,diagnosis_capture_ref=capture_ref)
    result={'session_ref':session,'attempt_refs':[],'referee_evidence_ref':None}
    result_ref=store.put(result)
    job={'id':'job_unit','sha256':'b'*64}
    store.claim_job(job);store.finish_job(job,{'state':'terminal','result':[result,result_ref]})
    reads=[]
    forbidden={encoded(pin) for pin in [secret,preparation,review]+([alternate] if alternate else [])}
    def public(pin):
        assert encoded(pin) not in forbidden,'Preparation/review/private evidence must not be followed'
        reads.append(pin)
        return store.read(pin)
    class Jobs:
        def resolve(self,ref):return {'session_ref':session}
    port=JobPort(Jobs(),store,allowed_refs=[job],public_reader=public,trace_reader=lambda pin:captures.get(encoded(pin)))
    return dict(store=store,port=port,job=job,session=session,opportunity=opportunity,
        opportunity_ref=opportunity_ref,capture=capture,capture_ref=capture_ref,diagnosis_ref=diagnosis_ref,
        response=response,prompt=prompt,call=call,model_input=model_input,captures=captures,reads=reads,
        alternate=alternate,forbidden=forbidden)


def test_inspection_exposes_only_indexed_decision_status_and_refs(tmp_path):
    f=fixture(tmp_path)
    try:
        value=asyncio.run(f['port'].inspect(f['job']))['opportunity']
        assert value=={'status':'captured','opportunity_ref':f['opportunity_ref'],'decision':'START',
            'diagnosis_ref':f['diagnosis_ref'],'diagnosis_capture_ref':f['capture_ref'],'diagnosis_status':'validated'}
        assert 'unit decision text' not in json.dumps(value)
        assert f['prompt'] not in f['reads'] and f['response'] not in f['reads']
    finally:f['store'].close()


def test_export_includes_typed_diagnosis_and_governed_closure_without_following_preparation(tmp_path):
    f=fixture(tmp_path,extra_capture=True)
    try:
        value=asyncio.run(f['port'].export(f['job']))
        rows=value['records'];by_kind={row['kind']:row for row in rows}
        for kind in ('rsi-opportunity','rsi-diagnosis-capture','rsi-diagnosis','rsi-diagnosis-prompt',
                     'rsi-diagnosis-response','model-call','model-call-input'):
            assert kind in by_kind
        assert by_kind['rsi-diagnosis']['ref']==by_kind['rsi-diagnosis-response']['ref']
        assert value['unavailable_trace_refs']==[] and value['unavailable_opportunity_evidence']==[]
        for row in rows:
            assert hashlib.sha256(base64.b64decode(row['bytes_base64'],validate=True)).hexdigest()==row['ref']['sha256']
            assert encoded(row['ref']) not in f['forbidden']
    finally:f['store'].close()


def test_malformed_bounded_response_remains_exportable_as_raw_response_not_diagnosis(tmp_path):
    f=fixture(tmp_path,valid=False)
    try:
        value=asyncio.run(f['port'].export(f['job']))
        kinds={row['kind'] for row in value['records']}
        assert {'rsi-opportunity','rsi-diagnosis-capture','rsi-diagnosis-response','model-call'}<=kinds
        assert 'rsi-diagnosis' not in kinds
        assert value['opportunity']['diagnosis_status']=='invalid'
        assert value['opportunity']['decision']=='NEEDS_REVIEW'
    finally:f['store'].close()


def test_unindexed_capture_is_unavailable_and_never_discovered_by_blob_scan(tmp_path):
    f=fixture(tmp_path,indexed=False)
    try:
        value=asyncio.run(f['port'].export(f['job']))
        assert value['opportunity']=={'status':'unavailable'}
        assert value['unavailable_opportunity_evidence']==['canonical_opportunity']
        assert not any(row['kind'].startswith('rsi-diagnosis') for row in value['records'])
        assert f['capture_ref'] not in f['reads']
    finally:f['store'].close()


def test_unindexed_opaque_historical_session_inspection_never_requires_original_body(tmp_path):
    store=RecordStore(tmp_path)
    session={'id':'opaque:unresolved-history','sha256':'d'*64}
    job={'id':'job_history','sha256':'e'*64}
    class Jobs:
        def resolve(self,ref):return {'session_ref':session}
    def forbidden_reader(ref):
        pytest.fail('Absent opportunity index must not resolve historical session body')
    try:
        port=JobPort(Jobs(),store,allowed_refs=[job],public_reader=forbidden_reader)
        assert asyncio.run(port.inspect(job))['opportunity']=={'status':'unavailable'}
    finally:store.close()


def test_historical_opportunity_without_typed_capture_reports_gap_without_guessing(tmp_path):
    f=fixture(tmp_path,indexed=False)
    try:
        f['store'].record_opportunity('unit:s',f['session'],f['opportunity_ref'])
        value=asyncio.run(f['port'].export(f['job']))
        kinds={row['kind'] for row in value['records']}
        assert {'rsi-opportunity','rsi-diagnosis'}<=kinds
        assert 'rsi-diagnosis-capture' not in kinds
        assert value['unavailable_opportunity_evidence']==['diagnosis_capture']
        assert f['capture_ref'] not in f['reads']
    finally:f['store'].close()


def test_private_typed_call_children_and_changed_exact_bytes_block_export(tmp_path):
    f=fixture(tmp_path)
    try:
        f['captures'][encoded(f['model_input'])]['kind']='private-worker-receipt'
        with pytest.raises(ValueError,match='Private or unknown'):
            asyncio.run(f['port'].export(f['job']))
        f['captures'][encoded(f['model_input'])]['kind']='model-call-input'
        f['captures'][encoded(f['model_input'])]['bytes']=b'changed controlled bytes'
        with pytest.raises(ValueError,match='bytes differ'):
            asyncio.run(f['port'].export(f['job']))
    finally:f['store'].close()


def test_capture_selection_cannot_change_and_survives_reopened_store(tmp_path):
    f=fixture(tmp_path,extra_capture=True)
    store=f['store']
    with pytest.raises(ValueError,match='immutable'):
        store.record_opportunity('unit:s',f['session'],f['opportunity_ref'],diagnosis_capture_ref=f['alternate'])
    store.close();store=RecordStore(tmp_path)
    try:
        assert store.opportunity_ref('unit:s',f['session'])==f['opportunity_ref']
        assert store.opportunity_capture_ref('unit:s',f['session'])==f['capture_ref']
        with pytest.raises(ValueError,match='binding'):
            store.opportunity_capture_ref('unit:s',dict(f['session'],sha256='c'*64))
    finally:store.close()


def test_diagnosis_export_does_not_truncate_an_oversized_response(tmp_path):
    f=fixture(tmp_path,indexed=False,valid=False)
    try:
        response=f['store'].put_bytes(b'x'*(64*1024+1))
        capture=dict(f['capture'],response_ref=response)
        capture_ref=f['store'].put(capture)
        opportunity=dict(f['opportunity'],evidence_refs=f['opportunity']['evidence_refs']+[capture_ref])
        opportunity_ref=f['store'].put(opportunity)
        f['store'].record_opportunity('unit:s',f['session'],opportunity_ref,diagnosis_capture_ref=capture_ref)
        with pytest.raises(ValueError,match='disclosure bound'):
            asyncio.run(f['port'].export(f['job']))
    finally:f['store'].close()
