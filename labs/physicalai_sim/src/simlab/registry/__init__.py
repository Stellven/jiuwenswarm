"""Capability registry (PAS-M1-001 B10; ARCH Responsibilities: "Admission only by conformance results").

Static entries say what this build supports, excludes (with the reason) and is
missing (with the phase that adds it). The MuJoCo executor is `admitted` only
when F1 known-answer evidence for the current build is recorded (`simlab bench
admit`); evidence for another build does not carry over.
"""
from __future__ import annotations

from simlab import build_identity

STATIC = [
    ("engine:mujoco", "engine", "supported", "MuJoCo 3.17.0 executor; not admitted until its F1 known-answer cases pass on this build", None),
    ("engine:numerical", "engine", "missing", "numerical engine executor arrives in phase 3 (PAS-M1-004)", None),
    ("engine:drake", "engine", "missing", "second engine for cross-checks arrives in phase 3 (PAS-M1-004)", None),
    ("engine:isaac_sim", "engine", "excluded", "published minimum is an RTX 4080-class GPU; this laptop has an RTX 3050 6 GB (test plan, constraints)", None),
    ("engine:maniskill3", "engine", "excluded", "CPU-only under WSL without GPU simulation or rendering; reference only in M1 (test plan, constraints)", None),
    ("library:actuators", "library", "missing", "phase 3 (PAS-M1-005)", None),
    ("library:extra_forces", "library", "missing", "phase 3 (PAS-M1-006)", None),
    ("library:flexible_parts", "library", "missing", "phase 3 (PAS-M1-007)", None),
    ("library:solvers", "library", "missing", "phase 3 (PAS-M1-008)", None),
    ("library:frozen_policies", "library", "missing", "phase 3 (PAS-M1-009)", None),
    ("library:world_models", "library", "missing", "phase 3 (PAS-M1-010)", None),
    ("interface:models_under_test", "interface", "missing", "model interface and memory arrive in phase 3 (PAS-M1-011)", None),
    ("model:pi0.5", "model", "excluded", "needs more than 8 GB of GPU memory; M2 on the DGX Spark (test plan, constraints)", None),
    ("extension_point:scene", "extension_point", "supported", "MJCF model file per arm, templated with ${name}", None),
    ("extension_point:controller", "extension_point", "supported", "control(obs, params, ctx) component code, confined (no network, no processes, declared limits)", None),
    ("extension_point:measurement", "extension_point", "supported", "measure(traces, params) component code, confined", None),
    ("operation:preview", "operation", "missing", "phase 2 (PAS-M1-002)", None),
    ("operation:pilot", "operation", "missing", "phase 2 (PAS-M1-002)", None),
    ("operation:release_inspection", "operation", "missing", "phase 2 (PAS-M1-002)", None),
    ("operation:fresh_replication", "operation", "missing", "phase 3 (PAS-M1-011)", None),
    ("operation:pause_resume_stream", "operation", "missing", "phase 4 (PAS-M1-013)", None),
    ("checkpoint:whole_state", "state", "missing", "phase 1 saves world state, random state, pending events and action history; "
     "controllers, memory and model-call history arrive in phase 4 (PAS-M1-013)", None),
]


def entries(store) -> list[dict]:
    build = build_identity.current()["build_id"]
    rows = {r["capability"]: dict(r) for r in store.q("SELECT * FROM registry")}
    out = []
    for cap, kind, status, reason, ev in STATIC:
        r = rows.pop(cap, None)
        if r is not None:
            if r["status"] == "admitted" and r["version"] != build:
                out.append({"capability": cap, "kind": kind, "status": "supported",
                            "reason": f"admission evidence {r['evidence_ref']} is for build {str(r['version'])[:12]}, not this build {build[:12]}",
                            "evidence_ref": r["evidence_ref"]})
                continue
            out.append({"capability": cap, "kind": r["kind"], "status": r["status"], "reason": r["reason"], "evidence_ref": r["evidence_ref"]})
        else:
            out.append({"capability": cap, "kind": kind, "status": status, "reason": reason, "evidence_ref": ev})
    for cap, r in sorted(rows.items()):
        out.append({"capability": cap, "kind": r["kind"], "status": r["status"], "reason": r["reason"], "evidence_ref": r["evidence_ref"]})
    return out


def admit(store, capability: str, evidence_ref: str, passed: bool, reason: str) -> dict:
    build = build_identity.current()["build_id"]
    kind = capability.split(":", 1)[0]
    status = "admitted" if passed else "supported"
    store.set_capability(capability, kind, status, reason, evidence_ref, build)
    return {"capability": capability, "status": status, "build_id": build, "evidence_ref": evidence_ref, "reason": reason}
