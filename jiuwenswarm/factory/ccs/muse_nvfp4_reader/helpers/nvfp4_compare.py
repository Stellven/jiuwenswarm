"""Compare a converted GGUF with the ModelOpt NVFP4 checkpoint it came from (verifier half, runtime stage).

Needs numpy, torch and safetensors (the conversion venv). Prints one JSON list of checks on stdout.

  python nvfp4_compare.py --gguf tiny-nvfp4.gguf --checkpoint tiny/nvfp4 [--gguf-py SRC/gguf-py]

For every stacked expert tensor `...layers.N.mlp.experts.{gate_up,down}_proj` of the checkpoint:
  * quantized layer (it has `_weight_scale`): the GGUF gate/up/down expert weights are ggml NVFP4 (type 40) with
    shape [in, rows, E]; their bytes equal the verifier's own repack of the source nibbles and E4M3 block scales
    (gate = rows [0, I), up = rows [I, 2I)); `.scale` is F32 [E] and equals weight_scale_2 column 0 (gate),
    column 1 (up) or the [E] vector (down) exactly; `.input_scale` likewise;
  * excluded layer (no `_weight_scale`): the expert weights are not NVFP4 and carry no `.scale`.
With `--gguf-py`, also dequantizes the GGUF blocks with that gguf-py and compares weight * .scale with the
checkpoint's own dequantization (E2M1 code * E4M3 block scale * weight_scale_2).
"""
import argparse
import json
from pathlib import Path
import re
import sys

import numpy as np
import torch
from safetensors import safe_open

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from gguf_pack import load_pack  # noqa: E402

STAGE = "runtime acceptance"
E2M1 = np.array([0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0], dtype=np.float32)
STACKED = re.compile(r"\.layers\.(\d+)\.mlp\.experts\.(gate_up|down)_proj$")


def rec(checks, name, ok, detail, status=None):
    checks.append({"name": name, "status": status or ("pass" if ok else "fail"), "stage": STAGE, "detail": detail})


def open_checkpoint(path):
    path = Path(path)
    index = path / "model.safetensors.index.json"
    if index.is_file():
        weight_map = json.loads(index.read_text())["weight_map"]
    else:
        files = sorted(path.glob("*.safetensors"))
        weight_map = {}
        for f in files:
            with safe_open(str(f), "pt") as h:
                weight_map.update({k: f.name for k in h.keys()})
    handles = {}

    def get(name):
        fn = weight_map[name]
        if fn not in handles:
            handles[fn] = safe_open(str(path / fn), "pt")
        return handles[fn].get_tensor(name)
    return weight_map, get


def repack(w, s):
    """Verifier's own model of ggml block_nvfp4: per 64 values, 4 UE4M3 scale bytes then 32 bytes of codes;
    each 16-value sub-block stores value k in the low nibble and value k+8 in the high nibble of byte k."""
    e, r, p = w.shape
    nb = p // 8
    vals = np.stack([w & 0x0F, w >> 4], axis=-1).reshape(e, r, nb, 16)
    qs = (vals[..., :8] | (vals[..., 8:] << 4)).astype(np.uint8).reshape(e, r, nb // 4, 32)
    d = (s & 0x7F).astype(np.uint8).reshape(e, r, nb // 4, 4)
    return np.concatenate([d, qs], axis=-1).reshape(e, r, nb // 4 * 36)


def source_dequant(w, s_f32, s2):
    e, r, p = w.shape
    codes = np.stack([w & 0x0F, w >> 4], axis=-1).reshape(e, r, p * 2)
    mag = E2M1[codes & 0x7]
    val = np.where(codes & 0x8, -mag, mag).reshape(e, r, p * 2 // 16, 16)
    return (val * (s_f32[..., None] * s2.reshape(e, 1, 1, 1))).reshape(e, r, p * 2)


def raw_bytes(row):
    return np.fromfile(row["file"], dtype=np.uint8, count=row["nbytes"], offset=row["start"])


def f32(row):
    if row["type"] != "f32":
        raise ValueError(f"{row['name']} is {row['type']}, not f32")
    return np.fromfile(row["file"], dtype="<f4", count=row["nbytes"] // 4, offset=row["start"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gguf", required=True)
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--gguf-py")
    args = ap.parse_args()
    checks = []
    pack = load_pack(args.gguf)
    T = pack["tensors"]
    weight_map, get = open_checkpoint(args.checkpoint)
    dequantize = None
    if args.gguf_py:
        sys.path.insert(0, args.gguf_py)
        try:
            from gguf.quants import dequantize as _dq  # noqa: E402
            from gguf.constants import GGMLQuantizationType  # noqa: E402
            dequantize = (_dq, GGMLQuantizationType(40))
        except Exception as exc:  # noqa: BLE001 - an older gguf-py without NVFP4 dequantization
            rec(checks, "effective_weights", False, f"gguf-py cannot dequantize NVFP4: {exc}", "skipped")

    stacked = sorted((int(m[1]), m[2], n) for n in weight_map if (m := STACKED.search(n)))
    if not stacked:
        rec(checks, "checkpoint_layout", False, "no stacked experts.{gate_up,down}_proj in the checkpoint")
        print(json.dumps(checks))
        return
    types, bytes_bad, scale_bad, input_bad, excluded_bad, eff_bad = [], [], [], [], [], []
    quantized, excluded, eff_max = set(), set(), 0.0
    for layer, proj, name in stacked:
        parts = [("gate", 0), ("up", 1)] if proj == "gate_up" else [("down", None)]
        if name + "_weight_scale" not in weight_map:
            excluded.add(layer)
            for kind, _ in parts:
                row = T.get(f"blk.{layer}.ffn_{kind}_exps.weight")
                if row is None or row["type"] == "nvfp4" or f"blk.{layer}.ffn_{kind}_exps.scale" in T:
                    excluded_bad.append(f"blk.{layer}.ffn_{kind}_exps: {row and row['type']}, scale "
                                        f"{'present' if f'blk.{layer}.ffn_{kind}_exps.scale' in T else 'absent'}")
            continue
        quantized.add(layer)
        w = get(name).numpy()
        s_t = get(name + "_weight_scale")
        s = s_t.view(torch.uint8).numpy()
        s_f = s_t.float().numpy()
        s2 = get(name + "_weight_scale_2").float().numpy().reshape(w.shape[0], -1)
        ins = get(name + "_input_scale").float().numpy().reshape(w.shape[0], -1) if name + "_input_scale" in weight_map else None
        half = w.shape[1] // 2
        for kind, col in parts:
            r0, r1 = (0, w.shape[1]) if col is None else ((0, half) if col == 0 else (half, w.shape[1]))
            col = 0 if col is None else col
            base = f"blk.{layer}.ffn_{kind}_exps"
            row = T.get(base + ".weight")
            if row is None or row["type"] != "nvfp4":
                types.append(f"{base}.weight: {row and row['type']}")
                continue
            want_shape = [w.shape[2] * 2, r1 - r0, w.shape[0]]
            if list(row["shape"]) != want_shape:
                types.append(f"{base}.weight shape {row['shape']} != {want_shape}")
                continue
            expect = repack(w[:, r0:r1], s[:, r0:r1])
            got = raw_bytes(row).reshape(expect.shape)
            if not np.array_equal(got, expect):
                diff = int((got != expect).sum())
                same_as_other = None
                if kind in ("gate", "up"):
                    o0, o1 = (half, w.shape[1]) if kind == "gate" else (0, half)
                    same_as_other = np.array_equal(got, repack(w[:, o0:o1], s[:, o0:o1]))
                bytes_bad.append(f"{base}.weight: {diff} bytes differ" + (" (holds the other half)" if same_as_other else ""))
            srow = T.get(base + ".scale")
            if srow is None or list(srow["shape"]) != [w.shape[0]]:
                scale_bad.append(f"{base}.scale {'missing' if srow is None else srow['shape']}")
            elif not np.array_equal(f32(srow), s2[:, col].astype(np.float32)):
                other = s2[:, 1 - col] if s2.shape[1] == 2 else None
                swapped = other is not None and np.array_equal(f32(srow), other.astype(np.float32))
                scale_bad.append(f"{base}.scale != weight_scale_2[:, {col}]" + (" (holds the other column)" if swapped else ""))
            if ins is not None:
                irow = T.get(base + ".input_scale")
                if irow is None:
                    input_bad.append(f"{base}.input_scale missing")
                elif not np.array_equal(f32(irow), ins[:, col].astype(np.float32)):
                    input_bad.append(f"{base}.input_scale != input_scale[:, {col}]")
            if dequantize and srow is not None and srow["type"] == "f32":
                dq, qt = dequantize
                eff = dq(raw_bytes(row).reshape(w.shape[0], r1 - r0, -1), qt).astype(np.float32)
                eff = eff * f32(srow).reshape(-1, 1, 1)
                ref = source_dequant(w[:, r0:r1], s_f[:, r0:r1], s2[:, col])
                scale = float(np.abs(ref).max()) or 1.0
                err = float(np.abs(eff - ref).max()) / scale
                eff_max = max(eff_max, err)
                if err > 1e-6:
                    eff_bad.append(f"{base}: max |w*scale - ref| / max|ref| = {err:.3e}")
    rec(checks, "expert_types", not types, types[:8] or f"quantized layers {sorted(quantized)}: gate/up/down NVFP4 (type 40), shapes [in, rows, E]")
    rec(checks, "blocks_bit_exact", not bytes_bad and not types, bytes_bad[:8] or "every NVFP4 block equals the repack of the source nibbles and E4M3 scales (gate rows first)")
    rec(checks, "expert_scales", not scale_bad and not types, scale_bad[:8] or ".scale F32 [E]: gate = scale_2[:, 0], up = scale_2[:, 1], down = scale_2")
    rec(checks, "input_scales", not input_bad and not types, input_bad[:8] or ".input_scale carried per half")
    rec(checks, "excluded_layers_kept", not excluded_bad, excluded_bad[:8] or f"excluded layers {sorted(excluded)}: experts kept at a float type, no .scale")
    if dequantize:
        rec(checks, "effective_weights", not eff_bad and not types, eff_bad[:8] or f"dequant(gguf) * .scale matches the checkpoint dequantization (max rel {eff_max:.1e})")
    print(json.dumps(checks))


if __name__ == "__main__":
    main()
