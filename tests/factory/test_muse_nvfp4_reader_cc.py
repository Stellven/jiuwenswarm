"""weights.build_muse_nvfp4_reader 1.0.0 as the factory calls it for node ingest_nvfp4.

The contract muse-q2-ttft-v2 names verify (converter diff, stage fixture) and verify_pack (nvfp4_pack evidence,
stage native CC execution). These tests seal the capsule in a CC v2 Host, call it with the grants node_check
gives verifiers, and judge the receipts with node_check.assess. Fixture checkout and synthetic packs only.
"""
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

REPO = Path(__file__).resolve().parents[2]
CAPSULE = REPO / 'jiuwenswarm/factory/ccs/muse_nvfp4_reader'
CONTRACT = REPO / 'jiuwenswarm/factory/contracts/muse-q2-ttft-v2.json'
FIXTURES = CAPSULE / 'tests/fixtures'
sys.path.insert(0, str(CAPSULE / 'tests'))
import muse_pack_fixture as fx  # noqa: E402


def stages():
    contract = json.loads(CONTRACT.read_text(encoding='utf-8'))
    node = next(n for n in contract['extensions']['factory.node-contracts']['nodes'] if n['node_id'] == 'ingest_nvfp4')
    return {v['output']: v for v in node['verifiers']}


def test_contract_names_capabilities_the_capsule_declares():
    import yaml
    from jiuwenswarm.factory.node_check import VERIFIER_GRANTS
    declaration = yaml.safe_load((CAPSULE / 'cc.yaml').read_text(encoding='utf-8'))
    assert declaration['id'] == 'weights.build_muse_nvfp4_reader' and declaration['version'] == '1.0.0'
    verifiers = stages()
    assert verifiers['converter']['verifier'] == 'weights.build_muse_nvfp4_reader.verify'
    assert verifiers['nvfp4_pack']['verifier'] == 'weights.build_muse_nvfp4_reader.verify_pack'
    for capability in ('verify', 'verify_pack'):
        assert set(declaration['capabilities'][capability]['changes']) <= set(VERIFIER_GRANTS)
    assert 'checkout' in declaration['capabilities']['verify']['takes']
    assert 'checkout' not in declaration['capabilities']['verify_pack']['takes']


@pytest.fixture
def host(tmp_path):
    host_mod = pytest.importorskip('jiuwenswarm.ccv2.ccv2')
    node_check = pytest.importorskip('jiuwenswarm.factory.node_check')
    h = host_mod.Host(tmp_path / 'host', session_grants=node_check.VERIFIER_GRANTS, python=sys.executable)
    release = h.prepare(CAPSULE)
    release = release['release'] if isinstance(release, dict) else release
    declaration, _ = h.release(release)

    def verify(capability, inputs, stage):
        grants = sorted(set(node_check.VERIFIER_GRANTS) & set(declaration['capabilities'][capability]['changes']))
        receipt = h.call(release, capability, inputs, grants=grants, timeout=300)
        assert receipt['state'] == 'succeeded', receipt
        return node_check.assess(receipt, stage)
    return verify


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


def test_converter_verify_reaches_the_contract_stage_without_torch(host, checkout):
    stage = stages()['converter']['stage']
    ok, reached, reason = host('verify', {'checkout': str(checkout), 'diff_path': str(FIXTURES / 'good.diff')}, stage)
    assert ok and reached == 'native CC execution', reason
    for diff in ('gate-up-swapped.diff', 'eager-repack.diff', 'touches-src.diff'):
        ok, _, reason = host('verify', {'checkout': str(checkout), 'diff_path': str(FIXTURES / diff)}, stage)
        assert not ok and 'verifier checks failed' in reason
    # without a python env the runtime stage is not reached: a stricter contract stage would fail
    ok, reached, reason = host('verify', {'checkout': str(checkout), 'diff_path': str(FIXTURES / 'good.diff')},
                               'runtime acceptance')
    assert not ok and reached == 'native CC execution', reason


def test_pack_verify_with_assess(host, tmp_path):
    stage = stages()['nvfp4_pack']['stage']
    paths = fx.make_pack(tmp_path / 'pack')
    inv = fx.make_inventory(tmp_path / 'inventory.json')
    ok, reached, reason = host('verify_pack', {'pack': str(paths[0]), 'inventory': str(inv), 'hash': True}, stage)
    assert ok and reached == stage, reason
    ok, _, reason = host('verify_pack', {'pack': str(paths[0])}, stage)
    assert not ok and 'layer_plan' in reason
    bad = fx.make_pack(tmp_path / 'bad', drop=('blk.2.ffn_down_exps.scale',))
    ok, _, reason = host('verify_pack', {'pack': str(bad[0]), 'inventory': str(inv)}, stage)
    assert not ok and 'expert_scales' in reason
