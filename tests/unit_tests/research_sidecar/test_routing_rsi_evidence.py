import pytest
from jiuwenswarm.research_sidecar.adapters.routing import validate_evidence


def test_fixed_route_choice_without_call_is_incomplete():
    route={'decision_source':'codex_router_disabled','route_decision_ref':None,'invocation_id':'i','model_id':'gpt-6.1-sol'}
    with pytest.raises(ValueError):validate_evidence(route,[])
    assert validate_evidence(route,[{'invocation_id':'i','observed_runtime':True,'purpose':'task_execution','identity':{'requested':'gpt-6.1-sol'},'route_decision_ref':None,'model_selection_profile_ref':{'id':'a'},'outcome':'completed'}])


def test_rsi_independent_mean_arithmetic_catches_signed_summary_drift(tmp_path):
    from copy import deepcopy
    from tests.unit_tests.research_rsi.fixture_package import make_unit_package
    from jiuwenswarm.research_sidecar.adapters.rsi import validate_final_statistics,validate_actual_proposer
    value=make_unit_package(tmp_path)
    validate_final_statistics(value['result'],value['session'],value['referee'])
    corrupt=deepcopy(value['result']);corrupt['statistics']['parent_passed']=7
    with pytest.raises(ValueError):validate_final_statistics(corrupt,value['session'],value['referee'])
    with pytest.raises(ValueError,match='real completed'):validate_actual_proposer([])
    value['store'].close()



def trace_transfer_fixture(*,scope_patch=None,packet_method='turn/completed'):
    import base64,hashlib,json
    def row(kind,value,raw=None):
        raw=json.dumps(value,sort_keys=True,separators=(',',':')).encode() if raw is None else raw
        ref={'id':hashlib.sha256(raw).hexdigest()+'.json','sha256':hashlib.sha256(raw).hexdigest()}
        return {'kind':kind,'ref':ref,'bytes_base64':base64.b64encode(raw).decode()}
    pin={'id':'protected','sha256':'a'*64}
    scope={'run_id':'r','node_id':'n','subnode_id':'s','attempt_id':'a','execution_id':'e','invocation_id':'i','call_id':'c','contract_ref':pin,'model_call_start_ref':pin}
    scope.update(scope_patch or {})
    packet=row('native-governed-packet',{},('  '+json.dumps({'method':packet_method,'params':{'threadId':'owned'}})+'  \n').encode())
    event=row('native-governed-trace-event',{'schema':'ai4r-native-governed-trace-event:1','scope':scope,'sequence':0,'direction':'in','method':packet_method,'raw_ref':packet['ref']})
    summary=row('native-governed-trace',{'schema':'ai4r-native-governed-trace:1','scope':scope,'status':'completed','event_refs':[event['ref']]})
    prompt=row('model-call-input',{'id':'in','run_id':'r','invocation_id':'i','call_id':'c','prompt':'public proposer input'})
    output=row('model-call-output',{'id':'out','run_id':'r','invocation_id':'i','call_id':'c','text':'public proposal'})
    call=row('model-call',{'id':'c','execution_id':'e','invocation_id':'i','evidence_refs':[prompt['ref'],summary['ref'],output['ref']]})
    observation=row('invocation-observation',{'run_id':'r','node_id':'n','subnode_id':'s','attempt_id':'a','contract_ref':pin,'trace_refs':[call['ref']]})
    return [call,observation,prompt,output,summary,event,packet]


def test_current_rsi_typed_trace_transport_preserves_original_packets_and_exact_scope(tmp_path):
    import base64
    from jiuwenswarm.research_sidecar.adapters.rsi import freeze_public_export,read_public_export
    rows=trace_transfer_fixture()
    freeze_public_export(tmp_path,{'state':'terminal','records':rows},validate=lambda *_:None)
    decoded=read_public_export(tmp_path,validate=lambda *_:None)
    assert len(decoded)==7
    raw=base64.b64decode(rows[-1]['bytes_base64'])
    assert (tmp_path/decoded[-1]['path']).read_bytes()==raw and raw.startswith(b'  ')


@pytest.mark.parametrize('fault',['missing_packet','account_packet','foreign_scope','unknown_kind'])
def test_rsi_transfer_refuses_private_or_incomplete_native_closure(tmp_path,fault):
    import base64,json
    from jiuwenswarm.research_sidecar.adapters.rsi import freeze_public_export
    rows=trace_transfer_fixture()
    if fault=='missing_packet':rows=rows[:-1]
    elif fault=='account_packet':rows=trace_transfer_fixture(packet_method='account/login')
    elif fault=='foreign_scope':rows=trace_transfer_fixture(scope_patch={'node_id':'foreign'})
    else:rows[-1]['kind']='native-account-frame'
    with pytest.raises(ValueError):freeze_public_export(tmp_path,{'state':'terminal','records':rows},validate=lambda *_:None)


def test_pass_gain_requires_complete_pair_timing_even_when_timing_does_not_select_the_winner(tmp_path):
    from tests.unit_tests.research_rsi.fixture_package import make_unit_package
    from jiuwenswarm.research_sidecar.adapters.rsi import validate_final_statistics
    value=make_unit_package(tmp_path)
    try:
        assert value['result']['qualified_by']=='pass_gain'
        value['referee']['pairs'][0]['parent_time_s']=[]
        with pytest.raises(ValueError,match='seven actual'):
            validate_final_statistics(value['result'],value['session'],value['referee'])
    finally:value['store'].close()


@pytest.mark.parametrize('variable',['OTHER_API_KEY','AI4R_RSI_JOB_SOCKET','AI4R_RSI_CUSTODIAN_SOCKET'])
def test_offline_referee_cli_refuses_inherited_authority_before_campaign_read(tmp_path,monkeypatch,variable):
    from jiuwenswarm.research_sidecar import cli
    monkeypatch.setattr(cli,'_root',lambda:tmp_path)
    def forbidden(*_):raise AssertionError('Unauthorized referee reached campaign data')
    monkeypatch.setattr(cli,'_campaign',forbidden);monkeypatch.setenv(variable,'sentinel-not-a-real-credential')
    assert cli.referee_main(['score','--campaign','registered','--oracle-version','oracle:1'])==2
