"""Spark hardware and bridge identity checks; these do not claim GPU execution."""
import json
from pathlib import Path
import subprocess
import sys
import pytest

from jiuwenswarm.factory.targets import labels, profile, validate_image
from jiuwenswarm.factory.bridge import digest, handle
from jiuwenswarm.factory.builder import Builder
from jiuwenswarm.factory.jobs import KeyConflict
from jiuwenswarm.factory.store import Store

@pytest.mark.parametrize('target', ['spark-gb10', 'jetson-orin'])
def test_target_admission(target):
    row = dict(Architecture='arm64', Config={'Labels':labels(target)})
    assert validate_image(target, row, target) == target
    other = 'jetson-orin' if target == 'spark-gb10' else 'spark-gb10'
    with pytest.raises(ValueError): validate_image(other, row, target)
    row['Architecture'] = 'amd64'
    with pytest.raises(ValueError): validate_image(target, row, target)

def test_spark_requires_cuda_and_sm():
    row = dict(Architecture='arm64', Config={'Labels':labels('spark-gb10')})
    for key in ('factory.target.cuda','factory.target.sm'):
        bad=json.loads(json.dumps(row));bad['Config']['Labels'][key]='wrong'
        with pytest.raises(ValueError):validate_image('spark-gb10',bad)
    with pytest.raises(ValueError):profile({'profile':'spark-gb10','cuda':'12.6'})
    with pytest.raises(ValueError):profile('unknown')

def test_target_task_validation(tmp_path):
    with Store(tmp_path/'s') as s:
        with pytest.raises(ValueError):s.create_task(dict(task_id='bad',objective='bad',target={'profile':'unknown'}))
        s.create_task(dict(task_id='spark',objective='spark',target={'profile':'spark-gb10'}))
        with pytest.raises(ValueError,match='differs'):Builder(s).submit('spark',dict(target='jetson-orin'),'mismatch')

def test_bridge_replay_conflict_and_ownership(tmp_path, monkeypatch):
    workspace=tmp_path; queue=tmp_path/'queue';queue.mkdir()
    with Store(workspace/'port-store') as s:
        s.create_task(dict(task_id='t',objective='identity'))
        argv=[sys.executable,'-m','jiuwenswarm.factory.spark_probe','--attempt','{attempt_id}']
        a=s.create_attempt('t',dict(kind='probe',idem_key='one',fingerprint='one',request={},resources={'argv':argv,'job_class':'cpu','timeout_s':5}))
        command=[v.replace('{attempt_id}',a['attempt_id']) for v in argv]
        envfile=queue/'env.json';envfile.write_text(json.dumps({'BUILD_JOBS':'8'}))
        job=dict(id='job-abc',name='factory:'+a['attempt_id'],argv=command,timeout=5,**{'class':'cpu'},env_file=str(envfile))
        (queue/'job-abc.json').write_text(json.dumps(job))
        packet=dict(operation='queue',qdir=str(queue),args=['submit','--class','cpu','--name',job['name'],'--timeout','5','--',*command],env={'BUILD_JOBS':'8'})
        assert handle(packet,workspace,queue,tmp_path/'jobq')['stdout']=='job-abc\n'
        job['argv']=[*command,'changed'];(queue/'job-abc.json').write_text(json.dumps(job))
        with pytest.raises(ValueError,match='conflicts'):handle(packet,workspace,queue,tmp_path/'jobq')
        packet['args']=['cancel','job-abc']
        with pytest.raises(ValueError,match='unowned'):handle(packet,workspace,queue,tmp_path/'jobq')
        packet['args']=['submit','--class','cpu','--name','factory:'+'f'*32,'--timeout','5','--',*command]
        with pytest.raises(ValueError,match='outside'):handle(packet,workspace,queue,tmp_path/'jobq')

def test_hash_binds_environment_and_deadline():
    a={'argv':['x'],'env':{'BUILD_JOBS':'8'},'timeout':5400}
    assert digest(a)!=digest(a|{'timeout':1})
    assert digest(a)!=digest(a|{'env':{'BUILD_JOBS':'4'}})
