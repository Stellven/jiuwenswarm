"""engine.build_expert_fill as the factory calls it.

These tests seal the capsule in a CC v2 Host with the verifier grants of node_check and judge receipts with
node_check.assess. Without a build and a tiny pack the verifier stops at the static stage, which must not
satisfy a node that requires runtime acceptance; each planted fault fails even the fixture stage.
"""
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

REPO = Path(__file__).resolve().parents[2]
CAPSULE = REPO / 'jiuwenswarm/factory/ccs/expert_fill'
FIXTURES = CAPSULE / 'tests/fixtures'
FAULTS = ('gate-default-on.diff', 'fill-after-matmul.diff', 'fill-writes-tensor.diff', 'touches-ggml-cpu.diff')


def test_declaration_fits_the_verifier_grants_and_stages():
    import yaml
    from jiuwenswarm.factory.node_check import STAGES, VERIFIER_GRANTS
    declaration = yaml.safe_load((CAPSULE / 'cc.yaml').read_text(encoding='utf-8'))
    assert declaration['id'] == 'engine.build_expert_fill' and declaration['version'] == '1.0.1'
    verify = declaration['capabilities']['verify']
    assert set(verify['changes']) <= set(VERIFIER_GRANTS)
    assert {'checkout', 'diff_path', 'tiny_dir'} <= set(verify['takes'])
    assert set(declaration['defs']['checks']['schema']['items']['properties']['stage']['enum']) <= set(STAGES)


@pytest.fixture
def checkout(tmp_path):
    if not shutil.which('git'):
        pytest.skip('git not available')
    root = tmp_path / 'llama.cpp'
    shutil.copytree(FIXTURES / 'stock', root)
    for args in (('init', '-q', '--template='), ('-c', 'core.autocrlf=false', 'add', '-A'),
                 ('-c', 'user.name=fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'stock')):
        subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True)
    return root


def test_static_pass_does_not_reach_runtime_acceptance(tmp_path, checkout):
    host_mod = pytest.importorskip('jiuwenswarm.ccv2.ccv2')
    node_check = pytest.importorskip('jiuwenswarm.factory.node_check')
    host = host_mod.Host(tmp_path / 'host', session_grants=node_check.VERIFIER_GRANTS, python=sys.executable)
    release = host.prepare(CAPSULE)
    release = release['release'] if isinstance(release, dict) else release
    declaration, _ = host.release(release)
    grants = sorted(set(node_check.VERIFIER_GRANTS) & set(declaration['capabilities']['verify']['changes']))

    def verify(diff, stage, **extra):
        receipt = host.call(release, 'verify', {'checkout': str(checkout), 'diff_path': str(FIXTURES / diff), **extra},
                            grants=grants, timeout=300)
        assert receipt['state'] == 'succeeded', receipt
        return node_check.assess(receipt, stage)

    ok, reached, reason = verify('good.diff', 'runtime acceptance', build=False)
    assert not ok and reached == 'native CC execution' and 'not done' in reason, reason
    ok, reached, reason = verify('good.diff', 'native CC execution', build=False, require_stage='native CC execution')
    assert ok and reached == 'native CC execution', reason
    for diff in FAULTS:
        ok, _, reason = verify(diff, 'fixture', require_stage='fixture')
        assert not ok and 'verifier checks failed' in reason, reason
