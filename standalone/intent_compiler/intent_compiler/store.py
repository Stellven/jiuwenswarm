"""Immutable capture and SQLite release authority. M0-IF-002@r1.

Artifact presence never proves acceptance. Only a successful acceptance transaction
can expose released outputs to consumers. Paths and hashes are checked on each read.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import uuid
import math
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def json_bytes(payload) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class StoreError(RuntimeError):
    pass


class Conflict(StoreError):
    pass


class Busy(StoreError):
    pass


class Store:
    def __init__(self, state_dir: Path):
        self.root = Path(state_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.files = self.root / "artifacts"
        self.files.mkdir(exist_ok=True)
        self.db = self.root / "runs.sqlite3"
        self._lock = threading.RLock()
        with self.connection() as con:
            con.executescript("""
                CREATE TABLE IF NOT EXISTS runs(
                    id TEXT PRIMARY KEY, client_id TEXT NOT NULL, account TEXT NOT NULL,
                    workspace TEXT NOT NULL, payload_hash TEXT NOT NULL, data TEXT NOT NULL,
                    UNIQUE(account,workspace,client_id));
                CREATE TABLE IF NOT EXISTS artifacts(
                    run_id TEXT NOT NULL,name TEXT NOT NULL,hash TEXT NOT NULL,
                    metadata TEXT NOT NULL, PRIMARY KEY(run_id,name));
                CREATE TABLE IF NOT EXISTS acceptance(
                    run_id TEXT NOT NULL,scope TEXT NOT NULL,subject TEXT NOT NULL,
                    gate_ref TEXT NOT NULL,record_ref TEXT NOT NULL,
                    PRIMARY KEY(run_id,scope));
                CREATE TABLE IF NOT EXISTS identity(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            """)
            con.execute("INSERT OR IGNORE INTO identity VALUES('instance_id',?)", (str(uuid.uuid4()),))
        # Account/profile custody is separate from run/workspace records.
        self.accounts_db = self.root / "accounts.sqlite3"
        with sqlite3.connect(self.accounts_db) as con:
            con.execute("CREATE TABLE IF NOT EXISTS profiles(account TEXT PRIMARY KEY,data TEXT NOT NULL)")

    @contextmanager
    def connection(self):
        con = sqlite3.connect(self.db, timeout=15)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA synchronous=FULL")
        con.execute("PRAGMA foreign_keys=ON")
        try:
            with con:
                yield con
        finally:
            con.close()

    @property
    def instance_id(self):
        with self.connection() as con:
            return con.execute("SELECT value FROM identity WHERE key='instance_id'").fetchone()[0]

    def register_profile(self, account: str, payload: dict):
        with sqlite3.connect(self.accounts_db) as con:
            con.execute("INSERT OR IGNORE INTO profiles VALUES(?,?)", (account, json.dumps(payload)))

    def _path(self, run_id: str, name: str) -> Path:
        if not run_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in run_id):
            raise StoreError("Invalid capture scope")
        parts = PurePosixPath(name)
        if not name or "\\" in name or parts.is_absolute() or any(p in (".", "..") for p in parts.parts) or ":" in name:
            raise StoreError("Artifact path is not confined")
        target = self.files / run_id / Path(*parts.parts)
        if not target.resolve().is_relative_to(self.files.resolve()):
            raise StoreError("Artifact path escapes storage")
        current = target
        while current != self.root:
            if current.is_symlink() or (current.exists() and getattr(current, "is_junction", lambda: False)()):
                raise StoreError("Artifact storage links are forbidden")
            current = current.parent
        return target

    def put_bytes(self, run_id: str, name: str, data: bytes, artifact_type="record", schema_version="1.0.0",
                  producing_invocation=None, media_type="application/octet-stream", **metadata) -> dict:
        if not isinstance(data, bytes):
            raise StoreError("Captured content must be bytes")
        target = self._path(run_id, name)
        ref = {"id": name, "sha256": digest(data)}
        with self._lock:
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                with target.open("xb") as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
                if os.name == "posix":
                    fd = os.open(str(target.parent), os.O_RDONLY)
                    try:
                        os.fsync(fd)
                    finally:
                        os.close(fd)
            except FileExistsError:
                if target.read_bytes() != data:
                    raise StoreError("Immutable artifact name already captures different content")
            envelope = {"ref": ref, "id": name, "sha256": ref["sha256"], "path": name, "artifact_type": artifact_type,
                        "schema_version": schema_version, "media_type": media_type,
                        "run_id": run_id, "producing_invocation": producing_invocation,
                        "audience": "authorized-user", "captured_at": utc_now(), **metadata}
            with self.connection() as con:
                existing = con.execute("SELECT hash FROM artifacts WHERE run_id=? AND name=?", (run_id, name)).fetchone()
                if existing and existing[0] != ref["sha256"]:
                    raise StoreError("Capture inventory identity conflict")
                con.execute("INSERT OR IGNORE INTO artifacts VALUES(?,?,?,?)",
                            (run_id, name, ref["sha256"], json.dumps(envelope)))
        return ref

    def put_json(self, run_id, name, payload, artifact_type="record", schema_version="1.0.0", producing_invocation=None, **metadata):
        return self.put_bytes(run_id, name, json_bytes(payload), artifact_type, schema_version,
                              producing_invocation, media_type="application/json", **metadata)

    def read_bytes(self, run_id: str, reference: dict | str) -> bytes:
        name = reference["id"] if isinstance(reference, dict) else reference
        with self.connection() as con:
            row = con.execute("SELECT hash FROM artifacts WHERE run_id=? AND name=?", (run_id, name)).fetchone()
        if not row:
            raise StoreError("Unknown artifact")
        data = self._path(run_id, name).read_bytes()
        if digest(data) != row[0] or (isinstance(reference, dict) and reference.get("sha256") != row[0]):
            raise StoreError("Artifact identity mismatch")
        return data

    def get_json(self, run_id, reference):
        return json.loads(self.read_bytes(run_id, reference).decode("utf-8"))

    def artifacts(self, run_id):
        with self.connection() as con:
            return [json.loads(r[0]) for r in con.execute("SELECT metadata FROM artifacts WHERE run_id=? ORDER BY name", (run_id,))]

    def create_run(self, client_request_id: str, submission: dict, account_id: str, workspace_id: str):
        if not client_request_id or len(client_request_id) > 200:
            raise StoreError("Client request ID must be nonempty and bounded")
        value_hash = digest(json_bytes(submission))
        with self._lock, self.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            prior = con.execute("SELECT id,payload_hash FROM runs WHERE client_id=? AND account=? AND workspace=?",
                                (client_request_id, account_id, workspace_id)).fetchone()
            if prior:
                if prior[1] != value_hash:
                    raise Conflict("Client request ID already names different input")
                return prior[0], False
            for row in con.execute("SELECT data FROM runs"):
                if json.loads(row[0])["status"] in ("queued", "running", "cancelling"):
                    raise Busy("Only one active compiler run is supported")
            run_id = str(uuid.uuid4())
            data = {"run_id": run_id, "client_request_id": client_request_id, "account_id": account_id,
                    "workspace_id": workspace_id, "submission": submission, "revision": 1,
                    "stage": "intake", "status": "queued", "candidate_refs": [], "accepted_refs": [],
                    "decision_ref": None, "bundle_ref": None, "reasons": [], "cancel_requested": False,
                    "created_at": utc_now(), "configuration_ref": None}
            con.execute("INSERT INTO runs VALUES(?,?,?,?,?,?)",
                        (run_id, client_request_id, account_id, workspace_id, value_hash, json.dumps(data)))
        return run_id, True

    def get_run(self, run_id):
        with self.connection() as con:
            row = con.execute("SELECT data FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise StoreError("Unknown run")
        return json.loads(row[0])

    def find_request(self, client_id, account_id, workspace_id):
        with self.connection() as con:
            row = con.execute("SELECT id FROM runs WHERE client_id=? AND account=? AND workspace=?",
                              (client_id, account_id, workspace_id)).fetchone()
        return row[0] if row else None

    def update_run(self, run_id, **fields):
        with self._lock, self.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT data FROM runs WHERE id=?", (run_id,)).fetchone()
            if not row:
                raise StoreError("Unknown run")
            data = json.loads(row[0])
            if fields.get("status") == "completed":
                if not con.execute("SELECT 1 FROM acceptance WHERE run_id=? AND scope='node'", (run_id,)).fetchone():
                    raise StoreError("Completion requires durable node acceptance")
            if data["cancel_requested"] and fields.get("status") in ("running", "completed", "queued"):
                raise StoreError("Cancelled work cannot dispatch or release")
            data.update(fields)
            data["revision"] += 1
            con.execute("UPDATE runs SET data=? WHERE id=?", (json.dumps(data), run_id))
        return data

    def pause_interrupted(self):
        with self._lock, self.connection() as con:
            for row in con.execute("SELECT id,data FROM runs").fetchall():
                data = json.loads(row[1])
                if data["status"] in ("queued", "running", "cancelling"):
                    data.update(status="paused", reasons=["Application restart interrupted work; no replay"], revision=data["revision"] + 1)
                    con.execute("UPDATE runs SET data=? WHERE id=?", (json.dumps(data), row[0]))

    def cancelled(self, run_id):
        return bool(self.get_run(run_id)["cancel_requested"])

    def request_cancel(self, run_id, request_id):
        name = "Cancellation_" + digest(request_id.encode())[:16] + ".json"
        with self._lock:
            with self.connection() as con:
                exists = con.execute("SELECT 1 FROM artifacts WHERE run_id=? AND name=?", (run_id, name)).fetchone()
            if exists:
                return self.get_json(run_id, name)
            # Same lock as acceptance: inspect current terminal state atomically with mutation.
            state = self.get_run(run_id)
            terminal = state["status"] in ("completed", "halted", "cancelled", "paused")
            record = {"schema_version": "1.0.0", "id": f"cancel:{request_id}", "request_id": request_id,
                      "run_id": run_id, "status": "terminal" if terminal else "acknowledged",
                      "preserved_effects": ["Saved input/candidate/evidence records remain; started provider effects cannot be undone"]}
            if not terminal:
                self.update_run(run_id, cancel_requested=True, status="cancelling", reasons=["Explicit cancellation requested"])
            self.put_json(run_id, name, record, artifact_type="client-cancellation")
            return record

    def accept(self, run_id, scope, subject_ref, gate_ref, contract_ref):
        from .checks import check_gate
        gate = self.get_json(run_id, gate_ref)
        errors = check_gate(gate)
        if errors or gate["action"] != "advance" or gate["run_id"] != run_id:
            raise StoreError("Invalid advancing gate: " + "; ".join(errors))
        if gate["accepted_refs"] != [subject_ref] or gate["contract_ref"] != contract_ref:
            raise StoreError("Acceptance subject/contract mismatch")
        self.read_bytes(run_id, subject_ref)
        self.read_bytes(run_id, contract_ref)
        for key in ("assessment_ref", "deterministic_result_ref", "node_contract_ref", "policy_ref", "check_plan_ref"):
            if gate.get(key):
                self.read_bytes(run_id, gate[key])
        for ref in gate["invocation_refs"] + gate["internal_decision_refs"]:
            self.read_bytes(run_id, ref)
        if scope == "node" and (gate["scope_kind"] != "node" or gate["subnode_id"] is not None):
            raise StoreError("External release requires node scope")
        if scope != "node" and (gate["scope_kind"] != "subnode" or gate["subnode_id"] != scope):
            raise StoreError("Internal acceptance scope mismatch")
        self._validate_acceptance(run_id, scope, gate, subject_ref, contract_ref)
        record = {"schema_version": "2.0.0", "id": "acceptance:" + str(uuid.uuid4()), "run_id": run_id,
                  "node_id": gate["node_id"], "attempt_id": gate["attempt_id"], "gate_ref": gate_ref,
                  "contract_ref": contract_ref, "output_refs": [subject_ref], "commit_id": str(uuid.uuid4()),
                  "node_contract_ref": gate["node_contract_ref"], "subnode_id": None if scope == "node" else scope}
        # Proposed record can survive a failed commit; acceptance table alone is authority.
        # Capture it before acquiring SQLite's write transaction to avoid nested writers.
        rec_ref = self.put_json(run_id, f"Accepted_{scope}.json", record, artifact_type="accepted-output", schema_version="2.0.0")
        with self._lock, self.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT data FROM runs WHERE id=?", (run_id,)).fetchone()
            if not row:
                raise StoreError("Unknown run")
            state = json.loads(row[0])
            if state["cancel_requested"] or state["status"] in ("paused", "halted", "cancelled"):
                raise StoreError("Run cannot advance after cancellation/halt/interruption")
            if con.execute("SELECT 1 FROM acceptance WHERE run_id=? AND scope=?", (run_id, scope)).fetchone():
                raise StoreError("Acceptance is immutable and cannot be replaced")
            if scope == "node":
                prior = con.execute("SELECT scope,subject,gate_ref FROM acceptance WHERE run_id=?", (run_id,)).fetchall()
                by_scope = {r[0]: r for r in prior}
                if not {"intention", "requirements"}.issubset(by_scope):
                    raise StoreError("Node release requires both internal acceptances")
                if json.loads(by_scope["requirements"][1]) != subject_ref:
                    raise StoreError("Node release changed accepted Requirements subject")
                expected_gates = [json.loads(by_scope[s][2]) for s in ("intention", "requirements")]
                if gate["internal_decision_refs"] != expected_gates:
                    raise StoreError("Node release internal decision chain mismatch")
            con.execute("INSERT INTO acceptance VALUES(?,?,?,?,?)", (run_id, scope, json.dumps(subject_ref), json.dumps(gate_ref), json.dumps(rec_ref)))
            state.update(decision_ref=gate_ref, revision=state["revision"] + 1)
            state["candidate_refs"] = [ref for ref in state["candidate_refs"] if ref != subject_ref]
            if scope != "node":
                state["accepted_refs"] = state["accepted_refs"] + [subject_ref]
            if scope == "node":
                state.update(status="completed", stage="released", accepted_refs=[subject_ref], reasons=["Research Brief durably released"])
            con.execute("UPDATE runs SET data=? WHERE id=?", (json.dumps(state), run_id))
        return rec_ref

    def _validate_acceptance(self, run_id, scope, gate, subject, contract_ref):
        """Resolve actual evidence at the durable authority, not just gate claims."""
        from . import checks
        def require(condition, reason):
            if not condition:
                raise StoreError("Acceptance evidence invalid: " + reason)
        contract = self.get_json(run_id, contract_ref)
        node = self.get_json(run_id, gate["node_contract_ref"])
        require(not checks.validate_field_contract("node-execution-contract", node), "node contract shape")
        for payload in (node, contract):
            require(all(payload.get(k) == gate[k] for k in ("run_id", "node_id", "attempt_id")), "contract run/node/attempt scope")
        if scope == "node":
            require(contract_ref == gate["node_contract_ref"], "node contract identity")
        else:
            require(not checks.validate_schema("subnode-execution-contract", contract), "subnode contract shape")
            require(contract["subnode_id"] == scope and contract["node_contract_ref"] == gate["node_contract_ref"], "subnode parent/scope")
        require(contract.get("configuration_ref") == node["configuration_ref"], "protected configuration pin")
        require(gate["input_refs"] == contract["input_refs"], "gate/contract inputs")
        plan = self.get_json(run_id, gate["check_plan_ref"])
        require(plan.get("contract_ref") == contract_ref and plan.get("node_contract_ref") == gate["node_contract_ref"], "bound check plan scope")
        require(plan.get("policy_ref") == gate["policy_ref"] and contract.get("policy_ref") == gate["policy_ref"], "policy pin")
        require(plan.get("profile_ref") == contract.get("guard_profile_ref"), "independent checking profile pin")
        profile = self.get_json(run_id, plan["profile_ref"])
        assigned = plan.get("mandatory_deterministic")
        require(isinstance(assigned, list) and assigned and len(set(assigned)) == len(assigned), "mandatory deterministic assignment")
        require(assigned == profile.get("mandatory_deterministic"), "mandatory deterministic profile coverage")
        deterministic = self.get_json(run_id, gate["deterministic_result_ref"])
        require(not checks.validate_schema("deterministic-check-result", deterministic), "deterministic shape")
        require(deterministic["subject_ref"] == subject and deterministic["check_plan_ref"] == gate["check_plan_ref"], "deterministic subject/plan")
        require(Counter(r["check_id"] for r in deterministic["results"]) == Counter(assigned), "missing/duplicate/unassigned deterministic finding")
        require(all(r["outcome"] == "PASS" and r["reason"].strip() and r["evidence_refs"] for r in deterministic["results"]), "mandatory deterministic nonpass/missing evidence")
        for result in deterministic["results"]:
            for ref in result["evidence_refs"]:
                self.read_bytes(run_id, ref)
        assessment = self.get_json(run_id, gate["assessment_ref"])
        context_ref = assessment.get("review_context_ref")
        require(context_ref is not None, "assessment review context absent")
        context = self.get_json(run_id, context_ref)
        require(not checks.validate_field_contract("review-context", context), "review context shape")
        require(context["subject_ref"] == subject and context["node_contract_ref"] == gate["node_contract_ref"], "review context subject/parent")
        if scope == "node":
            require(context["subnode_id"] == "requirements", "node reuses Requirements assessment")
            require(self.accepted(run_id, "requirements") == subject, "accepted internal Brief")
            prior_ref = self.acceptance_record(run_id, "requirements")
            require(prior_ref is not None, "Requirements acceptance receipt absent")
            prior_gate = self.get_json(run_id, self.get_json(run_id, prior_ref)["gate_ref"])
            require(prior_gate["assessment_ref"] == gate["assessment_ref"], "node changed accepted Requirements assessment")
            intent_receipt = self.acceptance_record(run_id, "intention")
            require(intent_receipt is not None, "Intention acceptance receipt absent")
            intent_gate = self.get_json(run_id, self.get_json(run_id, intent_receipt)["gate_ref"])
            require(gate["invocation_refs"] == intent_gate["invocation_refs"] + prior_gate["invocation_refs"], "node changed internally accepted invocation evidence")
            review_plan = self.get_json(run_id, context["check_plan_ref"])
        else:
            require(context["subnode_id"] == scope and context["contract_ref"] == contract_ref and context["check_plan_ref"] == gate["check_plan_ref"], "review context work scope")
            require(context["deterministic_result_ref"] == gate["deterministic_result_ref"], "review deterministic evidence")
            review_plan = plan
        review_profile = self.get_json(run_id, review_plan["profile_ref"])
        criteria = review_plan.get("mandatory_semantic")
        require(criteria and criteria == review_profile.get("mandatory_semantic") and criteria == context["criteria"], "protected semantic criteria coverage")
        allowed = context["input_refs"] + context["observations"] + [subject, context_ref, context["deterministic_result_ref"]]
        state = self.get_run(run_id)
        qualified = state.get("qualified", {})
        intake = qualified.get("intake", {})
        allowed += ([intake["request_ref"]] if "request_ref" in intake else []) + intake.get("source_refs", [])
        require(not checks.check_assessment(assessment, subject, context_ref, criteria, allowed), "assessment findings/identity/evidence")
        require(assessment["verdict"] in checks.ADVANCING, "semantic verdict nonadvancing")
        expected_roles = [scope, scope + ".verifier"] if scope != "node" else ["intention", "intention.verifier", "requirements", "requirements.verifier"]
        require(len(gate["invocation_refs"]) == len(expected_roles), "required work/review observations absent")
        durations, calls = [], []
        for role, ref in zip(expected_roles, gate["invocation_refs"]):
            observation = self.get_json(run_id, ref)
            require(not checks.validate_field_contract("invocation-observation", observation), "observation shape")
            require(observation["node_contract_ref"] == gate["node_contract_ref"] and observation["subnode_id"] == role, "observed parent/role")
            require(observation["observed_runtime"] and observation["outcome"] == "completed" and observation["model_calls"] == 1, "work/review completion and call count")
            duration = observation["duration_s"]
            require(isinstance(duration, (int, float)) and not isinstance(duration, bool) and math.isfinite(duration) and duration >= 0, "observed duration unavailable/invalid")
            observed_contract = self.get_json(run_id, observation["contract_ref"])
            require(not checks.validate_schema("subnode-execution-contract", observed_contract), "observed child contract shape")
            require(observed_contract["run_id"] == run_id and observed_contract["subnode_id"] == role and observed_contract["node_contract_ref"] == gate["node_contract_ref"], "observed invocation scope")
            require(observation["input_refs"] == observed_contract["input_refs"] and observation["binding_id"] == observed_contract["bindings"][0]["id"], "observed binding/input identity")
            require(duration <= observed_contract["subnode_limits"]["time_s"], "child time exceeded")
            if scope != "node":
                require(observation["output_refs"] == ([subject] if role == scope else [gate["assessment_ref"]]), "work/review output subject")
            for evidence in observation["input_refs"] + observation["output_refs"] + observation["trace_refs"]:
                self.read_bytes(run_id, evidence)
            durations.append(duration)
            calls.append(observation["model_calls"])
        require(sum(calls) <= node["node_limits"]["model_calls"] and sum(durations) <= node["node_limits"]["time_s"], "aggregate node call/time limit")
        budget_refs = list(gate["invocation_refs"])
        if scope == "requirements":
            intent_receipt = self.acceptance_record(run_id, "intention")
            require(intent_receipt is not None, "Requirements predecessor acceptance absent")
            intent_acceptance = self.get_json(run_id, intent_receipt)
            require(self.get_json(run_id, subject).get("intent_ref") == self.accepted(run_id, "intention"), "Requirements changed accepted Intent")
            budget_refs = self.get_json(run_id, intent_acceptance["gate_ref"])["invocation_refs"] + budget_refs
        configuration = self.get_json(run_id, node["configuration_ref"])
        token_budget = configuration.get("token_budget")
        if token_budget is not None:
            require(isinstance(token_budget, int) and not isinstance(token_budget, bool) and token_budget > 0, "configured token budget invalid")
            token_spend = 0
            for ref in budget_refs:
                usage = self.get_json(run_id, ref).get("usage", {})
                values = [usage.get("input_tokens"), usage.get("output_tokens")]
                require(all(isinstance(value, int) and not isinstance(value, bool) and value >= 0 for value in values), "configured token budget cannot be verified from unavailable/invalid usage")
                token_spend += sum(values)
            require(token_spend <= token_budget, "observed aggregate token limit exceeded")

    def accepted(self, run_id, scope):
        with self.connection() as con:
            row = con.execute("SELECT subject FROM acceptance WHERE run_id=? AND scope=?", (run_id, scope)).fetchone()
        return json.loads(row[0]) if row else None

    def acceptance_record(self, run_id, scope):
        with self.connection() as con:
            row = con.execute("SELECT record_ref FROM acceptance WHERE run_id=? AND scope=?", (run_id, scope)).fetchone()
        return json.loads(row[0]) if row else None

    def status_data(self, run_id):
        row = self.get_run(run_id)
        return {"schema_version": "1.0.0", "id": f"status:{run_id}:{row['revision']}",
                **{k: row[k] for k in ("client_request_id", "run_id", "revision", "stage", "status", "candidate_refs", "accepted_refs", "decision_ref", "reasons", "bundle_ref")}}
