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
