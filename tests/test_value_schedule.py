import pytest

from benchmarks.harbor_suite.value_schedule import Schedule


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
