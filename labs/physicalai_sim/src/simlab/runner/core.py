"""Runner and experiment core (PAS-M1-001 B05, B07, B08; PRD SL-3, SL-4, SL-7, SL-8).

Plain code that never judges. It validates, expands the design, runs every
trial attempt in a confined worker process, keeps every attempt (completed,
invalid, limit reached, interrupted, blocked), computes measurements, runs the
checks, and records results, traces, checkpoints and resources. No automatic
retries: an execution is an attempt and every attempt is recorded.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import resource
import shutil
import signal
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Any

import numpy as np

import simlab
from simlab import build_identity
from simlab.checks import (
    DEFAULT_RECOMPUTE_TOL, anchoring, control_arm_check, evidence_level, known_answer_check, recomputation_summary,
    rerun_summary, validity, watchdog_check, within,
)
from simlab.checks.recompute import recompute
from simlab.contracts import SimlabError
from simlab.contracts.enums import TERMINAL_RUN
from simlab.contracts.records import Experiment
from simlab.executors.mujoco.scene import resolve_template, resolve_value, SceneError
from simlab.measure import STANDARD_TRIAL_KINDS, pair_value, predicate, set_value, trial_value
from simlab.runner.design import expand
from simlab.store import Store, new_id, now
from simlab.validation import validate

SRC_ROOT = Path(simlab.__file__).resolve().parents[1]


def worker_env() -> dict:
    """A fixed, credential-free environment for executor workers."""
    return {"PATH": f"{Path(sys.executable).parent}:/usr/local/bin:/usr/bin:/bin", "PYTHONPATH": str(SRC_ROOT),
            "PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1", "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1", "HOME": "/tmp", "LANG": "C.UTF-8", "TMPDIR": "/tmp"}


def cpu_model() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


def hardware_inventory(data_dir: Path) -> dict:
    mem = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            k, v = line.split(":", 1)
            if k in {"MemTotal", "MemAvailable"}:
                mem[k] = int(v.split()[0]) // 1024
    except OSError:
        pass
    du = shutil.disk_usage(data_dir)
    return {"taken_at": now(), "cpu_model": cpu_model(), "threads": os.cpu_count(), "machine": platform.machine(),
            "kernel": platform.release(), "memory_total_mb": mem.get("MemTotal"), "memory_available_mb": mem.get("MemAvailable"),
            "disk_free_gb": round(du.free / 2**30, 1), "gpu": "not used (MuJoCo CPU executor)",
            "host_id": os.environ.get("SIMLAB_HOST_ID", platform.node()), "in_container": os.environ.get("SIMLAB_IN_CONTAINER") == "1"}


def run_identity() -> dict:
    b = build_identity.current()
    import mujoco  # noqa: PLC0415

    return {"simlab_version": simlab.__version__, "source_revision": os.environ.get("SIMLAB_SOURCE_REVISION", "unknown"),
            "build_id": b["build_id"], "lock_sha256": b["lock_sha256"], "image_digest": os.environ.get("SIMLAB_IMAGE_ID", "none"),
            "engines": {"mujoco": mujoco.__version__}, "numpy": np.__version__, "python": platform.python_version(),
            "host_id": os.environ.get("SIMLAB_HOST_ID", platform.node()), "cpu_model": cpu_model()}


class Cancelled(Exception):
    pass


class Runner:
    def __init__(self, store: Store, *, start: bool = True, worker_cmd: list[str] | None = None):
        self.store = store
        # Block-level tests may substitute a deterministic fake executor; BOUNDARY checks never do.
        self.worker_cmd = worker_cmd or [sys.executable, "-m", "simlab.executors.mujoco.worker"]
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._procs: dict[str, subprocess.Popen] = {}
        self._recover()
        self.thread = threading.Thread(target=self._loop, name="simlab-runner", daemon=True)
        if start:
            self.thread.start()

    # ------------------------------------------------------------------ lifecycle
    def _recover(self):
        """A previous process died with work in flight: its running attempts are INTERRUPTED, never dropped."""
        for row in self.store.q("SELECT run_id FROM runs WHERE status='RUNNING'"):
            for a in self.store.q("SELECT attempt_id FROM attempts WHERE run_id=? AND status='RUNNING'", (row["run_id"],)):
                self.store.end_attempt(a["attempt_id"], "INTERRUPTED", reason="runner process ended during the attempt", stop="interrupted")
            self.store.set_run(row["run_id"], status="FAILED", status_reason="runner process ended during the run (infrastructure)",
                               ended_at=now())

    def close(self):
        self._stop.set()
        self._wake.set()
        for p in list(self._procs.values()):
            _kill(p)

    def _loop(self):
        while not self._stop.is_set():
            row = self.store.q1("SELECT run_id FROM runs WHERE status='QUEUED' ORDER BY created_at LIMIT 1")
            if row is None:
                self._wake.wait(0.5)
                self._wake.clear()
                continue
            try:
                self.execute(row["run_id"])
            except Exception:  # infrastructure failure is recorded, never hidden
                self.store.set_run(row["run_id"], status="FAILED", ended_at=now(),
                                   status_reason="infrastructure failure: " + traceback.format_exc()[-1500:])

    # ------------------------------------------------------------------ submission
    def submit(self, experiment: dict, *, run_kind: str = "original", replay_of: str | None = None) -> dict:
        exp, findings = validate(experiment, self.store)
        if findings:
            return {"findings": findings}
        body = exp.model_dump(mode="json")
        body["experiment_id"] = body.get("experiment_id") or self._content_id(body)
        self.store.put_experiment(body)
        run_id = self.store.create_run(body["experiment_id"], run_kind, parent=body.get("parent"), replay_of=replay_of,
                                       identity=run_identity())
        self._wake.set()
        return {"run_id": run_id, "experiment_id": body["experiment_id"]}

    def _content_id(self, body: dict) -> str:
        from simlab.authoring import experiment_id_for  # noqa: PLC0415

        m = self.store.get_manifest(body["assets"]["manifest_id"])
        return experiment_id_for(body, m["artifacts"])

    def replay(self, run_id: str) -> dict:
        row = self.store.run_row(run_id)
        if row["status"] not in {"COMPLETED", "CANCELLED"}:
            raise SimlabError("E_NOT_REPLAYABLE", f"run {run_id} is {row['status']}; only an ended run can be replayed")
        orig, cur = json.loads(row["identity"] or "{}"), run_identity()
        diff = {k: (orig.get(k), cur.get(k)) for k in ("build_id", "image_digest", "cpu_model", "host_id") if orig.get(k) != cur.get(k)}
        if diff:
            raise SimlabError("E_NOT_REPLAYABLE", f"exact replay is claimed only on the same machine and build; differs: {diff}")
        run = self.store.create_run(row["experiment_id"], "replay", parent=json.loads(row["parent"]) if row["parent"] else None,
                                    replay_of=run_id, identity=cur)
        self._wake.set()
        return {"run_id": run, "replay_of": run_id, "experiment_id": row["experiment_id"]}

    def cancel(self, run_id: str) -> dict:
        row = self.store.run_row(run_id)
        if row["status"] in {s.value for s in TERMINAL_RUN}:
            raise SimlabError("E_ALREADY_TERMINAL", f"run {run_id} already ended {row['status']}")
        with self.store.tx() as db:
            db.execute("UPDATE runs SET cancel_requested=1 WHERE run_id=?", (run_id,))
            n = db.execute("UPDATE runs SET status='CANCELLED', status_reason='cancelled while queued', ended_at=? "
                           "WHERE run_id=? AND status='QUEUED'", (now(), run_id)).rowcount
        if n:
            self._write_result(run_id)
        else:
            p = self._procs.get(run_id)
            if p is not None:
                _kill(p)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            st = self.store.run_row(run_id)["status"]
            if st in {s.value for s in TERMINAL_RUN}:
                return {"run_id": run_id, "status": st}
            time.sleep(0.05)
        return {"run_id": run_id, "status": self.store.run_row(run_id)["status"]}

    # ------------------------------------------------------------------ execution
    def execute(self, run_id: str) -> None:
        st = self.store
        row = st.run_row(run_id)
        if row["status"] != "QUEUED":
            return
        exp_body = st.get_experiment(row["experiment_id"])
        exp = Experiment.model_validate(exp_body)
        manifest = st.get_manifest(exp.assets.manifest_id)
        t0, ru0 = time.monotonic(), resource.getrusage(resource.RUSAGE_SELF)
        run_dir = st.runs_dir / run_id
        disk0 = _dir_bytes(run_dir)
        st.set_run(run_id, status="RUNNING", started_at=now(), hardware=hardware_inventory(st.root))
        ctx = {"run_id": run_id, "exp": exp, "exp_body": exp_body, "manifest": manifest, "worker_cpu": 0.0, "worker_peak_mb": 0.0,
               "worker_write": 0, "replay_of": row["replay_of"], "run_kind": row["run_kind"]}
        ctx["paths"] = {a["path"]: str(st.blob_path(a["sha256"])) for a in manifest["artifacts"]}
        ctx["kinds"] = {a["path"]: a["kind"] for a in manifest["artifacts"]}
        restore = None
        if exp.parent is not None and exp.parent.checkpoint_id:
            cp = st.get_checkpoint(exp.parent.checkpoint_id)
            restore = {"meta": str(st.blob_path(cp["files"]["meta.json"])), "state": str(st.blob_path(cp["files"]["state.npy"])),
                       "actions": str(st.blob_path(cp["files"]["actions.npy"])), "checkpoint_id": cp["checkpoint_id"]}
        ctx["restore"] = restore
        replay_src = self._replay_sources(row["replay_of"]) if row["run_kind"] == "replay" else {}
        blocked = self._blocked_arms(exp)
        cancelled = False
        trials = expand(exp)
        try:
            for t in trials:
                if st.run_row(run_id)["cancel_requested"]:
                    raise Cancelled()
                t["trial_id"] = f"tr-{run_id[4:16]}-{t['ordinal']:05d}"
                st.add_trial(run_id, t)
                if t["arm_id"] in blocked:
                    st.blocked_attempt(run_id, t["trial_id"], t["seeds"], blocked[t["arm_id"]])
                    continue
                self._attempt(ctx, t, replay_actions=replay_src.get(t["ordinal"]))
        except Cancelled:
            cancelled = True
        status = "CANCELLED" if cancelled else "COMPLETED"
        if not cancelled:
            self._cross_trial(ctx)
            self._checks(ctx, trials)
        ru1 = resource.getrusage(resource.RUSAGE_SELF)
        resources = {"wall_s": round(time.monotonic() - t0, 3),
                     "cpu_s": round(ctx["worker_cpu"] + (ru1.ru_utime - ru0.ru_utime) + (ru1.ru_stime - ru0.ru_stime), 3),
                     "peak_ram_mb": round(max(ctx["worker_peak_mb"], ru1.ru_maxrss / 1024), 1), "gpu": "none", "peak_vram_mb": None,
                     "disk_written_mb": round(max(_dir_bytes(run_dir) - disk0, ctx["worker_write"]) / 2**20, 3)}
        st.set_run(run_id, status=status, ended_at=now(), resources=resources,
                   status_reason="cancelled during the run" if cancelled else "")
        self._write_result(run_id)

    def _write_result(self, run_id: str) -> None:
        from simlab.runner.results import build_result  # noqa: PLC0415

        res = build_result(self.store, run_id, verify=True)
        p = self.store.runs_dir / run_id / "result.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(res, indent=1, sort_keys=True))

    def _blocked_arms(self, exp: Experiment) -> dict[str, str]:
        out = {}
        for fe in exp.feasibility:
            if fe.status.value == "missing":
                arms = fe.affected_arms or [a.arm_id for a in exp.arms]
                for a in arms:
                    out.setdefault(a, f"missing dependency {fe.dependency_id} ({fe.dependency_kind}): {fe.reason}")
        return out

    def _replay_sources(self, run_id: str) -> dict[int, str]:
        out = {}
        for r in self.store.q("SELECT t.ordinal, a.exec FROM trials t JOIN attempts a ON a.trial_id=t.trial_id "
                              "WHERE t.run_id=? AND t.purpose='counted' ORDER BY a.started_at", (run_id,)):
            info = json.loads(r["exec"] or "{}")
            if info.get("actions_file"):
                out[r["ordinal"]] = info["actions_file"]
        return out

    # ------------------------------------------------------------------ one attempt
    def job_for(self, ctx: dict, t: dict, out_dir: Path, *, config_extra: dict | None = None, params_extra: dict | None = None) -> dict:
        exp: Experiment = ctx["exp"]
        arm = next(a for a in exp.arms if a.arm_id == t["arm_id"])
        params = {**t["params"], **(params_extra or {})}
        scene = next(c for c in arm.components if c.extension_point == "scene")
        xml = Path(ctx["paths"][scene.artifact]).read_text()
        xml = resolve_template(xml, params)
        assets = {p: path for p, path in ctx["paths"].items() if ctx["kinds"][p] in {"geometry", "collision", "model_file"} and p != scene.artifact}
        codes = {p: path for p, path in ctx["paths"].items() if ctx["kinds"][p] == "component"}
        cfg = {**exp.resolved_configuration.model_dump(mode="json"), **t.get("config", {}), **(config_extra or {})}
        proc = exp.procedure
        bounds_t, acc = {}, 0.0
        for s in proc.steps:
            acc += s.duration_s
            bounds_t[s.step_id] = acc
        ivs = []
        for iv in proc.interventions:
            ivs.append({**iv.model_dump(mode="json"), "at_s": float(resolve_value(iv.at_s, params)),
                        "value": resolve_value(iv.value, params)})
        ist = proc.initial_state.model_dump(mode="json")
        for field in ("qpos", "qvel"):
            ist[field] = {j: resolve_value(v, params) for j, v in ist[field].items()}
        cps = [{"checkpoint_point_id": c.checkpoint_point_id,
                "time_s": float(c.time_s) if c.time_s is not None else bounds_t[c.step_end]} for c in proc.checkpoints]
        ctl = next((c for c in arm.components if c.extension_point == "controller"), None)
        mcomps = [{"measurement_id": m.measurement_id, "artifact": m.definition.artifact,
                   "params": next((c.params for c in arm.components if c.artifact == m.definition.artifact), {})}
                  for m in exp.measurements if m.definition.kind == "component"]
        return {"out_dir": str(out_dir), "model_xml": xml, "assets": assets, "codes": codes, "config": cfg,
                "trace_signals": [s.model_dump(mode="json") for s in exp.trace_signals],
                "probes": [s.model_dump(mode="json") for s in exp.probes],
                "steps": [s.model_dump(mode="json") for s in proc.steps], "initial_state": ist, "interventions": ivs,
                "events": [e.model_dump(mode="json") for e in proc.events], "checkpoints": cps,
                "limits": exp.limits.model_dump(mode="json"),
                "controller": {"artifact": ctl.artifact, "params": ctl.params} if ctl else None,
                "measurement_components": mcomps, "rng_seed": t["seeds"]["rng"], "params": params}

    def _attempt(self, ctx: dict, t: dict, *, purpose: str = "counted", replay_actions: str | None = None,
                 config_extra: dict | None = None, params_extra: dict | None = None) -> dict:
        st, run_id = self.store, ctx["run_id"]
        attempt_id = st.start_attempt(run_id, t["trial_id"], t["seeds"], purpose)
        out_dir = st.runs_dir / run_id / t["trial_id"] / attempt_id
        try:
            job = self.job_for(ctx, t, out_dir, config_extra=config_extra, params_extra=params_extra)
        except (SceneError, KeyError, ValueError, TypeError) as e:
            reason = getattr(e, "code", type(e).__name__) + f": {e}"
            st.end_attempt(attempt_id, "INVALID", invalid_reason="invalid_state_or_action_delivery", reason=reason, stop="setup")
            return {"attempt_id": attempt_id, "status": "INVALID", "measurements": {}}
        if t.get("rv_outside_bounds"):
            used_by_iv = any(isinstance(iv.get("value"), str) or isinstance(iv.get("at_s"), str)
                             for iv in [i.model_dump() for i in ctx["exp"].procedure.interventions])
            st.end_attempt(attempt_id, "INVALID",
                           invalid_reason="incorrect_intervention" if used_by_iv else "invalid_state_or_action_delivery",
                           reason=f"random variables {t['rv_outside_bounds']} sampled outside their admissible bounds; not applied", stop="setup")
            return {"attempt_id": attempt_id, "status": "INVALID", "measurements": {}}
        if ctx.get("restore"):
            job["restore"] = ctx["restore"]
        if replay_actions:
            job["replay_actions"] = replay_actions
        res, killed = self._spawn(ctx, job)
        if killed == "cancel":
            st.end_attempt(attempt_id, "INTERRUPTED", reason="run cancelled during the attempt", stop="cancel")
            raise Cancelled()
        if res is None or res.get("status") in {"WORKER_ERROR", "WORKER_EXIT"}:
            if res is not None and "confinement" in (res.get("reason") or ""):
                st.end_attempt(attempt_id, "INTERRUPTED", reason=res.get("reason", ""), stop="worker_error")
                raise RuntimeError("worker confinement could not be installed: " + res.get("reason", ""))
            why = killed or (res or {}).get("reason") or "worker ended without a result"
            status = "LIMIT_REACHED" if killed == "wall" else "INTERRUPTED"
            st.end_attempt(attempt_id, status, reason=why, stop="limit:max_wall_s" if killed == "wall" else "worker_exit")
            return {"attempt_id": attempt_id, "status": status, "measurements": {}}
        status, invalid, reason = res["status"], res.get("invalid_reason"), res.get("reason", "")
        # integrity: every trace file must still hash to what the worker wrote
        bad = [tr["signal"] for tr in res.get("traces", []) if _sha(tr["file"]) != tr["sha256"]]
        if bad and status != "INVALID":
            status, invalid, reason = "INVALID", "corrupted_record", f"trace files changed after writing: {bad}"
        arm_id = t["arm_id"]
        for tr in res.get("traces", []):
            st.add_trace({"ref": f"{attempt_id}:{tr['signal']}", "run_id": run_id, "trial_id": t["trial_id"], "attempt_id": attempt_id,
                          "arm_id": arm_id, "signal": tr["signal"], "unit": tr.get("unit", ""), "path": tr["file"], "sha256": tr["sha256"],
                          "n": tr["n"], "dim": tr["dim"], "t_start": tr["t_start"], "t_end": tr["t_end"], "kind": tr.get("kind", "signal")})
        if res.get("events"):
            st.add_events(run_id, t["trial_id"], attempt_id, res["events"])
        for cp in res.get("checkpoints", []):
            files = {}
            for name in ("meta.json", "state.npy", "actions.npy"):
                data = Path(cp["dir"], name).read_bytes()
                files[name] = st.put_blob(data)
            st.add_checkpoint({"checkpoint_id": new_id("cp"), "run_id": run_id, "trial_id": t["trial_id"], "attempt_id": attempt_id,
                               "point": cp["point"], "time_s": cp["time_s"], "state_sha256": cp["state_sha256"], "files": files,
                               "model_sha256": res["model_sha256"], "meta": {"step_index": cp["step_index"], "arm_id": arm_id}})
        values: dict[str, Any] = {}
        if status in {"COMPLETED", "LIMIT_REACHED"} and purpose != "check_rerun_failed":
            values, missing = self._trial_measurements(ctx, res)
            if missing and status == "COMPLETED":
                status, invalid = "INVALID", "missing_required_observation"
                reason = f"required measurements without an observation: {missing}"
            rows = [{"run_id": run_id, "trial_id": t["trial_id"], "attempt_id": attempt_id, "measurement_id": mid, "scope": "trial",
                     "value": v, "unit": u, "note": "" if status == "COMPLETED" else f"attempt {status}",
                     "source": "primary" if purpose == "counted" else purpose}
                    for mid, (v, u) in values.items()]
            if status == "INVALID":
                rows = []
                values = {}
            if rows:
                st.add_measurements(rows)
        info = {k: res.get(k) for k in ("stop", "steps", "sim_time_s", "effective_config", "model_sha256", "state_digest",
                                        "suffix_digests", "restored", "replayed_actions", "model_overrides", "worker_resources")}
        info["actions_file"] = (res.get("actions") or {}).get("file")
        info["actions_sha256"] = (res.get("actions") or {}).get("sha256")
        info["confinement"] = res.get("confinement")
        st.end_attempt(attempt_id, status, invalid_reason=invalid if status == "INVALID" else None, reason=reason,
                       stop=res.get("stop"), state_digest=res.get("state_digest"), exec_info=info)
        return {"attempt_id": attempt_id, "status": status, "measurements": {k: v for k, (v, _u) in values.items()},
                "state_digest": res.get("state_digest"), "suffix_digests": res.get("suffix_digests")}

    def _spawn(self, ctx: dict, job: dict) -> tuple[dict | None, str | None]:
        Path(job["out_dir"]).mkdir(parents=True, exist_ok=True)
        proc = subprocess.Popen(list(self.worker_cmd), stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=worker_env(), start_new_session=True, cwd="/tmp",
                                text=True)
        self._procs[ctx["run_id"]] = proc
        out: dict = {}

        def feed():
            try:
                o, e = proc.communicate(json.dumps(job))
                out["stdout"], out["stderr"] = o, e
            except Exception as exc:  # pragma: no cover
                out["error"] = repr(exc)
        th = threading.Thread(target=feed, daemon=True)
        th.start()
        deadline = time.monotonic() + float(job["limits"]["max_wall_s"]) + 60.0
        killed = None
        try:
            while th.is_alive():
                th.join(0.05)
                if not th.is_alive():
                    break
                if self.store.run_row(ctx["run_id"])["cancel_requested"]:
                    _kill(proc)
                    killed = "cancel"
                elif time.monotonic() > deadline:
                    _kill(proc)
                    killed = "wall"
            th.join(5)
        finally:
            self._procs.pop(ctx["run_id"], None)
        if killed == "cancel":
            return None, "cancel"
        res = None
        lines = (out.get("stdout") or "").strip().splitlines()
        if lines:
            try:
                res = json.loads(lines[-1])
            except json.JSONDecodeError:
                res = None
        if res is None:
            tail = (out.get("stderr") or "")[-800:]
            return {"status": "WORKER_EXIT", "reason": f"worker exited {proc.returncode} without a result; "
                    f"stderr: {tail}{'; ' + out['error'] if out.get('error') else ''}"}, killed
        wr = res.get("worker_resources") or {}
        ctx["worker_cpu"] += float(wr.get("cpu_s") or 0)
        ctx["worker_peak_mb"] = max(ctx["worker_peak_mb"], float(wr.get("peak_rss_mb") or 0))
        ctx["worker_write"] += int(wr.get("write_bytes") or 0)
        return res, killed

    def _trial_measurements(self, ctx: dict, res: dict) -> tuple[dict, list[str]]:
        exp: Experiment = ctx["exp"]
        traces = {tr["signal"]: np.load(tr["file"], allow_pickle=False) for tr in res.get("traces", []) if tr.get("kind") == "signal"}
        events = res.get("events", [])
        out, missing = {}, []
        for m in exp.measurements:
            if m.scope.value != "trial":
                continue
            d = m.definition.model_dump(mode="json")
            if d["kind"] == "component":
                v = res.get("component_measurements", {}).get(m.measurement_id)
            else:
                try:
                    v = trial_value(d, traces, events)
                except (ValueError, IndexError, np.linalg.LinAlgError, FloatingPointError):
                    v = None
            if v is not None and not np.isfinite(v):
                v = None
            out[m.measurement_id] = (v, m.unit)
            if v is None and m.required:
                missing.append(m.measurement_id)
        for p in exp.predicates:
            v = out.get(p.measurement_id, (None, ""))[0]
            out["predicate:" + p.predicate_id] = (predicate(p.op, v, p.value), "bool")
        return out, missing

    # ------------------------------------------------------------------ after the trials
    def _final_rows(self, run_id: str) -> list[dict]:
        """Counted trials with their last attempt and trial-scope measurement values."""
        rows = []
        for t in self.store.q("SELECT * FROM trials WHERE run_id=? AND purpose='counted' ORDER BY ordinal", (run_id,)):
            a = self.store.q1("SELECT * FROM attempts WHERE trial_id=? ORDER BY started_at DESC LIMIT 1", (t["trial_id"],))
            vals = {r["measurement_id"]: json.loads(r["value"]) for r in self.store.q(
                "SELECT measurement_id, value FROM measurements WHERE attempt_id=? AND scope='trial'", (a["attempt_id"],))} if a else {}
            rows.append({**dict(t), "condition": t["condition_id"], "final_status": a["status"] if a else None,
                         "attempt": dict(a) if a else None, "values": vals})
        return rows

    def _cross_trial(self, ctx: dict) -> None:
        exp: Experiment = ctx["exp"]
        rows = self._final_rows(ctx["run_id"])
        out = []
        for m in exp.measurements:
            d = m.definition
            if m.scope.value == "pair":
                pairs: dict[str, dict] = {}
                for r in rows:
                    if r["pair_id"]:
                        pairs.setdefault(r["pair_id"], {"condition": r["condition"]})[r["arm_id"]] = r["values"].get(d.of)
                for pid, p in sorted(pairs.items()):
                    v = pair_value(d.model_dump(), p.get(d.arms[0]), p.get(d.arms[1]))
                    out.append({"run_id": ctx["run_id"], "measurement_id": m.measurement_id, "scope": "pair", "value": v, "unit": m.unit,
                                "key": json.dumps({"pair_id": pid, "condition": p["condition"], "arms": d.arms}, sort_keys=True),
                                "note": "" if v is not None else "a paired trial has no value"})
            elif m.scope.value == "set":
                groups: dict[tuple, list] = {}
                for r in rows:
                    if d.arms and r["arm_id"] not in d.arms:
                        continue
                    key = (r["arm_id"], r["condition"] if d.by_condition else "*")
                    groups.setdefault(key, []).append(r["values"].get(d.of))
                for (arm, cond), vals in sorted(groups.items()):
                    v, n = set_value(d.model_dump(), vals)
                    out.append({"run_id": ctx["run_id"], "measurement_id": m.measurement_id, "scope": "set", "value": v, "unit": m.unit,
                                "key": json.dumps({"arm_id": arm, "condition": cond, "n": n}, sort_keys=True), "note": ""})
        if out:
            self.store.add_measurements(out)

    def _checks(self, ctx: dict, trials: list[dict]) -> None:
        st, run_id, exp = self.store, ctx["run_id"], ctx["exp"]
        rows = self._final_rows(run_id)
        attempts = [dict(a) for a in st.q("SELECT * FROM attempts WHERE run_id=? AND purpose='counted'", (run_id,))]
        checks = [watchdog_check(attempts)]
        values = [{"measurement_id": mid, "value": v, "arm_id": r["arm_id"], "condition": r["condition"], "trial_id": r["trial_id"]}
                  for r in rows for mid, v in r["values"].items()]
        decls = [c.model_dump(mode="json") for c in exp.checks]
        for c in decls:
            if c["check_kind"] == "known_answer":
                checks.append(known_answer_check(c, values))
            elif c["check_kind"] == "control_arm":
                checks.append(control_arm_check(c, rows))
        if ctx["run_kind"] == "replay":
            for c in decls:
                if c["check_kind"] == "rerun":
                    checks.append({"check_id": c["check_id"], "check_kind": "rerun", "required": False, "status": "not_run",
                                   "observed": {"note": "reruns are not repeated in a replay; see the original run"}, "affected_measurements": []})
        else:
            for c in decls:
                if c["check_kind"] == "rerun":
                    checks.append(self._rerun(ctx, c, rows))
        rec = next((c for c in decls if c["check_kind"] == "recomputation"),
                   {"check_id": "recomputation", "check_kind": "recomputation", "required": True, "tolerance": DEFAULT_RECOMPUTE_TOL,
                    "measurements": []})
        checks.append(self._recompute(ctx, rec))
        if ctx["run_kind"] == "replay":
            checks.append(self._replay_identity(run_id, ctx["replay_of"]))
        for c in checks:
            st.put_check(run_id, c)

    def _rerun(self, ctx: dict, decl: dict, rows: list[dict]) -> dict:
        exp: Experiment = ctx["exp"]
        n = int(decl.get("samples_per_arm", 5))
        mids = [m.measurement_id for m in exp.measurements if m.scope.value == "trial"]
        samples = []
        for arm in exp.arms:
            done = [r for r in rows if r["arm_id"] == arm.arm_id and r["final_status"] == "COMPLETED"][:n]
            for k, r in enumerate(done):
                for v in decl["variations"]:
                    for val in v["values"]:
                        cfg, par = {}, {}
                        if v["setting"].startswith("config."):
                            cfg[v["setting"][7:]] = val
                        else:
                            par[v["setting"][6:]] = val
                        trial = {"trial_id": f"{r['trial_id']}.rr{len(samples):03d}", "ordinal": 100000 + len(samples), "purpose": "check",
                                 "arm_id": r["arm_id"], "condition": r["condition"], "replicate": r["replicate"], "episode": r["episode"],
                                 "pair_id": r["pair_id"], "seeds": json.loads(r["seeds"]), "params": json.loads(r["params"]),
                                 "config": {}, "check_id": decl["check_id"]}
                        trial["config"] = {**_trial_config(exp, r["condition"])}
                        self.store.add_trial(ctx["run_id"], trial)
                        res = self._attempt(ctx, trial, purpose="check", config_extra=cfg, params_extra=par)
                        samples.append({"trial_id": r["trial_id"], "rerun_trial_id": trial["trial_id"], "arm_id": r["arm_id"],
                                        "variation": {"setting": v["setting"], "value": val},
                                        "attempt": {"attempt_id": res["attempt_id"], "status": res["status"]},
                                        "original": {m: r["values"].get(m) for m in mids}, "rerun": {m: res["measurements"].get(m) for m in mids}})
        return rerun_summary(decl, samples, mids)

    def _recompute(self, ctx: dict, decl: dict) -> dict:
        st, exp = self.store, ctx["exp"]
        tol = decl.get("tolerance") or DEFAULT_RECOMPUTE_TOL
        want = set(decl.get("measurements") or [])
        defs = {m.measurement_id: m.definition.model_dump(mode="json") for m in exp.measurements
                if m.scope.value == "trial" and m.definition.kind in STANDARD_TRIAL_KINDS and (not want or m.measurement_id in want)}
        rows = []
        for r in st.q("SELECT m.trial_id, m.attempt_id, m.measurement_id, m.value FROM measurements m JOIN trials t ON t.trial_id=m.trial_id "
                      "WHERE m.run_id=? AND m.scope='trial' AND t.purpose='counted'", (ctx["run_id"],)):
            if r["measurement_id"] not in defs:
                continue
            files = {tr["signal"]: tr["path"] for tr in st.q("SELECT signal, path FROM traces WHERE attempt_id=?", (r["attempt_id"],))}
            events = [{"t": e["t"], "event_id": e["event_id"]} for e in st.q("SELECT t, event_id FROM events WHERE attempt_id=?", (r["attempt_id"],))]
            primary = json.loads(r["value"])
            try:
                again = recompute(defs[r["measurement_id"]], files, events)
            except Exception as exc:  # a recomputation that cannot run is a disagreement, reported
                again = None
                rows.append({"trial_id": r["trial_id"], "attempt_id": r["attempt_id"], "measurement_id": r["measurement_id"],
                             "primary": primary, "recomputed": None, "agree": False, "error": repr(exc)[:200]})
                continue
            rows.append({"trial_id": r["trial_id"], "attempt_id": r["attempt_id"], "measurement_id": r["measurement_id"],
                         "primary": primary, "recomputed": again, "agree": within(primary, again, tol)})
        return recomputation_summary(decl, rows)

    def _replay_identity(self, run_id: str, orig_id: str) -> dict:
        a = {r["ordinal"]: r for r in self._final_rows(orig_id)}
        b = {r["ordinal"]: r for r in self._final_rows(run_id)}
        diffs = []
        for k in sorted(set(a) | set(b)):
            ra, rb = a.get(k), b.get(k)
            if ra is None or rb is None:
                diffs.append({"ordinal": k, "difference": "trial missing"})
                continue
            da, db = (ra["attempt"] or {}).get("state_digest"), (rb["attempt"] or {}).get("state_digest")
            if da != db or ra["final_status"] != rb["final_status"]:
                diffs.append({"ordinal": k, "difference": "state trajectory", "original": da, "replay": db})
            for mid in sorted(set(ra["values"]) | set(rb["values"])):
                va, vb = ra["values"].get(mid), rb["values"].get(mid)
                if va != vb:
                    diffs.append({"ordinal": k, "difference": f"measurement {mid}", "original": va, "replay": vb})
        return {"check_id": "replay_identity", "check_kind": "replay_identity", "required": True, "status": "fail" if diffs else "pass",
                "observed": {"replay_of": orig_id, "rule": "bitwise-equal per-step state digests (time, qpos, qvel, act, qacc_warmstart) "
                             "and equal measurement values, trial by trial", "trials_compared": len(b), "differences": diffs[:50]},
                "affected_measurements": sorted({d["difference"][12:] for d in diffs if d["difference"].startswith("measurement ")})}


def _trial_config(exp: Experiment, condition: str) -> dict:
    from simlab.validation import conditions_of, split_settings  # noqa: PLC0415

    for cid, settings in conditions_of(exp.design)[0]:
        if cid == condition:
            return split_settings(settings)[1]
    return {}


def _kill(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        try:
            proc.kill()
        except ProcessLookupError:
            pass


def _sha(path: str) -> str | None:
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


def _dir_bytes(p: Path) -> int:
    if not p.exists():
        return 0
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
