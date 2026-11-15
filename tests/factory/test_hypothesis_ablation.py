"""Proposal-to-design translation keeps actual execution admission separate."""
import copy

import pytest

from jiuwenswarm.factory.hypotheses import propose
from jiuwenswarm.factory.methodology import dispatch, proposal_ablation
from jiuwenswarm.factory.store import Store
from test_hypotheses import hypothesis


@pytest.fixture
def proposal_store(tmp_path):
    with Store(tmp_path/'store') as store:
        store.create_task(dict(task_id='task',objective='Investigate a novel bounded mechanism'))
        store.append_observation('task',dict(obs_id='trace-one',kind='trace',values={'requests':[]}))
        result=propose(store.scoped('task'),'task','new-deadline-policy',hypothesis())
        yield store,result


def test_proposal_becomes_design_without_new_permission_field(proposal_store):
    store,proposal=proposal_store
    task_before=store.get_task('task');record_before=store.read('task',proposal['observation_id'])
    result=dispatch(store.scoped('task'),'task','ablation',
        {'evidence_ids':[proposal['observation_id']],'hypothesis_id':'new-deadline-policy'})['analysis']
    assert result['status']=='proposal_only'
    assert result['scoring_ready'] is False
    assert result['execution_authorized'] is result['promotion_authorized'] is False
    assert result['maximum_changed_variables']==1
    assert result['execution_order']==list('ABBA')
    assert result['hypothesis_id']=='new-deadline-policy'
    assert result['hypothesis_sha256']==proposal['proposal']['hypothesis_sha256']
    assert result['candidate']['single_change']==hypothesis()['changed_variable']
    for key in ('required_counters','falsification','correctness_obligations'):
        assert result[key]==hypothesis()[key]
    assert result['candidate']['applicability']==hypothesis()['applicability']
    assert result['candidate']['evidence_sources']==proposal['proposal']['evidence_sources']
    assert result['citations_unverified'] is True and result['citations_fetched'] is False
    assert result['proposal_evidence_source']=={'task_id':'task','evidence_id':proposal['observation_id']}
    assert store.get_task('task')==task_before
    assert store.read('task',proposal['observation_id'])==record_before


@pytest.mark.parametrize('mutation',[
    lambda p:p['hypothesis'].update(prediction='A silently changed prediction'),
    lambda p:p.update(hypothesis_sha256='0'*64),
    lambda p:p.update(status='accepted'),
    lambda p:p.update(execution_authorized=True),
    lambda p:p.update(promotion_authorized=True),
    lambda p:p.update(citations_unverified=False),
    lambda p:p.update(citations_fetched=True),
    lambda p:p.update(maximum_changed_variables=2),
    lambda p:p.update(correctness_status='passed'),
    lambda p:p.update(performance_status='improved'),
    lambda p:p.update(evidence_sources=[]),
])
def test_corrupted_or_promoted_payload_cannot_be_used_as_proposal(proposal_store,mutation):
    _,result=proposal_store;proposal=copy.deepcopy(result['proposal']);mutation(proposal)
    with pytest.raises(ValueError):proposal_ablation(proposal,{'task_id':'task','evidence_id':result['observation_id']})


def test_builtin_route_keeps_its_existing_policy_with_proposal_present(proposal_store):
    store,proposal=proposal_store
    refs=['trace-one',proposal['observation_id']]
    analysis=dispatch(store.scoped('task'),'task','diagnose',{'evidence_ids':refs})['analysis']
    assert 'measure_io_readiness' in {candidate['id'] for candidate in analysis['candidates']}
    result=dispatch(store.scoped('task'),'task','ablation',
        {'evidence_ids':refs,'hypothesis_id':'measure_io_readiness'})['analysis']
    assert result['candidate']['id']=='measure_io_readiness'
    assert result['mode']=='diagnostic_non_scoring'
    assert result['scoring_ready'] is False


def test_proposal_reference_requires_explicit_matching_hypothesis(proposal_store):
    store,proposal=proposal_store
    for supplied in ({}, {'hypothesis_id':'not-the-proposal'}):
        with pytest.raises(ValueError):dispatch(store.scoped('task'),'task','ablation',
            {'evidence_ids':[proposal['observation_id']],**supplied})


def test_duplicate_proposal_reference_cannot_ambiguously_select_design(proposal_store):
    store,proposal=proposal_store
    with pytest.raises(ValueError,match='Ambiguous'):dispatch(store.scoped('task'),'task','ablation',
        {'evidence_ids':[proposal['observation_id']]*2,'hypothesis_id':'new-deadline-policy'})


@pytest.mark.parametrize('sources',[[None],['not-a-record'],[42],[[]],[{}]])
def test_malformed_provenance_rows_raise_value_error(proposal_store,sources):
    _,result=proposal_store;proposal=copy.deepcopy(result['proposal'])
    proposal['evidence_sources']=sources
    with pytest.raises(ValueError,match='provenance'):proposal_ablation(proposal,{'task_id':'task','evidence_id':result['observation_id']})


# Reuse the existing loop's real store and immutable-template fixture. These are
# selection-only tests: no fake or actual benchmark execution is invoked.
from test_loop import setup_loop


def authored_loop_proposal(store,task_id):
    store.append_observation(task_id,dict(obs_id='trace-one',kind='trace',values={'requests':[]}))
    payload=hypothesis()
    payload.update(mechanism='Native verified drafting may reduce complete request latency.',
        changed_variable={'name':'--dspark','baseline':'none','candidate':'on'},
        prediction='At fixed pp512/tg128, native total latency falls without a sampled quality regression.')
    return propose(store.scoped(task_id),task_id,'novel-verified-draft',payload)


def test_authored_proposal_selects_only_when_operator_template_lists_id(setup_loop):
    from jiuwenswarm.factory.loop import FactoryLoop
    store,_=setup_loop
    policy=copy.deepcopy(store.get_task('parent')['constraints']['factory_loop'])
    policy['templates'][0]['allowed_hypothesis_ids'].append('novel-verified-draft')
    store.create_task(dict(task_id='novel-parent',objective='Measure a proposed native mechanism',
        contract_id='original',constraints={'factory_loop':policy},allowed_effects=['process.exec','gpu.use']))
    proposal=authored_loop_proposal(store,'novel-parent')
    loop=FactoryLoop(store,'novel-parent',clock=lambda:10)
    result=loop.select('novel-one',[proposal['observation_id']],'novel-verified-draft','draft-pilot',0)
    assert result['state']=='selected'
    decision=store.read('novel-parent','novel-parent:decision:1')
    assert 'Unmeasured agent hypothesis' in decision['uncertainty']
    assert hypothesis()['falsification'] in decision['uncertainty']
    assert decision['observations'][0]['scoring_ready'] is False
    assert decision['observations'][0]['candidate']['id']=='novel-verified-draft'
    assert store._db.execute('SELECT count(*) FROM attempts').fetchone()[0]==0


def test_authored_proposal_cannot_select_unlisted_template_id(setup_loop):
    from jiuwenswarm.factory.loop import FactoryLoop
    from jiuwenswarm.factory.store import ScopeDenied
    store,_=setup_loop;proposal=authored_loop_proposal(store,'parent')
    loop=FactoryLoop(store,'parent',clock=lambda:10)
    with pytest.raises(ScopeDenied,match='Hypothesis is not admitted'):
        loop.select('novel-one',[proposal['observation_id']],'novel-verified-draft','draft-pilot',0)
    assert store.get_task('parent')['current_decision_rev']==0
    assert loop.status()['cycles']==[]
