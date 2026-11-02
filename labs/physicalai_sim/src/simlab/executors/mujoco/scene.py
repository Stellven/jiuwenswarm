"""Scene resolution for the MuJoCo executor: templates, compile, configuration, signals.

Shared by validation (compile every arm/condition before running) and the worker.
"""
from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from typing import Any, Callable

import mujoco
import numpy as np

TEMPLATE_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
FORBIDDEN_ENABLE = {"ipc": "the experimental IPC contact mode breaks exact replay (research.md R7)"}
ENABLE = {"energy": mujoco.mjtEnableBit.mjENBL_ENERGY, "fwdinv": mujoco.mjtEnableBit.mjENBL_FWDINV,
          "invdiscrete": mujoco.mjtEnableBit.mjENBL_INVDISCRETE, "override": mujoco.mjtEnableBit.mjENBL_OVERRIDE,
          "sleep": mujoco.mjtEnableBit.mjENBL_SLEEP, "diagexact": mujoco.mjtEnableBit.mjENBL_DIAGEXACT,
          "ipc": mujoco.mjtEnableBit.mjENBL_IPC}
DISABLE = {n[len("mjDSBL_"):].lower(): getattr(mujoco.mjtDisableBit, n)
           for n in dir(mujoco.mjtDisableBit) if n.startswith("mjDSBL_")}
INTEGRATORS = {"Euler": mujoco.mjtIntegrator.mjINT_EULER, "RK4": mujoco.mjtIntegrator.mjINT_RK4,
               "implicit": mujoco.mjtIntegrator.mjINT_IMPLICIT, "implicitfast": mujoco.mjtIntegrator.mjINT_IMPLICITFAST}
SOLVERS = {"PGS": mujoco.mjtSolver.mjSOL_PGS, "CG": mujoco.mjtSolver.mjSOL_CG, "Newton": mujoco.mjtSolver.mjSOL_NEWTON}
CONES = {"pyramidal": mujoco.mjtCone.mjCONE_PYRAMIDAL, "elliptic": mujoco.mjtCone.mjCONE_ELLIPTIC}


class SceneError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def template_names(xml: str) -> set[str]:
    return set(TEMPLATE_RE.findall(xml))


def _fmt(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        return repr(v)
    if isinstance(v, (list, tuple)):
        return " ".join(_fmt(x) for x in v)
    return str(v)


def resolve_template(xml: str, params: dict[str, Any]) -> str:
    missing = sorted(template_names(xml) - set(params))
    if missing:
        raise SceneError("E_SEMANTIC_TEMPLATE", f"unresolved model-file parameters: {missing}")
    return TEMPLATE_RE.sub(lambda m: _fmt(params[m.group(1)]), xml)


def resolve_value(v: Any, params: dict[str, Any]) -> Any:
    """Resolve '${name}' strings (whole value) and lists of them in procedure fields."""
    if isinstance(v, str):
        m = TEMPLATE_RE.fullmatch(v.strip())
        if m:
            if m.group(1) not in params:
                raise SceneError("E_SEMANTIC_TEMPLATE", f"unresolved procedure parameter {m.group(1)!r}")
            return params[m.group(1)]
        return v
    if isinstance(v, list):
        return [resolve_value(x, params) for x in v]
    return v


def model_sha256(xml: str, assets: dict[str, bytes]) -> str:
    h = hashlib.sha256(xml.encode())
    for name in sorted(assets):
        h.update(b"\0" + name.encode() + b"\0" + hashlib.sha256(assets[name]).digest())
    return h.hexdigest()


def compile_model(xml: str, assets: dict[str, bytes]) -> mujoco.MjModel:
    try:
        return mujoco.MjModel.from_xml_string(xml, assets)
    except Exception as exc:  # engine message is the evidence
        raise SceneError("E_SEMANTIC_MJCF_COMPILE", f"MuJoCo {mujoco.__version__}: {exc}") from None


def apply_config(model: mujoco.MjModel, cfg: dict, *, need_energy: bool = False) -> dict:
    """Apply the resolved configuration; return the effective engine options as run."""
    opt = model.opt
    opt.timestep = float(cfg["timestep"])
    opt.integrator = INTEGRATORS[cfg["integrator"]]
    opt.solver = SOLVERS[cfg["solver"]]
    opt.iterations = int(cfg["iterations"])
    opt.tolerance = float(cfg["tolerance"])
    opt.ls_iterations = int(cfg.get("ls_iterations", 50))
    opt.noslip_iterations = int(cfg.get("noslip_iterations", 0))
    opt.cone = CONES[cfg.get("cone", "pyramidal")]
    opt.impratio = float(cfg.get("impratio", 1.0))
    if "gravity" in cfg and cfg["gravity"] is not None:
        g = list(cfg["gravity"])
        if len(g) != 3:
            raise SceneError("E_SEMANTIC_CONFIG", "gravity must have three components")
        opt.gravity[:] = g
    enable = set(cfg.get("enable_flags", []))
    for f in enable:
        if f in FORBIDDEN_ENABLE:
            raise SceneError("E_SEMANTIC_ENGINE_FLAG", f"enable flag {f!r}: {FORBIDDEN_ENABLE[f]}")
        if f not in ENABLE:
            raise SceneError("E_SEMANTIC_CONFIG", f"unknown enable flag {f!r} (known: {sorted(ENABLE)})")
    if opt.enableflags & int(mujoco.mjtEnableBit.mjENBL_IPC):
        raise SceneError("E_SEMANTIC_ENGINE_FLAG", "the model file enables IPC, which breaks exact replay")
    if need_energy:
        enable.add("energy")
    for f in enable:
        opt.enableflags |= int(ENABLE[f])
    disable = set(cfg.get("disable_flags", []))
    for f in disable:
        if f not in DISABLE:
            raise SceneError("E_SEMANTIC_CONFIG", f"unknown disable flag {f!r} (known: {sorted(DISABLE)})")
        opt.disableflags |= int(DISABLE[f])
    # A numerical failure must surface, never be silently reset (PRD SL-3.S).
    opt.disableflags |= int(mujoco.mjtDisableBit.mjDSBL_AUTORESET)
    return effective_options(model)


def effective_options(model: mujoco.MjModel) -> dict:
    o = model.opt
    inv = {int(v): k for k, v in INTEGRATORS.items()}
    sol = {int(v): k for k, v in SOLVERS.items()}
    cone = {int(v): k for k, v in CONES.items()}
    return {"engine": "mujoco", "engine_version": mujoco.__version__, "timestep": float(o.timestep),
            "integrator": inv.get(int(o.integrator)), "solver": sol.get(int(o.solver)), "iterations": int(o.iterations),
            "tolerance": float(o.tolerance), "ls_iterations": int(o.ls_iterations), "noslip_iterations": int(o.noslip_iterations),
            "cone": cone.get(int(o.cone)), "impratio": float(o.impratio), "gravity": [float(x) for x in o.gravity],
            "enable_flags": sorted(k for k, v in ENABLE.items() if o.enableflags & int(v)),
            "disable_flags": sorted(k for k, v in DISABLE.items() if o.disableflags & int(v)),
            "nq": int(model.nq), "nv": int(model.nv), "nu": int(model.nu), "na": int(model.na), "nbody": int(model.nbody)}


# ------------------------------------------------------------------ signals
@dataclass
class Signal:
    name: str
    dim: int
    derived: bool  # needs mj_forward for a consistent value at the sampled state
    fn: Callable[[mujoco.MjModel, mujoco.MjData], np.ndarray]
    energy: bool = False


def _id(model, objtype, name: str, what: str) -> int:
    i = mujoco.mj_name2id(model, objtype, name)
    if i < 0:
        raise SceneError("E_SEMANTIC_UNKNOWN_SIGNAL", f"no {what} named {name!r}")
    return i


def joint_slices(model, name: str) -> tuple[slice, slice]:
    j = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
    if j < 0:
        raise SceneError("E_SEMANTIC_UNKNOWN_TARGET", f"no joint named {name!r}")
    jt = int(model.jnt_type[j])
    nq = {0: 7, 1: 4, 2: 1, 3: 1}[jt]
    nv = {0: 6, 1: 3, 2: 1, 3: 1}[jt]
    qa, va = int(model.jnt_qposadr[j]), int(model.jnt_dofadr[j])
    return slice(qa, qa + nq), slice(va, va + nv)


def _contact_pairs(model, data, g1: int | None, g2: int | None):
    for i in range(data.ncon):
        c = data.contact[i]
        a, b = int(c.geom1), int(c.geom2)
        if g1 is not None and g2 is not None:
            if {a, b} != {g1, g2}:
                continue
        elif g1 is not None and g1 not in (a, b):
            continue
        yield i, c


def parse_signal(model: mujoco.MjModel, name: str) -> Signal:
    kind, _, rest = name.partition(":")
    O = mujoco.mjtObj
    if name == "time":
        return Signal(name, 1, False, lambda m, d: np.array([d.time]))
    if kind == "qpos":
        qs, _ = joint_slices(model, rest)
        return Signal(name, qs.stop - qs.start, False, lambda m, d, s=qs: d.qpos[s].copy())
    if kind == "qvel":
        _, vs = joint_slices(model, rest)
        return Signal(name, vs.stop - vs.start, False, lambda m, d, s=vs: d.qvel[s].copy())
    if kind in {"xpos", "xquat", "xipos"}:
        b = _id(model, O.mjOBJ_BODY, rest, "body")
        attr = {"xpos": "xpos", "xquat": "xquat", "xipos": "xipos"}[kind]
        return Signal(name, 4 if kind == "xquat" else 3, True, lambda m, d, b=b, a=attr: getattr(d, a)[b].copy())
    if kind in {"linvel", "angvel"}:
        b = _id(model, O.mjOBJ_BODY, rest, "body")
        lo = 3 if kind == "linvel" else 0

        def vel(m, d, b=b, lo=lo):
            res = np.zeros(6)
            mujoco.mj_objectVelocity(m, d, O.mjOBJ_BODY, b, res, 0)
            return res[lo:lo + 3].copy()
        return Signal(name, 3, True, vel)
    if kind in {"ctrl", "act", "actuator_force"}:
        a = _id(model, O.mjOBJ_ACTUATOR, rest, "actuator")
        if kind == "act" and model.actuator_actadr[a] < 0:
            raise SceneError("E_SEMANTIC_UNKNOWN_SIGNAL", f"actuator {rest!r} has no activation state")
        if kind == "ctrl":
            return Signal(name, 1, False, lambda m, d, a=a: np.array([d.ctrl[a]]))
        if kind == "act":
            return Signal(name, 1, False, lambda m, d, a=a: np.array([d.act[m.actuator_actadr[a]]]))
        return Signal(name, 1, True, lambda m, d, a=a: np.array([d.actuator_force[a]]))
    if kind == "sensor":
        s = _id(model, O.mjOBJ_SENSOR, rest, "sensor")
        adr, dim = int(model.sensor_adr[s]), int(model.sensor_dim[s])
        return Signal(name, dim, True, lambda m, d, a=adr, n=dim: d.sensordata[a:a + n].copy())
    if kind == "energy":
        idx = {"potential": [0], "kinetic": [1], "total": [0, 1]}.get(rest)
        if idx is None:
            raise SceneError("E_SEMANTIC_UNKNOWN_SIGNAL", "energy signals are energy:potential, energy:kinetic, energy:total")
        return Signal(name, 1, True, lambda m, d, i=idx: np.array([float(sum(d.energy[j] for j in i))]), energy=True)
    if kind == "momentum" and rest == "total":
        masses = model.body_mass.copy()

        def momentum(m, d, masses=masses):
            p = np.zeros(3)
            res = np.zeros(6)
            for b in range(1, m.nbody):
                mujoco.mj_objectVelocity(m, d, O.mjOBJ_BODY, b, res, 0)
                p += masses[b] * res[3:]
            return p
        return Signal(name, 3, True, momentum)
    if kind == "contact":
        sub, _, geoms = rest.partition(":")
        if sub == "count":
            return Signal(name, 1, True, lambda m, d: np.array([float(d.ncon)]))
        if sub == "penetration_max":
            def pen(m, d):
                dist = [d.contact[i].dist for i in range(d.ncon)]
                return np.array([max(0.0, -min(dist)) if dist else 0.0])
            return Signal(name, 1, True, pen)
        if sub == "normal_force":
            names = [g for g in geoms.split(":") if g]
            if not 1 <= len(names) <= 2:
                raise SceneError("E_SEMANTIC_UNKNOWN_SIGNAL", "contact:normal_force:<geom>[:<geom>]")
            ids = [_id(model, O.mjOBJ_GEOM, g, "geom") for g in names]
            g1, g2 = ids[0], (ids[1] if len(ids) > 1 else None)

            def fn(m, d, g1=g1, g2=g2):
                total, f6 = 0.0, np.zeros(6)
                for i, _c in _contact_pairs(m, d, g1, g2):
                    mujoco.mj_contactForce(m, d, i, f6)
                    total += f6[0]
                return np.array([total])
            return Signal(name, 1, True, fn)
        raise SceneError("E_SEMANTIC_UNKNOWN_SIGNAL", f"unknown contact signal {name!r}")
    if name == "contacts":
        return Signal(name, 0, True, lambda m, d: np.zeros(0))  # recorded as a contact table
    raise SceneError("E_SEMANTIC_UNKNOWN_SIGNAL", f"unknown signal {name!r}")


def contact_rows(model, data) -> list[list[float]]:
    f6 = np.zeros(6)
    rows = []
    for i in range(data.ncon):
        c = data.contact[i]
        mujoco.mj_contactForce(model, data, i, f6)
        rows.append([float(data.time), float(c.geom1), float(c.geom2), float(c.dist), float(f6[0])])
    return rows


def resolve_target(model, action: str, target: str) -> tuple[str, Any]:
    O = mujoco.mjtObj
    if action in {"set_qpos"}:
        qs, _ = joint_slices(model, target)
        return "qpos", qs
    if action in {"set_qvel", "add_qvel"}:
        _, vs = joint_slices(model, target)
        return "qvel", vs
    if action == "apply_force":
        b = mujoco.mj_name2id(model, O.mjOBJ_BODY, target)
        if b < 0:
            raise SceneError("E_SEMANTIC_UNKNOWN_TARGET", f"no body named {target!r}")
        return "xfrc", b
    if action == "set_ctrl":
        a = mujoco.mj_name2id(model, O.mjOBJ_ACTUATOR, target)
        if a < 0:
            raise SceneError("E_SEMANTIC_UNKNOWN_TARGET", f"no actuator named {target!r}")
        return "ctrl", a
    if action == "set_gravity":
        return "gravity", None
    raise SceneError("E_SEMANTIC_UNKNOWN_TARGET", f"unknown action {action!r}")


def finite(*arrays) -> bool:
    return all(bool(np.isfinite(a).all()) for a in arrays)


def isclose_vec(a, b) -> bool:
    a, b = np.asarray(a, float), np.asarray(b, float)
    return a.shape == b.shape and bool(np.all(a == b))


def is_number(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)
