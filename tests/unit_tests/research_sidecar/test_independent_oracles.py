import pytest
from jiuwenswarm.research_sidecar.independent_oracles import screening_mechanics, evaluate_checks


def score(ident,n,f,c,eligible=True):
    return dict(idea_id=ident,novelty=n,feasibility=f,compute_alignment=c,total=n+f+c,eligible=eligible)


def test_screening_oracle_recomputes_filter_sum_tie_and_top1():
    scores=[score('b',4,3,3),score('a',4,3,3),score('c',5,5,5,False)]
    output={'scores':scores,'ranking':[{'idea_id':'a','total':10,'rank':1},{'idea_id':'b','total':10,'rank':2}],'selected_idea_id':'a'}
    assert screening_mechanics(output,expected_ids=['a','b','c'],eligibility={'a':True,'b':True,'c':False})
    output['selected_idea_id']='c'
    with pytest.raises(ValueError):screening_mechanics(output,expected_ids=['a','b','c'],eligibility={'a':True,'b':True,'c':False})


def test_oracle_registry_cannot_execute_import_or_trust_producer_pass(tmp_path):
    label={'mandatory_checks':[{'check_id':'x','kind':'deterministic'}],'labels':{'x':{'oracle':'os.system','parameters':{}}}}
    observations=evaluate_checks(label,None,{'run_id':'run:unit'},tmp_path)
    assert 'x' not in observations
