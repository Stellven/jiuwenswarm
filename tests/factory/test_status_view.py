import json

from jiuwenswarm.factory.cli import main, format_status, readonly_status
from jiuwenswarm.factory.controller import Controller, scrub
from jiuwenswarm.factory.store import Store
from jiuwenswarm.factory.story import load_source
from test_story import chain


def test_compact_status(chain, capsys):
    data = load_source('factory-synthetic', chain)
    output = format_status(readonly_status(data), True, data)
    assert 'do-not-dump-this-id' not in output
    assert 'artifacts 1' in output and '3 bytes' in output
    assert 'decisions 3' in output and 'observations 2' in output
    assert 'Last evaluation' in output and 'synthetic · pass · ok · complete' in output
    assert '✓ decision_published' in output
    assert '\x1b' not in output
    assert len(output.splitlines()) <= 40
    assert max(map(len, output.splitlines())) <= 100
    main(['--home', str(chain), 'status', 'factory-synthetic', '--plain'])
    assert capsys.readouterr().out.rstrip() == output


def test_status_json_contract_unchanged(chain, capsys):
    controller = Controller(chain)
    try:
        expected = scrub(controller.status('factory-synthetic'))
    finally:
        controller.store.close()
    main(['--home', str(chain), 'status', 'factory-synthetic', '--json'])
    assert json.loads(capsys.readouterr().out) == expected


def test_readonly_cli_status_with_operator_history(chain, capsys, monkeypatch):
    task_id = 'factory-synthetic'
    controller = Controller(chain)
    try:
        controller.pause(task_id, 'first change')
        controller.lift_pause(task_id, 'change complete')
        controller.pause(task_id, 'second change')
        delivered = controller.status(task_id)['pending_operator_notes'][0]
        state = controller._load(task_id)
        state['operator_notes_delivered'] = [delivered['note_id']]
        controller._save(task_id, state)
        note = controller.add_note(task_id, 'x' * 294 + ' sk-' + 'a' * 24)
        expected = scrub(controller.status(task_id))
    finally:
        controller.store.close()

    def forbid_store(*args, **kwargs):
        raise AssertionError('Read-only status initialized the factory store')

    monkeypatch.setattr(Store, '__init__', forbid_store)
    monkeypatch.setenv('FACTORY_HOME', str(chain))
    main(['status', task_id, '--json'])
    status = json.loads(capsys.readouterr().out)
    assert status == expected
    assert status['paused']['reason'] == 'second change'
    assert status['pause_records'] == 3
    assert status['pending_operator_notes'] == [
        dict(note_id=note['note_id'], created=note['created'], text='x' * 294 + ' <reda')
    ]

    main(['status', task_id, '--plain'])
    output = capsys.readouterr().out
    assert 'PAUSED by operator' in output
    assert 'Operator notes waiting for the agent: 1' in output
