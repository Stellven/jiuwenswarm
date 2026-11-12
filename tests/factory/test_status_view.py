from jiuwenswarm.factory.cli import main, format_status, readonly_status
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
    import json
    from jiuwenswarm.factory.controller import Controller, scrub
    controller = Controller(chain)
    try:
        expected = scrub(controller.status('factory-synthetic'))
    finally:
        controller.store.close()
    main(['--home', str(chain), 'status', 'factory-synthetic', '--json'])
    assert json.loads(capsys.readouterr().out) == expected
