"""CC v2 native entry of weights.build_expert_scale_wiring: one JSON packet on stdin, one JSON result on stdout.

Capability `verify` checks a change that wires the per-expert NVFP4 scales into the Muse graph:
  fixture               the bundled good diff passes and each planted fault fails its rule on this base
  native CC execution   static rules on the change under review (scope, scale arguments, nothing else moved)
  compile               CPU build of llama-simple and llama-perplexity from base + the change (scratch dir)
  runtime acceptance    on the tiny packs: scale-free parity with stock, NVFP4 KLD vs the dequantized
                        reference, no NaN, and the first quantized layer's expert matmuls and block output
                        vs the reference; reached only when all four ran and passed
`done` needs require_stage (default runtime acceptance): a check that stage needs and that was skipped, or a
stage not reached, leaves it false; an inconclusive check counts only when runtime acceptance passed.
`stage_reached` is the highest stage whose checks, and those of every lower stage, passed.
This process spawns native binaries only (git, cmake, the llama.cpp tools); the helpers run in-process.
Nothing is written inside the checkout. Pass absolute paths.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "helpers"))
import checkout as co  # noqa: E402
import patchlib  # noqa: E402
import wiring_rules  # noqa: E402
from fixture_scope import DEMO_TASK, SCOPE_ENV, inherited_cap, require_scope  # noqa: E402
from gguf_pack import load_pack  # noqa: E402
from kld_compare import finite, kld  # noqa: E402
from llama_runs import PROMPT, eval_callback, simple  # noqa: E402
from slice_compare import compare as compare_slices  # noqa: E402

FIXTURE, STATIC, COMPILE, RUNTIME = "fixture", "native CC execution", "compile", "runtime acceptance"
LADDER = (FIXTURE, STATIC, COMPILE, RUNTIME)
FIXTURES = HERE / "tests" / "fixtures"
PLANTED = {"up-gets-gate-scale.diff": "scale_args", "down-scale-missing.diff": "scale_args",
           "touches-ggml.diff": "allowed_paths"}
MODEL_FILE, HEADER = wiring_rules.MODEL_FILE, "src/llama-graph.h"
TARGETS = ("llama-simple", "llama-perplexity", "llama-eval-callback")
ACCEPTANCE = ("scale_free_parity", "nvfp4_kld", "no_nan", "expert_slice")
PACKS = {"bf16_pack": "tiny-bf16.gguf", "nvfp4_pack": "tiny-nvfp4-f32.gguf", "ref_pack": "tiny-deqref-f32.gguf"}


def check(name, status, detail, stage):
    return {"name": name, "status": status, "stage": stage, "detail": detail}


def stage_reached(checks):
    """Highest stage with a passing check such that no check of it or of a lower stage failed or was skipped."""
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


def static(files, post, pre_reader):
    return wiring_rules.wiring_checks(files, pre_reader(MODEL_FILE), post.get(MODEL_FILE), pre_reader(HEADER))


def calibrate(pre_reader):
    """Fixtures that do not apply (a base other than stock 9048bad8) leave the rules uncalibrated: inconclusive."""
    if not FIXTURES.is_dir():
        return check("fixture_calibration", "inconclusive", "no bundled fixtures in this release: the static rules "
                     "are not calibrated here; runtime acceptance decides", FIXTURE)
    outcomes, missed = {}, []
    for name in ["good.diff", *PLANTED]:
        try:
            files = patchlib.parse_patch((FIXTURES / name).read_text(encoding="utf-8"))
            checks = static(files, patchlib.post_images(files, pre_reader), pre_reader)
        except (OSError, patchlib.PatchError) as exc:
            return check("fixture_calibration", "inconclusive",
                         f"{name} does not apply to this base ({exc}); the fixtures target stock 9048bad8, so the "
                         "static rules are not calibrated here and runtime acceptance decides", FIXTURE)
        failed = sorted(c["name"] for c in checks if c["status"] == "fail")
        outcomes[name] = failed or "passes"
        if name == "good.diff" and failed:
            missed.append(f"good.diff fails {failed}")
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


def pack_census(path):
    pack = load_pack(path)
    T = pack["tensors"]
    scales = [n for n in T if n.endswith("_exps.scale")]
    nvfp4 = [n for n, r in T.items() if r["type"] == "nvfp4"]
    return scales, nvfp4


def sha256(path, chunk=1 << 22):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        while block := handle.read(chunk):
            h.update(block)
    return h.hexdigest()


def pinned_digests(manifest_path):
    """{file name: sha256} from a tiny packs manifest ({"files": {name: sha}} or {"files": [{name, sha256}]}
    or a plain {name: sha})."""
    data = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    files = data.get("files", data) if isinstance(data, dict) else data
    if isinstance(files, list):
        return {Path(f.get("name") or f.get("path")).name: f.get("sha256") for f in files}
    return {Path(k).name: v for k, v in files.items() if isinstance(v, str)}


def pack_inputs(inputs, packs):
    """Judge the tiny packs themselves (not the change). Returns checks."""
    checks = []
    for key, path in packs.items():
        if not path.is_file():
            checks.append(check(f"{key}_present", "fail", f"{path} missing", STATIC))
    if checks:
        return checks
    digests = {key: sha256(path) for key, path in packs.items()}
    same = [f"{a} and {b}" for a, b in (("ref_pack", "nvfp4_pack"), ("bf16_pack", "nvfp4_pack"), ("bf16_pack", "ref_pack"))
            if packs[a].resolve() == packs[b].resolve() or digests[a] == digests[b]]
    checks.append(check("tiny_packs_distinct", "fail" if same else "pass",
                        f"{'; '.join(same)} are the same file or bytes: a pack compared with itself proves nothing"
                        if same else {k: v[:16] for k, v in digests.items()}, STATIC))
    if inputs.get("tiny_packs_manifest"):
        try:
            pinned = pinned_digests(inputs["tiny_packs_manifest"])
            bad = [f"{p.name}: {digests[k][:16]} != pinned {str(pinned.get(p.name))[:16]}" for k, p in packs.items()
                   if pinned.get(p.name) != digests[k]]
            checks.append(check("tiny_packs_pinned", "fail" if bad else "pass", bad or
                                f"all three packs match {Path(inputs['tiny_packs_manifest']).name}", STATIC))
        except (OSError, ValueError, AttributeError, TypeError) as exc:
            checks.append(check("tiny_packs_pinned", "fail", f"tiny_packs_manifest unreadable: {exc}", STATIC))
    scales, _ = pack_census(packs["bf16_pack"])
    checks.append(check("parity_pack_scale_free", "fail" if scales else "pass",
                        f"{packs['bf16_pack'].name} has .scale tensors {scales[:4]}: not a scale-free pack" if scales
                        else f"{packs['bf16_pack'].name}: no expert .scale tensor", STATIC))
    scales, nvfp4 = pack_census(packs["nvfp4_pack"])
    checks.append(check("numerics_pack_scaled", "pass" if scales and nvfp4 else "fail",
                        f"{packs['nvfp4_pack'].name}: {len(nvfp4)} NVFP4 tensors, {len(scales)} expert .scale tensors", STATIC))
    ref_scales, ref_nvfp4 = pack_census(packs["ref_pack"])
    checks.append(check("reference_pack_dequantized", "fail" if ref_nvfp4 or ref_scales else "pass",
                        f"{packs['ref_pack'].name} holds {len(ref_nvfp4)} NVFP4 tensors and {len(ref_scales)} .scale "
                        "tensors: not a dequantized reference" if ref_nvfp4 or ref_scales
                        else f"{packs['ref_pack'].name}: no NVFP4 tensor, no .scale", STATIC))
    return checks


def tiny_packs(inputs):
    return {k: Path(inputs["tiny_dir"]) / inputs.get(k, v) for k, v in PACKS.items()} if inputs.get("tiny_dir") else None


def runtime(inputs, checkout, head, work, src, require):
    """Stock build or stock_bin, then the four runtime acceptance checks (packs already judged). Returns checks."""
    missing = "fail" if require == RUNTIME else "skipped"
    packs = tiny_packs(inputs)
    if not packs:
        return [check("runtime_acceptance", missing, "no tiny_dir: parity and numerics not run", RUNTIME)]
    cap = inputs.get("mem_cap", "16G")
    capped = inherited_cap if os.environ.get(SCOPE_ENV) else co.capped
    jobs = int(inputs.get("jobs", 8))
    cand_bin = work / "cand-build" / "bin"
    checks = []
    _, nvfp4 = pack_census(packs["nvfp4_pack"])
    layer = min((int(n.split(".")[1]) for n in nvfp4 if n.startswith("blk.")), default=None)

    # stock binaries for the parity reference
    stock = inputs.get("stock_bin")
    if stock:
        stock = Path(stock)
        if not (stock / "llama-simple").is_file():
            return checks + [check("stock_bin", "fail", f"{stock}/llama-simple missing", STATIC)]
    else:
        root = Path(inputs["work_dir"]) if inputs.get("work_dir") else work
        stock_dir = root / f"stock-{head[:12]}"
        if not (stock_dir / "build" / "bin" / "llama-simple").is_file():
            stock_src = co.export_tree(checkout, stock_dir / "src", base=head)
            ok, detail = build(stock_src, stock_dir / "build", jobs, stock_dir / "build.log")
            if not ok:
                return checks + [check("stock_build", "fail" if ok is False or require == RUNTIME else "skipped",
                                       detail, COMPILE)]
        stock = stock_dir / "build" / "bin"
        checks.append(check("stock_build", "info", f"stock {head[:12]} at {stock}", COMPILE))

    acceptance = []
    rc_c, out_c, err_c, note = simple(cand_bin, packs["bf16_pack"], capped, cap)
    rc_s, out_s, err_s, _ = simple(stock, packs["bf16_pack"], capped, cap)
    same = rc_c == 0 and rc_s == 0 and out_c == out_s and len(out_c) > len(PROMPT)
    acceptance.append(check("scale_free_parity", "pass" if same else "fail",
                      f"greedy llama-simple -n 32 on {packs['bf16_pack'].name}: stdout byte-identical to stock "
                      f"({len(out_c)} bytes; {note})" if same else
                      f"candidate rc {rc_c}, stock rc {rc_s}, outputs {'differ' if out_c != out_s else 'empty'}: "
                      f"{out_c[-200:]!r} vs {out_s[-200:]!r} {err_c[-300:]}", RUNTIME))

    text = Path(inputs.get("text") or (src / "README.md"))
    prefix, note = capped([], cap)
    res, base = kld(str(cand_bin / "llama-perplexity"), packs["ref_pack"], packs["nvfp4_pack"], text,
                    work / "kld", threads=jobs, prefix=prefix)
    limit = float(inputs.get("kld_max", 0.005))
    value = res.get("mean_kld")
    ran = base is not None and res.get("rc") == 0 and value is not None
    acceptance.append(check("nvfp4_kld", "pass" if ran and finite([value]) and value <= limit else "fail",
                      f"mean KLD {value} vs {packs['ref_pack'].name} (limit {limit}; PPL(Q) {res.get('ppl_q')}, "
                      f"PPL(base) {res.get('ppl_base')}, same top p {res.get('same_top_p')}%; {note})" if ran
                      else f"perplexity failed: {res}", RUNTIME))
    vals = [res.get("mean_kld"), res.get("ppl_q")]
    acceptance.append(check("no_nan", "pass" if ran and finite(vals) else "fail",
                      f"KLD and PPL finite: {vals}" if ran and finite(vals) else f"non-finite or missing: {vals}", RUNTIME))
    rc_a = eval_callback(cand_bin, packs["nvfp4_pack"], work / "cb-nvfp4.log", capped, cap, jobs)
    rc_b = eval_callback(cand_bin, packs["ref_pack"], work / "cb-ref.log", capped, cap, jobs)
    tol = float(inputs.get("slice_tol", 0.05))
    if rc_a or rc_b or layer is None:
        acceptance.append(check("expert_slice", "fail", f"llama-eval-callback exited {rc_a} / {rc_b} (layer {layer})", RUNTIME))
    else:
        cmp = compare_slices(work / "cb-nvfp4.log", work / "cb-ref.log", layer, tol)
        acceptance.append(check("expert_slice", "pass" if cmp["ok"] else "fail",
                          f"layer {layer} expert matmuls and block output vs {packs['ref_pack'].name}: worst "
                          f"max|d|/max|ref| {cmp['worst_rel_err']:.3g} (tol {tol}); " + "; ".join(
                              f"{r['tensor']} {r['rel_err']:.3g}" if "rel_err" in r else f"{r['tensor']} {r['error']}"
                              for r in cmp["tensors"]), RUNTIME))
    if base is not None:
        ctl, _ = kld(str(Path(stock) / "llama-perplexity"), packs["ref_pack"], packs["nvfp4_pack"], text,
                     work / "kld-stock", threads=jobs, prefix=prefix, base=base)
        checks.append(check("stock_control", "info", f"stock graph on the same NVFP4 pack: mean KLD {ctl.get('mean_kld')}, "
                            f"PPL(Q) {ctl.get('ppl_q')} (scales ignored: expected NaN or far above the limit)", RUNTIME))
    return checks + acceptance


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
        static_checks = static(files, post, pre)
    except (KeyError, OSError, ValueError) as exc:
        return result([check("patch_input", "fail", f"{type(exc).__name__}: {exc}", STATIC)], require)
    checkout, head = change["checkout"], change["head"]
    carried = f"; carried from the earlier node, not reviewed: {change['carried']}" if change["carried"] else ""
    checks.append(check("patch_input", "pass", f"{change['mode']} change against {head[:12]}: {sorted(post)}{carried}",
                        STATIC))
    checks.append(calibrate(pre))
    checks += static_checks
    if tiny_packs(inputs):  # judge the inputs (not the change) before spending a build on them
        try:
            pack_checks = pack_inputs(inputs, tiny_packs(inputs))
        except (OSError, ValueError) as exc:
            pack_checks = [check("tiny_packs_readable", "fail", f"{type(exc).__name__}: {exc}", STATIC)]
        checks += pack_checks
        if any(c["status"] == "fail" for c in pack_checks):
            return result(checks + [check("compile", "skipped", "tiny packs unusable; not built", COMPILE),
                                    check("runtime_acceptance", "skipped", "tiny packs unusable; not run", RUNTIME)],
                          require)
    forced = bool(inputs.get("runtime_even_if_static_fails"))
    if (any(c["status"] == "fail" for c in static_checks) and not forced) or inputs.get("build") is False:
        why = "static gate failed" if inputs.get("build") is not False else "build: false"
        return result(checks + [check("compile", "skipped", f"{why}; not built", COMPILE),
                                check("runtime_acceptance", "skipped", f"{why}; not run", RUNTIME)], require)
    owned = inputs.get("work_dir")
    if owned:
        Path(owned).mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="scale-wiring-verify-", dir=owned))
    try:
        src = co.export_tree(checkout, work / "cand-src", post={**change["carried_post"], **post}, base=head)
        ok, detail = build(src, work / "cand-build", int(inputs.get("jobs", 8)), work / "cand-build.log")
        compile_status = {True: "pass", False: "fail", None: "fail" if require in (COMPILE, RUNTIME) else "skipped"}[ok]
        checks.append(check("compile", compile_status, detail, COMPILE))
        if not ok:
            return result(checks + [check("runtime_acceptance", "skipped", "no candidate build", RUNTIME)], require)
        rt = runtime(inputs, checkout, head, work, src, require)
        acceptance = set(ACCEPTANCE)
        ran = {c["name"] for c in rt if c["name"] in acceptance and c["status"] in ("pass", "fail")}
        if ran != acceptance:
            for c in rt:
                if c["stage"] == RUNTIME and c["status"] == "pass":
                    c["status"], c["detail"] = "info", f"{c['detail']} (runtime acceptance needs all of {sorted(acceptance)})"
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
        if os.environ.get('FACTORY_TASK_ID') == DEMO_TASK or os.environ.get(SCOPE_ENV):
            require_scope()
        outputs = do_verify(packet.get("inputs", {}))
    except (KeyError, OSError, TypeError, ValueError) as exc:
        outputs = result([check("verification_input", "fail", f"{type(exc).__name__}: {exc}", STATIC)])
    print(json.dumps({"outcome": "ok", "outputs": outputs}))


if __name__ == "__main__":
    main()
