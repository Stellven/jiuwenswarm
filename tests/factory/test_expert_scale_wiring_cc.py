"""weights.build_expert_scale_wiring 1.2.0 as the factory calls it for node wire_expert_scales.

The contract muse-q2-ttft-v2 names verify for the `change` diff at stage runtime acceptance. These tests seal
the capsule in a CC v2 Host with the verifier grants of node_check and judge receipts with node_check.assess.
Without a build and the tiny packs the verifier stops at the static stage, which must not satisfy the node.
"""
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

REPO = Path(__file__).resolve().parents[2]
CAPSULE = REPO / 'jiuwenswarm/factory/ccs/expert_scale_wiring'
CONTRACT = REPO / 'jiuwenswarm/factory/contracts/muse-q2-ttft-v2.json'
FIXTURES = CAPSULE / 'tests/fixtures'


def contract_entry():
    contract = json.loads(CONTRACT.read_text(encoding='utf-8'))
    node = next(n for n in contract['extensions']['factory.node-contracts']['nodes'] if n['node_id'] == 'wire_expert_scales')
    return next(v for v in node['verifiers'] if v['output'] == 'change')


def test_contract_names_the_capability_the_capsule_declares():
    import yaml
    from jiuwenswarm.factory.node_check import STAGES, VERIFIER_GRANTS
    declaration = yaml.safe_load((CAPSULE / 'cc.yaml').read_text(encoding='utf-8'))
    assert declaration['id'] == 'weights.build_expert_scale_wiring' and declaration['version'] == '1.2.0'
    entry = contract_entry()
    assert entry['verifier'] == 'weights.build_expert_scale_wiring.verify' and entry['stage'] in STAGES
    verify = declaration['capabilities']['verify']
    assert set(verify['changes']) <= set(VERIFIER_GRANTS)
    assert {'checkout', 'diff_path'} <= set(verify['takes'])
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
    stage = contract_entry()['stage']

    def verify(diff, **extra):
        receipt = host.call(release, 'verify', {'checkout': str(checkout), 'diff_path': str(FIXTURES / diff), **extra},
                            grants=grants, timeout=300)
        assert receipt['state'] == 'succeeded', receipt
        return node_check.assess(receipt, stage), node_check.assess(receipt, 'fixture')

    (ok, reached, reason), (ok_fixture, _, _) = verify('good.diff', build=False)
    assert not ok and reached == 'native CC execution', reason
    assert not ok_fixture  # a skipped compile and runtime leave done false: runtime acceptance is the default bar
    (ok, reached, reason), (ok_fixture, _, _) = verify('good.diff', build=False, require_stage='native CC execution')
    assert not ok and 'needs runtime acceptance' in reason and ok_fixture
    for diff in ('up-gets-gate-scale.diff', 'down-scale-missing.diff', 'touches-ggml.diff'):
        (ok, _, reason), (ok_fixture, _, _) = verify(diff)
        assert not ok and not ok_fixture and 'verifier checks failed' in reason
