# AI4R lineage and removal review (F07 / T07 first pass)

This is a substantial AI4Research runtime redesign using CC-v2. The old M1 control model does not remain. Common JiuwenSwarm services and Codex integration survive; removed compiler/pipeline/RSI machinery is not a compatible live-task backend. The feature amendment is [AMENDMENT.md](AMENDMENT.md); operational mapping and rollback are in [MIGRATION.md](MIGRATION.md).

## Evidence limits and exact commands

The checkout is a blob-filtered partial clone. Commit/tree objects exist, but the old blobs needed for diff hunks and line statistics are absent. Initial ordinary diff commands triggered Git's implicit lazy-fetch attempts, which failed with `Could not resolve host: github.com`; no objects were fetched. Subsequent history commands use an isolated bare object view at `/tmp/f07-history`, with this checkout's object directory as an alternate, copied pinned refs/HEAD, no remote and `diff.renames=false`. This prevents implicit network access and yields tree-only inventories. No source checkout, refs or evidence were rewritten. Rename detection is disabled explicitly because similarity detection would require missing old blobs. The count below is a tree deletion count, not a claim that a default similarity-enabled diff completed.

Requested commands and outputs in that offline view (exit codes included):

```text
$ git rev-parse origin/AI4Research-Main origin/ai4r_ccv2 HEAD
141c1c401138f916af0a41aca791adf226d814c7
2889a1d6342e9baa7721648eca196bbce79a31d4
2889a1d6342e9baa7721648eca196bbce79a31d4
```

Exit: 0.

```text
$ git merge-base --is-ancestor origin/AI4Research-Main HEAD; echo $?
0
```

Exit: 0.

```text
$ git log --oneline origin/AI4Research-Main..origin/ai4r_ccv2
2889a1d6 Provenance: reference-runner branch is pushed
68d8dd30 Provenance: note the matching unpushed reference-runner commit
a838b970 Docs: make the branch purpose clear; remove stale M1 docs
62f5ba46 Review fixes: duplicate ids, ownership, cleanup on exit, opt-in built CCs; rerun live sessions
69d4466a Restrict cc_artifact to the operator workspace
85e53558 Live agent evidence, docs, construction demo, image pull policy
0f3d118a Fix CC MCP stdin inheritance and tool signatures; add live-agent prompts
e2f037ce Add CC agent MCP catalog, Codex agent mode, demo CCs and live driver
b686bc11 Vendor CC v2 runner as jiuwenswarm.ccv2 with its 81 tests; remove remaining M1 profile hooks
1b724e19 Strip M1 research machinery; keep base JiuwenSwarm and Codex integration
```

Exit: 0.

```text
$ git diff --shortstat origin/AI4Research-Main origin/ai4r_ccv2
fatal: unable to read d57f42585dcfb93deed6daf0df9645985b1514a3
```

Exit: 128.

```text
$ git diff --dirstat=files,3 origin/AI4Research-Main origin/ai4r_ccv2
   3.3% benchmarks/ccbench/runs-20261028/b-native-fixtures/fixtures/
   8.6% benchmarks/ccbench/
   3.1% benchmarks/reports/2026-10-26-hybrid-router/external/data/originals/
   4.1% benchmarks/
   4.3% deploy/m1/
   4.5% docs/architecture/design-package/reference/examples/
   3.2% docs/architecture/experiments/m1-contract-review-2026-10-08/compact/reference/examples/
   3.2% docs/architecture/experiments/m1-contract-review-2026-10-08/full/reference/examples/
   3.3% docs/architecture/experiments/m1-contract-review-2026-10-08/full/
   4.4% docs/architecture/experiments/m1-full-baseline/
   6.6% docs/architecture/experiments/
   3.1% docs/architecture/
   4.4% jiuwenswarm/research/capsule_extensions/
   3.0% jiuwenswarm/research/resources/
   6.2% jiuwenswarm/research/
   3.6% jiuwenswarm/research_contracts/schemas/
   6.1% jiuwenswarm/
   3.2% tests/ccv2/
   5.7% tests/unit_tests/research/
   6.4% tests/unit_tests/
   4.2% tests/
```

Exit: 0.

The ancestry command also ran against the actual working checkout and exited 0. HEAD remains the donor; no commits were made. `--shortstat` cannot be supplied honestly from absent blobs. All requested startup/config old hunks are also blocked (individual attempts fail on the missing old blob); the table below distinguishes verified current content from unverified change attribution. This first pass does **not** claim hunk-review completion.

## Removed and added inventory

Counts come from `git diff --name-status --diff-filter=D origin/AI4Research-Main origin/ai4r_ccv2` and the corresponding `--diff-filter=A`, using the offline tree-only configuration above. Group by top-level directory, expanding `jiuwenswarm/` into packages; no duplicates. Historical paths are source names, not compatibility promises.

| Directory/package | Removed files | Added files | Reviewed inventory meaning |
|---|---:|---:|---|
| `artifacts/` | 0 | 21 | CC-v2 agent evidence added |
| `benchmarks/` | 645 | 0 | ccbench/harbor and benchmark runs/reports removed |
| `demo/` | 0 | 19 | CCs, requests, driver and prompts added |
| `deploy/` | 146 | 0 | M1 deployment removed |
| `docs/` | 1037 | 3 | M1 design/research/experiment docs removed; CC-v2 docs added |
| `jiuwenswarm/capsule_runtime/` | 11 | 0 | Old capsule runtime removed |
| `jiuwenswarm/ccv2/` | 0 | 12 | CC-v2 runner, agent MCP and schemas added |
| `jiuwenswarm/channels/` | 1 | 0 | Research CLI removed |
| `jiuwenswarm/gateway/` | 1 | 0 | Research HTTP bridge removed |
| `jiuwenswarm/research/` | 457 | 0 | Compiler, capsule pipeline, admission/execution and research resources removed |
| `jiuwenswarm/research_assets/` | 16 | 0 | M1 research assets removed |
| `jiuwenswarm/research_contracts/` | 133 | 0 | M1 contracts/schemas removed |
| `jiuwenswarm/research_records/` | 7 | 0 | Historical-record implementation removed; evidence is not live-task state |
| `jiuwenswarm/research_router/` | 11 | 0 | M1 research routing removed |
| `jiuwenswarm/research_rsi/` | 79 | 0 | RSI controller/capsule loop removed |
| `jiuwenswarm/research_sidecar/` | 32 | 0 | M1 sidecar removed |
| `jiuwenswarm/server/` | 11 | 0 | Server RSI handlers/brokers removed |
| `releases/` | 2 | 0 | M1 releases removed |
| `scripts/` | 12 | 0 | M1 scripts removed |
| `tests/` | 545 | 109 | M1 tests/fixtures removed; CC-v2 tests and Codex agent-mode tests added |
| **Total** | **3146** | **164** | Tree inventory |

```text
$ git diff --name-status --diff-filter=D origin/AI4Research-Main origin/ai4r_ccv2 | wc -l
3146
```

## Startup/config file review

Every row is tree-status `M` between the pinned revisions. **Old hunk unavailable in every row**: attribution of the exact removed/added lines remains blocked. The descriptions below are verified by reading the current donor file; they describe retained behavior, not an invented diff-hunk finding. Obtain the old blobs offline before completing the requested hunk review.

| Modified file | Current donor behavior / review implication |
|---|---|
| `jiuwenswarm/start_services.py` | Early dotenv then common services/instance dispatch; no Python M1 launch hooks remain. |
| `jiuwenswarm/dotenv_early.py` | Early dotenv/name parsing and desktop environment preservation; no M1 environment-key reads. |
| `jiuwenswarm/gateway/app_gateway.py` | Common gateway entry point survives; no removed research imports. |
| `jiuwenswarm/gateway/channel_manager/web/web_connect.py` | Common web connection path survives; deleted `research_http.py` no longer supplies a bridge. |
| `jiuwenswarm/init_workspace.py` | Workspace initialization survives; no M1 key reads. |
| `jiuwenswarm/server/app_agentserver.py` | Agent-server entry point survives; no removed research imports. |
| `jiuwenswarm/server/agent_ws_server.py` | Common agent websocket dispatch survives; a comment still mentions M1 capability gaps. |
| `jiuwenswarm/server/front/router.py` | Common session/project/config/history/control routing survives; server RSI package is deleted. |
| `jiuwenswarm/channels/cli/main.py` | Root CLI imports chat parser/run_chat; deleted research CLI is no longer dispatched. |
| `jiuwenswarm/channels/web/app_web.py` | Frontend survives, with `FRONTEND_PORT` default `5173`; handoff local hosting rule is `5175`. |
| `jiuwenswarm/server/runtime/codex_subscription/service.py` | Agent-mode workspace and instructions are opt-in; governed-call API survives, including historical research wording. |
| `jiuwenswarm/server/runtime/codex_subscription/transport.py` | Codex 0.163.0 transport has opt-in workspace-write shell/patch/MCP configuration; text-only mode remains default. |
| `pyproject.toml` | Common dependencies and Codex extra survive; stale M1 dependency comment remains, not a live control model. |
| `pytest.ini` | Includes Docker marker, asyncio auto mode and warning filters; these do not establish a live image result. |
| `tests/conftest.py` | Generic workspace/config/environment fixtures survive; no M1 key reads. |

## Legacy-key grep before edits

```text
$ rg -n 'JIUWENSWARM_M1_|AI4R_PILOT_BUDGET_DIRECTORY' jiuwenswarm
jiuwenswarm/channels/tui/frontend/src/core/researchClient.ts:51:    if (process.env.JIUWENSWARM_M1_PROFILE !== "1") return null;
jiuwenswarm/channels/tui/frontend/src/core/researchClient.ts:52:    const origin = process.env.JIUWENSWARM_M1_ORIGIN;
jiuwenswarm/channels/tui/frontend/src/core/researchClient.ts:53:    const tokenPath = process.env.JIUWENSWARM_M1_TOKEN_FILE;
jiuwenswarm/channels/tui/frontend/src/core/researchClient.ts:54:    const defaultsPath = process.env.JIUWENSWARM_M1_CLIENT_CONFIG;
jiuwenswarm/channels/tui/frontend/src/core/commands/registry.ts:126:    ...(process.env.JIUWENSWARM_M1_PROFILE === "1" ? [createResearchCommand()] : []),
```

Exit 0. Therefore “no remaining code reads these keys” is false: residual TUI code reads them. No Python consumer remained before this guard was added. TUI removal is not part of these minimal Python call-site edits. The guard rejects legacy values rather than interpreting them or rebuilding M1.

## Verification

- **B1:** `.venv/bin/python -m pytest tests/factory/test_migration.py --no-cov -q -p no:cacheprovider` — **12 passed**; output `/tmp/f07-b1.txt`.
- **B2 baseline, before edits:** exact acceptance command saved to `/tmp/f07-baseline.txt`, exit **4** during collection: `OSError: [Errno 30] Read-only file system: '/home/muk/.jiuwenswarm'` from common-utils logger initialization. No tests ran, so no Codex pass count can be asserted from that run.
- **B2 after edits:** exact acceptance command saved to `/tmp/f07-b2-after.txt`, same collection error, exit **4**. The intake's **93 CC-v2 passes / 10 host failures** remains historical host baseline evidence, not a result reproduced in this sandbox.
- **Supplemental writable-data baseline:** same combined command with `JIUWENSWARM_DATA_DIR=/tmp/f07-runtime`, output `/tmp/f07-baseline-writable.txt`, collected 149 tests but hung at the first MCP test (`test_artifact_registration_is_limited_to_the_workspace`); interrupted, exit **130**. This run began before edits. No Docker command or live-agent/image run was performed.
- **Supplemental Codex comparison:** exported donor `2889a1d6` with `git archive` to `/tmp/f07-donor` (no stash or checkout edits), ran the three Codex files with that tree on `PYTHONPATH` and a writable data root; compared with the same three files after edits. Both reached `test_real_facade_persists_streamed_reply_once` after **35 passed**, then timed out at 120s, exit **124**. Outputs `/tmp/f07-codex-baseline.txt` and `/tmp/f07-codex-after.txt`. These are incomplete runs, not a passing Codex suite.
- **Supplemental Codex isolation:** with `JIUWENSWARM_DATA_DIR=/tmp/f07-runtime`, the three Codex files plus `-k 'not test_real_facade_persists_streamed_reply_once'` returned **45 passed, 1 deselected, 6 subtests passed**, exit **0**, in 13.33s. Output `/tmp/f07-codex-selected.txt`. This narrower run does not replace B2 or establish that the stalled test passes.
- **B3:** `git merge-base --is-ancestor origin/AI4Research-Main HEAD` — **0**, before and after edits; HEAD unchanged.
- **B4:** offline tree-only removal count **3146**, exactly equal to the inventory sum; default similarity-enabled command is blocked by unavailable old blobs, so its acceptance result remains unverified.
- `git diff --check` passes. No commits, pushes, merges or deployments.

Startup coverage: subprocess tests cover the root CLI `research` rejection, Codex `--help` with legacy environment, start-services `--help` with legacy environment, and root CLI `--help` with the pilot-budget key. All exit 2 with stderr migration guidance before services/profile creation. Direct TUI launch and keys introduced only by later dotenv loading are outside this early Python environment guard; no actual services were started.
