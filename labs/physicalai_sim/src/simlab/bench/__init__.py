"""SIMLAB-Bench harness (PAS-M1-001 B12; test plan "SIMLAB-Bench families"; Harbor case format).

Runs frozen cases through the SIMLAB tool interface (the Python client over the
service socket), exports normalized evidence from SIMLAB's own records, and grades
it with each case's independent stdlib oracle in a separate isolated process.
It never grades itself: the oracle decides pass/fail, the harness only records.

Rules followed (benchmark requirements v0.12): objective, inputs, grading and primary
metric declared first in case.json (B01); feasible and invalid runs reported
separately (B02); development split only in this repository (B03); independent
oracle (B05); failed runs kept, no retries (B08); expected values only in referee/
(B12); a hardware inventory before each run (B17); results per family, no aggregate.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

BENCH = Path(__file__).resolve().parents[3] / "benchmarks" / "simlab_bench"
if not BENCH.is_dir():  # inside the image the lab lives at /opt/simlab or /src
    for root in (Path("/src"), Path("/opt/simlab")):
        if (root / "benchmarks" / "simlab_bench").is_dir():
            BENCH = root / "benchmarks" / "simlab_bench"
            break
CASES = BENCH / "cases"
RELEASES = BENCH / "releases"
PROFILES = BENCH / "profiles"


def sha_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def case_files(case_dir: Path) -> dict[str, str]:
    return {p.relative_to(CASES).as_posix(): sha_file(p) for p in sorted(case_dir.rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts}


def load_case(case_id: str) -> dict:
    d = CASES / case_id
    case = json.loads((d / "case.json").read_text())
    case["_dir"] = d
    return case


def all_cases() -> list[str]:
    return sorted(p.name for p in CASES.iterdir() if (p / "case.json").is_file())


# ------------------------------------------------------------------ release freeze
def freeze(release_id: str) -> dict:
    import mujoco  # noqa: PLC0415

    files = {}
    for cid in all_cases():
        files.update(case_files(CASES / cid))
    for name in ("run_oracle.py",):
        files[name] = sha_file(BENCH / name)
    for p in sorted(PROFILES.glob("*.json")):
        files["profiles/" + p.name] = sha_file(p)
    body = {"schema": "simlab-bench-release:1", "release_id": release_id, "engine": {"mujoco": mujoco.__version__},
            "cases": all_cases(), "files": files}
    body["release_sha256"] = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    RELEASES.mkdir(parents=True, exist_ok=True)
    out = RELEASES / f"{release_id}.json"
    if out.exists():
        raise SystemExit(f"release {release_id} is already frozen; a change needs a new release id")
    out.write_text(json.dumps(body, indent=1, sort_keys=True) + "\n")
    return body


def verify_release(release_id: str, case_ids: list[str]) -> dict:
    import mujoco  # noqa: PLC0415

    rel = json.loads((RELEASES / f"{release_id}.json").read_text())
    problems = []
    if rel["engine"]["mujoco"] != mujoco.__version__:
        problems.append(f"release was frozen for MuJoCo {rel['engine']['mujoco']}; this build runs {mujoco.__version__} (rerun after re-freezing)")
    for cid in case_ids:
        now = case_files(CASES / cid)
        frozen = {k: v for k, v in rel["files"].items() if k.startswith(cid + "/")}
        if now != frozen:
            changed = sorted(set(now) ^ set(frozen) | {k for k in now if k in frozen and now[k] != frozen[k]})
            problems.append(f"case {cid} differs from frozen release {release_id}: {changed[:5]}")
    return {"release": rel, "problems": problems}


# ------------------------------------------------------------------ building and running one variant
def experiment_header(case: dict, variant: dict) -> dict:
    tpl = json.loads((case["_dir"] / "public" / variant.get("experiment", "experiment.json")).read_text())
    if variant.get("procedure"):
        tpl["procedure"] = {**tpl["procedure"], **variant["procedure"]}
    head = tpl["header"]
    for arm in head["arms"]:
        arm["params"] = {**arm.get("params", {}), **variant.get("params", {})}
    head["resolved_configuration"] = {**head["resolved_configuration"], **variant.get("config", {})}
    head["design"]["randomness"]["base_seed"] = int(variant.get("seed", head["design"]["randomness"]["base_seed"]))
    import mujoco  # noqa: PLC0415

    head["engines"] = [{"engine": "mujoco", "version": mujoco.__version__, "why": tpl.get("engine_why", "admitted executor")}]
    return tpl, head


def build(client, case: dict, variant: dict) -> dict:
    tpl, head = experiment_header(case, variant)
    d = client.draft_create(header=head)["draft_id"]
    pub = case["_dir"] / "public"
    client.model_file_put(draft_id=d, path=tpl["scene"], content=(pub / tpl["scene"]).read_text())
    client.procedure_put(draft_id=d, procedure=tpl["procedure"])
    for m in tpl.get("measurements", []):
        client.measurement_put(draft_id=d, measurement=m)
    for o in tpl.get("observations", []):
        client.observation_put(draft_id=d, observation=o)
    for path, spec in tpl.get("components", {}).items():
        client.component_put(draft_id=d, path=path, extension_point=spec["extension_point"], code=(pub / spec["file"]).read_text())
    return client.bind(draft_id=d)


def _summary(res: dict) -> dict:
    return {"run_id": res["run_id"], "run_kind": res["run_kind"], "status": res["status"], "status_reason": res["status_reason"],
            "evidence_level": res["evidence_level"], "anchoring": res["anchoring"],
            "trials": [{"trial_id": t["trial_id"], "arm_id": t["arm_id"], "condition": t["condition"],
                        "attempts": [{"status": a["status"], "invalid_reason": a["invalid_reason"], "stop": a["stop"],
                                      "state_digest": a["state_digest"]} for a in t["attempts"]],
                        "measurements": {m["measurement_id"]: m["value"] for m in t["measurements"]}} for t in res["trials"]],
            "checks": [{"check_id": c["check_id"], "check_kind": c["check_kind"], "status": c["status"],
                        **({"observed": c["observed"]} if c["check_kind"] == "replay_identity" else {})} for c in res["checks"]],
            "checkpoints": res["checkpoints"], "identity": res["identity"], "resources": res["resources"]}


def _traces(client, res: dict, signals: list[str], t_start: float | None = None) -> dict:
    out = {}
    first = res["trials"][0]["trial_id"] if res["trials"] else None
    for tr in res["traces"]:
        if tr["signal"] in signals and tr["trial_id"] == first:
            f = client.fetch(ref=tr["ref"], t_start=t_start, max_rows=200000)
            out[tr["signal"]] = f["rows"]
    return out


def run_variant(client, case: dict, variant: dict) -> dict:
    """Execute one variant through the tools and return normalized evidence (SIMLAB's original records)."""
    crit = json.loads((case["_dir"] / "referee" / "criteria.json").read_text())
    need = crit.get("traces", [])
    t0 = time.monotonic()
    ev: dict[str, Any] = {"case_id": case["id"], "variant_id": variant["id"], "procedure_kind": case["procedure_kind"]}
    b = build(client, case, variant)
    findings = client.validate(experiment=b["experiment"])["findings"]
    ev["validation_findings"] = findings
    if findings:
        ev["execution"] = {"launched": False, "status": "invalid_experiment"}
        return ev
    sub = client.submit(experiment=b["experiment"])
    client.wait(run_id=sub["run_id"], timeout_s=1800)
    res = client.result(run_id=sub["run_id"])
    ev["result"] = _summary(res)
    ev["traces"] = _traces(client, res, need)
    if res["trials"]:
        ev["events"] = [{k: e[k] for k in ("t", "event_id", "kind")} for e in
                        client.query(run_id=res["run_id"], trial_id=res["trials"][0]["trial_id"])["events"]]
    kind = case["procedure_kind"]
    if kind in {"determinism", "replay"}:
        again = client.submit(experiment=b["experiment"])
        client.wait(run_id=again["run_id"], timeout_s=1800)
        ev["second_run"] = _summary(client.result(run_id=again["run_id"]))
        rep = client.replay(run_id=sub["run_id"])
        client.wait(run_id=rep["run_id"], timeout_s=1800)
        ev["replay"] = _summary(client.result(run_id=rep["run_id"]))
    if kind == "determinism" and res["checkpoints"]:
        cp = next(c for c in res["checkpoints"] if c["trial_id"] == res["trials"][0]["trial_id"])
        br = client.branch(checkpoint_id=cp["checkpoint_id"])
        bexp = client.bind(draft_id=br["draft_id"])["experiment"]
        bs = client.submit(experiment=bexp)
        client.wait(run_id=bs["run_id"], timeout_s=1800)
        bres = client.result(run_id=bs["run_id"])
        ev["checkpoint"] = {"checkpoint_id": cp["checkpoint_id"], "time_s": cp["time_s"]}
        ev["branch"] = _summary(bres)
        ev["original_after_checkpoint"] = _traces(client, res, need, cp["time_s"])
        ev["branch_after_checkpoint"] = _traces(client, bres, need, cp["time_s"])
    ev["execution"] = {"launched": True, "terminal": True, "status": res["status"], "wall_s": round(time.monotonic() - t0, 3)}
    return ev


def grade(case: dict, evidence_path: Path, out_path: Path) -> dict:
    """Run the case's oracle in a separate, isolated interpreter (stdlib only; never SIMLAB code)."""
    crit = case["_dir"] / "referee" / "criteria.json"
    r = subprocess.run([sys.executable, "-I", str(BENCH / "run_oracle.py"), str(case["_dir"] / "oracle.py"), str(evidence_path), str(crit),
                        str(out_path)], capture_output=True, text=True, timeout=600, env={"PATH": "/usr/bin:/bin"}, cwd="/tmp")
    if r.returncode != 0 or not out_path.exists():
        g = {"checks": [{"id": "oracle", "status": "unavailable", "reason": f"oracle failed: {r.stderr[-1500:]}"}], "metrics": {},
             "critical_violations": ["oracle did not run"]}
        out_path.write_text(json.dumps(g, indent=1))
        return g
    return json.loads(out_path.read_text())


def outcome(variant: dict, g: dict) -> str:
    statuses = [c["status"] for c in g.get("checks", [])]
    if not statuses or "unavailable" in statuses or g.get("critical_violations"):
        return "BLOCKED" if "unavailable" in statuses else "FAIL"
    passed = all(s == "pass" for s in statuses)
    if variant.get("negative_control"):
        return "PASS" if not passed else "FAIL"  # a negative control must be caught
    return "PASS" if passed else "FAIL"


def inventory() -> dict:
    from simlab.runner.core import hardware_inventory, run_identity  # noqa: PLC0415

    data = Path(os.environ.get("SIMLAB_DATA_DIR", "/tmp"))
    return {"hardware": hardware_inventory(data if data.exists() else Path("/tmp")), "identity": run_identity(),
            "python": platform.python_version()}


def run_profile(client, *, profile: str, cases: list[str] | None, family: str | None, release: str | None, output: Path,
                compute_log: Path | None = None, task: str = "PAS-M1-001") -> dict:
    prof = json.loads((PROFILES / f"{profile}.json").read_text())
    ids = cases or [c for c in all_cases() if family is None or load_case(c)["family"] == family]
    run_id = time.strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:6]
    out = output / run_id
    out.mkdir(parents=True)
    rel = verify_release(release, ids) if release else {"release": None, "problems": ["no frozen release named (development run)"]}
    (out / "release-check.json").write_text(json.dumps({"release_id": release, "problems": rel["problems"]}, indent=1))
    if release and rel["problems"]:
        raise SystemExit("frozen release check failed: " + "; ".join(rel["problems"]))
    (out / "profile.json").write_text(json.dumps({"profile": profile, **prof, "cases": ids}, indent=1))
    rows = []
    t_all = time.monotonic()
    for cid in ids:
        case = load_case(cid)
        variants = case["variants"] if prof["variants"] == "all" else case["variants"][:1]
        for v in variants:
            for rep in range(int(prof["repeats"])):
                cell = out / cid / v["id"] / f"repeat-{rep + 1}"
                cell.mkdir(parents=True)
                (cell / "inventory.json").write_text(json.dumps(inventory(), indent=1, default=str))  # B17: before the run
                t0 = time.monotonic()
                try:
                    ev = run_variant(client, case, v)
                except Exception as exc:  # kept, never retried (B08)
                    ev = {"case_id": cid, "variant_id": v["id"], "execution": {"launched": False, "status": "harness_error",
                                                                              "error": f"{type(exc).__name__}: {exc}"[:2000]}}
                wall = time.monotonic() - t0
                (cell / "evidence.json").write_text(json.dumps(ev, indent=1, default=str))
                g = grade(case, cell / "evidence.json", cell / "grade.json")
                res = (ev.get("result") or {}).get("resources") or {}
                row = {"family": case["family"], "case_id": cid, "tb_id": case.get("tb_id"), "variant_id": v["id"], "repeat": rep + 1,
                       "negative_control": bool(v.get("negative_control")), "split": v.get("split"),
                       "outcome": outcome(v, g), "execution_status": (ev.get("execution") or {}).get("status"),
                       "metrics": g.get("metrics", {}), "checks": [{k: c.get(k) for k in ("id", "status", "reason")} for c in g.get("checks", [])],
                       "run_id": (ev.get("result") or {}).get("run_id"), "wall_s": round(wall, 3), "simlab_resources": res}
                rows.append(row)
                if compute_log is not None:
                    from simlab.resources import compute_log_append  # noqa: PLC0415
                    compute_log_append(compute_log, task=task, what=f"bench {profile} {cid}/{v['id']} repeat {rep + 1}", wall_s=round(wall, 3),
                                       cpu_s=res.get("cpu_s"), peak_ram_mb=res.get("peak_ram_mb"), peak_vram_mb=None,
                                       disk_mb=res.get("disk_written_mb"), notes=f"outcome {row['outcome']}; run {row['run_id']}")
    report = {"schema": "simlab-bench-report:1", "run_id": run_id, "profile": profile, "release": release,
              "release_problems": rel["problems"], "wall_s": round(time.monotonic() - t_all, 2), "families": {}}
    for r in rows:
        fam = report["families"].setdefault(r["family"], {"cases": {}})
        fam["cases"].setdefault(r["case_id"], []).append(r)
    for fam, body in report["families"].items():
        cells = [r for rs in body["cases"].values() for r in rs]
        body["counts"] = {k: sum(1 for r in cells if r["outcome"] == k) for k in ("PASS", "FAIL", "BLOCKED")}
        body["note"] = "Per-case results; there is no aggregate score."
        (out / f"family_{fam}.json").write_text(json.dumps(body, indent=1, default=str))
        (out / f"family_{fam}.md").write_text(render_md(fam, body))
    (out / "report.json").write_text(json.dumps(report, indent=1, default=str))
    return {"report_dir": str(out), "families": {f: b["counts"] for f, b in report["families"].items()}, "wall_s": report["wall_s"]}


def render_md(fam: str, body: dict) -> str:
    lines = [f"# SIMLAB-Bench family {fam}", "", "Per case, variant and repeat. No aggregate score.", "",
             "| Case | Variant | Repeat | Negative control | Outcome | Primary metric | Value | Tolerance | Run |", "|---|---|---|---|---|---|---|---|---|"]
    for cid, rows in body["cases"].items():
        for r in rows:
            m = r["metrics"]
            lines.append(f"| {cid} | {r['variant_id']} | {r['repeat']} | {'yes' if r['negative_control'] else ''} | {r['outcome']} | "
                         f"{m.get('primary_metric', '')} | {m.get('primary_value', '')} | {m.get('tolerance', '')} | {r['run_id']} |")
    lines += ["", f"Counts: {body['counts']}"]
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------ speed and cost (MuJoCo testspeed equivalent)
SPEED_SCENE = """<mujoco model="speed">
  <option timestep="0.002"/>
  <worldbody>
    <geom name="floor" type="plane" size="5 5 0.1"/>
    {boxes}
    <body name="arm" pos="0 0 1.5"><joint name="hinge" type="hinge" axis="0 1 0"/>
      <geom type="capsule" fromto="0 0 0 0 0 -0.5" size="0.03" mass="1"/></body>
  </worldbody>
  <actuator><motor name="m" joint="hinge" ctrlrange="-5 5"/></actuator>
</mujoco>"""


def speed(n_steps: int = 20000, n_boxes: int = 20) -> dict:
    import resource  # noqa: PLC0415

    import mujoco  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

    boxes = "\n    ".join(f'<body pos="{(i % 5) * 0.25 - 0.5} {(i // 5) * 0.25 - 0.5} {0.2 + 0.12 * i}"><freejoint/>'
                           f'<geom type="box" size="0.05 0.05 0.05" mass="0.2"/></body>' for i in range(n_boxes))
    m = mujoco.MjModel.from_xml_string(SPEED_SCENE.format(boxes=boxes))
    d = mujoco.MjData(m)
    rng = np.random.default_rng(0)
    for _ in range(500):
        mujoco.mj_step(m, d)  # settle into active contact
    t0, c0 = time.perf_counter(), time.process_time()
    ncon = 0
    for i in range(n_steps):
        d.ctrl[0] = float(rng.uniform(-5, 5))
        mujoco.mj_step(m, d)
        ncon += d.ncon
    wall, cpu = time.perf_counter() - t0, time.process_time() - c0
    return {"record": "simlab-speed", "harness": "Python loop equivalent of MuJoCo testspeed (the 3.17.0 wheel ships no testspeed binary; plan U-06)",
            "mujoco": mujoco.__version__, "scene": f"{n_boxes} free boxes on a plane plus an actuated hinge with random control",
            "nbody": m.nbody, "nv": m.nv, "timestep": m.opt.timestep, "steps": n_steps, "wall_s": round(wall, 4), "cpu_s": round(cpu, 4),
            "steps_per_s": round(n_steps / wall, 1), "realtime_factor": round(n_steps * m.opt.timestep / wall, 2),
            "mean_contacts": round(ncon / n_steps, 2), "peak_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1),
            "inventory": inventory()}
