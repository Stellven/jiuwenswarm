from tests.unit_tests.research_rsi.qualification_fixtures import ControlledQualification
"""Private original-parent controls; unit assets do not qualify live RSI."""
import base64
import copy
import hashlib
from types import SimpleNamespace
import pytest
from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.state import json_bytes
from tests.unit_tests.research.test_admitted_measurement import adapter_fixture


async def parent_fixture(root):
    from jiuwenswarm.research.parent_measurement import ParentMeasurement
    store,admitted,contract_ref,plan_ref,fixture=await adapter_fixture(root)
    resources=admitted.resources;settings=resources.operator.snapshot()
    settings['rsi']={'custodian_public_key':base64.urlsafe_b64encode(fixture['signer'].public_bytes()).decode().rstrip('='),'custodian_key_id':fixture['signer'].key_id}
    resources.operator=SimpleNamespace(snapshot=lambda:copy.deepcopy(settings))
    resources.composition.library.rsi_security_guard=ControlledQualification()
    contract=store.read_record(contract_ref);parent=store.read_record(contract['node_contract_ref'])
    binding={'schema':'ai4r-admitted-measurement-binding:1','id':'parent-unit','session_ref':fixture['put'](fixture['session']),
        'target_ref':fixture['package']['target_profile_ref'],'parent_admission_ref':contract['bindings'][0]['admission_ref'],
        'parent_declaration_ref':contract['bindings'][0]['declaration_ref'],'parent_contract_ref':contract_ref,'parent_check_plan_ref':plan_ref,
        **{k:resources.exact_binding_refs[k] for k in ('configuration_ref','model_selection_profile_ref','deployment_ref')},
        'inputs':[{k:p[k] for k in ('name','contract_id','artifact_refs')} for p in contract['inputs']],
        'limits':copy.deepcopy(parent['node_limits']),'phase':'development','repeat_index':0}
    reservation={'schema':'ai4r-rsi-parent-reservation:1','id':'parent-unit-reservation',
        **{k:binding[k] for k in ('session_ref','target_ref','parent_declaration_ref','configuration_ref','phase','repeat_index')},
        'inputs_sha256':hashlib.sha256(json_bytes(binding['inputs'])).hexdigest(),'action_id':'paired-unit-action',
        'charge_kind':'development','queries_used':0,'queries_left':30}
    binding['reservation_ref']=fixture['put'](fixture['signer'].sign(reservation))
    return store,ParentMeasurement(resources,admitted=admitted),fixture,binding


@pytest.mark.asyncio
async def test_original_parent_is_canonical_and_never_fabricates_child_or_acceptance(tmp_path):
    store,owner,fixture,binding=await parent_fixture(tmp_path)
    counts={table:store.connection.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] for table in ('library_versions','acceptance')}
    authority=[r['ref'] for r in store.iter_records(kinds=('library-admission','activation-record','library-snapshot','gate-decision'))]
    request=fixture['put'](binding);grant=owner.prepare_admitted_measurement(request)
    assert owner.prepare_admitted_measurement(request)==grant
    value=store.read_record(grant);actual=store.read_record(value['contract_ref'])
    assert value['accepted'] is False and 'child_declaration_ref' not in value
    assert actual['bindings'][0]['declaration_ref']==binding['parent_declaration_ref']
    result_ref=await owner.execute_admitted_measurement(grant);result=store.read_record(result_ref)
    assert result['accepted'] is False and result['status'] in {'failed','blocked'}
    measured=store.read_record(result['measurement_ref'])
    assert measured['accepted'] is False and measured['contract_ref']==value['contract_ref']
    assert await owner.execute_admitted_measurement(grant)==result_ref
    assert counts=={table:store.connection.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] for table in counts}
    assert authority==[r['ref'] for r in store.iter_records(kinds=('library-admission','activation-record','library-snapshot','gate-decision'))]


@pytest.mark.asyncio
@pytest.mark.parametrize('fault',['signature','repeat','configuration','input','limits','child_field','parent_admission'])
async def test_parent_reservation_and_canonical_pins_reject_before_effects(tmp_path,fault):
    store,owner,fixture,binding=await parent_fixture(tmp_path)
    if fault=='signature':
        value=store.read_record(binding['reservation_ref']);value['action_id']='swapped';binding['reservation_ref']=fixture['put'](value)
    elif fault=='repeat':binding['repeat_index']=3
    elif fault=='configuration':binding['configuration_ref']=binding['target_ref']
    elif fault=='input':binding['inputs'][0]['artifact_refs']=[binding['parent_declaration_ref']]
    elif fault=='limits':binding['limits']['model_calls']=100
    elif fault=='child_field':binding['child_declaration_ref']=binding['parent_declaration_ref']
    else:binding['parent_admission_ref']=binding['target_ref']
    with pytest.raises(ResearchError):owner.prepare_admitted_measurement(fixture['put'](binding))
    assert not list(store.iter_records(kinds=('parent-reservation-claim','model-call','admitted-parent-grant')))


@pytest.mark.asyncio
async def test_v2_parent_derives_its_original_rubric_from_admitted_body(tmp_path):
    store,owner,fixture,binding=await parent_fixture(tmp_path)
    binding['schema']='ai4r-admitted-measurement-binding:2'
    binding['inputs']=[p for p in binding['inputs'] if p['name']!='screening_rubric']
    reservation=store.read_record(binding['reservation_ref']);reservation.update(schema='ai4r-rsi-parent-reservation:2',inputs_sha256=hashlib.sha256(json_bytes(binding['inputs'])).hexdigest())
    binding['reservation_ref']=fixture['put'](fixture['signer'].sign(reservation))
    grant=owner.prepare_admitted_measurement(fixture['put'](binding));value=store.read_record(grant)
    actual=store.read_record(value['contract_ref']);parent=store.read_record(binding['parent_declaration_ref'])
    row=owner.library.get(parent['identity']['name'],parent['identity']['version_label'])
    assert [p['name'] for p in actual['inputs']]==['brief','candidate_set','screening_rubric']
    assert actual['inputs'][-1]['artifact_refs']==[row['body_refs']['screening_rubric.json']]
