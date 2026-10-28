"""Measured opportunity qualification, independent of proposer optimism.

The legacy ``decide`` helper is not an intake or an evidence authority. Runtime
callers use ``produce_opportunity`` with a host-captured preparation allowlist.
"""
import math
import hashlib
import json
import statistics
from datetime import datetime, timezone

from .diagnosis import BoundedDiagnosis, closed_json, diagnosis_prompt
from .custody import ExposureError
from .mutation import SecurityViolation
from .profiles import freeze_profile
from .records import encoded
from .session_policy import _contracts, validate_private
from .targets import registered_helper
from .worker import validate_profile, validate_request

PREPARATION_SCHEMA = 'urn:ai4r:private:rsi-opportunity-preparation:1'
REVIEW_SCHEMA = 'urn:ai4r:private:rsi-opportunity-review:1'


def decide(*,attribution,symptom_reproduced,mandatory_passed,headroom,headroom_minimum,diagnosis,resource_ready=True):
    if not resource_ready:return {'decision':None,'readiness':'BLOCKED','reason':'required target resource unavailable'}
    if attribution=='uncertain':return {'decision':'NEEDS_REVIEW','reason':'implementation attribution uncertain'}
    if attribution!='implementation' or not symptom_reproduced or not mandatory_passed:return {'decision':'NO_ATTEMPT','reason':'implementation opportunity prerequisites failed'}
    if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or not 0<=x<=1 for x in (headroom,headroom_minimum)):return {'decision':'NO_ATTEMPT','reason':'measured headroom unavailable'}
    if headroom<headroom_minimum:return {'decision':'NO_ATTEMPT','reason':'measured headroom below profile minimum'}
    if not isinstance(diagnosis,dict) or not all(diagnosis.get(k) for k in ('cause','alternatives','falsification')):return {'decision':'NEEDS_REVIEW','reason':'structured diagnosis incomplete'}
    return {'decision':'START','reason':'reproduced implementation opportunity with measured headroom'}


def _read(store, pin):
    """Always verify exact bytes, including stores with non-hash identifiers."""
    raw = store.read(pin)
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError('Opportunity evidence exceeds the fixed transport bound')
    if hashlib.sha256(raw).hexdigest() != pin['sha256']:
        raise ValueError('Opportunity evidence original bytes differ')
    return raw


def _get(store, pin):
    return closed_json(_read(store, pin))


def _key(pin):
    return encoded(pin)


def validated_preparation(store, preparation_ref, *, approved_preparation_refs,
                          profile_ref, parent):
    """Read-only, independently measured facts from a host-approved original.

    ``approved_preparation_refs`` is installed protected runtime authority. It
    must never be copied from a submitted job, model answer or preparation.
    No lookup outside the explicit closure or hidden split is performed.
    """
    if preparation_ref not in approved_preparation_refs:
        raise ValueError('Preparation has no protected host approval')
    prep = _get(store, preparation_ref)
    validate_private(PREPARATION_SCHEMA, prep)
    if prep['target_profile_ref'] != profile_ref or prep['parent'] != parent:
        raise ValueError('Prepared target or exact parent differs')
    target = _get(store, profile_ref)
    declaration = _get(store, target['parent_declaration_ref'])
    freeze_profile(target, declaration, _contracts().validate)
    identity = declaration['identity']
    if (parent != {'cc_name': identity['name'], 'cc_version': identity['version_label'],
                   'declaration_sha256': target['parent_declaration_ref']['sha256']}
            or prep['parent_ref'] != target['parent_ref']
            or prep['parent_declaration_ref'] != target['parent_declaration_ref']
            or prep['configuration_ref'] != target['configuration_ref']
            or prep['development_ref'] != target['splits']['development']):
        raise ValueError('Preparation closure differs from the exact frozen profile')
    _read(store, target['parent_ref'])
    worker = validate_profile(_get(store, prep['worker_profile_ref']))
    if worker['target_ref'] != profile_ref or worker['parent_ref'] != target['parent_ref']:
        raise ValueError('Visible worker target or parent differs')
    review = _get(store, prep['review_ref'])
    validate_private(REVIEW_SCHEMA, review)
    if (review['target_profile_ref'] != profile_ref or review['parent'] != parent
            or review['configuration_ref'] != target['configuration_ref']
            or review['worker_profile_ref'] != prep['worker_profile_ref']
            or review['prepared_by'] == review['reviewer']
            or review['headroom_minimum'] != prep['headroom_minimum']):
        raise ValueError('Independent visible evidence review scope differs')
    forbidden = {_key(pin) for pin in target['protected_refs']}
    protected_hashes = {pin['sha256'] for pin in target['protected_refs']}
    forbidden.update(_key(target['splits'][name]) for name in ('hidden_loop', 'hidden_final', 'platform'))
    approved = {_key(pin) for pin in review['approved_evidence_refs']}
    if forbidden & approved or any(pin['sha256'] in protected_hashes for pin in review['approved_evidence_refs']):
        raise ValueError('Evidence disclosure overlaps a protected target resource')
    visible = set()
    for row in prep['evidence']:
        key = _key(row['ref'])
        if key not in approved or key in visible:
            raise ValueError('Diagnosis evidence is not independently approved or is duplicated')
        visible.add(key)
        _read(store, row['ref'])

    def check(row, candidate):
        # A capture does not decide its own audience. Every byte it references
        # must already be part of the independently approved visible export.
        for name in ('input_ref', 'expected_ref', 'capture_ref'):
            if _key(row[name]) not in approved:
                raise ValueError('Visible measurement references unapproved evidence')
            _read(store, row[name])
        registered_helper(worker['target_kind']).validate_visible_inputs(_get(store, row['input_ref']))
        capture = _get(store, row['capture_ref'])
        if (not isinstance(capture, dict) or set(capture) != {'schema', 'request', 'receipt'}
                or capture['schema'] != 'ai4r-rsi-worker-receipt:1'):
            raise ValueError('Original visible worker capture unavailable')
        request = validate_request(capture['request'])
        if (request['profile_ref'] != prep['worker_profile_ref']
                or request['session_ref'] != worker['session_ref']
                or request['candidate_ref'] != candidate or request['input_ref'] != row['input_ref']
                or request['phase'] != 'development' or request['repeat_index'] != 0):
            raise ValueError('Worker capture is not the exact approved visible measurement')
        receipt = capture['receipt']
        if (not isinstance(receipt, dict) or receipt.get('subject_ref') != candidate
                or receipt.get('contract_ref') != worker['contract_ref']
                or receipt.get('hardware_ref') != worker['hardware_ref']
                or receipt.get('observed_runtime') is not True
                or receipt.get('identity') != {'executor_uid': 12003, 'executor_gid': 12003}
                or receipt.get('termination_reason') != 'completed' or receipt.get('exit_code') != 0
                or type(receipt.get('wall_time_s')) not in (int, float)
                or not math.isfinite(receipt['wall_time_s']) or receipt['wall_time_s'] <= 0):
            raise ValueError('Observed visible worker execution is incomplete or foreign')
        stdout = receipt.get('stdout_ref')
        if _key(stdout) not in approved:
            raise ValueError('Visible output is outside the reviewed evidence export')
        actual = _get(store, stdout)
        expected = _get(store, row['expected_ref'])
        return actual == expected, receipt['wall_time_s']

    required = {_key(pin) for pin in target['required_test_refs']}
    actual_tests = {_key(row['test_ref']) for row in prep['mandatory_checks']}
    if required != actual_tests:
        raise ValueError('Prepared visible mandatory obligations are incomplete')
    mandatory = [check(row, target['parent_ref']) for row in prep['mandatory_checks']]
    development = [check(row, target['parent_ref']) for row in prep['development_checks']]
    quality_headroom = sum(not passed for passed, _ in development) / len(development)
    measured = quality_headroom
    timing = prep['timing']
    if timing is not None:
        if (timing['reference_ref'] == target['parent_ref']
                or timing['reference_ref'] not in review['approved_reference_refs']):
            raise ValueError('Timing reference lacks independent semantics and scope approval')
        _read(store, timing['reference_ref'])
        score = target['scoring']
        if (score['warmup_batches'] != 5 or score['paired_rounds'] != 7
                or score['min_relative_gain'] < .1 or score['noise_multiplier'] < 3
                or not math.isfinite(score['calibrated_relative_noise'])
                or score['calibrated_relative_noise'] < 0):
            raise ValueError('Frozen timing policy is unavailable or widened')
        p_times, r_times = [], []
        timing_captures = set()
        previous_end = None
        # Each paired round covers the same reviewed visible batch. The
        # external worker duration is used; candidate-authored clocks are not.
        expected_inputs = [row['input_ref'] for row in prep['development_checks']]
        for index, round_ in enumerate(timing['rounds']):
            totals = []
            windows = {}
            for side, candidate in (('parent', target['parent_ref']), ('reference', timing['reference_ref'])):
                rows = round_[side + '_checks']
                if ([row['input_ref'] for row in rows] != expected_inputs
                        or [row['expected_ref'] for row in rows] != [row['expected_ref'] for row in prep['development_checks']]):
                    raise ValueError('Timing comparison changed the approved input/output batch')
                values = [check(row, candidate) for row in rows]
                starts, ends = [], []
                for row in rows:
                    if _key(row['capture_ref']) in timing_captures:
                        raise ValueError('Timing rounds reuse an original measurement')
                    timing_captures.add(_key(row['capture_ref']))
                    receipt = _get(store, row['capture_ref'])['receipt']
                    try:
                        start = datetime.fromisoformat(receipt['started_at'].replace('Z', '+00:00'))
                        end = datetime.fromisoformat(receipt['ended_at'].replace('Z', '+00:00'))
                    except (KeyError, ValueError, AttributeError):
                        raise ValueError('Timing measurement chronology unavailable') from None
                    if start.tzinfo is None or end.tzinfo is None or end < start:
                        raise ValueError('Timing measurement chronology is invalid')
                    starts.append(start); ends.append(end)
                windows[side] = (min(starts), max(ends))
                if not all(passed for passed, _ in values):
                    raise ValueError('Timing reference or parent changed required visible quality')
                totals.append(sum(duration for _, duration in values))
            first, second = ('parent', 'reference') if index % 2 == 0 else ('reference', 'parent')
            if windows[first][1] > windows[second][0]:
                raise ValueError('Visible timing rounds are not alternating paired measurements')
            if previous_end is not None and previous_end > windows[first][0]:
                raise ValueError('Visible timing rounds overlap or reorder measurements')
            previous_end = windows[second][1]
            if index >= 5:
                p_times.append(totals[0]); r_times.append(totals[1])
        gain = max(0., 1 - statistics.median(r_times) / statistics.median(p_times))
        if gain >= score['min_relative_gain'] and gain > score['noise_multiplier'] * score['calibrated_relative_noise']:
            measured = max(measured, gain)
    return {'preparation': prep, 'target': target, 'review': review,
        'symptom_reproduced': measured > 0,
        'parent_mandatory_passed': all(passed for passed, _ in mandatory),
        'headroom': measured, 'headroom_minimum': prep['headroom_minimum'],
        'parent_visible_time_s': sum(duration for _, duration in mandatory)}


def _prerequisite_decision(facts):
    prep = facts['preparation']
    if prep['attribution'] == 'uncertain':
        return 'NEEDS_REVIEW', 'Implementation attribution remains uncertain after visible reproduction'
    if prep['attribution'] != 'implementation':
        return 'NO_ATTEMPT', 'Visible evidence attributes the symptom outside the implementation'
    if not facts['parent_mandatory_passed']:
        return 'NO_ATTEMPT', 'Exact parent failed required visible mandatory behavior'
    if not facts['symptom_reproduced']:
        return 'NO_ATTEMPT', 'No relevant symptom or calibrated timing headroom reproduced on approved visible inputs'
    if facts['headroom'] < facts['headroom_minimum']:
        return 'NO_ATTEMPT', 'Measured development headroom is below the independently frozen minimum'
    return None, None


async def produce_opportunity(store, *, profile_ref, parent, preparation_ref,
        approved_preparation_refs, model, opportunity_id, selected_by,
        trigger='operator_selected', limits=None, resource_ready=True,
        expected_worker_profile_ref=None):
    """Create canonical output; invalid evidence never causes model dispatch.

    Resource readiness and the allowlist are protected host inputs, never values
    interpreted from the model. A blocked result is canonically NO_ATTEMPT;
    BLOCKED is returned separately because it is not a public decision enum.
    """
    record = {'schema_version': '1.0.0', 'id': opportunity_id,
        'target_profile_ref': profile_ref, 'parent': parent, 'trigger': trigger,
        'selected_by': selected_by, 'evidence_refs': [preparation_ref],
        'attribution': 'uncertain', 'symptom_reproduced': False,
        'parent_mandatory_passed': False, 'headroom': None, 'headroom_minimum': 0,
        'diagnosis_ref': None, 'decision': 'NO_ATTEMPT',
        'reason': 'Required independently approved visible evidence unavailable',
        'decided_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}
    readiness = 'BLOCKED'
    facts = None
    capture_ref = None
    try:
        prepared_facts = validated_preparation(store, preparation_ref,
            approved_preparation_refs=approved_preparation_refs, profile_ref=profile_ref, parent=parent)
        if (expected_worker_profile_ref is not None
                and prepared_facts['preparation']['worker_profile_ref'] != expected_worker_profile_ref):
            raise ValueError('Prepared visible worker differs from the protected current session')
        facts = prepared_facts
    except (ValueError, KeyError, TypeError, OSError, RecursionError):
        # Record the missing original selection itself, never fabricate a
        # replacement measurement or silently reduce obligations.
        pass
    else:
        prep = facts['preparation']
        record.update(attribution=prep['attribution'],
            symptom_reproduced=facts['symptom_reproduced'],
            parent_mandatory_passed=facts['parent_mandatory_passed'],
            headroom=facts['headroom'], headroom_minimum=facts['headroom_minimum'])
        record['evidence_refs'] += [prep['review_ref']] + [row['ref'] for row in prep['evidence']]
        decision, reason = _prerequisite_decision(facts)
        if resource_ready is not True or model is None:
            record['reason'] = 'Required governed diagnosis or target resource unavailable'
        elif decision is not None:
            readiness = 'READY'
            record.update(decision=decision, reason=reason)
        else:
            bounded = BoundedDiagnosis(model, store=store, limits=limits)
            try:
                _, pin = await bounded.diagnose(parent=parent, profile_ref=profile_ref,
                    preparation_ref=preparation_ref, configuration_ref=prep['configuration_ref'],
                    authorized_component=facts['target']['mutable_paths'][0],
                    observed_symptom=prep['observed_symptom'], evidence=prep['evidence'])
            except (ExposureError, SecurityViolation):
                # BoundedDiagnosis has already durably retained the exact
                # prompt and available bridge completion evidence. Unknown
                # effects and security halts belong to controller containment,
                # never an ordinary ineligible-opportunity disposition.
                raise
            except Exception:
                readiness = 'READY'
                record.update(decision='NEEDS_REVIEW', reason='Bounded diagnosis unavailable, malformed or outside approved evidence/component scope')
                if bounded.last_capture_ref is not None:
                    capture = _get(store, bounded.last_capture_ref)
                    if capture['response_ref'] is None:
                        readiness = 'BLOCKED'
            else:
                capture = _get(store, bounded.last_capture_ref)
                record['diagnosis_ref'] = pin
                readiness = 'READY'
                if capture['status'] != 'validated' or capture['model_calls'] != 1 or not capture['generation_evidence_refs']:
                    record.update(decision='NEEDS_REVIEW', reason='Attributable completed governed diagnosis evidence unavailable')
                else:
                    record.update(decision='START', reason='Reproduced implementation opportunity with independently measured visible headroom and bounded grounded diagnosis')
            capture_ref = bounded.last_capture_ref
            if capture_ref is not None:
                record['evidence_refs'].append(capture_ref)
    _contracts().validate('rsi-opportunity', record)
    pin = store.put(record)
    return {'record': record, 'ref': pin, 'readiness': readiness,
        'diagnosis_capture_ref': capture_ref,
        'parent_visible_time_s': facts['parent_visible_time_s'] if facts else None}


def validate_opportunity(store, opportunity_ref, *, preparation_ref,
        approved_preparation_refs, profile_ref, parent):
    """Reconcile canonical START and original diagnosis without another call."""
    record = _get(store, opportunity_ref)
    _contracts().validate('rsi-opportunity', record)
    facts = validated_preparation(store, preparation_ref,
        approved_preparation_refs=approved_preparation_refs, profile_ref=profile_ref, parent=parent)
    prep = facts['preparation']
    if (record['target_profile_ref'] != profile_ref or record['parent'] != parent
            or preparation_ref not in record['evidence_refs']
            or record['attribution'] != prep['attribution']
            or any(record[key] != facts[key] for key in ('symptom_reproduced', 'parent_mandatory_passed', 'headroom', 'headroom_minimum'))):
        raise ValueError('Canonical opportunity differs from independently prepared facts')
    expected_evidence = [preparation_ref, prep['review_ref']] + [row['ref'] for row in prep['evidence']]
    if (record['evidence_refs'][:len(expected_evidence)] != expected_evidence
            or len(record['evidence_refs']) not in (len(expected_evidence), len(expected_evidence) + 1)):
        raise ValueError('Canonical opportunity evidence selection differs from the approved export')
    if record['decision'] == 'START':
        if _prerequisite_decision(facts)[0] is not None or record['diagnosis_ref'] is None:
            raise ValueError('Canonical START lacks independently established prerequisites')
        diagnosis = _get(store, record['diagnosis_ref'])
        validate_private('urn:ai4r:private:rsi-diagnosis:1', diagnosis)
        if (diagnosis['authorized_component'] != facts['target']['mutable_paths'][0]
                or not {_key(pin) for pin in diagnosis['supporting_visible_evidence']} <= {_key(row['ref']) for row in prep['evidence']}):
            raise ValueError('Retained diagnosis differs from approved component/evidence')
        if len(record['evidence_refs']) != len(expected_evidence) + 1:
            raise ValueError('Opportunity lacks one attributable diagnosis capture')
        capture = _get(store, record['evidence_refs'][-1])
        validate_private('urn:ai4r:private:rsi-diagnosis-capture:1', capture)
        if (capture['preparation_ref'] != preparation_ref or capture['target_profile_ref'] != profile_ref
                or capture['parent'] != parent or capture['configuration_ref'] != prep['configuration_ref']
                or capture['diagnosis_ref'] != record['diagnosis_ref'] or capture['status'] != 'validated'
                or capture['model_calls'] != 1 or not capture['generation_evidence_refs']
                or _get(store, capture['response_ref']) != diagnosis):
            raise ValueError('Diagnosis capture original binding/response differs')
        for pin in capture['generation_evidence_refs']:
            _read(store, pin)
        expected_prompt = diagnosis_prompt(authorized_component=facts['target']['mutable_paths'][0],
            observed_symptom=prep['observed_symptom'], evidence=prep['evidence']).encode('utf8')
        if _read(store, capture['prompt_ref']) != expected_prompt:
            raise ValueError('Retained diagnosis prompt differs from approved context recipe')
    return {**facts, 'record': record}
