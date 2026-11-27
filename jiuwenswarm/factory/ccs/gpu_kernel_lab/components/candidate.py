"""Verify recorded baseline/candidate fixtures for conditional routed kernel work."""
import hashlib
import json
import re
from pathlib import Path

from .muse_dispatch import SCHEMA as TRACE_SCHEMA, STAGE, canonical, require

SCHEMA = 'factory.r10-candidate-fixtures/1'
FORMATS = ('iq2_xxs', 'q2_k')
MODES = {'enabled': ('1', 1, 'candidate_batched'),
         'default_off': (None, 1, 'stock_quantized'),
         'explicit_off': ('0', 1, 'stock_quantized'),
         'unsupported_shape': ('1', 2, 'stock_quantized')}
MAX_ARTIFACT = 4 * 1024 * 1024


def sha256(value):
    return hashlib.sha256(value).hexdigest()


def is_sha(value, length=64):
    return isinstance(value, str) and re.fullmatch('[a-f0-9]{%d}' % length, value) is not None


def artifact(ref):
    path = Path(ref['path'])
    require(path.is_file() and path.stat().st_size <= MAX_ARTIFACT, 'Missing or oversized staged artifact')
    data = path.read_bytes()
    require(is_sha(ref['sha256']) and sha256(data) == ref['sha256'], 'Staged artifact digest differs')
    return data


def f32_words(words, size):
    require(isinstance(words, list) and len(words) == size and
            all(type(x) is int and 0 <= x <= 0xffffffff and x & 0x7f800000 != 0x7f800000 for x in words),
            'Expected complete finite IEEE-754 binary32 words')
    return words


def validate_case(case, identity, patch_sha, candidate_library):
    mode, dtype = case['mode'], case['type']
    switch, tokens, selected = MODES[mode]
    require(dtype in FORMATS and case['switch'] == switch, 'Fixture switch or quantized format differs')
    shape = case['shape']
    rows, tile, width = (shape[key] for key in ('output_rows', 'row_tile', 'input_width'))
    require(all(type(x) is int for x in (rows, tile, width)) and 1 < tile < rows <= 128 and rows % tile != 0
            and 256 <= width <= 8192 and width % 256 == 0 and type(shape['tokens']) is int and shape['tokens'] == tokens,
            'Fixture omitted a partial output tile or token shape')
    routes = case['expert_ids']
    require(isinstance(routes, list) and len(routes) == tokens, 'Missing per-token routes')
    require(all(isinstance(r, list) and 3 <= len(r) <= 8 and
                all(type(v) is int and 0 <= v < 256 for v in r) and
                1 < len(set(r)) < len(r) for r in routes), 'Each token needs distinct and repeated expert selections')
    gates = case['gate_f32_words']
    require(isinstance(gates, list) and len(gates) == tokens, 'Missing per-token gates')
    for weights, selected_routes in zip(gates, routes, strict=True):
        f32_words(weights, len(selected_routes))
        require(all(0 < w <= 0x3f800000 for w in weights) and len(set(weights)) >= 2,
                'Fixture needs positive unequal gates')
    count = sum(map(len, routes))
    expected_slots = list(range(count))
    reference, actual = case['reference'], case['candidate']
    require(reference['backend'] == 'stock_quantized' and reference['library_sha256'] == identity['cuda_library_sha256']
            and reference['source_commit'] == identity['source_commit'], 'Reference was not bound to the original quantized library')
    require(actual['backend'] == selected and actual['library_sha256'] == candidate_library
            and actual['patch_sha256'] == patch_sha and actual['parent_commit'] == identity['source_commit'],
            'Candidate did not execute the required branch or did not use the checked patch')
    expected_reason = 'outside_single_token_decode' if mode == 'unsupported_shape' else (
        'switch_off' if mode in {'default_off', 'explicit_off'} else None)
    require(actual['fallback_reason'] == expected_reason, 'Incorrect fallback reason')
    for record in (reference, actual):
        require(record['expert_ids'] == routes and record['gate_f32_words'] == gates,
                'Route order, selected experts or gate words differ')
        launches = record['matvec_launches']
        require(isinstance(launches, list) and launches and all(
            isinstance(x.get('kernel'), str) and x['kernel'] and isinstance(x.get('slots'), list) and x['slots']
            and all(type(slot) is int for slot in x['slots']) for x in launches), 'Missing measured launch coverage')
        require(sorted(slot for x in launches for slot in x['slots']) == expected_slots,
                'Dispatch must cover every selected route slot exactly once')
        if record is actual and selected == 'candidate_batched':
            require(len(launches) < len(reference['matvec_launches']) and len(launches) == 1,
                    'Enabled candidate did not replace separate stock launches with one batch')
        f32_words(record['routed_output_f32_words'], count * rows)
        f32_words(record['combined_output_f32_words'], tokens * rows)
    if selected == 'stock_quantized':
        require(actual['matvec_launches'] == reference['matvec_launches'], 'Fallback changed original dispatch')
    require(len(set(reference['routed_output_f32_words'])) > 1 and any(
        word & 0x7fffffff for word in reference['combined_output_f32_words']),
        'Degenerate reference outputs cannot qualify a candidate')
    require(all(reference[key] == actual[key] for key in ('routed_output_f32_words', 'combined_output_f32_words')),
            'Candidate disagrees with original routed or combined binary32 outputs')
    return {'type': dtype, 'mode': mode, 'tokens': tokens, 'selected_slots': count,
            'reference_launches': len(reference['matvec_launches']), 'candidate_launches': len(actual['matvec_launches'])}


def verify_candidate(dispatch_trace, fixture_receipt, candidate_patch):
    try:
        require(dispatch_trace['format'] == TRACE_SCHEMA and dispatch_trace['eligibility'] == 'eligible'
                and dispatch_trace['may_build'] is True, 'Accepted dispatch trace does not authorize candidate work')
        identity = dispatch_trace['identity']
        require(is_sha(identity['cuda_library_sha256']) and is_sha(identity['source_commit'], 40),
                'Accepted dispatch trace lacks original library and source pins')
        patch = artifact(candidate_patch)
        patch_sha = sha256(patch)
        require(patch.startswith(b'diff --git ') and b'\n@@ ' in patch, 'Staged candidate patch is not a Git diff')
        raw = artifact(fixture_receipt)
        receipt = json.loads(raw)
        require(receipt['format'] == SCHEMA and receipt['dispatch_trace_sha256'] == sha256(canonical(dispatch_trace))
                and receipt['candidate_patch_sha256'] == patch_sha, 'Fixture receipt does not bind accepted trace and patch')
        library = receipt['candidate_library_sha256']
        require(is_sha(library) and library != identity['cuda_library_sha256'], 'Missing distinct candidate library pin')
        cases = receipt['cases']
        required = {(dtype, mode) for dtype in FORMATS for mode in MODES}
        require(isinstance(cases, list) and len(cases) == len(required) and
                {(case['type'], case['mode']) for case in cases} == required,
                'Missing or duplicate quantized fixture, fallback or switch case')
        checked = [validate_case(case, identity, patch_sha, library) for case in cases]
    except (OSError, ValueError, KeyError, TypeError, AttributeError, OverflowError) as exc:
        return {'done': False, 'checks': [{'name': 'candidate_fixture_evidence', 'status': 'fail', 'stage': STAGE,
                                          'detail': str(exc)}], 'fixture_evidence': {}}

    return {'done': True, 'checks': [
        {'name': 'candidate_fixture_binding', 'status': 'pass', 'stage': STAGE,
         'detail': 'The pinned receipt matches the checked patch and eligible dispatch trace.'},
        {'name': 'quantized_output_and_routes', 'status': 'pass', 'stage': STAGE,
         'detail': 'Both formats preserve all repeated route slots, unequal gates and exact binary32 outputs at partial tiles.'},
        {'name': 'fallback_and_switch', 'status': 'pass', 'stage': STAGE,
         'detail': 'Enabled cases batch; default off, explicit off and unsupported shapes use the original quantized dispatch.'},
    ], 'fixture_evidence': {'format': SCHEMA, 'dispatch_trace_sha256': receipt['dispatch_trace_sha256'],
                            'candidate_patch_sha256': patch_sha, 'candidate_library_sha256': library,
                            'fixture_receipt_sha256': sha256(raw), 'cases': checked}}
