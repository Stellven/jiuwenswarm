"""Compare one layer slice of two llama-eval-callback dumps (stdlib only).

  python slice_compare.py CANDIDATE.log REFERENCE.log --layer 1 [--tol 0.05]

llama-eval-callback prints every named graph tensor with its first and last values per dimension and its sum.
For the layer, the expert matmul outputs ffn_moe_gate / ffn_moe_up / ffn_moe_down (named `..._scaled` when a
per-expert scale was applied) and the block output ffn_moe_out are matched by name (the `_scaled` suffix is
ignored) and compared over the printed values: max |cand - ref| / max |ref|. Prints JSON.

Why the matmul outputs and not only the logits: the Muse block RMS-normalizes each expert's output, so a wrong
up or down scale (a per-expert factor) nearly cancels before the logits; the matmul outputs still show it.
"""
import argparse
import json
import math
import re

HEADER = re.compile(r"common_debug_cb_eval:\s+(\S+) = \((\w+)\)")
NUMBER = re.compile(r"-?(?:\d+\.\d+(?:e[-+]?\d+)?|inf|nan)", re.IGNORECASE)
SUM = re.compile(r"^\s+sum\s*=\s*(\S+)")
NAMES = ("ffn_moe_gate", "ffn_moe_up", "ffn_moe_down", "ffn_moe_out")


def parse(path):
    """{name: (sum, [printed values])}, first occurrence of each name."""
    out, cur, vals = {}, None, []
    with open(path, errors="replace") as handle:
        for line in handle:
            m = HEADER.search(line)
            if m:
                cur, vals = m.group(1), []
                continue
            if cur is None:
                continue
            m = SUM.match(line)
            if m:
                try:
                    total = float(m.group(1))
                except ValueError:
                    total = float("nan")
                out.setdefault(cur, (total, vals))
                cur = None
            elif line.strip().startswith("["):
                vals += [float(x) for x in NUMBER.findall(line)]
    return out


def canonical(name):
    return re.sub(r"_scaled(-\d+)$", r"\1", name)


def compare(cand_log, ref_log, layer, tol=0.05):
    cand = {canonical(k): v for k, v in parse(cand_log).items()}
    ref = parse(ref_log)
    rows, worst = [], 0.0
    for base in NAMES:
        key = f"{base}-{layer}"
        if key not in cand or key not in ref:
            rows.append({"tensor": key, "error": "missing in " + ("candidate" if key not in cand else "reference")})
            worst = float("inf")
            continue
        (sa, va), (sb, vb) = cand[key], ref[key]
        if len(va) != len(vb) or not va:
            rows.append({"tensor": key, "error": f"printed {len(va)} vs {len(vb)} values"})
            worst = float("inf")
            continue
        scale = max(abs(x) for x in vb) or 1.0
        rel = max(abs(a - b) for a, b in zip(va, vb)) / scale
        if not all(math.isfinite(x) for x in va):
            rel = float("inf")
        rows.append({"tensor": key, "rel_err": rel, "sum_candidate": sa, "sum_reference": sb})
        worst = max(worst, rel)
    return {"layer": layer, "tol": tol, "worst_rel_err": worst, "ok": worst <= tol, "tensors": rows}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("candidate")
    ap.add_argument("reference")
    ap.add_argument("--layer", type=int, required=True)
    ap.add_argument("--tol", type=float, default=0.05)
    args = ap.parse_args()
    print(json.dumps(compare(args.candidate, args.reference, args.layer, args.tol), indent=1))


if __name__ == "__main__":
    main()
