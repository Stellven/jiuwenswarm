"""CC v2 native entry of weights.build_muse_nvfp4_reader: one JSON packet on stdin, one JSON result on stdout.

Capabilities
  scale_inventory  actor helper: role-by-role scale inventory of the checkpoint from its index and headers
  verify           verifier of the converter diff (fixture calibration, static rules, tiny-checkpoint runtime)
  verify_pack      verifier of the written NVFP4 GGUF pack (stdlib census, fails closed)
Pass absolute paths: the host runs this process in its own attempt directory. Nothing is written inside the
checkout; scratch work goes to work_dir (default: a temporary directory, removed afterwards).

`done` follows the evidence ladder fixture < native CC execution < runtime acceptance. verify needs
require_stage (default runtime acceptance, the tiny-conversion round trip): a check that stage needs and that
was skipped, a stage that was not reached, or an inconclusive rule without a passing runtime acceptance stage
leaves done false. `stage_reached` is the highest stage whose checks, and those of every lower stage, passed.
The converter and the compare run in the `python` input (a venv with torch, safetensors, numpy, transformers);
without it the controller's interpreter is used when it has those modules.
"""
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
import converter_rules  # noqa: E402
import patchlib  # noqa: E402
from pack_census import verify_pack  # noqa: E402
from scale_inventory import inventory  # noqa: E402

FIXTURE, STATIC, RUNTIME = "fixture", "native CC execution", "runtime acceptance"
LADDER = (FIXTURE, STATIC, RUNTIME)
FIXTURES = HERE / "tests" / "fixtures"
# Planted faults the static rules must catch on this checkout, and the check that must fail for each.
PLANTED = {"gate-up-swapped.diff": "gate_up_mapping", "scale2-columns-swapped.diff": "gate_up_mapping",
           "input-scale-dropped.diff": "input_scale_written", "eager-repack.diff": "lazy_repack",
           "eager-loader.diff": "lazy_repack", "touches-src.diff": "allowed_paths"}
# Planted faults written in a shape the static rules cannot decide: they must not pass that rule (fail or
# inconclusive), and only runtime acceptance rejects them.
UNDECIDED = {"mapping-inconclusive.diff": "gate_up_mapping"}
EXPORT = ("convert_hf_to_gguf.py", "conversion", "gguf-py")


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


def result(checks, require=None, **extra):
    """done: some check ran, none failed and, with require, that stage was reached with nothing it needs skipped.
    An inconclusive check is settled only by a passing runtime acceptance stage."""
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
    out = {"done": bool(checks) and not why, "checks": checks, "stage_reached": reached, "not_done_because": why}
    return {**out, **extra}


def required_stage(inputs, default):
    stage = inputs.get("require_stage") or default
    if stage not in LADDER:
        raise ValueError(f"require_stage must be one of {list(LADDER)}, not {stage!r}")
    return stage


def rebuild(patch_text, read_pre):
    files = patchlib.parse_patch(patch_text)
    return files, patchlib.post_images(files, read_pre)


def calibrate(pre):
    """Fixture stage: the bundled good diff passes and every planted fault fails its named rule on this base.
    When the fixtures do not apply (a base other than stock 9048bad8) the static rules are not calibrated: the
    check is inconclusive, so only a passing runtime acceptance stage can carry the verdict."""
    if not FIXTURES.is_dir():
        return check("fixture_calibration", "inconclusive", "no bundled fixtures in this release: the static rules "
                     "are not calibrated here; runtime acceptance decides", FIXTURE)
    outcomes, missed = {}, []
    for name in ["good.diff", *PLANTED, *UNDECIDED]:
        try:
            files, post = rebuild((FIXTURES / name).read_text(encoding="utf-8"), pre)
        except (OSError, patchlib.PatchError) as exc:
            return check("fixture_calibration", "inconclusive",
                         f"{name} does not apply to this base ({exc}); the fixtures target stock 9048bad8, so the "
                         "static rules are not calibrated here and runtime acceptance decides", FIXTURE)
        rules = {c["name"]: c["status"] for c in converter_rules.static_checks(files, post)}
        failed = {n for n, st in rules.items() if st == "fail"}
        outcomes[name] = sorted(failed) or ([f"{n} inconclusive" for n, st in rules.items() if st == "inconclusive"])
        if name == "good.diff" and failed:
            missed.append(f"good.diff fails {sorted(failed)}")
        elif name in PLANTED and PLANTED[name] not in failed:
            missed.append(f"{name} did not fail {PLANTED[name]}")
        elif name in UNDECIDED and rules.get(UNDECIDED[name]) not in ("fail", "inconclusive"):
            missed.append(f"{name} passed {UNDECIDED[name]} (it must fail or be inconclusive)")
    if missed:
        return check("fixture_calibration", "fail", "the static rules are not calibrated on this tree: " + "; ".join(missed), FIXTURE)
    return check("fixture_calibration", "pass", {k: v or "passes" for k, v in outcomes.items()}, FIXTURE)


def run_logged(command, log, cwd, env, timeout):
    with open(log, "wb") as handle:
        proc = subprocess.run(command, cwd=cwd, env=env, stdout=handle, stderr=subprocess.STDOUT, timeout=timeout)
    tail = Path(log).read_bytes()[-1500:].decode(errors="replace")
    return proc.returncode, tail


TORCH_PROBE = "import torch, safetensors, numpy, transformers"


def conversion_python(inputs):
    """(python, note): the `python` input, else the controller interpreter when it can run the converter."""
    if inputs.get("python"):
        return inputs["python"], "python input"
    own = os.environ.get('FACTORY_PYTHON', sys.executable)
    try:
        probe = subprocess.run([own, "-c", TORCH_PROBE], capture_output=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired):
        return None, f"{own} could not be probed"
    if probe.returncode:
        return None, f"no python given and {own} lacks torch/safetensors/numpy/transformers"
    return own, f"controller interpreter {own}"


def runtime(inputs, checkout, head, post, require):
    # Without what it needs, runtime acceptance fails when it is the required stage, and is skipped otherwise.
    missing = "fail" if require == RUNTIME else "skipped"
    if not inputs.get("tiny_checkpoint") and not inputs.get("tiny_base"):
        return [check("tiny_conversion", missing, "neither tiny_checkpoint nor tiny_base (tokenizer files "
                      "+ config.json) given; runtime acceptance not reached", RUNTIME)]
    python, how = conversion_python(inputs)
    if not python:
        return [check("tiny_conversion", missing, f"{how}: the converter was not run; give python (a venv with "
                      "torch, safetensors, numpy, transformers); runtime acceptance not reached", RUNTIME)]
    owned = inputs.get("work_dir")
    if owned:
        Path(owned).mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="muse-nvfp4-verify-", dir=owned))
    checks = []
    try:
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1")
        env.pop("NO_LOCAL_GGUF", None)
        src = co.export_tree(checkout, work / "src", EXPORT, post, base=head)
        ckpt = inputs.get("tiny_checkpoint")
        if not ckpt:
            base = inputs["tiny_base"]
            command = [python, str(HERE / "helpers" / "tiny_checkpoint.py"), "--out", str(work / "ckpt"),
                       "--tokenizer-dir", base, "--only", "nvfp4"]
            if inputs.get("tiny_config"):
                command += ["--config", inputs["tiny_config"]]
            command, _ = co.capped(command, inputs.get("mem_cap", "16G"))
            rc, tail = run_logged(command, work / "gen.log", work, env, 1800)
            if rc:
                return [check("tiny_checkpoint", "fail", f"generator exited {rc}: {tail}", RUNTIME)]
            ckpt = str(work / "ckpt" / "nvfp4")
        out = work / "tiny-nvfp4.gguf"
        command, note = co.capped([python, str(src / "convert_hf_to_gguf.py"), ckpt, "--outfile", str(out),
                                   "--outtype", "bf16"], inputs.get("mem_cap", "16G"))
        rc, tail = run_logged(command, work / "convert.log", work, env, 1800)
        if rc or not out.is_file():
            return [check("tiny_conversion", "fail", f"convert_hf_to_gguf.py exited {rc} ({note}): {tail}", RUNTIME)]
        checks.append(check("tiny_conversion", "pass", f"{ckpt} -> {out.name} ({out.stat().st_size} bytes; {note}; "
                            f"{how})", RUNTIME))
        proc = subprocess.run([python, str(HERE / "helpers" / "nvfp4_compare.py"), "--gguf", str(out),
                               "--checkpoint", ckpt, "--gguf-py", str(src / "gguf-py")],
                              capture_output=True, env=env, cwd=work, timeout=1800)
        try:
            compared = json.loads(proc.stdout)
        except ValueError:
            compared = [check("pack_compare", "fail", f"compare exited {proc.returncode}: "
                              f"{proc.stderr.decode(errors='replace')[-1500:]}", RUNTIME)]
        checks += compared
        if inputs.get("keep_work"):
            checks.append(check("work_dir", "info", str(work), RUNTIME))
        return checks
    except subprocess.TimeoutExpired as exc:
        return checks + [check("tiny_conversion", "fail", f"timed out: {exc}", RUNTIME)]
    finally:
        if not inputs.get("keep_work"):
            shutil.rmtree(work, ignore_errors=True)


def do_verify(inputs):
    checks = []
    require = required_stage(inputs, RUNTIME)
    try:
        change = co.review_change(inputs["checkout"], inputs.get("diff_path"), inputs.get("base"),
                                  inputs.get("carried_diff"))
    except (KeyError, OSError, ValueError) as exc:
        return result([check("patch_input", "fail", f"{type(exc).__name__}: {exc}", STATIC)], require)
    checkout, head, files, post = change["checkout"], change["head"], change["files"], change["post"]
    carried = f"; carried from the earlier node, not reviewed: {change['carried']}" if change["carried"] else ""
    checks.append(check("patch_input", "pass", f"{change['mode']} change against {head[:12]}: {sorted(post)}{carried}",
                        STATIC))
    checks.append(calibrate(change["pre"]))
    static = converter_rules.static_checks(files, post)
    checks += static
    blocking = {"allowed_paths", "protected_paths", "plain_text_edits", "python_parses", "stacked_reader"}
    if inputs.get("runtime_even_if_static_fails"):
        blocking = {"python_parses"}  # calibration of the runtime check on a planted fault
    if any(c["status"] == "fail" and c["name"] in blocking for c in static):
        checks.append(check("tiny_conversion", "skipped", "static scope or parse gate failed; not run", RUNTIME))
    else:
        checks += runtime(inputs, checkout, head, {**change["carried_post"], **post}, require)
    return result(checks, require)


def do_verify_pack(inputs):
    checks, manifest = verify_pack(inputs["pack"], inputs["source_index"], inputs.get("inventory"),
                                   inputs.get("quantized_layers"), inputs.get("expect_bytes_range"),
                                   inputs.get("allowed_types"), bool(inputs.get("hash", False)),
                                   inputs.get("scale_sample_layers"))
    return result(checks, STATIC, manifest=manifest)


def inspect_scale_layout(inputs):
    if set(inputs) - {"index", "headers"}:
        raise ValueError("inspect_scale_layout accepts only index and headers")
    return do_scale_inventory(inputs)


def do_scale_inventory(inputs):
    inv = inventory(inputs["index"], inputs.get("headers") or [])
    checks = [check("headers_read", "pass" if inv["headers_read"] else "fail",
                    inv["headers_read"] or "no shard header was read: dtypes and shapes unknown", STATIC),
              check("layout", "fail" if inv["layout_problems"] else "pass",
                    inv["layout_problems"] or "stacked experts: U8 packed weight, F8_E4M3 block scale, F32 scale_2", STATIC)]
    out = inputs.get("out")
    if out:
        Path(out).write_text(json.dumps(inv, indent=1) + "\n", encoding="utf-8")
        checks.append(check("inventory_written", "pass", out, STATIC))
    return result(checks, inventory={k: inv[k] for k in ("format", "shards", "headers_read", "quantized_layers",
                                                         "excluded_layers", "roles", "layout_problems", "findings")})


CAPABILITIES = {"inspect_scale_layout": inspect_scale_layout, "verify": do_verify, "verify_pack": do_verify_pack, "scale_inventory": do_scale_inventory}


def main():
    packet = json.load(sys.stdin)
    handler = CAPABILITIES.get(packet.get("capability"))
    if handler is None:
        response = {"outcome": "error", "error": {"code": "INVALID_INPUT", "message": f"Expected one of {sorted(CAPABILITIES)}"}}
    else:
        try:
            outputs = handler(packet.get("inputs", {}))
        except (KeyError, OSError, TypeError, ValueError) as exc:
            outputs = result([check("verification_input", "fail", f"{type(exc).__name__}: {exc}", STATIC)])
        response = {"outcome": "ok", "outputs": outputs}
    print(json.dumps(response))


if __name__ == "__main__":
    main()
