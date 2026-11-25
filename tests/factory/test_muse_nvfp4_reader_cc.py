"""weights.build_muse_nvfp4_reader 1.1.0 as the factory calls it for node ingest_nvfp4.

The contract muse-q2-ttft-v2 names verify (converter diff; runtime acceptance is the bar) and verify_pack
(nvfp4_pack evidence, stage native CC execution, judged against the checkpoint's own index and scale_2). These tests seal the capsule in a CC v2 Host, call it with the grants node_check
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
    assert declaration['id'] == 'weights.build_muse_nvfp4_reader' and declaration['version'] == '1.1.0'
    verifiers = stages()
    assert verifiers['converter']['verifier'] == 'weights.build_muse_nvfp4_reader.verify'
    assert verifiers['nvfp4_pack']['verifier'] == 'weights.build_muse_nvfp4_reader.verify_pack'
    for capability in ('verify', 'verify_pack'):
        assert set(declaration['capabilities'][capability]['changes']) <= set(VERIFIER_GRANTS)
    assert 'checkout' in declaration['capabilities']['verify']['takes']
    assert 'checkout' not in declaration['capabilities']['verify_pack']['takes']
    assert not declaration['capabilities']['verify_pack']['takes']['source_index'].get('optional')


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


STATIC, RUNTIME = 'native CC execution', 'runtime acceptance'


def test_converter_verify_needs_runtime_acceptance(host, checkout):
    good = {'checkout': str(checkout), 'diff_path': str(FIXTURES / 'good.diff')}
    # runtime acceptance is the default bar: without a tiny checkpoint the round trip fails, whatever the node stage
    for stage in (STATIC, RUNTIME):
        ok, reached, reason = host('verify', good, stage)
        assert not ok and reached == STATIC and 'tiny_conversion' in reason, reason
    # a caller that asks for the static stage only gets it, and planted faults still fail it
    ok, reached, reason = host('verify', dict(good, require_stage=STATIC), STATIC)
    assert ok and reached == STATIC, reason
    for diff in ('gate-up-swapped.diff', 'eager-repack.diff', 'eager-loader.diff', 'touches-src.diff'):
        ok, _, reason = host('verify', {'checkout': str(checkout), 'diff_path': str(FIXTURES / diff),
                                        'require_stage': STATIC}, STATIC)
        assert not ok and 'verifier checks failed' in reason
    # an inconclusive static mapping is never a pass without runtime acceptance
    ok, _, reason = host('verify', {'checkout': str(checkout), 'diff_path': str(FIXTURES / 'mapping-inconclusive.diff'),
                                    'require_stage': STATIC}, STATIC)
    assert not ok and 'not done' in reason


def test_pack_verify_with_assess(host, tmp_path):
    stage = stages()['nvfp4_pack']['stage']
    paths = fx.make_pack(tmp_path / 'pack')
    index = str(fx.make_checkpoint(tmp_path / 'ckpt'))
    inv = fx.make_inventory(tmp_path / 'inventory.json')
    ok, reached, reason = host('verify_pack', {'pack': str(paths[0]), 'source_index': index, 'inventory': str(inv),
                                               'hash': True, 'expect_bytes_range': [1, 1 << 30]}, stage)
    assert ok and reached == stage, reason
    bad = fx.make_pack(tmp_path / 'bad', drop=('blk.2.ffn_down_exps.scale',))
    ok, _, reason = host('verify_pack', {'pack': str(bad[0]), 'source_index': index}, stage)
    assert not ok and 'expert_scales' in reason
    swapped = fx.make_pack(tmp_path / 'swapped', swap_columns=True)
    ok, _, reason = host('verify_pack', {'pack': str(swapped[0]), 'source_index': index}, stage)
    assert not ok and 'scale_values' in reason
    empty = fx.make_checkpoint(tmp_path / 'bf16-ckpt', quantized=())
    ok, _, reason = host('verify_pack', {'pack': str(paths[0]), 'source_index': str(empty)}, stage)
    assert not ok and 'layer_plan' in reason


def test_pack_verify_requires_the_source_index(tmp_path):
    host_mod = pytest.importorskip('jiuwenswarm.ccv2.ccv2')
    node_check = pytest.importorskip('jiuwenswarm.factory.node_check')
    h = host_mod.Host(tmp_path / 'host', session_grants=node_check.VERIFIER_GRANTS, python=sys.executable)
    release = h.prepare(CAPSULE)
    release = release['release'] if isinstance(release, dict) else release
    paths = fx.make_pack(tmp_path / 'pack')
    try:
        receipt = h.call(release, 'verify_pack', {'pack': str(paths[0])}, grants=['workspace.read'], timeout=120)
    except Exception as exc:  # the host refuses a call without a required input
        assert 'source_index' in str(exc) or 'INVALID_INPUT' in str(exc) or 'required' in str(exc).lower(), exc
    else:
        assert not node_check.assess(receipt, STATIC)[0]
