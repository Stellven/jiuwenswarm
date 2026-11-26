"""Precision allocator: census of a GGUF pack -> a pack recipe (`factory.pack-recipe/1`) for stock llama-quantize.

The recipe is a proposal for the worker to read, edit and verify (`verify_recipe`), not a finished answer:
it names each tensor's source and target type, the `--tensor-type` pins that keep every non-expert tensor at
its source type, the full argv, a one-layer timing probe and the byte and disk estimates.

    python helpers/recipe.py /packs/muse-nvfp4-00001-of-00009.gguf --imatrix imatrix.gguf --out recipe.json
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gguf_pack import (TYPE_ID, block_of, canonical_target, expert_type, parse_target, target_types, load_pack, nbytes, pack_digest, padded, role_of,  # noqa: E402
                       sha256_file, type_name)

FORMAT = "factory.pack-recipe/1"
# File-type positional accepted by tools/quantize/quantize.cpp QUANT_OPTIONS. Every tensor is pinned, so the
# file type only has to be a quantized one; it is chosen to match the target so the file says what it holds.
FTYPE = {"q2_k": "Q2_K", "q3_k": "Q3_K_M", "q4_k": "Q4_K_M", "q5_k": "Q5_K_M", "q6_k": "Q6_K", "q8_0": "Q8_0",
         "q4_0": "Q4_0", "q4_1": "Q4_1", "q5_0": "Q5_0", "q5_1": "Q5_1", "iq2_xxs": "IQ2_XXS", "iq2_xs": "IQ2_XS",
         "iq2_s": "IQ2_S", "iq3_xxs": "IQ3_XXS", "iq3_s": "IQ3_S", "iq4_nl": "IQ4_NL", "iq4_xs": "IQ4_XS",
         "iq1_s": "IQ1_S", "iq1_m": "IQ1_M"}
# stock src/llama-quant.cpp tensor_type_fallback(): target -> type used when ne[0] is not whole blocks
FALLBACK = {**{t: "iq4_nl" for t in ("iq1_s", "iq1_m", "iq2_xxs", "iq2_xs", "iq2_s", "iq3_xxs", "iq3_s", "iq4_xs")},
            **{t: "q4_0" for t in ("q2_0", "q2_k", "q3_k", "tq1_0", "tq2_0")},
            "q4_k": "q5_0", "q5_k": "q5_1", "q6_k": "q8_0"}
SAFE_NAME = re.compile(r"^[a-z0-9_.]+$")  # stock lower-cases the pattern; keep names free of other regex syntax
HEADER_SLACK = 1 << 16  # imatrix, quantize and split KV the tool adds or drops per output header


def bits_per_weight(type_):
    block, size = block_of(type_)
    return 8.0 * size / block


def stock_fallback(type_, ncols):
    """What stock quantize writes instead of `type_` when ncols is not whole blocks (None when it fits)."""
    block, _ = block_of(type_)
    if ncols % block == 0:
        return None
    fallback = FALLBACK.get(type_, type_ if block <= 32 else "error: no fallback defined")
    if fallback in TYPE_ID and ncols % block_of(fallback)[0]:
        fallback = "f16"
    return fallback


def file_record(path, want_hash):
    path = Path(path)
    record = {"path": str(path), "name": path.name, "bytes": path.stat().st_size}
    if want_hash:
        record["sha256"] = sha256_file(path)
    return record


def load_source(pack_manifest, want_hash):
    """Read the source census from a GGUF path or a JSON manifest that names the files and their sha256."""
    path = Path(pack_manifest)
    named = {}
    if path.suffix.lower() == ".json":
        manifest = json.loads(path.read_text(encoding="utf-8"))
        rows = manifest.get("files") or []
        if not rows:
            raise ValueError(f"{path.name}: manifest lists no files")
        for row in rows:
            name = Path(row.get("path") or row.get("name")).name
            named[name] = row
        first = Path(rows[0].get("path") or rows[0].get("name"))
        if not first.is_absolute():
            first = path.parent / first
        pack = load_pack(first, hash_files=False)
    else:
        pack = load_pack(path, hash_files=want_hash)
    problems = []
    for record in pack["files"]:
        row = named.get(record["name"])
        if row is None:
            continue
        size = row.get("bytes", row.get("size"))
        if size is not None and int(size) != record["bytes"]:
            problems.append(f"{record['name']}: manifest says {size} bytes, file has {record['bytes']}")
        if row.get("sha256"):
            record["sha256"] = row["sha256"]
            record["sha256_from"] = "manifest"
    if named and len(named) != len(pack["files"]):
        problems.append(f"manifest lists {len(named)} files, the pack has {len(pack['files'])}")
    return pack, problems


def layer_pattern(suffix, layers):
    group = str(layers[0]) if len(layers) == 1 else "(" + "|".join(str(n) for n in layers) + ")"
    return "^blk\\." + group + "\\." + suffix.replace(".", "\\.") + "$"


def pins(rows):
    """Group (name -> type) into anchored stock regex pins; one pin per tensor suffix and type."""
    groups, singles = {}, []
    for name, type_ in rows:
        match = re.match(r"^blk\.(\d+)\.(.+)$", name)
        if match:
            groups.setdefault((match[2], type_), []).append(int(match[1]))
        else:
            singles.append(("^" + name.replace(".", "\\.") + "$", type_))
    out = [(layer_pattern(suffix, sorted(layers)), type_) for (suffix, type_), layers in sorted(groups.items())]
    return [{"pattern": p, "type": t} for p, t in sorted(singles) + out]


def quantizable(row):
    """Tensors stock llama-quantize may change (n_dims >= 2 and the name ends in `weight`); pin all of them."""
    return len(row["shape"]) >= 2 and row["name"].endswith("weight")


def plan_recipe(pack_manifest, target="q2_k", imatrix=None, output=None, llama_quantize="llama-quantize",
                keep_split=None, threads=None, want_hash=False, disk_grant_bytes=None, probe_layer=None):
    checks = []

    def add(name, status, detail):
        checks.append({"name": name, "status": status, "stage": "native CC execution", "detail": detail})

    target = canonical_target(target)
    types = parse_target(target)
    lowest = min(target_types(types), key=bits_per_weight)
    pack, problems = load_source(pack_manifest, want_hash)
    add("source_manifest", "fail" if problems else "pass", "; ".join(problems) or
        f"{len(pack['files'])} file(s), {len(pack['tensors'])} tensors")
    files = pack["files"]
    first = Path(files[0]["path"])
    split = len(files) > 1
    keep_split = split if keep_split is None else bool(keep_split)
    if output is None:
        stem = re.sub(r"-\d{5}-of-\d{5}$", "", first.stem)
        output = str(first.parent / f"{stem}-{target.upper().replace(',', '-').replace('=', '_')}.gguf")
    out_prefix = output[:-5] if keep_split and output.endswith(".gguf") else output

    tensors, refusals, pinned, experts = [], [], [], []
    for row in pack["tensors"].values():
        role = role_of(row["name"])
        want = expert_type(types, row["name"]) if role == "routed_expert" else row["type"]
        entry = {"name": row["name"], "role": role, "shape": row["shape"], "shard": row["shard"],
                 "source_type": row["type"], "target_type": want, "source_bytes": row["nbytes"]}
        if want != row["type"]:
            fallback = stock_fallback(want, row["shape"][0])
            if fallback:
                refusals.append(f"{row['name']}: ne[0]={row['shape'][0]} is not a multiple of the {want} block "
                                f"{block_of(want)[0]}; stock would write {fallback}")
                entry["stock_fallback"] = fallback
        try:
            entry["target_bytes"] = nbytes(want, row["shape"])
        except ValueError:
            entry["target_bytes"] = nbytes(entry.get("stock_fallback", "f16"), row["shape"]) \
                if entry.get("stock_fallback", "f16") in TYPE_ID else row["nbytes"]
        tensors.append(entry)
        if quantizable(row):
            (experts if role == "routed_expert" else pinned).append((row["name"], want))
    add("block_divisibility", "fail" if refusals else "pass",
        "; ".join(refusals[:20]) or f"every tensor sent to {target} has whole " + "/".join(str(block_of(t)[0]) for t in target_types(types)) + "-value rows")
    unsafe = [name for name, _ in pinned + experts if not SAFE_NAME.match(name)]
    add("pattern_safe_names", "fail" if unsafe else "pass",
        ", ".join(unsafe[:20]) or "tensor names need no regex escaping beyond '.'")
    routed = sum(1 for t in tensors if t["role"] == "routed_expert")
    add("routed_experts_found", "pass" if routed else "fail", f"{routed} routed expert weight tensors")

    overrides = pins(experts) + pins(pinned)
    imatrix_record = file_record(imatrix, True) if imatrix else None
    low_bit = bits_per_weight(lowest) < 3.5
    add("imatrix_named", "fail" if low_bit and not imatrix_record else "pass",
        (f"{target} is down to {bits_per_weight(lowest):.3f} bpw; " + ("imatrix " + imatrix_record["name"]
         if imatrix_record else "no imatrix given")) if low_bit else f"{target} does not need one")

    ftype = FTYPE.get(lowest, "Q8_0")  # every quantizable tensor is pinned; the file type only labels the file
    flags = ["--allow-requantize"]
    if imatrix:
        flags += ["--imatrix", str(imatrix)]
    for pin in overrides:
        flags += ["--tensor-type", f"{pin['pattern']}={pin['type']}"]
    tail = [ftype] + ([str(threads)] if threads else [])
    argv = [llama_quantize, *flags, *(["--keep-split"] if keep_split else []), str(first), output, *tail]

    # Timing probe: keep layers 0..L (names unchanged, so every pin still matches) and prune the rest.
    layers = sorted({int(m[1]) for t in tensors if (m := re.match(r"^blk\.(\d+)\.", t["name"]))})
    routed_layers = sorted({int(t["name"].split(".")[1]) for t in tensors
                            if t["role"] == "routed_expert" and t["source_type"] != t["target_type"]})
    probe = None
    if routed_layers:
        keep = probe_layer if probe_layer is not None else routed_layers[0]
        pruned = [n for n in layers if n > keep]
        probe_out = str(Path(out_prefix).with_name(Path(out_prefix).name + "-probe.gguf"))
        probe_bytes = sum(t["target_bytes"] for t in tensors
                          if not re.match(r"^blk\.(\d+)\.", t["name"]) or int(t["name"].split(".")[1]) <= keep)
        probe = {"keep_layers": f"0..{keep}", "converted_routed_layers": sum(1 for n in routed_layers if n <= keep),
                 "total_routed_layers": len(routed_layers), "output": probe_out, "bytes": probe_bytes,
                 "argv": [llama_quantize, *flags, *(["--prune-layers", ",".join(map(str, pruned))] if pruned else []),
                          str(first), probe_out, *tail],
                 "projection": "full_seconds ~= probe_seconds * total_routed_layers / converted_routed_layers"}

    alignment = pack["alignment"]
    n_files = len(files) if keep_split else 1
    header = sum(f.get("header_bytes", 0) for f in files)  # output headers carry the same tensor table
    data = sum(padded(t["target_bytes"], alignment) for t in tensors)
    source_bytes = sum(f["bytes"] for f in files)
    estimate = {"source_bytes": source_bytes, "output_data_bytes": data, "output_bytes": data + header,
                "output_bytes_tolerance": n_files * HEADER_SLACK, "probe_bytes": probe["bytes"] if probe else 0}
    estimate["temp_peak_bytes"] = estimate["output_bytes"] + estimate["probe_bytes"]
    estimate["note"] = ("llama-quantize writes the output in place (no temporary copy); the peak is the new pack "
                        "beside the source, plus the probe pack if it is not deleted first")
    parent = Path(out_prefix).parent
    if parent.is_dir():
        free = shutil.disk_usage(parent).free
        estimate["free_bytes_at_plan"] = free
        add("disk_free", "pass" if free >= estimate["temp_peak_bytes"] else "fail",
            f"{free} bytes free at {parent}, peak {estimate['temp_peak_bytes']}")
    if disk_grant_bytes is not None:
        ok = estimate["temp_peak_bytes"] <= int(disk_grant_bytes)
        add("disk_grant", "pass" if ok else "fail", f"peak {estimate['temp_peak_bytes']} vs grant {disk_grant_bytes}")

    by_role = {}
    for t in tensors:
        by_role.setdefault(t["role"], {"tensors": 0, "source_types": {}, "target_types": {}})
        r = by_role[t["role"]]
        r["tensors"] += 1
        r["source_types"][t["source_type"]] = r["source_types"].get(t["source_type"], 0) + 1
        r["target_types"][t["target_type"]] = r["target_types"].get(t["target_type"], 0) + 1
    recipe = {
        "format": FORMAT,
        "engine": {"tool": "llama-quantize", "source": "llama.cpp", "revision": "9048bad8d6e3a0f9f1726e238e451181c7e02613"},
        "source": {"files": [{k: v for k, v in f.items() if k != "tensors"} for f in files],
                   "digest": pack_digest(files), "tensors": len(tensors), "bytes": source_bytes, "alignment": alignment,
                   "architecture": pack["metadata"].get("general.architecture")},
        "target": target, "ftype": ftype,
        "roles": {"routed_expert": target, "routed_expert_by_projection": {k: types[k] for k in ("gate", "up", "down")},
                  "*": "source type"},
        "role_census": by_role,
        "imatrix": imatrix_record,
        "overrides": overrides,
        "output": {"path": output, "keep_split": keep_split, "prefix": out_prefix,
                   "files": [f"{out_prefix}-{i:05d}-of-{len(files):05d}.gguf" for i in range(1, len(files) + 1)]
                   if keep_split else [output]},
        "argv": argv,
        "probe": probe,
        "estimate": estimate,
        "disk_grant_bytes": disk_grant_bytes,
        "tensors": sorted(tensors, key=lambda t: (t["shard"], t["name"])),
    }
    if not any(f.get("sha256") for f in files):
        add("source_digest", "info", "header digests only; pass hash=true or plan from the ingest manifest "
            "before verify_recipe, which requires a sha256 per file")
    return recipe, checks


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("pack_manifest")
    p.add_argument("--target", default="q2_k")
    p.add_argument("--imatrix")
    p.add_argument("--output")
    p.add_argument("--llama-quantize", default="llama-quantize")
    p.add_argument("--hash", action="store_true")
    p.add_argument("--disk-grant-bytes", type=int)
    p.add_argument("--out", help="write the recipe JSON here")
    a = p.parse_args()
    recipe, checks = plan_recipe(a.pack_manifest, a.target, a.imatrix, a.output, a.llama_quantize,
                                 want_hash=a.hash, disk_grant_bytes=a.disk_grant_bytes)
    text = json.dumps(recipe, indent=1)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
    print(json.dumps(checks, indent=1))
    sys.exit(1 if any(c["status"] == "fail" for c in checks) else 0)


if __name__ == "__main__":
    main()
