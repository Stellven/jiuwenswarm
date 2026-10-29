"""Immutable decision validity; actual provider ownership stays in the bridge."""
from datetime import datetime, timezone


def decision_unexpired(decision, *, now=None, call_started=False):
    if call_started:
        return True
    now = now or datetime.now(timezone.utc)
    return now < datetime.strptime(decision["valid_until"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

