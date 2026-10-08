"""Bounded, server-owned compiler/gate lifecycle; implements M1-IF-INTENT@r1."""
from __future__ import annotations

import asyncio
import hashlib
import time
import uuid
from pathlib import Path

from .gate import semantic_gate, tier1
from .models import FrozenPolicy, GateDecision, InvocationEvidence
from .prompts import compiler_prompt, verifier_prompt
from .store import IntentStore, StoreError, encode_json

# Capture source identities with the loaded implementation. Editing files later
# cannot relabel already imported code or the policy used by an active run.
_SOURCE_PINS = {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                for name in ("models.py", "gate.py", "prompts.py", "store.py", "service.py", "bridge.py")}
_NATIVE_ROOT = Path(__file__).resolve().parents[2]
for _native_name in ("service.py", "transport.py"):
    _native_path = "server/runtime/codex_subscription/" + _native_name
    _SOURCE_PINS[_native_path] = hashlib.sha256((_NATIVE_ROOT / _native_path).read_bytes()).hexdigest()


class IntentService:
    def __init__(self, store: IntentStore, bridge, policy: FrozenPolicy | None = None):
        self.store = store
        self.bridge = bridge
        self.policy = policy or FrozenPolicy()
        self.tasks: dict[str, asyncio.Task] = {}
        self.volatile: dict[str, dict] = {}
        self._runtime_handle = None
        # Recovery can only run while no other process owns active execution.
        try:
            recovery_handle = self.store.claim_runtime()
        except StoreError as exc:
            if str(exc) != "RUNTIME_BUSY":
                raise
        else:
            try:
                self.store.recover_interrupted()
            finally:
                recovery_handle.close()

    def _capture(self, text, owner_id, profile_id, workspace_id, corrects_run_id, policy=None):
        policy = policy or self.policy
        if not isinstance(text, str) or not text.strip():
            raise ValueError("EMPTY_INPUT")
        if len(text.encode("utf-8")) > policy.max_input_bytes:
            raise ValueError("INPUT_SIZE_EXCEEDED")
        run_id = uuid.uuid4().hex
        pins = {"agreement": "M1-IF-INTENT@r1", "compiler": "fixed-intent-v1", "verifier": "fixed-intent-assessor-v1", "tools": [], "effects": []}
        pins.update(_SOURCE_PINS)
        self.store.create(run_id, text, owner_id, profile_id, workspace_id,
                          policy.model_dump(mode="json"), pins, corrects_run_id)
        return run_id

    def _begin(self, text, owner_id, profile_id, workspace_id, corrects_run_id, policy):
        if self._runtime_handle is not None:
            raise StoreError("RUNTIME_BUSY")
        self._runtime_handle = self.store.claim_runtime()
        try:
            self.store.recover_interrupted()
            return self._capture(text, owner_id, profile_id, workspace_id, corrects_run_id, policy)
        except BaseException:
            self._release_runtime()
            raise

    def _release_runtime(self):
        if self._runtime_handle is not None:
            self._runtime_handle.close()
            self._runtime_handle = None

    async def submit(self, text, owner_id, profile_id, workspace_id, corrects_run_id=None):
        policy = self.policy
        run_id = self._begin(text, owner_id, profile_id, workspace_id, corrects_run_id, policy)
        # Model work is not owned by the lifetime of this HTTP request/browser.
        self.tasks[run_id] = asyncio.create_task(self._process(run_id, text, owner_id, policy), name=f"intent-{run_id}")
        return run_id

    async def execute(self, text, owner_id, profile_id, workspace_id, corrects_run_id=None):
        policy = self.policy
        run_id = self._begin(text, owner_id, profile_id, workspace_id, corrects_run_id, policy)
        await self._process(run_id, text, owner_id, policy)
        return self.get(run_id, owner_id)

    @staticmethod
    def _halt(code, verdict="FAIL", tier1_passed=False):
        return GateDecision(verdict=verdict, tier1=tier1_passed, tier2=None, reasons=[code], warnings=[])

    async def _process(self, run_id, text, owner_id, policy):
        started = time.monotonic()
        calls = 0
        candidate = None
        passed_tier1 = False

        async def invoke(role, prompt):
            nonlocal calls
            remaining = policy.total_seconds - (time.monotonic() - started)
            if remaining <= 0:
                raise RuntimeError("TOTAL_TIME_EXCEEDED")
            if calls >= policy.max_calls:
                raise RuntimeError("CALL_BUDGET_EXCEEDED")
            calls += 1
            call_started = time.monotonic()
            self.store.write(run_id, f"{role}.prompt.txt", prompt)
            def preserve_observation(observation):
                if not isinstance(observation, InvocationEvidence):
                    raise RuntimeError("INVALID_INVOCATION_EVIDENCE")
                # Producer/adapter timestamps cannot reduce host-observed wall time.
                observation = observation.model_copy(update={"elapsed_seconds": max(observation.elapsed_seconds, time.monotonic() - call_started)})
                self.store.write(run_id, f"{role}.json", encode_json(observation.model_dump(mode="json")))
                self.store.write(run_id, "candidate.raw.json" if role == "compiler" else "assessment.raw.json", observation.raw_output)
                return observation

            call_task = asyncio.create_task(self.bridge.invoke(role, prompt, run_id, policy))
            try:
                observation = await asyncio.wait_for(call_task, timeout=min(policy.per_call_seconds, remaining))
            except asyncio.CancelledError:
                # wait_for finishes cancellation cleanup before propagating the
                # parent's cancellation. The native bridge can return a partial
                # receipt during that cleanup; preserve it without advancing.
                if call_task.done() and not call_task.cancelled():
                    try:
                        partial = call_task.result()
                    except Exception:
                        partial = None
                    if isinstance(partial, InvocationEvidence):
                        preserve_observation(partial)
                raise
            return preserve_observation(observation)

        try:
            self.store.state(run_id, "COMPILING")
            compiler = await invoke("compiler", compiler_prompt(text, run_id))
            candidate, decision = tier1(compiler.raw_output, text, run_id, compiler, policy)
            self.store.write(run_id, "tier1.json", encode_json(decision.model_dump(mode="json")))
            passed_tier1 = bool(decision.tier1)
            if candidate is not None and decision.verdict == "PASS":
                self.store.state(run_id, "VERIFYING")
                verifier = await invoke("verifier", verifier_prompt(text, compiler.raw_output, run_id))
                decision = semantic_gate(verifier.raw_output, text, compiler.raw_output, run_id, compiler, verifier, policy)
            if time.monotonic() - started > policy.total_seconds:
                decision = self._halt("TOTAL_TIME_EXCEEDED", tier1_passed=passed_tier1)
            # Cancellation is delivered at the final yield before release.
            await asyncio.sleep(0)
            self.store.complete(run_id, decision, candidate)
        except asyncio.CancelledError:
            self._preserve_halt(run_id, owner_id, self._halt("CANCELLED", tier1_passed=passed_tier1))
        except asyncio.TimeoutError:
            self._preserve_halt(run_id, owner_id, self._halt("TIME_BUDGET_EXCEEDED", tier1_passed=passed_tier1))
        except (OSError, StoreError):
            self._undurable(run_id, owner_id, "PERSISTENCE_UNAVAILABLE")
        except Exception as exc:
            stable = str(exc) if str(exc) in {"TOTAL_TIME_EXCEEDED", "CALL_BUDGET_EXCEEDED", "INVALID_INVOCATION_EVIDENCE"} else "MODEL_ENVIRONMENT_UNAVAILABLE"
            verdict = "FAIL" if stable in {"TOTAL_TIME_EXCEEDED", "CALL_BUDGET_EXCEEDED"} else "ENVIRONMENT_BLOCKED"
            self._preserve_halt(run_id, owner_id, self._halt(stable, verdict, passed_tier1))
        finally:
            self.tasks.pop(run_id, None)
            self._release_runtime()

    def _preserve_halt(self, run_id, owner_id, decision):
        try:
            self.store.complete(run_id, decision)
        except Exception:
            self._undurable(run_id, owner_id, "PERSISTENCE_UNAVAILABLE")

    def _undurable(self, run_id, owner_id, reason):
        self.volatile[run_id] = {"owner_id": owner_id, "run_id": run_id, "state": "HALTED", "status": "HALTED",
                                 "verdict": "ENVIRONMENT_BLOCKED", "reasons": [reason], "warnings": [],
                                 "accepted_reference": None, "accepted_intent": None, "evidence": {"artifacts": []},
                                 "durable": False, "corrects_run_id": None,
                                 "correction": "Restore storage and start a fresh attributable run; no accepted result is available."}

    def get(self, run_id, owner_id):
        if run_id in self.volatile:
            result = self.volatile[run_id]
            if result["owner_id"] != owner_id:
                raise StoreError("RUN_NOT_FOUND")
            return {k: v for k, v in result.items() if k != "owner_id"}
        try:
            row = self.store.read(run_id, owner_id)
        except StoreError as exc:
            if str(exc) == "EVIDENCE_INTEGRITY_FAILED":
                return {"run_id": run_id, "state": "HALTED", "status": "HALTED", "verdict": "ENVIRONMENT_BLOCKED",
                        "reasons": ["EVIDENCE_INTEGRITY_FAILED"], "warnings": [], "accepted_reference": None,
                        "accepted_intent": None, "evidence": {"artifacts": []}, "durable": False,
                        "corrects_run_id": None, "correction": "Inspect stored evidence; create a fresh corrected run."}
            raise
        decision = row["decision"] or {}
        reference = row["accepted_reference"]
        return {"run_id": run_id, "state": row["state"], "status": row["state"], "verdict": decision.get("verdict"),
                "reasons": decision.get("reasons", ["INTERRUPTED_RUN_PAUSED"] if row["state"] == "PAUSED" else []),
                "warnings": decision.get("warnings", []), "accepted_reference": reference,
                "accepted_intent": reference["intent"] if reference else None,
                "evidence": {"artifacts": row["artifacts"]}, "durable": True,
                "corrects_run_id": row["corrects_run_id"],
                "correction": "Start a linked fresh run with corrected input or repaired environment." if row["state"] in {"HALTED", "PAUSED"} else None}

    async def cancel(self, run_id, owner_id):
        current = self.get(run_id, owner_id)
        task = self.tasks.get(run_id)
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                # Cancellation before coroutine entry still needs a host halt.
                self._preserve_halt(run_id, owner_id, self._halt("CANCELLED"))
                self._release_runtime()
            self.tasks.pop(run_id, None)
        return self.get(run_id, owner_id) if task else current
