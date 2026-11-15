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


def test_deadline_refuses_before_runtime_or_auth_access(tmp_path,monkeypatch):
    before = set(tmp_path.iterdir())
    monkeypatch.setattr(mission.time,'time',lambda:mission.LATEST_STOP-10)
    with pytest.raises(ValueError,match='Insufficient time'):
        asyncio.run(mission.run(tmp_path,tmp_path/'missing-auth'))
    assert set(tmp_path.iterdir()) == before


def test_freeze_rejects_arbitrary_package_before_copy(tmp_path):
    evidence=tmp_path/'engine.json'
    evidence.write_text('{}')
    args=argparse.Namespace(root=tmp_path/'mission',engine_evidence=evidence,package=['gpu_kernel_lab'],extra_evidence=[])
    with pytest.raises(ValueError,match='bounded CPU'):
        mission.freeze(args)
    assert not args.root.exists()


def test_freeze_pins_extras_and_only_admitted_cpu_capabilities(tmp_path):
    evidence=tmp_path/'engine.json'
    evidence.write_text('{"scope":"manual-engine"}')
    extra=tmp_path/'later-prefill.json'
    extra.write_text('{"scope":"long-prefill-separate"}')
    args=argparse.Namespace(root=tmp_path/'mission',engine_evidence=evidence,package=[],extra_evidence=[extra])
    result=mission.freeze(args)
    assert result['frozen']
    manifest=mission.verify(args.root)
    assert manifest['extra_evidence'][0]['workspace_path']=='inputs/extra-1-later-prefill.json'
    assert manifest['engine_evidence_sha256']==mission.digest(evidence)
    declaration=yaml.safe_load((args.root/'runtime/jiuwenswarm/factory/ccs/memory_residency_lab/cc.yaml').read_text())
    assert set(declaration['capabilities'])=={'plan','verify'}
    assert not (args.root/'runtime/jiuwenswarm/factory/ccs/gpu_kernel_lab').exists()
    task=json.loads((args.root/'task.json').read_text())
    assert task['constraints']['mission']['latest_stop_utc']=='2026-11-15T08:00:00+00:00'
    (args.root/'factory/agent-workspace/inputs/extra-1-later-prefill.json').write_text('{"changed":true}')
    with pytest.raises(ValueError,match='Frozen evidence'):
        mission.verify(args.root)


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
