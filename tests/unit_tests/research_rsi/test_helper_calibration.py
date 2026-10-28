"""Public controlled capture vectors, never kernel or IF015 qualification.

No fixture generator, worker, model, custodian ledger or live root is invoked.
The in-memory originals test exact program/profile/source joins independently
of any operational assertion that these simulated receipts really occurred.
"""
import copy
import hashlib
import json

import pytest

from jiuwenswarm.research_rsi.records import encoded
from jiuwenswarm.research_rsi.signing import Signer
from jiuwenswarm.research_rsi.targets import registered_helper
from jiuwenswarm.research_rsi.targets import ranking_preparation as prepmod
from jiuwenswarm.research_rsi.targets.unrelated_helper import (
    NORMALIZE_LABELS_PARENT, preparation_children, preparation_expected,
    preparation_fingerprints,
)
from jiuwenswarm.research_rsi.worker import WORKER_PROGRAM, worker_program, timing_program


class PublicOriginals:
    def __init__(self): self.originals = {}
    def put_bytes(self, raw):
        digest = hashlib.sha256(raw).hexdigest()
        pin = {'id': digest + '.json', 'sha256': digest}
        self.originals[pin['id']] = raw
        return pin
    def put(self, value): return self.put_bytes(encoded(value))
    def read(self, pin):
        raw = self.originals[pin['id']]
        assert hashlib.sha256(raw).hexdigest() == pin['sha256']
        return raw
    def get(self, pin): return json.loads(self.read(pin))


def source_function(raw):
    namespace = {}
    exec(compile(raw, '<public-normalization-control>', 'exec'), namespace)
    return namespace['normalize_labels']


def public_labels(index=0):
    return {'labels': [' Z ' + str(index) + ' ', 'A ' + str(index), 'a ' + str(index),
                       '', '   ', 'Straße ' + str(index), 'x  y ' + str(index)]}


def test_normalization_controls_are_actual_faults_and_preserve_validation():
    controls = preparation_children(NORMALIZE_LABELS_PARENT)
    assert len({row['body'] for row in controls}) == 13
    value = public_labels(); expected = preparation_expected(value)
    for row in controls:
        inputs = copy.deepcopy(value['labels'])
        function = source_function(row['body'])
        assert (function(inputs) == expected) == (row['kind'] == 'good'), row['id']
        assert inputs == value['labels']
        with pytest.raises(ValueError): function([1])
    with pytest.raises(ValueError): preparation_children(NORMALIZE_LABELS_PARENT + b'\n')


def public_preparation(store):
    parent = store.put_bytes(NORMALIZE_LABELS_PARENT)
    declaration = store.put({'identity': {'name': 'unit.independent-labels', 'version_label': 'unit',
        'body': [{'path': 'normalize.py', 'sha256': parent['sha256']}]},
        'evolution': {'rsi': 'propose', 'may_change': ['files:normalize.py']}})
    origin = store.put({'unit': 'Public controlled originals; no operational evidence'})
    partitions = {}; provenance = []; serial = 0
    for split, count in [('development', 1), ('hidden_loop', 20), ('hidden_final', 20), ('platform', 1)]:
        rows = []
        for index in range(count):
            value = public_labels(serial); serial += 1
            fingerprints = preparation_fingerprints(value)
            input_ref = store.put(value); expected_ref = store.put(preparation_expected(value))
            case_id = 'case:' + input_ref['sha256']
            rows.append(dict(id=case_id, input_ref=input_ref, expected_ref=expected_ref))
            provenance.append(dict(id=case_id, partition=split, **fingerprints,
                                   expected_sha256=expected_ref['sha256'], generator_unit=index))
        partitions[split] = rows
    children = [dict(id=row['id'], kind=row['kind'], body_ref=store.put_bytes(row['body']))
                for row in preparation_children(NORMALIZE_LABELS_PARENT)]
    prep = dict(schema='ai4r-rsi-helper-preparation:2', target_kind='normalize-labels-v1',
        parent_ref=parent, parent_declaration_ref=declaration, mutable_path='normalize.py',
        author='unit:author', origin_kind='seeded', origin_ref=origin, generator_ref=origin,
        private_seed='unit:public-vector-not-a-private-seed', max_rows=7,
        partitions=partitions, provenance=provenance, prior_preparation_refs=[], children=children,
        status='PENDING_REVIEW_AND_CALIBRATION',
        fixture_identity='normalize-labels-v1-loop:' + prepmod._digest(sorted(
            row['semantic_sha256'] for row in provenance if row['partition'] == 'hidden_loop')),
        split_ids={name: 'split:' + prepmod._digest(sorted(row['input_ref']['sha256'] for row in rows))
                   for name, rows in partitions.items()})
    prep_ref = store.put(prep)
    assert prepmod._read_preparation(store, prep_ref) == prep
    review_ref = store.put(dict(schema='ai4r-rsi-ranking-review:1', preparation_ref=prep_ref,
        reviewer='unit:independent', provenance_approved=True, overlap_inventory_complete=True,
        development_disclosure_approved=False, independent=True,
        independence_reason='Public verifier controls only, not an independence approval', evidence_refs=[origin]))
    target = dict(parent_ref=parent, parent_declaration_ref=declaration, splits=prep['split_ids'],
        scoring=dict(batch_iterations=1000, calibrated_relative_noise=.01, min_relative_gain=.1, noise_multiplier=3),
        limits=dict(memory_mb=128, time_s=1), calibration_ref=prep_ref)
    manifest = dict(partitions=partitions, independent=True, independence_evidence_ref=review_ref,
        calibration_ref=prep_ref, target_ref=prep_ref)
    return prep_ref, prep, review_ref, target, manifest, origin


def controlled_calibration():
    store = PublicOriginals()
    prep_ref, prep, review_ref, target, manifest, origin = public_preparation(store)
    target_ref = store.put(target)
    session_ref = store.put(dict(pass_count_repeats=1, target_profile_ref=target_ref))
    profile = dict(schema='ai4r-rsi-worker-profile:3', target_kind='normalize-labels-v1',
        session_ref=session_ref, target_ref=target_ref, parent_ref=target['parent_ref'],
        contract_ref=origin, environment_ref=origin, hardware_ref=origin,
        memory_mb=128, pids_max=8, timeout_s=.1, process_policy='single_process_seccomp_v1')
    worker_ref = store.put(profile); serial = 0
    def batch(candidate, split, timing=False):
        nonlocal serial
        pins = []
        function = source_function(store.read(candidate))
        for row in manifest['partitions'][split]:
            serial += 1
            output = store.put(function(store.get(row['input_ref'])['labels']))
            reservation = store.put(dict(session_ref=session_ref, candidate_ref=candidate,
                phase=split, fixture_id=row['id'], operation='timing:unit' if timing else 'calibration:unit'))
            receipt = dict(invocation_id='unit:SIMULATED:' + str(serial), observed_runtime=True,
                identity=dict(executor_uid=12003, executor_gid=12003), contract_ref=origin,
                timeout_s=.1, termination_reason='completed', exit_code=0,
                wall_time_s=.02 if candidate == target['parent_ref'] else .01,
                stdout_ref=output, stderr_ref=store.put_bytes(b''),
                observed_limits={'isolation_probe_ref': store.put({'ready': True, 'unit': 'SIMULATED'})})
            program = (timing_program(1000, profile['target_kind'], profile['process_policy']) if timing
                       else worker_program(profile['target_kind'], profile['process_policy']))
            pins.append(store.put(dict(schema='ai4r-rsi-fixture-capture:2', session_ref=session_ref,
                candidate_ref=candidate, fixture_id=row['id'], phase=split, receipt=receipt, timing=timing,
                batch_iterations=1000 if timing else 1, program_sha256=hashlib.sha256(program).hexdigest(),
                worker_profile_ref=worker_ref, input_ref=row['input_ref'], reservation_ref=reservation, repeat_index=0)))
        return pins
    def timing(candidate):
        pins = []
        for index in range(12):
            order = (target['parent_ref'], candidate) if index % 2 == 0 else (candidate, target['parent_ref'])
            for body in order: pins += batch(body, 'hidden_final', True)
        return pins
    noise = timing(target['parent_ref']); controls = []
    for child in prep['children']:
        candidate = child['body_ref']; good = child['kind'] == 'good'
        controls.append(store.put(dict(schema='ai4r-rsi-calibration-control:1', preparation_ref=prep_ref,
            candidate_ref=candidate, mandatory_capture_refs=batch(candidate, 'platform'),
            final_capture_refs=(batch(target['parent_ref'], 'hidden_final') + batch(candidate, 'hidden_final')) if good else [],
            timing_capture_refs=timing(candidate) if good else [])))
    calibration = dict(schema='ai4r-rsi-calibration:2', **prepmod.calibration_contexts(target, manifest),
        preparation_ref=prep_ref, review_ref=review_ref, pass_count_repeats=1, noise_capture_refs=noise,
        control_refs=controls, known_bad_rejected=10, known_good_qualified=3,
        measurable_headroom=True, evidence_refs=[origin])
    return store, calibration, target, manifest, worker_ref


@pytest.fixture(scope='module')
def calibration_vector(): return controlled_calibration()


def verify(store, value, target, manifest):
    signer = Signer.generate('unit:SIMULATED-not-operational')
    return prepmod.verify_calibration2(signer.sign(value), target=target, manifest=manifest,
        store=store, public_key=signer.public_bytes(), key_id=signer.key_id)


def test_complete_normalize_capture_programs_reconcile(calibration_vector):
    store, value, target, manifest, worker_ref = calibration_vector
    actual = verify(store, value, target, manifest)
    assert actual['worker_profile_ref'] == worker_ref
    assert actual['known_bad_rejected'] == 10 and actual['known_good_qualified'] == 3
    assert worker_program() == WORKER_PROGRAM  # Historical ranking bytes retained.


@pytest.mark.parametrize('change', ['ranking_program', 'ranking_profile', 'wrong_expected', 'repeated_invocation'])
def test_normalize_capture_exact_kind_program_and_evidence_mismatch_blocks(calibration_vector, change):
    original, value, target, manifest, _ = calibration_vector
    store = PublicOriginals(); store.originals = dict(original.originals)
    value = copy.deepcopy(value)
    pin = value['noise_capture_refs'][0]; capture = store.get(pin)
    if change == 'ranking_program':
        capture['program_sha256'] = hashlib.sha256(timing_program(1000, 'ranking-v1', 'single_process_seccomp_v1')).hexdigest()
    elif change == 'ranking_profile':
        profile = store.get(capture['worker_profile_ref']); profile['target_kind'] = 'ranking-v1'
        capture['worker_profile_ref'] = store.put(profile)
    elif change == 'wrong_expected':
        capture['receipt']['stdout_ref'] = store.put({'labels': ['wrong-output']})
    else:
        capture['receipt']['invocation_id'] = store.get(value['noise_capture_refs'][1])['receipt']['invocation_id']
    value['noise_capture_refs'][0] = store.put(capture)
    with pytest.raises(ValueError): verify(store, value, target, manifest)
