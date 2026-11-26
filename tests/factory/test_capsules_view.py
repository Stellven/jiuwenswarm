from jiuwenswarm.factory.capsules import capsule_rows, format_capsules
from jiuwenswarm.factory.cli import main


def test_real_capsules(capsys):
    rows = capsule_rows()
    assert len(rows) == 68
    assert all(r['valid'] for r in rows)
    assert sum(r['binding'] == 'material-only' for r in rows) == 9
    assert sum(len(r['capabilities']) for r in rows) >= 28
    output = format_capsules(rows, True)
    assert output.count('✓ valid') == len(rows)
    assert f"{len(rows)} capsules · {sum(len(r['capabilities']) for r in rows)} capabilities" in output
    assert 'factory.components.expert_fill' in output
    assert '\x1b' not in output
    assert max(map(len, output.splitlines())) <= 100
    main(['capsules', '--plain'])
    assert capsys.readouterr().out.rstrip() == output
