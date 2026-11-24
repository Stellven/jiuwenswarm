"""CC v2 native entry of weights.build_muse_nvfp4_reader: one JSON packet on stdin, one JSON result on stdout.

Capabilities
  scale_inventory  actor helper: role-by-role scale inventory of the checkpoint from its index and headers
  verify           verifier of the converter diff (fixture calibration, static rules, tiny-checkpoint runtime)
  verify_pack      verifier of the written NVFP4 GGUF pack (stdlib census, fails closed)
Pass absolute paths: the host runs this process in its own attempt directory. Nothing is written inside the
checkout; scratch work goes to work_dir (default: a temporary directory, removed afterwards).
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
FIXTURES = HERE / "tests" / "fixtures"
# Planted faults the static rules must catch on this checkout, and the check that must fail for each.
PLANTED = {"gate-up-swapped.diff": "gate_up_mapping", "scale2-columns-swapped.diff": "gate_up_mapping",
           "input-scale-dropped.diff": "input_scale_written", "eager-repack.diff": "lazy_repack",
           "touches-src.diff": "allowed_paths"}
EXPORT = ("convert_hf_to_gguf.py", "conversion", "gguf-py")


def check(name, status, detail, stage):
    return {"name": name, "status": status, "stage": stage, "detail": detail}


def result(checks, **extra):
    return {"done": bool(checks) and all(c["status"] != "fail" for c in checks), "checks": checks, **extra}


def rebuild(patch_text, read_pre):
    files = patchlib.parse_patch(patch_text)
    return files, patchlib.post_images(files, read_pre)


def calibrate(checkout):
    """Fixture stage: the bundled good diff passes and every planted fault fails its named rule on this HEAD."""
    if not FIXTURES.is_dir():
        return check("fixture_calibration", "skipped", "no bundled fixtures in this release", FIXTURE)
    cache = {}

    def pre(path):
        if path not in cache:
            cache[path] = co.head_text(checkout, path)
        return cache[path]

    outcomes, missed = {}, []
    for name in ["good.diff", *PLANTED]:
        try:
            files, post = rebuild((FIXTURES / name).read_text(encoding="utf-8"), pre)
        except (OSError, patchlib.PatchError) as exc:
            return check("fixture_calibration", "skipped",
                         f"{name} does not apply to this HEAD ({exc}); the fixtures target stock 9048bad8", FIXTURE)
        failed = {c["name"] for c in converter_rules.static_checks(files, post) if c["status"] == "fail"}
        outcomes[name] = sorted(failed)
        if name == "good.diff" and failed:
            missed.append(f"good.diff fails {sorted(failed)}")
        elif name != "good.diff" and PLANTED[name] not in failed:
            missed.append(f"{name} did not fail {PLANTED[name]}")
    if missed:
        return check("fixture_calibration", "fail", "the static rules are not calibrated on this tree: " + "; ".join(missed), FIXTURE)
    return check("fixture_calibration", "pass", {k: v or "passes" for k, v in outcomes.items()}, FIXTURE)


def run_logged(command, log, cwd, env, timeout):
    with open(log, "wb") as handle:
        proc = subprocess.run(command, cwd=cwd, env=env, stdout=handle, stderr=subprocess.STDOUT, timeout=timeout)
    tail = Path(log).read_bytes()[-1500:].decode(errors="replace")
    return proc.returncode, tail


def runtime(inputs, checkout, post):
    python = inputs.get("python")
    if not python:
        return [check("tiny_conversion", "skipped", "no python given (a venv with torch, safetensors, numpy, "
                      "transformers): the converter was not run; runtime acceptance not reached", RUNTIME)]
    owned = inputs.get("work_dir")
    if owned:
        Path(owned).mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="muse-nvfp4-verify-", dir=owned))
    checks = []
    try:
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1")
        env.pop("NO_LOCAL_GGUF", None)
        src = co.export_tree(checkout, work / "src", EXPORT, post)
        ckpt = inputs.get("tiny_checkpoint")
        if not ckpt:
            base = inputs.get("tiny_base")
            if not base:
                return [check("tiny_conversion", "skipped", "neither tiny_checkpoint nor tiny_base (tokenizer files "
                              "+ config.json) given; runtime acceptance not reached", RUNTIME)]
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
        checks.append(check("tiny_conversion", "pass", f"{ckpt} -> {out.name} ({out.stat().st_size} bytes; {note})", RUNTIME))
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
    try:
        checkout, head = co.resolve(inputs["checkout"])
        patch, mode = co.candidate_patch(checkout, inputs.get("diff_path"))
        if not patch.strip():
            raise ValueError("there is no change to check")
        files, post = rebuild(patch, lambda p: co.head_text(checkout, p))
    except (KeyError, OSError, ValueError) as exc:
        return result([check("patch_input", "fail", f"{type(exc).__name__}: {exc}", STATIC)])
    checks.append(check("patch_input", "pass", f"{mode} change against HEAD {head[:12]}: {sorted(post)}", STATIC))
    checks.append(calibrate(checkout))
    static = converter_rules.static_checks(files, post)
    checks += static
    blocking = {"allowed_paths", "protected_paths", "plain_text_edits", "python_parses", "stacked_reader"}
    if inputs.get("runtime_even_if_static_fails"):
        blocking = {"python_parses"}  # calibration of the runtime check on a planted fault
    if any(c["status"] == "fail" and c["name"] in blocking for c in static):
        checks.append(check("tiny_conversion", "skipped", "static scope or parse gate failed; not run", RUNTIME))
    else:
        checks += runtime(inputs, checkout, post)
    return result(checks)


def do_verify_pack(inputs):
    checks, manifest = verify_pack(inputs["pack"], inputs.get("inventory"), inputs.get("source_index"),
                                   inputs.get("quantized_layers"), inputs.get("expect_bytes_range"),
                                   inputs.get("allowed_types"), bool(inputs.get("hash", False)))
    return result(checks, manifest=manifest)


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


CAPABILITIES = {"verify": do_verify, "verify_pack": do_verify_pack, "scale_inventory": do_scale_inventory}


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
