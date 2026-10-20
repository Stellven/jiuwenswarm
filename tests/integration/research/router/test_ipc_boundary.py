"""Real separate selection process and core IPC client, with no model effect."""
import asyncio
import json
import multiprocessing
import os
from pathlib import Path
import sqlite3
import time

import pytest

from jiuwenswarm.research.router_client import RouterPort


def _real_router(path, audit, fixture, environment_capture):
    # This test launches only the selector, with the same credential-free
    # environment rule as the installed optional-process launcher.
    for key in list(os.environ):
        if key.endswith("_API_KEY") or key.startswith(("AI4R_", "JIUWENSWARM_", "CODEX_")):
            os.environ.pop(key)
    Path(environment_capture).write_text(json.dumps(sorted(os.environ)), encoding="utf-8")
    from jiuwenswarm.research_router.contracts import ContractData
    from jiuwenswarm.research_router.engine import DecisionEngine
    from jiuwenswarm.research_router.request_validation import ProtectedData
    from jiuwenswarm.research_router.service import RouterService
    absent = {"id": "not-installed", "sha256": "a" * 64}
    engine = DecisionEngine(data=ProtectedData([fixture]), validate=ContractData().validate,
                            audit_root=audit, catalog_ref=absent, profile_refs=[],
                            development_profiles_ref=absent, adapter_revision="boundary-test:1")
    asyncio.run(RouterService(engine, [os.getuid()]).serve(path))


def await_socket(process, path):
    until = time.monotonic() + 10
    while not path.is_socket() and time.monotonic() < until:
        assert process.is_alive(), "Selection process exited before readiness"
        time.sleep(.01)
    assert path.is_socket(), "BLOCKED: actual selection socket did not become ready"


def test_real_selector_ipc_no_route_is_attributed_and_fixed_verifier_bypasses(tmp_path, monkeypatch):
    assert hasattr(os, "getuid"), "BLOCKED: Linux peer credentials required"
    fixture = Path(__file__).resolve().parents[3] / "fixtures/research/router/protected-capture"
    request = json.loads((fixture / "request.json").read_bytes())
    path, audit = tmp_path / "router.sock", tmp_path / "audit"
    monkeypatch.setenv("BOUNDARY_API_KEY", "sentinel-not-a-credential")
    child = multiprocessing.Process(target=_real_router,
        args=(str(path), str(audit), str(fixture), str(tmp_path / "environment.json")))
    child.start()
    try:
        await_socket(child, path)
        port = RouterPort(path, peer_uid=os.getuid())
        context = {"call_function": "worker", "router": {"enabled": True, "deadline_s": 30,
                   "profile_ref": request["model_selection_profile_ref"]},
                   "route_request": request, "approved_model_ids": []}
        choice = asyncio.run(port.select(context))
        assert choice.model_id == "codex-cli-default" and choice.decision_source == "codex_router_failed"
        assert choice.router_failure == "no_route"
        assert choice.router_halt_code == "PROFILE_UNAVAILABLE" and choice.route_decision_ref is None
        with sqlite3.connect(audit / "audit.sqlite") as db:
            before = db.execute("SELECT count(*) FROM claims").fetchone()[0]
        assert before == 1
        verifier = asyncio.run(port.select({**context, "call_function": "verifier"}))
        disabled = asyncio.run(port.select({**context, "router": {"enabled": False, "deadline_s": 30}}))
        assert verifier.decision_source == disabled.decision_source == "codex_router_disabled"
        assert verifier.route_decision_ref is disabled.route_decision_ref is None
        with sqlite3.connect(audit / "audit.sqlite") as db:
            assert db.execute("SELECT count(*) FROM claims").fetchone()[0] == before
        assert "BOUNDARY_API_KEY" not in json.loads((tmp_path / "environment.json").read_bytes())
    finally:
        child.terminate(); child.join(5)
        assert not child.is_alive()
