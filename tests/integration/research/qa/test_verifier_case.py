from jiuwenswarm.research_sidecar.adapters.verifier import validate_citation,validate_live_order
from jiuwenswarm.research_sidecar.independent_oracles import live_records
from jiuwenswarm.research_sidecar.evaluation_records import EvaluationRecords


def test_replay_or_actual_causal_release(frozen_campaign,actual_runs,label_for_case):
    check=frozen_campaign['check'];assert check in {'M1-QA/V05','M1-QA/V06'}
    variants={'live_gate_ordering'} if check=='M1-QA/V06' else None
    rows=actual_runs('verifier',variants)
    if check=='M1-QA/V05':
        seen_invalid=seen_valid=False
        for row,case,run,folder,frozen in rows:
            if row['variant_id']=='live_gate_ordering':continue
            assert isinstance(frozen,EvaluationRecords) and frozen.request['entry_point']=='E2', 'V05 requires its exact private replay export.'
            replay=frozen.replay_observation(node_id=frozen.source['node_id'],output_port=frozen.scope['selected_output_port'])
            if case['expected_behavior']=='halt':
                validate_citation(replay)
                seen_invalid=True
            else:
                assert replay['tier1']=='PASS' and replay['tier2'] in {'PASS','PASS_WITH_KNOWN_LIMITATIONS'} and replay['advanced']
                assert replay['verifier_calls']>=1;seen_valid=True
        assert seen_invalid and seen_valid,'Both frozen valid and unsupported-citation replay counterparts are required.'
    else:
        seen=set()
        for row,case,run,folder,frozen in rows:
            assert not isinstance(frozen,EvaluationRecords),'Private recording actions cannot prove actual live scheduler causality.'
            fault=case['fault_plan_ref'];declared=next(f for f in frozen_campaign['campaign']['fault_plan'] if f['fault_id']==fault)
            assert declared['kind'] in {'delay_gate_persistence','swap_artifact'}
            target=declared['target']['node_id'];assert target
            label=label_for_case(case)
            definitions=[d['parameters'] for d in label['labels'].values() if isinstance(d,dict) and d.get('oracle')=='live_gate']
            assert len(definitions)==1,'Exact independent live predecessor/successor binding is required.'
            p=definitions[0];assert p['predecessor_node']==target
            validate_live_order(live_records(frozen,folder,p),expected_advance=declared['kind']=='delay_gate_persistence',require_delay_barrier=declared['kind']=='delay_gate_persistence')
            seen.add(declared['kind'])
        assert seen=={'delay_gate_persistence','swap_artifact'}
