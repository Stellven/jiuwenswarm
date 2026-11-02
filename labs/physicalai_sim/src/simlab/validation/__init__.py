"""Validation before running (PAS-M1-001 B03; PRD SL-4.D; ARCH X1.3).

`validate` returns every finding at once: schema findings first, then semantic
findings. It never rejects an experiment because of its objective kind
(PRD SL-1.B). A defective experiment creates no run (the runner checks
`validate` before creating one).
"""
from __future__ import annotations

import itertools
import re
from typing import Any

from simlab.contracts import SimlabError, finding, parse_record, sha256_hex
from simlab.contracts.records import Experiment
from simlab.measure import PAIR_KINDS, SET_KINDS, STANDARD_TRIAL_KINDS

ADMITTED_ENGINE = {"engine": "mujoco"}
ORIGIN_REQUIRED_KINDS = {"predicate", "threshold", "arm", "variable", "trial_count"}
STATE_SIGNAL = re.compile(r"^(time|qpos:.+|qvel:.+|ctrl:.+|act:.+)$")


def conditions_of(design) -> tuple[list[tuple[str, dict]], list[dict]]:
    """Expand factors and conditions into (condition_id, settings); return findings for bad references."""
    findings: list[dict] = []
    factors = {f.factor_id: {lv.level_id: lv.settings for lv in f.levels} for f in design.factors}
    out: list[tuple[str, dict]] = []
    if design.conditions:
        for k, c in enumerate(design.conditions):
            settings: dict = {}
            for fid, lid in c.levels.items():
                if fid not in factors:
                    findings.append(finding("E_SEMANTIC_UNKNOWN_REF", f"condition {c.condition_id!r} names unknown factor {fid!r}",
                                            f"/design/conditions/{k}/levels/{fid}"))
                elif lid not in factors[fid]:
                    findings.append(finding("E_SEMANTIC_UNKNOWN_REF", f"condition {c.condition_id!r} names unknown level {lid!r} of {fid!r}",
                                            f"/design/conditions/{k}/levels/{fid}"))
                else:
                    settings.update(factors[fid][lid])
            out.append((c.condition_id, settings))
    elif design.factors:
        names = [f.factor_id for f in design.factors]
        for combo in itertools.product(*[[lv for lv in f.levels] for f in design.factors]):
            cid = "__".join(f"{n}.{lv.level_id}" for n, lv in zip(names, combo))
            settings = {}
            for lv in combo:
                settings.update(lv.settings)
            out.append((cid, settings))
    else:
        out.append(("nominal", {}))
    return out, findings


def split_settings(settings: dict) -> tuple[dict, dict]:
    """'config.<field>' entries override the resolved configuration; everything else is a template parameter."""
    params, config = {}, {}
    for k, v in settings.items():
        if k.startswith("config."):
            config[k[len("config."):]] = v
        else:
            params[k[len("param:"):] if k.startswith("param:") else k] = v
    return params, config


def _dupes(items, key) -> list[str]:
    seen, d = set(), []
    for it in items:
        k = getattr(it, key)
        if k in seen:
            d.append(k)
        seen.add(k)
    return d


def semantic(exp: Experiment, store=None, *, compile_scenes: bool = True) -> list[dict]:
    f: list[dict] = []
    # --- identifiers
    for path, items, key in (("/arms", exp.arms, "arm_id"), ("/measurements", exp.measurements, "measurement_id"),
                             ("/checks", exp.checks, "check_id"), ("/procedure/steps", exp.procedure.steps, "step_id"),
                             ("/procedure/interventions", exp.procedure.interventions, "intervention_id"),
                             ("/procedure/checkpoints", exp.procedure.checkpoints, "checkpoint_point_id"),
                             ("/procedure/events", exp.procedure.events, "event_id"), ("/design/factors", exp.design.factors, "factor_id"),
                             ("/protocol_items", exp.protocol_items, "item_id")):
        for d in _dupes(items, key):
            f.append(finding("E_SEMANTIC_DUPLICATE_ID", f"{key} {d!r} is declared more than once", path))
    arm_ids = {a.arm_id for a in exp.arms}
    meas = {m.measurement_id: m for m in exp.measurements}
    step_ids = {s.step_id for s in exp.procedure.steps}
    # --- origins (PRD SL-1.S: every protocol item carries its origin)
    for k, it in enumerate(exp.protocol_items):
        if it.item_kind in ORIGIN_REQUIRED_KINDS and not (it.origin and it.origin.strip()):
            f.append(finding("E_SEMANTIC_NO_ORIGIN", f"protocol item {it.item_id!r} ({it.item_kind}) has no origin",
                             f"/protocol_items/{k}/origin"))
    for k, p in enumerate(exp.predicates):
        if not (p.origin and p.origin.strip()):
            f.append(finding("E_SEMANTIC_NO_ORIGIN", f"predicate {p.predicate_id!r} has no origin", f"/predicates/{k}/origin"))
        if p.measurement_id not in meas:
            f.append(finding("E_SEMANTIC_UNKNOWN_REF", f"predicate {p.predicate_id!r} names unknown measurement {p.measurement_id!r}",
                             f"/predicates/{k}/measurement_id"))
    for k, t in enumerate(exp.thresholds):
        if not (t.origin and t.origin.strip()):
            f.append(finding("E_SEMANTIC_NO_ORIGIN", f"threshold {t.threshold_id!r} has no origin", f"/thresholds/{k}/origin"))
    # --- engine
    if not exp.engines:
        f.append(finding("E_SEMANTIC_ENGINE", "no engine is declared", "/engines"))
    for k, e in enumerate(exp.engines):
        import mujoco  # noqa: PLC0415

        if e.engine != "mujoco" or e.version != mujoco.__version__:
            f.append(finding("E_SEMANTIC_ENGINE", f"engine {e.engine} {e.version} is not the admitted executor mujoco {mujoco.__version__}",
                             f"/engines/{k}"))
        if not e.why.strip():
            f.append(finding("E_SEMANTIC_ENGINE", "each engine records why it was chosen", f"/engines/{k}/why"))
    if "ipc" in exp.resolved_configuration.enable_flags:
        f.append(finding("E_SEMANTIC_ENGINE_FLAG", "enable flag 'ipc' breaks exact replay (research.md R7)",
                         "/resolved_configuration/enable_flags"))
    # --- arms and components
    if not exp.arms:
        f.append(finding("E_SEMANTIC_ZERO_TRIALS", "the experiment declares no arm", "/arms"))
    for k, a in enumerate(exp.arms):
        scenes = [c for c in a.components if c.extension_point == "scene"]
        if len(scenes) != 1:
            f.append(finding("E_SEMANTIC_UNKNOWN_REF", f"arm {a.arm_id!r} must bind exactly one scene model file (has {len(scenes)})",
                             f"/arms/{k}/components"))
        ctl = [c for c in a.components if c.extension_point == "controller"]
        if len(ctl) > 1:
            f.append(finding("E_EXTENSION_POINT", f"arm {a.arm_id!r} binds more than one controller", f"/arms/{k}/components"))
    # --- design
    conds, cf = conditions_of(exp.design)
    f += cf
    n_trials = len(conds) * exp.design.replicates * exp.design.episodes * len(exp.arms)
    if n_trials == 0:
        f.append(finding("E_SEMANTIC_ZERO_TRIALS",
                         f"the design yields no trial ({len(conds)} conditions x {exp.design.replicates} replicates x "
                         f"{exp.design.episodes} episodes x {len(exp.arms)} arms)", "/design"))
    rv_names = {rv.name for rv in exp.design.randomness.random_variables}
    for k, rv in enumerate(exp.design.randomness.random_variables):
        d = rv.distribution
        ok = {"normal": d.mean is not None and d.std is not None and d.std >= 0,
              "uniform": d.low is not None and d.high is not None and d.low <= d.high,
              "choice": bool(d.choices)}[d.kind]
        if not ok:
            f.append(finding("E_SCHEMA_TYPE", f"random variable {rv.name!r}: {d.kind} needs its parameters",
                             f"/design/randomness/random_variables/{k}/distribution"))
    for k, c in enumerate(exp.design.comparisons):
        missing = [n for n in ("unit_of_inference", "pairing", "aggregation", "required_precision") if getattr(c, n) in (None, "")]
        if c.counted and missing:
            f.append(finding("E_SEMANTIC_COMPARISON_INCOMPLETE", f"comparison {c.comparison_id!r} lacks {', '.join(missing)}",
                             f"/design/comparisons/{k}"))
        for a in c.arms:
            if a not in arm_ids:
                f.append(finding("E_SEMANTIC_UNKNOWN_REF", f"comparison {c.comparison_id!r} names unknown arm {a!r}",
                                 f"/design/comparisons/{k}/arms"))
        if c.measurement_id and c.measurement_id not in meas:
            f.append(finding("E_SEMANTIC_UNKNOWN_REF", f"comparison {c.comparison_id!r} names unknown measurement {c.measurement_id!r}",
                             f"/design/comparisons/{k}/measurement_id"))
    # --- procedure
    total = sum(s.duration_s for s in exp.procedure.steps)
    if not exp.procedure.steps:
        f.append(finding("E_SEMANTIC_ZERO_TRIALS", "the procedure declares no step", "/procedure/steps"))
    for k, cp in enumerate(exp.procedure.checkpoints):
        where = f"/procedure/checkpoints/{k}"
        if (cp.step_end is None) == (cp.time_s is None):
            f.append(finding("E_SEMANTIC_UNDECLARED_CHECKPOINT", f"checkpoint {cp.checkpoint_point_id!r} needs exactly one of step_end or time_s", where))
        elif cp.step_end is not None and cp.step_end not in step_ids:
            f.append(finding("E_SEMANTIC_UNDECLARED_CHECKPOINT", f"checkpoint {cp.checkpoint_point_id!r} is at undeclared step {cp.step_end!r}",
                             where + "/step_end"))
        elif cp.time_s is not None and not (0 <= cp.time_s < total):
            f.append(finding("E_SEMANTIC_UNDECLARED_CHECKPOINT",
                             f"checkpoint {cp.checkpoint_point_id!r} at t={cp.time_s} is outside the procedure (0 to {total} s)", where + "/time_s"))
    for k, e in enumerate(exp.procedure.events):
        if e.kind == "threshold" and (not e.signal or not STATE_SIGNAL.match(e.signal) or e.value is None):
            f.append(finding("E_SEMANTIC_UNKNOWN_SIGNAL", f"threshold event {e.event_id!r} needs a state signal (time, qpos, qvel, ctrl, act) and a value",
                             f"/procedure/events/{k}"))
        if e.kind != "threshold" and not 1 <= len(e.geoms) <= 2:
            f.append(finding("E_SEMANTIC_UNKNOWN_REF", f"contact event {e.event_id!r} needs one or two geoms", f"/procedure/events/{k}/geoms"))
    # --- measurements
    events = {e.event_id for e in exp.procedure.events}
    for k, m in enumerate(exp.measurements):
        d, where = m.definition, f"/measurements/{k}/definition"
        if m.scope.value == "trial":
            if d.kind in PAIR_KINDS | SET_KINDS:
                f.append(finding("E_SCHEMA_ENUM", f"{d.kind} is not a trial-scope kind", where + "/kind"))
            elif d.kind == "component":
                if not d.artifact:
                    f.append(finding("E_EXTENSION_POINT", f"component measurement {m.measurement_id!r} names no artifact", where + "/artifact"))
            elif d.kind in {"event_time", "event_count"} or d.kind == "velocity_ratio_at_event":
                if d.event_id not in events:
                    f.append(finding("E_SEMANTIC_UNKNOWN_REF", f"measurement {m.measurement_id!r} names undeclared event {d.event_id!r}", where + "/event_id"))
                if d.kind == "velocity_ratio_at_event" and (d.t_end_event not in events or not d.signal):
                    f.append(finding("E_SEMANTIC_UNKNOWN_REF", f"measurement {m.measurement_id!r} needs a signal and a declared t_end_event", where))
            elif not d.signal:
                f.append(finding("E_SEMANTIC_UNKNOWN_SIGNAL", f"measurement {m.measurement_id!r} ({d.kind}) names no signal", where + "/signal"))
            if d.kind == "at_time" and d.t is None:
                f.append(finding("E_SCHEMA_REQUIRED", f"at_time measurement {m.measurement_id!r} needs t", where + "/t"))
            traced = {t.signal for t in exp.trace_signals} | {t.signal for t in exp.probes}
            for s in [d.signal, d.signal_b]:
                if s and d.kind in STANDARD_TRIAL_KINDS and s not in traced:
                    f.append(finding("E_SEMANTIC_UNKNOWN_SIGNAL", f"measurement {m.measurement_id!r} uses signal {s!r}, which is not traced",
                                     where + "/signal"))
        else:
            if m.scope.value == "pair" and d.kind not in PAIR_KINDS:
                f.append(finding("E_SCHEMA_ENUM", f"{d.kind} is not a pair-scope kind", where + "/kind"))
            if m.scope.value == "set" and d.kind not in SET_KINDS:
                f.append(finding("E_SCHEMA_ENUM", f"{d.kind} is not a set-scope kind", where + "/kind"))
            if d.of not in meas or meas[d.of].scope.value != "trial":
                f.append(finding("E_SEMANTIC_UNKNOWN_REF", f"measurement {m.measurement_id!r} aggregates {d.of!r}, which is not a trial measurement",
                                 where + "/of"))
            if m.scope.value == "pair":
                if len(d.arms) != 2 or any(a not in arm_ids for a in d.arms):
                    f.append(finding("E_SEMANTIC_UNKNOWN_REF", f"pair measurement {m.measurement_id!r} needs two declared arms", where + "/arms"))
                if exp.design.pairing != "paired":
                    f.append(finding("E_SEMANTIC_COMPARISON_INCOMPLETE", f"pair measurement {m.measurement_id!r} needs a paired design",
                                     "/design/pairing"))
            for a in d.arms if m.scope.value == "set" else []:
                if a not in arm_ids:
                    f.append(finding("E_SEMANTIC_UNKNOWN_REF", f"set measurement {m.measurement_id!r} names unknown arm {a!r}", where + "/arms"))
    # --- checks
    for k, c in enumerate(exp.checks):
        where = f"/checks/{k}"
        if c.check_kind == "known_answer":
            if c.measurement_id not in meas or c.expected is None or c.tolerance is None:
                f.append(finding("E_SEMANTIC_UNKNOWN_REF", f"known-answer check {c.check_id!r} needs a declared measurement, expected value and tolerance", where))
            if not (c.origin and c.origin.strip()):
                f.append(finding("E_SEMANTIC_NO_ORIGIN", f"known-answer check {c.check_id!r} has no origin", where + "/origin"))
        if c.check_kind == "control_arm" and (not c.arms or any(a not in arm_ids for a in c.arms)):
            f.append(finding("E_SEMANTIC_UNKNOWN_REF", f"control-arm check {c.check_id!r} needs declared arms", where + "/arms"))
        if c.check_kind == "rerun":
            if not c.variations:
                f.append(finding("E_SEMANTIC_UNKNOWN_REF", f"rerun check {c.check_id!r} declares no engine setting or assumed value to vary", where + "/variations"))
            for mid in c.required_precision:
                if mid not in meas:
                    f.append(finding("E_SEMANTIC_UNKNOWN_REF", f"rerun check {c.check_id!r} names unknown measurement {mid!r}", where + "/required_precision"))
            for j, v in enumerate(c.variations):
                if not (v.setting.startswith("config.") or v.setting.startswith("param:")) or not v.values:
                    f.append(finding("E_SEMANTIC_UNKNOWN_REF", f"rerun variation {v.setting!r} must be 'config.<field>' or 'param:<name>' with values",
                                     f"{where}/variations/{j}"))
        if c.check_kind == "recomputation":
            for mid in c.measurements:
                if mid not in meas:
                    f.append(finding("E_SEMANTIC_UNKNOWN_REF", f"recomputation check {c.check_id!r} names unknown measurement {mid!r}", where + "/measurements"))
    # --- feasibility
    for k, fe in enumerate(exp.feasibility):
        for a in fe.affected_arms:
            if a not in arm_ids:
                f.append(finding("E_SEMANTIC_UNKNOWN_REF", f"feasibility entry {fe.dependency_id!r} names unknown arm {a!r}",
                                 f"/feasibility/{k}/affected_arms"))
        if fe.status.value == "missing" and not fe.reason.strip():
            f.append(finding("E_SCHEMA_REQUIRED", f"missing dependency {fe.dependency_id!r} needs its reason", f"/feasibility/{k}/reason"))
    # --- store-dependent: manifest binding, assets, parent, scenes
    if store is not None:
        f += _bound(exp, store, conds, compile_scenes)
    return f


def _bound(exp: Experiment, store, conds, compile_scenes: bool) -> list[dict]:
    from simlab.authoring import experiment_id_for  # noqa: PLC0415

    f: list[dict] = []
    manifest = None
    if exp.assets is None:
        f.append(finding("E_NOT_BOUND", "the experiment is not bound to a manifest (use bind)", "/assets"))
    else:
        manifest = store.get_manifest(exp.assets.manifest_id)
        if manifest is None or manifest["manifest_sha256"] != exp.assets.manifest_sha256:
            f.append(finding("E_NOT_BOUND", f"manifest {exp.assets.manifest_id} with that hash is not stored", "/assets"))
            manifest = None
    files: dict[str, bytes] = {}
    if manifest is not None:
        expected = experiment_id_for(exp.model_dump(mode="json"), manifest["artifacts"])
        if manifest["experiment_id"] != expected:
            f.append(finding("E_SEMANTIC_MANIFEST_BINDING", "the manifest binds a different experiment (its content changed after bind)", "/assets"))
        if exp.experiment_id is not None and exp.experiment_id != expected:
            f.append(finding("E_SEMANTIC_MANIFEST_BINDING", f"experiment_id {exp.experiment_id} does not match its content ({expected})",
                             "/experiment_id"))
        for k, a in enumerate(manifest["artifacts"]):
            try:
                files[a["path"]] = store.get_blob(a["sha256"])
            except SimlabError as e:
                f.append(finding("E_SEMANTIC_ASSET_HASH", f"artifact {a['path']}: {e.message}", f"/assets/artifacts/{k}"))
        paths = {a["path"]: a for a in manifest["artifacts"]}
        for k, arm in enumerate(exp.arms):
            for j, c in enumerate(arm.components):
                a = paths.get(c.artifact)
                if a is None:
                    f.append(finding("E_SEMANTIC_ASSET_HASH", f"arm {arm.arm_id!r} binds {c.artifact!r}, which is not in the manifest",
                                     f"/arms/{k}/components/{j}/artifact"))
                elif c.extension_point == "scene" and a["kind"] != "model_file":
                    f.append(finding("E_EXTENSION_POINT", f"scene {c.artifact!r} is a {a['kind']}, not a model file", f"/arms/{k}/components/{j}"))
                elif c.extension_point in {"controller", "measurement"} and (a["kind"] != "component" or a.get("extension_point") != c.extension_point):
                    f.append(finding("E_EXTENSION_POINT", f"{c.artifact!r} is not component code for the {c.extension_point} extension point",
                                     f"/arms/{k}/components/{j}"))
        for k, m in enumerate(exp.measurements):
            if m.definition.kind == "component":
                a = paths.get(m.definition.artifact or "")
                if a is None or a["kind"] != "component" or a.get("extension_point") != "measurement":
                    f.append(finding("E_EXTENSION_POINT", f"measurement {m.measurement_id!r} needs a measurement component in the manifest",
                                     f"/measurements/{k}/definition/artifact"))
    # parent
    cp = None
    if exp.parent is not None:
        if (exp.parent.run_id is None) == (exp.parent.checkpoint_id is None):
            f.append(finding("E_SEMANTIC_PARENT_MISSING", "parent names exactly one of run_id or checkpoint_id", "/parent"))
        elif exp.parent.run_id is not None and store.q1("SELECT 1 FROM runs WHERE run_id=?", (exp.parent.run_id,)) is None:
            f.append(finding("E_SEMANTIC_PARENT_MISSING", f"parent run {exp.parent.run_id} does not exist", "/parent/run_id"))
        elif exp.parent.checkpoint_id is not None:
            cp = store.get_checkpoint(exp.parent.checkpoint_id)
            if cp is None:
                f.append(finding("E_SEMANTIC_PARENT_MISSING", f"parent checkpoint {exp.parent.checkpoint_id} does not exist", "/parent/checkpoint_id"))
            else:
                cf = checkpoint_findings(store, cp)
                f += cf
                if cf:
                    cp = None
                else:
                    import json as _json  # noqa: PLC0415
                    cp = {**cp, "meta": _json.loads(store.get_blob(cp["files"]["meta.json"]))}
    # scenes compile for every arm and condition; targets and signals exist
    if compile_scenes and manifest is not None and files:
        f += _scenes(exp, files, conds, cp)
    return f


CHECKPOINT_PARTS = {"world_state": "state.npy", "action_history": "actions.npy"}
CHECKPOINT_META = {"random_state": "rng_state", "pending_events": "pending", "applied_events": "applied", "step_index": "step_index"}


def checkpoint_findings(store, cp: dict) -> list[dict]:
    """A checkpoint must hold world state, random state, pending events and action history (PRD SL-7.D; AC-012)."""
    import json as _json  # noqa: PLC0415

    missing = [part for part, name in CHECKPOINT_PARTS.items() if name not in cp["files"]]
    meta = None
    if "meta.json" not in cp["files"]:
        missing.append("metadata")
    else:
        try:
            meta = _json.loads(store.get_blob(cp["files"]["meta.json"]))
        except Exception:  # damaged or absent
            missing.append("metadata")
    if meta is not None:
        missing += [part for part, key in CHECKPOINT_META.items() if key not in meta]
    for name in ("state.npy", "actions.npy"):
        if name in cp["files"]:
            try:
                store.get_blob(cp["files"][name])
            except Exception:
                missing.append(name)
    if missing:
        return [finding("E_SEMANTIC_CHECKPOINT_INCOMPATIBLE", f"checkpoint {cp['checkpoint_id']} is missing {sorted(set(missing))}",
                        "/parent/checkpoint_id")]
    return []


def _scenes(exp: Experiment, files: dict[str, bytes], conds, cp) -> list[dict]:
    from simlab.executors.mujoco.scene import (  # noqa: PLC0415
        SceneError, apply_config, compile_model, joint_slices, parse_signal, resolve_target, resolve_template, template_names,
    )

    raw: list[tuple[str, str, str, str, str]] = []  # code, message, path, arm, condition

    def add(code, msg, path, arm_id, cid):
        raw.append((code, msg, path, arm_id, cid))
    assets = {p: b for p, b in files.items()}
    rv = {r.name: _nominal(r) for r in exp.design.randomness.random_variables}
    seen: set[tuple] = set()
    signals = [t.signal for t in exp.trace_signals] + [t.signal for t in exp.probes]
    for k, arm in enumerate(exp.arms):
        scene = next((c for c in arm.components if c.extension_point == "scene"), None)
        if scene is None or scene.artifact not in files:
            continue
        xml_t = files[scene.artifact].decode("utf-8", "replace")
        for cid, settings in conds:
            params, cfg_over = split_settings(settings)
            params = {**rv, **arm.params, **params}
            key = (arm.arm_id, sha256_hex({"p": {k2: str(v) for k2, v in params.items()}, "c": {k2: str(v) for k2, v in cfg_over.items()}}))
            if key in seen:
                continue
            seen.add(key)
            where = f"/arms/{k}"
            missing = sorted(template_names(xml_t) - set(params))
            if missing:
                add("E_SEMANTIC_TEMPLATE", f"model-file parameters {missing} are not set", where + "/params", arm.arm_id, cid)
                continue
            try:
                model = compile_model(resolve_template(xml_t, params), {p: b for p, b in assets.items() if p != scene.artifact})
                apply_config(model, {**exp.resolved_configuration.model_dump(), **cfg_over})
            except SceneError as e:
                add(e.code, str(e), where + "/components", arm.arm_id, cid)
                continue
            for s in signals:
                try:
                    parse_signal(model, s)
                except SceneError as e:
                    add("E_SEMANTIC_UNKNOWN_SIGNAL", str(e), "/trace_signals", arm.arm_id, cid)
            for j, iv in enumerate(exp.procedure.interventions):
                try:
                    resolve_target(model, iv.action, iv.target)
                except SceneError as e:
                    add("E_SEMANTIC_UNKNOWN_TARGET", f"intervention {iv.intervention_id!r}: {e}", f"/procedure/interventions/{j}/target",
                        arm.arm_id, cid)
            for field in ("qpos", "qvel"):
                for joint in getattr(exp.procedure.initial_state, field):
                    try:
                        joint_slices(model, joint)
                    except SceneError as e:
                        add("E_SEMANTIC_UNKNOWN_TARGET", f"initial {field}: {e}", f"/procedure/initial_state/{field}/{joint}", arm.arm_id, cid)
            for j, r in enumerate(st for s in exp.procedure.steps for st in s.require):
                try:
                    parse_signal(model, r.signal)
                except SceneError as e:
                    add("E_SEMANTIC_UNKNOWN_SIGNAL", f"step requirement: {e}", "/procedure/steps", arm.arm_id, cid)
            if cp is not None:
                meta = cp["meta"]
                if (model.nq, model.nv, model.na, model.nu) != (meta["nq"], meta["nv"], meta["na"], meta["nu"]):
                    add("E_SEMANTIC_CHECKPOINT_INCOMPATIBLE",
                        f"model state (nq={model.nq}, nv={model.nv}, na={model.na}, nu={model.nu}) does not fit checkpoint {cp['checkpoint_id']}",
                        where + "/components", arm.arm_id, cid)
    # One defect is one finding: merge the arms and conditions that show it into its message.
    merged: dict[tuple[str, str, str], tuple[list[str], list[str]]] = {}
    for code, msg, path, arm_id, cid in raw:
        arms_, conds_ = merged.setdefault((code, msg, path), ([], []))
        if arm_id not in arms_:
            arms_.append(arm_id)
        if cid not in conds_:
            conds_.append(cid)
    out = []
    for (code, msg, path), (arms_, conds_) in merged.items():
        where = f"arm {arms_[0]!r}" if len(arms_) == 1 else f"arms {arms_}"
        if len(conds) > 1:
            where += f", condition{'s' if len(conds_) > 1 else ''} {conds_ if len(conds_) > 1 else repr(conds_[0])}"
        out.append(finding(code, f"{where}: {msg}", path))
    return out


def _nominal(rv) -> Any:
    d = rv.distribution
    if d.kind == "normal":
        return d.mean
    if d.kind == "uniform":
        return (d.low + d.high) / 2 if d.low is not None and d.high is not None else 0.0
    return d.choices[0] if d.choices else 0.0


def validate(data: Any, store=None, *, compile_scenes: bool = True) -> tuple[Experiment | None, list[dict]]:
    """Return (experiment or None, every finding). Empty findings means valid."""
    exp, findings = parse_record("simlab-experiment", data)
    if exp is None:
        # Report semantic findings too when the only schema defects are unknown fields:
        # removing an unknown field cannot change the meaning of the rest.
        if isinstance(data, dict) and findings and all(x["code"] == "E_SCHEMA_UNKNOWN_FIELD" for x in findings):
            repaired = _without(data, [x["path"] for x in findings])
            exp2, again = parse_record("simlab-experiment", repaired)
            if exp2 is not None and not again:
                return None, findings + semantic(exp2, store, compile_scenes=compile_scenes)
        return None, findings
    return exp, semantic(exp, store, compile_scenes=compile_scenes)


def _without(data: Any, pointers: list[str]) -> Any:
    import copy  # noqa: PLC0415

    out = copy.deepcopy(data)
    for ptr in pointers:
        parts = [p.replace("~1", "/").replace("~0", "~") for p in ptr.strip("/").split("/")] if ptr else []
        node = out
        for p in parts[:-1]:
            node = node[int(p)] if isinstance(node, list) else node.get(p)
            if node is None:
                break
        if isinstance(node, dict) and parts:
            node.pop(parts[-1], None)
    return out
