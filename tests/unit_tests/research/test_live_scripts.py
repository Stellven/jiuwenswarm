"""scripts/live: reproducible live-run tooling takes names and roots as arguments and holds no credential."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

LIVE = Path(__file__).resolve().parents[3] / 'scripts' / 'live'


def _load(name):
    spec = importlib.util.spec_from_file_location('live_' + name, LIVE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fixture(tmp_path):
    inputs = tmp_path / 'fixture' / 'inputs'
    inputs.mkdir(parents=True)
    (inputs / 'data.json').write_bytes(b'{"train":[],"test":[]}')
    (inputs / 'scoring-pins.json').write_text(json.dumps({'holdout_sha256': 'a' * 64, 'scorer_sha256': 'b' * 64}))
    return tmp_path / 'fixture'


def test_deploy_plan_uses_the_given_generation_and_image(tmp_path, capsys):
    deploy = _load('deploy_live')
    args = deploy.parser().parse_args(['plan', '--generation', 'g9', '--image-tag', 'ai4r:live-g9',
        '--out', str(tmp_path / 'out'), '--fixture', str(_fixture(tmp_path)), '--check-image', 'ai4r:old'])
    plan = {step: deploy.commands(step, args) for step in ('build', 'override', 'initialize', 'doctor')}
    text = json.dumps(plan)
    assert 'ai4r:live-g9' in text and 'poc-g9-sci' in text and 'r5h' not in text
    assert deploy.make_override('c' * 64, 'ai4r:live-g9', 'g9')['services']['benchmark-runner']['environment'] == {
        'AI4R_EXPECTED_BUILD': 'c' * 64}
    # The dataset hash is read from the fixture, not hard-coded.
    assert __import__('hashlib').sha256(b'{"train":[],"test":[]}').hexdigest() in text


def test_deploy_captures_static_unless_planned_is_named(tmp_path):
    deploy = _load('deploy_live')
    base = ['initialize', '--generation', 'g9', '--image-tag', 'ai4r:live-g9', '--out', str(tmp_path / 'out'),
            '--fixture', str(_fixture(tmp_path))]
    text = lambda extra: json.dumps(deploy.commands('initialize', deploy.parser().parse_args(base + extra)))
    assert "plan_source='static'" in text([])
    assert "plan_source='planned'" in text(['--plan-source', 'planned'])


def test_deploy_refuses_unsafe_names(tmp_path):
    deploy = _load('deploy_live')
    with pytest.raises(SystemExit):
        deploy.main(['plan', '--generation', 'bad name', '--image-tag', 'ai4r:x', '--out', str(tmp_path),
                     '--fixture', str(tmp_path)])


def test_run_trap_plan_binds_the_build_and_never_carries_a_token(tmp_path):
    trap = _load('run_trap')
    args = SimpleNamespace(out=tmp_path, fixture=_fixture(tmp_path), ledger=tmp_path / 'l.sqlite3',
                           expected_build='d' * 64, model='gpt-6.1-sol')
    plans = trap.command_plan(args, 'trap-x')
    assert set(plans) == {'install-tool', 'prepare', 'run-cc', 'collect'}
    text = json.dumps({k: [str(c[0]) for c in v] for k, v in plans.items()})
    assert 'AI4R_EXPECTED_BUILD=' + 'd' * 64 in text and '/run/benchmark-runner/token' in text
    assert 'AI4R_TOKEN=' not in text


def test_no_credential_value_in_live_scripts():
    for path in LIVE.glob('*.py'):
        text = path.read_text('utf-8')
        assert 'sk-' not in text and 'Bearer ' not in text
    refresh = (LIVE / 'refresh_runner_token.py').read_text('utf-8')
    assert "os.environ.get('AI4R_BOOTSTRAP_SESSION'" in refresh
