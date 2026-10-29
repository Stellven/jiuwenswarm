"""Custodian-only Target 1 preparation. Generated suites are never source assets.

Preparation is deliberately not readiness: independently reviewed provenance and
real signed calibration remain prerequisites. No candidate code executes here.
"""
from __future__ import annotations

import copy
import fnmatch
import hashlib
import math
import os
from pathlib import Path
import random
import secrets
import stat
import sys

from ..profiles import freeze_profile, safe_path
from ..records import RecordStore, encoded
from ..worker import ref

PARTITIONS = ('development', 'hidden_loop', 'hidden_final', 'platform')
CALIBRATION_SCHEMA = 'urn:ai4r:private:rsi-calibration:2'
PREPARATION_SCHEMA = 'urn:ai4r:private:rsi-ranking-preparation:1'
REVIEW_SCHEMA = 'urn:ai4r:private:rsi-ranking-review:1'
HELPER_PREPARATION_SCHEMA = 'urn:ai4r:private:rsi-helper-preparation:2'


def preparation_kind(prep):
    """Original closed preparation selects only an installed finite adapter."""
    from ..session_policy import validate_private
    if prep.get('schema') == 'ai4r-rsi-ranking-preparation:1':
        validate_private(PREPARATION_SCHEMA, prep)
        return 'ranking-v1'
    validate_private(HELPER_PREPARATION_SCHEMA, prep)
    return prep['target_kind']


def _preparation_adapter(kind):
    from types import SimpleNamespace
    from . import registered_helper
    helper = registered_helper(kind)
    if kind == 'ranking-v1':
        return SimpleNamespace(helper=helper, case=_case, expected=_expected,
                               fingerprints=input_fingerprints, children=planted_children, max_rows=3)
    from .unrelated_helper import (preparation_case, preparation_expected,
        preparation_fingerprints, preparation_children)
    if kind != 'normalize-labels-v1': raise ValueError('Unknown installed preparation adapter')
    return SimpleNamespace(helper=helper, case=preparation_case, expected=preparation_expected,
                           fingerprints=preparation_fingerprints, children=preparation_children, max_rows=7)


def _digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def require_custodian_store(store):
    """Refuse Windows/bind-mounted, shared, published, or wrong-owner stores."""
    if sys.platform != 'linux' or os.geteuid() != 12002:
        raise ValueError('Preparation requires the Linux custodian identity')
    if type(store) is not RecordStore or store.file_mode != 0o600:
        raise ValueError('Preparation requires an unpublished private RecordStore')
    root = store.root
    if not root.is_absolute() or any(p.is_symlink() for p in (root, *root.parents)):
        raise ValueError('Unsafe private preparation store')
    meta = root.stat()
    if not stat.S_ISDIR(meta.st_mode) or meta.st_uid != 12002 or stat.S_IMODE(meta.st_mode) != 0o700:
        raise ValueError('Preparation store must be privately custodian owned')
    # Windows drives presented through WSL/Docker cannot supply Linux custody.
    import ctypes
    class FS(ctypes.Structure):
        _fields_ = [('kind', ctypes.c_long), ('padding', ctypes.c_byte * 248)]
    info = FS()
    if ctypes.CDLL(None, use_errno=True).statfs(os.fsencode(root), ctypes.byref(info)):
        raise ValueError('Preparation filesystem custody unavailable')
    if info.kind in (0x9fa0, 0x01021997, 0x65735546, 0x5346544e):
        raise ValueError('Non-Linux preparation filesystem refused')
    for path in root.iterdir():
        metadata = path.lstat()
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != 12002
                or metadata.st_mode & 0o077 or metadata.st_nlink != 1):
            raise ValueError('Preparation store contains nonprivate bytes')
    return store


def input_fingerprints(value):
    """Exact and permutation/identity-renaming invariant overlap fingerprints."""
    rows = value['scores']
    # Rank identity order still matters for ties. Replace IDs with their lexical
    # ordinal before comparing; mere ID renaming must not renew hidden lineage.
    order = {name: i for i, name in enumerate(sorted(row['idea_id'] for row in rows))}
    normalized = [dict(row, idea_id=order[row['idea_id']]) for row in rows]
    normalized.sort(key=lambda row: row['idea_id'])
    return {'input_sha256': _digest(value), 'semantic_sha256': _digest({'scores': normalized})}


def _expected(value):
    # Separate data-only oracle, independent of both installed parent and planted
    # source bodies. Review must establish its suitability; this is not approval.
    records = []
    for score in value['scores']:
        if score['eligible']:
            records.append((score['novelty'] + score['feasibility'] + score['compute_alignment'], score['idea_id']))
    records.sort(key=lambda row: (-row[0], row[1]))
    return {'ranking': [{'rank': i + 1, 'idea_id': name, 'total': total}
                        for i, (total, name) in enumerate(records)], 'selected_idea_id': records[0][1]}


def _case(rng, count, mode):
    rows = []
    prefix = rng.getrandbits(128).to_bytes(16, 'big').hex()
    for index in range(count):
        rows.append({'idea_id': prefix + ':' + str(index), 'novelty': rng.randint(1, 5),
                     'feasibility': rng.randint(1, 5), 'compute_alignment': rng.randint(1, 5),
                     'eligible': bool(rng.randrange(3))})
    # Actual Screening inputs contain at most three ideas. Timing headroom uses
    # repeated batches, never a broadened input contract. Coverage patterns are
    # correlated and require independent review before statistical use.
    if count == 3 and mode == 0:
        for index in (0, 1):
            rows[index].update(novelty=5, feasibility=5, compute_alignment=5, eligible=True)
        rows[2].update(novelty=rng.randint(1, 4), feasibility=rng.randint(1, 4),
                       compute_alignment=rng.randint(1, 4), eligible=True)
    elif count == 3 and mode == 1:
        rows[0].update(novelty=rng.randint(2, 4), feasibility=rng.randint(2, 4),
                       compute_alignment=rng.randint(2, 4), eligible=True)
        rows[1].update(novelty=5, feasibility=5, compute_alignment=5, eligible=False)
        rows[2].update(novelty=rng.randint(1, 3), feasibility=rng.randint(1, 3),
                       compute_alignment=rng.randint(1, 3), eligible=True)
    else:
        rows[0]['eligible'] = True
    rng.shuffle(rows)
    return {'scores': rows}


def planted_children(parent_bytes):
    """Sources only: ten semantic faults and three preservation candidates.

    Good means intended semantics, never measured qualification or speed. All
    children remain single-file patches of the actual pinned production parent.
    """
    parent = parent_bytes.decode('utf-8')
    faults = {
        'omit_compute': ("'total': sum(dimensions)", "'total': sum(dimensions[:2])"),
        'descending_ties': ("(-row['total'], row['idea_id'])", "(-row['total'], tuple(-ord(c) for c in row['idea_id']))"),
        'ineligible': ("if score['eligible']:", "if True:"),
        'ascending_total': ("(-row['total'], row['idea_id'])", "(row['total'], row['idea_id'])"),
        'selected_last': ("'selected_idea_id': eligible[0]['idea_id']", "'selected_idea_id': eligible[-1]['idea_id']"),
        'rank_zero': ("rank=index + 1", "rank=index"),
        'shift_total': ("'total': sum(dimensions)", "'total': sum(dimensions) + 1"),
        'truncate': ("enumerate(eligible)", "enumerate(eligible[:1])"),
        'omit_last': ("enumerate(eligible)", "enumerate(eligible[:-1])"),
        'wrong_selected': ("'selected_idea_id': eligible[0]['idea_id']", "'selected_idea_id': ''"),
    }
    sources = []
    for name, (before, after) in faults.items():
        if parent.count(before) != 1:
            raise ValueError('Pinned parent needs an independently reviewed calibration adapter')
        sources.append({'id': name, 'kind': 'bad', 'body': parent.replace(before, after).encode()})
    # These preserve validation including exact type/int bounds and no mutation.
    fast = parent.replace("dimensions = [score[name] for name in ('novelty', 'feasibility', 'compute_alignment')]",
                          "dimensions = (score['novelty'], score['feasibility'], score['compute_alignment'])")
    direct = fast.replace("'total': sum(dimensions)", "'total': dimensions[0] + dimensions[1] + dimensions[2]")
    for name, source in [('tuple_dimensions', fast), ('direct_total', direct),
                         ('explicit_output', direct.replace("dict(row, rank=index + 1)", "{'idea_id': row['idea_id'], 'total': row['total'], 'rank': index + 1}"))]:
        if source == parent:
            raise ValueError('Preservation child must differ from parent')
        sources.append({'id': name, 'kind': 'good', 'body': source.encode()})
    if len({row['body'] for row in sources}) != 13:
        raise ValueError('Calibration controls must have distinct exact bytes')
    return sources


def prepare_ranking(store, *, parent_ref, parent_declaration_ref, declaration,
                    author, origin_ref, generator_ref, prior_preparation_refs=(),
                    populations=None, max_rows=3, seed=None):
    return prepare_helper(store, target_kind='ranking-v1', parent_ref=parent_ref,
        parent_declaration_ref=parent_declaration_ref, declaration=declaration, author=author,
        origin_ref=origin_ref, generator_ref=generator_ref, prior_preparation_refs=prior_preparation_refs,
        populations=populations, max_rows=max_rows, seed=seed)


def prepare_helper(store, *, target_kind, parent_ref, parent_declaration_ref, declaration,
                   author, origin_ref, generator_ref, prior_preparation_refs=(),
                   populations=None, max_rows=None, seed=None):
    """Generate only inside custody; return one opaque private preparation Ref.

    Caller must retain every prior registration, including retired/disclosed
    suites. Independent review must reconcile that inventory before freezing.
    """
    require_custodian_store(store)
    adapter = _preparation_adapter(target_kind)
    if max_rows is None: max_rows = adapter.max_rows
    for pin in (parent_ref, parent_declaration_ref, origin_ref, generator_ref):
        ref(pin); store.read(pin)
    if store.read(generator_ref) != Path(__file__).read_bytes():
        raise ValueError('Exact installed generator source pin required')
    if not isinstance(author, str) or not author.strip():
        raise ValueError('Seeded authorship is required')
    if store.get(parent_declaration_ref) != declaration:
        raise ValueError('Exact parent declaration differs')
    paths = [row['path'] for row in declaration['identity']['body'] if row['sha256'] == parent_ref['sha256']]
    permitted = [value[6:] for value in declaration.get('evolution', {}).get('may_change', []) if value.startswith('files:')]
    if (len(paths) != 1 or '/' in paths[0]
            or declaration.get('evolution', {}).get('rsi') != 'propose'
            or not any(fnmatch.fnmatchcase(paths[0], pattern) for pattern in permitted)):
        raise ValueError('Exactly one declared authorized helper component required')
    if target_kind == 'ranking-v1' and (not paths[0].startswith('ranking_')
            or declaration['identity'].get('name') != 'research.screening'):
        raise ValueError('Exactly one declared ranking component required')
    safe_path(paths[0])
    children = adapter.children(store.read(parent_ref))
    populations = dict(populations or dict(development=12, hidden_loop=20, hidden_final=20, platform=12))
    if (set(populations) != set(PARTITIONS) or any(type(n) is not int or not 1 <= n <= 10000 for n in populations.values())
            or any(populations[name] < 20 for name in ('hidden_loop', 'hidden_final'))
            or type(max_rows) is not int or max_rows != adapter.max_rows):
        raise ValueError('Invalid frozen partition population')
    if seed is None: seed = secrets.token_hex(32)
    if not isinstance(seed, str) or not 16 <= len(seed) <= 256:
        raise ValueError('Private reproducible seed required')
    prior = []
    forbidden = set()
    for pin in prior_preparation_refs:
        value = store.get(pin)
        if preparation_kind(value) != target_kind:
            raise ValueError('Historical preparation helper kind differs')
        prior.append(pin)
        forbidden.update(row['semantic_sha256'] for row in value['provenance'])
    partitions = {}; provenance = []; current = set()
    for split in PARTITIONS:
        rows = []
        for index in range(populations[split]):
            # Per-unit seeds do not establish statistical independence.
            rng = random.Random(_digest([seed, split, index]))
            for attempt in range(100):
                count = max_rows if index % 3 != 2 else rng.randint(1, max_rows)
                inputs = adapter.case(rng, count, index % 3)
                adapter.helper.validate_visible_inputs(inputs)
                fingerprints = adapter.fingerprints(inputs)
                if fingerprints['semantic_sha256'] not in forbidden | current: break
            else: raise ValueError('Frozen generation cannot avoid prior overlap')
            current.add(fingerprints['semantic_sha256'])
            input_ref = store.put(inputs); expected_ref = store.put(adapter.expected(inputs))
            case_id = 'case:' + fingerprints['input_sha256']
            rows.append(dict(id=case_id, input_ref=input_ref, expected_ref=expected_ref))
            provenance.append(dict(id=case_id, partition=split, **fingerprints,
                                   expected_sha256=expected_ref['sha256'], generator_unit=index))
        partitions[split] = rows
    controls = [{key: value for key, value in row.items() if key != 'body'} | {'body_ref': store.put_bytes(row['body'])}
                for row in children]
    value = {'schema': 'ai4r-rsi-ranking-preparation:1' if target_kind == 'ranking-v1' else 'ai4r-rsi-helper-preparation:2', 'parent_ref': parent_ref,
             'parent_declaration_ref': parent_declaration_ref, 'mutable_path': paths[0],
             'author': author, 'origin_kind': 'seeded', 'origin_ref': origin_ref, 'generator_ref': generator_ref,
             'private_seed': seed, 'max_rows': max_rows, 'partitions': partitions, 'provenance': provenance,
             'prior_preparation_refs': prior, 'children': controls, 'status': 'PENDING_REVIEW_AND_CALIBRATION',
             'fixture_identity': ('ranking-loop:' if target_kind == 'ranking-v1' else target_kind + '-loop:') + _digest(sorted(row['semantic_sha256'] for row in provenance if row['partition'] == 'hidden_loop')),
             'split_ids': {name: 'split:' + _digest(sorted(row['input_ref']['sha256'] for row in rows)) for name, rows in partitions.items()}}
    from ..session_policy import validate_private
    if target_kind != 'ranking-v1': value['target_kind'] = target_kind
    validate_private(PREPARATION_SCHEMA if target_kind == 'ranking-v1' else HELPER_PREPARATION_SCHEMA, value)
    return store.put(value)


def _read_preparation(store, pin):
    """Reconcile original fixture bytes rather than trust a manifest assertion."""
    from ..session_policy import validate_private
    prep = store.get(pin)
    kind = preparation_kind(prep)
    adapter = _preparation_adapter(kind)
    for name in ('parent_ref', 'parent_declaration_ref', 'origin_ref', 'generator_ref'):
        store.read(prep[name])
    provenance = []
    seen = set()
    for split in PARTITIONS:
        for index, row in enumerate(prep['partitions'][split]):
            value = store.get(row['input_ref'])
            adapter.helper.validate_visible_inputs(value)
            fingerprints = adapter.fingerprints(value)
            if (row['input_ref']['sha256'] != fingerprints['input_sha256'] or row['id'] != 'case:' + fingerprints['input_sha256']
                    or fingerprints['semantic_sha256'] in seen or store.get(row['expected_ref']) != adapter.expected(value)):
                raise ValueError('Prepared exact bytes, expected semantics or overlap changed')
            seen.add(fingerprints['semantic_sha256'])
            provenance.append(dict(id=row['id'], partition=split, **fingerprints,
                                   expected_sha256=row['expected_ref']['sha256'], generator_unit=index))
    if provenance != prep['provenance']:
        raise ValueError('Prepared provenance does not reconcile with original bytes')
    for prior_ref in prep['prior_preparation_refs']:
        prior = store.get(prior_ref)
        if preparation_kind(prior) != kind: raise ValueError('Historical helper kind differs')
        if seen & {row['semantic_sha256'] for row in prior['provenance']}:
            raise ValueError('Prepared fixture overlaps historical lineage')
    children = adapter.children(store.read(prep['parent_ref']))
    if [(row['id'], row['kind'], row['body']) for row in children] != [
            (row['id'], row['kind'], store.read(row['body_ref'])) for row in prep['children']]:
        raise ValueError('Prepared planted-child sources differ')
    split_ids = {name: 'split:' + _digest(sorted(row['input_ref']['sha256'] for row in rows))
                 for name, rows in prep['partitions'].items()}
    identity = ('ranking-loop:' if kind == 'ranking-v1' else kind + '-loop:') + _digest(sorted(row['semantic_sha256'] for row in provenance if row['partition'] == 'hidden_loop'))
    if split_ids != prep['split_ids'] or identity != prep['fixture_identity']:
        raise ValueError('Prepared fixture/split lineage identity differs')
    return prep


def calibration_contexts(target, manifest):
    """Version2 contexts are acyclic; version1 signatures retain old meaning."""
    return {'target_context_sha256': _digest({k: v for k, v in target.items() if k != 'calibration_ref'}),
            'fixture_context_sha256': _digest({k: v for k, v in manifest.items() if k not in {'calibration_ref', 'target_ref'}})}


def calibration_inventory(manifest, repeats):
    """Protected complete raw-capture inventory; no effect or readiness claim."""
    if type(repeats) is not int or repeats not in (1, 3):
        raise ValueError('Frozen one/three repeat plan required')
    final = len(manifest['partitions']['hidden_final']) * repeats
    mandatory = len(manifest['partitions']['platform']) * repeats
    if final < 20 * repeats or mandatory == 0:
        raise ValueError('Complete frozen calibration populations required')
    return {'noise_captures': 24 * final, 'bad_control_captures': mandatory,
            'good_control_captures': mandatory + 26 * final,
            'total_captures': 24 * final + 10 * mandatory + 3 * (mandatory + 26 * final)}


def development_export(store, preparation_ref, *, approved_review_ref):
    """Explicitly reviewed development only; no hidden hashes, counts or IDs."""
    require_custodian_store(store)
    prep = _read_preparation(store, preparation_ref); review = store.get(approved_review_ref)
    from ..session_policy import validate_private
    validate_private(REVIEW_SCHEMA, review)
    if (review.get('preparation_ref') != preparation_ref or review.get('development_disclosure_approved') is not True
            or review.get('reviewer') == prep['author'] or not review.get('reviewer')):
        raise ValueError('Independent development disclosure review required')
    return {'schema': 'ai4r-rsi-visible-ranking-cases:1', 'parent_ref': prep['parent_ref'],
            'cases': [{'id': row['id'], 'inputs': store.get(row['input_ref']),
                       'expected': store.get(row['expected_ref'])} for row in prep['partitions']['development']]}


def draft_target(store, preparation_ref, template, *, review_ref, validate):
    """Build private pre-calibration objects; never an operational authority."""
    require_custodian_store(store)
    prep = _read_preparation(store, preparation_ref); review = store.get(review_ref)
    from ..session_policy import validate_private
    validate_private(REVIEW_SCHEMA, review)
    if (review.get('preparation_ref') != preparation_ref or review.get('reviewer') == prep['author']
            or not review.get('reviewer') or review.get('provenance_approved') is not True
            or review.get('overlap_inventory_complete') is not True or type(review.get('independent')) is not bool
            or not review.get('evidence_refs')):
        raise ValueError('Independent provenance/overlap review required')
    for pin in review['evidence_refs']: store.read(pin)
    target = copy.deepcopy(template)
    target.update(parent_ref=prep['parent_ref'], parent_declaration_ref=prep['parent_declaration_ref'],
                  mutable_paths=[prep['mutable_path']], splits=prep['split_ids'], calibration_ref=preparation_ref)
    if (target['scoring'].get('warmup_batches') != 5 or target['scoring'].get('paired_rounds') != 7
            or target['scoring'].get('min_relative_gain', 0) < .1 or target['scoring'].get('noise_multiplier', 0) < 3
            or type(target['scoring'].get('batch_iterations')) is not int or target['scoring']['batch_iterations'] <= 0):
        raise ValueError('Frozen protected timing policy required')
    freeze_profile(target, store.get(prep['parent_declaration_ref']), validate)
    manifest = {'schema': 'ai4r-rsi-fixtures:1', 'fixture_identity': prep['fixture_identity'],
                'target_ref': preparation_ref, 'partitions': prep['partitions'], 'independent': review['independent'],
                'independence_evidence_ref': review_ref, 'calibration_ref': preparation_ref}
    return target, manifest


def freeze_prepared_target(store, *, preparation_ref, template, review_ref, calibration_ref,
                           public_key, key_id, validate):
    """Resolve real signed calibration2; return private target and manifest refs."""
    target, manifest = draft_target(store, preparation_ref, template, review_ref=review_ref, validate=validate)
    calibration = store.get(calibration_ref)
    verify_calibration2(calibration, target=target, manifest=manifest, store=store,
                        public_key=public_key, key_id=key_id)
    target['calibration_ref'] = calibration_ref
    freeze_profile(target, store.get(target['parent_declaration_ref']), validate)
    target_ref = store.put(target)
    manifest.update(target_ref=target_ref, calibration_ref=calibration_ref)
    return {'target_ref': target_ref, 'fixture_manifest_ref': store.put(manifest)}


def verify_calibration2(calibration, *, target, manifest, store, public_key, key_id):
    """Recompute controls/noise from actual protected receipt captures.

    A trusted custodian signature remains essential. Source-only controls or a
    signed assertion without the original runtime captures cannot qualify.
    This verifies evidence; it does not run workers, spend queries or sign.
    """
    from ..session_policy import validate_private
    from ..signing import verify
    from ..statistics import qualify
    validate_private(CALIBRATION_SCHEMA, calibration)
    verify(calibration, public_key, key_id)
    prep = _read_preparation(store, calibration['preparation_ref'])
    review = store.get(calibration['review_ref'])
    validate_private(REVIEW_SCHEMA, review)
    if (any(calibration[name] != value for name, value in calibration_contexts(target, manifest).items())
            or review.get('preparation_ref') != calibration['preparation_ref']
            or manifest['independence_evidence_ref'] != calibration['review_ref']
            or review.get('reviewer') == prep['author'] or not review.get('reviewer')
            or review.get('provenance_approved') is not True or review.get('overlap_inventory_complete') is not True
            or review.get('independent') is not True or not manifest['independent']
            or not calibration['measurable_headroom']):
        raise ValueError('Independent frozen calibration context unavailable')
    for pin in calibration['evidence_refs']: store.read(pin)
    if (target['parent_ref'] != prep['parent_ref'] or manifest['partitions'] != prep['partitions']
            or target['splits'] != prep['split_ids']):
        raise ValueError('Prepared frozen calibration populations differ')
    repeats = calibration['pass_count_repeats']
    inventory = calibration_inventory(manifest, repeats)
    if len(calibration['noise_capture_refs']) != inventory['noise_captures']:
        raise ValueError('Calibration baseline runtime capture inventory differs')
    seen_invocations = set()
    worker_profiles = {}

    def consume(pins, candidate, split, *, timing=False):
        from ..worker import worker_program, timing_program, validate_profile
        count = len(manifest['partitions'][split]) * repeats
        if len(pins) != count: raise ValueError('Complete original runtime capture batch required')
        values = []; elapsed = 0
        for index, row in enumerate(manifest['partitions'][split]):
            scores = []
            for repeat in range(repeats):
                capture = store.get(pins[index * repeats + repeat])
                fields = {'schema', 'session_ref', 'candidate_ref', 'fixture_id', 'phase', 'receipt', 'timing',
                          'batch_iterations', 'program_sha256', 'worker_profile_ref', 'input_ref', 'reservation_ref', 'repeat_index'}
                iterations = target['scoring']['batch_iterations'] if timing else 1
                profile = validate_profile(store.get(capture['worker_profile_ref']))
                policy=profile.get('process_policy')
                if profile['target_kind'] != preparation_kind(prep):
                    raise ValueError('Calibration worker helper kind differs from original preparation')
                helper = _preparation_adapter(profile['target_kind']).helper
                helper.validate_visible_inputs(store.get(row['input_ref']))
                program = timing_program(iterations,profile['target_kind'],policy) if timing else worker_program(profile['target_kind'],policy)
                if (set(capture) != fields or capture.get('schema') != 'ai4r-rsi-fixture-capture:2'
                        or capture.get('candidate_ref') != candidate or capture.get('timing') is not timing
                        or type(capture.get('batch_iterations')) is not int or capture['batch_iterations'] != iterations
                        or capture.get('program_sha256') != hashlib.sha256(program).hexdigest()
                        or capture.get('input_ref') != row['input_ref'] or type(capture.get('repeat_index')) is not int
                        or capture['repeat_index'] != repeat or capture.get('phase') != split or capture.get('fixture_id') != row['id']):
                    raise ValueError('Calibration capture differs from scheduled fixture')
                session = store.get(capture['session_ref'])
                session_target = store.get(session['target_profile_ref'])
                if (session.get('pass_count_repeats') != repeats
                        or calibration_contexts(session_target, manifest)['target_context_sha256'] != calibration['target_context_sha256']):
                    raise ValueError('Calibration execution context differs')
                worker_profiles[encoded(capture['worker_profile_ref'])] = capture['worker_profile_ref']
                reservation = store.get(capture['reservation_ref'])
                if (profile['session_ref'] != capture['session_ref'] or profile['target_ref'] != session['target_profile_ref']
                        or profile['parent_ref'] != target['parent_ref'] or len(worker_profiles) != 1
                        or profile['memory_mb'] > target['limits']['memory_mb'] or profile['timeout_s'] > target['limits']['time_s']
                        or any(reservation.get(name) != capture[name] for name in ('session_ref', 'candidate_ref', 'phase', 'fixture_id'))
                        or (timing and not str(reservation.get('operation', '')).startswith('timing:'))):
                    raise ValueError('Calibration actual worker/reservation binding differs')
                receipt = capture['receipt']
                identity = receipt.get('identity', {})
                invocation = receipt.get('invocation_id')
                duration = receipt.get('wall_time_s')
                if (not isinstance(invocation, str) or not invocation or invocation in seen_invocations
                        or receipt.get('observed_runtime') is not True or identity.get('executor_uid') != 12003
                        or identity.get('executor_gid') != 12003 or receipt.get('contract_ref') != profile['contract_ref']
                        or receipt.get('timeout_s') != profile['timeout_s']
                        or receipt.get('termination_reason') != 'completed' or receipt.get('exit_code') != 0
                        or type(duration) not in (int, float) or not math.isfinite(duration) or duration <= 0):
                    raise ValueError('Actual unique bounded worker receipt required')
                seen_invocations.add(invocation)
                proof = store.get(receipt['observed_limits']['isolation_probe_ref'])
                if proof.get('ready') is not True: raise ValueError('Actual worker isolation observation unavailable')
                store.read(receipt['stderr_ref'])
                scores.append(int(store.get(receipt['stdout_ref']) == store.get(row['expected_ref'])))
                elapsed += duration
            values.append(scores)
        return values, elapsed

    def paired_timing(pins, candidate, expected_parent, expected_child):
        size = len(manifest['partitions']['hidden_final']) * repeats
        if len(pins) != 24 * size: raise ValueError('Five warmups and seven paired runtime rounds required')
        times = {'parent': [], 'child': []}; offset = 0
        for round_index in range(12):
            order = ('parent', 'child') if round_index % 2 == 0 else ('child', 'parent')
            for name in order:
                values, elapsed = consume(pins[offset:offset + size], target['parent_ref'] if name == 'parent' else candidate, 'hidden_final', timing=True)
                offset += size
                if values != (expected_parent if name == 'parent' else expected_child):
                    raise ValueError('Calibration timing changed fixed-quality repeat outcomes')
                if round_index >= 5: times[name].append(elapsed)
        return times

    # Conservative parent/parent noise floor, frozen before controls qualify.
    n = len(manifest['partitions']['hidden_final'])
    expected = [[1] * repeats for _ in range(n)]
    noise_times = paired_timing(calibration['noise_capture_refs'], target['parent_ref'], expected, expected)
    observed_noise = max(abs(a - b) / a for a, b in zip(noise_times['parent'], noise_times['child']))
    declared_noise = target['scoring']['calibrated_relative_noise']
    if type(declared_noise) not in (int, float) or not math.isfinite(declared_noise) or declared_noise < observed_noise:
        raise ValueError('Frozen noise floor understates actual baseline calibration')
    controls = {row['body_ref']['sha256']: row for row in prep['children']}
    rejected = qualified = 0; visited = set()
    for pin in calibration['control_refs']:
        control = store.get(pin)
        if (set(control) != {'schema', 'preparation_ref', 'candidate_ref', 'mandatory_capture_refs', 'final_capture_refs', 'timing_capture_refs'}
                or control['schema'] != 'ai4r-rsi-calibration-control:1' or control['preparation_ref'] != calibration['preparation_ref']):
            raise ValueError('Unknown planted runtime calibration control')
        candidate = control['candidate_ref']; row = controls.get(candidate['sha256'])
        if row is None or candidate != row['body_ref'] or candidate['sha256'] in visited:
            raise ValueError('Calibration does not cover exact distinct planted children')
        visited.add(candidate['sha256'])
        mandatory, _ = consume(control['mandatory_capture_refs'], candidate, 'platform')
        passed = all(all(values) for values in mandatory)
        if row['kind'] == 'bad':
            if passed or control['final_capture_refs'] or control['timing_capture_refs']:
                raise ValueError('Planted bad child was not rejected before hidden evaluation')
            rejected += 1
            continue
        if not passed: raise ValueError('Preservation child failed actual mandatory checks')
        size = n * repeats
        final = control['final_capture_refs']
        if len(final) != 2 * size: raise ValueError('Complete paired final score captures required')
        parent_scores, _ = consume(final[:size], target['parent_ref'], 'hidden_final')
        child_scores, _ = consume(final[size:], candidate, 'hidden_final')
        times = paired_timing(control['timing_capture_refs'], candidate, parent_scores, child_scores)
        result = qualify(parent_scores, child_scores, repeats=repeats, independent=True,
                         parent_times=times['parent'], child_times=times['child'], warmups=5,
                         calibrated_noise=declared_noise, min_timing_gain=target['scoring']['min_relative_gain'],
                         noise_multiplier=target['scoring']['noise_multiplier'])
        if result['outcome'] != 'QUALIFIED': raise ValueError('Actual preservation-child timing headroom unavailable')
        qualified += 1
    if (len(visited) != 13 or rejected != calibration['known_bad_rejected'] or qualified != calibration['known_good_qualified']
            or rejected < 10 or qualified < 3):
        raise ValueError('Actual planted-child calibration population incomplete')
    if len(seen_invocations) != inventory['total_captures']:
        raise ValueError('Calibration unique runtime invocation inventory differs')
    return {'known_bad_rejected': rejected, 'known_good_qualified': qualified,
            'measurable_headroom': True, 'observed_relative_noise': observed_noise,
            'worker_profile_ref': next(iter(worker_profiles.values()))}
