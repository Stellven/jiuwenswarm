"""Result assembly, integrity verification, query and fetch (PAS-M1-001 B04/B05; PRD SL-8).

The Result is rebuilt from the store on every read and validated against the
IF-001@r1 model. Reading verifies each completed attempt's trace files; a file
that no longer matches its recorded SHA-256 turns that attempt INVALID with
`corrupted_record` (recorded in the store), and its measurements are marked
invalid, not dropped.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from simlab.checks import anchoring as anchoring_of, evidence_level, validity
from simlab.contracts import SCHEMA_VERSION, SimlabError
from simlab.contracts.records import Result
from simlab.store import Store

FETCH_MAX_ROWS = 5000


def _sha(path: str) -> str | None:
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


def verify_integrity(store: Store, run_id: str) -> list[str]:
    damaged = []
    for a in store.q("SELECT attempt_id, status FROM attempts WHERE run_id=? AND status IN ('COMPLETED','LIMIT_REACHED')", (run_id,)):
        for tr in store.q("SELECT signal, path, sha256 FROM traces WHERE attempt_id=?", (a["attempt_id"],)):
            if _sha(tr["path"]) != tr["sha256"]:
                store.mark_corrupted(a["attempt_id"], f"trace {tr['signal']} no longer matches its recorded SHA-256")
                damaged.append(a["attempt_id"])
                break
    return damaged


def build_result(store: Store, run_id: str, *, verify: bool = True) -> dict:
    run = store.run_row(run_id)
    if verify and run["status"] in {"COMPLETED", "CANCELLED"}:
        verify_integrity(store, run_id)
    exp = store.get_experiment(run["experiment_id"])
    manifest = store.get_manifest(exp["assets"]["manifest_id"])
    units = {m["measurement_id"]: m["unit"] for m in exp.get("measurements", [])}
    checks = [{"check_id": c["check_id"], "check_kind": c["check_kind"], "required": bool(c["required"]), "status": c["status"],
               "observed": json.loads(c["observed"]), "affected_measurements": json.loads(c["affected"])}
              for c in store.q("SELECT * FROM checks WHERE run_id=? ORDER BY rowid", (run_id,))]
    failed = validity(checks, exp.get("measurements", []))
    trials, traces, ckpts = [], [], []
    corrupted_attempts = set()
    for t in store.q("SELECT * FROM trials WHERE run_id=? AND purpose='counted' ORDER BY ordinal", (run_id,)):
        atts = []
        for a in store.q("SELECT * FROM attempts WHERE trial_id=? ORDER BY started_at", (t["trial_id"],)):
            if a["invalid_reason"] == "corrupted_record":
                corrupted_attempts.add(a["attempt_id"])
            atts.append({"attempt_id": a["attempt_id"], "status": a["status"], "invalid_reason": a["invalid_reason"], "reason": a["reason"],
                         "seeds": json.loads(a["seeds"]), "started_at": a["started_at"], "ended_at": a["ended_at"], "stop": a["stop"],
                         "state_digest": a["state_digest"]})
        ms = []
        for m in store.q("SELECT * FROM measurements WHERE trial_id=? AND scope='trial' ORDER BY rowid", (t["trial_id"],)):
            bad = m["measurement_id"] in failed or m["attempt_id"] in corrupted_attempts
            note = m["note"]
            if m["attempt_id"] in corrupted_attempts:
                note = (note + "; " if note else "") + "attempt record corrupted after measurement"
            v = json.loads(m["value"])
            ms.append({"measurement_id": m["measurement_id"], "value": v, "unit": m["unit"], "attempt_id": m["attempt_id"],
                       "validity": "invalid" if bad else "valid", "note": note})
        trials.append({"trial_id": t["trial_id"], "arm_id": t["arm_id"], "condition": t["condition_id"], "replicate": t["replicate"],
                       "episode": t["episode"], "pair_id": t["pair_id"], "attempts": atts, "measurements": ms})
        for tr in store.q("SELECT * FROM traces WHERE trial_id=? ORDER BY rowid", (t["trial_id"],)):
            traces.append({"ref": tr["ref"], "trial_id": tr["trial_id"], "attempt_id": tr["attempt_id"], "arm_id": tr["arm_id"],
                           "signal": tr["signal"], "unit": tr["unit"], "n": tr["n"], "t_start": tr["t_start"], "t_end": tr["t_end"],
                           "sha256": tr["sha256"]})
    for c in store.q("SELECT * FROM checkpoints WHERE run_id=? ORDER BY rowid", (run_id,)):
        ckpts.append({"checkpoint_id": c["checkpoint_id"], "point": c["point"], "trial_id": c["trial_id"], "attempt_id": c["attempt_id"],
                      "time_s": c["time_s"], "state_sha256": c["state_sha256"]})
    cross = []
    for m in store.q("SELECT * FROM measurements WHERE run_id=? AND scope IN ('pair','set') ORDER BY rowid", (run_id,)):
        key = json.loads(m["key"])
        cross.append({"measurement_id": m["measurement_id"], "scope": m["scope"], "key": key, "value": json.loads(m["value"]),
                      "unit": m["unit"], "n": int(key.get("n", 2 if m["scope"] == "pair" else 0)),
                      "validity": "invalid" if m["measurement_id"] in failed else "valid", "note": m["note"]})
    mids = sorted({m["measurement_id"] for m in exp.get("measurements", [])} | {"predicate:" + p["predicate_id"] for p in exp.get("predicates", [])})
    mvalid = [{"measurement_id": mid, "validity": "invalid" if mid in failed else "valid", "failed_checks": failed.get(mid, [])} for mid in mids]
    first_exec = store.q1("SELECT exec FROM attempts WHERE run_id=? AND exec IS NOT NULL AND exec != '{}' ORDER BY started_at LIMIT 1", (run_id,))
    eff = json.loads(first_exec["exec"]).get("effective_config") if first_exec else None
    identity = json.loads(run["identity"] or "{}")
    status = run["status"]
    resources = json.loads(run["resources"]) if run["resources"] else None
    result = {
        "record": "simlab-result", "schema_version": SCHEMA_VERSION, "run_id": run_id, "experiment_id": run["experiment_id"],
        "manifest_sha256": manifest["manifest_sha256"], "run_kind": run["run_kind"],
        "parent": json.loads(run["parent"]) if run["parent"] else None, "replay_of": run["replay_of"],
        "status": status, "status_reason": run["status_reason"], "identity": identity,
        "hardware": json.loads(run["hardware"] or "{}"), "trials": trials, "cross_trial_measurements": cross, "checks": checks,
        "anchoring": anchoring_of(exp), "measurement_validity": mvalid, "model_calls": [], "checkpoints": ckpts, "traces": traces,
        "feasibility": exp.get("feasibility", []), "deviations": exp.get("deviations", []), "capability_gaps": [],
        "resources": resources,
        "provenance": {
            "source_revision": identity.get("source_revision"), "build_id": identity.get("build_id"), "lock_sha256": identity.get("lock_sha256"),
            "image_digest": identity.get("image_digest"),
            "dependencies": [{"name": "mujoco", "version": identity.get("engines", {}).get("mujoco")},
                             {"name": "numpy", "version": identity.get("numpy")}, {"name": "python", "version": identity.get("python")}],
            "assets": [{"path": a["path"], "kind": a["kind"], "sha256": a["sha256"]} for a in manifest["artifacts"]],
            "models": [],
            "configuration": {"resolved": exp["resolved_configuration"], "effective_engine_options": eff},
            "randomness": exp["design"]["randomness"],
            "package": {"experiment_id": run["experiment_id"], "manifest_id": manifest["manifest_id"], "manifest_sha256": manifest["manifest_sha256"]},
            "run_id": run_id, "trial_ids": [t["trial_id"] for t in trials],
            "attempt_ids": [a["attempt_id"] for t in trials for a in t["attempts"]],
            "raw_evidence": {"data_dir": str(store.root), "run_dir": str(store.runs_dir / run_id), "trace_refs": len(traces)},
            "analysis": {"measurements": "simlab.measure (primary)", "recomputation": "simlab.checks.recompute (independent)",
                         "definitions_sha256": hashlib.sha256(json.dumps(exp.get("measurements", []), sort_keys=True).encode()).hexdigest()},
        },
        "evidence_level": evidence_level(status, checks),
        "counts_as_evidence": True,
    }
    return Result.model_validate(result).model_dump(mode="json")


def status_of(store: Store, run_id: str) -> dict:
    run = store.run_row(run_id)
    counts = {r["status"]: r["n"] for r in store.q(
        "SELECT status, COUNT(*) AS n FROM attempts WHERE run_id=? AND purpose='counted' GROUP BY status", (run_id,))}
    total = store.q1("SELECT COUNT(*) AS n FROM trials WHERE run_id=? AND purpose='counted'", (run_id,))["n"]
    return {"run_id": run_id, "experiment_id": run["experiment_id"], "run_kind": run["run_kind"], "status": run["status"],
            "status_reason": run["status_reason"], "trials_started": total, "attempts_by_status": counts,
            "created_at": run["created_at"], "started_at": run["started_at"], "ended_at": run["ended_at"]}


def query(store: Store, run_id: str, *, arm_id: str | None = None, trial_id: str | None = None, t_start: float | None = None,
          t_end: float | None = None, signal: str | None = None) -> dict:
    store.run_row(run_id)
    where, args = ["run_id=?"], [run_id]
    if arm_id:
        where.append("arm_id=?"); args.append(arm_id)
    if trial_id:
        where.append("trial_id=?"); args.append(trial_id)
    if signal:
        if store.q1("SELECT 1 FROM traces WHERE run_id=? AND signal=?", (run_id, signal)) is None:
            raise SimlabError("E_UNKNOWN_SIGNAL", f"run {run_id} has no signal {signal!r}", "/signal")
        where.append("signal=?"); args.append(signal)
    out_traces = []
    for tr in store.q(f"SELECT * FROM traces WHERE {' AND '.join(where)} ORDER BY rowid", tuple(args)):
        if t_start is not None and tr["t_end"] is not None and tr["t_end"] < t_start:
            continue
        if t_end is not None and tr["t_start"] is not None and tr["t_start"] > t_end:
            continue
        n = tr["n"]
        if (t_start is not None or t_end is not None) and n:
            arr = np.load(tr["path"], mmap_mode="r", allow_pickle=False)
            t = arr[:, 0]
            mask = np.ones(len(t), dtype=bool)
            if t_start is not None:
                mask &= t >= t_start
            if t_end is not None:
                mask &= t <= t_end
            n = int(mask.sum())
        out_traces.append({"ref": tr["ref"], "trial_id": tr["trial_id"], "attempt_id": tr["attempt_id"], "arm_id": tr["arm_id"],
                           "signal": tr["signal"], "unit": tr["unit"], "kind": tr["kind"], "dim": tr["dim"], "n_in_range": n,
                           "t_start": tr["t_start"], "t_end": tr["t_end"]})
    tw, ta = ["m.run_id=?", "t.purpose='counted'"], [run_id]
    if arm_id:
        tw.append("t.arm_id=?"); ta.append(arm_id)
    if trial_id:
        tw.append("m.trial_id=?"); ta.append(trial_id)
    meas = [{"trial_id": m["trial_id"], "attempt_id": m["attempt_id"], "measurement_id": m["measurement_id"], "scope": m["scope"],
             "value": json.loads(m["value"]), "unit": m["unit"]}
            for m in store.q(f"SELECT m.* FROM measurements m JOIN trials t ON t.trial_id=m.trial_id WHERE {' AND '.join(tw)} ORDER BY m.rowid",
                             tuple(ta))] if not signal else []
    ew, ea = ["e.run_id=?", "t.purpose='counted'"], [run_id]
    if arm_id:
        ew.append("t.arm_id=?"); ea.append(arm_id)
    if trial_id:
        ew.append("e.trial_id=?"); ea.append(trial_id)
    if t_start is not None:
        ew.append("e.t>=?"); ea.append(t_start)
    if t_end is not None:
        ew.append("e.t<=?"); ea.append(t_end)
    events = [{"trial_id": e["trial_id"], "attempt_id": e["attempt_id"], "t": e["t"], "event_id": e["event_id"], "kind": e["kind"],
               "detail": json.loads(e["detail"])}
              for e in store.q(f"SELECT e.* FROM events e JOIN trials t ON t.trial_id=e.trial_id WHERE {' AND '.join(ew)} ORDER BY e.rowid",
                               tuple(ea))] if not signal else []
    return {"run_id": run_id, "filters": {"arm_id": arm_id, "trial_id": trial_id, "t_start": t_start, "t_end": t_end, "signal": signal},
            "traces": out_traces, "measurements": meas, "events": events}


def fetch(store: Store, ref: str, *, t_start: float | None = None, t_end: float | None = None, max_rows: int = FETCH_MAX_ROWS) -> dict:
    tr = store.q1("SELECT * FROM traces WHERE ref=?", (ref,))
    if tr is None:
        raise SimlabError("E_UNKNOWN_REF", f"no trace {ref!r}", "/ref")
    if _sha(tr["path"]) != tr["sha256"]:
        store.mark_corrupted(tr["attempt_id"], f"trace {tr['signal']} no longer matches its recorded SHA-256")
        raise SimlabError("E_UNKNOWN_REF", f"trace {ref!r} is corrupted (SHA-256 mismatch); its attempt is now INVALID/corrupted_record", "/ref")
    arr = np.load(tr["path"], allow_pickle=False)
    if arr.size:
        t = arr[:, 0]
        mask = np.ones(len(t), dtype=bool)
        if t_start is not None:
            mask &= t >= t_start
        if t_end is not None:
            mask &= t <= t_end
        arr = arr[mask]
    max_rows = max(1, min(int(max_rows), 200000))
    stride = max(1, -(-arr.shape[0] // max_rows)) if arr.shape[0] else 1
    rows = arr[::stride]
    cols = ["t", "geom1", "geom2", "dist", "normal_force"] if tr["kind"] == "contacts" else ["t"] + [f"v{i}" for i in range(tr["dim"])]
    return {"ref": ref, "signal": tr["signal"], "unit": tr["unit"], "kind": tr["kind"], "columns": cols, "n_total": int(arr.shape[0]),
            "stride": stride, "rows": rows.tolist(), "sha256": tr["sha256"],
            "note": "decimated: every stride-th row" if stride > 1 else "complete"}
