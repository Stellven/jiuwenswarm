import pytest

from jiuwenswarm.research_router.claims import ClaimStore, ClaimConflict


def test_claim_duplicate_changed_user_and_restart_no_replay(tmp_path):
    path = tmp_path / "claims.sqlite"
    s = ClaimStore(path); assert s.claim("e", "alice", {"x": 1})[0] == "claimed"
    assert s.claim("e", "alice", {"x": 1})[0] == "in_progress"
    with pytest.raises(ClaimConflict): s.claim("e", "alice", {"x": 2})
    with pytest.raises(ClaimConflict): s.claim("e", "bob", {"x": 1})
    s.close(); s = ClaimStore(path)
    assert s.claim("e", "alice", {"x": 1})[0] == "outcome_unknown"
    s.close()


def test_ready_expiry_does_not_expire_started_and_alternate_once(tmp_path):
    clock = [100.0]; s = ClaimStore(tmp_path / "claims.sqlite", clock=lambda: clock[0])
    s.claim("e", "alice", {}); s.ready("e", {"id": "decision"})
    s.alternate("e", "b", {"a", "b"});
    with pytest.raises(ClaimConflict): s.alternate("e", "a", {"a", "b"})
    s.start("e"); clock[0] += 31
    assert s.lookup("e")["state"] == "started"
    with pytest.raises(ClaimConflict): s.start("e")

