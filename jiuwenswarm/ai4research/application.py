"""M0-IF-006/020@r2: authenticated, fixed sequence and durable projection."""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from pathlib import Path

from .common import GovernanceError, canonical_json, hash_json, sha256_bytes
from .configuration import resolve_configuration, validate_trial_options
from .intent.models import validate_intent
from .runner import TrialRunner
from .verification.gate import aggregate

PACKAGE = Path(__file__).parent
TERMINAL = {"ACCEPTED", "FAILED", "ENVIRONMENT_BLOCKED", "INCONCLUSIVE", "CANCELLED", "PAUSED"}


class IntentTrialApplication:
    """Clients can submit/inspect/cancel. They never receive gate authority."""

    def __init__(self, *, identity, library, store, bridge, baseline, gate_authority, pins):
        self.identity, self.library, self.store, self.bridge = identity, library, store, bridge
        self.baseline, self._gate_authority, self.pins = baseline, gate_authority, pins
        self.runner = TrialRunner(bridge, library, store)
        self.tasks = {}
        self.volatile_faults = {}
        self._submit_lock = asyncio.Lock()
        self.profile_bytes = (PACKAGE / "verification/profile.json").read_bytes()
        self.profile_sha256 = sha256_bytes(self.profile_bytes)

    async def readiness(self):
        bridge = await self.bridge.readiness()
        custody = self.identity.custody_status()
        storage = self.store.readiness()
        mock = bool(getattr(self.bridge, "is_mock", False))
        route_matches = not self.baseline or (self.baseline["provider"] == "mock") == mock
        return {"scope": "TRIAL-1", "model": bridge, "storage": storage,
                "identity_security": custody,
                "definitions": "ready" if self.baseline else "environment_blocked",
                "definition_admission": getattr(self, "admission_status", {"ready": bool(self.baseline)}),
                "ready": bool(self.baseline) and bridge.get("ready", False) and storage["ready"] and route_matches and (mock or custody.get("ready", False)),
                "mock": bool(getattr(self.bridge, "is_mock", False)),
                "acceptance": "Fixture wiring only" if getattr(self.bridge, "is_mock", False) else "Actual connected acceptance requires recorded runs"}

    def _owned_run(self, ctx, run_id):
        run = self.store.get_run(run_id, caller_id=ctx.user_id)
        if run["workspace_id"] != ctx.workspace_id:
            raise GovernanceError("policy_denied", "Run belongs to another workspace.")
        return run

    async def submit(self, ctx, *, original_text, client_request_id, options=None, predecessor_run_id=None):
        if not isinstance(original_text, str) or not original_text.strip() or len(original_text.encode("utf-8")) > 32768:
            raise GovernanceError("invalid_input", "Submit a nonempty text objective within the 32 KiB limit.")
        if not isinstance(client_request_id, str) or not client_request_id.strip() or len(client_request_id) > 128:
            raise GovernanceError("invalid_input", "A bounded client request identity is required.")
        if not Path(ctx.workspace_path).is_dir():
            raise GovernanceError("environment_unavailable", "Authorized workspace is unavailable.")
        options = validate_trial_options(options)
        submission_hash = hash_json({"original_text": original_text, "options": options,
                                    "predecessor_run_id": predecessor_run_id})
        async with self._submit_lock:
            for old in self.store.list_runs(caller_id=ctx.user_id, workspace_id=ctx.workspace_id):
                if old["client_request_id"] == client_request_id:
                    if old["contract"].get("submission_sha256") != submission_hash:
                        raise GovernanceError("invalid_input", "Client request identity cannot be reused for changed input.")
                    return self.project(ctx, old["run_id"])
            if any(not task.done() for task in self.tasks.values()):
                raise GovernanceError("model_busy", "One trial run is already active; inspect it before submitting fresh work.")
            if predecessor_run_id:
                self._owned_run(ctx, predecessor_run_id)
            run_id = uuid.uuid4().hex
            pin_records = {role: pin.to_dict() if hasattr(pin, "to_dict") else pin for role, pin in self.pins.items()}
            if self.baseline:
                profile = resolve_configuration(options, dict(self.identity.get_profile().defaults), self.baseline).to_dict()
            else:
                profile = {"interface_revision": "M0-IF-002@r2", "requested": options,
                           "effective": {"mode": options.get("mode", "web"), "model_roles": None,
                                         "seed": None, "requested_seed": options.get("seed"),
                                         "seed_unavailable_reason": "Native seed control unavailable.",
                                         "readiness": "environment_blocked"}}
            contract = {"interface_revision": "M0-IF-006@r2", "run_id": run_id, "node_id": "intent",
                        "user_id": ctx.user_id, "workspace_id": ctx.workspace_id, "session_id": ctx.session_id,
                        "original_sha256": sha256_bytes(original_text.encode("utf-8")),
                        "submission_sha256": submission_hash, "profile_sha256": self.profile_sha256,
                        "output_schema": "intent-r2", "responsibility": "Faithful intermediate Intent extraction; architecture D5",
                        "sequence": ["compiler", "deterministic_checks", "verifier", "protected_durable_gate"],
                        "pins": pin_records, "allowed_effects": [], "automatic_retries": 0,
                        "runtime_identity": profile["effective"].get("runtime_identity"),
                        "scope": "TRIAL-1 only; stage/full-M1 exits incomplete"}
            run = self.store.create_run(user_id=ctx.user_id, workspace_id=ctx.workspace_id,
                client_request_id=client_request_id, original_text=original_text, configuration=profile,
                contract=contract, pins=pin_records, run_id=run_id, mode=profile["effective"]["mode"],
                predecessor_run_id=predecessor_run_id, caller_id=ctx.user_id)
            try:
                for artifact_type, data in (("frozen_configuration", profile), ("intent_contract", contract),
                                            ("cc_pins", pin_records), ("verifier_profile", json.loads(self.profile_bytes))):
                    self.store.put_artifact(run_id, canonical_json(data), artifact_type=artifact_type, caller_id=ctx.user_id)
            except GovernanceError as exc:
                self.volatile_faults[run_id] = exc.code
                return self.project(ctx, run_id)
            task = asyncio.create_task(self._execute(ctx, run, dict(self.pins)), name=f"intent-trial-{run_id}")
            self.tasks[run_id] = task
            task.add_done_callback(lambda completed, key=run_id: self.tasks.pop(key, None))
            return self.project(ctx, run_id)

    def _artifact(self, run, kind, data):
        return self.store.put_artifact(run["run_id"], canonical_json(data), artifact_type=kind, caller_id=run["user_id"])

    async def _execute(self, ctx, run, pins):
        subject = None
        evidence_refs = [run["original_ref"]]
        try:
            readiness = await self.readiness()
            self._artifact(run, "readiness", readiness)
            if not readiness["ready"] or not self.baseline:
                raise GovernanceError("environment_unavailable", "Authenticated model, definitions or protected IPC is unavailable.")
            effective = run["configuration"]["effective"]
            deadline = time.monotonic() + effective["total_timeout_seconds"]
            # Recheck exact closure/standing; never replace frozen pins.
            scope = "fixture-only" if effective.get("mock") else "real"
            for pin in pins.values():
                self.library.validate_pin(pin, required_scope=scope)
            if sha256_bytes((PACKAGE / "verification/profile.json").read_bytes()) != self.profile_sha256:
                raise GovernanceError("profile_changed", "Protected fidelity profile changed after freeze.")
            self.store.set_status(run["run_id"], "COMPILING", caller_id=ctx.user_id)
            compiler_input = {"run_id": run["run_id"], "source_sha256": run["original_ref"]["sha256"],
                              "original_text": run["original_text"]}
            subject, compiler_evidence = await self.runner.invoke(run, "compiler", compiler_input,
                pin=pins["compiler"], model=effective["model_roles"]["compiler"], deadline=deadline, caller_id=ctx.user_id)
            evidence_refs.append(subject)
            self.store.set_status(run["run_id"], "CHECKING", caller_id=ctx.user_id)
            raw = self.store.get_artifact(subject, caller_id=ctx.user_id)
            validate_intent(raw, run["original_text"], run["run_id"])
            for pin in pins.values():
                self.library.validate_pin(pin, required_scope=scope)
            deterministic = [{"check_id": "D1", "status": "PASS", "reason": "Strict intermediate schema and exact original/run/source evidence validated.",
                              "evidence_refs": ["original", "candidate", "execution"]},
                             {"check_id": "D2", "status": "PASS", "reason": "Frozen implementation pins, single bounded compiler call and no prohibited effects observed.",
                              "evidence_refs": ["execution"]}]
            checks_ref = self._artifact(run, "deterministic_checks", deterministic)
            evidence_refs.append(checks_ref)
            self.store.record_event(run["run_id"], "deterministic_pass", {"subject_ref": subject, "checks_ref": checks_ref}, caller_id=ctx.user_id)
            if effective["max_calls"] < 2:
                raise GovernanceError("call_budget", "Frozen total call ceiling forbids semantic dispatch.")
            self.store.set_status(run["run_id"], "VERIFYING", caller_id=ctx.user_id)
            verifier_input = {"original_text": run["original_text"], "candidate": json.loads(raw),
                "subject_sha256": subject["sha256"], "source_sha256": run["original_ref"]["sha256"],
                "contract": run["contract"], "contract_sha256": hash_json(run["contract"]),
                "profile": json.loads(self.profile_bytes), "profile_sha256": self.profile_sha256,
                "execution": compiler_evidence, "deterministic": deterministic}
            assessment_ref, verifier_evidence = await self.runner.invoke(run, "verifier", verifier_input,
                pin=pins["verifier"], model=effective["model_roles"]["verifier"], deadline=deadline, caller_id=ctx.user_id)
            evidence_refs.append(assessment_ref)
            self.store.set_status(run["run_id"], "DECIDING", caller_id=ctx.user_id)
            for pin in pins.values():
                self.library.validate_pin(pin, required_scope=scope)
            if time.monotonic() >= deadline:
                raise GovernanceError("timeout", "Node-wide budget expired before durable decision.")
            final_readiness = await self.readiness()
            if not final_readiness["ready"]:
                raise GovernanceError("environment_unavailable", "Required security or authentication changed before release.")
            frozen_runtime = effective.get("runtime_identity")
            if frozen_runtime and any(final_readiness["model"].get(key) != value
                                      for key, value in frozen_runtime.items()):
                raise GovernanceError("account_changed", "Frozen model account generation changed before durable release.")
            # Re-read exact subject and assessment; a memory/UI cache has no authority.
            self.store.get_artifact(subject, caller_id=ctx.user_id)
            decision = aggregate(self.store.get_artifact(assessment_ref, caller_id=ctx.user_id),
                subject_ref=subject, original_ref=run["original_ref"], contract=run["contract"],
                profile_sha256=self.profile_sha256, deterministic=deterministic, evidence_refs=evidence_refs)
            self._commit(run, decision, subject, evidence_refs)
        except asyncio.CancelledError:
            return
        except Exception as exc:
            code = getattr(exc, "code", "execution_failed")
            verdict = "ENVIRONMENT_BLOCKED" if code in {"environment_unavailable", "security_unavailable", "ineligible_pin"} else "INCONCLUSIVE" if code in {"malformed_assessment", "missing_findings", "delivery_unknown"} else "FAIL"
            decision = {"verdict": verdict, "subject_ref": subject, "evidence_refs": evidence_refs,
                        "mandatory_pass": False, "checks": [{"check_id": "halt", "status": verdict, "reason": code}],
                        "reasons": [code], "profile_sha256": self.profile_sha256,
                        "contract_sha256": hash_json(run["contract"])}
            try:
                current = self.store.get_run(run["run_id"], caller_id=ctx.user_id)
                if current["status"] not in TERMINAL:
                    self.record_not_run(current, code)
                    self._commit(run, decision, subject, evidence_refs)
            except Exception:
                # Persistence faults cannot publish or invent a persisted reason.
                # The durable unfinished run is inspectable and pauses on restart.
                self.volatile_faults[run["run_id"]] = "persistence_failed"
                return

    def record_not_run(self, run, reason):
        roles = {a["role"] for a in run["attempts"]}
        checks = []
        if "compiler" not in roles:
            checks.append({"check_id": "compiler_dispatch", "status": "NOT_RUN", "reason": reason})
        # A failed invocation prevents deterministic validation even though the
        # compiler has an attempt record. CHECKING proves validation was reached.
        reached_validation = any(e["event_type"] == "status" and e["payload"].get("status") == "CHECKING"
                                 for e in run["events"])
        if not reached_validation:
            checks.append({"check_id": "deterministic_validation", "status": "NOT_RUN", "reason": reason})
        if "verifier" not in roles:
            checks.extend({"check_id": stage, "status": "NOT_RUN", "reason": reason}
                          for stage in ("verifier_dispatch", *(f"semantic:F{i}" for i in range(1, 7))))
        if checks:
            self.store.record_event(run["run_id"], "not_run", {"checks": checks}, caller_id=run["user_id"])

    def _commit(self, run, decision, subject, evidence_refs):
        receipt = self.store.commit_decision(run["run_id"], subject_ref=subject, decision=decision,
            evidence_refs=evidence_refs, authority=self._gate_authority, caller_id=run["user_id"], idempotency_key="final-decision-r2")
        if not receipt["accepted_ref"]:
            self.store.record_event(run["run_id"], "attention_required", {
                "attention_id": receipt["decision_sha256"],
                "run_id": run["run_id"], "reason": decision["reasons"], "action": "Inspect evidence and submit fresh corrected work.",
                "mode": run["mode"], "override_allowed": False}, caller_id=run["user_id"])

    def project(self, ctx, run_id):
        run = self._owned_run(ctx, run_id)
        output = {"run_id": run_id, "status": run["status"], "client_request_id": run["client_request_id"],
                  "predecessor_run_id": run["predecessor_run_id"], "accepted_ref": run["accepted_ref"],
                  "decision": run["decision"], "attention": [e["payload"] for e in run["events"] if e["event_type"] == "attention_required"],
                  "not_run": [check for e in run["events"] if e["event_type"] == "not_run" for check in e["payload"]["checks"]],
                  "bundle_url": f"/api/intent-trial/runs/{run_id}/bundle", "mock": run["configuration"].get("effective", {}).get("mock", False),
                  "scope": "TRIAL-1 intermediate Intent; full stages/M1 incomplete"}
        if run["accepted_ref"]:
            output["accepted_intent"] = json.loads(self.store.get_artifact(run["accepted_ref"], caller_id=ctx.user_id))
        elif run_id in self.volatile_faults and run["status"] not in TERMINAL:
            output.update(status="ENVIRONMENT_BLOCKED", durable_status=run["status"], reason_durable=False,
                          volatile_reason=self.volatile_faults[run_id],
                          attention=[{"attention_id": run_id + "-storage-unavailable", "reason": ["persistence_failed"],
                                      "action": "Storage is unavailable; this reason is not durably recorded. Inspect after repair and submit fresh work.",
                                      "override_allowed": False}])
        elif run["status"] in {"CANCELLED", "PAUSED"}:
            reason = "Explicit cancellation" if run["status"] == "CANCELLED" else "Service interruption; no replay"
            output["attention"] = [{"attention_id": run_id + "-" + run["status"], "reason": [reason],
                                    "action": reason + ". Inspect evidence or submit fresh linked work.", "override_allowed": False}]
        return output

    async def cancel(self, ctx, run_id):
        run = self._owned_run(ctx, run_id)
        self.store.cancel(run_id, caller_id=ctx.user_id, reason="Explicit authenticated user cancellation.")
        self.record_not_run(self._owned_run(ctx, run_id), "Explicit cancellation")
        task = self.tasks.get(run_id)
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        return self.project(ctx, run_id)

    async def shutdown(self):
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.store.recover_interrupted()
