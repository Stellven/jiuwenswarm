from jiuwenswarm.research_sidecar.inventory import collect


def test_missing_required_commit_dimension_blocks_without_physical_fabrication(tmp_path,monkeypatch):
    monkeypatch.setattr('jiuwenswarm.research_sidecar.inventory._commit_snapshot',lambda:None)
    result=collect(campaign_id='c',run_id='r',repeat_index=0,host_profile='other_declared',role='experiment',budgets={},workspace=tmp_path,requirements={'min_commit_mb':1})
    assert result['readiness']=='blocked' and result['commit_limit_mb'] is None
    assert result['memory_total_mb']>0 and result['unavailable_fields']


def test_observed_system_commit_is_distinct_from_process_vms(tmp_path,monkeypatch):
    monkeypatch.setattr('jiuwenswarm.research_sidecar.inventory._commit_snapshot',lambda:{'commit_limit_mb':100,'commit_used_mb':90})
    out=collect(campaign_id='c',run_id='r',repeat_index=0,host_profile='other_declared',role='orchestration',budgets={},workspace=tmp_path,requirements={'min_commit_mb':11})
    assert out['commit_limit_mb']==100 and out['commit_used_mb']==90
    assert 'available system commit below required capacity' in out['readiness_reasons']
    assert all(row['field'] not in {'commit_limit_mb','commit_used_mb'} for row in out['unavailable_fields'])
