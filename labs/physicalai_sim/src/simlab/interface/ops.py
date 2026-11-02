"""The single operation table behind every SIMLAB tool (PAS-M1-001 B09; IF-001 "Operations"; PRD SL-9.D).

The JSON-RPC service dispatches to `Service`; the Python client, the CLI and the
MCP server are generated from OPERATIONS, so all three expose the same
operations with the same inputs, outputs and typed errors.
"""
from __future__ import annotations

import json
import time
from typing import Any, Callable

from simlab.authoring import Authoring
from simlab.contracts import SimlabError
from simlab.contracts.enums import TERMINAL_RUN
from simlab.runner.core import Runner
from simlab.runner.results import build_result, fetch, query, status_of
from simlab.store import Store
from simlab.validation import validate

S_STR = {"type": "string"}
S_OBJ = {"type": "object"}
S_NUM = {"type": "number"}

OPERATIONS: dict[str, dict[str, Any]] = {
    "capability": {"doc": "List what this SIMLAB build supports, excludes and is missing (registry entries with reasons and evidence).",
                   "params": {}, "required": []},
    "validate": {"doc": "Validate an experiment and return every finding at once (empty list: valid). Never creates a run.",
                 "params": {"experiment": S_OBJ}, "required": ["experiment"]},
    "submit": {"doc": "Submit a bound experiment. Returns {run_id, experiment_id}, or {findings} and no run when it is invalid.",
               "params": {"experiment": S_OBJ}, "required": ["experiment"]},
    "status": {"doc": "Run status and attempt counts.", "params": {"run_id": S_STR}, "required": ["run_id"]},
    "wait": {"doc": "Block until the run ends or timeout_s passes; returns its status.",
             "params": {"run_id": S_STR, "timeout_s": S_NUM}, "required": ["run_id"]},
    "result": {"doc": "The full simlab-result record of a run (trials, attempts, measurements, checks, traces, provenance).",
               "params": {"run_id": S_STR}, "required": ["run_id"]},
    "query": {"doc": "Find traces, measurements and events of a run by arm, trial, time range and signal.",
              "params": {"run_id": S_STR, "arm_id": S_STR, "trial_id": S_STR, "t_start": S_NUM, "t_end": S_NUM, "signal": S_STR},
              "required": ["run_id"]},
    "fetch": {"doc": "Fetch the data of one trace reference from query (optionally a time range; decimated beyond max_rows).",
              "params": {"ref": S_STR, "t_start": S_NUM, "t_end": S_NUM, "max_rows": {"type": "integer"}}, "required": ["ref"]},
    "replay": {"doc": "Replay a run with its recorded seeds and actions (same machine and build only). Creates a new run of kind replay.",
               "params": {"run_id": S_STR}, "required": ["run_id"]},
    "cancel": {"doc": "Cancel a run: CANCELLED, the running attempt INTERRUPTED, completed trials kept.",
               "params": {"run_id": S_STR}, "required": ["run_id"]},
    "branch": {"doc": "Start a draft from a saved checkpoint (parent = the checkpoint); change it with the authoring tools, then bind and submit.",
               "params": {"checkpoint_id": S_STR, "header": S_OBJ}, "required": ["checkpoint_id"]},
    "draft_create": {"doc": "Create a draft workspace; header may hold experiment fields (objective, objective_kind, arms, design, limits, ...).",
                     "params": {"header": S_OBJ, "parent": S_OBJ}, "required": []},
    "geometry_put": {"doc": "Create or change a geometry asset: text content, base64 content, or a primitive {shape: box|cylinder|sphere, ...}.",
                     "params": {"draft_id": S_STR, "path": S_STR, "content": S_STR, "content_b64": S_STR, "primitive": S_OBJ},
                     "required": ["draft_id", "path"]},
    "collision_put": {"doc": "Create or change a collision asset: content, a primitive, or from_geometry {path, method: copy|bounding_box}.",
                      "params": {"draft_id": S_STR, "path": S_STR, "content": S_STR, "content_b64": S_STR, "primitive": S_OBJ,
                                 "from_geometry": S_OBJ}, "required": ["draft_id", "path"]},
    "model_file_put": {"doc": "Create or change an MJCF model file (may use ${name} parameters set by arms, factors or random variables).",
                       "params": {"draft_id": S_STR, "path": S_STR, "content": S_STR}, "required": ["draft_id", "path", "content"]},
    "procedure_put": {"doc": "Set the procedure: steps, initial_state, events, interventions, checkpoints.",
                      "params": {"draft_id": S_STR, "procedure": S_OBJ}, "required": ["draft_id", "procedure"]},
    "intervention_put": {"doc": "Add or replace one intervention (set_qpos, set_qvel, add_qvel, apply_force, set_ctrl, set_gravity).",
                         "params": {"draft_id": S_STR, "intervention": S_OBJ}, "required": ["draft_id", "intervention"]},
    "measurement_put": {"doc": "Add or replace one measurement (trial, pair or set scope).",
                        "params": {"draft_id": S_STR, "measurement": S_OBJ}, "required": ["draft_id", "measurement"]},
    "observation_put": {"doc": "Add or replace one recorded signal {signal, unit, frame, rate_hz}; probe=true records it as a diagnostic probe.",
                        "params": {"draft_id": S_STR, "observation": S_OBJ, "probe": {"type": "boolean"}}, "required": ["draft_id", "observation"]},
    "component_put": {"doc": "Create or change component code at a declared extension point (controller: control(); measurement: measure()). Runs confined.",
                      "params": {"draft_id": S_STR, "path": S_STR, "extension_point": S_STR, "code": S_STR},
                      "required": ["draft_id", "path", "extension_point", "code"]},
    "artifact_list": {"doc": "List a draft's artifacts with their SHA-256 and the draft header.", "params": {"draft_id": S_STR},
                      "required": ["draft_id"]},
    "artifact_get": {"doc": "Read one draft artifact.", "params": {"draft_id": S_STR, "path": S_STR}, "required": ["draft_id", "path"]},
    "artifact_delete": {"doc": "Remove one artifact from an unbound draft.", "params": {"draft_id": S_STR, "path": S_STR},
                        "required": ["draft_id", "path"]},
    "bind": {"doc": "Bind the draft into an immutable manifest and return the experiment (header fields given here override the draft's).",
             "params": {"draft_id": S_STR, "header": S_OBJ}, "required": ["draft_id"]},
}
RESERVED = {"preview": "phase 2 (PAS-M1-002)", "pilot": "phase 2 (PAS-M1-002)", "release_inspection": "phase 2 (PAS-M1-002)",
            "fresh_replication": "phase 3 (PAS-M1-011)", "pause": "phase 4 (PAS-M1-013)", "resume": "phase 4 (PAS-M1-013)",
            "stream": "phase 4 (PAS-M1-013)"}


class Service:
    def __init__(self, store: Store, runner: Runner | None = None):
        self.store = store
        self.runner = runner or Runner(store)
        self.authoring = Authoring(store)

    def call(self, op: str, params: dict | None) -> Any:
        params = dict(params or {})
        if op in RESERVED:
            raise SimlabError("E_RESERVED_OPERATION", f"{op} is reserved for {RESERVED[op]} and not provided by this build")
        spec = OPERATIONS.get(op)
        if spec is None:
            raise SimlabError("E_UNKNOWN_OPERATION", f"no operation {op!r}")
        unknown = set(params) - set(spec["params"])
        if unknown:
            raise SimlabError("E_INVALID_INPUT", f"{op} does not take {sorted(unknown)}", "/" + sorted(unknown)[0])
        missing = [p for p in spec["required"] if params.get(p) is None]
        if missing:
            raise SimlabError("E_INVALID_INPUT", f"{op} needs {missing}", "/" + missing[0])
        return getattr(self, "op_" + op)(**params)

    # ------------------------------------------------------------------ operations
    def op_capability(self):
        from simlab.registry import entries  # noqa: PLC0415

        return {"capabilities": entries(self.store), "operations": sorted(OPERATIONS), "reserved_operations": RESERVED}

    def op_validate(self, experiment):
        _exp, findings = validate(experiment, self.store)
        return {"findings": findings}

    def op_submit(self, experiment):
        return self.runner.submit(experiment)

    def op_status(self, run_id):
        return status_of(self.store, run_id)

    def op_wait(self, run_id, timeout_s=600):
        deadline = time.monotonic() + max(0.0, min(float(timeout_s), 3600.0))
        terminal = {s.value for s in TERMINAL_RUN}
        while True:
            s = status_of(self.store, run_id)
            if s["status"] in terminal or time.monotonic() >= deadline:
                return s
            time.sleep(0.1)

    def op_result(self, run_id):
        return build_result(self.store, run_id, verify=True)

    def op_query(self, run_id, arm_id=None, trial_id=None, t_start=None, t_end=None, signal=None):
        return query(self.store, run_id, arm_id=arm_id, trial_id=trial_id, t_start=t_start, t_end=t_end, signal=signal)

    def op_fetch(self, ref, t_start=None, t_end=None, max_rows=5000):
        return fetch(self.store, ref, t_start=t_start, t_end=t_end, max_rows=max_rows)

    def op_replay(self, run_id):
        return self.runner.replay(run_id)

    def op_cancel(self, run_id):
        return self.runner.cancel(run_id)

    def op_branch(self, checkpoint_id, header=None):
        cp = self.store.get_checkpoint(checkpoint_id)
        if cp is None:
            raise SimlabError("E_UNKNOWN_CHECKPOINT", f"no checkpoint {checkpoint_id}", "/checkpoint_id")
        run = self.store.run_row(cp["run_id"])
        exp = self.store.get_experiment(run["experiment_id"])
        manifest = self.store.get_manifest(exp["assets"]["manifest_id"])
        base = {k: v for k, v in exp.items() if k not in {"record", "schema_version", "experiment_id", "assets", "parent"}}
        trial = self.store.q1("SELECT arm_id FROM trials WHERE trial_id=?", (cp["trial_id"],))
        # The branch continues the checkpointed trial's arm unless the header changes the arms.
        base["arms"] = [a for a in base["arms"] if a["arm_id"] == trial["arm_id"]] or base["arms"]
        base["design"] = {**base["design"], "factors": [], "conditions": [], "replicates": 1, "episodes": 1, "comparisons": []}
        base["measurements"] = [m for m in base.get("measurements", []) if m["scope"] == "trial"]
        base["parent"] = {"checkpoint_id": checkpoint_id}
        if header:
            base.update(header)
        params = json.loads(self.store.q1("SELECT params FROM trials WHERE trial_id=?", (cp["trial_id"],))["params"])
        for a in base["arms"]:
            a["params"] = {**params, **a.get("params", {})} if a["arm_id"] == trial["arm_id"] else a.get("params", {})
        d = self.authoring.draft_create({k: v for k, v in base.items() if k in _header_fields()}, parent={"checkpoint_id": checkpoint_id})
        for art in manifest["artifacts"]:
            if art["kind"] in {"procedure", "intervention", "measurement", "observation"}:
                continue  # structured parts travel in the header and stay editable through the authoring tools
            data = self.store.get_blob(art["sha256"])
            self.authoring._put(d["draft_id"], art["path"], art["kind"], data, art.get("extension_point"))
        return {"draft_id": d["draft_id"], "parent": {"checkpoint_id": checkpoint_id}, "checkpoint": {
            "run_id": cp["run_id"], "trial_id": cp["trial_id"], "point": cp["point"], "time_s": cp["time_s"]}}

    def op_draft_create(self, header=None, parent=None):
        return self.authoring.draft_create(header, parent)

    def op_geometry_put(self, draft_id, path, content=None, content_b64=None, primitive=None):
        return self.authoring.geometry_put(draft_id, path, content, content_b64, primitive)

    def op_collision_put(self, draft_id, path, content=None, content_b64=None, primitive=None, from_geometry=None):
        return self.authoring.collision_put(draft_id, path, content, content_b64, primitive, from_geometry)

    def op_model_file_put(self, draft_id, path, content):
        return self.authoring.model_file_put(draft_id, path, content)

    def op_procedure_put(self, draft_id, procedure):
        return self.authoring.procedure_put(draft_id, procedure)

    def op_intervention_put(self, draft_id, intervention):
        return self.authoring.intervention_put(draft_id, intervention)

    def op_measurement_put(self, draft_id, measurement):
        return self.authoring.measurement_put(draft_id, measurement)

    def op_observation_put(self, draft_id, observation, probe=False):
        return self.authoring.observation_put(draft_id, observation, bool(probe))

    def op_component_put(self, draft_id, path, extension_point, code):
        return self.authoring.component_put(draft_id, path, extension_point, code)

    def op_artifact_list(self, draft_id):
        return self.authoring.artifact_list(draft_id)

    def op_artifact_get(self, draft_id, path):
        return self.authoring.artifact_get(draft_id, path)

    def op_artifact_delete(self, draft_id, path):
        return self.authoring.artifact_delete(draft_id, path)

    def op_bind(self, draft_id, header=None):
        return self.authoring.bind(draft_id, header)


def _header_fields() -> set[str]:
    from simlab.authoring import HEADER_FIELDS  # noqa: PLC0415

    return HEADER_FIELDS
