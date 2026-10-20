"""Observe the existing CLI RSI case; never start another optimization run."""
from jiuwenswarm.research_sidecar.adapters.rsi import read_public_export,validate_public_session,validate_actual_proposer


def test_actual_bounded_proposer_and_independent_signed_session(frozen_campaign,actual_runs,label_for_case):
    assert frozen_campaign['check']=='M1-QA/V08'
    for _,case,run,folder,_ in actual_runs('rsi'):
        label=label_for_case(case)
        definitions=[d['parameters'] for d in label['labels'].values() if isinstance(d,dict) and d.get('oracle')=='rsi_session_integrity']
        assert len(definitions)==1,'Exact independently frozen public signer binding required.'
        pin=definitions[0];records=read_public_export(folder/'rsi-export')
        validate_public_session(records,public_key=bytes.fromhex(pin['public_key_hex']),key_id=pin['key_id'])
        validate_actual_proposer(records)
        result=next(e['record'] for e in records if e['kind']=='rsi-session-result')
        assert result['outcome'] in {'QUALIFIED','NO_IMPROVEMENT','UNEVALUATED_CANDIDATE','INCONCLUSIVE'}
        assert result['attempts_used']>0 and result['queries_used']>0 and run['model_calls']
        assert run['outcome_detail']['product_decision']==result['outcome']
