"""Mission preparation/deadline boundaries only; never a provider or GPU call."""
import argparse
import asyncio
import importlib.util
import json
import os
from pathlib import Path

import pytest
import yaml

SPEC = importlib.util.spec_from_file_location('branch_mission', Path(__file__).resolve().parents[2] / 'scripts/factory_branch_mission.py')
mission = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mission)


def test_regular_evidence_rejects_links_pipes_and_oversize(tmp_path):
    evidence = tmp_path/'evidence.json'
    evidence.write_bytes(b'{"scope":"actual"}')
    assert mission.read_regular(evidence) == evidence.read_bytes()
    linked = tmp_path/'link.json'
    linked.symlink_to(evidence)
    with pytest.raises(OSError):
        mission.read_regular(linked)
    fifo = tmp_path/'fifo'
    os.mkfifo(fifo)
    with pytest.raises(ValueError,match='regular file'):
        mission.read_regular(fifo)
    with pytest.raises(ValueError,match='regular file'):
        mission.read_regular(evidence,max_bytes=1)


def policy_for(tmp_path, **updates):
    import subprocess
    evidence = tmp_path / 'engine.json'
    evidence.write_text('{"scope":"manual-engine"}')
    extra = tmp_path / 'later-prefill.json'
    extra.write_text('{"scope":"long-prefill-separate"}')
    policy = dict(schema='factory.cpu-campaign/1', campaign_id='fresh-cpu-investigation',
        deadline_utc='2099-11-15T08:00:00+00:00', objective='Decide which hypothesis merits a bounded followup.',
        source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=mission.SOURCE, text=True).strip(),
        packages=['branch_workbench', 'evidence', 'memory_residency_lab', 'evidence_digest_lab', 'numerical_investigation_lab'],
        limits=dict(max_turns=4, wall_clock_s=900, max_branches=4, branch_cpu_seconds=40,
                    minimum_start_seconds=60, max_experiments=0, max_builds=0, gpu_seconds=0),
        evidence=dict(engine=str(evidence), extra=[str(extra)]))
    policy.update(updates)
    return policy


def freeze_args(tmp_path, policy):
    path = tmp_path / 'spec.json'
    path.write_text(json.dumps(policy))
    return argparse.Namespace(root=tmp_path / 'mission', campaign_spec=path)


def test_deadline_refuses_before_runtime_or_auth_access(tmp_path, monkeypatch):
    policy = policy_for(tmp_path)
    args = freeze_args(tmp_path, policy)
    mission.freeze(args)
    monkeypatch.setattr(mission.time, 'time', lambda:mission.datetime.fromisoformat(policy['deadline_utc']).timestamp() - 10)
    before = mission.tree(args.root)
    with pytest.raises(ValueError, match='Insufficient time'):
        asyncio.run(mission.run(args.root, tmp_path / 'missing-auth'))
    assert mission.tree(args.root) == before


@pytest.mark.parametrize('change, message', [
    ({'packages':['branch_workbench', 'evidence', 'gpu_kernel_lab']}, 'bounded CPU'),
    ({'deadline_utc':'2026-11-15T08:00:00'}, 'absolute'),
    ({'deadline_utc':'2000-01-01T00:00:00+00:00'}, 'Expired'),
    ({'source_commit':''}, 'source_commit'),
    ({'campaign_id':'night-branch-jiuwen-v1'}, 'fresh'),
    ({'extra_authority':['gpu']}, 'fields/schema'),
])
def test_invalid_campaign_rejected_before_copy(tmp_path, change, message):
    args = freeze_args(tmp_path, policy_for(tmp_path, **change))
    with pytest.raises(ValueError, match=message):
        mission.freeze(args)
    assert not args.root.exists()


@pytest.mark.parametrize('limit, value', [('gpu_seconds',1), ('max_builds',1), ('max_experiments',1),
    ('max_turns',7), ('wall_clock_s',1501), ('branch_cpu_seconds',61), ('max_branches',9),
    ('minimum_start_seconds',True)])
def test_campaign_bounds_fail_closed(tmp_path, limit, value):
    policy = policy_for(tmp_path)
    policy['limits'][limit] = value
    args = freeze_args(tmp_path, policy)
    with pytest.raises(ValueError, match='bounded CPU campaign limit'):
        mission.freeze(args)
    assert not args.root.exists()


def test_freeze_pins_extras_and_only_admitted_cpu_capabilities(tmp_path):
    policy = policy_for(tmp_path)
    args = freeze_args(tmp_path, policy)
    result = mission.freeze(args)
    assert result['frozen']
    manifest = mission.verify(args.root)
    assert manifest['extra_evidence'][0]['workspace_path'] == 'inputs/extra-1-later-prefill.json'
    assert manifest['engine_evidence_sha256'] == mission.digest(Path(policy['evidence']['engine']))
    ccs = args.root / 'runtime/jiuwenswarm/factory/ccs'
    declaration = yaml.safe_load((ccs / 'memory_residency_lab/cc.yaml').read_text())
    assert set(declaration['capabilities']) == {'plan', 'verify'}
    assert {p.name for p in ccs.iterdir()} == set(policy['packages'])
    task = json.loads((args.root / 'task.json').read_text())
    assert task == mission.campaign_task(policy, manifest['input_sha256'])
    assert task['task_id'] == policy['campaign_id']
    assert 'at least two' not in task['objective']
    assert not (args.root / 'factory/agent-workspace/inputs/engine-raw').exists()
    (args.root / 'factory/agent-workspace/inputs/extra-1-later-prefill.json').write_text('{"changed":true}')
    with pytest.raises(ValueError, match='Frozen evidence'):
        mission.verify(args.root)


@pytest.mark.parametrize('mutation', ['deadline', 'effects', 'packages', 'input_added', 'runtime'])
def test_verify_rejects_changed_frozen_policy(tmp_path, mutation):
    args = freeze_args(tmp_path, policy_for(tmp_path))
    mission.freeze(args)
    if mutation == 'deadline':
        policy = json.loads((args.root / 'campaign.json').read_text())
        policy['deadline_utc'] = '2100-01-01T00:00:00+00:00'
        mission.dump(args.root / 'campaign.json', policy)
    elif mutation in {'effects', 'packages'}:
        task = json.loads((args.root / 'task.json').read_text())
        if mutation == 'effects':
            task['allowed_effects'].append('gpu')
        else:
            task['constraints']['mission']['selected_packages'].append('gpu_kernel_lab')
        mission.dump(args.root / 'task.json', task)
        # Updating task hash alone cannot authorize a policy change.
        manifest = json.loads((args.root / 'manifest.json').read_text())
        manifest['task_sha256'] = mission.digest(args.root / 'task.json')
        mission.dump(args.root / 'manifest.json', manifest)
    elif mutation == 'input_added':
        (args.root / 'factory/agent-workspace/inputs/unpinned.json').write_text('{}')
    else:
        (args.root / 'runtime/jiuwenswarm/factory/ccs/evidence_digest_lab/run.py').write_text('#changed')
    with pytest.raises(ValueError, match='Frozen'):
        mission.verify(args.root)


def test_existing_root_preserved_and_source_identity_checked(tmp_path):
    args = freeze_args(tmp_path, policy_for(tmp_path))
    args.root.mkdir()
    marker = args.root / 'historical-export'
    marker.write_text('retain exactly')
    with pytest.raises(ValueError, match='already exists'):
        mission.freeze(args)
    assert marker.read_text() == 'retain exactly'
    other = freeze_args(tmp_path, policy_for(tmp_path, source_commit='0'*40))
    other.root = tmp_path / 'fresh-root'
    with pytest.raises(ValueError, match='does not match'):
        mission.freeze(other)
    assert not other.root.exists()


def test_crash_receipts_are_typed_hashed_and_counted(tmp_path):
    import sqlite3
    root=tmp_path/'mission'
    database=root/'factory/ccstore/calls.sqlite'
    database.parent.mkdir(parents=True)
    with sqlite3.connect(database) as db:
        db.execute('CREATE TABLE calls (receipt TEXT)')
        db.executemany('INSERT INTO calls VALUES (?)',[(None,),('{bad',),('[]',),('null',),
            (json.dumps({'state':{},'capability':'status','release':'a'*64}),),
            (json.dumps({'state':'running','capability':'status','release':'a'*64}),)])
    report=mission.read_receipts(root)
    assert len(report['incomplete'])==6
    assert len(report['receipts'])==2
    assert all(len(row['sha256'])==64 for row in report['incomplete'])
    assert report['counts']['a'*64+'.status']=={'succeeded':0,'other':2}


def test_failed_exports_retain_minimal_primary_error(tmp_path,monkeypatch):
    root=tmp_path/'mission'
    class BrokenStore:
        def dump(self, task_id):
            raise RuntimeError('offline snapshot failure')
    monkeypatch.setattr(mission,'read_receipts',lambda root:(_ for _ in ()).throw(ValueError('broken receipts')))
    report=mission.export_run(root,BrokenStore(),{'error':{'type':'PrimaryModelFailure'}})
    retained=json.loads((root/'controller-result.json').read_text())
    assert retained['error']=={'type':'PrimaryModelFailure'}
    assert {row['stage'] for row in report['export_errors']} >= {'evidence-snapshot','native-receipts','branches','pareto'}
    assert Path(retained['retained_attempt']).is_file()


@pytest.mark.parametrize('field', ['allowed_effects', 'budget', 'constraints', 'source'])
def test_resume_rejects_persisted_policy_changes_before_auth(tmp_path, monkeypatch, field):
    import copy
    import jiuwenswarm.factory.controller as controller_module
    args = freeze_args(tmp_path, policy_for(tmp_path))
    mission.freeze(args)
    existing = json.loads((args.root / 'task.json').read_text())
    existing = copy.deepcopy(existing)
    if field == 'allowed_effects':
        existing[field].append('gpu')
    elif field == 'budget':
        existing[field]['max_turns'] += 1
    elif field == 'source':
        existing[field]['pre_integration_commit'] = '0'*40
    else:
        existing[field]['mission']['latest_stop_utc'] = '2100-01-01T00:00:00+00:00'
    class ChangedStore:
        closed = False
        def get_task(self, task_id):
            assert task_id == existing['task_id']
            return existing
        def close(self):
            self.closed = True
    store = ChangedStore()
    class FakeController:
        def __init__(self, **kwargs):
            self.store = store
    monkeypatch.setattr(mission, 'setup', lambda *args: None)
    monkeypatch.setattr(controller_module, 'Controller', FakeController)
    before = mission.tree(args.root)
    with pytest.raises(ValueError, match='Stored campaign policy changed on resume'):
        asyncio.run(mission.run(args.root, tmp_path / 'missing-auth'))
    assert store.closed
    assert mission.tree(args.root) == before


def test_historical_exports_are_read_only(tmp_path, monkeypatch, capsys):
    root = tmp_path / 'historical'
    (root / 'runtime').mkdir(parents=True)
    (root / 'launch.py').write_text('# historical launcher retained unchanged\n')
    mission.dump(root / 'task.json', {'task_id':mission.HISTORICAL_TASK_ID})
    mission.dump(root / 'manifest.json', dict(schema='factory.branch-mission/1',
        task_id=mission.HISTORICAL_TASK_ID, task_sha256=mission.digest(root / 'task.json'),
        launcher_sha256=mission.digest(root / 'launch.py'), runtime_files={}, input_sha256={}, packages=['evidence']))
    before = mission.tree(root)
    assert mission.verify(root)['schema'] == 'factory.branch-mission/1'
    with pytest.raises(ValueError, match='Historical campaign is read-only'):
        asyncio.run(mission.run(root, tmp_path / 'missing-auth'))
    monkeypatch.setattr(mission.sys, 'argv', ['launcher', '--root', str(root), 'status'])
    mission.main()
    assert json.loads(capsys.readouterr().out)['task_id'] == mission.HISTORICAL_TASK_ID
    assert mission.tree(root) == before
