"""Finite timing authorizations; controlled identities confer no RSI qualification."""
import copy
import hashlib
import pytest
from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.state import SQLiteRunStore,json_bytes


def context(tmp_path):
    store=SQLiteRunStore(tmp_path);ref=store.put_blob(b'controlled exact subject')
    inputs=[{'name':name,'contract_id':'test','artifact_refs':[ref]} for name in ('brief','candidate_set')]
    body=store.put_blob(b'{"controlled":"rubric"}')
    declaration=store.put_blob(json_bytes({'identity':{'body':[{'path':'screening_rubric.json','sha256':body['sha256']}]}}))
    target={'scoring':{'batch_iterations':2,'warmup_batches':5,'paired_rounds':7}}
    session={'pass_count_repeats':3}
    binding={'schema':'ai4r-isolated-evaluation-binding:2','session_ref':ref,'target_ref':ref,'child_declaration_ref':declaration,
        'child_body_refs':{'screening_rubric.json':body},'configuration_ref':ref,'inputs':inputs,'phase':'hidden_final','repeat_index':2}
    record={'schema':'ai4r-rsi-trial-reservation:3',**{k:binding[k] for k in ('session_ref','target_ref','child_declaration_ref','configuration_ref','phase','repeat_index')},
        'inputs_sha256':hashlib.sha256(json_bytes(inputs)).hexdigest(),'action_id':'charged-final-action','charge_kind':'final',
        'queries_used':3,'queries_left':27,'signer_key_id':'explicit-unit-key','signature':'explicit-unit-signature'}
    return store,binding,record,target,session,body


@pytest.mark.parametrize('slot',[('score',),('warmup',0,0),('warmup',4,1),('paired',0,0),('paired',6,1)])
def test_slot_identity_is_deterministic_and_bounded_by_exact_frozen_context(tmp_path,slot):
    from jiuwenswarm.research.measurement_slots import reservation_id,parse_slot
    _,binding,record,target,session,_=context(tmp_path)
    record['id']=reservation_id(record,slot)
    assert parse_slot(record,binding,target,session)==slot
    changed=dict(record,queries_used=4,queries_left=26,signer_key_id='other-unit-key')
    assert reservation_id(changed,slot)==record['id']


@pytest.mark.parametrize('fault',['digest','leading_zero','warmup_range','paired_range','iteration','phase','repeat','version'])
def test_slots_reject_noncanonical_unbounded_or_unsealed_requests(tmp_path,fault):
    from jiuwenswarm.research.measurement_slots import reservation_id,parse_slot
    _,binding,record,target,session,_=context(tmp_path);record['id']=reservation_id(record,('warmup',0,0))
    if fault=='digest':record['action_id']='another-charge'
    elif fault=='leading_zero':record['id']=record['id'].removesuffix(':0:0')+':00:0'
    elif fault=='warmup_range':record['id']=record['id'].removesuffix(':0:0')+':5:0'
    elif fault=='paired_range':record['id']=record['id'].split(':warmup:')[0]+':paired:7:0'
    elif fault=='iteration':record['id']=record['id'].removesuffix(':0:0')+':0:2'
    elif fault=='phase':binding['phase']=record['phase']='hidden_loop';record['id']=reservation_id(record,('warmup',0,0))
    elif fault=='repeat':session['pass_count_repeats']=1
    else:binding['schema']='ai4r-isolated-evaluation-binding:1'
    with pytest.raises(ResearchError):parse_slot(record,binding,target,session)


@pytest.mark.parametrize('first_version,second_version',[(1,2),(2,1),(2,3),(3,2)])
def test_score_claim_normalizes_both_binding_orders_and_blocks_legacy_uncertainty(tmp_path,first_version,second_version):
    from jiuwenswarm.research.measurement_slots import claim_reservation,reservation_id
    store,binding,record,target,session,rubric=context(tmp_path)
    def prepare(version):
        value=copy.deepcopy(binding);value['schema']='ai4r-isolated-evaluation-binding:'+str(min(version,2))
        if version==1:value['inputs'].append({'name':'screening_rubric','contract_id':'screening-rubric','artifact_refs':[rubric]})
        reservation=copy.deepcopy(record);reservation['schema']='ai4r-rsi-trial-reservation:'+str(version)
        reservation['inputs_sha256']=hashlib.sha256(json_bytes(value['inputs'])).hexdigest();reservation['id']='historical-'+str(version)
        if version==3:reservation['id']=reservation_id(reservation,('score',))
        value['reservation_ref']=store.put_blob(json_bytes(reservation))
        return value,reservation,store.put_blob(json_bytes(value))
    first,reservation,first_ref=prepare(first_version)
    claim_reservation(store,first,reservation,owner='isolated',binding_ref=first_ref,target=target,session=session,
        references={'trial_ref':first_ref},validate_legacy=lambda value:None)
    second,other,second_ref=prepare(second_version)
    with pytest.raises(ResearchError):claim_reservation(store,second,other,owner='isolated',binding_ref=second_ref,target=target,session=session,
        references={'trial_ref':second_ref},validate_legacy=lambda value:None)


def test_actual_legacy_metadata_join_and_uncertain_slot_are_not_replayed(tmp_path):
    from jiuwenswarm.research.measurement_slots import claim_reservation,reservation_id,legacy_key
    store,binding,record,target,session,_=context(tmp_path)
    old=copy.deepcopy(record);old['schema']='ai4r-rsi-trial-reservation:2';old['id']='legacy-score'
    binding['reservation_ref']=store.put_blob(json_bytes(old));old_binding=store.put_blob(json_bytes(binding))
    with store.transaction() as db:db.execute('INSERT INTO metadata VALUES(?,?)',(legacy_key(old,'isolated'),json_bytes({'binding_ref':old_binding,'trial_ref':old_binding}).decode()))
    record['id']=reservation_id(record,('score',));binding['reservation_ref']=store.put_blob(json_bytes(record));binding_ref=store.put_blob(json_bytes(binding))
    with pytest.raises(ResearchError):claim_reservation(store,binding,record,owner='isolated',binding_ref=binding_ref,target=target,session=session,references={'trial_ref':binding_ref},validate_legacy=lambda value:None)
    record['id']=reservation_id(record,('warmup',0,0));binding['reservation_ref']=store.put_blob(json_bytes(record));binding_ref=store.put_blob(json_bytes(binding))
    claim_reservation(store,binding,record,owner='isolated',binding_ref=binding_ref,target=target,session=session,references={'trial_ref':binding_ref},validate_legacy=lambda value:None)
    with pytest.raises(ResearchError):claim_reservation(store,binding,record,owner='isolated',binding_ref=binding_ref,target=target,session=session,references={'trial_ref':binding_ref},validate_legacy=lambda value:None)


@pytest.mark.asyncio
@pytest.mark.parametrize('owner',['isolated','parent'])
async def test_actual_independent_signed_validators_accept_only_frozen_v3_slots(tmp_path,owner):
    from jiuwenswarm.research.measurement_slots import reservation_id
    if owner=='isolated':
        from tests.unit_tests.research.test_isolated_evaluation import trial_fixture
        store,service,fixture,binding=await trial_fixture(tmp_path)
        validator=service.reservations.validate
    else:
        from tests.unit_tests.research.test_parent_measurement import parent_fixture
        store,service,fixture,binding=await parent_fixture(tmp_path)
        validator=service._reservation
    binding['schema']=binding['schema'].removesuffix(':1')+':2';binding['inputs']=binding['inputs'][:2];binding['phase']='hidden_final'
    value=store.read_record(binding['reservation_ref']);value.pop('signature');value.pop('signer_key_id')
    value['schema']=value['schema'].removesuffix(':1')+':3';value['phase']='hidden_final';value['charge_kind']='final'
    value['inputs_sha256']=hashlib.sha256(json_bytes(binding['inputs'])).hexdigest();value['id']=reservation_id(value,('warmup',0,0))
    binding['reservation_ref']=fixture['put'](fixture['signer'].sign(value))
    validator(binding)
    value['id']=value['id'].removesuffix(':0:0')+':5:0';binding['reservation_ref']=fixture['put'](fixture['signer'].sign(value))
    with pytest.raises(ResearchError):validator(binding)


@pytest.mark.parametrize('slot',[('score',),('warmup',0,0)])
def test_ambiguous_original_legacy_claim_blocks_before_any_new_slot(tmp_path,slot):
    from jiuwenswarm.research.measurement_slots import claim_reservation,reservation_id
    store,binding,record,target,session,_=context(tmp_path)
    record['id']=reservation_id(record,slot);binding['reservation_ref']=store.put_blob(json_bytes(record));ref=store.put_blob(json_bytes(binding))
    with store.transaction() as db:db.execute('INSERT INTO metadata VALUES(?,?)',('isolated-reservation:unresolved','{}'))
    with pytest.raises(ResearchError):claim_reservation(store,binding,record,owner='isolated',binding_ref=ref,target=target,session=session,references={'trial_ref':ref},validate_legacy=lambda value:None)
    assert not list(store.iter_records(kinds=('isolated-reservation-claim',)))


def test_unrelated_protected_historical_session_does_not_require_the_current_signing_key(tmp_path):
    from jiuwenswarm.research.measurement_slots import claim_reservation,reservation_id,legacy_key
    store,binding,record,target,session,_=context(tmp_path)
    old_binding=copy.deepcopy(binding);old=copy.deepcopy(record)
    old['schema']='ai4r-rsi-trial-reservation:2';old['id']='old-rotated-key-session';old['signer_key_id']='historical-retired-key'
    old_binding['session_ref']=old['session_ref']=store.put_blob(b'exact unrelated historical session')
    old_binding['reservation_ref']=store.put_blob(json_bytes(old));old_ref=store.put_blob(json_bytes(old_binding))
    with store.transaction() as db:db.execute('INSERT INTO metadata VALUES(?,?)',(legacy_key(old,'isolated'),json_bytes({'binding_ref':old_ref}).decode()))
    record['id']=reservation_id(record,('score',));binding['reservation_ref']=store.put_blob(json_bytes(record));ref=store.put_blob(json_bytes(binding))
    def current_key_only(value):raise AssertionError('An unrelated protected session must not be requalified with the new signing key')
    claim_reservation(store,binding,record,owner='isolated',binding_ref=ref,target=target,session=session,references={'trial_ref':ref},validate_legacy=current_key_only)
