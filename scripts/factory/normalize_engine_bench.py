#!/usr/bin/env python3
"""Normalize Muse Spark benchmark receipts without running a model."""
import argparse
from collections import Counter
from functools import cache
import hashlib
import json
from pathlib import Path
import re
import tempfile


MIB = 1024**2
R8_RUNS = {
    "14b78261ad4b4142b832fbe008f49d4c": ("r8-smoke", "S-A"),
    "3b1a557a00454da29ededd27fbcb9678": ("r8-smoke", "S-B"),
    "8c7d64ac667b42caa24361da7fdc11a0": ("r8-prefill-calibration", "CAL-B"),
    "e5b36273f07c4eb98985428c48bcc8dd": ("r8-prefill-calibration", "CAL-P"),
}
REPORTS = (
    ("report", "nov24-lab-abc", "2026-11-24", None),
    ("report-abcde", "nov25-lab-abcde", "2026-11-25", "{arm}.stderr.log"),
    ("probe-D", "nov25-probe-d", "2026-11-25", None),
    ("probe-ub2048", "nov25-probe-ub2048", "2026-11-25", "{arm}.stderr.log"),
    ("report-sizes", "nov25-size-probe", "2026-11-25", "{arm}-sizes.stderr.log"),
    ("sweep-agent", "nov25-agent-sweep", "2026-11-25", "{arm}-agent.stderr.log"),
)
DEVICE_KEYS = ("model", "kv", "compute", "moe_cache")
BUFFER_RE = re.compile(r"CUDA\d+\s+(model buffer|KV buffer|compute buffer|MoE cache) size\s*=\s*([\d.]+) MiB")
BUILD_RE = re.compile(r"common_params_print_info: build \d+ \(([a-f0-9]+)\)")
SETTING_RE = re.compile(r"llama_context: (n_batch|n_ubatch|n_ctx|n_seq_max)\s*=\s*(\d+)\s*$")
CENSUS_RE = re.compile(r"llama_model_loader: - type\s+(\w+):\s*(\d+) tensors")


@cache
def payload(path):
    return path.read_bytes()


def read_json(path):
    return json.loads(payload(path))


def digest(buffer):
    return hashlib.sha256(buffer).hexdigest()


@cache
def file_digest(path):
    return digest(payload(path))


def source(path, record=None, line=None):
    location = {"record": record} if record is not None else {"line": line}
    return dict(path=str(path), sha256=file_digest(path), **location)


def flag(argv, name):
    values = [argv[i + 1] for i, arg in enumerate(argv[:-1]) if arg == name]
    return int(values[-1]) if values else None


def mib(value):
    return value / MIB if value is not None else None


def pack(model, name=None):
    if name is None:
        name = ("mixed 2-bit" if "muse-2bit" in model else
                "Q2_K" if "Q2_K" in model else "NVFP4")
    formats = {"mixed 2-bit": "GGUF IQ2_XXS / Q2_K", "Q2_K": "GGUF Q2_K", "NVFP4": "GGUF NVFP4"}
    return dict(name=name, format=formats[name], bytes=None, bits_per_weight=None, census_digest=None, manifest_sha256=None,
                first_shard=model or None)


def engine(name, binary=None, commit=None, sha256=None, image=None):
    return dict(name=name, binary=binary, commit=commit, sha256=sha256, image=image)


def settings(argv=(), cache_mib=None, ctx=None, cpu_moe=None, np=None, fitt=None):
    return dict(b=flag(argv, "-b"), ub=flag(argv, "-ub"),
                moe_cache_mib=flag(argv, "--moe-cache-mib") or cache_mib,
                ctx=flag(argv, "-c") or ctx, np=flag(argv, "-np") or np,
                cpu_moe=True if "--cpu-moe" in argv else cpu_moe, fitt=flag(argv, "-fitt") or fitt)


def memory(device=None, budget=None, peak_cgroup=None, available=None, rss=None):
    device = device or dict.fromkeys(DEVICE_KEYS)
    complete = all(device[key] is not None for key in DEVICE_KEYS)
    margin = round(budget - sum(device[key] for key in DEVICE_KEYS), 2) if budget is not None and complete else None
    return dict(peak_rss=rss, peak_cgroup_mib=peak_cgroup, min_available=available,
                device=device, budget=budget, fit_margin=margin)


def quiet(evidence=None):
    evidence = evidence or {}
    status = evidence.get("status")
    eligible = {"accepted": True, "excluded": False}.get(status)
    samples = evidence.get("samples", [])
    loads = [sample["load_averages"][0] for sample in samples if sample.get("load_averages")]
    appearances = Counter(
        (process.get("own_lab"), process.get("kind"), process.get("name"), process.get("state"))
        for sample in samples for process in sample.get("processes") or ()
    )
    ranked = sorted(appearances, key=lambda key: (key[0] is True, key[1] == "other", -appearances[key], str(key)))
    processes = [
        dict(own_lab=own, kind=kind, name=name, state=state, observations=appearances[own, kind, name, state])
        for own, kind, name, state in ranked[:24]
    ]
    reasons = evidence.get("reasons", [])
    reason = "; ".join(reasons) or ("No row-level quiet evidence" if eligible is None else None)
    return dict(eligible=eligible, load1=max(loads, default=None), processes=processes or None, reason=reason,
                sample_count=len(samples) if evidence else None, process_groups_omitted=max(0, len(ranked) - len(processes)))


def metrics(row=None, load=None):
    row = row or {}
    return dict(ttft_ms=row.get("client_ttft_ms"), decode_tps=row.get("decode_tokens_per_second", row.get("decode_tps")),
                prefill_tps=row.get("prompt_tokens_per_second", row.get("prompt_per_second")),
                total_ms=row.get("request_total_ms", row.get("wall_ms")), load_s=load,
                server_prefill_ms=row.get("prompt_ms"))


def record(date, run, arm, kind, primary, **fields):
    label = fields.pop("label", "measured")
    return dict(schema="engine-bench/1", id=f"{run}/{arm}/{kind}/{fields.pop('key')}", date=date, run=run,
                arm=arm, kind=kind, source=primary, label=label, comparison_group=run,
                request=None, metrics=metrics(), quiet=quiet(), error=None) | fields


def request(row, n_predict=None):
    return dict(name=row.get("request"), prompt_tokens=row.get("prompt_tokens", row.get("prompt_n")),
                n_predict=row.get("n_predict", n_predict), state=row.get("state"),
                repeat=row.get("repeat", row.get("rep")), generated_tokens=row.get("generated_tokens", row.get("predicted_n")),
                cached_tokens=row.get("cached_tokens"))


@cache
def server_log(path):
    captures = {}
    observed = {}
    buffers = {key: [] for key in DEVICE_KEYS}
    census = {}
    details = {}
    split_requests = []
    ready_line = None
    current = None
    names = {"n_batch": "b", "n_ubatch": "ub", "n_ctx": "ctx", "n_seq_max": "np"}
    devices = dict(zip(("model buffer", "KV buffer", "compute buffer", "MoE cache"), DEVICE_KEYS))
    for number, line in enumerate(payload(path).decode(errors="replace").splitlines(), 1):
        if found := BUFFER_RE.search(line):
            buffers[devices[found[1]]].append(float(found[2]))
        elif found := SETTING_RE.search(line):
            observed[names[found[1]]] = int(found[2])
        elif found := BUILD_RE.search(line):
            details["commit"] = found[1]
        elif found := CENSUS_RE.search(line):
            census[found[1]] = int(found[2])
        elif found := re.search(r"file size\s*=\s*([\d.]+) GiB \(([\d.]+) BPW\)", line):
            details.update(file_size_gib_reported=float(found[1]), bits_per_weight=float(found[2]))
        elif found := re.search(r"(\d+)\.(\d+)\.(\d+)\.(\d+) I srv\s+server_run_i: model loaded", line):
            minutes, seconds, millis, micros = map(int, found.groups())
            details["server_ready_s"] = 60 * minutes + seconds + millis / 1000 + micros / 1000000
            ready_line = number
        elif found := re.search(r"new prompt, .*task\.n_tokens = (\d+)", line):
            current = dict(prompt_tokens=int(found[1]), batches=[], lines=[number])
            split_requests.append(current)
            continue
        elif current is not None and (found := re.search(r"prompt processing, n_tokens =\s*(\d+)", line)):
            current["batches"].append(int(found[1]))
            current["lines"].append(number)
            continue
        elif current is not None and (found := re.search(r"init sampler, .*tokens: text = (\d+)", line)):
            current["lines"].append(number)
            current["batches"].append(int(found[1]))
            current = None
            continue
        else:
            continue
        captures[number] = line
    device = {key: round(sum(values), 2) if values else None for key, values in buffers.items()}
    chunks = [
        dict(tokens=entry["prompt_tokens"],
             chunks=[end - start for start, end in zip([0] + entry["batches"], entry["batches"])],
             lines=entry["lines"])
        for entry in split_requests
        if entry["batches"] and entry["batches"][-1] == entry["prompt_tokens"]
        and entry["batches"] == sorted(set(entry["batches"]))
    ]
    return dict(device=device, observed=observed, census=census, details=details, lines=captures, splits=chunks,
                ready_line=ready_line)


def add_log(log_path, settings_row, pack_row, engine_row, references):
    if log_path is None or not log_path.is_file():
        return {}, None
    log = server_log(log_path)
    references.extend(source(log_path, line=number) for number in log["lines"])
    settings_row.update(log["observed"])
    if engine_row["commit"] is None:
        engine_row["commit"] = log["details"].get("commit")
    pack_row["bits_per_weight"] = log["details"].get("bits_per_weight")
    if log["census"]:
        pack_row["census_digest"] = digest(json.dumps(log["census"], sort_keys=True, separators=(",", ":")).encode())
    return log, log["device"]


def add_manifest(pack_row, model, references):
    if not model:
        return
    first_shard = Path(model)
    stem, _, shard = first_shard.name.partition("-00001-of-")
    if not shard:
        return
    manifest = first_shard.with_name(stem + ".manifest.json")
    if manifest.is_file():
        doc = read_json(manifest)
        pack_row["bytes"] = sum(entry["bytes"] for entry in doc["files"])
        pack_row["manifest_sha256"] = digest(payload(manifest))
        references.append(source(manifest, record="/files"))
        return
    shards = sorted(first_shard.parent.glob(f"{stem}-*-of-{shard}"))
    if len(shards) == int(Path(shard).stem):
        pack_row["bytes"] = sum(item.stat().st_size for item in shards)


def historical(root):
    for filename, run, date, logfile in REPORTS:
        path = root / "lab" / f"{filename}.json"
        doc = read_json(path)
        shared = {}
        for arm, raw in doc["arms"].items():
            refs = [source(path, record=f"/arms/{arm}")]
            binary_dir = raw.get("bin", {"A": "/tmp/wt-spike-llama/build-cuda/bin",
                                         "B": "/tmp/wt-spike-llama/build-cuda/bin"}.get(arm, "/tmp/wt-e1/build/bin"))
            binary = str(Path(binary_dir) / "llama-server")
            engine_row = engine({"C": "E1", "D": "E1", "E": "E2"}.get(arm, "E0"), binary)
            model = raw.get("model", "")
            pack_row = pack(model, "NVFP4" if arm == "A" else "Q2_K")
            add_manifest(pack_row, model, refs)
            cache_request = int(raw.get("cache_mib", 61440))
            config = settings(raw.get("args", []), cache_mib=cache_request, ctx=int(raw.get("ctx", 4096)), cpu_moe=True, np=1)
            log_path = root / "lab" / logfile.format(arm=arm) if logfile else None
            log, device = add_log(log_path, config, pack_row, engine_row, refs)
            if log_path is None:
                config["b"] = config["b"] or 2048
                config["ub"] = config["ub"] or 512
            peak = raw.get("sampled_peak_memory_gib")
            memory_row = memory(device=device, budget=110000 if run == "nov25-lab-abcde" and arm == "A" else None,
                                peak_cgroup=peak * 1024 if peak is not None else None)
            shared[arm] = dict(engine=engine_row, pack=pack_row, settings=config, memory=memory_row, sources=refs)
            yield record(date, run, arm, "load", refs[0], key="startup", **shared[arm],
                         metrics=metrics(load=raw.get("load_seconds")), raw={"arm": raw, "server": log})
        for index, row in enumerate(doc["rows"]):
            arm = row["arm"]
            yield record(date, run, arm, "performance", source(path, record=f"/rows/{index}"),
                         key=str(index), **shared[arm], request=request(row, 128),
                         metrics=metrics(row, doc["arms"][arm].get("load_seconds")), raw=row)
        if run == "nov25-agent-sweep":
            for arm, fit in doc.get("fit", {}).items():
                yield record(date, run, arm, "performance", source(path, record=f"/fit/{arm}"),
                             key="fitted", **shared[arm], label="indicative",
                             metrics=metrics({"decode_tps": fit["tok_s"]}), raw=fit)


def live_receipts(root):
    runs = root / "graph-r8/runs"
    build_path = runs / "b9a0873d31b3462abbcf8702a7bf7309/result.json"
    build = read_json(build_path)["result"]
    for attempt, (run, arm) in R8_RUNS.items():
        directory = runs / attempt
        result_path = directory / "result.json"
        result = read_json(result_path)
        measured = result["result"]
        if measured["build"] != build["name"]:
            raise ValueError(f"Unexpected server build in {result_path}")
        server = build["binaries"]["llama-server"]
        engine_row = engine("E0", server["path"], build["commit"], server["sha256"])
        refs = [source(result_path, record="/result"), source(build_path, record="/result/binaries/llama-server")]
        pack_row = pack(measured["model"])
        add_manifest(pack_row, measured["model"], refs)
        argv = measured["server_args"]
        placement = {}
        progress_path = directory / "progress.log"
        for number, line in enumerate(payload(progress_path).decode().splitlines(), 1):
            if " placement: " in line:
                placement = json.loads(line.split(" placement: ", 1)[1])
                refs.append(source(progress_path, line=number))
                break
        config = settings(argv, fitt=placement.get("fit_margin_mib"))
        log_path = directory / "server.log"
        log, device = add_log(log_path, config, pack_row, engine_row, refs)
        memory_row = memory(device, placement.get("device_budget_mib"), mib(result.get("peak_memory_bytes")),
                            mib(result.get("min_available_bytes")))
        shared = dict(engine=engine_row, pack=pack_row, settings=config, memory=memory_row, attempt_id=attempt)
        ready = measured["ready_s"]
        raw = {key: value for key, value in measured.items() if key != "rows"}
        yield record("2026-11-26", run, arm, "load", refs[0], key="startup", **shared, sources=refs,
                     metrics=metrics(load=ready), raw=dict(result=raw, placement=placement, server=log,
                         peak_memory_bytes=result.get("peak_memory_bytes"), min_available_bytes=result.get("min_available_bytes")))
        prompts = {entry["id"]: entry["n_predict"] for entry in result["request"]["prompts"]}
        rows_path = directory / "rows.json"
        for index, row in enumerate(read_json(rows_path)):
            row_refs = refs.copy()
            req = request(row, prompts[row["request"]])
            splits = log["splits"]
            if len(splits) == measured["rows"] and splits[index]["tokens"] == req["prompt_tokens"]:
                req["prefill_chunks"] = splits[index]["chunks"]
                req["prefill_chunks_kind"] = "checkpoint_segments"
                row_refs.extend(source(log_path, line=number) for number in splits[index]["lines"])
            yield record("2026-11-26", run, arm, "performance", source(rows_path, record=f"/{index}"),
                         key=str(index), **shared, sources=row_refs, request=req, metrics=metrics(row, ready), raw=row)


def accuracy(root):
    path = root / "acc/state.json"
    doc = read_json(path)
    assets = {}
    for arm in ("A", "B"):
        raw = doc["arms"][arm]
        refs = [source(path, record=f"/arms/{arm}")]
        pack_row = pack("", "NVFP4" if arm == "A" else "Q2_K")
        config = settings(raw["args"], cache_mib=int(raw["cache_mib"]), ctx=int(raw["ctx"]), cpu_moe=True)
        assets[arm] = dict(engine=engine("E0", "/tmp/wt-spike-llama/build-cuda/bin/llama-server"),
                           pack=pack_row, settings=config, memory=memory(), sources=refs)
    run = "nov25-mmlu-q2"
    for index, look in enumerate(doc["looks_done"]):
        signed_interval = dict(lo=-look["hi_pts"] / 100, hi=-look["lo_pts"] / 100)
        for arm, score in (("A", "acc_ref"), ("B", "acc_cand")):
            yield record("2026-11-25", run, arm, "accuracy", source(path, record=f"/looks_done/{index}"),
                         key=str(look["n"]), **assets[arm], test=doc["benchmark"], n=look["n"], acc=look[score],
                         reference_acc=look["acc_ref"], delta=-look["loss_pts"] / 100 if arm == "B" else 0,
                         interval=signed_interval if arm == "B" else None, margin=look["margin_pts"] / 100,
                         verdict=look["decision"] if arm == "B" else None, raw=look)

    log = root / "acc/run.log"
    for number, line in enumerate(payload(log).decode().splitlines(), 1):
        match = re.search(r" ([AB]): ready (\d+)s$", line)
        if match:
            arm, seconds = match.groups()
            yield record("2026-11-25", run, arm, "load", source(log, line=number), key=str(number),
                         **assets[arm], metrics=metrics(load=int(seconds)), raw=line)


def legacy_smoke(root):
    path = root / "smoke/e0-nvfp4.json"
    doc = read_json(path)
    pack_row = pack(doc["model"])
    refs = []
    add_manifest(pack_row, doc["model"], refs)
    engine_row = engine("E0", str(Path(doc["bindir"]) / "llama-server"))
    config = settings(ctx=4096, np=1, cpu_moe=True)
    log_path = path.with_suffix(".stderr.log")
    log, device = add_log(log_path, config, pack_row, engine_row, refs)
    shared = dict(engine=engine_row, pack=pack_row, settings=config, memory=memory(device), sources=refs)
    for index, row in enumerate(doc["rows"]):
        req = request(row, 64)
        req["name"] = row["prompt"]
        yield record("2026-11-24", "nov24-smoke", "S-A", "performance", source(path, record=f"/rows/{index}"),
                     key=str(index), **shared, request=req, metrics=metrics(row), raw=row)
    yield record("2026-11-24", "nov24-smoke", "S-A", "load", source(log_path, line=log["ready_line"]),
                 key="startup", **shared,
                 metrics=metrics(load=log["details"].get("server_ready_s")), raw=log)


def phase_four(path):
    doc = read_json(path)
    identity = doc["factory_provenance"]
    run = "r8-lab"
    shared = {}
    for arm, config in doc["config"]["arms"].items():
        raw = doc["arms"].get(arm, {})
        refs = [source(path, record=f"/config/arms/{arm}"), source(path, record="/factory_provenance")]
        argv = raw.get("argv", ())
        pack_row = pack(config["model"])
        add_manifest(pack_row, config["model"], refs)
        if pack_row["manifest_sha256"] != identity["pack_manifest_sha256"]:
            raise ValueError("Phase 4 pack manifest no longer matches the factory provenance")
        engine_row = engine("E0", binary="llama-server", commit=identity["source_commit"],
                            sha256=identity["llama_server_sha256"], image=identity["image_id"])
        config_row = settings(argv, cache_mib=config["cache_mib"], fitt=raw.get("fit_margin_mib"))
        log, device = add_log(path.with_name(f"{arm}.server.log"), config_row, pack_row, engine_row, refs)
        memory_row = memory(device, raw.get("device_budget_mib", doc["config"]["device_budget_mib"]),
                            mib(raw.get("sampled_peak_memory_bytes")), mib(raw.get("min_available_bytes")),
                            mib(raw.get("peak_process_rss_bytes")))
        shared[arm] = dict(engine=engine_row, pack=pack_row, settings=config_row, memory=memory_row,
                           sources=refs, attempt_id=identity["build_attempt_id"])
        if raw:
            date = raw["started"][:10]
            yield record(date, run, arm, "load", source(path, record=f"/arms/{arm}"),
                         key="startup", **shared[arm], metrics=metrics(load=raw.get("load_seconds")),
                         raw={"arm": raw, "server": log, "provenance": identity})
    for index, row in enumerate(doc["rows"]):
        arm = row["arm"]
        raw = doc["arms"].get(arm, {})
        date = raw.get("started", "2026-11-26")[:10]
        raw_evidence = row.get("quiet") or {}
        evidence = quiet(raw_evidence)
        row_refs = shared[arm]["sources"].copy()
        if raw_evidence:
            quiet_source = source(path, record=f"/rows/{index}/quiet")
            row_refs.append(quiet_source)
            evidence["source"] = quiet_source
        raw_row = {key: value for key, value in row.items() if key != "quiet"}
        if raw_evidence:
            raw_row["quiet"] = {key: value for key, value in raw_evidence.items() if key != "samples"}
        yield record(date, run, arm, "performance", source(path, record=f"/rows/{index}"),
                     key=str(index), **(shared[arm] | {"sources": row_refs}), request=request(row), quiet=evidence,
                     metrics=metrics(row, raw.get("load_seconds")), raw=raw_row, error=row.get("error"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.home() / "muse-demo")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--phase-four-report", type=Path, help="Include the r8 B/P report after the lab exit")
    args = parser.parse_args()
    root = args.root.resolve()
    out = args.out or root / "bench/engine-bench.jsonl"
    rows = [*historical(root), *legacy_smoke(root), *accuracy(root), *live_receipts(root)]
    if args.phase_four_report is not None:
        rows.extend(phase_four(args.phase_four_report.resolve()))
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=out.parent, delete=False, encoding="utf-8") as temp:
        temporary_path = Path(temp.name)
        for row in rows:
            print(json.dumps(row, ensure_ascii=False, allow_nan=False), file=temp)
    temporary_path.chmod(0o644)
    temporary_path.replace(out)
    print(f"Wrote {len(rows)} rows to {out}")


if __name__ == "__main__":
    main()
