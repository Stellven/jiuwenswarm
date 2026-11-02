"""MuJoCo executor worker: runs exactly one trial attempt in a confined process (B06).

    python -m simlab.executors.mujoco.worker < job.json  > result.json

The runner writes a job (resolved model, configuration, procedure, signals,
limits, seeds, optional restore or replay payload) to stdin; the worker installs
confinement (sandbox.install) before compiling the model or loading component
code, runs the trial, writes traces and checkpoints into the job's output
directory and prints one JSON result line. It never judges: it reports what
happened (COMPLETED, INVALID with one of the six reasons, LIMIT_REACHED).
"""
from __future__ import annotations

import builtins
import hashlib
import json
import math
import signal
import sys
import time
import traceback
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import numpy.linalg  # noqa: F401  (pre-loaded before confinement)
import mujoco

from simlab.executors.mujoco import sandbox
from simlab.executors.mujoco.scene import (
    SceneError, apply_config, compile_model, contact_rows, finite, model_sha256, parse_signal, resolve_target,
)

STATE_SPEC = mujoco.mjtState.mjSTATE_INTEGRATION


class Stop(Exception):
    def __init__(self, status: str, stop: str, reason: str = "", invalid_reason: str | None = None):
        super().__init__(reason or stop)
        self.status, self.stop, self.reason, self.invalid_reason = status, stop, reason, invalid_reason


class CpuLimit(Exception):
    pass


def _on_xcpu(signum, frame):
    raise CpuLimit()


def safe(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in name)


def save_npy(path: Path, arr: np.ndarray) -> str:
    with path.open("wb") as fh:
        np.save(fh, np.ascontiguousarray(arr), allow_pickle=False)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_component(code: str, path: str, entry: str):
    ns = {"__name__": "simlab_component", "__file__": path, "__builtins__": builtins}
    exec(compile(code, path, "exec"), ns)  # confined: seccomp, rlimits and the audit hook are in force
    fn = ns.get(entry)
    if not callable(fn):
        raise Stop("INVALID", "component", f"component {path} defines no callable {entry}()", "invalid_state_or_action_delivery")
    return fn


def state_bytes(d: mujoco.MjData) -> bytes:
    return (np.array([d.time]).tobytes() + d.qpos.tobytes() + d.qvel.tobytes() + d.act.tobytes()
            + d.qacc_warmstart.tobytes())


class Trial:
    def __init__(self, job: dict, assets: dict[str, bytes], codes: dict[str, str], restore: dict | None,
                 replay_actions: np.ndarray | None):
        self.job, self.codes = job, codes
        self.out = Path(job["out_dir"])
        self.t_wall0 = time.monotonic()
        traces = job.get("trace_signals", []) + job.get("probes", [])
        need_energy = any(t["signal"].startswith("energy:") for t in traces) or bool(job["limits"]["watchdog"].get("max_energy_growth"))
        self.model = compile_model(job["model_xml"], assets)
        self.model_sha = model_sha256(job["model_xml"], assets)
        self.effective = apply_config(self.model, job["config"], need_energy=need_energy)
        self.m, self.d = self.model, mujoco.MjData(self.model)
        self.dt = float(self.m.opt.timestep)
        self.rng = np.random.default_rng(int(job["rng_seed"]))
        self.signals = []
        seen = set()
        for t in traces:
            if t["signal"] in seen:
                continue
            seen.add(t["signal"])
            sig = parse_signal(self.m, t["signal"])
            every = 1 if not t.get("rate_hz") else max(1, int(round(1.0 / (float(t["rate_hz"]) * self.dt))))
            self.signals.append((sig, every, t.get("unit", "")))
        self.buf = {s.name: [] for s, _, _ in self.signals}
        self.contacts: list[list[float]] = []
        self.events: list[dict] = []
        self.actions: list[np.ndarray] = []
        self.applied: list[str] = []
        self.forces: list[tuple[int, int]] = []  # (body, until_index)
        self.ctx_state: dict = {}
        self.denials_seen = 0
        self.model_overrides: dict = {}
        # procedure in step indices
        steps = job["steps"]
        bounds, acc = [], 0.0
        for s in steps:
            acc += float(s["duration_s"])
            bounds.append((int(round(acc / self.dt)), s))
        self.boundaries = bounds
        total = int(round(acc / self.dt))
        cap = int(round(float(job["limits"]["max_sim_time_s"]) / self.dt))
        self.n_total = min(total, cap)
        self.horizon_limited = total > cap
        self.ivs = sorted(({**iv, "index": int(round(float(iv["at_s"]) / self.dt))} for iv in job.get("interventions", [])),
                          key=lambda x: (x["index"], x["intervention_id"]))
        self.cps = {int(round(float(c["time_s"]) / self.dt)): c for c in job.get("checkpoints", [])}
        self.events_decl = job.get("events", [])
        self.contact_state = {e["event_id"]: False for e in self.events_decl if e["kind"] in {"contact_begin", "contact_end"}}
        self.threshold_prev: dict = {}
        self.controller = None
        self.control_every = int(job["config"].get("control_every_steps", 1))
        if job.get("controller"):
            c = job["controller"]
            self.controller = load_component(codes[c["artifact"]], c["artifact"], "control")
            self.controller_params = c.get("params", {})
        sandbox.mark_components_loaded()
        self.replay = None
        if replay_actions is not None:
            self.replay = {int(row[0]): row[1:].copy() for row in replay_actions}
        self.start_index = 0
        self.restored = None
        self.hasher = hashlib.sha256()
        self.suffix: dict[str, hashlib._Hash] = {}
        self.wd = job["limits"]["watchdog"]
        self.badqacc0 = 0
        self.E0 = None
        self.last_sampled: dict[str, int] = {}
        if restore is not None:
            self._restore(restore)
        else:
            self._initial_state()

    # ---------------------------------------------------------------- setup
    def _initial_state(self):
        m, d, ist = self.m, self.d, self.job.get("initial_state") or {}
        if ist.get("keyframe"):
            k = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_KEY, ist["keyframe"])
            if k < 0:
                raise Stop("INVALID", "initial_state", f"no keyframe {ist['keyframe']!r}", "invalid_state_or_action_delivery")
            mujoco.mj_resetDataKeyframe(m, d, k)
        for field, attr in (("qpos", "qpos"), ("qvel", "qvel")):
            for joint, value in (ist.get(field) or {}).items():
                try:
                    kind, sl = resolve_target(m, "set_qpos" if field == "qpos" else "set_qvel", joint)
                except SceneError as e:
                    raise Stop("INVALID", "initial_state", str(e), "invalid_state_or_action_delivery") from None
                v = np.atleast_1d(np.asarray(value, dtype=float))
                if v.shape != (sl.stop - sl.start,) or not finite(v):
                    raise Stop("INVALID", "initial_state", f"initial {field} for {joint!r} must be {sl.stop - sl.start} finite numbers",
                               "invalid_state_or_action_delivery")
                getattr(d, attr)[sl] = v
        mujoco.mj_forward(m, d)
        self.hasher.update(state_bytes(d))

    def _restore(self, r: dict):
        meta, state, actions = r["meta"], r["state"], r["actions"]
        if meta["nq"] != self.m.nq or meta["nv"] != self.m.nv or meta["na"] != self.m.na or meta["nu"] != self.m.nu:
            raise Stop("INVALID", "restore", "checkpoint state does not fit this model", "invalid_state_or_action_delivery")
        for k, v in meta.get("model_overrides", {}).items():
            if k == "gravity":
                self.m.opt.gravity[:] = v
                self.model_overrides["gravity"] = v
        mujoco.mj_setState(self.m, self.d, state, STATE_SPEC)
        self.rng.bit_generator.state = meta["rng_state"]
        self.start_index = int(meta["step_index"])
        self.applied = list(meta["applied"])
        self.forces = [tuple(f) for f in meta["active_forces"]]
        self.ctx_state = meta.get("controller_state", {})
        self.contact_state.update({k: v for k, v in meta.get("contact_state", {}).items() if k in self.contact_state})
        self.threshold_prev = meta.get("threshold_prev", {})
        self.E0 = meta.get("E0")
        self.actions = [row for row in actions]
        effective_pending = [iv["intervention_id"] for iv in self.ivs if iv["index"] >= self.start_index
                             and iv["intervention_id"] not in self.applied]
        self.restored = {"checkpoint_time_s": meta["time"], "step_index": self.start_index,
                         "pending_restored": meta["pending"], "pending_effective": effective_pending,
                         "pending_changed": sorted(set(meta["pending"]) ^ set(effective_pending))}
        self.suffix["restore"] = hashlib.sha256()

    # ---------------------------------------------------------------- per step
    def _apply_intervention(self, iv: dict, i: int):
        m, d = self.m, self.d
        try:
            kind, where = resolve_target(m, iv["action"], iv.get("target", ""))
        except SceneError as e:
            raise Stop("INVALID", f"intervention:{iv['intervention_id']}", str(e), "incorrect_intervention") from None
        v = np.atleast_1d(np.asarray(iv["value"], dtype=float))
        b = iv.get("bounds")
        if b is not None and (np.any(v < b[0]) or np.any(v > b[1])):
            raise Stop("INVALID", f"intervention:{iv['intervention_id']}",
                       f"value {v.tolist()} is outside its declared bounds {list(b)}", "incorrect_intervention")
        if not finite(v):
            raise Stop("INVALID", f"intervention:{iv['intervention_id']}", "intervention value is not finite", "incorrect_intervention")
        if kind in {"qpos", "qvel"}:
            arr = d.qpos if kind == "qpos" else d.qvel
            if v.shape != (where.stop - where.start,):
                raise Stop("INVALID", f"intervention:{iv['intervention_id']}",
                           f"{iv['action']} on {iv['target']!r} needs {where.stop - where.start} values, got {v.size}",
                           "incorrect_intervention")
            arr[where] = (arr[where] + v) if iv["action"] == "add_qvel" else v
            expect = arr[where].copy()
            mujoco.mj_forward(m, d)
            if not np.array_equal(arr[where], expect):
                raise Stop("INVALID", f"intervention:{iv['intervention_id']}", "read-back differs from the applied value", "incorrect_intervention")
        elif kind == "xfrc":
            if v.size not in (3, 6):
                raise Stop("INVALID", f"intervention:{iv['intervention_id']}", "apply_force needs 3 (force) or 6 (force, torque) values",
                           "incorrect_intervention")
            d.xfrc_applied[where, :v.size] = v
            until = i + max(1, int(round(float(iv.get("duration_s", 0.0)) / self.dt)))
            self.forces.append((int(where), until))
        elif kind == "ctrl":
            if v.size != 1:
                raise Stop("INVALID", f"intervention:{iv['intervention_id']}", "set_ctrl needs one value", "incorrect_intervention")
            d.ctrl[where] = v[0]
        elif kind == "gravity":
            if v.size != 3:
                raise Stop("INVALID", f"intervention:{iv['intervention_id']}", "set_gravity needs three values", "incorrect_intervention")
            m.opt.gravity[:] = v
            self.model_overrides["gravity"] = v.tolist()
        self.applied.append(iv["intervention_id"])
        self.events.append({"t": float(d.time), "event_id": iv["intervention_id"], "kind": "intervention",
                            "detail": {"action": iv["action"], "target": iv.get("target", ""), "value": v.tolist()}})

    def _control(self, i: int):
        m, d = self.m, self.d
        if self.replay is not None:
            a = self.replay.get(i)
            if a is not None:
                d.ctrl[:] = a
                self.actions.append(np.concatenate([[float(i)], a]))
            return
        if self.controller is None or i % self.control_every:
            return
        obs = {"time": float(d.time), "qpos": d.qpos.copy(), "qvel": d.qvel.copy(), "act": d.act.copy(),
               "ctrl": d.ctrl.copy(), "sensordata": d.sensordata.copy()}
        ctx = SimpleNamespace(rng=self.rng, dt=self.dt, nu=int(m.nu), state=self.ctx_state,
                              actuators=[mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_ACTUATOR, k) for k in range(m.nu)],
                              joints=[mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_JOINT, k) for k in range(m.njnt)])
        try:
            out = self.controller(obs, self.controller_params, ctx)
        except (CpuLimit, MemoryError):
            raise
        except Exception as exc:
            raise Stop("INVALID", "controller", f"controller raised {type(exc).__name__}: {exc}",
                       "invalid_state_or_action_delivery") from None
        if isinstance(out, dict):
            out = out.get("ctrl")
        try:
            a = np.asarray(out, dtype=float).reshape(-1)
        except (TypeError, ValueError):
            raise Stop("INVALID", "controller", f"controller returned {type(out).__name__}, not {m.nu} numbers",
                       "invalid_state_or_action_delivery") from None
        if a.shape != (m.nu,) or not finite(a):
            raise Stop("INVALID", "controller", f"controller action must be {m.nu} finite numbers, got {a.tolist()[:8]}",
                       "invalid_state_or_action_delivery")
        d.ctrl[:] = a
        self.actions.append(np.concatenate([[float(i)], a]))

    def _sample(self, i: int, force: bool = False):
        due = [(s, every) for s, every, _ in self.signals
               if (force or i % every == 0) and self.last_sampled.get(s.name) != i]
        if not due:
            return
        if any(s.derived for s, _ in due):
            mujoco.mj_forward(self.m, self.d)
        for s, _every in due:
            self.last_sampled[s.name] = i
            if True:
                if s.name == "contacts":
                    self.contacts.extend(contact_rows(self.m, self.d))
                else:
                    self.buf[s.name].append(np.concatenate([[self.d.time], s.fn(self.m, self.d)]))

    def _checkpoint(self, i: int, cp: dict):
        d = self.d
        state = np.zeros(mujoco.mj_stateSize(self.m, STATE_SPEC))
        mujoco.mj_getState(self.m, d, state, STATE_SPEC)
        pending = [iv["intervention_id"] for iv in self.ivs if iv["index"] >= i and iv["intervention_id"] not in self.applied]
        try:
            json.dumps(self.ctx_state)
            ctl_state, ctl_note = self.ctx_state, "captured"
        except TypeError:
            ctl_state, ctl_note = {}, "controller state is not JSON-serializable and was not captured"
        meta = {"record": "simlab-checkpoint", "checkpoint_point_id": cp["checkpoint_point_id"], "time": float(d.time),
                "step_index": i, "rng_state": self.rng.bit_generator.state, "pending": pending, "applied": list(self.applied),
                "active_forces": [list(f) for f in self.forces], "controller_state": ctl_state, "controller_state_note": ctl_note,
                "contact_state": dict(self.contact_state), "threshold_prev": dict(self.threshold_prev), "E0": self.E0,
                "model_overrides": dict(self.model_overrides), "model_sha256": self.model_sha,
                "nq": int(self.m.nq), "nv": int(self.m.nv), "na": int(self.m.na), "nu": int(self.m.nu),
                "state_spec": "mjSTATE_INTEGRATION", "state_size": int(state.size),
                "parts": ["world_state", "random_state", "pending_events", "action_history"]}
        cdir = self.out / "checkpoints" / safe(cp["checkpoint_point_id"])
        cdir.mkdir(parents=True, exist_ok=True)
        acts = np.array(self.actions) if self.actions else np.zeros((0, 1 + self.m.nu))
        files = {"state.npy": save_npy(cdir / "state.npy", state), "actions.npy": save_npy(cdir / "actions.npy", acts)}
        meta_bytes = json.dumps(meta, sort_keys=True).encode()
        (cdir / "meta.json").write_bytes(meta_bytes)
        files["meta.json"] = hashlib.sha256(meta_bytes).hexdigest()
        state_sha = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
        self.cp_out.append({"point": cp["checkpoint_point_id"], "time_s": float(d.time), "step_index": i,
                            "dir": str(cdir), "files": files, "state_sha256": state_sha})
        self.suffix[cp["checkpoint_point_id"]] = hashlib.sha256()
        self.events.append({"t": float(d.time), "event_id": cp["checkpoint_point_id"], "kind": "checkpoint", "detail": {}})

    def _events(self):
        m, d = self.m, self.d
        for e in self.events_decl:
            if e["kind"] in {"contact_begin", "contact_end"}:
                ids = [mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_GEOM, g) for g in e["geoms"]]
                active = False
                for k in range(d.ncon):
                    c = d.contact[k]
                    pair = {int(c.geom1), int(c.geom2)}
                    if (len(ids) == 2 and pair == set(ids)) or (len(ids) == 1 and ids[0] in pair):
                        if c.dist <= 0:
                            active = True
                            break
                prev = self.contact_state[e["event_id"]]
                if active != prev:
                    self.contact_state[e["event_id"]] = active
                    if (active and e["kind"] == "contact_begin") or (not active and e["kind"] == "contact_end"):
                        self.events.append({"t": float(d.time - self.dt), "event_id": e["event_id"], "kind": e["kind"],
                                            "detail": {"geoms": e["geoms"]}})
            elif e["kind"] == "threshold":
                sig = parse_signal(m, e["signal"])
                v = float(sig.fn(m, d)[e.get("component", 0)])
                prev = self.threshold_prev.get(e["event_id"])
                lvl = float(e["value"])
                if prev is not None:
                    up = prev < lvl <= v
                    down = prev > lvl >= v
                    if (e["direction"] == "up" and up) or (e["direction"] == "down" and down) or (e["direction"] == "any" and (up or down)):
                        self.events.append({"t": float(d.time), "event_id": e["event_id"], "kind": "threshold",
                                            "detail": {"value": v, "level": lvl}})
                self.threshold_prev[e["event_id"]] = v

    def _watchdog(self, i: int):
        d, wd = self.d, self.wd
        bad = int(d.warning[mujoco.mjtWarning.mjWARN_BADQACC].number)
        if bad > self.badqacc0 or not finite(d.qpos, d.qvel, d.qacc):
            raise Stop("INVALID", "watchdog:nonfinite", f"non-finite state or bad acceleration at t={d.time:.6g}", "numerical_failure")
        if wd.get("max_speed") and self.m.nv and float(np.max(np.abs(d.qvel))) > wd["max_speed"]:
            raise Stop("COMPLETED", "watchdog:max_speed", f"generalized speed {float(np.max(np.abs(d.qvel))):.6g} exceeded {wd['max_speed']}")
        if wd.get("max_penetration") and d.ncon:
            pen = max(0.0, -min(d.contact[k].dist for k in range(d.ncon)))
            if pen > wd["max_penetration"]:
                raise Stop("COMPLETED", "watchdog:max_penetration", f"penetration {pen:.6g} m exceeded {wd['max_penetration']}")
        if wd.get("max_energy_growth"):
            e = float(d.energy[0] + d.energy[1])
            if self.E0 is None:
                self.E0 = e
            growth = (e - self.E0) / max(abs(self.E0), float(wd.get("energy_floor", 1e-9)))
            if growth > wd["max_energy_growth"]:
                raise Stop("COMPLETED", "watchdog:max_energy_growth", f"energy grew by {growth:.6g} (relative) over {wd['max_energy_growth']}")

    def _requirements(self, i: int):
        for idx, step in self.boundaries:
            if idx != i or not step.get("require"):
                continue
            mujoco.mj_forward(self.m, self.d)
            for r in step["require"]:
                v = float(parse_signal(self.m, r["signal"]).fn(self.m, self.d)[r.get("component", 0)])
                ok = {"<": v < r["value"], "<=": v <= r["value"], ">": v > r["value"], ">=": v >= r["value"],
                      "abs<": abs(v) < r["value"]}[r["op"]]
                if not ok:
                    raise Stop("INVALID", f"require:{step['step_id']}",
                               f"step {step['step_id']!r} precondition {r['signal']} {r['op']} {r['value']} not met (value {v:.6g})",
                               "protocol_violation")

    # ---------------------------------------------------------------- run
    def run(self) -> dict:
        m, d = self.m, self.d
        self.cp_out: list[dict] = []
        status, stop, reason, invalid = "COMPLETED", "completed", "", None
        i = self.start_index
        self.badqacc0 = int(d.warning[mujoco.mjtWarning.mjWARN_BADQACC].number)
        max_wall = float(self.job["limits"]["max_wall_s"])
        try:
            if self.wd.get("max_energy_growth") and self.E0 is None:
                mujoco.mj_forward(m, d)
                self.E0 = float(d.energy[0] + d.energy[1])
            self._sample(i, force=True)
            while i < self.n_total:
                if i in self.cps and not (self.restored and i == self.start_index):
                    self._checkpoint(i, self.cps[i])
                for iv in self.ivs:
                    if iv["index"] == i and iv["intervention_id"] not in self.applied:
                        self._apply_intervention(iv, i)
                for f in [f for f in self.forces if f[1] <= i]:
                    d.xfrc_applied[f[0], :] = 0.0
                    self.forces.remove(f)
                self._control(i)
                mujoco.mj_step(m, d)
                i += 1
                sb = state_bytes(d)
                self.hasher.update(sb)
                for h in self.suffix.values():
                    h.update(sb)
                self._watchdog(i)
                if self.events_decl:
                    self._events()
                self._requirements(i)
                self._sample(i)
                if (i & 511) == 0 and time.monotonic() - self.t_wall0 > max_wall:
                    raise Stop("LIMIT_REACHED", "limit:max_wall_s", f"attempt exceeded its wall-time limit {max_wall} s")
            if i in self.cps and not self.horizon_limited and not (self.restored and i == self.start_index):
                self._checkpoint(i, self.cps[i])  # a checkpoint at the end of the last step: the final state
            if self.horizon_limited:
                status, stop, reason = "LIMIT_REACHED", "limit:max_sim_time_s", "procedure longer than max_sim_time_s; stopped at the limit"
        except Stop as s:
            status, stop, reason, invalid = s.status, s.stop, s.reason, s.invalid_reason
        except CpuLimit:
            status, stop, reason = "LIMIT_REACHED", "limit:component_cpu_s", "attempt exceeded its declared CPU limit"
        except MemoryError:
            status, stop, reason = "LIMIT_REACHED", "limit:component_memory_mb", "attempt exceeded its declared memory limit"
        try:
            self._sample(i, force=True)
        except Exception:  # a final sample on a broken state is not available; the stop reason stands
            pass
        for k, den in enumerate(sandbox.DENIALS):
            self.events.append({"t": float(d.time), "event_id": f"denial-{k}", "kind": "confinement_denial", "detail": den})
        self.events.append({"t": float(d.time), "event_id": "stop", "kind": "stop", "detail": {"stop": stop, "status": status}})
        return self._finish(status, stop, reason, invalid, i)

    def _finish(self, status, stop, reason, invalid, i) -> dict:
        traces = []
        for s, every, unit in self.signals:
            if s.name == "contacts":
                arr = np.array(self.contacts, dtype=float).reshape(-1, 5)
                kind = "contacts"
            else:
                arr = np.array(self.buf[s.name], dtype=float).reshape(-1, 1 + s.dim)
                kind = "signal"
            f = self.out / f"{safe(s.name)}.npy"
            sha = save_npy(f, arr)
            traces.append({"signal": s.name, "unit": unit, "file": str(f), "sha256": sha, "n": int(arr.shape[0]),
                           "dim": int(arr.shape[1] - 1), "t_start": float(arr[0, 0]) if len(arr) else None,
                           "t_end": float(arr[-1, 0]) if len(arr) else None, "kind": kind})
        acts = np.array(self.actions) if self.actions else np.zeros((0, 1 + self.m.nu))
        af = self.out / "actions.npy"
        actions_sha = save_npy(af, acts)
        comps = {}
        if status in {"COMPLETED", "LIMIT_REACHED"}:
            data = {s.name: (np.array(self.buf[s.name]) if s.name != "contacts" else np.array(self.contacts)) for s, _, _ in self.signals}
            for mc in self.job.get("measurement_components", []):
                try:
                    fn = load_component(self.codes[mc["artifact"]], mc["artifact"], "measure")
                    v = fn(data, mc.get("params", {}))
                    comps[mc["measurement_id"]] = float(v) if v is not None else None
                except Exception as exc:
                    comps[mc["measurement_id"]] = None
                    self.events.append({"t": float(self.d.time), "event_id": mc["measurement_id"], "kind": "measurement_error",
                                        "detail": {"error": f"{type(exc).__name__}: {exc}"[:500]}})
        return {"status": status, "invalid_reason": invalid, "reason": reason, "stop": stop, "steps": i - self.start_index,
                "sim_time_s": float(self.d.time), "traces": traces, "events": self.events, "checkpoints": self.cp_out,
                "actions": {"file": str(af), "sha256": actions_sha, "n": int(acts.shape[0])},
                "state_digest": self.hasher.hexdigest(), "suffix_digests": {k: h.hexdigest() for k, h in self.suffix.items()},
                "component_measurements": comps, "effective_config": self.effective, "model_sha256": self.model_sha,
                "restored": self.restored, "model_overrides": self.model_overrides,
                "replayed_actions": None if self.replay is None else len(self.replay)}


def main() -> int:
    t0, c0 = time.monotonic(), time.process_time()
    job = json.loads(sys.stdin.read())
    out = Path(job["out_dir"])
    out.mkdir(parents=True, exist_ok=True)
    result: dict
    try:
        assets = {name: Path(p).read_bytes() for name, p in job.get("assets", {}).items()}
        codes = {a: Path(p).read_text() for a, p in job.get("codes", {}).items()}
        restore = None
        if job.get("restore"):
            r = job["restore"]
            restore = {"meta": json.loads(Path(r["meta"]).read_text()), "state": np.load(r["state"], allow_pickle=False),
                       "actions": np.load(r["actions"], allow_pickle=False)}
        replay = np.load(job["replay_actions"], allow_pickle=False) if job.get("replay_actions") else None
        signal.signal(signal.SIGXCPU, _on_xcpu)
        confinement = sandbox.install(job["limits"].get("component", {}))
    except Exception as exc:
        print(json.dumps({"status": "WORKER_ERROR", "reason": f"setup or confinement failed: {type(exc).__name__}: {exc}",
                          "traceback": traceback.format_exc()[-2000:]}))
        return 3
    try:
        trial = Trial(job, assets, codes, restore, replay)
        result = trial.run()
    except Stop as s:
        result = {"status": s.status, "invalid_reason": s.invalid_reason, "reason": s.reason, "stop": s.stop,
                  "traces": [], "events": [], "checkpoints": [], "steps": 0}
    except SceneError as e:
        result = {"status": "INVALID", "invalid_reason": "invalid_state_or_action_delivery", "reason": f"{e.code}: {e}",
                  "stop": "setup", "traces": [], "events": [], "checkpoints": [], "steps": 0}
    except CpuLimit:
        result = {"status": "LIMIT_REACHED", "stop": "limit:component_cpu_s", "reason": "CPU limit during setup",
                  "invalid_reason": None, "traces": [], "events": [], "checkpoints": [], "steps": 0}
    except MemoryError:
        result = {"status": "LIMIT_REACHED", "stop": "limit:component_memory_mb", "reason": "memory limit during setup",
                  "invalid_reason": None, "traces": [], "events": [], "checkpoints": [], "steps": 0}
    import resource as _r  # noqa: PLC0415
    ru = _r.getrusage(_r.RUSAGE_SELF)
    result["confinement"] = {**confinement, "denials": list(sandbox.DENIALS)}
    result["worker_resources"] = {"wall_s": round(time.monotonic() - t0, 4), "cpu_s": round(time.process_time() - c0, 4),
                                  "peak_rss_mb": round(ru.ru_maxrss / 1024, 1), "write_bytes": ru.ru_oublock * 512}
    sys.stdout.write(json.dumps(result, default=float) + "\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
