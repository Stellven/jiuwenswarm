"""Synthetic host fixtures only: no kernel cgroup, daemon or model effects."""
import asyncio
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('group_budget', Path(__file__).parents[3] / 'deploy/m1/rsi_host_group_budget.py')
budget = importlib.util.module_from_spec(spec); spec.loader.exec_module(budget)


def request():
    return {'schema': 'ai4r-rsi-host-group-demand:1', 'jobs': {'timing_calibration': 2196,
            'visible_opportunity': 312, 'security': 13, 'final_qualification_and_candidate': 1024},
            'container_reserve': 64, 'max_descendants': 4096}


def test_full_workload_exceeds_original_limit_and_fits_finite_allowance():
    assert budget.demand(request(), 100) == 3709
    assert 2196 > 512


@pytest.mark.parametrize('change', ['unbounded', 'huge', 'negative', 'bool', 'unknown', 'exhausted'])
def test_finite_demand_cannot_widen_or_ignore_retained_groups(change):
    value = request(); retained = 100
    if change == 'unbounded': value['max_descendants'] = 'max'
    if change == 'huge': value['jobs']['final_qualification_and_candidate'] = 1025
    if change == 'negative': value['jobs']['security'] = -1
    if change == 'bool': value['container_reserve'] = True
    if change == 'unknown': value['jobs']['extra'] = 1
    if change == 'exhausted': retained = 2000
    with pytest.raises(ValueError): budget.demand(value, retained)


def group(path, populated='0', procs=''):
    path.mkdir(parents=True); (path / 'cgroup.events').write_text('populated ' + populated + '\nfrozen 0\n')
    (path / 'cgroup.procs').write_text(procs)


def test_nested_retained_groups_are_observed_without_any_mutation(tmp_path, monkeypatch):
    root = tmp_path / 'jobs'; group(root); group(root / 'old'); group(root / 'old/nested')
    monkeypatch.setattr(budget.host, 'secure', lambda p: None)
    before = {str(p): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    assert len(budget.empty_job_groups(root)) == 3
    assert {str(p): p.read_bytes() for p in root.rglob('*') if p.is_file()} == before
    (root / 'old/nested/cgroup.events').write_text('populated 1\n')
    with pytest.raises(ValueError, match='NOT_EMPTY'): budget.empty_job_groups(root)
    (root / 'old/nested/cgroup.events').write_text('populated 0\n')
    (root / 'old/nested/cgroup.procs').write_text('123\n')
    with pytest.raises(ValueError, match='NOT_EMPTY'): budget.empty_job_groups(root)


def fixture(tmp_path, monkeypatch):
    path = tmp_path / 'issued'; path.mkdir(); cg = tmp_path / 'cgroup'; cg.mkdir()
    (cg / 'cgroup.max.descendants').write_text('512')
    original = tmp_path / 'started.json'; original.write_text('original receipt')
    leaf = cg / 'old-job'; group(leaf)
    monkeypatch.setattr(budget.host, 'CG', cg)
    monkeypatch.setattr(budget.host, 'secure', lambda p: None)
    monkeypatch.setattr(budget, 'location', lambda: path)
    plan = {'incarnation': {'boot': 'one'}, 'prior_max_descendants': 512, 'request': request(), 'bounds': {'memory': 'same'},
            'dying_descendants': 0, 'visible_descendants': 12, 'retained_descendants': 12,
            'planned_total_descendants': budget.demand(request(), 12)}
    (path / 'plan.json').write_bytes(budget.encoded(plan))
    monkeypatch.setattr(budget, 'observe', lambda req, expected_limit=None: dict(plan, prior_max_descendants=expected_limit or 512))
    return path, cg, original


def test_apply_changes_only_descendant_limit_and_keeps_originals(tmp_path, monkeypatch):
    path, cg, original = fixture(tmp_path, monkeypatch)
    before = original.read_bytes(); leaf = (cg / 'old-job').stat().st_ino
    result = budget.apply(budget.host.digest(path / 'plan.json'))
    assert result['max_descendants'] == 4096
    assert (cg / 'cgroup.max.descendants').read_text() == '4096'
    assert original.read_bytes() == before and (cg / 'old-job').stat().st_ino == leaf
    assert (path / 'complete.json').exists()
    with pytest.raises(ValueError, match='CLAIM_BLOCKS'): budget.apply(budget.host.digest(path / 'plan.json'))


def test_changed_observation_or_wrong_review_has_no_claim_or_effect(tmp_path, monkeypatch):
    path, cg, _ = fixture(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match='APPROVAL'): budget.apply('0' * 64)
    monkeypatch.setattr(budget, 'observe', lambda *a, **k: {})
    with pytest.raises(ValueError, match='PLAN_CHANGED'): budget.apply(budget.host.digest(path / 'plan.json'))
    assert not (path / 'claim.json').exists() and (cg / 'cgroup.max.descendants').read_text() == '512'


def test_interrupted_post_write_claim_blocks_replay(tmp_path, monkeypatch):
    path, cg, _ = fixture(tmp_path, monkeypatch)
    def observation(req, expected_limit=None):
        if expected_limit is not None: raise ValueError('HOST_CHANGED')
        return json.loads((path / 'plan.json').read_bytes())
    monkeypatch.setattr(budget, 'observe', observation)
    with pytest.raises(ValueError, match='HOST_CHANGED'): budget.apply(budget.host.digest(path / 'plan.json'))
    assert (path / 'claim.json').exists() and not (path / 'complete.json').exists()
    assert (cg / 'cgroup.max.descendants').read_text() == '4096'
    with pytest.raises(ValueError, match='CLAIM_BLOCKS'): budget.apply(budget.host.digest(path / 'plan.json'))


def test_container_inspections_preserve_mount_fields_but_ignore_mount_order(monkeypatch):
    row = {'Id': 'a' * 64, 'State': {'Running': False, 'Restarting': False, 'Pid': 0},
           'HostConfig': {'RestartPolicy': {'Name': 'no', 'MaximumRetryCount': 0}},
           'Mounts': [{'Destination': '/b', 'Source': '/old', 'RW': False}, {'Destination': '/a', 'Source': '/new', 'RW': True}]}
    def call(command): return ('a' * 64).encode() if 'ps' in command else json.dumps([row]).encode()
    monkeypatch.setattr(budget.restore, 'client', call)
    first = budget.containers(); row['Mounts'].reverse()
    assert budget.containers() == first
    row['Mounts'][0]['RW'] = not row['Mounts'][0]['RW']
    assert budget.containers() != first
    row['State']['Running'] = True
    with pytest.raises(ValueError, match='NOT_STOPPED'): budget.containers()


@pytest.mark.parametrize('changed', [None, 'memory', 'populated', 'unbounded', 'dying', 'count-race'])
def test_actual_observer_joins_resource_receipt_and_all_empty_descendants(tmp_path, monkeypatch, changed):
    cg = tmp_path / 'cgroup'; cg.mkdir(); group(cg / 'jobs'); group(cg / 'jobs/retained')
    controls = {'memory.max': '4096', 'memory.swap.max': '0', 'pids.max': '1024', 'cpu.max': '200000 100000', 'cgroup.max.descendants': '512', 'cgroup.max.depth': '8'}
    for name, value in controls.items(): (cg / name).write_text(value)
    (cg / 'cgroup.stat').write_text('nr_descendants 2\nnr_dying_descendants 0\n')
    original = tmp_path / 'started.json'; original.write_text('original')
    receipt = {'cgroup_inode': cg.stat().st_ino, 'memory_max': '4096', 'pids_max': '1024', 'cpu_max': '200000 100000'}
    monkeypatch.setattr(budget.host, 'CG', cg); monkeypatch.setattr(budget.host, 'ROOT', tmp_path)
    monkeypatch.setattr(budget.host, 'verified', lambda: None); monkeypatch.setattr(budget.host, 'secure', lambda p: None)
    monkeypatch.setattr(budget.host, 'active_receipt', lambda: receipt)
    monkeypatch.setattr(budget.host, 'incarnation', lambda: {'boot': 'test'})
    monkeypatch.setattr(budget, 'containers', lambda: [])
    if changed == 'memory': (cg / 'memory.max').write_text('8192')
    if changed == 'populated': (cg / 'jobs/retained/cgroup.events').write_text('populated 1\n')
    if changed == 'unbounded': (cg / 'cgroup.max.descendants').write_text('max')
    if changed == 'dying': (cg / 'cgroup.stat').write_text('nr_descendants 2\nnr_dying_descendants 3\n')
    if changed == 'count-race': (cg / 'cgroup.stat').write_text('nr_descendants 3\nnr_dying_descendants 0\n')
    if changed and changed != 'dying':
        with pytest.raises(ValueError): budget.observe(request())
    else:
        result = budget.observe(request())
        assert result['retained_descendants'] == (5 if changed == 'dying' else 2) and result['prior_max_descendants'] == 512
        assert result['visible_descendants'] == 2
        assert result['bounds'] == {k: receipt[k] for k in ('memory_max', 'pids_max', 'cpu_max')}
        assert original.read_text() == 'original'


def test_doctor_uses_explicit_remaining_demand_and_rejects_lost_original_group(tmp_path, monkeypatch):
    path, _, _ = fixture(tmp_path, monkeypatch)
    plan = json.loads((path / 'plan.json').read_bytes())
    plan.update(cgroup_inode=17, swap_max='0', max_depth='8', original_started_sha256='original',
                active_receipt_sha256='active', admin_source_sha256={'helper': 'pin'},
                job_groups=[{'path': 'old', 'inode': 99}])
    (path / 'plan.json').write_bytes(budget.encoded(plan))
    monkeypatch.setattr(budget, 'observe', lambda req, expected_limit=None: dict(plan, prior_max_descendants=expected_limit or 512))
    budget.apply(budget.host.digest(path / 'plan.json'))
    remaining = request(); remaining['jobs'] = dict.fromkeys(remaining['jobs'], 0)
    input_path = tmp_path / 'remaining.json'; input_path.write_bytes(budget.encoded(remaining))
    def observe(req, **kwargs):
        assert req == remaining
        return dict(plan, prior_max_descendants=4096, retained_descendants=2700, planned_total_descendants=2764)
    monkeypatch.setattr(budget, 'observe', observe)
    assert budget.doctor(input_path)['remaining_descendants'] == 1396
    monkeypatch.setattr(budget, 'observe', lambda *a, **k: dict(plan, job_groups=[{'path': 'old', 'inode': 101}]))
    with pytest.raises(ValueError, match='HOST_CHANGED'): budget.doctor(input_path)


def test_installed_final_evaluator_schedule_fits_final_category_without_worker_effects():
    from jiuwenswarm.research_rsi.fixed_resources import FixtureEvaluator
    evaluator = object.__new__(FixtureEvaluator)
    evaluator.repeats = 1
    evaluator.manifest = {'partitions': {'platform': [{'id': str(i)} for i in range(12)],
        'hidden_loop': [{'id': str(i)} for i in range(20)], 'hidden_final': [{'id': str(i)} for i in range(20)]},
        'independent': True}
    evaluator.target = {'configuration_ref': {'id': 'synthetic-config', 'sha256': 'a' * 64},
                        'scoring': {'calibrated_relative_noise': 0.01}}
    evaluator.last_evidence = []; calls = []
    async def one(candidate, row, phase, operation, repeat, timing=False):
        calls.append((phase, timing)); return 1, 1.0
    evaluator.one = one
    async def schedule():
        assert await evaluator.mandatory('synthetic-child')
        await evaluator.loop('synthetic-child', 'hidden_loop')
        result = await evaluator.paired('synthetic-parent', 'synthetic-child', 'hidden_final', 1, evaluator.target['configuration_ref'])
        assert len(result['parent_times']) == len(result['child_times']) == 7
    asyncio.run(schedule())
    assert sum(phase == 'hidden_final' for phase, _ in calls) == 2 * 20 + 12 * 2 * 20 == 520
    assert len(calls) == 12 + 20 + 520 == 552
    final_budget = request(); final_budget['jobs'] = dict.fromkeys(final_budget['jobs'], 0)
    final_budget['jobs']['final_qualification_and_candidate'] = len(calls)
    assert budget.demand(final_budget, 0) == len(calls) + final_budget['container_reserve']
    assert len(calls) < request()['jobs']['final_qualification_and_candidate'] == 1024


@pytest.mark.parametrize('after_write', [False, True])
@pytest.mark.parametrize('change', ['decrease', 'increase', 'visible', 'resource', 'container', 'bad-total', 'bad-retained'])
def test_only_dying_group_reclamation_can_change_reviewed_observation(after_write, change):
    before = {'request': request(), 'dying_descendants': 2, 'visible_descendants': 12,
              'retained_descendants': 14, 'planned_total_descendants': budget.demand(request(), 14),
              'prior_max_descendants': 512, 'groups': [{'path': 'old', 'inode': 42}],
              'bounds': {'cpu': 'same'}, 'containers': [{'id': 'same'}]}
    after = dict(before, dying_descendants=1, retained_descendants=13,
                 planned_total_descendants=budget.demand(request(), 13),
                 prior_max_descendants=4096 if after_write else 512)
    if change == 'increase': after.update(dying_descendants=3, retained_descendants=15, planned_total_descendants=budget.demand(request(), 15))
    if change == 'visible': after['groups'] = [{'path': 'old', 'inode': 43}]
    if change == 'resource': after['bounds'] = {'cpu': 'changed'}
    if change == 'container': after['containers'] = [{'id': 'foreign'}]
    if change == 'bad-total': after['planned_total_descendants'] += 1
    if change == 'bad-retained': after['retained_descendants'] += 1
    assert budget.compatible(before, after, after_write=after_write) is (change == 'decrease')


def test_apply_accepts_reclamation_before_claim_and_after_write(tmp_path, monkeypatch):
    path, cg, _ = fixture(tmp_path, monkeypatch)
    before = json.loads((path / 'plan.json').read_bytes())
    before.update(dying_descendants=2, retained_descendants=14, planned_total_descendants=budget.demand(request(), 14))
    (path / 'plan.json').write_bytes(budget.encoded(before))
    def observe(req, expected_limit=None):
        dying = 0 if expected_limit is not None else 1
        retained = 12 + dying
        return dict(before, dying_descendants=dying, retained_descendants=retained,
                    planned_total_descendants=budget.demand(req, retained), prior_max_descendants=expected_limit or 512)
    monkeypatch.setattr(budget, 'observe', observe)
    assert budget.apply(budget.host.digest(path / 'plan.json'))['max_descendants'] == 4096
    assert (path / 'complete.json').exists() and (cg / 'cgroup.max.descendants').read_text() == '4096'


def test_post_write_dying_increase_is_rejected_even_below_original_plan_count(tmp_path, monkeypatch):
    path, _, _ = fixture(tmp_path, monkeypatch)
    before = json.loads((path / 'plan.json').read_bytes())
    before.update(dying_descendants=2, retained_descendants=14, planned_total_descendants=budget.demand(request(), 14))
    (path / 'plan.json').write_bytes(budget.encoded(before))
    def observe(req, expected_limit=None):
        dying = 1 if expected_limit is not None else 0
        return dict(before, dying_descendants=dying, retained_descendants=12 + dying,
                    planned_total_descendants=budget.demand(req, 12 + dying), prior_max_descendants=expected_limit or 512)
    monkeypatch.setattr(budget, 'observe', observe)
    with pytest.raises(ValueError, match='POSTCONDITION_CHANGED'): budget.apply(budget.host.digest(path / 'plan.json'))
    assert (path / 'claim.json').exists() and not (path / 'complete.json').exists()
