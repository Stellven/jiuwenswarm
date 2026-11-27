"""Conditional GPU fixture gate tests use synthetic retained receipts and no GPU."""
import json
from pathlib import Path
import sys

import pytest

from jiuwenswarm.ccv2.ccv2 import Host
from jiuwenswarm.factory.ccs.gpu_kernel_lab.components import candidate, muse_dispatch


@pytest.fixture
def inputs(tmp_path):
    trace = {'format': muse_dispatch.SCHEMA, 'eligibility': 'eligible', 'may_build': True,
             'identity': {'cuda_library_sha256': '1' * 64, 'source_commit': '2' * 40}}
    patch = b'diff --git a/dispatch b/dispatch\n@@ -1 +1 @@\n-old\n+changed\n'
    patch_sha = candidate.sha256(patch)
    cases = []
    for dtype in candidate.FORMATS:
        for mode, (switch, tokens, backend) in candidate.MODES.items():
            experts = [[2, 7, 2]] * tokens
            gates = [[0x3f000000, 0x3ec00000, 0x3e000000]] * tokens
            stock = {'backend': 'stock_quantized', 'library_sha256': '1' * 64, 'source_commit': '2' * 40,
                     'expert_ids': experts, 'gate_f32_words': gates,
                     'matvec_launches': [{'kernel': 'stock', 'slots': [i]} for i in range(3 * tokens)],
                     'routed_output_f32_words': [0x3f800000 + i for i in range(15 * tokens)],
                     'combined_output_f32_words': [0x3f800000] * (5 * tokens)}
            fallback = {'default_off': 'switch_off', 'explicit_off': 'switch_off',
                        'unsupported_shape': 'outside_single_token_decode'}.get(mode)
            changed = dict(stock, backend=backend, library_sha256='3' * 64, parent_commit='2' * 40,
                           patch_sha256=patch_sha, fallback_reason=fallback)
            if mode == 'enabled':
                changed['matvec_launches'] = [{'kernel': 'gated', 'slots': list(range(3 * tokens))}]
            cases.append({'mode': mode, 'type': dtype, 'switch': switch, 'expert_ids': experts, 'gate_f32_words': gates,
                          'shape': {'tokens': tokens, 'output_rows': 5, 'row_tile': 4, 'input_width': 256},
                          'reference': stock, 'candidate': changed})
    receipt = {'format': candidate.SCHEMA, 'dispatch_trace_sha256': candidate.sha256(muse_dispatch.canonical(trace)),
               'candidate_patch_sha256': patch_sha, 'candidate_library_sha256': '3' * 64, 'cases': cases}
    folder = tmp_path / 'inputs'
    folder.mkdir()
    return trace, patch, receipt, folder


def stage(data, path, *, native=False):
    path.write_bytes(data)
    location = {'uri': path.as_uri()} if native else {'path': str(path)}
    return dict(location, sha256=candidate.sha256(data))


def evidence(inputs, *, native=False):
    trace, patch, manifest, folder = inputs
    return {'dispatch_trace': trace, 'candidate_patch': stage(patch, folder / 'patch', native=native),
            'fixture_receipt': stage(json.dumps(manifest).encode(), folder / 'receipt', native=native)}


def test_candidate_verifier_is_discoverable_and_checks_all_cases(inputs, tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[2]
    monkeypatch.setenv('PYTHONPATH', str(root))
    host = Host(tmp_path / 'store', session_grants=['process.exec'], python=sys.executable)
    release = host.prepare(root / 'jiuwenswarm/factory/ccs/gpu_kernel_lab')
    proof = evidence(inputs, native=True)
    result = host.call(release, 'verify_candidate', proof)
    assert result['state'] == 'succeeded', result.get('diagnostics')
    outputs = result['outputs']
    assert outputs['done'] and len(outputs['fixture_evidence']['cases']) == 8
    assert outputs['fixture_evidence']['fixture_receipt_sha256'] == proof['fixture_receipt']['sha256']
    assert result['effects']['granted'] == ['process.exec']
    missing = host.call(release, 'verify_candidate', {k: v for k, v in proof.items() if k != 'fixture_receipt'})
    assert missing['state'] != 'succeeded'


@pytest.mark.parametrize('changed', ['trace', 'patch', 'formats', 'gate', 'duplicate_launch', 'output',
                                    'reference', 'off_switch', 'fallback', 'tile'])
def test_candidate_verifier_fails_closed(inputs, changed):
    trace, patch, receipt, _ = inputs
    enabled = receipt['cases'][0]
    if changed == 'trace':
        trace.update(may_build=False, eligibility='already_batched')
    elif changed == 'patch':
        receipt['candidate_patch_sha256'] = '0' * 64
    elif changed == 'formats':
        receipt['cases'].pop()
    elif changed == 'gate':
        enabled['candidate']['gate_f32_words'] = [[0x3f800000] * 3]
    elif changed == 'duplicate_launch':
        enabled['candidate']['matvec_launches'][0]['slots'] = [0, 1, 1]
    elif changed == 'output':
        enabled['candidate']['combined_output_f32_words'] = [0x3f800001] * 5
    elif changed == 'reference':
        enabled['reference']['library_sha256'] = '0' * 64
    elif changed == 'off_switch':
        receipt['cases'][1]['candidate']['backend'] = 'candidate_batched'
    elif changed == 'fallback':
        receipt['cases'][3]['candidate']['fallback_reason'] = 'switch_off'
    elif changed == 'tile':
        enabled['shape']['output_rows'] = 8
    result = candidate.verify_candidate(**evidence(inputs))
    assert not result['done'] and result['fixture_evidence'] == {}
