from tests.unit_tests.research_rsi.qualification_fixtures import ControlledQualification
"""IF011 adapter controls use explicit local captures, not a qualified child run."""
import asyncio,copy,hashlib
import pytest
from jiuwenswarm.research_rsi.records import RecordStore,encoded
from jiuwenswarm.research_rsi.signing import Signer


def pin(name):return {'id':name,'sha256':hashlib.sha256(name.encode()).hexdigest()}


def binding():
    refs={name:pin(name) for name in ['session_ref','target_ref','parent_admission_ref','parent_declaration_ref','parent_contract_ref','child_declaration_ref','configuration_ref','model_selection_profile_ref','deployment_ref','check_bundle_ref','checking_profile_ref','reservation_ref']}
    return {'schema':'ai4r-isolated-evaluation-binding:1','id':'binding:one',**refs,'child_body_refs':{'screening_prompt.txt':pin('prompt')},'dependency_refs':[],
        'inputs':[{'name':'candidate_set','contract_id':'candidate-set','artifact_refs':[pin('input')]}],
        'limits':{'time_s':30,'model_calls':2,'memory_mb':128},'phase':'hidden_loop','repeat_index':0}


def test_signed_reservation_binds_charged_action_and_exact_trial_fields(tmp_path):
    from jiuwenswarm.research_rsi.trial_port import TrialReservationIssuer,verify_reservation
    from jiuwenswarm.research_rsi.custody import ExposureLedger
    store=RecordStore(tmp_path/'records');ledger=ExposureLedger(tmp_path/'ledger.sqlite');signer=Signer.generate('custodian')
    partitions={name:[name+str(i) for i in range(20)] for name in ('development','hidden_loop','hidden_final','platform')}
    ledger.register('fixture',partitions,known_bad=10,known_good=3);ledger.open_session('session', 'fixture')
    value=binding();session={'session_id':'session','pass_count_repeats':3,'configuration_ref':value['configuration_ref'],'target_profile_ref':value['target_ref']}
    session_ref=store.put(session);value['session_ref']=session_ref
    issuer=TrialReservationIssuer(ledger,store,signer,approved_sessions=[session_ref])
    with pytest.raises(ValueError):issuer.issue(value,action_id='loop',charge_kind='loop')
    candidate=pin('candidate')
    ledger.reserve('session','loop','loop',fingerprint=hashlib.sha256(encoded(candidate)).hexdigest())
    with pytest.raises(ValueError):issuer.issue(value,action_id='loop',charge_kind='loop',candidate_ref=pin('different-candidate'))
    reservation=issuer.issue(value,action_id='loop',charge_kind='loop',candidate_ref=candidate);record=store.get(reservation)
    verify_reservation(record,value,signer.public_bytes(),'custodian')
    assert record['queries_used']==1 and record['queries_left']==29
    assert not any(key in encoded(record).decode() for key in ['expected_output','fixture_id','label'])
    for key in ('child_declaration_ref','configuration_ref','target_ref'):
        with pytest.raises(ValueError):verify_reservation(record,value|{key:pin('swapped')},signer.public_bytes(),'custodian')
    with pytest.raises(ValueError):verify_reservation(record,value|{'repeat_index':2},signer.public_bytes(),'custodian')
    with pytest.raises(ValueError):issuer.issue(value|{'repeat_index':3},action_id='loop',charge_kind='loop',candidate_ref=candidate)
    ledger.close();store.close()


def test_closed_client_rejects_acceptance_or_foreign_result_and_does_not_reexecute_unknown(tmp_path):
    from jiuwenswarm.research_rsi.text_trial import TextTrialClient
    store=RecordStore(tmp_path/'records');value=binding();pin_binding=store.put(value);calls=[]
    async def transport(operation,ref):
        calls.append(operation)
        if operation=='trial_prepare':return {'trial_ref':pin('trial')}
        raise TimeoutError('actual outcome unknown')
    client=TextTrialClient(store,transport=transport,allowed_session_refs=[value['session_ref']])
    with pytest.raises(TimeoutError):asyncio.run(client.execute(pin_binding))
    with pytest.raises(ValueError):asyncio.run(client.execute(pin_binding))
    assert calls==['trial_prepare','trial_execute']
    result={'schema':'ai4r-isolated-evaluation-result:1','id':'result', 'trial_ref':pin('trial'),'session_ref':value['session_ref'],'target_ref':value['target_ref'],
        'parent_declaration_ref':value['parent_declaration_ref'],'child_declaration_ref':value['child_declaration_ref'],'status':'completed','outputs':[],
        'mandatory_tests_passed':True,'deterministic_result_ref':None,'assessment_refs':[],'observation_refs':[],'trace_refs':[],'failure':None,'accepted':False}
    client.validate_result(value,pin('trial'),result)
    for mutation in ({'accepted':True},{'child_declaration_ref':pin('foreign')},{'session_ref':pin('foreign')}):
        with pytest.raises(ValueError):client.validate_result(value,pin('trial'),result|mutation)
    store.close()


def test_service_port_has_only_custodian_trial_operations_and_imports_exact_refs(tmp_path):
    from jiuwenswarm.research_rsi.trial_port import TrialPort
    from jiuwenswarm.research.state import SQLiteRunStore
    core=SQLiteRunStore(tmp_path/'core');public=RecordStore(tmp_path/'public')
    value=binding();ref=public.put(value);observed=[]
    class Service:
        def prepare_isolated_evaluation(self,pin):observed.append(pin);return {'id':'trial','sha256':'a'*64}
        async def execute_isolated_evaluation(self,pin):raise ValueError('not executed by preparation')
    port=TrialPort(Service(),core,qualification=ControlledQualification(),public_reader=public.read,allowed_session_refs=[value['session_ref']])
    assert set(port.handlers())=={'trial_prepare','trial_execute','trial_inspect'}
    # Unknown referenced bytes fail before the service; no broad store mount.
    with pytest.raises((ValueError,FileNotFoundError)):asyncio.run(port.prepare(ref))
    assert observed==[]
    core.close();public.close()
