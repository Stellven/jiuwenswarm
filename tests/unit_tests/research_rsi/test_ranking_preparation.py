"""Preparation controls. Public vectors are not operational hidden datasets."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import pytest

from jiuwenswarm.research_rsi.records import RecordStore
from jiuwenswarm.research_rsi.signing import Signer
from jiuwenswarm.research_rsi.targets.ranking_preparation import (
    CALIBRATION_SCHEMA, calibration_contexts, calibration_inventory, input_fingerprints,
    planted_children, prepare_ranking, require_custodian_store, verify_calibration2,
)

ROOT = Path(__file__).parents[3]
PARENT = ROOT / 'jiuwenswarm/research/resources/capsules/ranking_parent.txt'


def public_scores():
    return [dict(idea_id=name, novelty=n, feasibility=f, compute_alignment=c, eligible=e)
            for name, n, f, c, e in [('z', 5, 5, 5, True), ('a', 5, 5, 5, True),
                                     ('b', 1, 2, 3, True), ('ignored', 5, 5, 5, False)]]


def function(source):
    namespace = {}; exec(compile(source, '<public-calibration-source-control>', 'exec'), namespace)
    return namespace['rank_opportunities']


def test_planted_population_has_ten_real_faults_and_three_distinct_preservation_sources():
    parent = PARENT.read_bytes(); baseline = function(parent); controls = planted_children(parent)
    assert sum(row['kind'] == 'bad' for row in controls) == 10
    assert sum(row['kind'] == 'good' for row in controls) == 3
    assert len({row['body'] for row in controls}) == 13
    scores = public_scores(); expected = baseline(scores)
    for row in controls:
        before = copy.deepcopy(scores)
        actual = function(row['body'])(scores)
        assert (actual == expected) == (row['kind'] == 'good'), row['id']
        assert scores == before
    assert PARENT.read_bytes() == parent


@pytest.mark.parametrize('dimension', ['novelty', 'feasibility', 'compute_alignment'])
def test_preservation_children_retain_sum_three_and_all_dimension_boundaries(dimension):
    good = [function(row['body']) for row in planted_children(PARENT.read_bytes()) if row['kind'] == 'good']
    baseline = function(PARENT.read_bytes())
    for n in range(1, 6):
        scores = public_scores(); scores[2][dimension] = n
        for candidate in good: assert candidate(scores) == baseline(scores)
    for invalid in (True, False, 0, 6, 1.0, '3', None):
        scores = public_scores(); scores[0][dimension] = invalid
        for candidate in [baseline, *good]:
            with pytest.raises(ValueError): candidate(scores)


def test_preservation_children_keep_identity_eligibility_and_no_eligible_rejections():
    functions = [function(PARENT.read_bytes()), *[function(row['body']) for row in planted_children(PARENT.read_bytes()) if row['kind'] == 'good']]
    invalid = []
    for value in ('', None, 1):
        scores = public_scores(); scores[0]['idea_id'] = value; invalid.append(scores)
    scores = public_scores(); scores[0]['idea_id'] = scores[1]['idea_id']; invalid.append(scores)
    for value in (1, 0, 'true', None):
        scores = public_scores(); scores[0]['eligible'] = value; invalid.append(scores)
    scores = public_scores()
    for row in scores: row['eligible'] = False
    invalid.extend([scores, []])
    for scores in invalid:
        for candidate in functions:
            with pytest.raises(ValueError): candidate(copy.deepcopy(scores))


def test_unknown_parent_source_cannot_silently_reuse_planted_controls():
    with pytest.raises(ValueError, match='reviewed calibration adapter'):
        planted_children(b'def rank_opportunities(scores): return scores\n')


def test_overlap_fingerprint_tracks_order_and_identity_renaming_without_false_exact_hash():
    value = {'scores': public_scores()}; changed = copy.deepcopy(value)
    changed['scores'].reverse()
    first = input_fingerprints(value); second = input_fingerprints(changed)
    assert first['input_sha256'] != second['input_sha256']
    assert first['semantic_sha256'] == second['semantic_sha256']
    for row in changed['scores']: row['idea_id'] = 'prefix:' + row['idea_id']
    assert input_fingerprints(changed)['semantic_sha256'] == first['semantic_sha256']
    changed['scores'][0]['novelty'] = 1
    assert input_fingerprints(changed)['semantic_sha256'] != first['semantic_sha256']


def test_calibration_v2_contexts_are_acyclic_and_bind_all_other_fields():
    target = dict(parent_ref={'id': 'parent'}, scoring={'batch_iterations': 1000}, calibration_ref={'id': 'pending'})
    manifest = dict(target_ref={'id': 'pending'}, calibration_ref={'id': 'pending'}, partitions={'hidden_final': ['private-opaque']})
    initial = calibration_contexts(target, manifest)
    target['calibration_ref'] = {'id': 'signed'}
    manifest.update(target_ref={'id': 'final-target'}, calibration_ref={'id': 'signed'})
    assert calibration_contexts(target, manifest) == initial
    target['scoring']['batch_iterations'] += 1
    assert calibration_contexts(target, manifest)['target_context_sha256'] != initial['target_context_sha256']
    manifest['partitions']['hidden_final'].append('another-private-opaque')
    assert calibration_contexts(target, manifest)['fixture_context_sha256'] != initial['fixture_context_sha256']


def test_source_only_signed_calibration_is_not_readiness(tmp_path):
    from jiuwenswarm.research_records.contracts import ContractData
    store = RecordStore(tmp_path); signer = Signer.generate('unit:never-operational')
    pin = store.put({'unit': 'code-only placeholders; no measured calibration'})
    calibration = signer.sign(dict(schema='ai4r-rsi-calibration:2', target_context_sha256='a' * 64,
        fixture_context_sha256='b' * 64, preparation_ref=pin, review_ref=pin, known_bad_rejected=10,
        known_good_qualified=3, measurable_headroom=True, evidence_refs=[pin],
        pass_count_repeats=3, noise_capture_refs=[], control_refs=[]))
    with pytest.raises(ValueError, match='contract validation failed'):
        ContractData().validate(CALIBRATION_SCHEMA, calibration)
    with pytest.raises(ValueError):
        verify_calibration2(calibration, target={}, manifest={}, store=store,
                            public_key=signer.public_bytes(), key_id=signer.key_id)
    store.db.close()


def test_raw_calibration_inventory_counts_frozen_repeats_and_every_paired_round():
    manifest = {'partitions': {'hidden_final': [None] * 20, 'platform': [None] * 12}}
    inventory = calibration_inventory(manifest, 3)
    assert inventory == dict(noise_captures=24 * 20 * 3, bad_control_captures=12 * 3,
                             good_control_captures=12 * 3 + 26 * 20 * 3,
                             total_captures=13 * 12 * 3 + 102 * 20 * 3)
    for repeats in (0, 2, True, 3.0):
        with pytest.raises(ValueError): calibration_inventory(manifest, repeats)


def test_hidden_generation_refuses_non_custodian_without_writing_cases(tmp_path):
    store = RecordStore(tmp_path)
    if sys.platform == 'linux' and os.geteuid() == 12002:
        # This branch verifies store ownership rather than assuming a root runner.
        os.chmod(tmp_path, 0o755)
    with pytest.raises(ValueError): require_custodian_store(store)
    before = set(tmp_path.iterdir())
    with pytest.raises(ValueError):
        prepare_ranking(store, parent_ref={}, parent_declaration_ref={}, declaration={},
                        author='unit', origin_ref={}, generator_ref={})
    assert set(tmp_path.iterdir()) == before
    store.db.close()


def test_actual_linux_custodian_preparation_is_private_pending_and_nonoverlapping():
    # Hidden generation is exercised only inside real Linux tmpfs under the
    # actual custodian UID. No fixture bytes, seed, ID or label leave that child.
    if sys.platform != 'linux' or os.geteuid() != 0:
        assert sys.platform != 'linux' or os.geteuid() != 0
        return
    root = Path(tempfile.mkdtemp(prefix='rsi-preparation-control-', dir='/dev/shm'))
    os.chmod(root, 0o700); os.chown(root, 12002, 12002)
    program = r'''
import copy, os, sys
from pathlib import Path
from jiuwenswarm.research_rsi.records import RecordStore
from jiuwenswarm.research_rsi.targets.ranking_preparation import prepare_ranking,development_export,draft_target,freeze_prepared_target
import jiuwenswarm.research_rsi.targets.ranking_preparation as preparation_module
from jiuwenswarm.research_rsi.fixed_resources import FixtureEvaluator
from jiuwenswarm.research_records.contracts import ContractData
os.setgid(12002);os.setuid(12002);os.umask(0o077)
root=Path(sys.argv[1]);store=RecordStore(root)
parent=store.put_bytes(Path(sys.argv[2]).read_bytes())
declaration={'identity':{'name':'research.screening','body':[{'path':'ranking_parent.txt','sha256':parent['sha256']}]},'evolution':{'rsi':'propose','may_change':['files:ranking_*.txt']}}
decl=store.put(declaration);origin=store.put({'unit':'seeded custody control; no admission or runtime calibration'})
generator=store.put_bytes(Path(preparation_module.__file__).read_bytes())
kwargs=dict(parent_ref=parent,parent_declaration_ref=decl,declaration=declaration,author='unit:author',origin_ref=origin,generator_ref=generator)
pin=prepare_ranking(store,**kwargs,seed='unit:private-seed-0001')
prep=store.get(pin)
assert prep['status']=='PENDING_REVIEW_AND_CALIBRATION'
assert all(len(prep['partitions'][name])>=20 for name in ['hidden_loop','hidden_final'])
assert len(prep['provenance'])==64
assert all(1<=len(store.get(row['input_ref'])['scores'])<=3 for rows in prep['partitions'].values() for row in rows)
assert len({row['semantic_sha256'] for row in prep['provenance']})==64
assert len({row['id'] for rows in prep['partitions'].values() for row in rows})==64
second=store.get(prepare_ranking(store,**kwargs,seed='unit:private-seed-0001',prior_preparation_refs=[pin]))
assert not ({row['semantic_sha256'] for row in prep['provenance']}&{row['semantic_sha256'] for row in second['provenance']})
assert second['prior_preparation_refs']==[pin]
review=store.put(dict(schema='ai4r-rsi-ranking-review:1',preparation_ref=pin,reviewer='unit:independent-review',development_disclosure_approved=True,provenance_approved=True,overlap_inventory_complete=True,independent=False,independence_reason='Controlled unit fixtures do not establish statistical independence',evidence_refs=[origin]))
visible=development_export(store,pin,approved_review_ref=review)
assert len(visible['cases'])==12 and set(visible)=={'schema','parent_ref','cases'}
assert all(row['id'] in {c['id'] for c in prep['partitions']['development']} for row in visible['cases'])
template={'scoring':{'warmup_batches':5,'paired_rounds':7,'min_relative_gain':.1,'noise_multiplier':3,'batch_iterations':1000},'protected_refs':[origin],'session_query_limit':30,'lifetime_query_limit':90,'limits':{'time_s':1,'model_calls':1,'memory_mb':128}}
target,manifest=draft_target(store,pin,template,review_ref=review,validate=lambda *args:None)
assert manifest['independent'] is False
FixtureEvaluator(manifest=manifest,store=store,worker=None,session_ref=origin,target=target,repeats=3)
changed=copy.deepcopy(prep);changed['provenance'][0]['expected_sha256']='0'*64
changed_pin=store.put(changed)
changed_review=store.put(dict(store.get(review),preparation_ref=changed_pin))
try:draft_target(store,changed_pin,template,review_ref=changed_review,validate=lambda *args:None)
except ValueError:pass
else:raise AssertionError('changed provenance accepted')
changed=copy.deepcopy(prep);changed['children'][0]['body_ref']=parent
changed_pin=store.put(changed)
changed_review=store.put(dict(store.get(review),preparation_ref=changed_pin))
try:draft_target(store,changed_pin,template,review_ref=changed_review,validate=lambda *args:None)
except ValueError:pass
else:raise AssertionError('changed planted child accepted')
try:prepare_ranking(store,**kwargs,populations={'development':1,'hidden_loop':19,'hidden_final':20,'platform':1})
except ValueError:pass
else:raise AssertionError('undersized hidden split accepted')
try:prepare_ranking(store,**kwargs,max_rows=64)
except ValueError:pass
else:raise AssertionError('broadened incoming score contract accepted')
try:prepare_ranking(store,**dict(kwargs,generator_ref=origin))
except ValueError:pass
else:raise AssertionError('unattributed generator accepted')
assert Path(sys.argv[2]).read_bytes()==store.read(parent)
assert all(path.stat().st_uid==12002 and not path.stat().st_mode&0o077 for path in root.iterdir())
store.db.close()
import shutil
shutil.rmtree(root)
'''
    completed = subprocess.run([sys.executable, '-B', '-c', program, str(root), str(PARENT)],
                               capture_output=True, text=True, timeout=60)
    # Keep generated fixtures only in protected tmpfs; parent never reads them.
    assert completed.returncode == 0, completed.stderr
    assert not root.exists()
    assert completed.stdout == ''
