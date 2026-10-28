"""Schema-complete signed synthetic review vectors, never live improvement evidence."""
import copy
import hashlib
import importlib.util
import json
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).parents[3]
spec = importlib.util.spec_from_file_location('unit_cc_publisher', ROOT / 'deploy/m1/rsi_ui_publish.py')
publisher = importlib.util.module_from_spec(spec); spec.loader.exec_module(publisher)
from _ai4r_cc_ui_publish.cc_rsi_publication import ApprovedOriginals, append_session, append_progress


@pytest.fixture
def signed_review(tmp_path):
    from tests.unit_tests.research_rsi.fixture_package import make_unit_package
    fixture = make_unit_package(tmp_path)
    store = fixture['store']; package = fixture['package']
    target = store.read_record(fixture['session']['target_profile_ref'])
    parent_ref = fixture['session']['parent_declaration_ref']; body_ref = target['parent_ref']
    source = {'schema': 'ai4r-rsi-parent-source-export:1', 'status': 'NOT_ADMISSION', 'stage': 'screening',
              'parent_declaration_ref': parent_ref, 'parent_body_refs': {'ranking_parent.txt': body_ref},
              'public_original_refs': [parent_ref, body_ref]}
    source_ref = fixture['put'](source)
    class SyntheticPublic:
        def get(self, pin): return store.read_record(pin)
        def read(self, pin): return store.read_blob(pin)
    checkpoint = {'schema': 'ai4r-rsi-host-stopped-checkpoint:1', 'candidate_started': False,
                  'diagnosis_proposal_calls': 0, 'relay_socket_present': False, 'relay_session_preserved': True,
                  'unknown_reclassified': False, 'rsi_ledger': {'counts': {'completed': 22, 'outcome_unknown': 1}},
                  'observed_at': '2026-10-25T00:00:00Z'}
    raw = json.dumps(checkpoint).encode()
    base = publisher.stopped_projection(SyntheticPublic(), source_ref, raw, hashlib.sha256(raw).hexdigest(), 'synthetic-unit-stopped')
    approved = [package['session_ref'], package['session_result_ref'], fixture['session']['target_profile_ref'],
                parent_ref, body_ref, *fixture['result']['attempt_refs'], package['referee_evidence_ref'],
                package['child_declaration_ref'], fixture['attempt']['child_ref']]
    try: yield fixture, base, approved
    finally: store.close()


def append(fixture, base, approved, **kwargs):
    return append_session(base, ApprovedOriginals(fixture['store'].read_blob, approved),
        session_ref=fixture['package']['session_ref'], result_ref=fixture['package']['session_result_ref'],
        public_key=fixture['signer'].public_bytes(), key_id='unit:custodian', **kwargs)


def test_real_typed_signed_join_keeps_candidate_and_bodyless_attempt_separate(signed_review):
    fixture, base, approved = signed_review
    view = append(fixture, base, approved)
    assert len(view['snapshot']['nodes']) == 2
    node = view['snapshot']['nodes'][-1]
    assert node['hash'] == fixture['attempt']['child_ref']['sha256']
    assert node['admission_status'].startswith('unadmitted')
    assert node['admit']['allowed'] is False
    assert node['noise'] is None and node['speed'] is None
    assert 'Parent ' in node['correctness']
    assert len(view['snapshot']['runs'][-1]['activity']) == 2
    assert 'no captured capsule' in view['snapshot']['runs'][-1]['activity'][1]['summary']
    assert view['candidates'][-1]['candidate_code'] == fixture['store'].read_blob(fixture['attempt']['child_ref']).decode()
    public = json.dumps(view)
    assert 'unit:hidden_final' not in public and 'signer_key_id' not in public and 'observation_refs' not in public


def test_wrong_key_or_unapproved_body_never_publishes(signed_review):
    fixture, base, approved = signed_review
    with pytest.raises(ValueError):
        append_session(base, ApprovedOriginals(fixture['store'].read_blob, approved),
            session_ref=fixture['package']['session_ref'], result_ref=fixture['package']['session_result_ref'],
            public_key=b'x' * 32, key_id='unit:custodian')
    without_body = [pin for pin in approved if pin != fixture['attempt']['child_ref']]
    with pytest.raises(ValueError): append(fixture, base, without_body)
    assert len(base['snapshot']['nodes']) == 1


def test_human_receipt_joins_exact_admission_and_standing(signed_review):
    from jiuwenswarm.research.contracts import validate
    fixture, base, approved = signed_review
    put = fixture['put']; package = fixture['package']; pin = package['session_ref']
    admission = {'schema_version': '1.0.0', 'id': 'unit-admission', 'candidate_ref': package['child_declaration_ref'],
        'cc': fixture['result']['child'], 'parent_ref': fixture['session']['parent_declaration_ref'], 'parent_admission_ref': pin,
        'evidence_refs': [pin], 'check_pins': None, 'memory_mb': 256, 'status': 'admitted', 'standing': 'inactive', 'reasons': ['Synthetic typed fixture only']}
    validate('library-admission', admission); admission_ref = put(admission)
    standing = {'schema_version': '1.0.0', 'id': 'unit-standing', 'actor': 'unit:human', 'recorded_at': '2026-10-25T01:00:00Z',
        'cc': admission['cc'], 'admission_ref': admission_ref, 'from_standing': 'inactive', 'to_standing': 'active',
        'reason': 'Synthetic UI receipt fixture only', 'effect_scope': 'rsi_sandbox'}
    validate('activation-record', standing); standing_ref = put(standing)
    admit_receipt = put({'id': 'unit:admit', 'command': 'admit-rsi', 'actor': 'unit:human', 'recorded_at': '2026-10-25T00:30:00Z',
                         'status': 'admitted', 'admission_ref': admission_ref})
    activate_receipt = put({'id': 'unit:activate', 'command': 'standing', 'actor': 'unit:human', 'recorded_at': standing['recorded_at'],
                            'status': 'completed', 'standing_ref': standing_ref})
    view = append(fixture, base, [*approved, admission_ref, standing_ref, admit_receipt, activate_receipt],
                  operator_receipt_refs=[admit_receipt, activate_receipt])
    node = view['snapshot']['nodes'][-1]
    assert node['admission_status'] == 'admitted (inactive on admission)'
    assert node['activation_status'] == 'Last recorded: active (rsi_sandbox)'
    assert node['operator_receipts'][0]['actor'] == 'unit:human'
    assert node['activate']['allowed'] is False
    assert view['snapshot']['targets'][0]['active_hash'] is None


def unit_progress(base, **changes):
    target = base['snapshot']['targets'][0]
    return dict({'schema': 'ai4r-cc-rsi-prerequisite-progress:1', 'run_id': 'synthetic-live-run',
        'target_id': target['id'], 'parent_hash': target['parent_hash'], 'observed_at': '2026-10-25T01:00:00Z',
        'stage': 'screening_calibration', 'status': 'running', 'setup_completed': 8, 'setup_unknown': 0,
        'cumulative_setup_completed': 30, 'cumulative_setup_unknown': 1, 'diagnosis_calls': 0,
        'proposal_calls': 0, 'candidate_count': 0, 'max_candidates': 1, 'max_generation_calls': 2}, **changes)


def progress_ref(progress):
    digest = hashlib.sha256(json.dumps(progress, sort_keys=True).encode()).hexdigest()
    return {'id': 'synthetic-progress:' + digest, 'sha256': digest}


def test_search_provider_capacity_is_known_failed_without_enabling_actions(signed_review):
    _,base,_=signed_review
    progress=unit_progress(base,stage='search_calibration',status='blocked',reason_code='provider_capacity',
        setup_unknown=0,setup_failed=1,cumulative_setup_failed=2)
    value=append_progress(base,progress,progress_ref(progress))
    run=value['snapshot']['runs'][-1]
    assert run['stage']=='search_calibration' and run['status']=='blocked'
    assert 'provider refused capacity' in run['activity'][0]['summary']
    assert 'current 1, cumulative 2; these remain charged' in run['activity'][0]['summary']
    assert all(not row['run']['allowed'] for row in value['snapshot']['targets'])
    assert all(not row[action]['allowed'] for row in value['snapshot']['nodes'] for action in ('admit','activate'))
    assert value['candidates']==base['candidates']


@pytest.mark.parametrize('changes',[{'reason_code':'raw provider text'}, {'reason_code':{'raw':'private'}},
    {'reason_code':'provider_capacity'}, {'setup_failed':True,'cumulative_setup_failed':1},
    {'setup_failed':2,'cumulative_setup_failed':1}, {'setup_failed':1}])
def test_capacity_progress_rejects_raw_errors_or_invented_failed_counts(signed_review,changes):
    _,base,_=signed_review
    progress=unit_progress(base,stage='search_calibration',status='blocked',**changes)
    with pytest.raises(ValueError):append_progress(base,progress,progress_ref(progress))


def test_live_progress_uses_observed_aggregates_without_fabricating_code_or_metrics(signed_review):
    fixture, base, approved = signed_review
    progress = unit_progress(base)
    view = append_progress(base, progress, progress_ref(progress))
    run = view['snapshot']['runs'][-1]
    assert run['id'] == progress['run_id'] and run['stage'] == 'screening_calibration' and run['status'] == 'running'
    assert 'Current run setup: 8 completed, 0 unknown' in run['activity'][0]['summary']
    assert 'Cumulative setup/smoke: 30 completed, 1 unknown' in run['activity'][0]['summary']
    assert run['budget']['setup_calls'] == 30 and run['budget']['cost'] is None
    assert run['budget']['elapsed_seconds'] is None and run['budget']['diagnosis_calls'] == 0
    assert view['candidates'] == base['candidates'] and len(view['snapshot']['nodes']) == 1
    assert view['snapshot']['nodes'][0]['correctness'] is None and view['snapshot']['nodes'][0]['noise'] is None
    assert not view['snapshot']['targets'][0]['run']['allowed']
    assert all(not row['admit']['allowed'] and not row['activate']['allowed'] for row in view['snapshot']['nodes'])
    # Reapplying the same observation is idempotent; an update replaces its own
    # metadata, preserving the historical stopped run and captured parent.
    assert append_progress(view, progress, progress_ref(progress)) == view
    changed = unit_progress(base, observed_at='2026-10-25T01:01:00Z', setup_completed=9, cumulative_setup_completed=31)
    updated = append_progress(view, changed, progress_ref(changed))
    assert len(updated['snapshot']['runs']) == len(view['snapshot']['runs'])
    assert updated['snapshot']['runs'][0] == base['snapshot']['runs'][0]
    assert '9 completed' in updated['snapshot']['runs'][-1]['activity'][0]['summary']
    candidate = unit_progress(base, stage='candidate_evaluation', diagnosis_calls=1, proposal_calls=1, candidate_count=1)
    pending = append_progress(base, candidate, progress_ref(candidate))
    assert 'Observed candidates: 1 / 1' in pending['snapshot']['runs'][-1]['activity'][0]['summary']
    assert pending['candidates'] == base['candidates'] and len(pending['snapshot']['nodes']) == 1


@pytest.mark.parametrize('changes', [
    {'target_id': 'foreign-target'}, {'parent_hash': 'f' * 64}, {'setup_completed': True},
    {'setup_completed': -1}, {'setup_unknown': 1}, {'setup_unknown': 2, 'status': 'outcome_unknown'},
    {'setup_completed': 31}, {'cumulative_setup_completed': 1000001},
    {'diagnosis_calls': 1}, {'stage': 'proposal', 'diagnosis_calls': 0},
    {'stage': 'proposal', 'proposal_calls': 1, 'diagnosis_calls': 0},
    {'stage': 'candidate_evaluation', 'candidate_count': 1, 'proposal_calls': 0, 'diagnosis_calls': 1},
    {'max_candidates': 2}, {'max_generation_calls': 3}, {'observed_at': '2026-10-25T01:00:00'},
    {'stage': 'raw-private-error'}, {'status': 'native-turn-id'}, {'raw_error': 'must never reach browser'},
])
def test_progress_counts_identity_and_closed_fields_fail_closed(signed_review, changes):
    fixture, base, approved = signed_review
    progress = unit_progress(base, **changes)
    with pytest.raises(ValueError): append_progress(base, progress, progress_ref(progress))
    assert len(base['snapshot']['runs']) == 1 and len(base['snapshot']['nodes']) == 1


def test_signed_terminal_replaces_only_matching_progress_and_cannot_be_downgraded(signed_review):
    fixture, base, approved = signed_review
    progress = unit_progress(base, run_id=fixture['session']['session_id'])
    with_progress = append_progress(base, progress, progress_ref(progress))
    unrelated = unit_progress(base, run_id='synthetic-unrelated-live-run')
    with_progress = append_progress(with_progress, unrelated, progress_ref(unrelated))
    terminal = append(fixture, with_progress, approved)
    runs = terminal['snapshot']['runs']
    assert len(runs) == 3
    same = [row for row in runs if row['id'] == fixture['session']['session_id']]
    assert len(same) == 1 and same[0]['stage'] == 'terminal'
    assert same[0]['status'] == fixture['result']['outcome']
    for run in with_progress['snapshot']['runs']:
        if run['id'] != fixture['session']['session_id']:
            assert run in runs
    assert len(terminal['snapshot']['nodes']) == 2
    assert terminal['snapshot']['availability'] == 'ROOT_OBSERVED_PROGRESS'
    with pytest.raises(ValueError): append_progress(terminal, progress, progress_ref(progress))


@pytest.mark.parametrize('fault', ['none600', 'none640', 'wrong_sha', 'mode', 'owner', 'links', 'symlink', 'duplicate'])
def test_progress_reader_enforces_pin_and_root_file_contract_without_runtime_access(signed_review, tmp_path, monkeypatch, fault):
    # Isolated bytes plus synthetic OS metadata exercise the installed reader's
    # checks on Windows; no real Root identity, protected path or ledger is used.
    fixture, base, approved = signed_review
    raw = json.dumps(unit_progress(base)).encode()
    if fault == 'duplicate': raw = raw[:-1] + b', "setup_completed": 8}'
    path = tmp_path / 'synthetic-progress.json'; path.write_bytes(raw)
    mode = 0o600 if fault == 'none600' else 0o660 if fault == 'mode' else 0o640
    metadata = SimpleNamespace(st_mode=stat.S_IFREG | mode, st_uid=10001 if fault == 'owner' else 0,
        st_nlink=2 if fault == 'links' else 1, st_size=len(raw))
    class ProtectedDirectory:
        def lstat(self): return SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_uid=0)
    class SyntheticRootFile:
        parents = (ProtectedDirectory(),)
        def is_absolute(self): return True
        def __fspath__(self): return str(path)
        def lstat(self): return SimpleNamespace(st_mode=stat.S_IFLNK if fault == 'symlink' else metadata.st_mode)
    digest = 'f' * 64 if fault == 'wrong_sha' else hashlib.sha256(raw).hexdigest()
    result = None
    with monkeypatch.context() as patch:
        patch.setattr(publisher.os, 'name', 'posix')
        patch.setattr(publisher.os, 'geteuid', lambda: 0, raising=False)
        patch.setattr(publisher.os, 'O_NOFOLLOW', getattr(publisher.os, 'O_NOFOLLOW', 0), raising=False)
        patch.setattr(publisher.os, 'O_NONBLOCK', getattr(publisher.os, 'O_NONBLOCK', 0), raising=False)
        patch.setattr(publisher.os, 'fstat', lambda fd: metadata)
        if fault.startswith('none'):
            result = publisher.append_progress_grant(base, SyntheticRootFile(), digest)
        else:
            with pytest.raises(ValueError): publisher.append_progress_grant(base, SyntheticRootFile(), digest)
    if result is not None:
        assert result['snapshot']['runs'][-1]['stage'] == 'screening_calibration'
