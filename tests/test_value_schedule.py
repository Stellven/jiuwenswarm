import pytest
import sqlite3

from benchmarks.harbor_suite.value_schedule import Schedule


def test_explicit_time_extension_preserves_calls_original_start_and_unknowns(tmp_path):
    ledger = Schedule.create(tmp_path / 'extended.sqlite3', now=100)
    try:
        ledger.reserve('pair', 'a' * 64, {'cc': 2}, now=101)
        ledger.claim('pair', 'cc', 'pending', now=102)
        before = ledger.status()
        result = ledger.extend_time_authorized('user-approved-one-hour', 3600,
            evidence='user-approval.json', now=103)
        after = ledger.status()
        assert after['policy']['deadline'] == before['policy']['deadline'] + 3600
        assert after['policy']['started'] == before['policy']['started']
        assert after['policy']['max_calls'] == before['policy']['max_calls'] == 256
        assert after['calls_charged'] == before['calls_charged'] == 1
        assert after['attempts'] == before['attempts'] and after['pairs'] == before['pairs']
        assert result['max_calls_unchanged'] == 256
        with pytest.raises(sqlite3.IntegrityError):
            ledger.extend_time_authorized('user-approved-one-hour', 3600, evidence='same.json', now=104)
        assert ledger.status()['policy'] == after['policy']
        with pytest.raises(ValueError):
            ledger.extend_time_authorized('oversized', 3601, evidence='not-authorized.json')
    finally:
        ledger.close()


def test_luna_pair_requires_same_requested_and_effective_model_for_both_arms(tmp_path):
    ledger = Schedule.create(tmp_path / 'same-ledger.sqlite3', now=100)
    try:
        policy = ledger.status()['policy']
        ledger.reserve('luna-pair', 'a' * 64, {'native-skills': 1, 'cc': 1},
                       requested_model='gpt-6-luna', now=101)
        assert ledger.status()['pairs'][0]['requested_model'] == 'gpt-6-luna'
        with pytest.raises(ValueError, match='model/effort mismatch'):
            ledger.claim('luna-pair', 'native-skills', 'wrong-sol-request', now=102)
        assert ledger.status()['calls_charged'] == 0
        ledger.claim('luna-pair', 'native-skills', 'luna-native', model='gpt-6-luna', now=103)
        with pytest.raises(ValueError, match='verified model and effort'):
            ledger.finish('luna-native', 'completed', evidence='original.json',
                          effective_model='gpt-6.1-sol', effective_effort='medium')
        ledger.finish('luna-native', 'completed', evidence='original.json',
                      effective_model='gpt-6-luna', effective_effort='medium')
        with pytest.raises(ValueError, match='model/effort mismatch'):
            ledger.claim('luna-pair', 'cc', 'wrong-cc-model', model='gpt-6.1-sol', now=104)
        ledger.claim('luna-pair', 'cc', 'luna-cc', model='gpt-6-luna', now=105)
        ledger.finish('luna-cc', 'completed', evidence='cc-original.json',
                      effective_model='gpt-6-luna', effective_effort='medium')
        status = ledger.status()
        assert status['calls_consumed'] == status['calls_charged'] == 2
        assert status['policy'] == policy
        assert all(row['effective_model'] == 'gpt-6-luna' for row in status['attempts'])
        ledger.finish_pair('luna-pair')
        ledger.reserve('legacy-default', 'b' * 64, {'cc': 1}, now=106)
        assert ledger.status()['pairs'][-1]['requested_model'] == 'gpt-6.1-sol'
    finally:
        ledger.close()


def test_luna_external_envelope_requires_observed_identity_without_releasing_charge(tmp_path):
    ledger = Schedule.create(tmp_path / 'external-model.sqlite3', now=100)
    try:
        ledger.reserve('pair', 'a' * 64, {'cc': 8}, requested_model='gpt-6-luna', now=101)
        with pytest.raises(ValueError, match='model/effort mismatch'):
            ledger.claim_envelope('pair', 'cc', 'wrong-model', 8, now=102)
        ledger.claim_envelope('pair', 'cc', 'original', 8, model='gpt-6-luna', now=103)
        for identity in ({}, {'effective_model': 'gpt-6.1-sol', 'effective_effort': 'medium'},
                         {'effective_model': 'gpt-6-luna', 'effective_effort': 'high'}):
            with pytest.raises(ValueError, match='verified pair model and effort'):
                ledger.finish_envelope('original', 'completed', actual_calls=2,
                                       evidence='original-export.json', **identity)
            assert ledger.status()['calls_charged'] == 8
            assert ledger.status()['external_envelopes'][0]['state'] == 'dispatched'
        ledger.finish_envelope('original', 'completed', actual_calls=2, evidence='original-export.json',
                               effective_model='gpt-6-luna', effective_effort='medium')
        status = ledger.status()
        assert status['calls_charged'] == status['calls_consumed'] == 2
        assert status['calls_remaining'] == 254
        assert status['external_envelopes'][0]['effective_model'] == 'gpt-6-luna'
    finally:
        ledger.close()


def test_existing_ledger_additive_migration_preserves_policy_pending_effect_and_charges(tmp_path):
    path = tmp_path / 'original-ledger.sqlite3'
    with sqlite3.connect(path) as db:
        db.executescript('''
            CREATE TABLE policy(max_calls INTEGER, deadline REAL, started REAL, model TEXT, effort TEXT);
            INSERT INTO policy VALUES(256,10900,100,'gpt-6.1-sol','medium');
            CREATE TABLE pairs(id TEXT PRIMARY KEY, task_sha256 TEXT, caps TEXT, state TEXT, created REAL);
            INSERT INTO pairs VALUES('original','frozen-sha','{"cc": 2}','active',101);
            CREATE TABLE attempts(id TEXT PRIMARY KEY, pair_id TEXT, arm TEXT, started REAL, state TEXT,
                                  effective_model TEXT,effective_effort TEXT,evidence TEXT);
            INSERT INTO attempts VALUES('pending-original','original','cc',102,'dispatched',NULL,NULL,NULL);
        ''')
    ledger = Schedule(path)
    try:
        status = ledger.status()
        assert status['policy'] == {'max_calls': 256, 'deadline': 10900, 'started': 100,
                                    'model': 'gpt-6.1-sol', 'effort': 'medium'}
        assert status['pairs'][0]['requested_model'] == 'gpt-6.1-sol'
        assert status['calls_consumed'] == status['calls_charged'] == 1
        assert status['calls_remaining'] == 255
        assert status['attempts'][0]['id'] == 'pending-original'
        with pytest.raises(ValueError, match='active or outcome is unknown'):
            ledger.claim('original', 'cc', 'new-must-wait', now=103)
    finally:
        ledger.close()


def test_pair_rejects_unsupported_model_without_reservation(tmp_path):
    ledger = Schedule.create(tmp_path / 'unsupported.sqlite3', now=100)
    try:
        with pytest.raises(ValueError, match='supported campaign model'):
            ledger.reserve('wrong', 'a' * 64, {'cc': 1}, requested_model='fallback-model', now=101)
        assert ledger.status()['pairs'] == []
    finally:
        ledger.close()


def test_whole_pair_reservation_and_unknown_reconciliation(tmp_path):
    ledger = Schedule.create(tmp_path / 'campaign.sqlite3', max_calls=4, now=100)
    try:
        ledger.reserve('p1', 'a' * 64, {'native-skills': 2, 'cc': 2}, now=101)
        ledger.claim('p1', 'native-skills', 'original-request', now=102)
        ledger.finish('original-request', 'unknown', evidence='original/timeout.json')
        with pytest.raises(ValueError, match='unknown'):
            ledger.claim('p1', 'cc', 'must-not-send', now=103)
        with pytest.raises(ValueError, match='reconcile'):
            ledger.finish_pair('p1')
        ledger.finish('original-request', 'completed', evidence='original/reconciled.json',
                      effective_model='gpt-6.1-sol', effective_effort='medium')
        ledger.claim('p1', 'cc', 'cc-request', now=104)
        ledger.finish('cc-request', 'failed', evidence='original/failure.json')
        ledger.finish_pair('p1')
        assert ledger.status()['calls_consumed'] == 2
        with pytest.raises(ValueError, match='whole-pair'):
            ledger.reserve('p2', 'b' * 64, {'native-skills': 2, 'cc': 1}, now=105)
        ledger.reserve('p2', 'b' * 64, {'native-skills': 1, 'cc': 1}, now=105)
    finally:
        ledger.close()


def test_deadline_model_fallback_and_duplicate_attempts(tmp_path):
    ledger = Schedule.create(tmp_path / 'campaign.sqlite3', wall_s=10, now=100)
    try:
        ledger.reserve('pair', 'c' * 64, {'cc': 1}, now=101)
        with pytest.raises(ValueError, match='fallback'):
            ledger.claim('pair', 'cc', 'x', model='other', now=102)
        ledger.claim('pair', 'cc', 'x', now=102)
        with pytest.raises(ValueError, match='verified'):
            ledger.finish('x', 'completed', evidence='x.json', effective_model='gpt-6.1-sol')
        ledger.finish('x', 'completed', evidence='x.json', effective_model='gpt-6.1-sol', effective_effort='medium')
        with pytest.raises(ValueError, match='cap'):
            ledger.claim('pair', 'cc', 'x', now=103)
        ledger.finish_pair('pair')
        with pytest.raises(ValueError, match='wall-clock'):
            ledger.reserve('late', 'd' * 64, {'cc': 1}, now=110)
        assert ledger.status()['calls_consumed'] == 1
    finally:
        ledger.close()


def test_reopen_preserves_pending_and_limits(tmp_path):
    path = tmp_path / 'campaign.sqlite3'
    ledger = Schedule.create(path, now=100)
    ledger.reserve('pending', 'e' * 64, {'native': 1, 'cc': 1}, now=101)
    ledger.close()
    resumed = Schedule(path)
    try:
        with pytest.raises(ValueError, match='active pair'):
            resumed.reserve('second', 'f' * 64, {'cc': 1}, now=102)
        resumed.finish_pair('pending', state='blocked')
        resumed.reserve('second', 'f' * 64, {'cc': 1}, now=103)
    finally:
        resumed.close()


def test_no_overwrite_or_raised_ceiling(tmp_path):
    path = tmp_path / 'campaign.sqlite3'
    with pytest.raises(ValueError):
        Schedule.create(path, max_calls=257)
    ledger = Schedule.create(path)
    ledger.close()
    with pytest.raises(FileExistsError):
        Schedule.create(path)


def test_external_run_bound_is_charged_until_terminal_export_reconciliation(tmp_path):
    path = tmp_path / 'external.sqlite3'
    ledger = Schedule.create(path, max_calls=100, now=100)
    ledger.reserve('pair', 'a' * 64, {'native': 1, 'cc': 80}, now=101)
    ledger.claim_envelope('pair', 'cc', 'submission-original', 80, now=102)
    pending = ledger.status()
    assert pending['calls_consumed'] == 0
    assert pending['calls_charged'] == 80
    assert pending['calls_remaining'] == 20
    assert pending['attempts'] == []  # Do not fabricate per-call IDs for an app run.
    ledger.close()

    resumed = Schedule(path)
    try:
        assert resumed.status()['external_envelopes'][0]['call_bound'] == 80
        resumed.finish_envelope('submission-original', 'unknown', evidence='run-export/pending.json')
        unknown = resumed.status()
        assert unknown['calls_consumed'] == 0
        assert unknown['calls_charged'] == 80
        with pytest.raises(ValueError, match='unknown'):
            resumed.claim('pair', 'native', 'native-must-wait', now=103)
        with pytest.raises(ValueError, match='unknown'):
            resumed.finish_pair('pair')

        # Caller supplies actual_calls only after validating the original
        # terminal export. Reconciliation releases unused reserved capacity.
        resumed.finish_envelope('submission-original', 'completed', actual_calls=9,
                                evidence='run-export/validated-terminal.json')
        status = resumed.status()
        assert status['calls_consumed'] == 9
        assert status['calls_charged'] == 9
        assert status['calls_remaining'] == 91
        resumed.finish_pair('pair')
        resumed.reserve('next', 'b' * 64, {'native': 1, 'cc': 90}, now=104)
    finally:
        resumed.close()


def test_external_bound_overrun_and_arm_cap_fail_closed(tmp_path):
    ledger = Schedule.create(tmp_path / 'external-overrun.sqlite3', max_calls=90, now=100)
    try:
        ledger.reserve('pair', 'c' * 64, {'cc': 8}, now=101)
        with pytest.raises(ValueError, match='reserved arm cap'):
            ledger.claim_envelope('pair', 'cc', 'too-large', 9, now=102)
        with pytest.raises(ValueError, match='1..80'):
            ledger.claim_envelope('pair', 'cc', 'above-policy-ceiling', 81, now=102)

        ledger.claim_envelope('pair', 'cc', 'original', 8, now=103)
        with pytest.raises(ValueError, match='exceeded its pre-dispatch call bound'):
            ledger.finish_envelope('original', 'completed', actual_calls=9,
                                   evidence='run-export/overrun.json')
        status = ledger.status()
        assert status['external_envelopes'][0]['state'] == 'dispatched'
        assert status['calls_charged'] == 8
        assert status['calls_remaining'] == 82
        with pytest.raises(ValueError, match='active or outcome is unknown'):
            ledger.claim('pair', 'cc', 'second-writer', now=104)
    finally:
        ledger.close()


def test_external_envelope_and_model_attempt_are_mutually_exclusive(tmp_path):
    ledger = Schedule.create(tmp_path / 'single-writer.sqlite3', max_calls=20, now=100)
    try:
        ledger.reserve('pair', 'd' * 64, {'native': 1, 'cc': 8}, now=101)
        ledger.claim('pair', 'native', 'native-call', now=102)
        with pytest.raises(ValueError, match='another request is active'):
            ledger.claim_envelope('pair', 'cc', 'external-submission', 8, now=103)
        ledger.finish('native-call', 'failed', evidence='native/original-receipt.json')
        ledger.claim_envelope('pair', 'cc', 'external-submission', 8, now=104)
        with pytest.raises(ValueError, match='another request is active'):
            ledger.claim('pair', 'native', 'native-call-2', now=105)
    finally:
        ledger.close()
