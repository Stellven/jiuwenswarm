"""Lifecycle contract tests; interface fixtures are not live AI4R evidence."""
import asyncio
import json
from pathlib import Path
import sqlite3

import pytest

from benchmarks.harbor_pilot.bridge import (
    BridgeCancelled, Config, atomic, campaign_id, case_from_instruction,
    host_inventory, output_lock, read_json, run_trial,
)


def config(tmp_path):
    bundle = tmp_path / "bundle"
    (bundle / "cases").mkdir(parents=True)
    (bundle / "inputs").mkdir()
    for case in ("cpu", "paper"):
        atomic(bundle / "cases" / (case + ".json"), {
            "schema_version": "sequential-cases:1", "cases": [
                {"id": case, "task": "Execute the frozen technical research request.",
                 "inputs": [{"path": "public.txt", "kind": "docs"}], "repeats": 1}]})
    (bundle / "inputs" / "public.txt").write_text("public fixture")
    output = tmp_path / "output"
    output.mkdir()
    token = tmp_path / "private-token"
    token.write_text("never-export-this-token")
    return Config(bundle, output, "http://127.0.0.1:5175", token, "pinned-app-build", cancel_timeout_s=0.1)


def record(args, *, state="completed", collected="complete", request="stable-request", app="app-run"):
    folder = Path(args.campaign_dir)
    folder.mkdir(exist_ok=True)
    atomic(folder / "campaign.json", {"schema_version": "sequential-campaign:1"})
    run = folder / "runs" / "attempt-r1"
    run.mkdir(parents=True, exist_ok=True)
    atomic(run / "run_record.json", {"run_id": "attempt-r1", "request_id": request,
           "app_run_id": app, "execution_state": state, "collection_state": collected})


def test_same_trial_reconciles_without_second_run(tmp_path):
    cfg = config(tmp_path)
    calls = []
    async def execute(args):
        calls.append(args.command)
        if args.command == "run":
            record(args, state="unknown", collected="pending", app=None)
            return 3, {}
        record(args)
        return 0, {}
    first = asyncio.run(run_trial(cfg, "cpu", "trial-one", execute=execute))
    assert not first.receipt["terminal_confirmed"]
    second = asyncio.run(run_trial(cfg, "cpu", "trial-one", execute=execute))
    assert calls == ["run", "resume"]
    assert second.receipt["request_id"] == first.receipt["request_id"]
    assert second.receipt["recovered"] and second.receipt["evidence_complete"]
    assert not (cfg.output_root / ".harbor-pilot-active.json").exists()
    assert "never-export-this-token" not in (second.folder / "pilot-receipt.json").read_text()


def test_next_case_cannot_dispatch_while_delivery_unknown(tmp_path):
    cfg = config(tmp_path)
    calls = []
    async def execute(args):
        calls.append((args.command, args.campaign_id))
        record(args, state="unknown", collected="pending", app=None)
        return 3, {}
    first = asyncio.run(run_trial(cfg, "cpu", "trial-one", execute=execute))
    with pytest.raises(ValueError, match="remains unresolved"):
        asyncio.run(run_trial(cfg, "paper", "trial-two", execute=execute))
    assert [name for name, _ in calls] == ["run", "resume"]
    assert {ident for _, ident in calls} == {first.receipt["campaign_id"]}
    assert read_json(cfg.output_root / ".harbor-pilot-active.json")["campaign_id"] == first.receipt["campaign_id"]


def test_prior_terminal_run_must_finish_collection_before_next_dispatch(tmp_path):
    cfg = config(tmp_path)
    calls = []
    async def execute(args):
        calls.append(args.command)
        record(args, collected="failed")
        return 3, {}
    asyncio.run(run_trial(cfg, "cpu", "trial-one", execute=execute))
    with pytest.raises(ValueError, match="remains unresolved"):
        asyncio.run(run_trial(cfg, "paper", "trial-two", execute=execute))
    assert calls == ["run", "resume"]


def test_changed_input_bytes_cannot_resume_trial(tmp_path):
    cfg = config(tmp_path)
    calls = []
    async def execute(args):
        calls.append(args.command)
        record(args)
        return 0, {}
    asyncio.run(run_trial(cfg, "cpu", "trial-one", execute=execute))
    (cfg.bundle_root / "inputs/public.txt").write_text("changed fixture")
    with pytest.raises(ValueError, match="pins changed"):
        asyncio.run(run_trial(cfg, "cpu", "trial-one", execute=execute))
    assert calls == ["run"]


def test_preexisting_evidence_without_bridge_pins_is_not_adopted(tmp_path):
    cfg = config(tmp_path)
    folder = cfg.output_root / campaign_id("cpu", "foreign-trial")
    folder.mkdir()
    sentinel = folder / "user-owned.txt"
    sentinel.write_text("retain")
    async def execute(args):
        raise AssertionError("Foreign evidence must not reach the runner")
    with pytest.raises(ValueError, match="Refusing to adopt"):
        asyncio.run(run_trial(cfg, "cpu", "foreign-trial", execute=execute))
    assert sentinel.read_text() == "retain"
    assert not (folder / "pilot-receipt.json").exists()


def test_harbor_cancellation_cancels_observes_and_collects_app(tmp_path):
    cfg = config(tmp_path)
    calls = []
    async def scenario():
        started = asyncio.Event()
        async def execute(args):
            calls.append(args.command)
            if args.command == "run":
                record(args, state="running", collected="pending")
                started.set()
                await asyncio.Event().wait()
            elif args.command == "cancel":
                record(args, state="cancellation_pending", collected="pending")
            else:
                record(args, state="cancelled")
            return 3, {}
        task = asyncio.create_task(run_trial(cfg, "cpu", "cancelled-trial", execute=execute))
        await started.wait()
        task.cancel()
        with pytest.raises(BridgeCancelled) as caught:
            await task
        receipt = caught.value.result.receipt
        assert receipt["execution_state"] == "cancelled"
        assert receipt["evidence_complete"] and receipt["cancellation_requested"]
    asyncio.run(scenario())
    assert calls == ["run", "cancel", "resume"]
    assert not (cfg.output_root / ".harbor-pilot-active.json").exists()


def test_unconfirmed_cancellation_retains_cross_trial_lock(tmp_path):
    cfg = config(tmp_path)
    calls = []
    async def scenario():
        started = asyncio.Event()
        async def execute(args):
            calls.append(args.command)
            if args.command == "run":
                record(args, state="running", collected="pending")
                started.set()
                await asyncio.Event().wait()
            record(args, state="cancellation_pending", collected="pending")
            return 3, {}
        task = asyncio.create_task(run_trial(cfg, "cpu", "cancelled-trial", execute=execute))
        await started.wait()
        task.cancel()
        with pytest.raises(BridgeCancelled) as caught:
            await task
        assert not caught.value.result.receipt["terminal_confirmed"]
        with pytest.raises(ValueError, match="remains unresolved"):
            await run_trial(cfg, "paper", "next-trial", execute=execute)
    asyncio.run(scenario())
    assert calls.count("run") == 1
    assert (cfg.output_root / ".harbor-pilot-active.json").exists()


def test_double_cancellation_joins_containment_before_releasing_output_lock(tmp_path):
    cfg = config(tmp_path)
    calls = []
    async def scenario():
        started, containing, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
        containment_finished = False
        async def execute(args):
            nonlocal containment_finished
            calls.append(args.command)
            if args.command == "run":
                record(args, state="running", collected="pending")
                started.set()
                await asyncio.Event().wait()
            elif args.command == "cancel":
                containing.set()
                try:
                    await release.wait()
                finally:
                    containment_finished = True
                record(args, state="cancellation_pending", collected="pending")
            else:
                record(args, state="cancelled")
            return 3, {}
        task = asyncio.create_task(run_trial(cfg, "cpu", "double-cancel", execute=execute))
        await started.wait()
        task.cancel()
        await containing.wait()
        task.cancel()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert not task.done() and not containment_finished
        with pytest.raises(ValueError, match="Another Harbor pilot observer"):
            with output_lock(cfg.output_root):
                pass
        release.set()
        with pytest.raises(BridgeCancelled) as caught:
            await task
        assert containment_finished
        assert caught.value.result.receipt["evidence_complete"]
        assert caught.value.result.receipt["execution_state"] == "cancelled"
        assert not [pending for pending in asyncio.all_tasks() if pending is not asyncio.current_task()
                    and pending.get_name().startswith("ai4r-pilot-containment")]
        with output_lock(cfg.output_root):
            pass
    asyncio.run(scenario())
    assert calls == ["run", "cancel", "resume"]


def test_repeated_cancellation_keeps_deadline_and_joins_timed_out_cleanup(tmp_path):
    cfg = config(tmp_path)
    async def scenario():
        started, containing = asyncio.Event(), asyncio.Event()
        joined = False
        async def execute(args):
            nonlocal joined
            if args.command == "run":
                record(args, state="running", collected="pending")
                started.set()
                await asyncio.Event().wait()
            containing.set()
            try:
                await asyncio.Event().wait()
            finally:
                joined = True
        task = asyncio.create_task(run_trial(cfg, "cpu", "double-cancel-timeout", execute=execute))
        await started.wait()
        task.cancel()
        await containing.wait()
        task.cancel()
        with pytest.raises(BridgeCancelled) as caught:
            await asyncio.wait_for(task, timeout=2)
        assert joined
        assert caught.value.result.receipt["error_type"] == "TimeoutError"
        assert not caught.value.result.receipt["terminal_confirmed"]
        assert (cfg.output_root / ".harbor-pilot-active.json").exists()
        assert not [pending for pending in asyncio.all_tasks() if pending is not asyncio.current_task()
                    and pending.get_name().startswith("ai4r-pilot-containment")]
    asyncio.run(scenario())


def test_timeout_during_previous_attempt_reconciliation_contains_that_attempt(tmp_path):
    cfg = config(tmp_path)
    calls = []
    async def scenario():
        phase = "initial"
        waiting = asyncio.Event()
        async def execute(args):
            calls.append((args.command, args.campaign_id))
            if args.command == "run":
                record(args, state="unknown", collected="pending", app=None)
            elif args.command == "resume" and phase == "reconciling":
                waiting.set()
                await asyncio.Event().wait()
            elif args.command == "cancel":
                record(args, state="cancellation_pending", collected="pending")
            else:
                record(args, state="cancelled")
            return 3, {}
        original = await run_trial(cfg, "cpu", "previous", execute=execute)
        phase = "reconciling"
        task = asyncio.create_task(run_trial(cfg, "paper", "next", execute=execute))
        await waiting.wait()
        phase = "cancelling"
        task.cancel()
        with pytest.raises(BridgeCancelled) as caught:
            await task
        assert caught.value.result.receipt["campaign_id"] == original.receipt["campaign_id"]
        assert caught.value.result.receipt["execution_state"] == "cancelled"
        assert caught.value.result.receipt["evidence_complete"]
    asyncio.run(scenario())
    assert [name for name, _ in calls] == ["run", "resume", "cancel", "resume"]
    assert len({ident for _, ident in calls}) == 1


def test_unlaunched_terminal_requires_read_only_claim_check(tmp_path):
    cfg = config(tmp_path)
    async def execute(args):
        record(args, state="timed_out", collected="not_applicable", app=None)
        with sqlite3.connect(Path(args.campaign_dir) / "ledger.sqlite") as db:
            db.execute("CREATE TABLE attempts(id TEXT PRIMARY KEY, fingerprint TEXT)")
        return 2, {}
    result = asyncio.run(run_trial(cfg, "cpu", "pre-dispatch-timeout", execute=execute))
    assert result.receipt["terminal_confirmed"]
    assert not result.receipt["evidence_complete"]
    assert not (cfg.output_root / ".harbor-pilot-active.json").exists()


def test_exception_retains_receipt_without_disclosing_exception_message(tmp_path):
    cfg = config(tmp_path)
    async def execute(args):
        raise RuntimeError("network error with never-export-this-token")
    result = asyncio.run(run_trial(cfg, "paper", "failed-trial", execute=execute))
    assert result.receipt["error_type"] == "RuntimeError"
    assert not result.receipt["terminal_confirmed"]
    assert "never-export-this-token" not in (result.folder / "pilot-receipt.json").read_text()
    assert (cfg.output_root / ".harbor-pilot-active.json").exists()


def test_config_rejects_credential_inside_evidence_or_public_inputs(tmp_path):
    cfg = config(tmp_path)
    private = cfg.output_root / "token"
    private.write_text("secret")
    path = tmp_path / "host-config.json"
    atomic(path, {"schema": "ai4r-harbor-config:1", "bundle_root": str(cfg.bundle_root),
                 "output_root": str(cfg.output_root), "endpoint": cfg.endpoint,
                 "token_file": str(private), "expected_build": cfg.expected_build})
    with pytest.raises(ValueError, match="Credential must remain outside"):
        Config.load(path)


def test_case_marker_and_fresh_inventory_have_no_assumed_gpu(tmp_path):
    assert case_from_instruction("AI4R_HARBOR_CASE: cpu\nTask") == "cpu"
    with pytest.raises(ValueError):
        case_from_instruction("AI4R_HARBOR_CASE: cpu\nAI4R_HARBOR_CASE: paper")
    assert campaign_id("cpu", "same") == campaign_id("cpu", "same")
    assert campaign_id("cpu", "same") != campaign_id("paper", "same")
    inventory = host_inventory(tmp_path)
    assert inventory["host"] and inventory["captured_at"]
    assert inventory["accelerators"]["status"] == "unavailable"
    assert inventory["execution_host"]["status"] == "unavailable"
