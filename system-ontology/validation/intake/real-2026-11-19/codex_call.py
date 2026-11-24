"""One model call through the Codex command line, the way the repository's own harness makes it
(benchmarks/ccbench/cclib/harness.py, CodexModel): one subprocess per call, an empty working folder, read-only
sandbox, nothing kept between calls. The model and its reasoning effort are the product's fixed ones
(jiuwenswarm/research/fixed_subscription.py): gpt-6.1-sol, medium.

    python codex_call.py ROLE      # the prompt on stdin, the reply on stdout

Every call keeps its prompt, reply, stdout and stderr in calls/<time>-ROLE/ beside this file.
"""
import os
import pathlib
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
CODEX = pathlib.Path.home() / "AppData/Local/OpenAI/Codex/bin/5449c1f0f26f1f98/codex.exe"
MODEL, EFFORT = "gpt-6.1-sol", "medium"


def main():
    role = sys.argv[1] if len(sys.argv) > 1 else "call"
    text = sys.stdin.buffer.read()
    d = HERE / "calls" / (time.strftime("%Y%m%d-%H%M%S") + "-" + role)
    d.mkdir(parents=True, exist_ok=False)
    (d / "prompt.txt").write_bytes(text)
    out = d / "reply.txt"
    argv = [str(CODEX), "exec", "--skip-git-repo-check", "-m", MODEL, "-c", f'model_reasoning_effort="{EFFORT}"',
            "-s", "read-only", "--ephemeral", "-C", str(d), "-o", str(out), "-"]
    t0 = time.time()
    try:
        r = subprocess.run(argv, input=text, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=float(os.environ.get('CODEX_TIMEOUT', '285')))
    except subprocess.TimeoutExpired as e:
        (d / "stderr.txt").write_bytes((e.stderr or b"") + b"\nTIMEOUT\n")
        sys.stderr.write("codex timed out; see " + str(d))
        return 3
    (d / "stdout.txt").write_bytes(r.stdout)
    (d / "stderr.txt").write_bytes(r.stderr)
    (d / "meta.txt").write_text(f"returncode {r.returncode}\nseconds {time.time() - t0:.1f}\nmodel {MODEL}\neffort {EFFORT}\n"
                                f"prompt_bytes {len(text)}\n", encoding="utf-8")
    if r.returncode != 0 or not out.exists():
        sys.stderr.write(f"codex exited {r.returncode}; see {d}\n" + r.stderr.decode("utf-8", "replace")[-400:])
        return 2
    sys.stdout.buffer.write(out.read_bytes())
    return 0


if __name__ == "__main__":
    sys.exit(main())
