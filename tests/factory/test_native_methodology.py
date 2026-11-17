from jiuwenswarm.factory.methodology import diagnose, followup


def native(**gates):
    return dict(stage='screen',verdict='target_not_met',execution_complete=True,
        gates=dict(exact_tokens_and_finish=True,fixed_placement=True,baseline_timing_stable=True,**gates),
        baseline_tokens_s=14.45,candidate_tokens_s=15.65,conservative_relative_gain=.083)


def test_native_rejected_target_keeps_recorded_correctness_separate_from_reverification():
    result=diagnose([native()],['screen'])
    assert result['recorded_repeatability_gates_passed'] is True
    assert result['repeatability']['status']=='not_established'
    assert 'establish_repeatability' not in [c['id'] for c in result['candidates']]
    assert result['recorded_throughput_comparisons'][0]['verdict']=='target_not_met'
    assert result['semantic_accuracy']=='not_established'
    bad=native();bad['gates']['exact_tokens_and_finish']=False
    result=diagnose([bad],['bad'])
    assert result['recorded_repeatability_gates_passed'] is False
    assert result['recommended_inspection']=='establish_repeatability'


def test_native_process_budget_is_not_a_zero_legacy_cell_budget():
    analysis=diagnose([native()],['screen'])
    task=dict(task_id='t',constraints=dict(throughput_campaign=dict(max_gpu_processes=14,deadline=1234)))
    result=followup(analysis,task,remaining=dict(max_completed_gpu_cells=0,max_turns=10))
    assert 'max_completed_gpu_cells' not in result['remaining_resources']
    assert 'max_completed_gpu_cells' not in result['proposed_input']['budget']
    assert result['native_throughput_envelope']==dict(max_gpu_processes=14,deadline=1234)
    assert result['current_work_executable'] is False
    assert result['requires_operator_admission'] is True
