"""Per-machine GPU calibration. The Muse controller enforces idle and contention checks."""

import csv
import json
import math
from pathlib import Path
import subprocess
import sys


def guarded_attempt(run_dir, name, executable, options):
    evidence = (run_dir / name).resolve()
    controller = Path("tools/run_muse_v03.py").resolve(strict=True)
    executable = Path(executable).expanduser().resolve(strict=True)
    subprocess.run([sys.executable, str(controller), "--gpu-step", name, "--evidence-dir", str(evidence),
                    "--", str(executable), *options], check=True)
    state = json.loads((evidence / "gpu-state.json").read_text())
    return Path(state["folder"])


def bandwidth_result(attempt):
    lines = (attempt / "command.log").read_text().splitlines()
    if any("Validation failed" in line for line in lines):
        raise ValueError("BabelStream reported a validation failure")
    header = next((i for i, line in enumerate(lines)
                   if line.startswith("function,") and "max_mbytes_per_sec" in line), None)
    if header is None:
        raise ValueError("BabelStream's timed CSV table was absent")
    rows = {row["function"]: row for row in csv.DictReader(lines[header:]) if row.get("max_mbytes_per_sec")}
    triad = rows.get("Triad")
    if triad is None:
        raise ValueError("BabelStream's validated Triad bandwidth was absent")
    kernels = {name: round(float(row["max_mbytes_per_sec"]) / 1000, 3) for name, row in rows.items()}
    if not all(math.isfinite(rate) and rate > 0 for rate in kernels.values()):
        raise ValueError("BabelStream reported an invalid bandwidth")
    return {"GB/s": kernels["Triad"], "kernel": "Triad", "dtype": f"fp{8 * int(triad['sizeof'])}",
            "iterations": int(triad["num_times"]), "array_elements": int(triad["n_elements"]),
            "per_kernel_GB/s": kernels}


def compute_format(row):
    kernel = row["Operation"]
    if "ue4m3xe2m1_ue4m3xe2m1" in kernel:
        return "NVFP4 E2M1 with UE4M3 scales"
    if "ue8m0xe2m1_ue8m0xe2m1" in kernel:
        return "MXFP4 E2M1 with UE8M0 scales"
    if "ue8m0xe4m3_ue8m0xe4m3" in kernel:
        return "MXFP8 E4M3 with UE8M0 scales"
    if "gemm_tf32" in kernel:
        return "TF32"
    a, b = (row[key].split(":", 1)[0] for key in ("A", "B"))
    formats = {"f16": "FP16", "bf16": "BF16", "f32": "FP32", "f64": "FP64"}
    return formats.get(a, a) if a == b else f"{a} x {b}"


def compute_result(attempt):
    best = {}
    for path in sorted(attempt.glob("cutlass*.csv")):
        with path.open(newline="") as stream:
            for row in csv.DictReader(stream):
                disposition = row["Disposition"].lower().replace(" ", "_")
                if (row["Provider"].lower() != "cutlass" or row["Status"].lower() != "success"
                        or disposition not in {"passed", "not_verified"}):
                    continue
                rate = float(row["GFLOPs"]) * 1e9
                if not math.isfinite(rate) or rate <= 0:
                    continue
                name = compute_format(row)
                kernel = row["Operation"]
                accumulator = None
                if kernel.startswith("cutlass_simt_dgemm_"):
                    accumulator = "f64"
                elif (kernel.startswith(("cutlass_simt_sgemm_", "cutlass_tensorop_s"))
                      or "_f32_void_f32_" in kernel):
                    accumulator = "f32"
                item = {"FLOP/s": rate, "kernel": kernel, "operation": row["OperationKind"],
                        "A": row["A"], "B": row["B"], "D": row.get("D") or row.get("C"),
                        "accumulator": accumulator, "verification": disposition,
                        "M": int(row["m"]), "N": int(row["n"]), "K": int(row["k"]),
                        "runtime_ms": float(row["Runtime"])}
                previous = best.get(name)
                if previous is None or (disposition == "passed", rate) > (
                        previous["verification"] == "passed", previous["FLOP/s"]):
                    best[name] = item
    if not best:
        raise ValueError("CUTLASS produced no successful floating-point GEMM measurements")
    return {"by_format": best, "flop_convention": "GEMM multiply-add counts as two FLOPs"}


def calibrate_gpu(run_dir, rec, babelstream, cutlass_profiler):
    jobs = [
        (babelstream, "babelstream", "L6.cal.memory_bandwidth", "BabelStream CUDA Triad",
         ["--csv", "--arraysize", str(2**26), "--numtimes", "30"], bandwidth_result),
        (cutlass_profiler, "cutlass", "L6.cal.compute", "NVIDIA CUTLASS Profiler GEMM",
         ["--m=4096", "--n=4096", "--k=4096", "--warmup-iterations=5", "--profiling-iterations=20",
          "--output=cutlass.csv"], compute_result),
    ]
    for executable, name, metric, source, options, parse in jobs:
        if executable is None:
            continue
        try:
            attempt = guarded_attempt(run_dir, name, executable, options)
            result = parse(attempt)
        except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
            rec.add(metric, None, source=source, note=f"{exc}; see {name}/")
            print(f"{metric} unavailable: {exc}", file=sys.stderr)
            continue
        rec.add(metric, result, source=source, note=f"raw output in {attempt.relative_to(run_dir.resolve())}")
        print(json.dumps({metric: result}), flush=True)
