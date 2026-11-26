"""verify_pack: census of a written Muse NVFP4 GGUF pack against the checkpoint's layer plan. Stdlib only.

Fails closed: an unreadable shard, or no layer plan (inventory, source index or quantized_layers), is a failing
check, never a skip. Reads headers and the small F32 `.scale` tensors only. Returns the pack manifest
(factory.pack-manifest/1, the format the pack compiler reads) with per-file sha256 when hash is true.
"""
from pathlib import Path
import json
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gguf_pack import census, load_pack, pack_digest, read_tensor, role_of  # noqa: E402
from scale_inventory import inventory as read_inventory  # noqa: E402

STAGE = "native CC execution"
MANIFEST = "factory.pack-manifest/1"
KINDS = ("gate", "up", "down")
DEFAULT_TYPES = ("f32", "f16", "bf16", "nvfp4")
FLOATS = ("f32", "f16", "bf16")
EXPERT = re.compile(r"^blk\.(\d+)\.ffn_(gate|up|down)_exps\.weight$")


def layer_plan(inventory=None, source_index=None, quantized_layers=None):
    """(quantized, excluded, n_layers, input_scale_layers, source) or raises ValueError."""
    if inventory:
        inv = json.loads(Path(inventory).read_text(encoding="utf-8"))
        src = "inventory"
    elif source_index:
        inv = read_inventory(source_index)
        src = "source_index"
    elif quantized_layers is not None:
        q = sorted(int(x) for x in quantized_layers)
        return q, None, None, None, None, "quantized_layers"
    else:
        raise ValueError("no inventory, source_index or quantized_layers: the layer plan is unknown (fails closed)")
    experts = inv.get("experts", {})
    with_input = sorted(int(l) for l, p in experts.items() if any("input_scale" in v for v in p.values()))
    return inv["quantized_layers"], inv["excluded_layers"], inv.get("n_layers"), with_input, experts, src


def f32_values(row):
    import struct
    data = read_tensor(row)
    return list(struct.unpack(f"<{len(data) // 4}f", data))


def verify_pack(pack_path, inventory=None, source_index=None, quantized_layers=None, expect_bytes_range=None,
                allowed_types=None, hash_files=False):
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
    try:
        quantized, excluded, n_layers, with_input, experts, basis = layer_plan(inventory, source_index, quantized_layers)
        add("layer_plan", True, f"from {basis}: quantized {len(quantized)} layers, excluded {excluded}")
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

    if quantized is not None:
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
                if with_input is not None and l in with_input and i is None:
                    input_bad.append(f"{base}.input_scale missing")
                elif i is not None and (i["type"] != "f32" or i["shape"] != [e]):
                    input_bad.append(f"{base}.input_scale {i['type']} {i['shape']}")
        add("expert_types", not wrong, wrong[:8] or f"{len(quantized) * 3} routed expert weights in quantized layers are nvfp4 (type 40)")
        add("expert_scales", not scale_bad, scale_bad[:8] or "every NVFP4 expert weight has an F32 [n_expert] .scale, all positive")
        if with_input is None:
            add("input_scales", True, "no source plan for input scales", "info")
        else:
            add("input_scales", not input_bad, input_bad[:8] or f"input scales carried for {len(with_input)} layers")
    else:
        add("expert_types", False, "no layer plan to judge against (fails closed)")
        add("expert_scales", False, "no layer plan to judge against (fails closed)")

    if excluded is not None:
        kept_bad, seen = [], set()
        for l in excluded:
            for k in KINDS:
                base = f"blk.{l}.ffn_{k}_exps"
                row = T.get(base + ".weight")
                if row is None:
                    continue
                src = ((experts or {}).get(str(l), {}).get("down" if k == "down" else "gate_up", {})
                       .get("packed_weight", {}).get("dtype"))
                # with a header-read inventory the checkpoint dtype is known and must be kept; from the index
                # alone it is not, and any float type passes (the output type then follows --outtype)
                ok_type = row["type"] == src.lower() if src else row["type"] in FLOATS
                if not ok_type or base + ".scale" in T:
                    kept_bad.append(f"{base}.weight={row['type']} (checkpoint {src or 'dtype unknown'}), "
                                    f".scale {'present' if base + '.scale' in T else 'absent'}")
                seen.add(f"{row['type']}" + ("" if src else " (checkpoint dtype unknown)"))
        add("excluded_layers_kept", not kept_bad, kept_bad[:8] or f"layers {excluded}: experts at {sorted(seen)}, no .scale")
    elif quantized is not None:
        add("excluded_layers_kept", True, "layer plan from quantized_layers only: excluded layers not named", "skipped")
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
                "layer_plan": {"quantized": quantized, "excluded": excluded}}
    return checks, manifest
