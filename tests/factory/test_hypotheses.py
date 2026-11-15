"""Synthetic scoped persistence and bounded input tests; no engines or network."""
import copy
from pathlib import Path

import pytest

from jiuwenswarm.factory.hypotheses import dispatch, propose, validate
from jiuwenswarm.factory.store import NotFound, ScopeDenied, Store


def hypothesis():
    return dict(mechanism='Earlier bounded read admission may reduce target demand waits.',
        applicability=dict(hardware='GB10 shared LPDDR5x',model='DeepSeek V4.1 IST-DAS2bpw',
            source_revision='ffa80d73133ea5c548aefe57889a16e8085a938f',
            limits='Hypothesis requires held-out routing traces and spare overlap slack.'),
        evidence_ids=['trace-one'],primary_source_urls=['https://arxiv.org/abs/2510.10302v2'],
        changed_variable=dict(name='bounded predicted read depth',baseline='0',candidate='1'),
        prediction='At unchanged workload, demand wait falls at least5% without more total native time.',
        required_counters=['demand_wait_ms','wasted_prefetch_bytes','native_prefill_plus_decode_ms'],
        falsification='Reject if wait does not fall or total latency rises.',
        correctness_obligations=['Keep target router authoritative','Full six experts','Frozen quality gate'])


@pytest.fixture
def store(tmp_path):
    with Store(tmp_path/'store') as value:
        for task in ('mine','other'):
            value.create_task(dict(task_id=task,objective='Investigate bounded mechanisms'))
        value.append_observation('mine',dict(obs_id='trace-one',kind='trace',values={'wait_ms':5}))
        value.append_observation('other',dict(obs_id='other-trace',kind='trace',values={'wait_ms':7}))
        yield value


def test_new_agent_hypothesis_is_durable_unmeasured_and_replay_safe(store):
    payload=hypothesis();before=copy.deepcopy(payload)
    result=dispatch(store.scoped('mine'),'mine','propose',dict(hypothesis_id='novel-deadline',hypothesis=payload))
    assert payload==before
    assert result['observation_id']=='hypothesis-proposal-novel-deadline'
    assert result['replayed'] is False
    proposal=result['proposal']
    assert proposal['hypothesis']==payload
    assert proposal['citations_unverified'] is True
    assert proposal['citations_fetched'] is False
    assert proposal['performance_status']==proposal['correctness_status']=='not_evaluated'
    assert proposal['execution_authorized'] is proposal['promotion_authorized'] is False
    assert proposal['evidence_sources'][0]['task_id']=='mine'
    record=store.read('mine',result['observation_id'])
    assert record['kind']=='hypothesis_proposal'
    replay=propose(store.scoped('mine'),'mine','novel-deadline',payload)
    assert replay['replayed'] is True and replay['proposal']==proposal
    payload['prediction']='A conflicting claim must not replace the record.'
    with pytest.raises(ValueError,match='different immutable'):propose(store.scoped('mine'),'mine','novel-deadline',payload)
    assert store.read('mine',result['observation_id'])==record


def test_missing_or_ungranted_cross_task_evidence_cannot_create_proposal(store):
    payload=hypothesis();payload['evidence_ids']=['other-trace']
    with pytest.raises(NotFound):propose(store.scoped('mine'),'mine','cross-task',payload)
    with pytest.raises(NotFound):store.read('mine','hypothesis-proposal-cross-task')
    with pytest.raises(ScopeDenied):propose(store.scoped('mine'),'other','cross-task',payload)
    result=propose(store.scoped('mine',{'other'}),'mine','cross-task',payload)
    assert result['proposal']['evidence_sources'][0]['task_id']=='other'


def test_verified_artifact_can_be_cited_without_copying_contents(store):
    store.put_artifact('mine','raw-trace',b'opaque raw trace','application/octet-stream',None)
    payload=hypothesis();payload['evidence_ids']=['raw-trace']
    result=propose(store.scoped('mine'),'mine','artifact-citation',payload)
    assert result['proposal']['evidence_sources'][0]['record_kind']=='artifact'
    assert 'opaque raw trace' not in str(result)


@pytest.mark.parametrize('mutation',[
    lambda h:h.update(execute=True),
    lambda h:h.update(mechanism=''),
    lambda h:h.update(prediction='x'*2001),
    lambda h:h.update(evidence_ids=[]),
    lambda h:h.update(evidence_ids=['trace-one']*2),
    lambda h:h.update(evidence_ids=['x']*21),
    lambda h:h.update(primary_source_urls=['http://arxiv.org/paper']),
    lambda h:h.update(primary_source_urls=['https://secret@example.com/paper']),
    lambda h:h.update(primary_source_urls=['file:///tmp/paper']),
    lambda h:h.update(primary_source_urls=['https://example.com/a b']),
    lambda h:h.update(required_counters=[]),
    lambda h:h.update(correctness_obligations=[]),
    lambda h:h['changed_variable'].update(candidate='0'),
    lambda h:h['changed_variable'].update(second_name='another knob'),
    lambda h:h['applicability'].pop('limits'),
])
def test_invalid_or_authority_bearing_input_rejected_before_write(store,mutation):
    payload=hypothesis();mutation(payload)
    with pytest.raises(ValueError):propose(store.scoped('mine'),'mine','invalid',payload)
    with pytest.raises(NotFound):store.read('mine','hypothesis-proposal-invalid')


@pytest.mark.parametrize('identifier',['','a'*65,'Host:reserved','with space','Uppercase',True])
def test_hypothesis_id_is_bounded_stable_slug(identifier):
    with pytest.raises(ValueError):validate(identifier,hypothesis())


def test_total_bytes_bounded_even_when_individual_fields_valid():
    payload=hypothesis();payload['required_counters']=[str(i)+'x'*990 for i in range(20)]
    payload['correctness_obligations']=[str(i)+'y'*990 for i in range(20)]
    with pytest.raises(ValueError,match='32 KiB'):validate('large',payload)


def test_non_evidence_and_unknown_operation_rejected(store):
    payload=hypothesis();payload['evidence_ids']=['mine']
    with pytest.raises(ValueError,match='observation or verified artifact'):propose(store.scoped('mine'),'mine','task-reference',payload)
    with pytest.raises(ValueError):dispatch(store.scoped('mine'),'mine','execute',{})
    with pytest.raises(ValueError):dispatch(store.scoped('mine'),'mine','propose',{'hypothesis_id':'extra','hypothesis':hypothesis(),'execute':True})


def test_cc_seals_without_any_engine_or_network(tmp_path):
    from jiuwenswarm.ccv2.ccv2 import Host
    folder=Path(__file__).resolve().parents[2]/'jiuwenswarm/factory/ccs/methodology_hypothesis'
    assert Host(tmp_path/'ccstore',session_grants=['process.exec']).prepare(folder)


def test_local_only_hypothesis_requires_scoped_evidence_without_paper_citation(store):
    payload=hypothesis();payload['primary_source_urls']=[]
    payload['mechanism']='Local profiling and source inspection suggest a redundant synchronization.'
    result=propose(store.scoped('mine'),'mine','local-sync-evidence',payload)
    assert result['proposal']['hypothesis']['primary_source_urls']==[]
    assert result['proposal']['hypothesis']['applicability']['source_revision']
    assert result['proposal']['evidence_sources'][0]['evidence_id']=='trace-one'
    assert result['proposal']['citations_unverified'] is True
    assert result['proposal']['citations_fetched'] is False
    payload['evidence_ids']=[]
    with pytest.raises(ValueError):propose(store.scoped('mine'),'mine','no-local-evidence',payload)
