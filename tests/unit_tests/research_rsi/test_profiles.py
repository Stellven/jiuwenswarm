import pytest
from jiuwenswarm.research_rsi.targets.ranking import rank_opportunities
from jiuwenswarm.research_rsi.profiles import freeze_profile,ProfileError


def test_exact_sum_ascending_immutable_tie_top_one():
    rows=[{'idea_id':i,'novelty':3,'feasibility':4,'compute_alignment':5,'eligible':True} for i in ('z','a')]
    result=rank_opportunities(rows)
    assert result['selected_idea_id']=='a' and result['ranking'][0]=={'rank':1,'idea_id':'a','total':12}
    rows[0]['eligible']=False
    assert len(rank_opportunities(rows)['ranking'])==1


def test_profile_cannot_widen_files_glob_or_mutate_protected_ref():
    parent={'identity':{'body':[{'path':'helper.py','sha256':'a'*64}]},'evolution':{'rsi':'propose','may_change':['files:helper.py']}}
    profile={'mutable_paths':['helper.py'],'parent_ref':{'id':'body','sha256':'a'*64},'protected_refs':[{'id':'referee','sha256':'b'*64}],
        'splits':dict(development='d',hidden_loop='l',hidden_final='f',platform='p'),'session_query_limit':30,'lifetime_query_limit':90,'limits':dict(time_s=1,model_calls=1,memory_mb=64)}
    assert freeze_profile(profile,parent,lambda n,v:None)==profile
    with pytest.raises(ProfileError):freeze_profile({**profile,'mutable_paths':['referee.py']},parent,lambda n,v:None)
