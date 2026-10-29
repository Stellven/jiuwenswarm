import pytest
from jiuwenswarm.research_sidecar.adapters.capsule import validate_evidence
from jiuwenswarm.research_sidecar.adapters.verifier import validate_citation,validate_live_order


def test_c001_and_replay_cannot_prove_live_gate():
    assert validate_citation({'tier1':'FAIL','tier2':'NOT_RUN','advanced':False,'verifier_calls':0})
    with pytest.raises(ValueError):validate_live_order({'mode':'actual','scheduler_kind':'recording_stub'},expected_advance=False)
    with pytest.raises(ValueError):validate_evidence({'mode':'actual','work_observations':['x'],'outputs':['x'],'deterministic_checks':['x'],'gates':[]})


def test_causal_identity_required_not_timestamp_order():
    ref={'id':'a','sha256':'a'*64};gate_ref={'id':'g','sha256':'b'*64}
    rows={'mode':'actual','scheduler_kind':'live','predecessor_node':'screening','successor_node':'hypothesis',
        'accepted_outputs':[{'commit_id':'c','node_id':'screening','attempt_id':'attempt1','subnode_id':'',
            'output_refs':{'opportunity_card':ref},'gate_decision_refs':[gate_ref]}],
        'gates':[{'ref':gate_ref,'record':{'node_id':'screening','attempt_id':'attempt1','scope_kind':'node','action':'advance','accepted_refs':[ref]}}],
        'successor_starts':[{'node_id':'hypothesis','predecessor_commits':[{'node_id':'screening','attempt_id':'attempt1','port':'opportunity_card','artifact_ref':ref,'commit_id':'c'}],
            'bound_input_refs':[{'name':'opportunity_card','ref':ref}]}]}
    assert validate_live_order(rows,expected_advance=True)
    rows['successor_starts'][0]['bound_input_refs']=[{'name':'opportunity_card','ref':{'id':'swapped','sha256':'c'*64}}]
    with pytest.raises(ValueError):validate_live_order(rows,expected_advance=True)


def test_live_lock_requires_observed_barrier_and_explicit_skipped_cause():
    base={'mode':'actual','scheduler_kind':'live','predecessor_node':'screening','successor_node':'hypothesis',
        'successor_starts':[],'accepted_outputs':[],'gates':[]}
    with pytest.raises(ValueError):validate_live_order(base,expected_advance=False)
    assert validate_live_order({**base,'locked_nodes':[{'node_id':'hypothesis','lifecycle_status':'Failed','skipped_because':'predecessor screening failed'}]},expected_advance=False)
