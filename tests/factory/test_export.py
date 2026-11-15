import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

from jiuwenswarm.factory import export
from jiuwenswarm.factory.store import Store


def test_read_only_export_roundtrip(tmp_path, monkeypatch):
    home = tmp_path / 'store'
    with Store(home) as store:
        store.create_task(dict(task_id='t', objective='measure', contract_id='qwen36-greedy-v1'))
        store.advance_decision('t', 0, {'hypothesis': 'first'})
        store.advance_decision('t', 1, {'hypothesis': 'second'})
        store.append_observation('t', dict(obs_id='o', values={'evidence': 'measured'}))
        store.create_attempt('t', dict(attempt_id='b', kind='build', idem_key='key', fingerprint='fp', request={}))
        store.transition_attempt('t', 'b', 'running')
        store.transition_attempt('t', 'b', 'succeeded')
        store.put_artifact('t', 'raw', b'unchanged\x00', 'application/octet-stream', 'b')
        store.put_artifact('t', 'secret', b'contact a.person@example.test; sk-abcdefghijklmnopqrstuv', 'text/plain', 'b')
        store.put_artifact('t', 'large', b'x'*100, 'text/plain', 'b')
        store.add_evaluation('t', dict(eval_id='run:evaluation', contract_id='qwen36-greedy-v1', contract_version='1', contract={}, inputs={}, execution_outcome='ok', correctness='pass', evidence_completeness='complete'))
    sessions = home / 'sessions'
    sessions.mkdir()
    (sessions / 't.jsonl').write_text(json.dumps({'access_token': 'confidential', 'text': 'a.person@example.test'}) + '\n')
    # Lower only artifact limit; other evidence files may be omitted honestly.
    monkeypatch.setattr(export, 'LIMIT', 90)
    monkeypatch.setattr(export, 'command', lambda argv: {'available': False, 'error': 'offline'})
    before = (home / 'factory.sqlite').read_bytes()
    out = export.export_task('t', tmp_path / 'bundle', home)
    assert (home / 'factory.sqlite').read_bytes() == before
    assert export.verify(out) > 10
    decisions = json.loads((out / 'records/decisions.json').read_text())
    assert [r['rev'] for r in decisions] == [1, 2]
    attempts = json.loads((out / 'records/attempts.json').read_text())
    assert [s['state'] for s in attempts[0]['history']] == ['queued', 'running', 'succeeded']
    artifacts = {a['artifact_id']: a for a in json.loads((out / 'artifacts.json').read_text())}
    assert (out / artifacts['raw']['exported_path']).read_bytes() == b'unchanged\x00'
    assert artifacts['secret']['sha256'] != artifacts['secret']['exported_sha256']
    assert artifacts['large']['exported_path'] is None
    assert 'confidential' not in (out / 'session.jsonl').read_text()
    (out / 'records/tasks.json').write_text('tampered')
    with pytest.raises(ValueError, match='Manifest'):
        export.verify(out)


@pytest.mark.parametrize('payload', [b'Bearer abcdefghijklmnopqrstuvwxyz12345', b'sk-abcdefghijklmnopqrstuv', b'a@example.com', b'eyJabcdefghijk.abcdefghijklmn.abcdefghijklmn', b'token=abcdefghijklmnopqrstuv'])
def test_verify_fails_closed_for_secrets(tmp_path, payload):
    (tmp_path / 'leak').write_bytes(payload)
    (tmp_path / 'MANIFEST.json').write_text(json.dumps({'leak': hashlib.sha256(payload).hexdigest()}))
    with pytest.raises(ValueError, match='Secrets scan failed'):
        export.verify(tmp_path)


def test_digest_failure_never_publishes_bundle(store, tmp_path):
    artifact = store.put_artifact('t', 'raw', b'evidence', 'text/plain', None)
    (store.home / artifact['location']).write_bytes(b'tampered')
    with pytest.raises(ValueError, match='digest mismatch'):
        export.export_task('t', tmp_path / 'bundle', store.home)
    assert not (tmp_path / 'bundle').exists()
    assert not list(tmp_path.glob('.export-*'))


def test_cli_export_bypasses_mutating_controller(store, tmp_path, monkeypatch):
    from jiuwenswarm.factory.cli import main
    monkeypatch.setattr(Store, '__init__', lambda *a, **k: pytest.fail('Store opened for writing'))
    main(['--home', str(store.home), 'export', 't', '--out', str(tmp_path / 'cli')])
    assert export.verify(tmp_path / 'cli')


def test_build_source_and_image_fallback(store, tmp_path, monkeypatch):
    source = tmp_path / 'checkout'
    source.mkdir()
    request = {'source': {'path': str(source), 'commit': 'a'*40}}
    store.create_attempt('t', dict(attempt_id='build', kind='build', idem_key='key', fingerprint='fp', request=request))
    store.put_artifact('t', 'build:build-record', json.dumps({'image': {'Id': 'sha256:'+'a'*64, 'Architecture': 'arm64'}}).encode(), 'application/json', 'build')
    def command(argv):
        if argv[0] == 'docker':
            return {'available': False, 'error': 'permission denied'}
        return {'available': True, 'stdout': 'git identity'}
    monkeypatch.setattr(export, 'command', command)
    out = export.export_task('t', tmp_path / 'bundle', store.home)
    images = json.loads((out / 'image-identity.json').read_text())
    assert images[0]['provenance'] == 'build record only'
    assert images[0]['image']['Architecture'] == 'arm64'
    assert (out / 'source/build.diff').read_text() == 'git identity'
    assert export.verify(out)


def test_explicit_contract_path_and_internal_evaluation_id_export(tmp_path,monkeypatch):
    snapshot={'contract_id':'explicit-v1','version':1,'tolerance':'byte-identical stdout'}
    contract=tmp_path/'operator-contract.json';contract.write_text(json.dumps(snapshot))
    home=tmp_path/'home'
    with Store(home) as s:
        s.create_task({'task_id':'t','objective':'explicit file contract','contract_id':str(contract)})
        s.add_evaluation('t',dict(eval_id='e',contract_id='explicit-v1',contract_version='1',contract=snapshot,
            inputs={},correctness='not_evaluated',execution_outcome='ok',evidence_completeness='complete'))
    monkeypatch.setattr(export,'command',lambda argv:{'available':False,'error':'offline'})
    before=(home/'factory.sqlite').read_bytes()
    out=export.export_task('t',tmp_path/'bundle',home)
    assert export.verify(out)>0
    origins=json.loads((out/'contract-origins.json').read_text())
    assert any(r['source']=='evaluation_snapshot' and r['contract_id']=='explicit-v1' for r in origins)
    assert (home/'factory.sqlite').read_bytes()==before


def test_optional_loop_ledger_export_is_decoded_scoped_and_read_only(tmp_path, monkeypatch):
    home=tmp_path/'home'
    with Store(home) as store:
        for task in ('mine','other'):
            store.create_task(dict(task_id=task,objective='scoped loop evidence'))
        with store._transaction():
            store._db.execute('CREATE TABLE factory_loop_policy (task_id TEXT PRIMARY KEY, policy TEXT NOT NULL, started REAL NOT NULL, stopped TEXT)')
            store._db.execute('CREATE TABLE factory_loop_cycles (task_id TEXT NOT NULL, cycle_id TEXT NOT NULL, number INTEGER NOT NULL, record TEXT NOT NULL, PRIMARY KEY(task_id,cycle_id))')
            for task in ('mine','other'):
                store._db.execute('INSERT INTO factory_loop_policy VALUES (?,?,?,?)',
                    (task,json.dumps({'max_cycles':2,'templates':[{'id':task}]}),10,None))
                # Deliberate reverse insertion verifies cycle order, not rowid order.
                for number in (2,1):
                    store._db.execute('INSERT INTO factory_loop_cycles VALUES (?,?,?,?)',
                        (task,'cycle-'+str(number),number,json.dumps({'state':'collected','child_task_id':task+'-child-'+str(number)})))
    before=(home/'factory.sqlite').read_bytes()
    monkeypatch.setattr(Store,'__init__',lambda *a,**kw:pytest.fail('Read-only export initialized Store'))
    monkeypatch.setattr(export,'command',lambda argv:{'available':False,'error':'offline'})
    records=export.snapshot(home,'mine')
    assert records['factory_loop_policy']==[dict(task_id='mine',policy={'max_cycles':2,'templates':[{'id':'mine'}]},started=10,stopped=None)]
    cycles=records['factory_loop_cycles']
    assert [c['number'] for c in cycles]==[1,2]
    assert all(c['task_id']=='mine' and c['record']['child_task_id'].startswith('mine-child-') for c in cycles)
    out=export.export_task('mine',tmp_path/'bundle',home)
    assert json.loads((out/'records/factory_loop_policy.json').read_text())==records['factory_loop_policy']
    assert json.loads((out/'records/factory_loop_cycles.json').read_text())==cycles
    assert export.verify(out)>0
    assert (home/'factory.sqlite').read_bytes()==before


def test_legacy_export_does_not_create_optional_loop_tables(tmp_path, monkeypatch):
    home=tmp_path/'home'
    with Store(home) as store:
        store.create_task(dict(task_id='legacy',objective='before loop schema'))
    before=(home/'factory.sqlite').read_bytes()
    monkeypatch.setattr(Store,'__init__',lambda *a,**kw:pytest.fail('Read-only export initialized Store'))
    records=export.snapshot(home,'legacy')
    assert 'factory_loop_policy' not in records
    assert 'factory_loop_cycles' not in records
    out=export.export_task('legacy',tmp_path/'bundle',home)
    assert not (out/'records/factory_loop_policy.json').exists()
    assert not (out/'records/factory_loop_cycles.json').exists()
    with sqlite3.connect((home/'factory.sqlite').as_uri()+'?mode=ro',uri=True) as db:
        tables={row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert not {'factory_loop_policy','factory_loop_cycles'} & tables
    assert (home/'factory.sqlite').read_bytes()==before
