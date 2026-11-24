import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from jiuwenswarm.factory.store import Store


@pytest.fixture
def home(tmp_path):
    home = tmp_path / 'store'
    with Store(home) as store:
        store.create_task({'task_id': 'a', 'objective': 'measure'})
        store.create_task({'task_id': 'b', 'objective': 'compare'})
    return home


def invoke(home, capability, inputs, *, extra_env=None, output_dir=None):
    env = dict(os.environ, FACTORY_HOME=str(home), FACTORY_TASK_ID='a', FACTORY_READ_TASKS='', FACTORY_WORKSPACE='')
    env.update(extra_env or {})
    packet = dict(call='call', attempt=1, capability=capability, inputs=inputs,
                  output_dir=str(output_dir or home.parent / 'out'), resources={})
    result = subprocess.run([sys.executable, '-m', 'jiuwenswarm.factory.api', capability],
                            input=json.dumps(packet), text=True, capture_output=True, env=env, timeout=20)
    assert result.returncode == 0, result.stderr
    assert not result.stderr
    # json.loads also verifies that stdout is exactly one process result.
    return json.loads(result.stdout)


def test_api_query_bounded(home):
    with Store(home) as store:
        for i in range(60):
            store.append_observation('a', {'kind': 'measurement', 'values': {'index': i, 'log': 'x' * 1000}})
    assert invoke(home, 'evidence.query', {'limit': 51})['error']['code'] == 'INVALID_INPUT'
    result = invoke(home, 'evidence.query', {})
    assert result['outcome'] == 'ok'
    assert len(result['outputs']['items']) == 50
    assert all(len(item['summary']) <= 300 for item in result['outputs']['items'])
    assert all(set(item) == {'id', 'type', 'kind', 'summary', 'created'} for item in result['outputs']['items'])
    following = invoke(home, 'evidence.query', {'since': result['outputs']['cursor']})
    assert len(following['outputs']['items']) == 11


def test_api_publish_decision_cas(home):
    first = invoke(home, 'evidence.publish', {'type': 'decision', 'expected_rev': 0, 'record': {'hypothesis': 'measure first'}})
    assert first['outputs']['rev'] == 1
    stale = invoke(home, 'evidence.publish', {'type': 'decision', 'expected_rev': 0, 'record': {'hypothesis': 'stale'}})
    assert stale['error']['code'] == 'STALE_REVISION'
    second = invoke(home, 'evidence.publish', {'type': 'decision', 'record': {'expected_rev': 1, 'reason_for_change': 'timing'}})
    assert second['outputs']['rev'] == 2
    assert second['outputs']['parent_rev'] == 1
    assert invoke(home, 'evidence.publish', {'type': 'decision', 'record': {}})['error']['code'] == 'INVALID_INPUT'


def test_api_observation_and_artifact_roundtrip(home):
    artifact = invoke(home, 'evidence.publish', {'type': 'artifact', 'record': {'artifact_id': 'blob', 'text': 'z' * 70000}})
    assert artifact['outcome'] == 'ok'
    read = invoke(home, 'evidence.read', {'id': 'blob'})['outputs']
    assert len(read['text_preview'].encode()) <= 65536
    assert read['preview_truncated'] is True
    assert read['sha256'] == artifact['outputs']['sha256']
    assert not Path(read['location']).is_absolute()
    assert str(home) not in json.dumps(read)
    obs = invoke(home, 'evidence.publish', {'type': 'observation', 'record': {'obs_id': 'timing', 'source_artifacts': ['blob'], 'kind': 'timing', 'values': {'seconds': 2}}})
    assert invoke(home, 'evidence.read', {'id': 'timing'})['outputs'] == obs['outputs']
    assert invoke(home, 'evidence.publish', {'type': 'artifact', 'record': {'artifact_id': 'blob', 'text': 'different'}})['error']['code'] == 'ARTIFACT_CONFLICT'
    assert invoke(home, 'evidence.read', {'id': 'missing'})['error']['code'] == 'NOT_FOUND'


def test_api_path_containment(home, tmp_path):
    out = tmp_path / 'out'
    workspace = tmp_path / 'workspace'
    out.mkdir()
    workspace.mkdir()
    (out / 'result').write_text('result')
    (workspace / 'source').write_text('source')
    outside = tmp_path / 'outside'
    outside.write_text('private')
    (out / 'link').symlink_to(outside)
    for path in ('result', str(workspace / 'source')):
        response = invoke(home, 'evidence.publish', {'type': 'artifact', 'record': {'path': path}}, extra_env={'FACTORY_WORKSPACE': str(workspace)}, output_dir=out)
        assert response['outcome'] == 'ok'
    for path in (str(outside), '../outside', 'link'):
        response = invoke(home, 'evidence.publish', {'type': 'artifact', 'record': {'path': path}}, output_dir=out)
        assert response['error']['code'] == 'SCOPE_DENIED'
        assert str(tmp_path) not in response['error']['message']


def test_api_scopes(home):
    with Store(home) as store:
        store.append_observation('b', {'obs_id': 'private', 'values': {'value': 1}})
    assert invoke(home, 'evidence.read', {'id': 'private', 'task_id': 'b'})['error']['code'] == 'SCOPE_DENIED'
    granted = {'FACTORY_READ_TASKS': 'b'}
    assert invoke(home, 'evidence.read', {'id': 'private'}, extra_env=granted)['outcome'] == 'ok'
    assert invoke(home, 'evidence.read', {'id': 'private', 'task_id': 'b'}, extra_env=granted)['outcome'] == 'ok'
    assert invoke(home, 'evidence.query', {'task_id': 'b'}, extra_env=granted)['outcome'] == 'ok'
    assert invoke(home, 'evidence.publish', {'type': 'observation', 'record': {'task_id': 'b'}}, extra_env=granted)['error']['code'] == 'SCOPE_DENIED'
    assert invoke(home, 'evidence.query', {}, extra_env={'FACTORY_TASK_ID': ''})['error']['code'] == 'INVALID_INPUT'


@pytest.mark.parametrize('capability,inputs', [
    ('evidence.query', {'limit': True}), ('evidence.query', {'since': -1}),
    ('evidence.query', {'kinds': 'observation'}), ('evidence.query', {'text': 3}),
    ('evidence.publish', {'type': 'observation', 'record': {'interpretation': 'no'}}),
    ('evidence.read', {'id': []}), ('unknown', {}),
])
def test_api_invalid_inputs(home, capability, inputs):
    assert invoke(home, capability, inputs)['error']['code'] == 'INVALID_INPUT'


def test_human_cli(tmp_path):
    task_file = tmp_path / 'task.json'
    task_file.write_text(json.dumps({'task_id': 'cli', 'objective': 'measure'}))
    prefix = [sys.executable, '-m', 'jiuwenswarm.factory.store', '--home', str(tmp_path / 'store')]
    for command in (['init-task', str(task_file)], ['show', 'cli'], ['dump', 'cli']):
        process = subprocess.run(prefix + command, capture_output=True, text=True, timeout=20)
        assert process.returncode == 0, process.stderr
        assert not process.stderr
        assert json.loads(process.stdout)
