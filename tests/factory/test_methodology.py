"""Methodology proposals are bounded evidence analysis, never experiment execution."""
import json
from pathlib import Path

import pytest

from jiuwenswarm.factory.methodology import ablation, cache_protocol, diagnose, dispatch, followup
from jiuwenswarm.factory.store import NotFound, Store


def request(ids=(1, 2), prompt='same', decode_ms=1000):
    return dict(prompt=prompt, ids=list(ids), finish_reason='length', generated_tokens=2,
                decode_ms=decode_ms, prompt_tokens=4, prompt_ms=100,
                draft_offered=0, draft_accepted=0)


def report(equal=True):
    return dict(status='success', container_removed=True,
                requests=[request(), request(ids=(1, 2) if equal else (1, 3), decode_ms=500)])


def test_diagnosis_missing_metrics_remain_unknown():
    result = diagnose([{'status': 'success'}], ['e1'])
    assert result['decode_tps']['median'] is None
    assert result['draft_engagement']['acceptance_ratio'] is None
    assert result['semantic_accuracy'] == 'not_established'
    assert result['recommended_inspection'] == 'establish_repeatability'
    assert {'decode', 'prefill', 'placement', 'io', 'cpu', 'cache', 'draft', 'quality', 'telemetry'} <= set(result['ontology'])
    assert all(c['expected_benefit'] == 'unknown' for c in result['candidates'])


def test_raw_timing_is_preferred_over_claimed_rate():
    data = report()
    data['requests'][0]['native_decode_tps'] = 999
    result = diagnose([data], ['e1'])
    assert result['decode_tps']['minimum'] == 2
    assert result['decode_tps']['maximum'] == 4
    assert result['decode_tps']['median'] == 3
    assert 'not a treatment effect' in result['decode_tps']['scope']


def test_same_prompt_token_difference_blocks_repeatability():
    result = diagnose([report(equal=False)], ['e1'])
    assert result['repeatability']['status'] == 'different'
    assert result['repeatability']['different_groups'] == 1
    assert ablation(result)['mode'] == 'diagnostic_non_scoring'
    assert not ablation(result)['scoring_ready']


def test_different_treatments_are_not_compared_as_aa():
    a = {'requests': [request()]}
    b = {'requests': [request(ids=(9, 9))]}
    result = diagnose([{'measurements': [a, b]}], ['e1'])
    assert result['repeatability']['status'] == 'not_established'


def test_recovery_and_failed_episodes_precede_optimization():
    result = diagnose([{'results': [
        {'status': 'failed', 'error': 'memory guard'},
        {'status': 'passed', 'container_still_running_after_collector_death': True,
         'final_report_missing_after_collector_death': True}]}], ['faults'])
    assert result['recommended_inspection'] == 'recover_before_scoring'
    assert result['failure_count'] == 1
    assert result['failures'][0]['error'] == 'memory guard'
    assert ablation(result)['mode'] == 'diagnostic_non_scoring'


def test_ablation_is_one_variable_and_cannot_auto_admit():
    analysis = diagnose([report()], ['e1'])
    result = ablation(analysis, 'measure_placement')
    assert result['execution_order'] == ['A', 'B', 'B', 'A']
    assert result['maximum_changed_variables'] == 1
    assert result['maximum_trials'] == 3
    assert result['status'] == 'proposal_only'
    assert result['scoring_ready'] is False
    assert 'independent A/A validity' in result['admission_requirements']
    with pytest.raises(ValueError, match='report-backed'):
        ablation(analysis, 'install_everything')


def test_cache_protocol_never_claims_cold_cache_or_evicts_shared_data():
    result = cache_protocol(diagnose([report()], ['e1']))
    assert result['phases'][0]['fresh_container'] is True
    assert 'does not imply cold SSD' in result['phases'][0]['description']
    assert 'global cache eviction' in result['forbidden']
    assert result['maximum_completed_cells'] == 6


def test_two_cycles_change_proposed_question_without_mutating_contract(store):
    task_before = store.get_task('t')
    failure = dict(status='failed', error='collector died')
    store.put_artifact('t', 'cycle1', json.dumps(failure).encode(), 'application/json', None)
    original = store.artifact_bytes('t', 'cycle1')
    first = dispatch(store.scoped('t'), 't', 'followup', {'evidence_ids': ['cycle1']})['analysis']
    assert first['proposed_input']['hypothesis_id'] == 'diagnose_failure'
    store.append_observation('t', dict(obs_id='proposed-next-input', kind='methodology_proposal', values=first))
    store.put_artifact('t', 'cycle2', json.dumps(report()).encode(), 'application/json', None)
    # Inspect the follow-up report: readiness measurement is now the next gap.
    second = dispatch(store.scoped('t'), 't', 'followup', {'evidence_ids': ['cycle2']})['analysis']
    assert second['proposed_input']['hypothesis_id'] == 'measure_io_readiness'
    assert second['requires_operator_admission'] is True
    assert second['discovered_cc_candidate']['performance_benefit'] == 'unknown'
    assert {k: v for k, v in store.get_task('t').items() if k != 'evidence_cursor'} == {k: v for k, v in task_before.items() if k != 'evidence_cursor'}
    assert store.artifact_bytes('t', 'cycle1') == original
    # Multi-cycle review retains a previous failed attempt rather than forgetting it.
    history = dispatch(store.scoped('t'), 't', 'diagnose', {'evidence_ids': ['cycle1', 'cycle2']})['analysis']
    assert history['failure_count'] == 1
    assert history['episodes'] == 2


def test_dispatch_has_no_side_effects_and_rejects_unreadable_evidence(store):
    store.put_artifact('t', 'report', json.dumps(report()).encode(), 'application/json', None)
    before = store.dump('t')
    for operation in ('diagnose', 'cache_protocol', 'ablation', 'followup'):
        assert 'analysis' in dispatch(store.scoped('t'), 't', operation, {'evidence_ids': ['report']})
    assert store.dump('t') == before
    store.create_task({'task_id': 'other', 'objective': 'private'})
    store.put_artifact('other', 'foreign', b'{}', 'application/json', None)
    with pytest.raises(NotFound):
        dispatch(store.scoped('t'), 't', 'diagnose', {'evidence_ids': ['foreign']})
    with pytest.raises(ValueError):
        dispatch(store.scoped('t'), 't', 'followup', {'evidence_ids': ['report'], 'allowed_effects': ['gpu.use']})


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -1, True, None])
def test_invalid_measurements_do_not_become_zero_or_speedups(value):
    row = request()
    row.update(decode_ms=value, native_decode_tps=value)
    result = diagnose([{'requests': [row]}], ['e1'])
    assert result['decode_tps']['count'] == 0
    assert result['decode_tps']['median'] is None


def test_cc_materials_seal_with_the_existing_runner(tmp_path):
    from jiuwenswarm.ccv2.ccv2 import Host
    host = Host(tmp_path / 'ccstore', session_grants=['process.exec'])
    base = Path(__file__).resolve().parents[2] / 'jiuwenswarm/factory/ccs'
    for directory in ('methodology_diagnosis', 'methodology_out_of_core', 'methodology_ablation', 'methodology_followup'):
        release = host.prepare(base / directory)
        assert host.material(release, 'methodology')
        assert host.material(release, 'ontology')


def test_tokenized_new_adapter_repeats_and_same_identity_cross_cell():
    from jiuwenswarm.factory.methodology import diagnose
    r={'comparison_group':'a'*64,'requests':[
        {'prompt_sha256':'b'*64,'canonical_sha256':'c'*64,'finish':'length'},
        {'prompt_sha256':'b'*64,'canonical_sha256':'c'*64,'finish':'length'}]}
    s={'comparison_group':'a'*64,'requests':[
        {'prompt_sha256':'b'*64,'canonical_sha256':'d'*64,'finish':'length'},
        {'prompt_sha256':'b'*64,'canonical_sha256':'d'*64,'finish':'length'}]}
    result=diagnose([r,s],['r','s'])
    assert result['repeatability']['status']=='different'
    assert result['repeatability']['comparable_cross_cell_groups']==1
    s['comparison_group']='e'*64
    result=diagnose([r,s],['r','s'])
    assert result['repeatability']['status']=='observed_equal'
    assert result['repeatability']['comparable_cross_cell_groups']==0


def test_followup_reads_only_explicitly_granted_prior_task_reports(store):
    import json
    import pytest
    from jiuwenswarm.factory.methodology import dispatch
    from jiuwenswarm.factory.store import NotFound
    store.create_task({'task_id':'prior','objective':'Historical reference'})
    store.put_artifact('prior','previous-report',json.dumps({'requests':[]}).encode(),'application/json','operator')
    with pytest.raises(NotFound):
        dispatch(store.scoped('t'),'t','diagnose',{'evidence_ids':['previous-report']})
    result=dispatch(store.scoped('t',{'prior'}),'t','followup',{'evidence_ids':['previous-report']})['analysis']
    assert result['evidence_sources']==[{'task_id':'prior','evidence_id':'previous-report'}]
    assert result['requires_operator_admission'] is True
