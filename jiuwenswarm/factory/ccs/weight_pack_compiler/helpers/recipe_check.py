"""Verifier for a pack recipe (`factory.pack-recipe/1`). Reads the recipe and, when given, the source headers.

Each failed check is a gate: the worker must not start the requantization. See VALIDATION.md.
The requested target type and the source pack come from the caller (the contract), never from the recipe: the
recipe must agree with them, and every type it plans is judged against the source headers, not its own table.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gguf_pack import TYPE_ID, block_of, load_pack, nbytes, padded, role_of, type_name  # noqa: E402
from stock_quantize import parse_argv, predict  # noqa: E402

STAGE = "native CC execution"
# Types with a CUDA matmul kernel in stock 9048bad8: mmvq.cu get_vec_dot_q_cuda and mmq.cu
# ggml_cuda_should_use_mmq both list them; f16/bf16/f32 go through cuBLAS / mmvf.
GB10_TYPES = {"q2_k", "q3_k", "q4_k", "q5_k", "q6_k", "q8_0", "q4_0", "q4_1", "q5_0", "q5_1", "iq2_xxs", "iq2_xs",
              "iq2_s", "iq3_xxs", "iq3_s", "iq4_xs", "iq4_nl", "mxfp4", "nvfp4", "f16", "bf16", "f32"}
HEX64 = re.compile(r"^[0-9a-f]{64}$")
LOW_BIT = 3.5  # bits per weight below which the recipe must name an imatrix


def source_pack(pack_manifest):
    """The verifier's own read of the source: a GGUF path, or a JSON manifest whose first file is the first shard."""
    path, problems = Path(pack_manifest), []
    if path.suffix.lower() != ".json":
        return load_pack(path), problems
    rows = json.loads(path.read_text(encoding="utf-8")).get("files") or []
    if not rows:
        raise ValueError(f"{path.name}: manifest lists no files")
    first = Path(rows[0].get("path") or rows[0].get("name"))
    pack = load_pack(first if first.is_absolute() else path.parent / first)
    listed = {Path(r.get("path") or r.get("name")).name: r.get("bytes", r.get("size")) for r in rows}
    for f in pack["files"]:
        if f["name"] not in listed:
            problems.append(f"{f['name']} is not in the manifest")
        elif listed[f["name"]] is not None and int(listed[f["name"]]) != f["bytes"]:
            problems.append(f"{f['name']}: manifest {listed[f['name']]} bytes, file {f['bytes']}")
    return pack, problems


def bpw(type_):
    block, size = block_of(type_)
    return 8.0 * size / block


def verify_recipe(recipe, target, pack_manifest, disk_grant_bytes=None, gb10_types=None):
    checks = []

    def add(name, ok, detail, status=None):
        checks.append({"name": name, "status": status or ("pass" if ok else "fail"), "stage": STAGE,
                       "detail": detail})

    if not target:
        add("target_given", False, "no target: the requested routed-expert type must come from the caller, "
            "not from the recipe (fails closed)")
        return checks
    if not pack_manifest:
        add("source_matches_recipe", False, "no pack_manifest: the recipe cannot vouch for its own source types "
            "(fails closed)")
        return checks

    required = ("format", "source", "target", "tensors", "argv", "estimate")
    missing = [k for k in required if k not in recipe]
    add("recipe_format", recipe.get("format") == "factory.pack-recipe/1" and not missing,
        f"format={recipe.get('format')!r}" + (f"; missing {missing}" if missing else ""))
    if missing:
        return checks
    target = type_name(target)
    planned_target = str(recipe["target"]).lower()
    add("target_matches", planned_target == target,
        f"recipe target {planned_target}, requested {target}" if planned_target != target else f"recipe targets {target}")
    tensors = recipe["tensors"]
    admitted = set(gb10_types or GB10_TYPES)

    files = recipe["source"].get("files") or []
    bad = [f.get("name", "?") for f in files if not HEX64.match(str(f.get("sha256", "")))]
    add("source_digests", bool(files) and not bad and bool(recipe["source"].get("digest")),
        f"{len(files)} source file(s)" + (f"; no sha256 for {bad[:10]}" if bad else ", each with sha256"))

    live = {}
    try:
        pack, problems = source_pack(pack_manifest)
        live = {n: (r["type"], r["shape"]) for n, r in pack["tensors"].items()}
        planned = {t["name"]: (t["source_type"], t["shape"]) for t in tensors}
        sizes = {f["name"]: f["bytes"] for f in pack["files"]}
        diff = sorted(set(live) ^ set(planned)) + [n for n in live if n in planned and live[n] != planned[n]]
        diff += [f"{f['name']} size" for f in files if sizes.get(f.get("name")) != f.get("bytes")]
        add("source_matches_recipe", not diff and not problems,
            "; ".join(problems + diff[:20]) or f"{len(live)} tensors and file sizes match the source headers")
    except (OSError, ValueError) as exc:
        add("source_matches_recipe", False, f"source unreadable: {exc}")

    def source_type(t):  # the header's type; the recipe's own claim only when the header lacks the tensor
        return live[t["name"]][0] if t["name"] in live else t["source_type"]

    routed = [t for t in tensors if role_of(t["name"]) == "routed_expert"]
    wrong = [f"{t['name']}={t['target_type']}" for t in routed if t["target_type"] != target]
    unchanged = [f"{t['name']} is already {source_type(t)}" for t in routed if source_type(t) == target]
    add("expert_targets", bool(routed) and not wrong and not unchanged,
        f"{len(routed)} routed expert weights {sorted({source_type(t) for t in routed})} -> {target}" if routed and not (wrong or unchanged)
        else "no routed expert weights" if not routed else
        "; ".join(([f"not {target}: {wrong[:10]}"] if wrong else []) +
                  ([f"routed experts must change to the target type: {unchanged[:5]}"] if unchanged else [])))
    moved = [f"{t['name']} {source_type(t)}->{t['target_type']}" for t in tensors
             if role_of(t["name"]) != "routed_expert" and t["target_type"] != source_type(t)]
    add("non_expert_kept", not moved, "; ".join(moved[:10]) or
        f"{len(tensors) - len(routed)} non-expert tensors keep their source type (source headers)")
    off_list = sorted({t["target_type"] for t in tensors if t["target_type"] not in admitted
                       and t["target_type"] != source_type(t)})
    kept_off = sorted({t["target_type"] for t in tensors if t["target_type"] not in admitted
                       and t["target_type"] == source_type(t) and len(t["shape"]) >= 2})
    add("gb10_kernel_types", not off_list, (f"no GB10 kernel for {off_list}" if off_list else
        "every converted type has a stock CUDA kernel") + (f"; kept source types outside the list: {kept_off}"
                                                           if kept_off else ""))
    split = []
    for t in tensors:
        if t["target_type"] != source_type(t):
            if t["target_type"] not in TYPE_ID:
                split.append(f"{t['name']}: unknown type {t['target_type']}")
            elif t["shape"][0] % block_of(t["target_type"])[0]:
                split.append(f"{t['name']}: ne[0]={t['shape'][0]} not a multiple of {block_of(t['target_type'])[0]}")
    add("block_divisibility", not split, "; ".join(split[:10]) or "every converted tensor has whole-block rows")

    try:
        call = parse_argv(recipe["argv"])
    except ValueError as exc:
        add("argv_parses", False, str(exc))
        call = None
    if call:
        add("argv_parses", True, f"input {call['input']}, ftype {call['ftype']}, {len(call['tensor_types'])} pins")
        add("allow_requantize", "--allow-requantize" in call["flags"], "--allow-requantize present"
            if "--allow-requantize" in call["flags"] else "missing: stock refuses to convert NVFP4 without it")
        stray = sorted(call["flags"] & {"--prune-layers", "--dry-run", "--pure", "--leave-output-tensor"})
        add("argv_scope", not stray, f"full-run argv carries {stray}" if stray else "no pruning, dry-run or pure flag")
        mismatch, unpinned = [], []
        for t in tensors:
            got, how = predict(call, t["name"], t["shape"], source_type(t))
            if got is None:
                unpinned.append(t["name"])
            elif got != t["target_type"]:
                mismatch.append(f"{t['name']}: stock writes {got} ({how}), recipe says {t['target_type']}")
        add("argv_realizes_targets", not mismatch and not unpinned,
            "; ".join(mismatch[:10] + [f"unpinned (stock mixture would choose): {unpinned[:10]}"] * bool(unpinned))
            or "the argv makes stock write exactly the recipe's target type for every tensor")
        first = files[0].get("path") if files else None
        add("argv_input_is_source", bool(first) and Path(call["input"]).name == Path(first).name,
            f"argv input {Path(call['input']).name}, recipe source {Path(first).name if first else None}")
        if call["output"] and call["output"] in {f.get("path") for f in files}:
            add("argv_output_not_source", False, "output path overwrites a source file")

    low = bpw(target) < LOW_BIT
    imatrix = recipe.get("imatrix") or {}
    named = bool(imatrix.get("path")) and bool(HEX64.match(str(imatrix.get("sha256", ""))))
    in_argv = bool(call) and call["imatrix"] is not None and Path(call["imatrix"]).name == Path(imatrix.get("path", "")).name
    if low:
        add("imatrix_named", named and in_argv, f"{target} is {bpw(target):.3f} bpw; imatrix "
            + (f"{Path(imatrix['path']).name} sha256 {imatrix['sha256'][:12]}" if named else "not named with sha256")
            + ("" if in_argv else "; --imatrix missing or a different file in argv"))
    else:
        add("imatrix_named", True, f"{target} is {bpw(target):.3f} bpw; no imatrix required", "info")

    est = recipe["estimate"]
    try:
        align = int(recipe["source"].get("alignment", 32))
        data = sum(padded(nbytes(t["target_type"], t["shape"]), align) for t in tensors
                   if t["target_type"] in TYPE_ID and t["shape"][0] % block_of(t["target_type"])[0] == 0)
        header = int(est.get("output_bytes", 0)) - data  # headers: tensor table and metadata, never the bulk
        ok = int(est.get("output_data_bytes", -1)) == data and 0 <= header <= data // 50 + (16 << 20)
        add("estimate_consistent", ok, f"recomputed data {data} bytes vs recipe {est.get('output_data_bytes')}, "
            f"output estimate {est.get('output_bytes')}")
    except (TypeError, ValueError, KeyError) as exc:
        add("estimate_consistent", False, f"estimate unreadable: {exc}")
    grant = disk_grant_bytes if disk_grant_bytes is not None else recipe.get("disk_grant_bytes")
    if grant is not None:
        peak = int(est.get("temp_peak_bytes", 0))
        floor = int(est.get("output_bytes", 0))
        add("disk_grant", 0 < floor <= peak <= int(grant),
            f"temporary peak {peak} bytes (output alone {floor}), grant {grant}")
    else:
        add("disk_grant", True, "no disk grant given", "skipped")
    return checks
