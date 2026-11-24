"""Role-by-role scale inventory of a ModelOpt NVFP4 checkpoint, from its index and shard headers. Stdlib only.

A safetensors file starts with an 8-byte little-endian header length N and N bytes of JSON
({name: {dtype, shape, data_offsets}}). Reading the headers costs a few KiB per shard, never tensor data.

  python scale_inventory.py INDEX.json --headers DIR_OR_FILES... [--out inventory.json]
  python scale_inventory.py INDEX.json --url https://host/path/to/repo/resolve/main --shards 5,92 --out inv.json

`--headers` takes shard files (*.safetensors) or header JSON files named after the shard number
(`hdr-00005.json`, `00005.json`) or the shard (`model-00005-of-00127.safetensors.json`).
With `--url` the header of each listed shard is fetched with two HTTP range requests (actor use only).
"""
import argparse
import json
from pathlib import Path
import re
import struct
import sys
import urllib.request

FORMAT = "factory.nvfp4-scale-inventory/1"
STACKED = re.compile(r"^(?P<prefix>.*\.layers\.(?P<layer>\d+)\.mlp\.experts\.(?P<proj>gate_up|down)_proj)"
                     r"(?P<suffix>|_weight_scale|_weight_scale_2|_input_scale)$")
ROLE = {"": "packed_weight", "_weight_scale": "block_scale", "_weight_scale_2": "global_scale",
        "_input_scale": "input_scale"}
SHARD_NO = re.compile(r"(\d{5})")


def parse_header(raw):
    header = json.loads(raw)
    header.pop("__metadata__", None)
    return header


def read_local_header(path):
    path = Path(path)
    if path.suffix == ".json":
        return parse_header(path.read_bytes())
    with open(path, "rb") as handle:
        n = struct.unpack("<Q", handle.read(8))[0]
        if n > 1 << 28:
            raise ValueError(f"{path.name}: implausible header length {n}")
        return parse_header(handle.read(n))


def read_remote_header(url):
    def ranged(start, end):
        req = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read()
    n = struct.unpack("<Q", ranged(0, 7))[0]
    return parse_header(ranged(8, 8 + n - 1))


def shard_for(header_path, shards):
    """The index shard a header file belongs to."""
    name = Path(header_path).name
    if name in shards:
        return name
    if name.endswith(".json") and name[:-5] in shards:
        return name[:-5]
    m = SHARD_NO.search(name)
    if m:
        hits = [s for s in shards if f"-{m[1]}-of-" in s]
        if len(hits) == 1:
            return hits[0]
    raise ValueError(f"{name}: cannot tell which shard of the index this header belongs to")


def header_files(items):
    out = []
    for item in items:
        p = Path(item)
        if p.is_dir():
            out += sorted(list(p.glob("*.safetensors")) + [j for j in p.glob("*.json") if SHARD_NO.search(j.name)
                                                          and "index" not in j.name])
        else:
            out.append(p)
    return out


def inventory(index_path, headers=None, url=None, url_shards=()):
    index_path = Path(index_path)
    index = json.loads(index_path.read_text(encoding="utf-8"))
    weight_map = index["weight_map"]
    shards = sorted(set(weight_map.values()))
    read = {}
    for path in header_files(headers or []):
        read[shard_for(path, shards)] = read_local_header(path)
    for no in url_shards:
        shard = shard_for(f"{int(no):05d}", shards)
        read[shard] = read_remote_header(url.rstrip("/") + "/" + shard)
    tensors = {}
    for shard, header in read.items():
        for name, meta in header.items():
            tensors[name] = {"dtype": meta["dtype"], "shape": meta["shape"], "file": shard}

    layers, experts = set(), {}
    for name, shard in weight_map.items():
        m = STACKED.match(name)
        if m and "vision" not in name and "audio" not in name:
            layer = int(m["layer"])
            layers.add(layer)
            slot = experts.setdefault(layer, {}).setdefault(m["proj"], {})
            slot[ROLE[m["suffix"]]] = tensors.get(name, {"file": shard})
    quantized = sorted(l for l, p in experts.items() if all("block_scale" in v for v in p.values()))
    excluded = sorted(l for l in experts if l not in quantized)

    roles, findings = {}, []
    for layer, projs in sorted(experts.items()):
        for proj, slot in projs.items():
            for role, meta in slot.items():
                if "dtype" not in meta:
                    continue
                key = f"{proj}.{role if layer in quantized else 'bf16_expert' if role == 'packed_weight' else role}"
                sig = f"{meta['dtype']} {meta['shape']}"
                roles.setdefault(key, {}).setdefault(sig, 0)
                roles[key][sig] += 1
    problems = []
    for layer in quantized:
        for proj, slot in experts[layer].items():
            w, s, s2 = slot.get("packed_weight", {}), slot.get("block_scale", {}), slot.get("global_scale", {})
            if "shape" not in w or "shape" not in s:
                continue
            e, rows, packed = w["shape"]
            if w["dtype"] != "U8" or s["dtype"] != "F8_E4M3" or s["shape"] != [e, rows, packed * 2 // 16]:
                problems.append(f"layer {layer} {proj}: weight {w['dtype']} {w['shape']}, block scale {s['dtype']} {s['shape']}")
            if "shape" in s2:
                want = [e, 2] if proj == "gate_up" else [e]
                if s2["shape"] != want or s2["dtype"] != "F32":
                    problems.append(f"layer {layer} {proj}: weight_scale_2 {s2['dtype']} {s2['shape']}, expected F32 {want}")
    seen = {k: v for k, v in roles.items()}
    if any(k == "gate_up.global_scale" and any("[" in s and ", 2]" in s for s in v) for k, v in seen.items()):
        findings.append("gate_up_proj_weight_scale_2 is [E, 2]: column 0 scales the gate half, column 1 the up half "
                        "(two values per expert, not one shared value)")
    if "gate_up.packed_weight" in seen:
        findings.append("gate_up_proj packs gate rows first, then up rows, along dim 1 ([E, 2*I, M/2])")
    if excluded:
        findings.append(f"layers {excluded} have no block scale: their experts are excluded from NVFP4 and stay as stored")
    dense = {}
    for name, meta in tensors.items():
        if not STACKED.match(name):
            dense.setdefault(meta["dtype"], 0)
            dense[meta["dtype"]] += 1
    quant = None
    for candidate in ("hf_quant_config.json", "config.json"):
        f = index_path.parent / candidate
        if f.is_file():
            data = json.loads(f.read_text(encoding="utf-8"))
            quant = data.get("quantization") or data.get("quantization_config") or quant
            if quant:
                break
    return {"format": FORMAT, "index": str(index_path), "total_size": index.get("metadata", {}).get("total_size"),
            "shards": len(shards), "headers_read": sorted(read), "n_layers": len(layers),
            "quantized_layers": quantized, "excluded_layers": excluded, "quantization": quant,
            "roles": roles, "other_tensors_by_dtype": dense, "experts": {str(k): v for k, v in sorted(experts.items())},
            "layout_problems": problems, "findings": findings}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("index")
    ap.add_argument("--headers", nargs="*", default=[])
    ap.add_argument("--url")
    ap.add_argument("--shards", default="", help="comma list of shard numbers to fetch with --url")
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    shards = [s for s in args.shards.split(",") if s]
    inv = inventory(args.index, args.headers, args.url, shards)
    text = json.dumps(inv, indent=1)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    summary = {k: inv[k] for k in ("shards", "headers_read", "quantized_layers", "excluded_layers", "roles",
                                   "layout_problems", "findings")}
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
