"""Corruption tests for the independent recorded-result verifier."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

module_path=Path(__file__).resolve().parents[2]/'deploy/spark/check_engine_results.py'
spec=importlib.util.spec_from_file_location('recorded_checks',module_path)
checks=importlib.util.module_from_spec(spec);spec.loader.exec_module(checks)


def save(path,value):path.write_text(json.dumps(value))


@pytest.fixture
def cell(tmp_path):
    root=tmp_path/'cell';engine=root/'engine';engine.mkdir(parents=True)
    image='sha256:'+'a'*64;cid='b'*64
    cfg=dict(args=['--experts','6'],environment={'STRATA_DS4_REUSE':'0'},image=image,requests=[{}],pins={})
    before=dict(Id=cid,Image=image,HostConfig=dict(Memory=104*2**30,MemorySwap=104*2**30,NanoCpus=8_000_000_000,ReadonlyRootfs=True,NetworkMode='none',Privileged=False),Mounts=[dict(Type='bind',RW=False)],Config=dict(Env=['STRATA_DS4_REUSE=0']))
    final=before|dict(State=dict(Running=False,Pid=0,ExitCode=0,OOMKilled=False))
    save(engine/'inspect-created.json',before);save(engine/'inspect-final.json',final)
    stdout=b'READY 1024 stop\nT 17\nT 18\nDONE 2 2 2000.0 1000.0 length 0 0 0 0 0\n'
    stderr=b'ds4: experts per word: 6 (full quality)\n';wire=b'RSI_EXEC\nGEN 128 0,1\nQUIT\n'
    for name,data in [('stdout.log',stdout),('stderr.log',stderr),('stdin-wire.log',wire)]: (engine/name).write_bytes(data)
    events=[dict(sequence=i,stream=stream,offset=0,retained_bytes=len(data),truncated=False) for i,(stream,data) in enumerate([('stdin',wire),('stdout',stdout),('stderr',stderr)])]
    (engine/'pipe-events.jsonl').write_text(''.join(json.dumps(v)+'\n' for v in events))
    (engine/'samples.jsonl').write_text(json.dumps(dict(host_kib={'MemAvailable':16*2**20},memory_events=dict(oom=0,oom_kill=0,oom_group_kill=0)))+'\n')
    report=dict(reason='completed',quiescent=True,container_exit_code=0,container_oom_killed=False,container_id=cid,artifacts={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in engine.iterdir()})
    save(engine/'report.json',report)
    result=dict(status='success',collector=report,configuration=cfg,container_removed=True,input_identity_after={},requests=[dict(ids=[17,18],generated_tokens=2,prompt_tokens=2,native_decode_tps=2.0,native_prefill_tps=1.0)])
    save(root/'engine-result.json',result)
    return root


def mutate_result(root,callback):
    p=root/'engine-result.json';j=json.loads(p.read_text());callback(j);save(p,j)


def refresh_artifacts(root):
    p=root/'engine/report.json';report=json.loads(p.read_text())
    report['artifacts']={n:hashlib.sha256((root/'engine'/n).read_bytes()).hexdigest() for n in report['artifacts']}
    save(p,report);mutate_result(root,lambda r:r.update(collector=report))


def test_valid_record_is_not_a_scored_improvement(cell):
    r=checks.verify_cell(cell)
    assert r['total_generated_tokens']==2 and r['requests'][0]['decode_tps']==2.0
    assert r['semantic_accuracy']=='not_tested' and r['scored_ab_improvement']=='not_established'


@pytest.mark.parametrize('change', ['rate','ids','failed','cleanup','missing_file','truncated_jsonl','bad_swap','wrong_experts','oom','missing_done'])
def test_corruption_is_rejected(cell,change):
    if change=='rate':mutate_result(cell,lambda r:r['requests'][0].update(native_decode_tps=999.0))
    elif change=='ids':mutate_result(cell,lambda r:r['requests'][0].update(ids=[17,99]))
    elif change=='failed':mutate_result(cell,lambda r:r.update(status='failed'))
    elif change=='cleanup':mutate_result(cell,lambda r:r.update(container_removed=False))
    elif change=='missing_file':(cell/'engine/stdout.log').unlink()
    elif change=='truncated_jsonl':
        with (cell/'engine/samples.jsonl').open('a') as f:f.write('{"partial":')
        refresh_artifacts(cell)
    elif change=='bad_swap':
        p=cell/'engine/inspect-created.json';j=json.loads(p.read_text());j['HostConfig']['MemorySwap']+=1;save(p,j);refresh_artifacts(cell)
    elif change=='wrong_experts':mutate_result(cell,lambda r:r['configuration'].update(args=['--experts','5']))
    elif change=='oom':
        p=cell/'engine/inspect-final.json';j=json.loads(p.read_text());j['State']['OOMKilled']=True;save(p,j);refresh_artifacts(cell)
    elif change=='missing_done':
        p=cell/'engine/stdout.log';p.write_bytes(b'READY 1024 stop\nT 17\n');refresh_artifacts(cell)
    with pytest.raises(checks.InvalidEvidence):checks.verify_cell(cell)
