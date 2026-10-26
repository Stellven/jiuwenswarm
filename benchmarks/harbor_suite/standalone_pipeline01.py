"""Public-only CPU rehearsal. This does not execute or qualify native AI4R stages."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class MemoryCounters(ctypes.Structure):
    _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong)] + [
        (name, ctypes.c_size_t) for name in (
            "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
            "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage",
            "PagefileUsage", "PeakPagefileUsage", "PrivateUsage")]


def memory(handle):
    if os.name != "nt":
        return None
    counters = MemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    ok = ctypes.windll.psapi.GetProcessMemoryInfo(
        ctypes.c_void_p(int(handle)), ctypes.byref(counters), counters.cb)
    if not ok:
        return None
    return {"peak_working_set_bytes": counters.PeakWorkingSetSize,
            "peak_pagefile_bytes": counters.PeakPagefileUsage}


def expected_batches(data):
    """Derive exact postings from cumulative document states, independent of updates."""
    documents = dict(data["documents"])
    result = []
    for changes in data["batches"]:
        for ident, content in changes:
            if content is None:
                documents.pop(ident, None)
            else:
                documents[ident] = content
        postings = {}
        for ident, content in documents.items():
            for term in set(re.findall(r"[a-z0-9]+", content.lower())):
                postings.setdefault(term, []).append(ident)
        postings = {term: sorted(ids) for term, ids in postings.items()}
        answers = {}
        for query in data["queries"]:
            terms = set(re.findall(r"[a-z0-9]+", query.lower()))
            answers[query] = sorted(ident for ident in documents
                                    if terms and all(ident in postings.get(t, []) for t in terms))
        digest = hashlib.sha256(json.dumps(postings, sort_keys=True,
                                          separators=(",", ":")).encode()).hexdigest()
        result.append({"postings_sha256": digest, "answers": answers})
    return result


def execute(command, folder, env, timeout, memory_limit):
    started = now()
    start_ns = time.perf_counter_ns()
    reason = None
    observed = None
    with (folder / "stdout.txt").open("wb") as stdout, (folder / "stderr.txt").open("wb") as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr, env=env)
        while True:
            sample = memory(process._handle) if os.name == "nt" else None
            if sample:
                observed = {k: max((observed or {}).get(k, 0), v) for k, v in sample.items()}
                if max(sample.values()) > memory_limit:
                    reason = "process_memory_limit"
            if (time.perf_counter_ns() - start_ns) / 1e9 > timeout:
                reason = "process_wall_limit"
            if reason:
                process.kill()
                process.wait()
                break
            if process.poll() is not None:
                break
            time.sleep(0.001)
    record = {"command_argv": command, "pid": process.pid, "started_utc": started,
              "ended_utc": now(), "wall_elapsed_ns": time.perf_counter_ns() - start_ns,
              "exit_code": process.returncode, "termination_reason": reason,
              "observed_memory": observed, "pythonhashseed": env["PYTHONHASHSEED"],
              "memory_observation": "Windows process peak counters polled at ~1ms; best effort, not an OS hard cap"}
    write(folder / "process.json", record)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    inputs, output = args.inputs.resolve(), args.output.resolve()
    if output.exists():
        parser.error("output must be a new directory")
    assignment = json.loads((inputs / "assignment.json").read_text(encoding="utf-8"))
    manifest = json.loads((inputs / "public-input-manifest.json").read_text(encoding="utf-8"))
    inventory = []
    for entry in manifest["files"]:
        path = (inputs / entry["path"]).resolve()
        if not path.is_relative_to(inputs / "public") or not path.is_file():
            raise ValueError("manifest path outside public inputs")
        if sha(path) != entry["sha256"] or path.stat().st_size != entry["size"]:
            raise ValueError("public input integrity mismatch: " + entry["path"])
        inventory.append(entry)
    protocol = json.loads((inputs / "public/protocol.json").read_text(encoding="utf-8"))
    schema = json.loads((inputs / "public/handoff.schema.json").read_text(encoding="utf-8"))
    if protocol["run_order"] != ["baseline", "treatment"] * protocol["repeats"]:
        raise ValueError("unsupported paired run order")
    output.mkdir(parents=True)
    snapshots = output / "inputs"
    snapshots.mkdir()
    for entry in inventory + [{"path": "assignment.json"}, {"path": "public-input-manifest.json"}]:
        source = inputs / entry["path"]
        destination = snapshots / entry["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    shutil.copyfile(__file__, output / "runner.py")
    write(output / "environment.json", {
        "started_utc": now(), "argv": sys.argv, "python_executable": sys.executable,
        "python": sys.version, "platform": platform.platform(), "machine": platform.machine(),
        "processor": platform.processor(), "cpu_count": os.cpu_count(), "cwd": str(Path.cwd()),
        "protocol_seed": protocol["seed"], "seed_handling": "PYTHONHASHSEED fixed for every child; reference has no stochastic algorithm or seed CLI",
        "budgets": assignment["budgets"], "resource_limits": {
            "concurrency": "one child at a time", "process_wall_seconds": protocol["budgets"]["max_seconds_per_process"],
            "process_memory_mb": protocol["budgets"]["max_memory_mb"],
            "process_memory": "peak counters monitored on Windows; no OS hard cap; venv launcher may omit child Python",
            "variant_wall": "remaining 900s used as child timeout",
            "disk": "256MiB checked after each child; not an OS quota",
            "aggregate_memory": "not enforced or measured across agent and runner",
            "network_gpu": "runner/reference make no network/provider/GPU calls; not OS sandbox enforced"}})
    summaries = []
    for variant in assignment["variants"]:
        started_ns = time.perf_counter_ns()
        folder = output / variant["id"]
        folder.mkdir()
        workload = snapshots / "public" / (variant["id"] + ".json")
        data = json.loads(workload.read_text(encoding="utf-8"))
        handoff = data["handoff"]
        schema_valid = all(key in handoff for key in schema["required"]) and all(
            handoff.get(key) in spec["enum"] for key, spec in schema["properties"].items())
        units_agree = handoff.get("baseline_latency_unit") == handoff.get("treatment_latency_unit")
        validation = {"required_and_enums_valid": schema_valid, "units_agree": units_agree,
                      "validation_scope": "required fields and property enums from this public schema; not a general JSON Schema validator",
                      "handoff": handoff, "validated_utc": now(),
                      "source": "public/" + workload.name + "#/handoff",
                      "authority": "standalone agent runner pre-dispatch check; not native gate decision"}
        write(folder / "handoff-validation.json", validation)
        summary = {"variant": variant["id"], "native_ai4r_e1": "NOT_RUN",
                   "full_task_success": "UNSCORED", "launched_processes": 0}
        if not schema_valid or not units_agree:
            summary.update(status="HALTED_BEFORE_DISPATCH", scientific_result="NOT_RUN",
                           reason="schema-invalid handoff" if not schema_valid else "conflicting intermediate latency units")
        else:
            expected = expected_batches(data)
            write(folder / "expected-from-public-data.json", expected)
            observations = []
            checks = []
            for index, role in enumerate(protocol["run_order"]):
                run_folder = folder / ("%02d-%s-repeat%d" % (index + 1, role, index // 2))
                run_folder.mkdir()
                env = dict(os.environ, PYTHONHASHSEED=str(protocol["seed"]), PYTHONDONTWRITEBYTECODE="1")
                command = [sys.executable, str(snapshots / "public/reference_index.py"),
                           str(workload), "--role", role, "--repeat", str(index // 2)]
                remaining = assignment["budgets"]["wall_time_s"] - (time.perf_counter_ns() - started_ns) / 1e9
                if remaining <= 0:
                    raise RuntimeError("variant wall budget exhausted before dispatch")
                record = execute(command, run_folder, env,
                                 min(protocol["budgets"]["max_seconds_per_process"], remaining),
                                 protocol["budgets"]["max_memory_mb"] * 1024**2)
                summary["launched_processes"] += 1
                if record["exit_code"] != 0:
                    raise RuntimeError("reference failed; see " + str(run_folder))
                observation = json.loads((run_folder / "stdout.txt").read_text(encoding="utf-8"))
                correct = len(observation["batches"]) == len(expected) and all(
                    batch["postings_sha256"] == wanted["postings_sha256"] and batch["answers"] == wanted["answers"]
                    for batch, wanted in zip(observation["batches"], expected))
                correct = correct and observation["elapsed_unit"] == "ns" and observation["operation_unit"] == "posting_mutation" and observation["role"] == role and observation["repeat_index"] == index // 2
                correct = correct and all(isinstance(b["operations"], int) and b["operations"] >= 0 and isinstance(b["elapsed_ns"], int) and b["elapsed_ns"] >= 0 for b in observation["batches"])
                correct = correct and observation["workload_sha256"] == hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
                checks.append(correct)
                observations.append(observation)
                if not correct:
                    summary.update(status="INVALID_OBSERVATION", scientific_result="NOT_EVALUATED",
                                   failed_process_record=str((run_folder / "process.json").relative_to(output)))
                    write(folder / "summary.json", summary)
                    raise RuntimeError("invalid reference output; see " + str(run_folder))
                if sum(p.stat().st_size for p in output.rglob("*") if p.is_file()) > 256 * 1024**2:
                    raise RuntimeError("disk budget exceeded")
            roles = {}
            for role in ("baseline", "treatment"):
                records = [o for o in observations if o["role"] == role]
                roles[role] = {
                    "operation_totals": [sum(b["operations"] for b in o["batches"]) for o in records],
                    "operations_per_batch": [[b["operations"] for b in o["batches"]] for o in records],
                    "elapsed_ns_per_batch": [[b["elapsed_ns"] for b in o["batches"]] for o in records],
                    "median_elapsed_ns_per_batch": [statistics.median(o["batches"][i]["elapsed_ns"] for o in records) for i in range(len(expected))],
                    "median_total_elapsed_ns": statistics.median(sum(b["elapsed_ns"] for b in o["batches"]) for o in records)}
            success = all(checks) and all(t < b for t, b in zip(roles["treatment"]["operation_totals"], roles["baseline"]["operation_totals"]))
            summary.update(status="EXPERIMENT_COMPLETED", all_public_data_correctness_checks=all(checks),
                           scientific_result="PASS" if success else "FAIL", roles=roles,
                           interpretation="Scientific result is the preregistered mutation criterion; timings are descriptive only.")
        summary["wall_elapsed_ns"] = time.perf_counter_ns() - started_ns
        write(folder / "summary.json", summary)
        summaries.append(summary)
    unchanged = all(sha(inputs / entry["path"]) == entry["sha256"] and sha(snapshots / entry["path"]) == entry["sha256"] for entry in inventory)
    write(output / "summary.json", {"scope": "standalone public workload rehearsal; agent-authored analysis",
          "native_ai4r_e1": "NOT_RUN", "full_task_success": "UNSCORED",
          "public_inputs_unchanged": unchanged, "ended_utc": now(), "variants": summaries})
    files = [{"path": str(p.relative_to(output)), "sha256": sha(p), "size": p.stat().st_size}
             for p in sorted(output.rglob("*")) if p.is_file()]
    write(output / "artifact-inventory.json", {"files": files, "note": "Inventory excludes itself."})
    print(json.dumps({"output": str(output), "public_inputs_unchanged": unchanged,
                      "variants": [{k: s[k] for k in ("variant", "status", "scientific_result", "launched_processes")} for s in summaries]}, indent=2))


if __name__ == "__main__":
    main()
