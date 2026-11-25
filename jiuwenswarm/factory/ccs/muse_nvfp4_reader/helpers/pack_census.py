"""verify_pack: census of a written Muse NVFP4 GGUF pack against the checkpoint itself. Stdlib only.

The layer plan comes from the checkpoint's own `model.safetensors.index.json` (source_index, required): a layer
whose stacked experts have a `_weight_scale` is quantized, the others are excluded. An agent-written inventory
or quantized_layers list is only cross-checked against it, never trusted alone, and a plan with no quantized
layer fails (a stock all-BF16 pack is not an NVFP4 pack). The `.scale` vectors are compared value for value
with the checkpoint's `_weight_scale_2` (gate = column 0, up = column 1, down = the vector), read from the
shard header plus one small range read per tensor, so a gate/up column swap fails.

Fails closed: an unreadable shard, a missing source index, or a scale_2 that cannot be read is a failing check,
never a skip. Reads headers and the small F32 `.scale` tensors only. Returns the pack manifest
(factory.pack-manifest/1, the format the pack compiler reads) with per-file sha256 when hash is true.
"""
from pathlib import Path
import json
import re
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gguf_pack import census, load_pack, pack_digest, read_tensor, role_of  # noqa: E402
from scale_inventory import STACKED, inventory as read_inventory, parse_header  # noqa: E402

STAGE = "native CC execution"
MANIFEST = "factory.pack-manifest/1"
KINDS = ("gate", "up", "down")
DEFAULT_TYPES = ("f32", "f16", "bf16", "nvfp4")
FLOATS = ("f32", "f16", "bf16")
EXPERT = re.compile(r"^blk\.(\d+)\.ffn_(gate|up|down)_exps\.weight$")
SMALL = 1 << 20  # a scale vector read from a shard is [E] or [E, 2] F32: KiB, never more than this


class Checkpoint:
    """Header and small range reads of the shards next to a safetensors index (or hdr-NNNNN.json headers)."""

    def __init__(self, index_path):
        self.index_path = Path(index_path)
        self.root = self.index_path.parent
        self.weight_map = json.loads(self.index_path.read_text(encoding="utf-8"))["weight_map"]
        self.headers = {}
        self.names = {}  # (layer, proj, suffix) -> tensor name
        for name in self.weight_map:
            m = STACKED.match(name)
            if m and "vision" not in name and "audio" not in name:
                self.names[(int(m["layer"]), m["proj"], m["suffix"])] = name

    def header(self, shard):
        """(header dict, data start, shard path or None when only a header JSON is present)."""
        if shard not in self.headers:
            path = self.root / shard
            if path.is_file():
                with open(path, "rb") as handle:
                    n = struct.unpack("<Q", handle.read(8))[0]
                    if n > 1 << 28:
                        raise ValueError(f"{shard}: implausible header length {n}")
                    self.headers[shard] = (parse_header(handle.read(n)), 8 + n, path)
            else:
                no = re.search(r"(\d{5})-of-", shard)
                cands = [self.root / f"{shard}.json"] + ([self.root / f"hdr-{no[1]}.json", self.root / f"{no[1]}.json"] if no else [])
                hit = next((c for c in cands if c.is_file()), None)
                if hit is None:
                    raise ValueError(f"{shard}: neither the shard nor its header JSON is beside the index")
                self.headers[shard] = (parse_header(hit.read_bytes()), None, None)
        return self.headers[shard]

    def meta(self, name):
        shard = self.weight_map[name]
        header, _, _ = self.header(shard)
        if name not in header:
            raise ValueError(f"{name} is not in the header of {shard}")
        return header[name]

    def f32(self, name):
        """Values of a small F32 tensor (flattened, row-major) by one range read."""
        shard = self.weight_map[name]
        header, start, path = self.header(shard)
        meta = header.get(name)
        if meta is None:
            raise ValueError(f"{name} is not in the header of {shard}")
        if meta["dtype"] != "F32":
            raise ValueError(f"{name} is {meta['dtype']}, expected F32")
        lo, hi = meta["data_offsets"]
        if hi - lo > SMALL:
            raise ValueError(f"{name} is {hi - lo} bytes; refusing a large read")
        if path is None:
            raise ValueError(f"{shard} is not present (header JSON only): {name} values cannot be read")
        with open(path, "rb") as handle:
            handle.seek(start + lo)
            data = handle.read(hi - lo)
        if len(data) != hi - lo:
            raise ValueError(f"{name}: data truncated")
        return list(struct.unpack(f"<{len(data) // 4}f", data)), meta["shape"]


def layer_plan(source_index, inventory=None, quantized_layers=None):
    """(quantized, excluded, n_layers, input_scale_layers, experts, problems) from the source index; the
    optional inventory / quantized_layers are cross-checked against it. Raises ValueError without an index."""
    if not source_index:
        raise ValueError("no source_index (the checkpoint's model.safetensors.index.json): the layer plan is "
                         "unknown; an agent-written inventory alone is not a reference (fails closed)")
    inv = read_inventory(source_index)
    quantized, excluded, experts = inv["quantized_layers"], inv["excluded_layers"], inv.get("experts", {})
    problems = []
    if inventory:
        other = json.loads(Path(inventory).read_text(encoding="utf-8"))
        if sorted(other.get("quantized_layers") or []) != quantized or sorted(other.get("excluded_layers") or []) != excluded:
            problems.append(f"inventory {Path(inventory).name} disagrees with the source index: quantized "
                            f"{other.get('quantized_layers')}, excluded {other.get('excluded_layers')}")
    if quantized_layers is not None and sorted(int(x) for x in quantized_layers) != quantized:
        problems.append(f"quantized_layers {sorted(quantized_layers)} disagrees with the source index")
    with_input = sorted(int(l) for l, p in experts.items() if any("input_scale" in v for v in p.values()))
    return quantized, excluded, inv.get("n_layers"), with_input, experts, problems


def f32_values(row):
    data = read_tensor(row)
    return list(struct.unpack(f"<{len(data) // 4}f", data))


def _f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]


def scale_match(T, ck, layers):
    """Compare every sampled pack .scale / .input_scale with the checkpoint column it must hold.
    Returns (bad, compared)."""
    bad, compared = [], 0
    for l in layers:
        for proj, kinds in (("gate_up", (("gate", 0), ("up", 1))), ("down", (("down", None),))):
            for suffix, gsuffix in (("_weight_scale_2", ".scale"), ("_input_scale", ".input_scale")):
                name = ck.names.get((l, proj, suffix))
                if name is None:
                    if suffix == "_weight_scale_2":
                        bad.append(f"layer {l} {proj}: no {suffix} in the source index")
                    continue
                try:
                    values, shape = ck.f32(name)
                except (OSError, ValueError, KeyError) as exc:
                    bad.append(f"{name}: {exc}")
                    continue
                cols = shape[1] if len(shape) == 2 else 1
                n = shape[0] if shape else 0
                columns = [[_f32(values[e * cols + c]) for e in range(n)] for c in range(cols)]
                for kind, col in kinds:
                    base = f"blk.{l}.ffn_{kind}_exps"
                    row = T.get(base + gsuffix)
                    if row is None:
                        continue  # a missing tensor is reported by expert_scales / input_scales
                    try:
                        got = f32_values(row)
                    except (OSError, ValueError) as exc:
                        bad.append(f"{base}{gsuffix}: {exc}")
                        continue
                    want_col = 0 if col is None or cols == 1 else col
                    if proj == "gate_up" and cols != 2 and suffix == "_weight_scale_2":
                        bad.append(f"{name} has shape {shape}, expected [E, 2] (gate, up)")
                        continue
                    compared += 1
                    if got != columns[want_col]:
                        other = [c for c in range(cols) if c != want_col and got == columns[c]]
                        bad.append(f"{base}{gsuffix} != {name}[:, {want_col}]" + (
                            f" (it holds column {other[0]}: gate/up columns swapped)" if other else ""))
    return bad, compared


def verify_pack(pack_path, source_index, inventory=None, quantized_layers=None, expect_bytes_range=None,
                allowed_types=None, hash_files=False, scale_sample_layers=None):
    checks = []

    def add(name, ok, detail, status=None):
        checks.append({"name": name, "status": status or ("pass" if ok else "fail"), "stage": STAGE, "detail": detail})

    try:
        pack = load_pack(pack_path, hash_files=hash_files)
    except (OSError, ValueError) as exc:
        add("pack_readable", False, f"{pack_path}: {exc}")
        return checks, None
    T, meta = pack["tensors"], pack["metadata"]
    add("pack_readable", True, f"{len(pack['files'])} shard(s), {len(T)} tensors, every header read and every tensor inside its file")

    arch = meta.get("general.architecture")
    n_expert = meta.get(f"{arch}.expert_count")
    n_block = meta.get(f"{arch}.block_count")
    ck = None
    try:
        quantized, excluded, n_layers, with_input, experts, problems = layer_plan(source_index, inventory, quantized_layers)
        ck = Checkpoint(source_index)
        add("layer_plan", bool(quantized) and not problems,
            "; ".join(problems) if problems else (
                f"from the source index: quantized {len(quantized)} layers, excluded {excluded}" if quantized else
                "the source index names no quantized expert layer (no stacked expert has a _weight_scale): "
                "an NVFP4 pack has nothing to carry"))
    except (OSError, ValueError, KeyError) as exc:
        add("layer_plan", False, str(exc))
        quantized, excluded, n_layers, with_input, experts = None, None, None, None, None

    pack_layers = sorted({int(m[1]) for n in T if (m := EXPERT.match(n))})
    expect_layers = list(range(int(n_block))) if n_block is not None else None
    missing = [f"blk.{l}.ffn_{k}_exps.weight" for l in (expect_layers or pack_layers) for k in KINDS
               if f"blk.{l}.ffn_{k}_exps.weight" not in T]
    plan_layers = sorted(set(quantized or []) | set(excluded or []))
    mismatch = excluded is not None and plan_layers != pack_layers
    add("expert_layers_complete", bool(pack_layers) and not missing and not mismatch,
        f"missing {missing[:8]}" if missing else (f"pack expert layers {pack_layers[:4]}... != checkpoint {plan_layers[:4]}..." if mismatch
                                                  else f"{len(pack_layers)} layers x gate/up/down routed experts"))

    if quantized:
        wrong, scale_bad, input_bad = [], [], []
        for l in quantized:
            for k in KINDS:
                base = f"blk.{l}.ffn_{k}_exps"
                row = T.get(base + ".weight")
                if row is None:
                    continue
                if row["type"] != "nvfp4":
                    wrong.append(f"{base}.weight={row['type']}")
                e = row["shape"][2] if len(row["shape"]) == 3 else None
                s = T.get(base + ".scale")
                if s is None:
                    scale_bad.append(f"{base}.scale missing")
                elif s["type"] != "f32" or s["shape"] != [e] or (n_expert is not None and e != n_expert):
                    scale_bad.append(f"{base}.scale {s['type']} {s['shape']} (weight has {e} experts, expert_count {n_expert})")
                elif any(not (v > 0) for v in f32_values(s)):
                    scale_bad.append(f"{base}.scale has a non-positive or NaN value")
                i = T.get(base + ".input_scale")
                if l in with_input and i is None:
                    input_bad.append(f"{base}.input_scale missing")
                elif i is not None and (i["type"] != "f32" or i["shape"] != [e]):
                    input_bad.append(f"{base}.input_scale {i['type']} {i['shape']}")
        add("expert_types", not wrong, wrong[:8] or f"{len(quantized) * 3} routed expert weights in quantized layers are nvfp4 (type 40)")
        add("expert_scales", not scale_bad, scale_bad[:8] or "every NVFP4 expert weight has an F32 [n_expert] .scale, all positive")
        add("input_scales", not input_bad, input_bad[:8] or f"input scales carried for {len(with_input)} layers")
        sample = sorted(set(quantized) & set(int(x) for x in scale_sample_layers)) if scale_sample_layers else quantized
        if not sample:
            add("scale_values", False, f"scale_sample_layers {scale_sample_layers} names no quantized layer")
        else:
            bad, compared = scale_match(T, ck, sample)
            add("scale_values", not bad and compared > 0, bad[:8] or (
                f"{compared} .scale/.input_scale vectors of {len(sample)} layers equal the checkpoint's "
                "_weight_scale_2 / _input_scale columns (gate 0, up 1, down the vector)" if compared else
                "no pack scale vector could be compared with the checkpoint"))
    else:
        for name in ("expert_types", "expert_scales", "scale_values"):
            add(name, False, "no layer plan with quantized layers to judge against (fails closed)")

    if excluded is not None:
        kept_bad, seen = [], set()
        for l in excluded:
            for k in KINDS:
                base = f"blk.{l}.ffn_{k}_exps"
                row = T.get(base + ".weight")
                if row is None:
                    continue
                proj = "down" if k == "down" else "gate_up"
                src, why = None, ""
                name = ck.names.get((l, proj, "")) if ck else None
                if name:
                    try:
                        src = ck.meta(name)["dtype"]
                    except (OSError, ValueError, KeyError) as exc:
                        why = f" (header unread: {exc})"
                # with the checkpoint header the dtype is known and must be kept; without it any float type
                # passes (the output type then follows --outtype)
                ok_type = row["type"] == src.lower() if src else row["type"] in FLOATS
                if not ok_type or base + ".scale" in T:
                    kept_bad.append(f"{base}.weight={row['type']} (checkpoint {src or 'dtype unknown'}{why}), "
                                    f".scale {'present' if base + '.scale' in T else 'absent'}")
                seen.add(f"{row['type']}" + ("" if src else " (checkpoint dtype unknown)"))
        add("excluded_layers_kept", not kept_bad, kept_bad[:8] or f"layers {excluded}: experts at {sorted(seen)}, no .scale")
    else:
        add("excluded_layers_kept", False, "no layer plan to judge against (fails closed)")

    elsewhere = [n for n, r in T.items() if r["type"] == "nvfp4" and role_of(n) != "routed_expert"]
    add("nvfp4_only_on_experts", not elsewhere, f"NVFP4 outside routed experts: {elsewhere[:8]}" if elsewhere
        else "no NVFP4 tensor outside the routed experts (attention, router, latent projections kept)")
    allowed = tuple(t.lower() for t in (allowed_types or DEFAULT_TYPES))
    odd = sorted({f"{r['type']}" for r in T.values() if r["type"] not in allowed})
    add("tensor_types", not odd, f"unexpected types {odd} (allowed {list(allowed)})" if odd else f"all types in {list(allowed)}")

    total = sum(f["bytes"] for f in pack["files"])
    if expect_bytes_range:
        lo, hi = expect_bytes_range
        add("total_bytes", lo <= total <= hi, f"{total} bytes, expected [{lo}, {hi}]")
    else:
        add("total_bytes", True, f"{total} bytes", "info")

    by_type = {}
    for r in T.values():
        by_type[r["type"]] = by_type.get(r["type"], 0) + 1
    files = [{k: f[k] for k in ("name", "bytes", "mtime", "header_sha256", "sha256") if k in f} for f in pack["files"]]
    manifest = {"format": MANIFEST, "files": files, "digest": pack_digest(pack["files"]),
                "hashed": all("sha256" in f for f in files), "tensors": len(T), "total_bytes": total,
                "census": census(T), "census_by_type": by_type, "architecture": arch,
                "file_type": meta.get("general.file_type"),
                "layer_plan": {"quantized": quantized, "excluded": excluded, "source_index": str(source_index)}}
    return checks, manifest
