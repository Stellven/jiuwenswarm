"""Synthetic evidence only; no live jobs or factory-home writes."""
import json

import pytest

from jiuwenswarm.factory import export, story
from jiuwenswarm.factory.store import Store


@pytest.fixture
def chain(tmp_path, monkeypatch):
    from jiuwenswarm.factory import contract
    contracts = tmp_path / 'contracts'
    contracts.mkdir()
    (contracts / 'synthetic.json').write_text(json.dumps(dict(contract_id='synthetic', version=1,
        tolerance='byte-identical stdout', model={'path': '/models/Test-Q4_K_M.gguf'})))
    monkeypatch.setattr(contract, 'CONTRACTS', contracts)
    home = tmp_path / 'home'
    with Store(home) as store:
        store.create_task(dict(task_id='factory-synthetic', objective='repair config',
                               initial_run_config={'env': {'K': '48'}},
                               component_cc='factory.component', contract_id='synthetic', target='test-target'))
        store.advance_decision('factory-synthetic', 0, dict(action={'type': 'inspect', 'config': {'K': '48'}}, reason_for_change='Inspect first'))
        store.append_observation('factory-synthetic', dict(obs_id='failure', kind='inspect',
            error={'code': 'CONFIG_REJECTED', 'message': 'invalid K=48 (range 1..32)'}, values={'state': 'failed'}))
        store.advance_decision('factory-synthetic', 1, dict(action={'type': 'build', 'config': {'K': '8'}},
            evidence_ids=['failure'], reason_for_change='Repair rejected setting'))
        store.create_attempt('factory-synthetic', dict(attempt_id='build', kind='build', idem_key='k', fingerprint='fp',
            request={'source': {'commit': 'a'*40}}))
        store.transition_attempt('factory-synthetic', 'build', 'running')
        store.transition_attempt('factory-synthetic', 'build', 'succeeded')
        store.append_observation('factory-synthetic', dict(obs_id='built', kind='build_result',
            host_run={'attempt_id': 'build'}, values={'status': 'success', 'image_id': 'sha256:'+'b'*64, 'build_wall_seconds': 2}))
        store.put_artifact('factory-synthetic', 'do-not-dump-this-id', b'abc', 'text/plain', 'build')
        store.add_evaluation('factory-synthetic', dict(eval_id='eval', contract_id='synthetic', contract_version='1',
            contract={}, inputs={}, correctness='pass', execution_outcome='ok', evidence_completeness='complete'))
        store.advance_decision('factory-synthetic', 2, dict(action={'type': 'accept'}, reason_for_change='Measured success'))
    return home


def test_story_order_failure_diff_and_plain(chain):
    data = story.load_source('factory-synthetic', chain)
    events = story.build_events(data)
    assert [e['created'] for e in events] == sorted(e['created'] for e in events)
    output = story.render_story(data, plain=True)
    assert '✗' in output and 'CONFIG_REJECTED' in output
    assert '48 → 8' in output and 'replan/build' in output
    assert output.index('CONFIG_REJECTED') < output.index('48 → 8') < output.index('Measured success')
    assert 'chain: component ✓ → commit ✓ → build ✓ → image ✓' in output
    assert '1 artifacts · 3 bytes' in output
    assert '\x1b' not in output
    assert max(map(len, output.splitlines())) <= 100
    assert sum(e['kind'] == 'build' and 'durable job' in e['summary'] for e in events) == 3


def test_bundle_store_same_renderer(chain, tmp_path, monkeypatch):
    monkeypatch.setattr(export, 'command', lambda args: {'available': False, 'error': 'offline'})
    bundle = export.export_task('factory-synthetic', tmp_path / 'bundle', chain)
    assert story.render_story(story.load_source(str(bundle)), True) == story.render_story(story.load_source('factory-synthetic', chain), True)


def test_unknown_records(chain):
    data = story.load_source('factory-synthetic', chain)
    data['future_records'] = [{'created': data['tasks'][0]['created'], 'message': 'new evidence'}]
    data['events'].append({'kind': 'future-event', 'cursor': 999, 'created': 1})
    output = story.render_story(data, True)
    assert 'new evidence' in output and 'future-event' in output


def test_cli_json_and_readonly(chain, monkeypatch, capsys):
    from jiuwenswarm.factory.cli import main
    monkeypatch.setattr(Store, '__init__', lambda *a, **k: pytest.fail('mutating Store initialized'))
    before = {p.name: p.read_bytes() for p in chain.glob('factory.sqlite*')}
    main(['--home', str(chain), 'story', 'factory-synthetic', '--json'])
    assert any(e['mark'] == '✗' for e in json.loads(capsys.readouterr().out))
    assert before == {p.name: p.read_bytes() for p in chain.glob('factory.sqlite*')}


def test_follow_append_only(chain, monkeypatch, capsys):
    data = story.load_source('factory-synthetic', chain)
    final = json.loads(json.dumps(data))
    data['decisions'] = data['decisions'][:-1]
    data['_meta']['outcome'] = None
    sources = iter([data, final])
    monkeypatch.setattr(story, 'load_source', lambda *args: next(sources))
    sleeps = []
    monkeypatch.setattr(story.time, 'sleep', sleeps.append)
    story.show_story('factory-synthetic', chain, plain=True, follow=True)
    output = capsys.readouterr().out
    assert sleeps == [2]
    assert output.count('factory ·') == 1
    assert output.count('CONFIG_REJECTED') == 1
    assert output.count('Measured success') == 1
    assert output.count('chain:') == 1


def test_color_policy(monkeypatch):
    monkeypatch.setattr(story.sys.stdout, 'isatty', lambda: True)
    monkeypatch.delenv('NO_COLOR', raising=False)
    assert '\x1b[31m' in story.paint('✗ failed')
    assert '\x1b' not in story.paint('✗ failed', True)
    monkeypatch.setenv('NO_COLOR', '')
    assert '\x1b' not in story.paint('✓ success')
