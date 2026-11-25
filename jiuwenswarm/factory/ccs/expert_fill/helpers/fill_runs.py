"""Capped, niced runs of stock and candidate llama.cpp binaries for the expert fill checks. Stdlib only.

  simple(bindir, pack, capped, cap, env, n)      greedy llama-simple: (rc, stdout bytes, stderr text, cap note)
  perplexity(bindir, pack, text, capped, cap, env, jobs)
                                                  llama-perplexity: (rc, final estimate or None, stderr text)
  markers(stderr)                                 the `expert_fill: active` lines
  stats(stderr)                                   {key: int} of the last `expert_fill: stats k=v ...` line, or None

The marker and stats line formats are the contract METHOD.md states: one `expert_fill: active ...` line per
context with the gate set (none without), and at context teardown one `expert_fill: stats calls=N ...
bytes_read=N reads=N fill_us=N ...` line (more keys allowed).
"""
import os
from pathlib import Path
import re
import subprocess

PROMPT = "The capital of France is"
GATE = "LLAMA_EXPERT_FILL"
STATS = re.compile(r"^.*expert_fill: stats (.*)$", re.M)
ACTIVE = re.compile(r"^.*expert_fill: active\b.*$", re.M)
PPL = re.compile(r"Final estimate: PPL = ([0-9.eE+-]+|nan|inf|-nan)\s*\+/-\s*([0-9.eE+-]+|nan|inf|-nan)")


def _env(extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith(GATE)}
    env.update(extra or {})
    return env


def simple(bindir, pack, capped, cap, env=None, n=32, prompt=PROMPT):
    # llama-simple parses only its own short flags (-m model, -n tokens), not the common argument set
    command, note = capped([str(Path(bindir) / "llama-simple"), "-m", str(pack), "-n", str(n), prompt], cap)
    proc = subprocess.run(command, capture_output=True, timeout=900, env=_env(env))
    return proc.returncode, proc.stdout, proc.stderr.decode(errors="replace"), note


def perplexity(bindir, pack, text, capped, cap, env=None, jobs=8, ctx=128, chunks=4):
    # -lv 4: the common logger shows the library's info lines (marker, stats) only at this verbosity
    command, _ = capped([str(Path(bindir) / "llama-perplexity"), "-lv", "4", "-m", str(pack), "-f", str(text), "-c", str(ctx),
                         "-b", str(ctx), "--chunks", str(chunks), "-t", str(jobs)], cap)
    proc = subprocess.run(command, capture_output=True, timeout=900, env=_env(env))
    err = proc.stderr.decode(errors="replace") + proc.stdout.decode(errors="replace")
    m = PPL.search(err)
    return proc.returncode, (m.group(1) if m else None), err


def markers(stderr):
    return ACTIVE.findall(stderr)


def stats(stderr):
    found = STATS.findall(stderr)
    if not found:
        return None
    out = {}
    for k, v in re.findall(r"(\w+)=(-?\d+)", found[-1]):
        out[k] = int(v)
    return out
