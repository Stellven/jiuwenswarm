import pytest

from jiuwenswarm.research_router.claims import ClaimStore


def test_decision_and_event_are_durable_before_return(tmp_path):
    s = ClaimStore(tmp_path / "audit.sqlite"); s.claim("e", "a", {})
    s.ready("e", {"id": "route:a", "selected_endpoint": "a"})
    assert s.lookup("e")["decision"]["selected_endpoint"] == "a"
    assert [x["event"] for x in s.events("e")] == ["claimed", "ready"]
    s.close()

