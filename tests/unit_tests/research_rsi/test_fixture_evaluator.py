"""Frozen timing protocol controls; the worker is an explicit capture double."""
import asyncio

from jiuwenswarm.research_rsi.fixed_resources import FixtureEvaluator


def test_equal_correctness_executes_five_warmups_and_seven_alternating_frozen_batches():
    evaluator=object.__new__(FixtureEvaluator)
    evaluator.repeats=1;evaluator.target={'configuration_ref':{'id':'cfg'},'scoring':{
        'batch_iterations':11,'warmup_batches':5,'paired_rounds':7,'calibrated_relative_noise':.01}}
    evaluator.manifest={'partitions':{'hidden_final':[{'id':str(i)} for i in range(20)]},'independent':True}
    calls=[]
    async def scores(candidate,*_):return [[1]]*20
    async def one(candidate,row,phase,operation,repeat,*,timing=False):
        calls.append((candidate,row['id'],operation,timing));return 1,2 if candidate=='parent' else 1
    evaluator.scores=scores;evaluator.one=one
    result=asyncio.run(evaluator.paired('parent','child','hidden_final',1,{'id':'cfg'}))
    assert len(calls)==12*2*20 and all(row[3] for row in calls)
    assert [calls[i*20][0] for i in range(6)]==['parent','child','child','parent','parent','child']
    assert result['warmups']==5 and result['parent_times']==[40]*7 and result['child_times']==[20]*7


def test_timing_program_uses_protected_iterations_and_rejects_nonpositive_counts():
    import pytest
    from jiuwenswarm.research_rsi.worker import timing_program
    assert b'range(11)' in timing_program(11)
    for value in (0,-1,True,1.5,'11'):
        with pytest.raises(ValueError):timing_program(value)


def test_equal_fractional_means_use_timing_without_majority_or_perfect_score_threshold():
    evaluator=object.__new__(FixtureEvaluator);evaluator.repeats=3
    evaluator.target={'configuration_ref':{'id':'cfg'},'scoring':{'batch_iterations':1,'calibrated_relative_noise':.01}}
    evaluator.manifest={'partitions':{'hidden_final':[{'id':'one'}]},'independent':True}
    async def scores(candidate,*_):return [[1,1,0]] if candidate=='parent' else [[1,0,1]]
    calls=[]
    async def one(candidate,row,phase,operation,repeat,*,timing=False):
        calls.append((candidate,repeat));return (1 if repeat<2 else 0),1
    evaluator.scores=scores;evaluator.one=one
    result=asyncio.run(evaluator.paired('parent','child','hidden_final',3,{'id':'cfg'}))
    assert len(calls)==12*2*3 and result['parent_times']==[3]*7 and result['child_times']==[3]*7


def test_changed_timed_fixture_scores_leave_timing_explicitly_unreliable():
    evaluator=object.__new__(FixtureEvaluator);evaluator.repeats=1
    evaluator.target={'configuration_ref':{'id':'cfg'},'scoring':{'batch_iterations':1,'calibrated_relative_noise':.01}}
    evaluator.manifest={'partitions':{'hidden_final':[{'id':'one'}]},'independent':True}
    async def scores(*_):return [[0]]
    async def one(*args,**kwargs):return 1,1
    evaluator.scores=scores;evaluator.one=one
    result=asyncio.run(evaluator.paired('parent','child','hidden_final',1,{'id':'cfg'}))
    assert 'parent_times' not in result and result['timing_unavailable_reason']


def test_unequal_final_means_do_not_start_unneeded_timing_effects():
    evaluator=object.__new__(FixtureEvaluator);evaluator.repeats=3
    evaluator.target={'configuration_ref':{'id':'cfg'},'scoring':{'batch_iterations':1,'calibrated_relative_noise':.01}}
    evaluator.manifest={'partitions':{'hidden_final':[{'id':'one'}]},'independent':True}
    async def scores(candidate,*_):return [[1,0,0]] if candidate=='parent' else [[1,1,0]]
    calls=[]
    async def one(candidate,row,phase,operation,repeat,*,timing=False):
        calls.append((candidate,operation,repeat));return int(repeat<(1 if candidate=='parent' else 2)),1
    evaluator.scores=scores;evaluator.one=one
    result=asyncio.run(evaluator.paired('parent','child','hidden_final',3,{'id':'cfg'}))
    assert calls==[] and 'parent_times' not in result and 'child_times' not in result
    assert result['parent']!=result['child']
