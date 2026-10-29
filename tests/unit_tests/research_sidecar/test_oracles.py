from jiuwenswarm.research_sidecar.oracles import judge_eligible,score_checks


def test_judge_requires_strict_upper_bound_every_family_and_withholds():
    assert not judge_eligible({'overall':{'false_pass_rate':.1,'upper_95':.45},'families':{}})
    rows,withheld=score_checks([{'check_id':'c','kind':'model_judged','check_family':'f','weight':1,'description':'Pinned judge audit is required.'}],{'c':{'passed':True,'evidence':[]}},judge_audit=None)
    assert withheld and rows[0]['status']=='unavailable' and rows[0]['awarded']==0
