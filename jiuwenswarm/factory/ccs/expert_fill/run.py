"""CC v2 native entry of engine.build_expert_fill: one JSON packet on stdin, one JSON result on stdout.

Capability `verify` checks a change that adds demand-driven parallel expert fill to llama.cpp:
  fixture               the bundled good diff passes and each planted fault fails its rule on this base
  native CC execution   static rules on the change under review (scope, gate default off, fill before the
                        expert matmul, no tensor writes, no graph change)
  compile               CPU build of llama-simple and llama-perplexity from base + the change (scratch dir)
  runtime acceptance    on a tiny MoE pack: greedy output byte-identical to stock with the gate unset and set
                        (resident-skip on and off), activation marker only with the gate set, fill stats
                        nonzero with the gate set, prefill not filled by default, perplexity with fill on every
                        ubatch finite and equal to stock; reached only when all of them ran and passed
`done` needs require_stage (default runtime acceptance): a check that stage needs and that was skipped, or a
stage not reached, leaves it false; an inconclusive check counts only when runtime acceptance passed.
Nothing is written inside the checkout. Pass absolute paths.
"""
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "helpers"))
import checkout as co  # noqa: E402
import fill_rules  # noqa: E402
import fill_runs  # noqa: E402
import patchlib  # noqa: E402

FIXTURE, STATIC, COMPILE, RUNTIME = "fixture", "native CC execution", "compile", "runtime acceptance"
LADDER = (FIXTURE, STATIC, COMPILE, RUNTIME)
FIXTURES = HERE / "tests" / "fixtures"
PLANTED = {"gate-default-on.diff": "gate_default_off", "fill-after-matmul.diff": "fill_before_matmul",
           "fill-writes-tensor.diff": "no_tensor_writes", "touches-ggml-cpu.diff": "allowed_paths"}
TARGETS = ("llama-simple", "llama-perplexity")
ACCEPTANCE = ("parity_gate_unset", "parity_gate_set", "marker_only_with_gate", "fill_stats", "prefill_not_filled",
              "no_nan")
DEFAULT_PACK = "tiny-q2exps.gguf"
ON = {"LLAMA_EXPERT_FILL": "1"}


def check(name, status, detail, stage):
    return {"name": name, "status": status, "stage": stage, "detail": detail}


def stage_reached(checks):
    reached = None
    for stage in LADDER:
        here = [c["status"] for c in checks if c["stage"] == stage]
        if "fail" in here or "skipped" in here:
            break
        if "pass" in here:
            reached = stage
    return reached


def result(checks, require=None):
    why = []
    failed = [c["name"] for c in checks if c["status"] == "fail"]
    if failed:
        why.append(f"failed: {failed}")
    reached = stage_reached(checks)
    if require:
        need = LADDER.index(require)
        skipped = [c["name"] for c in checks if c["status"] == "skipped" and LADDER.index(c["stage"]) <= need]
        if skipped:
            why.append(f"skipped but needed for {require}: {skipped}")
        if reached is None or LADDER.index(reached) < need:
            why.append(f"reached {reached or 'no stage'}, {require} required")
    undecided = [c["name"] for c in checks if c["status"] == "inconclusive"]
    if undecided and reached != RUNTIME:
        why.append(f"inconclusive {undecided} and runtime acceptance did not pass (the runtime stage decides them)")
    return {"done": bool(checks) and not why, "checks": checks, "stage_reached": reached, "not_done_because": why}


def calibrate(pre_reader):
    """Fixtures that do not apply (a base other than stock 9048bad8) leave the rules uncalibrated: inconclusive."""
    if not FIXTURES.is_dir():
        return check("fixture_calibration", "inconclusive", "no bundled fixtures in this release: runtime "
                     "acceptance decides", FIXTURE)
    outcomes, missed = {}, []
    for name in ["good.diff", *PLANTED]:
        try:
            files = patchlib.parse_patch((FIXTURES / name).read_text(encoding="utf-8"))
            patchlib.post_images(files, pre_reader)  # the fixture must apply to this base
            checks = fill_rules.fill_checks(files)
        except (OSError, patchlib.PatchError) as exc:
            return check("fixture_calibration", "inconclusive", f"{name} does not apply to this base ({exc}); the "
                         "fixtures target stock 9048bad8, so runtime acceptance decides", FIXTURE)
        failed = sorted(c["name"] for c in checks if c["status"] == "fail")
        outcomes[name] = failed or "passes"
        if name == "good.diff" and (failed or any(c["status"] == "inconclusive" for c in checks)):
            missed.append(f"good.diff does not pass cleanly: {failed or 'inconclusive'}")
        elif name != "good.diff" and PLANTED[name] not in failed:
            missed.append(f"{name} did not fail {PLANTED[name]}")
    if missed:
        return check("fixture_calibration", "fail", "rules not calibrated on this tree: " + "; ".join(missed), FIXTURE)
    return check("fixture_calibration", "pass", outcomes, FIXTURE)


def build(src, build_dir, jobs, log):
    """CPU Release build of the targets. Returns (ok, detail); ok None when cmake is missing."""
    cmake = shutil.which("cmake")
    if not cmake:
        return None, "cmake not found"
    gen = ["-G", "Ninja"] if shutil.which("ninja") else []
    configure = [cmake, "-S", str(src), "-B", str(build_dir), *gen, "-DCMAKE_BUILD_TYPE=Release", "-DGGML_CUDA=OFF",
                 "-DGGML_NATIVE=ON", "-DLLAMA_BUILD_TESTS=OFF", "-DLLAMA_BUILD_SERVER=OFF", "-DLLAMA_CURL=OFF",
                 "-DLLAMA_OPENSSL=OFF"]
    steps = [configure, [cmake, "--build", str(build_dir), "--target", *TARGETS, "-j", str(jobs)]]
    with open(log, "wb") as handle:
        for step in steps:
            command, _ = co.capped(step, None)
            proc = subprocess.run(command, stdout=handle, stderr=subprocess.STDOUT, timeout=3600)
            if proc.returncode:
                tail = Path(log).read_bytes()[-1500:].decode(errors="replace")
                return False, f"{Path(step[0]).name} {step[1]} exited {proc.returncode}: {tail}"
    missing = [t for t in TARGETS if not (build_dir / "bin" / t).is_file()]
    if missing:
        return False, f"built, but {missing} not in {build_dir / 'bin'}"
    return True, str(build_dir / "bin")


def finite(value):
    try:
        return value is not None and math.isfinite(float(value))
    except ValueError:
        return False


def runtime(inputs, checkout, head, work, src, require):
    """Stock build (or stock_bin), then the acceptance runs. Returns checks."""
    missing = "fail" if require == RUNTIME else "skipped"
    if not inputs.get("tiny_dir"):
        return [check("runtime_acceptance", missing, "no tiny_dir: parity and fill runs not done", RUNTIME)]
    pack = Path(inputs["tiny_dir"]) / inputs.get("pack", DEFAULT_PACK)
    if not pack.is_file():
        return [check("tiny_pack_present", "fail", f"{pack} missing", RUNTIME)]
    cap = inputs.get("mem_cap", "16G")
    jobs = int(inputs.get("jobs", 8))
    cand = work / "cand-build" / "bin"
    checks = []

    stock = inputs.get("stock_bin")
    if stock:
        stock = Path(stock)
        if not all((stock / t).is_file() for t in TARGETS):
            return [check("stock_bin", "fail", f"{stock} lacks {list(TARGETS)}", COMPILE)]
    else:
        root = Path(inputs["work_dir"]) if inputs.get("work_dir") else work
        stock_dir = root / f"stock-fill-{head[:12]}"
        if not all((stock_dir / "build" / "bin" / t).is_file() for t in TARGETS):
            stock_src = co.export_tree(checkout, stock_dir / "src", base=head)
            ok, detail = build(stock_src, stock_dir / "build", jobs, stock_dir / "build.log")
            if not ok:
                return [check("stock_build", "fail" if ok is False or require == RUNTIME else "skipped", detail,
                              COMPILE)]
        stock = stock_dir / "build" / "bin"
        checks.append(check("stock_build", "info", f"stock {head[:12]} at {stock}", COMPILE))

    rc_s, out_s, err_s, note = fill_runs.simple(stock, pack, co.capped, cap)
    if rc_s or len(out_s) <= len(fill_runs.PROMPT):
        return checks + [check("stock_reference", "fail", f"stock llama-simple rc {rc_s}: {err_s[-400:]}", RUNTIME)]
    acc = []
    rc0, out0, err0, _ = fill_runs.simple(cand, pack, co.capped, cap)
    ok = rc0 == 0 and out0 == out_s
    acc.append(check("parity_gate_unset", "pass" if ok else "fail",
                     f"greedy llama-simple -n 32 on {pack.name}, {fill_runs.GATE} unset: stdout byte-identical to "
                     f"stock ({len(out0)} bytes; {note})" if ok else
                     f"rc {rc0}; outputs differ: {out0[-160:]!r} vs stock {out_s[-160:]!r} {err0[-300:]}", RUNTIME))
    rc1, out1, err1, _ = fill_runs.simple(cand, pack, co.capped, cap, env=ON)
    cold = {**ON, "LLAMA_EXPERT_FILL_SKIP_RESIDENT": "0"}
    rc2, out2, err2, _ = fill_runs.simple(cand, pack, co.capped, cap, env=cold)
    ok = rc1 == 0 and rc2 == 0 and out1 == out_s and out2 == out_s
    acc.append(check("parity_gate_set", "pass" if ok else "fail",
                     f"{fill_runs.GATE}=1 (resident skip on, and off with LLAMA_EXPERT_FILL_SKIP_RESIDENT=0): both "
                     "stdouts byte-identical to stock" if ok else
                     f"rc {rc1}/{rc2}; gate-set output {'matches' if out1 == out_s else 'differs'}, read-all output "
                     f"{'matches' if out2 == out_s else 'differs'}: {out1[-160:]!r} {err1[-300:]} {err2[-300:]}",
                     RUNTIME))
    m0, m1 = fill_runs.markers(err0), fill_runs.markers(err1)
    stray = [ln for ln in err0.splitlines() if "expert_fill" in ln]
    ok = not stray and len(m1) == 1
    acc.append(check("marker_only_with_gate", "pass" if ok else "fail",
                     f"gate set: {m1[0].strip()!r}; gate unset: no expert_fill line" if ok else
                     f"gate unset printed {stray[:3]}; gate set printed {len(m1)} active markers {m1[:2]} "
                     "(want exactly one per context)", RUNTIME))
    s1, s2 = fill_runs.stats(err1), fill_runs.stats(err2)
    need = ("calls", "bytes_read", "reads", "fill_us")
    problems = []
    for label, s in (("gate set", s1), ("read-all", s2)):
        if s is None:
            problems.append(f"{label}: no 'expert_fill: stats' line")
        elif [k for k in need if k not in s]:
            problems.append(f"{label}: stats lack {[k for k in need if k not in s]}")
    if not problems:
        if s1["calls"] <= 0:
            problems.append(f"gate set: calls={s1['calls']} (the fill never ran on a decode token)")
        if s2["calls"] <= 0 or s2["reads"] <= 0 or s2["bytes_read"] <= 0:
            problems.append(f"read-all: calls={s2['calls']} reads={s2['reads']} bytes_read={s2['bytes_read']} "
                            "(the read pool never read)")
        if s2.get("read_errors", 0):
            problems.append(f"read-all: read_errors={s2['read_errors']}")
    acc.append(check("fill_stats", "fail" if problems else "pass", problems or
                     {"gate_set": s1, "read_all": s2}, RUNTIME))
    rcp, _, errp, _ = fill_runs.simple(cand, pack, co.capped, cap, env=cold, n=1)
    sp = fill_runs.stats(errp)
    ok = rcp == 0 and sp is not None and sp.get("calls", -1) == 0
    acc.append(check("prefill_not_filled", "pass" if ok else "fail",
                     "prompt-only run (-n 1) with the gate set: stats calls=0 (decode-only by default)" if ok else
                     f"prompt-only run rc {rcp}, stats {sp}: the default fill touches prefill ubatches", RUNTIME))

    text = Path(inputs.get("text") or (src / "README.md"))
    every = {**cold, "LLAMA_EXPERT_FILL_MAX_TOKENS": "0"}
    rps, ppl_s, errps = fill_runs.perplexity(stock, pack, text, co.capped, cap, jobs=jobs)
    rpc, ppl_c, errpc = fill_runs.perplexity(cand, pack, text, co.capped, cap, env=every, jobs=jobs)
    spc = fill_runs.stats(errpc) or {}
    ok = rps == 0 and rpc == 0 and finite(ppl_c) and ppl_c == ppl_s and spc.get("calls", 0) > 0
    acc.append(check("no_nan", "pass" if ok else "fail",
                     f"llama-perplexity -c 128 --chunks 4 with the fill on every ubatch (calls={spc.get('calls')}): "
                     f"PPL {ppl_c} finite and equal to stock {ppl_s}" if ok else
                     f"rc {rpc} (stock {rps}); PPL {ppl_c} vs stock {ppl_s}; fill calls {spc.get('calls')}: "
                     f"{errpc[-300:]}", RUNTIME))
    return checks + acc


def required_stage(inputs):
    stage = inputs.get("require_stage") or RUNTIME
    if stage not in LADDER:
        raise ValueError(f"require_stage must be one of {list(LADDER)}, not {stage!r}")
    return stage


def do_verify(inputs):
    checks = []
    require = required_stage(inputs)
    try:
        change = co.review_change(inputs["checkout"], inputs.get("diff_path"), inputs.get("base"),
                                  inputs.get("carried_diff"))
        files, post, pre = change["files"], change["post"], change["pre"]
        static_checks = fill_rules.fill_checks(files)
    except (KeyError, OSError, ValueError) as exc:
        return result([check("patch_input", "fail", f"{type(exc).__name__}: {exc}", STATIC)], require)
    checkout, head = change["checkout"], change["head"]
    carried = f"; carried from an earlier node, not reviewed: {change['carried']}" if change["carried"] else ""
    checks.append(check("patch_input", "pass", f"{change['mode']} change against {head[:12]}: {sorted(post)}{carried}",
                        STATIC))
    checks.append(calibrate(pre))
    checks += static_checks
    forced = bool(inputs.get("runtime_even_if_static_fails"))
    if (any(c["status"] == "fail" for c in static_checks) and not forced) or inputs.get("build") is False:
        why = "static gate failed" if inputs.get("build") is not False else "build: false"
        return result(checks + [check("compile", "skipped", f"{why}; not built", COMPILE),
                                check("runtime_acceptance", "skipped", f"{why}; not run", RUNTIME)], require)
    owned = inputs.get("work_dir")
    if owned:
        Path(owned).mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="expert-fill-verify-", dir=owned))
    try:
        src = co.export_tree(checkout, work / "cand-src", post={**change["carried_post"], **post}, base=head)
        ok, detail = build(src, work / "cand-build", int(inputs.get("jobs", 8)), work / "cand-build.log")
        status = {True: "pass", False: "fail", None: "fail" if require in (COMPILE, RUNTIME) else "skipped"}[ok]
        checks.append(check("compile", status, detail, COMPILE))
        if not ok:
            return result(checks + [check("runtime_acceptance", "skipped", "no candidate build", RUNTIME)], require)
        rt = runtime(inputs, checkout, head, work, src, require)
        ran = {c["name"] for c in rt if c["name"] in ACCEPTANCE and c["status"] in ("pass", "fail")}
        if ran != set(ACCEPTANCE):
            for c in rt:
                if c["stage"] == RUNTIME and c["status"] == "pass":
                    c["status"], c["detail"] = "info", f"{c['detail']} (runtime acceptance needs all of {list(ACCEPTANCE)})"
            if not any(c["status"] == "fail" for c in rt):
                rt.append(check("runtime_acceptance", "fail", f"ran {sorted(ran)} of {list(ACCEPTANCE)}", RUNTIME))
        checks += rt
        if inputs.get("keep_work"):
            checks.append(check("work_dir", "info", str(work), RUNTIME))
        return result(checks, require)
    except subprocess.TimeoutExpired as exc:
        return result(checks + [check("runtime_acceptance", "fail", f"timed out: {exc}", RUNTIME)], require)
    finally:
        if not inputs.get("keep_work"):
            shutil.rmtree(work, ignore_errors=True)


def main():
    packet = json.load(sys.stdin)
    if packet.get("capability") != "verify":
        print(json.dumps({"outcome": "error", "error": {"code": "INVALID_INPUT", "message": "Expected the verify capability"}}))
        return
    try:
        outputs = do_verify(packet.get("inputs", {}))
    except (KeyError, OSError, TypeError, ValueError) as exc:
        outputs = result([check("verification_input", "fail", f"{type(exc).__name__}: {exc}", STATIC)])
    print(json.dumps({"outcome": "ok", "outputs": outputs}))


if __name__ == "__main__":
    main()
