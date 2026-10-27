"""Offline predicate tests: reseal semantic faults to isolate them from integrity."""
import copy
import hashlib
import json

import pytest

from jiuwenswarm.research.checks.trace import CHECK_IDS, check_trace
from jiuwenswarm.research.state import json_bytes
from jiuwenswarm.research.trace_manifest import TraceBuilder


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def seal(manifest):
    previous = None
    for seq, event in enumerate(manifest['events'], 1):
        event.update(seq=seq, prev_event_sha256=previous)
        event['event_sha256'] = sha(json_bytes({k: v for k, v in event.items() if k != 'event_sha256'}))
        previous = event['event_sha256']
    manifest['manifest_sha256'] = sha(json_bytes({k: v for k, v in manifest.items() if k != 'manifest_sha256'}))


def good_trace(op='sum', values=(1, 2, 3), claimed=6):
    blobs = {}

    def blob(value):
        raw = json_bytes(value)
        blobs[sha(raw)] = raw
        return {'sha256': sha(raw)}

    policy = dict(invocation_id='invocation:offline', contract_ref=blob('contract'),
                  declaration_ref=blob('declaration'), profile_ref=blob('profile'),
                  allowed_tools=['measure', 'edit'], required_pre_submit_checks=['schema'],
                  claim_coverage_required=True)
    trace = TraceBuilder(*(policy[k] for k in ('invocation_id', 'contract_ref', 'declaration_ref', 'profile_ref')))
    trace.append_event('tool_call', 'measure', args_ref=blob({'tool': 'measure'}))
    measured = blob({'values': list(values)})
    trace.append_event('tool_result', 'measure', result_ref=measured)
    artifact = json_bytes({'total': claimed, 'source': 'recorded'})
    candidate = sha(artifact)
    blobs[candidate] = artifact
    trace.append_event('artifact_write', 'host', detail={'candidate_sha256': candidate})
    receipt = blob(dict(check_id='schema', runner='checker', candidate_sha256=candidate, status='pass'))
    trace.append_event('check_run', 'checker', result_ref=receipt,
                       detail=dict(check_id='schema', candidate_sha256=candidate))
    trace.append_event('submit', 'host', detail={'candidate_sha256': candidate})
    claims = [dict(output_pointer='/total', kind='derivation', evidence_event_seqs=[2],
                   derivation=dict(op=op, operands=[dict(**measured, pointer=f'/values/{i}') for i in range(len(values))])),
              dict(output_pointer='/source', kind='evidence', evidence_event_seqs=[2])]
    manifest = trace.finalize(dict(status='succeeded', final_artifact_sha256=candidate), claims)
    return manifest, blobs, policy, artifact


def replace_receipt(manifest, blobs, **updates):
    event = next(e for e in manifest['events'] if e['kind'] == 'check_run')
    receipt = json.loads(blobs[event['result_ref']['sha256']])
    receipt.update(updates)
    raw = json_bytes(receipt)
    blobs[sha(raw)] = raw
    event['result_ref'] = {'sha256': sha(raw)}


def test_good_trace_is_pure_and_has_exact_result_shape():
    args = good_trace()
    before = copy.deepcopy(args)
    result = check_trace(*args)
    assert args == before
    assert list(result) == ['checks', 'blocking_failures', 'advance']
    assert [r['id'] for r in result['checks']] == list(CHECK_IDS)
    assert all(set(r) == {'id', 'status', 'reason', 'evidence_event_seqs'} for r in result['checks'])
    assert all(r['status'] == 'pass' for r in result['checks'])
    assert result['blocking_failures'] == []
    assert result['advance'] is True


@pytest.mark.parametrize('defect', CHECK_IDS)
def test_each_single_fault_is_isolated(defect):
    manifest, blobs, policy, artifact = good_trace(claimed=7 if defect == 'numeric_derivation' else 6)
    if defect == 'chain_integrity':
        ref = manifest['events'][0]['args_ref']
        blobs[ref['sha256']] = b'{"tool":"measure","extra":true}'
    elif defect == 'identity_join':
        policy['invocation_id'] = 'another-invocation'
    elif defect == 'tool_allowlist':
        manifest['events'][0]['producer'] = 'forbidden'
    elif defect == 'check_run_join':
        replace_receipt(manifest, blobs, runner='wrong-runner')
    elif defect == 'pre_submit_checks':
        policy['required_pre_submit_checks'].append('lint')
    elif defect == 'no_edit_after_check':
        edit = copy.deepcopy(manifest['events'][0])
        edit.update(producer='edit', args_ref=None, detail={'mutates_candidate': True})
        manifest['events'].insert(-1, edit)
    elif defect == 'claim_coverage_and_artifact':
        manifest['claims'].pop()
    seal(manifest)
    result = check_trace(manifest, blobs, policy, artifact)
    assert result['blocking_failures'] == [defect]
    assert result['advance'] is False


@pytest.mark.parametrize('op,values,claimed', [
    ('sum', (0.1, 0.2), 0.3), ('mean', (0.1, 0.2), 0.15),
    ('median', (4, 1, 2), 2), ('median', (4, 1, 2, 3), 2.5),
    ('min', (4, -2, 3), -2), ('max', (4, -2, 3), 4),
    ('count', (0, 0, 0), 3), ('ratio', (1, 8), 0.125),
    ('diff', (0.3, 0.2), 0.1), ('sum', (9007199254740993, 1), 9007199254740994),
])
def test_exact_operations(op, values, claimed):
    assert check_trace(*good_trace(op, values, claimed))['advance'] is True
    wrong = check_trace(*good_trace(op, values, claimed + 1))
    assert wrong['blocking_failures'] == ['numeric_derivation']


@pytest.mark.parametrize('op,values', [('ratio', (1, 0)), ('ratio', (1, 2, 3)),
                                       ('diff', (1,)), ('multiply', (1, 2)),
                                       ('mean', (True, 2))])
def test_invalid_derivations_block(op, values):
    assert check_trace(*good_trace(op, values))['blocking_failures'] == ['numeric_derivation']


@pytest.mark.parametrize('kind', ['unsupported', 'unmeasured'])
def test_nonassertable_claim_never_advances_even_without_coverage(kind):
    manifest, blobs, policy, artifact = good_trace()
    manifest['claims'][0].update(kind=kind, evidence_event_seqs=[])
    del manifest['claims'][0]['derivation']
    policy['claim_coverage_required'] = False
    seal(manifest)
    result = check_trace(manifest, blobs, policy, artifact)
    assert result['advance'] is None
    assert result['blocking_failures'] == []


@pytest.mark.parametrize('seq', [1, 3, 99])
def test_evidence_requires_existing_result_event(seq):
    manifest, blobs, policy, artifact = good_trace()
    manifest['claims'][1]['evidence_event_seqs'] = [seq]
    seal(manifest)
    assert check_trace(manifest, blobs, policy, artifact)['blocking_failures'] == ['numeric_derivation']


def test_operand_must_be_result_of_cited_event():
    manifest, blobs, policy, artifact = good_trace()
    manifest['claims'][0]['derivation']['operands'][0] = manifest['events'][0]['args_ref']
    seal(manifest)
    assert check_trace(manifest, blobs, policy, artifact)['blocking_failures'] == ['numeric_derivation']


def test_artifact_digest_is_checked_independently_of_coverage():
    manifest, blobs, policy, artifact = good_trace()
    policy['claim_coverage_required'] = False
    assert check_trace(manifest, blobs, policy, artifact + b' ')['blocking_failures'] == ['claim_coverage_and_artifact']


def test_missing_artifact_abstains_instead_of_assuming_claim_truth():
    manifest, blobs, policy, _ = good_trace()
    del blobs[manifest['terminal']['final_artifact_sha256']]
    result = check_trace(manifest, blobs, policy)
    assert result['advance'] is None
    assert result['blocking_failures'] == []


def test_missing_receipt_cannot_become_a_pass():
    manifest, blobs, policy, artifact = good_trace()
    del blobs[manifest['events'][3]['result_ref']['sha256']]
    result = check_trace(manifest, blobs, policy, artifact)
    assert result['advance'] is False
    assert next(r for r in result['checks'] if r['id'] == 'check_run_join')['status'] == 'not_assessable'


def test_failed_rerun_overrides_prior_pass():
    manifest, blobs, policy, artifact = good_trace()
    rerun = copy.deepcopy(manifest['events'][3])
    manifest['events'].insert(-1, rerun)
    # Replace the first run, then exchange receipt refs so the failing run is last.
    replace_receipt(manifest, blobs, status='fail')
    manifest['events'][3]['result_ref'], rerun['result_ref'] = rerun['result_ref'], manifest['events'][3]['result_ref']
    seal(manifest)
    assert check_trace(manifest, blobs, policy, artifact)['blocking_failures'] == ['pre_submit_checks']


def test_mutation_between_required_checks_is_detected_by_candidate_join():
    manifest, blobs, policy, artifact = good_trace()
    replace_receipt(manifest, blobs, candidate_sha256='a' * 64)
    seal(manifest)
    result = check_trace(manifest, blobs, policy, artifact)
    assert 'check_run_join' in result['blocking_failures']
    assert 'no_edit_after_check' in result['blocking_failures']


def test_chain_tampering_without_resealing_is_rejected():
    manifest, blobs, policy, artifact = good_trace()
    manifest['events'][1]['producer'] = 'tampered'
    assert check_trace(manifest, blobs, policy, artifact)['blocking_failures'] == ['chain_integrity']


@pytest.mark.parametrize('manifest', [None, [], {}, {'events': [None]}])
def test_malformed_manifests_never_advance(manifest):
    result = check_trace(manifest, {}, {})
    assert result['advance'] is False
    assert 'chain_integrity' in result['blocking_failures']


def test_optional_artifact_resolves_from_blob_mapping():
    manifest, blobs, policy, _ = good_trace()
    assert check_trace(manifest, blobs, policy)['advance'] is True


def test_all_supplied_blob_digests_are_recomputed():
    manifest, blobs, policy, artifact = good_trace()
    blobs['a' * 64] = b'untrusted content'
    assert check_trace(manifest, blobs, policy, artifact)['blocking_failures'] == ['chain_integrity']


@pytest.mark.parametrize('field', ['invocation_id', 'contract_ref', 'declaration_ref', 'profile_ref'])
def test_every_identity_field_is_pinned(field):
    manifest, blobs, policy, artifact = good_trace()
    policy[field] = 'other' if field == 'invocation_id' else {'sha256': 'f' * 64}
    assert check_trace(manifest, blobs, policy, artifact)['blocking_failures'] == ['identity_join']


def test_explicit_tool_name_cannot_bypass_allowlist_with_allowed_producer():
    manifest, blobs, policy, artifact = good_trace()
    manifest['events'][0]['detail'] = {'tool_name': 'forbidden'}
    seal(manifest)
    assert check_trace(manifest, blobs, policy, artifact)['blocking_failures'] == ['tool_allowlist']


def test_artifact_write_after_check_is_an_edit_even_when_bytes_are_identical():
    manifest, blobs, policy, artifact = good_trace()
    manifest['events'].insert(-1, copy.deepcopy(manifest['events'][2]))
    seal(manifest)
    assert check_trace(manifest, blobs, policy, artifact)['blocking_failures'] == ['no_edit_after_check']


def test_submit_pointer_list_and_escaped_pointers():
    manifest, blobs, policy, _ = good_trace()
    artifact = json_bytes({'a/b': {'~': [6]}, 'unclaimed': 'metadata'})
    candidate = sha(artifact)
    blobs[candidate] = artifact
    for event in manifest['events']:
        if event['kind'] in ('artifact_write', 'check_run', 'submit'):
            event['detail']['candidate_sha256'] = candidate
    raw = json_bytes({'claimed_output_pointers': ['/a~1b/~0/0']})
    blobs[sha(raw)] = raw
    manifest['events'][-1]['args_ref'] = {'sha256': sha(raw)}
    replace_receipt(manifest, blobs, candidate_sha256=candidate)
    manifest['terminal']['final_artifact_sha256'] = candidate
    manifest['claims'] = [manifest['claims'][0]]
    manifest['claims'][0]['output_pointer'] = '/a~1b/~0/0'
    seal(manifest)
    assert check_trace(manifest, blobs, policy, artifact)['advance'] is True
