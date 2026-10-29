"""Pure offline trace predicates; integrity does not attest actual execution.

Blob conventions (the trace schema deliberately leaves payloads opaque):
artifact_write/submit detail contains candidate_sha256 (artifact_write may use
after_sha256). check_run detail contains check_id and candidate_sha256; its JSON
result records check_id, runner (the event producer), candidate_sha256, status.
Passing status is 'pass' (case insensitive). Mutating tool calls declare
mutates_candidate=true or before_sha256/after_sha256 in detail or JSON args.
Submit JSON args may list claimed_output_pointers; otherwise coverage concerns
every leaf of the JSON artifact. Claims select their asserted value there with
output_pointer. Operands must reference result blobs of cited evidence events.
JSON numbers are decoded as exact Fractions, never binary floating point.

Missing evidence abstains; contradictory evidence fails. Every failure blocks;
any abstention prevents advance=True. No input is modified or fetched.
"""
from __future__ import annotations

import hashlib
import json
import re
from fractions import Fraction

from ..trace_manifest import verify_chain


CHECK_IDS = (
    'chain_integrity', 'identity_join', 'tool_allowlist', 'check_run_join',
    'pre_submit_checks', 'no_edit_after_check', 'numeric_derivation',
    'claim_coverage_and_artifact',
)


def _json(raw):
    def invalid(value):
        raise ValueError('nonfinite_json_number')
    return json.loads(raw, parse_float=Fraction, parse_int=Fraction,
                      parse_constant=invalid)


def _pointer(value, pointer):
    if not isinstance(pointer, str) or re.fullmatch(r'(?:/(?:[^~/]|~[01])*)*', pointer) is None:
        raise ValueError('invalid_pointer')
    for token in pointer.split('/')[1:]:
        token = token.replace('~1', '/').replace('~0', '~')
        if isinstance(value, list):
            if re.fullmatch(r'0|[1-9][0-9]*', token) is None:
                raise ValueError('invalid_array_index')
            value = value[int(token)]
        elif isinstance(value, dict):
            value = value[token]
        else:
            raise ValueError('pointer_into_scalar')
    return value


def _leaves(value, path=''):
    if isinstance(value, (dict, list)) and value:
        entries = value.items() if isinstance(value, dict) else enumerate(value)
        for key, child in entries:
            token = str(key).replace('~', '~0').replace('/', '~1')
            yield from _leaves(child, path + '/' + token)
    else:
        yield path


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, Fraction)):
        raise ValueError('non_numeric_value')
    return Fraction(value)


def _derive(op, values):
    values = [_number(value) for value in values]
    if not values:
        raise ValueError('empty_operands')
    if op == 'sum':
        return sum(values, Fraction())
    if op == 'mean':
        return sum(values, Fraction()) / len(values)
    if op == 'median':
        ordered = sorted(values)
        middle = len(values) // 2
        return ordered[middle] if len(values) % 2 else (ordered[middle-1] + ordered[middle]) / 2
    if op == 'min':
        return min(values)
    if op == 'max':
        return max(values)
    if op == 'count':
        return Fraction(len(values))
    if op in ('ratio', 'diff') and len(values) == 2:
        return values[0] / values[1] if op == 'ratio' else values[0] - values[1]
    raise ValueError('unsupported_operation_or_arity')


def check_trace(manifest, blobs, policy, artifact_bytes=None):
    """Return exactly eight checks, blocking failures, and a three-valued gate."""
    checks = {cid: dict(id=cid, status='pass', reason='predicate_satisfied',
                       evidence_event_seqs=[]) for cid in CHECK_IDS}

    def mark(cid, status, reason, seqs=()):
        row = checks[cid]
        row['evidence_event_seqs'] = sorted(set(row['evidence_event_seqs']) | set(seqs))
        if row['status'] == 'fail' or (row['status'] == 'not_assessable' and status != 'fail'):
            return
        row.update(status=status, reason=reason)

    def load(ref):
        raw = blobs[ref['sha256']]
        if not isinstance(raw, bytes):
            raise ValueError('blob_not_bytes')
        return _json(raw)

    errors = (KeyError, TypeError, ValueError, IndexError, ZeroDivisionError, UnicodeError)
    failures = verify_chain(manifest)
    if failures:
        mark('chain_integrity', 'fail', '; '.join(failures))
    # Check all supplied content, including artifact/operand blobs which need not
    # also occur as event args/results. Never trust a mapping key as its digest.
    for blob_digest, raw in blobs.items():
        if not isinstance(raw, bytes) or hashlib.sha256(raw).hexdigest() != blob_digest:
            mark('chain_integrity', 'fail', 'blob_digest_mismatch')
    if not isinstance(manifest, dict) or not isinstance(manifest.get('events'), list):
        for cid in CHECK_IDS[1:]:
            mark(cid, 'not_assessable', 'malformed_manifest')
    else:
        events = [e for e in manifest['events'] if isinstance(e, dict)]
        for event in events:
            refs = [event.get('args_ref'), event.get('result_ref')]
            refs += event.get('input_refs', []) if isinstance(event.get('input_refs'), list) else []
            for ref in filter(None, refs):
                try:
                    raw = blobs[ref['sha256']]
                    if not isinstance(raw, bytes) or hashlib.sha256(raw).hexdigest() != ref['sha256']:
                        mark('chain_integrity', 'fail', 'blob_digest_mismatch', [event['seq']])
                except errors:
                    mark('chain_integrity', 'not_assessable', 'referenced_blob_unavailable', [event.get('seq', 0)])

        for key in ('invocation_id', 'contract_ref', 'declaration_ref', 'profile_ref'):
            if key not in policy:
                mark('identity_join', 'not_assessable', 'missing_policy_identity')
            elif manifest.get(key) != policy[key]:
                mark('identity_join', 'fail', 'identity_mismatch:' + key)

        def metadata(event):
            result = {}
            try:
                args = load(event.get('args_ref'))
                if isinstance(args, dict):
                    result.update(args)
            except errors:
                pass
            if isinstance(event.get('detail'), dict):
                result.update(event['detail'])
            return result

        def digest(event):
            data = metadata(event)
            return data.get('candidate_sha256', data.get('after_sha256'))

        for event in events:
            if event.get('kind') == 'tool_call':
                if 'allowed_tools' not in policy:
                    mark('tool_allowlist', 'not_assessable', 'missing_tool_policy', [event['seq']])
                else:
                    names = [event.get('producer')]
                    data = metadata(event)
                    names += [data[k] for k in ('tool', 'tool_name') if k in data]
                    if any(name not in policy['allowed_tools'] for name in names):
                        mark('tool_allowlist', 'fail', 'tool_not_allowed', [event['seq']])

        submits = [e for e in events if e.get('kind') == 'submit']
        submit = submits[-1] if submits else None
        runs = []
        for index, event in enumerate(events):
            if event.get('kind') != 'check_run':
                continue
            data = metadata(event)
            try:
                receipt = load(event.get('result_ref'))
                if not isinstance(receipt, dict):
                    raise ValueError('receipt_not_object')
            except errors:
                mark('check_run_join', 'not_assessable', 'check_receipt_unavailable', [event['seq']])
                continue
            runs.append((event, data, receipt))
            writes = [e for e in events[:index] if e.get('kind') == 'artifact_write']
            target = writes[-1] if writes else submit
            expected = digest(target) if target else None
            fields = ('runner', 'candidate_sha256', 'check_id', 'status')
            if any(k not in receipt for k in fields) or not expected or not data.get('candidate_sha256') or not data.get('check_id'):
                mark('check_run_join', 'not_assessable', 'missing_check_join_metadata', [event['seq']])
            elif (receipt['runner'] != event.get('producer') or receipt['check_id'] != data['check_id']
                  or receipt['candidate_sha256'] != data['candidate_sha256']
                  or receipt['candidate_sha256'] != expected
                  or receipt.get('runner_candidate_sha256', expected) != expected):
                mark('check_run_join', 'fail', 'check_receipt_join_mismatch', [event['seq'], target['seq']])

        required = policy.get('required_pre_submit_checks')
        final_runs = []
        if required is None or submit is None:
            for cid in ('pre_submit_checks', 'no_edit_after_check'):
                mark(cid, 'not_assessable', 'missing_submit_or_check_policy')
        else:
            for check_id in required:
                matches = [(e, d, r) for e, d, r in runs if d.get('check_id') == check_id and e['seq'] < submit['seq']]
                # The latest run controls: an earlier pass cannot mask a failed rerun.
                if not matches or str(matches[-1][2].get('status', '')).lower() != 'pass':
                    mark('pre_submit_checks', 'fail', 'required_passing_check_missing:' + check_id,
                         [e['seq'] for e, _, _ in matches] + [submit['seq']])
                else:
                    final_runs.append(matches[-1])
            if required and len(final_runs) != len(required):
                mark('no_edit_after_check', 'not_assessable', 'required_final_checks_unavailable')
            elif final_runs:
                last = max(e['seq'] for e, _, _ in final_runs)
                for e in events:
                    if last < e['seq'] < submit['seq']:
                        data = metadata(e)
                        mutation = e.get('kind') == 'artifact_write' or (e.get('kind') == 'tool_call' and
                            (data.get('mutates_candidate') is True or 'after_sha256' in data or 'before_sha256' in data))
                        if mutation:
                            mark('no_edit_after_check', 'fail', 'candidate_mutated_after_checks', [e['seq'], last, submit['seq']])
                if not digest(submit):
                    mark('no_edit_after_check', 'not_assessable', 'submit_candidate_unavailable', [submit['seq']])
                elif any(r.get('candidate_sha256') != digest(submit) for _, _, r in final_runs):
                    mark('no_edit_after_check', 'fail', 'submitted_candidate_differs_from_checks',
                         [e['seq'] for e, _, _ in final_runs] + [submit['seq']])

        terminal = manifest.get('terminal', {})
        final_digest = terminal.get('final_artifact_sha256') if isinstance(terminal, dict) else None
        raw_artifact = artifact_bytes if artifact_bytes is not None else blobs.get(final_digest)
        artifact = None
        try:
            artifact = _json(raw_artifact)
        except errors:
            pass
        claims = manifest.get('claims', [])
        claims = claims if isinstance(claims, list) else []
        result_events = {e['seq']: e for e in events if e.get('result_ref') is not None
                         and e.get('kind') in ('tool_result', 'model_call', 'tool_call', 'check_run')}
        for claim in claims:
            if not isinstance(claim, dict):
                mark('numeric_derivation', 'fail', 'malformed_claim')
                continue
            seqs = claim.get('evidence_event_seqs', [])
            kind = claim.get('kind')
            if kind in ('unsupported', 'unmeasured'):
                mark('numeric_derivation', 'not_assessable', 'claim_not_assertable', seqs)
                continue
            if not seqs or any(seq not in result_events for seq in seqs):
                mark('numeric_derivation', 'fail', 'claim_result_event_missing', seqs)
                continue
            if kind == 'evidence':
                continue
            if kind != 'derivation':
                mark('numeric_derivation', 'fail', 'unknown_claim_kind', seqs)
                continue
            try:
                derivation = claim['derivation']
                recorded = {result_events[s]['result_ref']['sha256'] for s in seqs}
                operands = derivation['operands']
                if any(ref['sha256'] not in recorded for ref in operands):
                    mark('numeric_derivation', 'fail', 'operand_not_recorded_result', seqs)
                    continue
                values = [_pointer(load(ref), ref.get('pointer', '')) for ref in operands]
                expected = _derive(derivation['op'], values)
            except KeyError:
                mark('numeric_derivation', 'not_assessable', 'operand_blob_or_pointer_unavailable', seqs)
                continue
            except errors:
                mark('numeric_derivation', 'fail', 'invalid_derivation', seqs)
                continue
            if artifact is None:
                mark('numeric_derivation', 'not_assessable', 'claimed_value_unavailable', seqs)
                continue
            try:
                if expected != _number(_pointer(artifact, claim['output_pointer'])):
                    mark('numeric_derivation', 'fail', 'derived_value_mismatch', seqs)
            except errors:
                mark('numeric_derivation', 'fail', 'invalid_claimed_value', seqs)

        cid = 'claim_coverage_and_artifact'
        if artifact_bytes is not None:
            if not isinstance(artifact_bytes, bytes) or hashlib.sha256(artifact_bytes).hexdigest() != final_digest:
                mark(cid, 'fail', 'final_artifact_digest_mismatch')
        if submit and digest(submit) and final_digest != digest(submit):
            mark(cid, 'fail', 'terminal_submit_digest_mismatch', [submit['seq']])
        if 'claim_coverage_required' not in policy:
            mark(cid, 'not_assessable', 'missing_coverage_policy')
        elif policy['claim_coverage_required']:
            pointers = metadata(submit).get('claimed_output_pointers') if submit else None
            if pointers is None and artifact is not None:
                pointers = list(_leaves(artifact))
            if not isinstance(pointers, list):
                mark(cid, 'not_assessable', 'claimed_output_pointers_unavailable')
            else:
                supported = {c.get('output_pointer') for c in claims if isinstance(c, dict)
                             and c.get('kind') in ('evidence', 'derivation') and c.get('evidence_event_seqs')}
                if any(p not in supported for p in pointers):
                    mark(cid, 'fail', 'claimed_output_lacks_support')
                if artifact is not None:
                    for pointer in pointers:
                        try:
                            _pointer(artifact, pointer)
                        except errors:
                            mark(cid, 'fail', 'claimed_output_pointer_missing')

    rows = list(checks.values())
    blocking = [r['id'] for r in rows if r['status'] == 'fail']
    return dict(checks=rows, blocking_failures=blocking,
                advance=False if blocking else None if any(r['status'] == 'not_assessable' for r in rows) else True)
