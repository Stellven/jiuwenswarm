from concurrent.futures import ThreadPoolExecutor
import pytest

from jiuwenswarm.research.pilot_budget import PilotBudget, PilotBudgetError, prepare


def test_attempts_are_spent_on_failure_and_survive_restart(tmp_path):
    directory = tmp_path / 'budget'
    prepare(directory, 'pilot', max_calls=2, wall_s=20)
    first = PilotBudget(directory)
    assert first.claim('a', 'gpt-6-luna', now=100) == 20
    first.finish('a', 'provider_failure')
    first.close()
    second = PilotBudget(directory)
    assert second.claim('b', 'gpt-6.1-sol', now=101) == 19
    second.close()  # An interrupted/unknown attempt is never refunded.
    third = PilotBudget(directory)
    with pytest.raises(PilotBudgetError):
        third.claim('c', 'gpt-6-luna', now=102)
    assert third.inspect()['attempts'] == 2
    assert third.inspect()['outcomes'] == {'provider_failure': 1, 'unknown': 1}
    third.close()


def test_deadline_and_rollback_fail_closed_without_starting_on_status(tmp_path):
    prepare(tmp_path, 'pilot', max_calls=5, wall_s=10)
    budget = PilotBudget(tmp_path)
    assert budget.inspect()['started_at_unix'] is None
    assert budget.claim('a', 'gpt-6-luna', now=100) == 10
    for instant in (99, 110, 111):
        with pytest.raises(PilotBudgetError):
            budget.claim(str(instant), 'gpt-6-luna', now=instant)
    with pytest.raises(PilotBudgetError):
        budget.claim('fallback', None, now=101)
    assert budget.inspect()['attempts'] == 1
    budget.close()


def test_concurrent_claims_cannot_overrun_limit(tmp_path):
    prepare(tmp_path, 'pilot', max_calls=3, wall_s=10)
    def claim(index):
        budget = PilotBudget(tmp_path)
        try:
            budget.claim(str(index), 'gpt-6-luna', now=100)
            return True
        except PilotBudgetError:
            return False
        finally:
            budget.close()
    with ThreadPoolExecutor(max_workers=6) as pool:
        assert sum(pool.map(claim, range(12))) == 3


def test_policy_cannot_be_replaced_and_unsafe_custody_is_rejected(tmp_path):
    directory = tmp_path / 'budget'
    prepare(directory, 'pilot')
    with pytest.raises(FileExistsError):
        prepare(directory, 'new')
    directory.chmod(0o755)
    with pytest.raises(PilotBudgetError):
        PilotBudget(directory)
