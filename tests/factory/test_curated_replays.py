"""Curated replay builder: provenance, digest preservation, no record without a source.

Synthetic homes only; the real-data check runs when CURATED_REPLAY_BASE points at a Spark copy.
"""
import hashlib
import json
import os
from pathlib import Path
import sqlite3

import pytest

from jiuwenswarm.factory.export import verify
from jiuwenswarm.factory.store import TABLES, TASK_INPUTS
from jiuwenswarm.gateway.channel_manager.web.factory_http import FactoryHttpService
from scripts.spark import build_demo_replays as curated

HOME = 'star-synthetic-home'
TASK = 'synthetic-do'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def make_home(base: Path):
    home = base / 'factory-runs' / HOME
    (home / 'artifacts' / 'ab').mkdir(parents=True)
    (home / 'sessions').mkdir()
    db = sqlite3.connect(home / 'factory.sqlite')
    for table, (_, ddl) in TABLES.items():
        extra = ''.join(f', {name} {kind}' for name, kind in TASK_INPUTS.items()) if table == 'tasks' else ''
        db.execute(f'CREATE TABLE {table} ({ddl}{extra})')
    db.execute('CREATE TABLE evidence (cursor INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, id TEXT, type TEXT, '
               'kind TEXT, summary TEXT, created REAL, record JSON)')
    db.execute("INSERT INTO tasks (task_id, objective, constraints, allowed_effects, target, budget, revision, "
               "current_decision_rev, evidence_cursor, created, contract_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
               (TASK, 'Build the cache', '{}', '[]', '{}', '{}', 1, 1, 3, 1000.0, 'star-deepseek-v1'))
    db.execute("INSERT INTO decisions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (f'{TASK}:decision:1', TASK, 1, 0, '[]', '[]', 'h', 'u',
                json.dumps({'type': 'integrate', 'next_bounded_operation': 'Write the seeding code.'}),
                'e', '{}', 's', 'r', 1010.0))
    files = {'contract.json': b'{"contract_id": "star-deepseek-v1"}\n', 'change.diff': b'--- a\n+++ b\n@@\n+seed\n',
             'note.md': b'# Note\n', 'leaky.json': b'{"api_key": "abcdefghijklmnopqrstuvwxyz123456"}\n'}
    for name, data in files.items():
        digest = sha(data)
        location = f'artifacts/ab/{digest}'
        (home / location).write_bytes(data)
        artifact_id = 'input-0:star-deepseek-v1.json' if name == 'contract.json' else name
        db.execute('INSERT INTO artifacts VALUES (?,?,?,?,?,?,?,?,?)',
                   (artifact_id, TASK, digest, len(data), 'application/octet-stream', None, location, 1, 1005.0))
    db.execute('INSERT INTO observations VALUES (?,?,?,?,?,?,?,?,?,?)',
               ('build-handoff', TASK, '["change.diff"]', 'build_request_preparation',
                json.dumps({'source_commit': 'ad2130b0'}), '{}', '{}', None, '', 1020.0))
    db.commit()
    db.close()
    (home / 'sessions' / f'{TASK}.jsonl').write_bytes(b'{"t": 1, "event": "turn.start"}\n{"t": 2, "event": "edit"}\n'
                                                      b'{"t": 3, "event": "turn.end"}\n')
    ops = base / 'OPS'
    (ops / 'iterations').mkdir(parents=True)
    (ops / 'DECISIONS.md').write_text('# Decisions\n2026-11-20T15:40:57Z Use report-v3 as the headline.\n',
                                      encoding='utf-8')
    (ops / 'iterations' / 'report.md').write_text('# Result\n\n27.08 s sooner.\n', encoding='utf-8')
    return home


def spec():
    art = lambda artifact_id, label, key=None: dict(kind='artifact', home=HOME, task=TASK, id=artifact_id,
                                                   label=label, key=key)
    session = dict(kind='home_file', home=HOME, path=f'sessions/{TASK}.jsonl', label='Session (full)')
    report = dict(kind='ops', path='iterations/report.md', label='Result report', key='The measured numbers')
    return dict(folder='curated-synthetic', title='Replay 1: synthetic', primary=(HOME, TASK), order=1, steps=[
        dict(title='The task', say='The owner set the contract.',
             primary=dict(table='tasks', home=HOME, task=TASK, id=TASK),
             files=[art('input-0:star-deepseek-v1.json', 'Contract', 'The contract'),
                    art('note.md', 'Note', 'A note'), art('leaky.json', 'Leaky', 'Omitted'),
                    dict(session, key='The session')]),
        dict(title='The change', say='The agent wrote the code.',
             primary=dict(table='decisions', home=HOME, task=TASK, id=f'{TASK}:decision:1'),
             records=[dict(table='observations', home=HOME, task=TASK, id='build-handoff')],
             graph=['step:integrate'],
             files=[art('change.diff', 'Diff · seeding', 'The code change'),
                    dict(kind='excerpt', name='edit.jsonl', source=session, ranges=[(2, 2)], label='Excerpt',
                         key='The edit call'), report]),
        dict(title='The result', say='27.08 s sooner.',
             primary=dict(table='file', file='ops:DECISIONS.md', line=2),
             files=[report, dict(kind='ops', path='DECISIONS.md', label='Decisions', key='Line 2'),
                    art('note.md', 'Note', 'Context')],
             quotes=[dict(file='ops:iterations/report.md', lines=[3])]),
    ])


@pytest.fixture
def bundle(tmp_path):
    base = tmp_path / 'spark'
    make_home(base)
    return curated.build(base, base / 'factory-runs' / 'exports', spec()), base


def load(path, name):
    return json.loads((path / name).read_text(encoding='utf-8'))


def test_bundle_verifies_and_every_copied_file_keeps_its_source_digest(bundle):
    path, base = bundle
    assert verify(path) > 0
    provenance = load(path, 'provenance.json')
    manifest = load(path, 'MANIFEST.json')
    for name, origin in provenance['files'].items():
        assert manifest[name] == origin['sha256'] == sha((path / name).read_bytes())
        if origin['source'] == 'factory_home_artifact':
            source = base / 'factory-runs' / origin['source_home'] / origin['source_path']
        elif origin['source'] == 'factory_home_file':
            source = base / 'factory-runs' / origin['source_home'] / origin['source_path']
        elif origin['source'] == 'ops_file':
            source = base / origin['source_path']
        else:
            assert origin['source'] == 'verbatim_excerpt'
            whole = (path / origin['excerpt_of']).read_bytes().splitlines(keepends=True)
            picked = b''.join(b''.join(whole[a - 1:b]) for a, b in origin['line_ranges'])
            assert picked == (path / name).read_bytes()
            continue
        assert sha(source.read_bytes()) == origin['sha256']


def test_files_that_trip_the_secret_scan_are_left_out_not_altered(bundle):
    path, _ = bundle
    omitted = load(path, 'omissions.json')
    assert [o['artifact_id'] for o in omitted] == ['leaky.json']
    assert all('leaky' not in k['label'].lower() for s in load(path, 'replay.json')['steps'] for k in s['key_files'])


def test_no_record_or_file_without_a_source(bundle):
    path, _ = bundle
    replay = load(path, 'replay.json')
    provenance = load(path, 'provenance.json')
    assert replay['summary'].startswith('Curated replay: selected real records from 1 factory home')
    rows = {(t, r[curated.KEYS.get(t, 'task_id')]) for t in ('decisions', 'observations')
            for r in load(path, f'records/{t}.json')}
    for step in replay['steps']:
        assert step['presentation_label'] == 'Presentation title'
        for ref in step['records']:
            if ref['table'] == 'file':
                assert ref['source'].startswith('OPS/')
                continue
            assert ref['source_home'] == HOME and ref['task_id'] == TASK
            if ref['table'] in {'decisions', 'observations'}:
                assert (ref['table'], ref['id']) in rows
        for name in step['files']:
            assert name in provenance['files']
        for key in step['key_files']:
            assert key['path'] in provenance['files'] and not key['label'].startswith('artifacts/')
        for quote in step['quotes']:
            lines = (path / quote['path']).read_bytes().splitlines()
            assert lines[quote['line'] - 1].decode() == quote['text']
    for table, refs in provenance['records'].items():
        for ref in refs:
            assert ref['task_id'] == TASK


def test_step_time_and_kind_come_from_the_record(bundle):
    path, _ = bundle
    steps = load(path, 'replay.json')['steps']
    assert [s['original_kind'] for s in steps] == ['task', 'integrate', 'ops_record_line']
    assert steps[0]['created'] == 1000.0 and steps[1]['created'] == 1010.0
    assert steps[2]['created_utc'].startswith('2026-11-20T15:40:57')


def test_web_service_lists_the_bundle_as_a_pinned_demo_with_step_events(bundle):
    path, base = bundle
    service = FactoryHttpService(roots=[str(base / 'factory-runs')], measurement_root=str(base / 'OPS'))
    runs = service.listing()['runs']
    demo = [run for run in runs if run.get('demo')]
    assert [run['name'] for run in demo] == ['Replay 1: synthetic']
    detail = service.detail(demo[0]['id'])
    assert [e['presentation_title'] for e in detail['events']] == ['The task', 'The change', 'The result']
    assert detail['curated']['steps'][1]['event_cursor'] == 2
    names = {row['path']: row['display_path'] for row in detail['files']}
    assert names[detail['curated']['steps'][1]['key_files'][0]['path']] == 'Diff · seeding'
    assert all(row['integrity'] == 'verified' for row in detail['files'] if row['path'] != 'MANIFEST.json')
    graph = detail['graph']
    steps = [n for n in graph['nodes'] if n.get('label_kind') == 'Replay step']
    assert [n['node_id'] for n in steps] == ['step-1', 'step-2', 'step-3']
    assert [n['depends_on'] for n in steps] == [[], ['step-1'], ['step-2']]
    records = [n for n in graph['nodes'] if n['depends_on'] == ['step-2']]
    assert {tuple(n['evidence_ids']) for n in records} >= {(f'{TASK}:decision:1',), ('build-handoff',)}
    assert detail['events'][1]['graph_nodes'][0] == 'step-2'


@pytest.mark.skipif(not os.environ.get('CURATED_REPLAY_BASE'), reason='set CURATED_REPLAY_BASE to a Spark data copy')
def test_real_replay_builds_from_spark_records(tmp_path):
    base = Path(os.environ['CURATED_REPLAY_BASE'])
    path = curated.build(base, tmp_path, curated.REPLAY_1)
    replay = load(path, 'replay.json')
    assert len(replay['steps']) == 9
    assert replay['steps'][-1]['quotes'][0]['text'].startswith('Across ten pairs per size, C3 returned')
    assert verify(path) > 0


def test_record_redaction_keeps_json_valid():
    value = {'a': [{'projected_upload_gib_per_token': 0.12345678901234567, 'ok': 1}], 'api_key': 'sk-abcdefghijklmnopqrstuvwxyz'}
    out = curated.redact_values(value)
    assert out['a'][0] == {'projected_upload_gib_per_token': '<redacted>', 'ok': 1}
    assert out['api_key'] == '<redacted>'
    json.loads(json.dumps(out))
