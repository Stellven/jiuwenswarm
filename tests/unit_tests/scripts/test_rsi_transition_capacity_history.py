"""Administrative proof composition only; no runtime or original-store writes."""
import copy
import json
import os
from pathlib import Path
from types import SimpleNamespace
import importlib.util
import pytest

ROOT=Path(__file__).parents[3]
def module(name):
    spec=importlib.util.spec_from_file_location('capacity_transition_'+name,ROOT/'deploy/m1'/(name+'.py'))
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
s=module('rsi_bootstrap_supersession');repair=module('rsi_stopped_repair')
def pin(name):return {'id':name,'sha256':s.digest(name.encode())}
def row(name,outcome='completed',function='verifier'):
    return pin(name),{'id':'calibration-call:'+name,'call_function':function,'outcome':outcome}

def test_default_and_v1_remain_completed_only():
    repair.validate_transition_calibration_calls([row('okay')])
    for outcome in ('failed','outcome_unknown','started'):
        with pytest.raises(ValueError,match='NONCALIBRATION'):repair.validate_transition_calibration_calls([row('old',outcome)])

@pytest.mark.parametrize('fault',[None,'unknown','noncalibration','wrong-sha','duplicate','extra-failed','unused','completed-allowance'])
def test_derived_allowance_must_be_exact_unique_and_consumed_by_failed_calibration(fault):
    calls=[row('done'),row('capacity-one','failed'),row('capacity-two','failed')]
    allowed=[calls[1][0],calls[2][0]]
    if fault=='unknown':calls[1][1]['outcome']='outcome_unknown'
    if fault=='noncalibration':calls[1][1]['call_function']='proposer'
    if fault=='wrong-sha':allowed[0]=dict(allowed[0],sha256='f'*64)
    if fault=='duplicate':allowed.append(allowed[0])
    if fault=='extra-failed':calls.append(row('extra','failed'))
    if fault=='unused':allowed.append(pin('not-an-original-call'))
    if fault=='completed-allowance':calls[1][1]['outcome']='completed'
    if fault:
        with pytest.raises(ValueError):repair.validate_transition_calibration_calls(calls,allowed_failed_refs=allowed)
    else:repair.validate_transition_calibration_calls(calls,allowed_failed_refs=allowed)


@pytest.fixture
def history(tmp_path,monkeypatch):
    from tests.unit_tests.scripts.test_rsi_bootstrap_supersession import context
    request,original,planner,*_=context();request['budget_caps']={'pre_delivery':15,'setup':21,'including_rsi':23}
    second={**request,'schema':'ai4r-rsi-bootstrap-supersession-input:2','stage':'verifier','supersession_id':'capacity-two',
        'fresh_profile_generation':'fresh-two','failed_model_call_ref':pin('second-failed'),
        'prior_uncertain_ref':pin('second-uncertain'),'release_record_ref':pin('second-release'),'containment_receipt_ref':pin('second-containment'),
        'budget_caps':{'pre_delivery':16,'setup':22,'including_rsi':24},
        'predecessor':{'supersession_id':request['supersession_id'],'completion_sha256':'a'*64,'selected_manifest_sha256':s.digest(s.encoded(planner))}}
    final=copy.deepcopy(planner);final['stages'][0]['profile_ref']=pin('fresh-verifier')
    final['profile_generations']['verifier']='fresh-two'
    paths=[tmp_path/'one',tmp_path/'two']
    for path in paths:path.mkdir();(path/'complete.json').write_bytes(b'{}')
    second['predecessor']['completion_sha256']=s.digest(b'{}')
    scope_ref=pin('scope');scope={'schema':'ai4r-rsi-bootstrap-native-scope:1','account_root':'/var/lib/ai4r-rsi/controller/accounts','root':original['root']}
    records={scope_ref['id']:scope};failures=[];chain=[];observed=[]
    for index,item in enumerate((request,second)):
        profile=(original if index==0 else planner)['stages'][1 if index==0 else 0]['profile_ref']
        calls=[pin('partial-one'),pin('partial-two'),item['failed_model_call_ref']] if index==0 else [item['failed_model_call_ref']]
        failure={'profile_ref':profile,'old_stage_calls':calls,'old_stage_calls_charged':len(calls),'all_started_model_calls':5}
        failures.append(failure)
        prepared={'manifest':planner if index==0 else final,'failure':dict(failure,all_started_model_calls=index+3),'budget_caps':item['budget_caps']}
        chain.append((item,prepared,paths[index]))
        start=pin('start-'+str(index));records[start['id']]={'record_kind':'rsi-native-effect-start:1','scope_ref':scope_ref,'contract_ref':profile,'pid_namespace':'pid:[7]'}
        evidence_value={'owned':'ceased','index':index};evidence_sha=s.digest(s.encoded(evidence_value))
        evidence={'id':evidence_sha+'.json','sha256':evidence_sha};records[evidence['id']]=evidence_value
        records[item['containment_receipt_ref']['id']]={'schema':'ai4r-rsi-native-containment:1','scope_ref':scope_ref,
            'prior_lease_ref':start,'owned_container_id':str(index+1)*64,'prior_pid_namespace':'pid:[7]',
            'observed_exited':True,'observed_no_owned_processes':True,'evidence_refs':[evidence],'recorded_at':'2026-10-26T00:00:00Z'}
        records[item['prior_uncertain_ref']['id']]={'record_kind':'rsi-native-effect-completion:1','scope_ref':scope_ref,
            'state':'uncertain','prior_lease_ref':start,'proof':{'no_dispatch_start_observed':False,'known_terminal_call_refs':calls}}
        records[item['release_record_ref']['id']]={'record_kind':'rsi-native-effect-release:1','scope_ref':scope_ref,
            'prior_state':{'state':'uncertain','ref':item['prior_uncertain_ref']},'host_containment_ref':item['containment_receipt_ref'],'recorded_at':'2026-10-26T00:00:00Z'}
    current_start=pin('current-start');current_ref=pin('current-complete');current_call=pin('current-call')
    records[current_start['id']]={'record_kind':'rsi-native-effect-start:1','scope_ref':scope_ref,'contract_ref':final['stages'][0]['profile_ref'],
        'session_id':'catalog-calibration:unit-current','pid_namespace':'pid:[8]','owner_pid':123,'recorded_at':'2026-10-26T00:00:00Z'}
    current_claim=pin('current-claim');current_grant=pin('current-grant');current_request=pin('current-request')
    records[current_claim['id']]={'grant_ref':current_grant};records[current_grant['id']]={'request_ref':current_request}
    records[current_request['id']]={'calibration_profile_ref':final['stages'][0]['profile_ref']}
    records[current_ref['id']]={'record_kind':'rsi-native-effect-completion:1','scope_ref':scope_ref,'state':'complete',
        'prior_lease_ref':current_start,'proof':{'no_dispatch_start_observed':False,'known_terminal_call_refs':[current_call],'actual_model_containment_refs':[]},'recorded_at':'2026-10-26T00:00:00Z'}
    terminal={'ref':current_call,'record':{'id':'calibration-call:current','invocation_id':'invocation:current','outcome':'completed'}}
    starts=[{'ref':pin('model-start'),'record':{'call_id':'calibration-call:current','invocation_id':'invocation:current','call_claim_ref':current_claim}}]
    core=SimpleNamespace(read_record=lambda pin:records[pin['id']],iter_records=lambda kinds:iter(starts if kinds==('model-call-start',) else [terminal] if kinds==('model-call',) else []))
    current={'state':'complete','ref':current_ref}
    class DB:
        def execute(self,*args):return SimpleNamespace(fetchone=lambda:(current['state'],json.dumps(current['ref'])))
    leases=SimpleNamespace(db=DB(),get=lambda pin:records[pin['id']],read=lambda pin:s.encoded(records[pin['id']]))
    def classify(store,base,item,known_failed_refs=()):
        index=int(item['supersession_id']=='capacity-two');observed.append(('classify',index,known_failed_refs))
        assert base==(original if index==0 else planner)
        return copy.deepcopy(failures[index])
    monkeypatch.setattr(s,'failed_capacity',classify)
    monkeypatch.setattr(s,'check_transition',lambda store,base,selected,item:observed.append(('transition',item['supersession_id'])))
    monkeypatch.setattr(s,'read',lambda path,**kwargs:path.read_bytes())
    return SimpleNamespace(core=core,leases=leases,scope_ref=scope_ref,original=original,chain=chain,records=records,
        current=current,current_ref=current_ref,current_start=current_start,observed=observed,failures=failures)


@pytest.mark.parametrize('fault',[None,'forged-release','wrong-profile','no-dispatch','incomplete-current','current-kind','current-scope','current-proof','charge'])
def test_completed_history_revalidates_real_release_population_transitions_and_current_normal_finish(history,fault):
    h=history;first=h.chain[0][0]
    if fault=='forged-release':h.records[first['release_record_ref']['id']]['record_kind']='forged'
    if fault=='wrong-profile':h.records['start-0']['contract_ref']=pin('foreign-profile')
    if fault=='no-dispatch':h.records[first['prior_uncertain_ref']['id']]['proof']['no_dispatch_start_observed']=True
    if fault=='incomplete-current':h.current['state']='uncertain'
    if fault=='current-kind':h.records[h.current_ref['id']]['record_kind']='unrelated-complete'
    if fault=='current-scope':h.records[h.current_ref['id']]['scope_ref']=pin('foreign-scope')
    if fault=='current-proof':h.records[h.current_ref['id']]['proof']['known_terminal_call_refs']=[]
    if fault=='charge':h.chain[1][1]['budget_caps']={'pre_delivery':15,'setup':21,'including_rsi':23}
    if fault:
        with pytest.raises(ValueError):s.rejoin_completed_capacity_history(h.core,h.leases,h.scope_ref,h.original,h.chain)
    else:
        result=s.rejoin_completed_capacity_history(h.core,h.leases,h.scope_ref,h.original,h.chain)
        assert result['failed_refs']==[item['failed_model_call_ref'] for item,_,_ in h.chain]
        assert result['historical_extra_model_calls']==4 and result['current_native_lease']['ref']==h.current_ref
        assert [row for row in h.observed if row[0]=='transition']==[('transition','capacity-one'),('transition','capacity-two')]
        assert [row[2] for row in h.observed if row[0]=='classify']==[[h.chain[1][0]['failed_model_call_ref']],[first['failed_model_call_ref']]]


@pytest.mark.skipif(os.name!='posix' or os.geteuid()!=0,reason='Root archive custody')
def test_tampered_root_chain_is_rejected_before_any_original_core_is_opened(tmp_path,monkeypatch):
    from tests.unit_tests.scripts.test_rsi_bootstrap_supersession import context,completed_fixture
    (tmp_path/'config').mkdir();parent=tmp_path/'config/bootstrap-supersessions';s.mkdir(parent)
    request,original,selected,*_=context();path=parent/request['generation']
    completed_fixture(path,request,original,selected)
    (path/'plan.json').chmod(0o600);(path/'plan.json').write_bytes(b'{}');(path/'plan.json').chmod(0o440)
    monkeypatch.setattr(s,'ReadCore',lambda *args:pytest.fail('Tampered chain must fail before Core access'))
    with pytest.raises((ValueError,KeyError)):s.historical_capacity_dispositions(tmp_path,request['generation'])
