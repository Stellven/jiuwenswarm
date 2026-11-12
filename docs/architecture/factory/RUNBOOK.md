# Satay factory runbook

The factory is one native JiuwenSwarm/Codex agent using six CCs. The host enforces grants, durable state and job lifecycle; the deterministic Manager admits the image and ingests lab evidence. Native CCs are trusted-local code. See [AMENDMENT.md](AMENDMENT.md), [MIGRATION.md](MIGRATION.md) and [LINEAGE.md](LINEAGE.md).

## Setup and pins

Run from `/home/muk/projects/jiuwenswarm`, branch `ai4r/iterative-cc-factory`. Intake records Python 3.12.16, openjiuwen 0.1.18, CUDA 12.6.68, JetPack 6.2.3+b81, Docker 29.1.3, arm64 Jetson Orin Nano, 7,607 MiB RAM, and 13 GiB free at intake. Those are historical observations, not current resource guarantees. Source pins are in [intake.json](../../../artifacts/factory/intake.json); feature HEAD is recorded in the completion report and each bundle's `export.json`.

For a fresh Linux/aarch64 environment (do not recreate an existing working `.venv`):

```sh
cd /home/muk/projects/jiuwenswarm
uv venv .venv --python 3.12.16
uv pip install -p .venv/bin/python -e '.[codex]' rfc8785 psutil pyyaml jsonschema pytest pytest-asyncio pytest-cov 'openai-codex-cli-bin==0.163.0'
.venv/bin/python --version
.venv/bin/python -c 'from importlib.metadata import version; print(version("openjiuwen")); print(version("openai-codex-cli-bin"))'
```

The project pins openjiuwen to `9e3390195a9ea15235b2b5f7412cb2aa440622cc` in `pyproject.toml`. If that Git dependency is unreachable, use an existing approved installation of that exact dependency, as on the intake host. Do not install pywin32 on Linux. Pin Codex CLI **0.163.0** explicitly: resolving the extra alone produced 0.167.2, rejected by this transport. The command pins the tested transport and Python; it is not a complete frozen transitive lockfile.

## Operator prerequisites

Before any new live run, check resources and existing work:

```sh
export FACTORY_HOME="$HOME/.jiuwenswarm-factory"
export CUDA_HOME=/usr/local/cuda
export PATH="$CUDA_HOME/bin:$PATH"
export JOBQ_DIR=/home/muk/projects/siminfeng/lab/jobq
df -h "$FACTORY_HOME"
free -h
nvcc --version
docker image inspect campaign/llamacpp:jetson-up1108-om11 --format '{{.Id}} {{.Architecture}}'
/home/muk/projects/siminfeng/bin/jobq --help
pgrep -af 'jobq.*worker'
```

Require **at least 8 GiB free** on the build/artifact filesystem before a build, and working memory/swap headroom for the operator-approved recipe. The demo model is 22,360,456,160 bytes, larger than RAM; mmap/offload settings and the existing host memory policy are prerequisites. A free-RAM number alone cannot establish readiness. Preserve existing images, models, credentials and queued campaign work.

A durable jobq worker must serve the **same shared queue** used by the factory. Factory GPU/build jobs wait behind campaign jobs; use the existing worker and resource serialization. If no worker exists, the operator starts one in its managed service/terminal with the same environment:

```sh
JOBQ_DIR=/home/muk/projects/siminfeng/lab/jobq /home/muk/projects/siminfeng/bin/jobq worker
```

The worker needs `.venv` Python/module access, Docker permission, `/usr/local/cuda/bin` on PATH, the pinned siminfeng engine/recipe, and access to owned source, model and prompt paths. Do not start a second competing worker to bypass a busy queue. Tests deliberately use private queues and fixture workers; that is not the live configuration.

The reused recipe is `/home/muk/projects/siminfeng/builds/llamacpp-jetson/Dockerfile`; the engine is `/home/muk/projects/siminfeng/cc/build_engine/build_engine.py`. The engine reference pin is `682c6377da20d9229ef1fdb705f63a7a751d14cb`; intake records 154 dirty engine files, so the build's engine/recipe hashes and preparation receipt matter. Model and prompt paths are fixed in the contract/lab runner. The controller, worker, Manager and runner remain outside the tested image. Image delivery is same-host only.

## Authentication and owned checkout

Copy the existing approved login without printing its contents:

```sh
mkdir -p "$FACTORY_HOME/agent-data/subscription/codex-home" "$FACTORY_HOME/agent-workspace"
cp -n "$HOME/.codex/auth.json" "$FACTORY_HOME/agent-data/subscription/codex-home/auth.json"
chmod 600 "$FACTORY_HOME/agent-data/subscription/codex-home/auth.json"
.venv/bin/python -m jiuwenswarm.factory.cli auth-status
```

If the profile needs a fresh sign-in, use `.venv/bin/python -m jiuwenswarm.factory.cli login` and the displayed sign-in URL. Never export auth.json or print tokens. Do not replace an existing owned checkout. For a new factory home only:

```sh
export FACTORY_SOURCE_REPO=/absolute/path/to/local/llama.cpp-with-e14b87603
git -C "$FACTORY_SOURCE_REPO" rev-parse --verify 'e14b87603^{commit}'
git clone --local --no-hardlinks "$FACTORY_SOURCE_REPO" "$FACTORY_HOME/agent-workspace/llama.cpp"
git -C "$FACTORY_HOME/agent-workspace/llama.cpp" checkout --detach e14b87603
```

The provided live home already contains integration commit `690e4713a55bae8dd6b40de3ccbdc8d7ea7e05f8`; leave it intact.

## Freeze reference, once

The checked-in `qwen36-greedy-v1` is already frozen. **Do not run freeze-reference against it again.** For an operator-created, unfrozen versioned contract with the required reference image/build receipt, the exact command is:

```sh
.venv/bin/python -m jiuwenswarm.factory.manager freeze-reference --contract NEW_CONTRACT_ID --image campaign/llamacpp:jetson-up1108-om11
```

This command submits real reference inference and modifies that new contract. Only the operator freezes a reference. A scored comparison never edits its contract; changed argv/checks require a new version/comparable run set. The v1 pre-freeze amendment records `-lv 4` and the candidate-only xfill check. Its reference stdout hash is `7a154179236463bc4c0628b2b24765bdebb6b51810885773b22359d7f2b608a8`.

## Native task commands

These are procedures for a separately authorized future run, not commands executed during F08. `jiuwenswarm factory` dispatches to the same CLI as `python -m jiuwenswarm.factory.cli` and `jiuwenswarm-factory`. Use the root command below with `.venv/bin` on PATH:

```sh
export PATH="$PWD/.venv/bin:$PATH"
TASK=$(jiuwenswarm factory init jiuwenswarm/factory/tasks/demo-qwen36.json)
jiuwenswarm factory run "$TASK" --grant process.exec --grant workspace.read --grant workspace.write --grant gpu.use
jiuwenswarm factory status "$TASK" --json
jiuwenswarm factory show "$TASK"
jiuwenswarm factory show "$TASK" "$TASK:decision:1"
# After controller restart, using the same task ID and explicit grants:
jiuwenswarm factory resume "$TASK" --grant process.exec --grant workspace.read --grant workspace.write --grant gpu.use
# Record cancellation intent, then inspect status until termination is observed:
jiuwenswarm factory cancel "$TASK"
jiuwenswarm factory status "$TASK" --json
# Destination must be new and outside FACTORY_HOME:
jiuwenswarm factory export "$TASK" --out "artifacts/factory/evidence/$TASK"
.venv/bin/python -m jiuwenswarm.factory.export --verify "artifacts/factory/evidence/$TASK"
```

Allowed effects are the intersection of task grants and CLI grants (default none). The task's source path is relative to the configured owned workspace; there is no CLI `--workspace` flag. `init` starts no jobs/model. `run` and `resume` can. Resume reconciles existing attempts, preserves budgets, and refuses uncertain-delivery/interrupted agent threads rather than replaying them. A cancelled request is not proof of cleanup. A terminal accept is contract-scoped, not a general quality claim.

For read-only handoff review, use the exported `records/*.json`, `session.jsonl`, `INDEX.md` and `--verify`. Normal status/show open the controller/store and may initialize schema; F08's exporter uses SQLite `mode=ro`, performs no reconciliation and writes only its destination. It will not overwrite bundles. Copy artifacts above 50 MiB by a separately authorized transport; they are listed in `omissions.json`. `artifacts.json` maps original hashes to sanitized copies. `MANIFEST.json` hashes every included file except itself. Docker inspection failure is retained with build-record identity provenance; it does not attest a current daemon image.

## Troubleshooting from observed failures

| Symptom | Action and evidence |
|---|---|
| nvcc missing during preparation | Put `/usr/local/cuda/bin` on the worker PATH, set CUDA_HOME, inspect `:prep`; changing the submitting shell does not repair an already-running worker environment. |
| Job remains queued in a private queue | Use shared `JOBQ_DIR=/home/muk/projects/siminfeng/lab/jobq` and its existing worker. Earlier private default had no worker/host exclusivity; current Jobs default is shared. Do not bypass campaign work. |
| Opaque inspector `INVALID_INPUT` | Attempt 1 had three failed inspector calls and ended `report_inconclusive`, despite build success. Operator fix is observation `ea7c11f954974b1cb63ff5170e593266`; inspect structured errors and declared inputs. It was a tool defect, not a model rejection. |
| `CONFIG_REJECTED ... invalid LLAMA_EXPERT_PREGATE_K=48 (range 1..32)` | Retain failure/cost, query evidence, repair only K to 8, and reinspect. Attempt 2 demonstrates this; do not silently repair task inputs in the host. |
| Duplicate effective-config lines | Read the full stderr and use final effective values from the selected binary, not the first/default declaration. The inspector handles repeated lines; compare the corrected requested config. |
| stdout matches but engagement is incomplete | `-lv 4` is required for engagement log lines. Do not amend an already-scored contract; v1 records its operator amendment before freeze. xfill is candidate-only because patch 09 is absent from reference. |
| Admission input rejection | Provide image object with exactly `tag` and immutable `id`, plus the successful `build_attempt_id`; inspect `cc_describe` rather than treating a failed receipt as admission. Attempt 2 repaired one input rejection. |
| Docker socket denied during export | Inspect `image-identity.json`: identity falls back to build record; current image labels cannot be reverified. No privilege escalation or image run is required to export. |
| Disk pressure | [PRUNED.md](../../../artifacts/factory/PRUNED.md) identifies removed build staging and the attempt-1 archive. Keep build records/logs; never infer a missing archive was exported. |
| Old M1 keys or `research` command | Remove legacy configuration per MIGRATION.md. Guard exits 2 with explanation. Do not restore removed modules. |

No factory web UI is required. If a local frontend is used, `FRONTEND_PORT=5175` is mandatory.
