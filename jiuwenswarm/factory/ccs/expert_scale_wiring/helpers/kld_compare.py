"""KL divergence of a pack against a reference pack with stock llama-perplexity. Stdlib only.

  python kld_compare.py --bin BUILD/bin --ref tiny-deqref-f32.gguf --model tiny-nvfp4-f32.gguf \
      --text README.md --work /tmp/kld [--ctx 128 --chunks 8 --threads 8] [--env GGML_CUDA_MMQ_PREC=q8]

Writes the reference logits once (--kl-divergence-base), then scores the model against them and prints JSON:
mean KLD, mean PPL(Q) and PPL(base), same-top-p, and the two log paths. Run it under your memory cap.
The verifier of this capsule parses the same lines with `parse`.
"""
import argparse
import json
import math
import os
from pathlib import Path
import re
import subprocess

FIELDS = {"mean_kld": r"^Mean\s+KLD:\s+(\S+)", "ppl_q": r"^Mean PPL\(Q\)\s*:\s*(\S+)",
          "ppl_base": r"^Mean PPL\(base\)\s*:\s*(\S+)", "same_top_p": r"^Same top p:\s*(\S+)"}


def parse(text):
    out = {}
    for key, pattern in FIELDS.items():
        m = re.search(pattern, text, re.MULTILINE)
        if m:
            try:
                out[key] = float(m.group(1))
            except ValueError:
                out[key] = float("nan")
    return out


def finite(values):
    return all(isinstance(v, float) and math.isfinite(v) for v in values)


def run(command, log, env=None, timeout=1800):
    with open(log, "wb") as handle:
        proc = subprocess.run(command, stdout=handle, stderr=subprocess.STDOUT, env=env, timeout=timeout)
    return proc.returncode, Path(log).read_text(errors="replace")


def kld(perplexity, ref, model, text, work, ctx=128, chunks=8, threads=None, prefix=(), env=None, base=None):
    """(result dict, base path). Reuses base when given; otherwise writes it from ref."""
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    common = ["-f", str(text), "-c", str(ctx), "--chunks", str(chunks)] + (["-t", str(threads)] if threads else [])
    if base is None:
        base = work / "kld-base.bin"
        rc, log = run([*prefix, perplexity, "-m", str(ref), "--kl-divergence-base", str(base), *common],
                      work / "kld-base.log", env)
        if rc or not base.is_file():
            return {"error": f"reference run exited {rc}", "log": str(work / "kld-base.log"), "tail": log[-800:]}, None
    name = Path(model).stem
    rc, log = run([*prefix, perplexity, "-m", str(model), "--kl-divergence-base", str(base), "--kl-divergence",
                   *common], work / f"kld-{name}.log", env)
    res = parse(log)
    res.update(rc=rc, log=str(work / f"kld-{name}.log"))
    if rc:
        res["tail"] = log[-800:]
    return res, base


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bin", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--text", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--ctx", type=int, default=128)
    ap.add_argument("--chunks", type=int, default=8)
    ap.add_argument("--threads", type=int)
    ap.add_argument("--env", action="append", default=[], help="KEY=VALUE for the scored run")
    args = ap.parse_args()
    env = dict(os.environ, **dict(e.split("=", 1) for e in args.env))
    res, _ = kld(str(Path(args.bin) / "llama-perplexity"), args.ref, args.model, args.text, args.work, args.ctx,
                 args.chunks, args.threads, env=env)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
