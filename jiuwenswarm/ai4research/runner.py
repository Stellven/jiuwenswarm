"""M0-IF-004@r2 shared once-only bounded compiler/verifier runner."""
from __future__ import annotations

import asyncio
import time
import uuid
from pathlib import Path

from .common import GovernanceError, canonical_json


class TrialRunner:
    def __init__(self, bridge, library, store):
        self.bridge, self.library, self.store = bridge, library, store

    async def invoke(self, run, role, input_data, *, pin, model, deadline, caller_id):
        if role not in {"compiler", "verifier"}:
            raise GovernanceError("policy_denied", "Only the two authored trial roles are allowed.")
        effective = run["configuration"].get("effective", run["configuration"])
        scope = "fixture-only" if effective.get("mock") else "real"
        self.library.validate_pin(pin, required_scope=scope)
        expected_pin = run["pins"][role]
        record = pin.to_dict() if hasattr(pin, "to_dict") else pin
        if model != effective["model_roles"][role] or any(record.get(key) != expected_pin.get(key) for key in ("sha256", "implementation_hash", "contract_hash")):
            raise GovernanceError("policy_denied", "Caller cannot substitute the frozen role model or implementation.")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise GovernanceError("timeout", "Node-wide time budget exhausted before dispatch.")
        per_call = effective.get("per_role_timeout_seconds", {}).get(role, remaining)
        declaration = pin.declaration if hasattr(pin, "declaration") else pin.get("declaration", {})
        declared_time = declaration.get("budget", {}).get("per_call", {}).get("wall_s", remaining)
        remaining = min(remaining, per_call, declared_time)
        attempt = self.store.begin_attempt(run["run_id"], role, caller_id=caller_id)
        identities = {"run_id": run["run_id"], "node_id": "intent", "attempt_id": attempt["attempt_id"],
                      "invocation_id": attempt["invocation_id"], "role": role}
        if effective.get("runtime_identity"):
            identities["runtime_identity"] = effective["runtime_identity"]
        started = time.monotonic()
        outcome = None
        observation_ref = None
        prompt_ref = None
        try:
            prompt_path = Path(__file__).parent / "intent" / (role + ".prompt.md")
            prompt_ref = self.store.put_artifact(run["run_id"], canonical_json({
                "role": role, "model": model, "identities": identities, "input_data": input_data,
                "developer_instructions": prompt_path.read_text(encoding="utf-8")}),
                artifact_type="invocation_context", origin="observed", attempt_id=attempt["attempt_id"],
                invocation_id=attempt["invocation_id"], caller_id=caller_id)
            remaining = min(deadline - time.monotonic(), per_call - (time.monotonic() - started), declared_time - (time.monotonic() - started))
            if remaining <= 0:
                raise GovernanceError("timeout", "Budget expired during required context persistence; no model dispatch.")
            async with asyncio.timeout(remaining):
                outcome = await self.bridge.complete(role=role, model=model, input_data=input_data,
                                                     identities=identities, timeout_seconds=remaining)
            # Capture attributable observations before deciding whether they satisfy policy.
            # Only declared metadata crosses custody; unknown fields may contain credentials.
            fields = {"text", "model", "provider", "runtime_version", "provider_version", "elapsed_seconds",
                      "model_calls", "usage", "cost", "seed", "effects", "is_mock", "mock",
                      "usage_unavailable_reason", "cost_unavailable_reason", "seed_unavailable_reason",
                      "thread_id", "turn_id", "account_fingerprint", "account_epoch", *identities}
            fields.update({"requested_model", "configured_model", "configured_model_provider", "model_identity_basis",
                           "served_model", "served_model_unavailable_reason"})
            observed = {key: outcome[key] for key in fields if key in outcome}
            observation_ref = self.store.put_artifact(run["run_id"], canonical_json(observed),
                artifact_type="invocation_observation", origin="observed", attempt_id=attempt["attempt_id"],
                invocation_id=attempt["invocation_id"], caller_id=caller_id)
            if outcome.get("effects") or outcome.get("model_calls") != 1 or outcome.get("model") != model:
                raise GovernanceError("prohibited_effect", "Execution evidence violates the frozen route/effect/call policy.")
            for key, value in identities.items():
                if outcome.get(key) != value:
                    raise GovernanceError("subject_mismatch", "Invocation evidence has different attribution.")
            if not isinstance(outcome.get("text"), str):
                raise GovernanceError("malformed_output", "No bounded text output was captured.")
            artifact = self.store.put_artifact(run["run_id"], outcome["text"].encode("utf-8"),
                artifact_type="intent_candidate" if role == "compiler" else "raw_assessment",
                schema_revision="intent-r2" if role == "compiler" else "assessment-r2",
                origin="candidate" if role == "compiler" else "assessment",
                attempt_id=identities["attempt_id"], invocation_id=identities["invocation_id"], caller_id=caller_id)
            evidence = {**observed, "text": None, "output_ref": artifact,
                        "prompt_ref": prompt_ref, "observation_ref": observation_ref,
                        "elapsed_seconds": time.monotonic() - started, "pin": pin.to_dict() if hasattr(pin, "to_dict") else pin}
            evidence["stdout_stderr_unavailable_reason"] = "Native backend exposes bounded text/protocol observations, not raw stderr or credential-bearing protocol."
            self.store.finish_attempt(run["run_id"], attempt["attempt_id"], outcome="success", evidence=evidence, caller_id=caller_id)
            return artifact, evidence
        except BaseException as exc:
            code = "cancelled" if isinstance(exc, asyncio.CancelledError) else "timeout" if isinstance(exc, TimeoutError) else getattr(exc, "code", "execution_failed")
            terminal = {"cancelled": "CANCELLED", "timeout": "TIMED_OUT",
                        "environment_unavailable": "ENVIRONMENT_BLOCKED",
                        "delivery_unknown": "DELIVERY_UNKNOWN"}.get(code, "FAILED")
            current = self.store.get_run(run["run_id"], caller_id=caller_id)
            stored_attempt = next(a for a in current["attempts"] if a["attempt_id"] == attempt["attempt_id"])
            if stored_attempt["outcome"] == "RUNNING":
                if isinstance(exc, asyncio.CancelledError) and current["status"] != "CANCELLED":
                    terminal = "INTERRUPTED"
                self.store.finish_attempt(run["run_id"], attempt["attempt_id"], outcome=terminal,
                                          evidence={"elapsed_seconds": time.monotonic() - started, "error": code,
                                                    "model_calls": outcome.get("model_calls") if isinstance(outcome, dict) else None,
                                                    "observed_model": outcome.get("model") if isinstance(outcome, dict) else None,
                                                    "effects": outcome.get("effects") if isinstance(outcome, dict) else None,
                                                    "prompt_ref": prompt_ref, "observation_ref": observation_ref,
                                                    "delivery": "observed" if outcome is not None else "unknown", **identities}, caller_id=caller_id)
            if isinstance(exc, asyncio.CancelledError):
                raise
            if isinstance(exc, GovernanceError):
                raise
            raise GovernanceError(code, "Trial invocation halted; automatic replay is forbidden.") from exc
