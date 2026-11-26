"""Time reading and repacking ONE expert of one stacked NVFP4 tensor, then project the full conversion.

Run it with the conversion venv before starting the full run (METHOD.md step 4):

  python time_one_expert.py --checkpoint /models/muse-nvfp4 --tree /src/llama.cpp [--layer 1] [--expert 0]

Reads only expert E of `layers.N.mlp.experts.{gate_up,down}_proj` (+ its block scale) through a safetensors
slice, repacks it with the tree's own `ModelBase._nvfp4_pack`, and prints JSON: seconds per expert per
projection, the projected repack seconds for all quantized layers, and the bytes one stacked tensor holds
when it is materialized (the peak a lazy writer keeps per tensor).
"""
import argparse
import json
from pathlib import Path
import re
import sys
import time


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--tree", required=True, help="llama.cpp tree whose conversion/base.py packs NVFP4")
    ap.add_argument("--layer", type=int, default=1)
    ap.add_argument("--expert", type=int, default=0)
    args = ap.parse_args()
    sys.path[:0] = [args.tree, str(Path(args.tree) / "gguf-py")]
    import torch  # noqa: F401
    from safetensors import safe_open
    from conversion.base import ModelBase  # the stock packer you will call

    ckpt = Path(args.checkpoint)
    weight_map = json.loads((ckpt / "model.safetensors.index.json").read_text())["weight_map"]
    quantized = sorted({int(m[1]) for n in weight_map
                        if (m := re.search(r"\.layers\.(\d+)\.mlp\.experts\.gate_up_proj_weight_scale$", n))})
    out = {"layer": args.layer, "expert": args.expert, "quantized_layers": len(quantized), "projections": {}}
    total = 0.0
    for proj in ("gate_up", "down"):
        name = next(n for n in weight_map if n.endswith(f".layers.{args.layer}.mlp.experts.{proj}_proj"))
        t0 = time.perf_counter()
        with safe_open(str(ckpt / weight_map[name]), "pt") as f:
            w_slice = f.get_slice(name)
            n_exp, rows, packed = w_slice.get_shape()
            w = w_slice[args.expert]
        with safe_open(str(ckpt / weight_map[name + "_weight_scale"]), "pt") as f:
            s = f.get_slice(name + "_weight_scale")[args.expert]
        t1 = time.perf_counter()
        raw, _ = ModelBase._nvfp4_pack(w, s)
        t2 = time.perf_counter()
        per_expert = t2 - t0
        total += per_expert * n_exp * len(quantized)
        out["projections"][proj] = {"read_s": round(t1 - t0, 4), "pack_s": round(t2 - t1, 4), "experts": n_exp,
                                    "stacked_packed_bytes": n_exp * raw.nbytes,
                                    "stacked_source_bytes": n_exp * rows * packed * (1 + 1 / 8)}
    out["projected_repack_s"] = round(total, 1)
    out["note"] = "read time is cold-cache only for the first run; the writer adds the GGUF write time"
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
