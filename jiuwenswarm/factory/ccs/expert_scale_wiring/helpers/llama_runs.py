"""Capped, niced runs of the stock llama.cpp example binaries the scale wiring checks use. Stdlib only.

  simple(bindir, pack, capped, cap)                   greedy llama-simple: (rc, stdout, stderr tail, cap note)
  eval_callback(bindir, pack, log, capped, cap, jobs)  llama-eval-callback dump of one token into log: rc

`capped` is the checkout helper (cgroup MemoryMax + nice). These run native binaries only.
"""
from pathlib import Path
import subprocess

PROMPT = "The capital of France is"


def simple(bindir, pack, capped, cap, n=32, prompt=PROMPT):
    # llama-simple parses only its own short flags (-m model, -n tokens), not the common argument set
    command, note = capped([str(Path(bindir) / "llama-simple"), "-m", str(pack), "-n", str(n), prompt], cap)
    proc = subprocess.run(command, capture_output=True, timeout=900)
    return proc.returncode, proc.stdout, proc.stderr.decode(errors="replace")[-800:], note


def eval_callback(bindir, pack, log, capped, cap, jobs, prompt=PROMPT):
    command, _ = capped([str(Path(bindir) / "llama-eval-callback"), "--model", str(pack), "-p", prompt, "-n", "1",
                         "-t", str(jobs)], cap)
    with open(log, "wb") as handle:
        proc = subprocess.run(command, stdout=handle, stderr=subprocess.STDOUT, timeout=900)
    return proc.returncode
