# AI4R lineage and removal review (F08 / T07 completion)

This is a substantial AI4Research runtime redesign using CC-v2. The old M1 control model does not remain. Common JiuwenSwarm services and Codex integration survive; removed compiler/pipeline/RSI machinery is not a compatible live-task backend. The feature amendment is [AMENDMENT.md](AMENDMENT.md); operational mapping and rollback are in [MIGRATION.md](MIGRATION.md).

## Completed local history review (F08)

Old and new blobs are local. These commands ran successfully in the working checkout on 2026-11-12; no lazy-fetch workaround is needed. HEAD is the committed feature snapshot below; the F08 working-tree additions are not included in its delta.

```text
$ git rev-parse origin/AI4Research-Main origin/ai4r_ccv2 HEAD
141c1c401138f916af0a41aca791adf226d814c7
2889a1d6342e9baa7721648eca196bbce79a31d4
e2bef4a19e9ff3587bc3e5646eb06b1a9b42dd09
```

Exit: 0.

```text
$ git diff --shortstat origin/AI4Research-Main origin/ai4r_ccv2
 3331 files changed, 15437 insertions(+), 510852 deletions(-)
```

Exit: 0.

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

```text
$ git diff --stat origin/ai4r_ccv2 HEAD
 AGENTS.md                                          |    3 +
 artifacts/factory/intake.json                      |   98 ++
 docs/architecture/README.md                        |    3 +
 docs/architecture/ccv2/README.md                   |   13 +-
 docs/architecture/factory/AMENDMENT.md             |   19 +
 docs/architecture/factory/CONTROLLER.md            |   77 +
 docs/architecture/factory/LINEAGE.md               |  159 ++
 docs/architecture/factory/MIGRATION.md             |   32 +
 jiuwenswarm/channels/cli/main.py                   |    7 +
 jiuwenswarm/codex_start.py                         |    3 +
 jiuwenswarm/factory/AGENT.md                       |   33 +
 jiuwenswarm/factory/__init__.py                    |    1 +
 jiuwenswarm/factory/api.py                         |  182 +++
 jiuwenswarm/factory/build_job.py                   |  172 +++
 jiuwenswarm/factory/builder.py                     |  143 ++
 jiuwenswarm/factory/ccs/builder/cc.yaml            |   84 +
 jiuwenswarm/factory/ccs/builder/run.py             |   28 +
 .../ccs/engine_component/09-thread-names.patch     |   23 +
 jiuwenswarm/factory/ccs/engine_component/README.md |   23 +
 jiuwenswarm/factory/ccs/engine_component/cc.yaml   |   12 +
 .../combined-01-02-03-04-05-06-07-08.patch         | 1609 ++++++++++++++++++++
 .../factory/ccs/engine_component/component.yaml    |   46 +
 jiuwenswarm/factory/ccs/engine_inspector/cc.yaml   |   81 +
 jiuwenswarm/factory/ccs/engine_inspector/run.py    |   28 +
 jiuwenswarm/factory/ccs/evidence/cc.yaml           |   62 +
 jiuwenswarm/factory/ccs/evidence/run.py            |   28 +
 .../factory/ccs/integration_skill/INTEGRATE.md     |   41 +
 .../factory/ccs/integration_skill/PREFLIGHT.md     |   42 +
 .../factory/ccs/integration_skill/REPAIR.md        |   33 +
 jiuwenswarm/factory/ccs/integration_skill/cc.yaml  |   10 +
 jiuwenswarm/factory/ccs/lab_client/cc.yaml         |   90 ++
 jiuwenswarm/factory/ccs/lab_client/run.py          |   25 +
 jiuwenswarm/factory/cli.py                         |  101 ++
 jiuwenswarm/factory/contract.py                    |   98 ++
 jiuwenswarm/factory/contracts/.gitignore           |    1 +
 .../factory/contracts/qwen36-greedy-v1.json        |   78 +
 jiuwenswarm/factory/controller.py                  |  342 +++++
 jiuwenswarm/factory/inspector.py                   |  263 ++++
 jiuwenswarm/factory/jobs.py                        |  229 +++
 jiuwenswarm/factory/lab_runner.py                  |  209 +++
 jiuwenswarm/factory/manager.py                     |  297 ++++
 jiuwenswarm/factory/migration.py                   |   36 +
 jiuwenswarm/factory/schemas/component.schema.json  |  182 +++
 jiuwenswarm/factory/schemas/task.schema.json       |   34 +
 jiuwenswarm/factory/store.py                       |  505 ++++++
 .../factory/tasks/demo-qwen36-attempt2.json        |   51 +
 jiuwenswarm/factory/tasks/demo-qwen36.json         |   48 +
 .../server/runtime/codex_subscription/service.py   |   32 +-
 jiuwenswarm/start_services.py                      |    3 +
 pyproject.toml                                     |    6 +
 tests/factory/conftest.py                          |   73 +
 tests/factory/fixtures/lab/README.txt              |    6 +
 tests/factory/fixtures/lab/cmd.txt                 |    3 +
 tests/factory/fixtures/lab/invalid-stderr.txt      |    1 +
 tests/factory/fixtures/lab/result.json             |   33 +
 tests/factory/fixtures/lab/stderr.txt              |  356 +++++
 tests/factory/fixtures/lab/stdout.txt              |   19 +
 tests/factory/fixtures/lab/telemetry.jsonl         |    1 +
 tests/factory/fixtures/lab/threads.summary.json    |    1 +
 tests/factory/fixtures/lab/tripped-result.json     |    7 +
 tests/factory/fixtures/lab/tripped-watchdog.jsonl  |    4 +
 tests/factory/fixtures/lab/watchdog.jsonl          |    1 +
 tests/factory/test_api.py                          |  123 ++
 tests/factory/test_builder.py                      |  196 +++
 tests/factory/test_capsules.py                     |  222 +++
 tests/factory/test_controller.py                   |  284 ++++
 tests/factory/test_jobs.py                         |  138 ++
 tests/factory/test_lab.py                          |  404 +++++
 tests/factory/test_migration.py                    |   54 +
 tests/factory/test_store.py                        |  177 +++
 70 files changed, 7826 insertions(+), 2 deletions(-)
```

Exit: 0.

`git merge-base --is-ancestor origin/AI4Research-Main HEAD` — exit **0**.

`git merge-base --is-ancestor origin/ai4r_ccv2 HEAD` — exit **0**.

The feature is descended from both pinned branches. This establishes ancestry, not publication or a shared-branch merge.

## Removed and added inventory

Counts come from `git diff --no-renames --name-status --diff-filter=D origin/AI4Research-Main origin/ai4r_ccv2` and the corresponding `--no-renames --diff-filter=A`, at the pinned revisions (rename detection disabled for this inventory only). Group by top-level directory, expanding `jiuwenswarm/` into packages; no duplicates. Historical paths are source names, not compatibility promises.

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
$ git diff --no-renames --name-status --diff-filter=D origin/AI4Research-Main origin/ai4r_ccv2 | wc -l
3146
```

## Startup/config file review

Read the actual hunks with `git diff origin/AI4Research-Main origin/ai4r_ccv2 -- <file>` for every row below (all exit 0). These describe the donor delta, distinct from the feature delta above.

| Modified file | Hunk-reviewed change |
|---|---|
| `jiuwenswarm/start_services.py` | Removes M1 profile import, alternate data root and bootstrap dispatch; makes early dotenv, instance imports and common data root unconditional. |
| `jiuwenswarm/dotenv_early.py` | Removes research.native_profile restore_protected_startup calls around dotenv; preserves desktop environment restoration. |
| `jiuwenswarm/gateway/app_gateway.py` | Removes native research ports/attachment, channel filtering and M1 route restriction; restores common logging, heartbeat, cron, optional A2A and model warmup paths. |
| `jiuwenswarm/gateway/channel_manager/web/web_connect.py` | Deletes research-profile message interception and ResearchError response branch; common websocket routing remains. |
| `jiuwenswarm/init_workspace.py` | Deletes M1-profile delegation to research.initialize; common workspace initialization remains. |
| `jiuwenswarm/server/app_agentserver.py` | Removes native profile/logging/refusal/trajectory/port hooks; common logging and teammate bootstrap become unconditional; Codex-only readiness early return remains. |
| `jiuwenswarm/server/agent_ws_server.py` | Deletes RSI handler/provider fields, injection method, rsi.* dispatch and handler/context/harness resolution implementation. |
| `jiuwenswarm/server/front/router.py` | Deletes M1 local chat/session interception; Codex auth/model routing now depends only on codex_subscription SDK selection. |
| `jiuwenswarm/channels/cli/main.py` | Deletes research subcommand dispatch and M1 native TUI selection; ordinary chat CLI remains. |
| `jiuwenswarm/channels/web/app_web.py` | Removes research auth proxy route and M1 origin/Host special cases; only /api is proxied as API and upstream Host is used. |
| `jiuwenswarm/server/runtime/codex_subscription/service.py` | Removes pilot budget, M1 account root and device-code branch; adds opt-in CC agent instructions/workspace and tool events while retaining default text-only validation. |
| `jiuwenswarm/server/runtime/codex_subscription/transport.py` | Adds opt-in workspace-write shell/patch/MCP profile, marker-based config refresh and agent_mode_enabled; normal restricted profile remains default. |
| `pyproject.toml` | Drops research_sidecar package exclusion and four research resource package-data globs; dependency declarations are unchanged by this donor delta. |
| `pytest.ini` | Registers the docker marker for daemon-dependent tests. |
| `tests/conftest.py` | Removes automatic tests.benchmark_case_assets plugin loading. |

The frontend default remains 5173 in code; local hosting requires `FRONTEND_PORT=5175`. Feature commits subsequently add early legacy-configuration rejection and native factory dispatch; see [MIGRATION.md](MIGRATION.md) and [RUNBOOK.md](RUNBOOK.md).

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

## Historical F07 verification (unchanged results)

- **B1:** `.venv/bin/python -m pytest tests/factory/test_migration.py --no-cov -q -p no:cacheprovider` — **12 passed**; output `/tmp/f07-b1.txt`.
- **B2 baseline, before edits:** exact acceptance command saved to `/tmp/f07-baseline.txt`, exit **4** during collection: `OSError: [Errno 30] Read-only file system: '/home/muk/.jiuwenswarm'` from common-utils logger initialization. No tests ran, so no Codex pass count can be asserted from that run.
- **B2 after edits:** exact acceptance command saved to `/tmp/f07-b2-after.txt`, same collection error, exit **4**. The intake's **93 CC-v2 passes / 10 host failures** remains historical host baseline evidence, not a result reproduced in this sandbox.
- **Supplemental writable-data baseline:** same combined command with `JIUWENSWARM_DATA_DIR=/tmp/f07-runtime`, output `/tmp/f07-baseline-writable.txt`, collected 149 tests but hung at the first MCP test (`test_artifact_registration_is_limited_to_the_workspace`); interrupted, exit **130**. This run began before edits. No Docker command or live-agent/image run was performed.
- **Supplemental Codex comparison:** exported donor `2889a1d6` with `git archive` to `/tmp/f07-donor` (no stash or checkout edits), ran the three Codex files with that tree on `PYTHONPATH` and a writable data root; compared with the same three files after edits. Both reached `test_real_facade_persists_streamed_reply_once` after **35 passed**, then timed out at 120s, exit **124**. Outputs `/tmp/f07-codex-baseline.txt` and `/tmp/f07-codex-after.txt`. These are incomplete runs, not a passing Codex suite.
- **Supplemental Codex isolation:** with `JIUWENSWARM_DATA_DIR=/tmp/f07-runtime`, the three Codex files plus `-k 'not test_real_facade_persists_streamed_reply_once'` returned **45 passed, 1 deselected, 6 subtests passed**, exit **0**, in 13.33s. Output `/tmp/f07-codex-selected.txt`. This narrower run does not replace B2 or establish that the stalled test passes.
- **B3:** `git merge-base --is-ancestor origin/AI4Research-Main HEAD` — **0**, before and after edits; HEAD unchanged.
- **B4:** offline tree-only removal count **3146**, exactly equal to the inventory sum; F08 default similarity-enabled command completes: **3145** deleted paths, plus one 100% rename from `benchmarks/ccbench/nativetask/native-runtime-en/benchmarks/__init__.py` to `tests/ccv2/__init__.py`. The explicit `--no-renames` command yields **3146**, matching this tree inventory.
- `git diff --check` passes. No commits, pushes, merges or deployments.

Startup coverage: subprocess tests cover the root CLI `research` rejection, Codex `--help` with legacy environment, start-services `--help` with legacy environment, and root CLI `--help` with the pilot-budget key. All exit 2 with stderr migration guidance before services/profile creation. Direct TUI launch and keys introduced only by later dotenv loading are outside this early Python environment guard; no actual services were started.

## F08 verification

The exact shortstat, dirstat, feature stat and both ancestry checks above complete locally. Startup/config hunks are reviewed. F08 does not rerun the donor suites or reclassify the historical failures. Factory/export validation and live execution evidence are linked in [COMPLETION-REPORT.md](../../../artifacts/factory/COMPLETION-REPORT.md). No shared branch, source checkout, contract or factory database was changed by this review.
