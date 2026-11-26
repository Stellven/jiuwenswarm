"""weights.build_weight_pack_compiler 2.0.0 as the factory calls it for node requant_q2.

The contract muse-q2-ttft-v2 names verify_recipe and verify_pack as the verifiers of the node's two evidence
outputs. These tests call the capsule the two ways the factory does: the native ccv2 packet on stdin, and the
CC v2 Host with the verifier grants node_check uses, judged by node_check.assess. Synthetic GGUF packs only.
"""
import json
from pathlib import Path
import subprocess
import sys

import pytest

REPO = Path(__file__).resolve().parents[2]
CAPSULE = REPO / 'jiuwenswarm/factory/ccs/weight_pack_compiler'
CONTRACT = REPO / 'jiuwenswarm/factory/contracts/muse-q2-ttft-v2.json'
sys.path.insert(0, str(CAPSULE / 'tests'))
import wpc_gguf_fixture as fx  # noqa: E402


def native(capability, **inputs):
    proc = subprocess.run([sys.executable, str(CAPSULE / 'run.py')], capture_output=True, text=True,
                          input=json.dumps({'capability': capability, 'inputs': inputs}))
    assert proc.returncode == 0, proc.stderr
    response = json.loads(proc.stdout)
    assert response['outcome'] == 'ok'
    return response['outputs']


def failed(outputs):
    return {c['name'] for c in outputs['checks'] if c['status'] == 'fail'}


@pytest.fixture
def packs(tmp_path):
    source = fx.make_source(tmp_path)
    imatrix = tmp_path / 'imatrix.gguf'
    imatrix.write_bytes(b'importance')
    recipe = tmp_path / 'recipe.json'
    planned = native('plan_recipe', pack_manifest=str(source[0]), imatrix=str(imatrix), hash=True,
                     recipe_out=str(recipe), disk_grant_bytes=1 << 30)
    assert planned['done'], planned['checks']
    out = tmp_path / 'q2'
    out.mkdir()
    return dict(source=source, recipe=recipe, out=out, imatrix=imatrix)


def test_contract_names_capabilities_the_capsule_declares():
    import yaml
    declaration = yaml.safe_load((CAPSULE / 'cc.yaml').read_text(encoding='utf-8'))
    assert declaration['id'] == 'weights.build_weight_pack_compiler' and declaration['version'] == '2.0.0'
    contract = json.loads(CONTRACT.read_text(encoding='utf-8'))
    text = json.dumps(contract)
    for capability in ('verify_recipe', 'verify_pack'):
        assert f'weights.build_weight_pack_compiler.{capability}' in text
        assert declaration['capabilities'][capability]['changes'] == ['workspace.read']


def test_native_packet_clean_and_faulted(packs):
    fx.make_q2(packs['out'])
    first = str(packs['out'] / 'muse-nvfp4-Q2_K-00001-of-00002.gguf')
    recipe = native('verify_recipe', recipe=str(packs['recipe']), pack_manifest=str(packs['source'][0]),
                    disk_grant_bytes=1 << 30)
    assert recipe['done'] and not failed(recipe)
    pack = native('verify_pack', pack=first, recipe=str(packs['recipe']), source_pack=str(packs['source'][0]),
                  expect_bytes_range=[1, 1 << 30])
    assert pack['done'] and pack['manifest']['census']['routed_expert'] == {'q2_k': 9}

    faulted = packs['out'].parent / 'faulted'
    faulted.mkdir()
    fx.make_q2(faulted, drop=('blk.1.ffn_gate_exps.scale',), overrides={'blk.2.attn_q.weight': 'q4_k'})
    bad = native('verify_pack', pack=str(faulted), recipe=str(packs['recipe']), source_pack=str(packs['source'][0]))
    assert not bad['done'] and {'scale_tensors_present', 'non_expert_types', 'tensor_set'} <= failed(bad)


def test_host_call_with_node_check_grants_and_assess(packs, tmp_path):
    host_mod = pytest.importorskip('jiuwenswarm.ccv2.ccv2')
    node_check = pytest.importorskip('jiuwenswarm.factory.node_check')
    fx.make_q2(packs['out'])
    host = host_mod.Host(tmp_path / 'host', session_grants=node_check.VERIFIER_GRANTS, python=sys.executable)
    release = host.prepare(CAPSULE)
    declaration, _ = host.release(release)

    def verify(capability, inputs, stage):
        grants = sorted(set(node_check.VERIFIER_GRANTS) & set(declaration['capabilities'][capability]['changes']))
        receipt = host.call(release, capability, inputs, grants=grants, timeout=120)
        assert receipt['state'] == 'succeeded', receipt
        return node_check.assess(receipt, stage)

    ok, reached, reason = verify('verify_recipe', {'recipe': str(packs['recipe']),
                                                   'pack_manifest': str(packs['source'][0])}, 'fixture')
    assert ok and reached == 'native CC execution', reason
    inputs = {'pack': str(packs['out']), 'recipe': str(packs['recipe']), 'source_pack': str(packs['source'][0]),
              'expect_bytes_range': [1, 1 << 30]}
    ok, reached, reason = verify('verify_pack', inputs, 'native CC execution')
    assert ok, reason
    (packs['out'] / 'muse-nvfp4-Q2_K-00002-of-00002.gguf').unlink()
    ok, _, reason = verify('verify_pack', inputs, 'native CC execution')
    assert not ok and 'pack_readable' in reason
