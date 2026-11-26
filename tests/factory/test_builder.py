import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from jiuwenswarm.factory.api import dispatch
from jiuwenswarm.factory.builder import Builder
from jiuwenswarm.factory.build_job import PreparationError, prepare
from jiuwenswarm.factory.jobs import KeyConflict
from jiuwenswarm.factory.store import ScopeDenied
from conftest import until


@pytest.fixture
def request_build(tmp_path, monkeypatch):
    source = tmp_path / 'source'
    source.mkdir()
    def git(*args):
        return subprocess.run(['git', '-C', str(source), *args], capture_output=True,
                              text=True, check=True).stdout.strip()
    git('init')
    (source / 'input').write_text('source')
    git('add', 'input')
    git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-m', 'fixture')
    tools = tmp_path / 'tools'
    tools.mkdir()
    for name in ('nvcc', 'gcc', 'cmake', 'ninja', 'ccache', 'dpkg-query'):
        tool = tools / name
        tool.write_text('#!/bin/sh\necho fake-' + name + '\n')
        tool.chmod(0o755)
    # The fake sg consumes the same prefix that production must pass to jobq.
    sg = tools / 'sg'
    sg.write_text('#!/bin/sh\nexec /bin/sh -c "$3"\n')
    sg.chmod(0o755)
    docker = tools / 'docker'
    docker.write_text('#!/bin/sh\necho "$*" >> "$FAKE_DOCKER_LOG"\nif [ "$1" = image ] && [ "$FAKE_CACHE_MISS" = 1 ]; then exit 1; fi\necho fake-docker\n')
    docker.chmod(0o755)
    monkeypatch.setenv('PATH', str(tools) + ':' + os.environ['PATH'])
    monkeypatch.setenv('FAKE_DOCKER_LOG', str(tmp_path / 'docker.log'))
    engine = tmp_path / 'fake_engine.py'
    engine.write_text('''import argparse,json,os,pathlib,sys,time
p=argparse.ArgumentParser()
for a in ('target','source','commit','tag','out','patch'): p.add_argument('--'+a)
a=p.parse_args()
out=pathlib.Path(a.out)
assert not out.exists()
out.mkdir()
print('fake build stdout')
print('fake build stderr',file=sys.stderr)
r=dict(schema_version=2,status='failed' if os.environ.get('FAKE_BUILD_FAIL') else 'success',failure_stage='compile' if os.environ.get('FAKE_BUILD_FAIL') else None,image={'Id':'sha256:fake'},source={'commit':a.commit,'tree':'tree'},patch_sha256=None,toolchain={'nvcc':'fake'},base_images={},build_wall_seconds=.01)
(out/'build-record.json').write_text(json.dumps(r))
sys.exit(1 if os.environ.get('FAKE_BUILD_FAIL') else 0)
''')
    monkeypatch.setenv('FACTORY_BUILD_ENGINE', str(engine))
    recipe = tmp_path / 'Dockerfile'
    recipe.write_text('ARG BASE_RUNTIME=nvcr.io/nvidia/l4t-cuda:12.6.11-runtime@sha256:' + 'a' * 64 + '\n')
    monkeypatch.setenv('FACTORY_BUILD_RECIPE', str(recipe))
    monkeypatch.setattr('jiuwenswarm.factory.builder.RECIPE', recipe)
    monkeypatch.setattr('jiuwenswarm.factory.build_job.RECIPE', recipe)
    return dict(target='jetson-orin', source=dict(path=str(source), commit=git('rev-parse', 'HEAD')),
                tag='factory/llamacpp:test')


def test_builder_ingests_and_reuses_success(store, request_build, worker):
    builder = Builder(store)
    first = builder.submit('t', request_build, 'first')
    worker()
    assert until(builder.jobs, first['attempt_id'])['state'] == 'succeeded'
    result = builder.result(first['attempt_id'])
    assert len(result['result_refs']) == 9
    obs = store.read('t', first['attempt_id'] + ':build-result')
    assert obs['kind'] == 'build_result'
    assert obs['values']['image_id'] == 'sha256:fake'
    receipt = json.loads(store.artifact_bytes('t', first['attempt_id'] + ':receipt'))
    assert receipt['request_fingerprint'] == first['fingerprint']
    assert receipt['image_id'] == obs['values']['image_id']
    assert receipt['prep']['sha256'] == store.read_artifact('t', first['attempt_id'] + ':prep')['sha256']
    assert builder.submit('t', request_build, 'reuse')['attempt_id'] == first['attempt_id']
    assert len(list(builder.jobs.jobq_dir.glob('job-*.json'))) == 1


@pytest.mark.parametrize('change', ['tag', 'target', 'patch', 'env', 'commit'])
def test_changed_inputs_no_reuse(store, request_build, worker, tmp_path, change):
    builder = Builder(store)
    first = builder.submit('t', request_build, 'first')
    worker()
    assert until(builder.jobs, first['attempt_id'])['state'] == 'succeeded'
    request = json.loads(json.dumps(request_build))
    if change == 'tag':
        request['tag'] = 'factory/llamacpp:changed'
    elif change == 'patch':
        patch = tmp_path / 'patch'
        patch.write_text('patch')
        request['patch'] = str(patch)
    elif change == 'env':
        request['env'] = {'BUILD_JOBS': '2'}
    elif change == 'target':
        request['target'] = 'x86-5070ti'
        with pytest.raises(ValueError):
            builder.submit('t', request, 'changed')
        return
    else:
        source = Path(request['source']['path'])
        (source / 'input').write_text('changed')
        subprocess.run(['git', '-C', str(source), 'add', '.'], check=True)
        subprocess.run(['git', '-C', str(source), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-m', 'changed'], check=True, capture_output=True)
        request['source']['commit'] = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    second = builder.submit('t', request, 'changed')
    assert second['attempt_id'] != first['attempt_id']
    assert second['fingerprint'] != first['fingerprint']


def test_failed_attempt_not_reused(store, request_build, worker, monkeypatch):
    monkeypatch.setenv('FAKE_BUILD_FAIL', '1')
    builder = Builder(store)
    first = builder.submit('t', request_build, 'first')
    worker()
    assert until(builder.jobs, first['attempt_id'])['state'] == 'failed'
    assert builder.result(first['attempt_id'])['result_refs'] == []
    assert builder.submit('t', request_build, 'retry')['attempt_id'] != first['attempt_id']


def test_prep_missing_toolchain(store, request_build, tmp_path):
    builder = Builder(store)
    attempt = builder.submit('t', request_build, 'missing')
    request_path = Path(attempt['resources']['argv'][-1])
    # Direct worker process with a deliberately empty PATH: it must not launch
    # the fake build_engine, and it still must ingest structured failure evidence.
    empty = tmp_path / 'empty'
    empty.mkdir()
    env = dict(os.environ, PATH=str(empty), FACTORY_HOME=str(store.home))
    process = subprocess.run([sys.executable, '-m', 'jiuwenswarm.factory.build_job',
        '--task', 't', '--attempt', attempt['attempt_id'], '--request', str(request_path)],
        env=env, capture_output=True, text=True, timeout=15)
    assert process.returncode == 1, process.stderr
    prep = json.loads(store.artifact_bytes('t', attempt['attempt_id'] + ':prep'))
    assert prep['error'] == {'code': 'TOOLCHAIN_MISSING', 'tool': 'nvcc', 'path': str(empty)}
    assert not (store.home / 'builds' / attempt['attempt_id'] / 'engine').exists()
    assert store.read('t', attempt['attempt_id'] + ':build-result')['values']['failure_stage'] == 'prep'


def test_prep_pulls_only_digest(store, request_build, worker, monkeypatch, tmp_path):
    monkeypatch.setenv('FAKE_CACHE_MISS', '1')
    builder = Builder(store)
    first = builder.submit('t', request_build, 'miss')
    worker()
    assert until(builder.jobs, first['attempt_id'])['state'] == 'succeeded'
    prep = json.loads(store.artifact_bytes('t', first['attempt_id'] + ':prep'))
    assert prep['cache_hit'] is False
    commands = (tmp_path / 'docker.log').read_text().splitlines()
    pulls = [line for line in commands if line.startswith('pull ')]
    assert len(pulls) == 1 and '@sha256:' in pulls[0]


def test_builder_validation(store, request_build):
    builder = Builder(store)
    for updated in ({'tag': 'campaign/llamacpp:bad'}, {'target': 'other'}, {'deadline_s': -1}, {'env': {'SECRET': 'no'}}):
        with pytest.raises(ValueError):
            builder.submit('t', request_build | updated, 'bad')
    Path(request_build['source']['path'], 'untracked').write_text('dirty')
    with pytest.raises(ValueError):
        builder.submit('t', request_build, 'dirty')


def test_builder_api_dispatch(store, request_build):
    scoped = store.scoped('t')
    result = dispatch(scoped, 't', 'builder.submit', {'inputs': {'request': request_build, 'idem_key': 'api'}})
    assert set(result) == {'attempt_id', 'state', 'jobq_id'}
    assert result['state'] == 'queued'
    state = dispatch(scoped, 't', 'builder.status', {'inputs': {'attempt_id': result['attempt_id']}})
    assert state['jobq_id'] == result['jobq_id']
    store.create_task(dict(task_id='other', objective='scope'))
    with pytest.raises(ScopeDenied):
        dispatch(store.scoped('other', {'t'}), 'other', 'builder.cancel', {'inputs': {'attempt_id': result['attempt_id']}})
    cancelled = dispatch(scoped, 't', 'builder.cancel', {'inputs': {'attempt_id': result['attempt_id']}})
    assert cancelled['state'] == 'cancelled'
    assert dispatch(scoped, 't', 'builder.result', {'inputs': {'attempt_id': result['attempt_id']}})['result_refs'] == []


def test_reuse_key_is_durable(store, request_build, worker):
    builder = Builder(store)
    first = builder.submit('t', request_build, 'first')
    worker()
    until(builder.jobs, first['attempt_id'])
    assert builder.submit('t', request_build, 'reused')['attempt_id'] == first['attempt_id']
    with pytest.raises(KeyConflict):
        Builder(store).submit('t', request_build | {'tag': 'factory/llamacpp:changed'}, 'reused')


def test_completed_job_reused_without_prior_status(store, request_build, worker):
    builder = Builder(store)
    first = builder.submit('t', request_build, 'first')
    worker()
    result = subprocess.run([sys.executable, str(builder.jobs.jobq_bin), 'wait', first['jobq_id'], '--timeout', '10'],
                            capture_output=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert Builder(store).submit('t', request_build, 'reused')['attempt_id'] == first['attempt_id']


def test_spark_build_identity_binds_dependency_and_target(store, request_build):
    """Normalization records both clean source trees and the selected worker recipe."""
    builder = Builder(store)
    request = dict(request_build, target='spark-gb10', tag='factory/strata:test',
                   dependency=dict(request_build['source']))
    spark = builder._request(request)
    jetson = builder._request(request_build)
    assert spark['target'] == 'spark-gb10'
    assert spark['dependency']['commit'] == spark['source']['commit']
    assert spark['dependency']['tree'] == spark['source']['tree']
    assert spark['engine_sha256'] != jetson['engine_sha256']
    assert spark['recipe_sha256'] != jetson['recipe_sha256']
    from jiuwenswarm.factory.jobs import fingerprint
    def identity(value):return fingerprint('build',value,['worker'],'build',value['deadline_s'])
    changed = builder._request(request | {'env': {'BUILD_JOBS':'4'}})
    assert identity(changed) != identity(spark)
    with pytest.raises(ValueError,match='Dependency'):
        builder._request(request | {'dependency':dict(request['dependency'],commit='0'*40)})
    with pytest.raises(ValueError,match='90 minutes'):
        builder._request(request | {'deadline_s':5401})


def test_spark_image_check_is_opt_in_through_the_existing_node_grant(store, request_build):
    from jiuwenswarm.factory.scheduler import check_ceiling
    from scripts.factory.make_muse_2bit_v4_rev8 import _build_image

    builder = Builder(store)
    pinned = dict(request_build, target='spark-gb10', build_target='llama-server', delivery='image',
                  dependency=dict(request_build['source']))
    check_ceiling(_build_image(), 'builder', 'submit')
    assert 'verify_image' not in builder._request(pinned)
    assert builder._request(dict(pinned, verify_image=True))['verify_image'] is True
    for changes in ({'delivery': 'native'}, {'build_target': 'strata-dsv41'}, {'target': 'jetson-orin'},
                    {'verify_image': 'true'}):
        with pytest.raises(ValueError, match='verify_image'):
            builder._request({**pinned, 'verify_image': True, **changes})


@pytest.mark.parametrize('proof_present', [True, False])
def test_spark_worker_publishes_the_image_check_artifact(store, request_build, monkeypatch, proof_present):
    from jiuwenswarm.factory import build_job

    builder = Builder(store)
    request = builder._request(dict(request_build, target='spark-gb10', build_target='llama-server',
                                    dependency=dict(request_build['source']), verify_image=True))
    attempt = store.create_attempt('t', dict(kind='build', idem_key='fixture', fingerprint='fixture',
                                             request=request, resources={}))
    aid = attempt['attempt_id']
    image_id, digest = 'sha256:' + 'a' * 64, 'b' * 64
    proof = dict(status='passed', source_commit=request['source']['commit'], image_id=image_id, executable_sha256=digest)

    def engine(argv, **kwargs):
        assert '--verify-image' in argv
        out = Path(argv[argv.index('--out') + 1])
        out.mkdir()
        record = dict(status='success', image=dict(Id=image_id), executable_sha256=digest)
        if proof_present:
            record['image_check'] = proof
        (out / 'build-record.json').write_text(json.dumps(record))
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(build_job.subprocess, 'run', engine)
    assert build_job.run(store, 't', aid, request) == (0 if proof_present else 1)
    receipt = json.loads(store.artifact_bytes('t', aid + ':receipt'))
    if proof_present:
        assert receipt['image_check']['artifact_id'] == aid + ':image-check'
        assert receipt['executable_sha256'] == digest
        assert json.loads(store.artifact_bytes('t', aid + ':image-check')) == proof
    else:
        assert 'image_check' not in receipt
        assert store.read('t', aid + ':build-result')['error']['code'] == 'IMAGE_CHECK_RECORD_INVALID'
