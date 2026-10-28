# Generic native JiuwenSwarm tasks

## Origin (ccbench copy)

Copied from cc-sweep-20261026/nativetask (sha256 in BASELINE-CODE-MANIFEST), changes:

- No `C:/Users` paths. Product code (`benchmarks.harbor_suite.{native_value,value_host,value_schedule}`) comes from `AI4R_CODE_ROOT`; the broker runs with the current interpreter instead of a fixed venv.
- `--out DIR` is required (plan, run, collect, init-ledger). Attempts, sessions and the ledger are written only under DIR; the old "must stay under nativetask/" rule is now "under --out". New `init-ledger --out DIR` creates `DIR/ledger.sqlite3` (a value_schedule campaign ledger; upstream caps: 256 calls, 10800 s; never overwrites).
- Fail fast: `run --execute` stops before writing anything if the codex binary is missing (`--binary`, `AI4R_CODEX_BIN`, or `codex` on PATH; the placeholder default `C:/PATH/TO/QUALIFIED/codex.exe` is gone) or if the native image is not present locally. The old code did check the binary, but only inside `execute()`, after the attempt record and session folders existed.
- Image identity: each executed attempt record (`attempts/<id>.json`) and `staging-receipt.json` now carry `image: {tag, id, repo_digests, inspected}` from `docker image inspect`.
- The English overlay of `native_value.py` (28 KB) is copied to `native-runtime-en/` (was `traps/native-runtime-en`).
- Tests use temp directories; 7 new/changed tests cover the binary check, the image check, image identity and `init-ledger`.
- Not copied: `attempts/`, `sessions/` (898 MB), `lock-*` outputs, `lock-ledger.sqlite3`, `TEST-OUTPUT.txt`.

Run everything through `scripts/ai4r-bench` (container `ai4r:cc-v1-baseline`, repo mounted read-only, output in `--out DIR`). Add `--host` to use the host Python. Env roots: `AI4R_CODE_ROOT` (product repo; default: this repo), `AI4R_BENCH_DATA` (old evidence root: traps, stored baselines), `AI4R_CODEX_BIN` (codex; default `codex` on PATH). Files written by the original harness had CRLF line endings on Windows; this copy writes LF, so compare old results after CRLF to LF.

```sh
# host only (it starts its own docker containers). One-time: a ledger.
sh scripts/ai4r-bench nativetask init-ledger --out OUT
sh scripts/ai4r-bench nativetask plan --task-file T/task.txt --inputs-dir T/inputs --ledger OUT/ledger.sqlite3 --out OUT
sh scripts/ai4r-bench nativetask run --task-file T/task.txt --inputs-dir T/inputs --ledger OUT/ledger.sqlite3 --attempt-id a1 --execute --out OUT   # 1 task, 1 rep
sh scripts/ai4r-bench selftest nativetask
```

`run_native_task.py` runs arbitrary public tasks through the existing native
JiuwenSwarm application, ordinary tools, and optionally one ordinary skill folder.
Default: `gpt-6.1-sol`, medium effort, 600 seconds, 80 model calls. The upstream
worker supports 1–600 seconds and 1–80 calls; larger values are rejected.
There is no measurement host, injected measurement script, private holdout,
HTTP app call, or CC verifier. An independent oracle measures the output later.
The task text is passed unchanged.

## Prerequisites

An operator must have an existing initialized `value_schedule` ledger **under
this folder**, the local `ai4r:cc-value-medium-20261026` image, Docker, and a
qualified signed-in host Codex executable. This driver never creates or resets a
ledger. It rejects a ledger outside `nativetask/` because SQLite writes there.
Supply only public files in the inputs directory; every file there is visible
to the agent. Supply an individual skill folder containing `SKILL.md`.
Inputs and skills containing symlinks or junctions are refused.

Reuse locations are fixed defaults: the integration worktree's Python,
`benchmarks.harbor_suite.{native_value,value_host,value_schedule}`, and the
English overlay at `../traps/native-runtime-en` (override with `--runtime`).
No reused source is edited. The worker imports `native_value` from that overlay
using `PYTHONPATH=/runtime:/opt/ai4r`.

## Commands

See "Origin" above for the entry command. `plan` is pure (no files, processes or ledger). `run` without `--execute` is a dry run that journals the ID. `run --execute` needs Docker, the native image, a ledger and a signed-in codex.
`--skill-dir DIR` adds one ordinary skill folder, `--model`, `--wall-s`, `--max-calls` set the limits. `collect --session-id ID --attempt-id NEW [--execute]` recollects local evidence.

## Native image

Default image tag: `ai4r:cc-value-medium-20261026` (the opponent of the sweep). It is not present locally and **no build recipe or digest was stored for it** (the old attempt records carry no digest). `docker image inspect` is now run for every executed attempt and the result is written into the attempt record.

Search done: the product repo (`deploy/`, `benchmarks/harbor_suite`, git log), `cc-sweep-20261026/nativetask`, the sweep notes and run drivers. The tag appears only as a default argument and in reports. The run drivers pin a *build identity* (`traps/run_trap.py` BUILD `19b917a8ef47...`, a sha256 over the installed package closure), not a recipe or an image digest. The sibling images on this machine (`ai4r:cc-intent-m1-7-*`, `ai4r:cc-v1-baseline`) are builds of `deploy/m1/Dockerfile.app` (target `production`: pinned python 3.12, node 22, uv, frozen lock, wheels built offline). So the opponent was most likely that Dockerfile at an October 26 commit; the exact commit is not recorded.

Closest portable equivalent (needs network for base images, `uv sync` and `npm ci`, and several GB of RAM and disk; it was **not run** while preparing this folder):

```sh
sh scripts/ai4r-bench build-native --yes --out OUT     # docker build -f deploy/m1/Dockerfile.app --target production -t ai4r:ccbench-native .
```

It writes `OUT/native-image.json` (tag, image id, repo digests, git commit). Then run with `--image ai4r:ccbench-native`. This is plain JiuwenSwarm from this checkout; the native arm uses `agent.work.normal` with no capsules. Without `--yes` the command is only printed. To skip the build, `--image ai4r:cc-v1-baseline` (id `sha256:f4108a225c6c...`) is already present. Results on a rebuilt or substituted image are not the same experiment as the sweep's native arm.

The worker runs `python -m benchmarks.harbor_suite.native_value` with `PYTHONPATH=/runtime:/opt/ai4r`, where `/runtime` is the mounted `native-runtime-en/` overlay.

Automatic collection runs after worker/broker execution, including failures.
The standalone collection command recovers partial artifacts without Docker or
model work. Recollection moves previous copied artifacts into `collections/prior-*`
and copies a fresh snapshot, preserving history without stale project files.
Collection skips output symlinks/junctions rather than reading their targets.
No oracle code or measurement is run by this driver.

## Offline tests

Every test mocks process launch and the real scheduler entry point and uses a temp directory.

```sh
sh scripts/ai4r-bench selftest nativetask
```
