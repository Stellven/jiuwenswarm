# Factory completion report

Reviewed and set by the orchestrator (Claude Opus) on 2026-11-12 after independent re-verification of the live evidence; drafted by Codex F08. This report records implemented code, recorded real execution, offline checks and unproven acceptance cases separately. No shared-branch merge or publication is implied.

cc_demo_ready: true — scoped: real agent → component CC → skill-guided integration and evidence-driven repair (real `CONFIG_REJECTED` K=48 → K=8) → durable Builder → deterministic Manager (same-host admission) → real Qwen3.6-35B inference byte-identical to the frozen reference, all recorded (attempt 2, `factory-d4b71bcc…`). Caveats: no timed ten-minute rehearsal yet (script in DEMO-10MIN.md; the live chain takes ~12 min, so the talk uses the labeled recordings for build/lab segments); attempt 1 needed one operator tool fix (recorded).

ai4r_lineage_and_migration_verified: true — `origin/AI4Research-Main` (141c1c40, unchanged on the remote at 2026-11-12T01:59Z) is an ancestor of the feature branch; donor removals/startup changes reviewed in LINEAGE.md; legacy M1 config fails with a migration error through the installed native entrypoint (live receipt); the full factory ran through the branch's native JiuwenSwarm path. This is **not** a merge: AI4Research-Main is unchanged; only `ai4r/iterative-cc-factory` is published.

## Update 2026-11-12: bare-engine evolve (run 4, `factory-bd173c08…`): ACCEPT

The agent started from bare llama.cpp `cf34d311`. It integrated five component CCs in dependency order and A/B-tested each on Qwen3.6-35B-A3B, using the `methodology_ab` CC with two ABBA rounds and an A/A noise floor. Its decisions:
- **kept** expert_fill (1.11×) and expert_pregate (1.13×);
- **held dormant** mmap_advice (0.49×) and router_prefetch (0.62×): switches off, code retained for dependents, checked against `depends_on`;
- **reverted** thread_names (1.01×, not measured as a performance win).

The final image is 785.22 ms/token against bare 903.95, with stdout byte-identical to the frozen reference `7a154179…` for all 9 lab jobs. The run took 175 minutes: 15 turns, 25 decision revisions, 7 builds of about 130 s each, no operator intervention. The agent refused to multiply incremental ratios into a cumulative claim. The bundle is `evidence/factory-bd173c082bf34ae3b8471938c19b8068/` (slim; the full export verified 604 files with a clean secrets scan). The demo script is DEMO-10MIN.md.

Runs 1–3 failed honestly. Each failure was a tool problem, and each fix was a tool change: the grants refusal, `FACTORY_PYTHON`, and `keep_dormant`. Their recordings are kept.

## Implementation and pins

The native path is `jiuwenswarm factory` → controller → CC-v2 tools → scoped evidence API / durable jobq → Builder or Manager → external lab runner → Manager ingestion → versioned agent decision. No AI4R adapter, registry service, M1 intent compiler or old capsule runtime was restored. The feature exception is [AMENDMENT.md](../../docs/architecture/factory/AMENDMENT.md).

Implemented modules under `jiuwenswarm/factory/`: store (SQLite and hash-addressed artifacts), api (task scope and CAS decisions), jobs (durable identity/reconciliation/cancellation), builder/build_job (validated source and pinned preparation), inspector (binary/config/preflight evidence), controller/cli (real JiuwenSwarm agent and budgets), contract, manager, lab_runner, migration, and export. Six packaged capsules: `engine_component` and `integration_skill` are passive materials; `engine_inspector`, `builder`, `lab_client` and `evidence` expose finite calls. Native CCs are trusted-local, not a sandbox boundary.

| Pin | Recorded identity |
|---|---|
| AI4Research-Main target | `141c1c401138f916af0a41aca791adf226d814c7` |
| CC-v2 donor (reference and fetched) | `2889a1d6342e9baa7721648eca196bbce79a31d4` |
| Feature HEAD during F08 | `e2bef4a19e9ff3587bc3e5646eb06b1a9b42dd09` (F08 changes remain uncommitted) |
| siminfeng engine reference/local HEAD | `682c6377da20d9229ef1fdb705f63a7a751d14cb`; intake records 154 dirty files; build records hash actual engine/recipe |
| Intake llama.cpp baseline | `cf34d311332e362198f0a410c466d1e940287d02` in the up1108 checkout |
| Owned component source | pre-integration `e14b87603`; integrated `690e4713a55bae8dd6b40de3ccbdc8d7ea7e05f8` |
| Python / dependency | Python 3.12.16; openjiuwen 0.1.18; project Git pin `9e3390195a9ea15235b2b5f7412cb2aa440622cc` |
| Codex CLI | **0.163.0** manually pinned; extra resolved 0.167.2, which transport rejects |
| Host intake | Satay, aarch64 Orin Nano, JetPack 6.2.3+b81, CUDA 12.6.68, Docker 29.1.3, RAM 7,607 MiB |

Pins and host observations originate in [intake.json](intake.json). Capsule release hashes are in each bundle's `capsule-releases.json`: SHA256 of sorted relative path, NUL, per-file SHA256, LF entries (excluding Python caches). These are **export-time** source identities; historical loaded capsule bytes were not separately attested. Each bundle includes the corresponding capsule files. Owned-checkout `git log -3` and integration-commit diff are bundled under `source/`.

## Reviewer-verified live facts (quoted)

> Attempt 1 task `factory-aeaa9acc88d34a3ab1375154da98c385`: agent integrated patch 09 → commit `690e4713a` in the owned checkout; durable build succeeded (`factory/llamacpp:aeaa9acc-thread-names-1`, `sha256:89ad6ac4…`); three inspector calls failed with opaque `INVALID_INPUT` (tool defect); agent ended `report_inconclusive` at rev 6. Operator intervention recorded as observation `ea7c11f954974b1cb63ff5170e593266` (inspector input/error fix).

> Attempt 2 task `factory-d4b71bcce337406b96f627d469bec092` (operator `read_tasks` grant to attempt 1): 6 decision revisions, 3 turns, ~706 s; real `CONFIG_REJECTED: expert_config: invalid LLAMA_EXPERT_PREGATE_K=48 (range 1..32)` → single-field repair K=8 → build `3216f109…` (124 s, cache_hit true) → image `factory/llamacpp:d4b71bcc-thread-names-1` `sha256:f02f8a93453e…` → Manager admission (one input rejection repaired) → lab run `cabd3a09…`: execution_outcome ok, correctness pass, evidence complete; stdout sha256 `7a154179236463bc4c0628b2b24765bdebb6b51810885773b22359d7f2b608a8` == frozen reference (contract `qwen36-greedy-v1`, reference from `campaign/llamacpp:jetson-up1108-om11`, same as historical J-OM11); all 6 engagement checks true incl. `xfill-*` threads; 745 ms/token (single run; not a benchmark). Terminal decision `accept` rev 6.

> Contract pre-freeze amendment (`-lv 4`; candidate-only xfill check) is recorded in the contract file.

## Live, recorded and fixture evidence

Here “recorded real” means existing live execution evidence, not a new F08 execution. “Live read-only” means inspection/verification of existing bytes during F08.

| Evidence | Kind | Pointer / limits |
|---|---|---|
| Agent attempt 1 | Recorded real agent, build; no accepted lab result | [bundle INDEX](evidence/factory-aeaa9acc88d34a3ab1375154da98c385/INDEX.md), `records/decisions.json`, `records/observations.json`, scrubbed `session.jsonl`; [run1 recording](recording/demo-run1.typescript), [timing](recording/demo-run1.timing) |
| Agent attempt 2 | Recorded real agent, build, Manager and inference | [bundle INDEX](evidence/factory-d4b71bcce337406b96f627d469bec092/INDEX.md); build `3216f10925b74aca8bfc8be140e65b7b`, admission `admission:78856fb9c5c49df9a0550cd1342b810dab29f02dfee36929827780fe1f276aa2`, lab `cabd3a09443f493899c756ab0ce1a671`, evaluation `cabd3a09443f493899c756ab0ce1a671:evaluation`; [run2 recording](recording/demo-run2.typescript), [timing](recording/demo-run2.timing) |
| Operator durable jobs | Recorded real operator; independent of agent acceptance | [operator bundle](evidence/operator-live-jobs-1/INDEX.md), bundled `live-jobs-receipt.jsonl` (included with `--extra-file artifacts/factory/live-jobs-receipt.jsonl`); source [live receipt](live-jobs-receipt.jsonl) may continue to grow |
| Manifest and sanitation checks | Live read-only validation of included bundle bytes | `python -m jiuwenswarm.factory.export --verify DIR`, for all three directories |
| Factory tests | Offline tests; fake tools/queue workers; fixture lab output | `tests/factory/`; fixture evidence is not the accepted candidate run |
| Ten-minute presentation | Scripted walk-through of recorded runs, **not a timed rehearsal** | [DEMO-10MIN.md](../../docs/architecture/factory/DEMO-10MIN.md); long execution recordings are not a completed ten-minute screen recording |

Operator receipt snapshot: `aae86e0c5e304397816140dfbad11749` / `job-d3db0f96f23745c0a1e75a98fcea3a24` was submitted by PID 960501 in 0.24 s, client exited, PID 960805 observed the same running attempt with one named job, and the changed same-key request returned KeyConflict. A new client observed success at t=1794447691.0069273, ~209 s after submission. The first cancel-labelled receipt `c36b4f1bc09b47bcb0e7d2bdd7046b2a` actually failed; it is not evidence of cancellation. Second attempt `c440203a1ca74814ac717f18374f590a` was observed running, then `cancel_requested` → `cancelled`; cleanup was `process_groups_reaped;containers_unverified`. Container cleanup is therefore not fully verified live. F08 did not submit or cancel these jobs.

## Commands and results from F08

```sh
.venv/bin/python -m pytest tests/factory --no-cov -q -p no:cacheprovider
```

**146 passed in 50.68 s**, including nine new exporter test cases. An earlier run returned 137 passed / 9 failed: all failing Builder success cases hit the actual 8 GiB disk precondition (receipt free_bytes=8019177472). After host disk space changed, the same command passed without changing Builder, tests or the disk guard. Output for the successful run: `/tmp/f08-g1-final.txt`. This resource sensitivity remains an operational limitation.

```sh
.venv/bin/python -m jiuwenswarm.factory.export factory-aeaa9acc88d34a3ab1375154da98c385 --out artifacts/factory/evidence/factory-aeaa9acc88d34a3ab1375154da98c385
.venv/bin/python -m jiuwenswarm.factory.export factory-d4b71bcce337406b96f627d469bec092 --out artifacts/factory/evidence/factory-d4b71bcce337406b96f627d469bec092
```

Both commands were run successfully. Final snapshots of all three tasks were then written with the same `export_task` implementation after adding archive identity and label limitations (no Store initialization). The supported root spelling is `jiuwenswarm factory export TASK --out DIR`; `.venv/bin/jiuwenswarm factory export factory-aeaa9acc88d34a3ab1375154da98c385 --out /tmp/f08-root-cli-bundle` also completed successfully. The CLI test verifies export bypasses Store construction.

```sh
.venv/bin/python -m jiuwenswarm.factory.export --verify artifacts/factory/evidence/factory-aeaa9acc88d34a3ab1375154da98c385
.venv/bin/python -m jiuwenswarm.factory.export --verify artifacts/factory/evidence/factory-d4b71bcce337406b96f627d469bec092
.venv/bin/python -m jiuwenswarm.factory.export --verify artifacts/factory/evidence/operator-live-jobs-1
```

Final verification: **52**, **68**, and **60** included files respectively; all hashes verify and secrets scans are clean.

Each bundle has task, ordered decisions, observations, attempts/history, evaluations/uploads/events, hash-addressed artifacts, source identity/diff, build outputs and image provenance. Agent bundles include scrubbed sessions and contract. Operator task has no agent transcript or scored contract; this is explicit. Missing chain links are labelled, not inferred. `MANIFEST.json` maps included paths to SHA256 (except itself); verification also rejects extra files, changed bytes, symlinks and residual token/JWT/key/email patterns. Original artifact identities and sanitized-copy hashes map in `artifacts.json`; every included file is scanned. Large files are listed in `omissions.json`, never copied into the bundle.

`git diff --shortstat origin/AI4Research-Main origin/ai4r_ccv2`: **3331 files changed, 15437 insertions(+), 510852 deletions(-)**. `--dirstat=files,3`, startup/config hunks, feature `--stat`, and both `merge-base --is-ancestor ... HEAD` checks completed (ancestry exit 0 for each). See [LINEAGE.md](../../docs/architecture/factory/LINEAGE.md). Default deletion inventory is 3145 plus one rename; explicit `--no-renames` yields the prior 3146 tree-deletion count. `git diff --check` passes. No commits, pushes, merges, deployments, new builds or lab runs were performed by F08. Contracts and primary factory store were used read-only; other operator activity may continue independently.

## Acceptance cases T01–T08

“Offline only” is not live proof. Source/code review is not a live execution. Cases below preserve the work-order acceptance wording; task-level completion is not inferred from a passing unit suite.

| Case | Work-order acceptance case | Status / scope | Evidence |
|---|---|---|---|
| T01.1 | Record fetched versus reference pins and preserve unrelated work | Recorded intake + source review | [intake.json](intake.json); target/donor/feature pins; pre-existing untracked operator evidence preserved. |
| T01.2 | Verify local Orin board, JetPack/CUDA, Docker, memory/disk and queue; no Spark provisioning or competing GPU/build job | Recorded intake; no new F08 provisioning | intake host and queue_snapshot; no competing job started by F08. Does not independently prove all earlier operator activity was nondisruptive. |
| T01.3 | AI4Research-Main target and CC-v2 donor ancestry are rechecked; preserve concurrent changes | Verified local Git ancestry | [LINEAGE.md](../../docs/architecture/factory/LINEAGE.md), both ancestry exit codes 0; working-tree changes preserved. |
| T02.1 | Same evidence bytes survive process restart | Offline only; live durable evidence also exists | `tests/factory/test_store.py::test_restart_roundtrip`; exported persisted live records. No live injected restart-loss trial. |
| T02.2 | Stale decision revision cannot overwrite a newer decision | Offline only | `tests/factory/test_store.py::test_stale_decision_rejected`; live revisions are ordered, but stale overwrite rejection was not exercised live. |
| T02.3 | Same artifact identity with different bytes is rejected | Offline only | `tests/factory/test_store.py::test_artifact_conflict_rejected`. |
| T02.4 | No success acknowledgment when persistence fails | Offline fault injection only | `tests/factory/test_store.py::test_persistence_failure_no_ack` and `test_decision_commit_failure_rolls_back_pointer`. |
| T02.5 | Cross-task access is denied unless explicitly authorized | Offline negative test + recorded explicit grant | `tests/factory/test_store.py::test_cross_task_denied` / `test_cross_task_allowed_when_granted`; attempt-2 task constraints.read_tasks and session. No live denied cross-task attempt. |
| T03.1 | Actual build longer than 60 seconds survives client disconnect and reconnect | Recorded real operator demonstration | operator bundle: `aae86e0c5e304397816140dfbad11749`; client_exit → new-client observed_terminal_by_new_client, ~209 s; Builder/agent runs also exceed 60 s. |
| T03.2 | Identical key and request returns the same job; changed request with same key conflicts | Recorded real operator demonstration | operator receipt duplicate_submit_same_key_same_request (one job) and changed_request_same_key (KeyConflict); same attempt ID. |
| T03.3 | Changed inputs cannot reuse incompatible completed output | Offline only for incompatible completed output | `tests/factory/test_builder.py::test_changed_inputs_no_reuse`; live changed-key conflict does not prove all completed-output invalidation cases. |
| T03.4 | Observed cancellation and cleanup; no untracked children or duplicate recovery launch | Partial live + offline recovery tests | operator attempt `c440203a1ca74814ac717f18374f590a` cancelled after running; process groups reaped, containers_unverified. `test_cancel_observed_no_orphans`, `test_lost_launch_ack_recovered`, `test_reconnect_recovers_same_job` are offline. Full live no-orphan/duplicate-recovery proof absent. |
| T03.5 | Pinned dependency preparation and real image construction produce linked receipts | Recorded real preparation and construction; dependency acquisition caveat | attempt-2 `:prep`, `:build-record`, `:receipt`; cache_hit true. Actual dependency download on a cache miss is not demonstrated live; `test_prep_pulls_only_digest` is offline. |
| T03.6 | Reuse qualified native jetson-orin recipe; no x86/Spark image substitution | Recorded real native target build | attempt-2 build record target_profile/requirements/platform, admission artifact; image Architecture arm64. Reinspection denied in F08. |
| T04.1 | Validate against actual CC-v2 schemas and all material paths | Offline validation + exported materials | `tests/factory/test_capsules.py::test_declarations_and_materials`, `test_component_schema_and_hashes`; bundle capsules and release hashes. |
| T04.2 | Preserve existing runner receipt/replay/grant behavior | Offline regression coverage; donor suite limitations retained | factory capsule tests exercise receipt/grant/replay behavior. Full donor suite not rerun by F08; intake has 10 pre-existing host failures. |
| T04.3 | Run live JiuwenSwarm discovery, material read and executable invocation | Recorded real agent demonstration | attempt-1 and attempt-2 `session.jsonl` contain cc_list/cc_material/cc_call events, paired with facade recording and durable records. |
| T04.4 | Treat denied grants and failed receipt states as failures, not normal success | Offline grant denial + recorded failed receipts | `test_missing_grant_denied`; attempt-1 inconclusive and attempt-2 failure/revision chain. A live denied-grant trial was not demonstrated. |
| T05.1 | Controlled actual preflight/config rejection leads to queried evidence and a revised next action | Recorded real agent demonstration | attempt-2 observation `abcedeb4176b4740acb2daf2bf094dd5`, artifact `e25248518f9549c69640be5e84e7af23`, decision rev 2. |
| T05.2 | Successful corrected attempt retains original failure and its cost | Recorded real agent demonstration | six decision revisions, initial K48 preserved in task; K8 correction, build and accepted evaluation; costs/timestamps in attempts and session. |
| T05.3 | No hard-coded repair/success transcript | Source review + recorded real execution | controller delegates action choice; no host repair transcript; session records material reads and tool calls. `tests/factory/test_controller.py` is offline support. |
| T05.4 | Budget exhaustion yields partial outcome with pending work | Offline only | `tests/factory/test_controller.py::test_budget_exhaustion_partial` and `test_wall_clock_exhaustion_partial`. Attempt-1 inconclusive is not a live budget-exhaustion trial. |
| T06.1 | Manager admits and verifies the exact local image on Satay; same-host delivery is labeled honestly | Recorded real admission, same-host only | attempt-2 admission `admission:78856fb9c5c49df9a0550cd1342b810dab29f02dfee36929827780fe1f276aa2` binds image to build; Reviewer re-exported bundles carry live Docker identity; inspect each snapshot’s provenance. |
| T06.2 | Actual model executes with declared settings and frozen scoped correctness check | Recorded real inference | lab `cabd3a09443f493899c756ab0ce1a671`, `:cmd.txt`, `:config.json`, `:stdout.txt`, `:result.json`, `:evaluation`; frozen contract included. |
| T06.3 | Wrong target/image, failed correctness and upload failure are distinct outcomes | Offline negative cases only | `tests/factory/test_lab.py::test_admit_bad_digest`, `test_admit_wrong_target`, `test_eval_mismatch_candidate_failed`, `test_upload_failure_no_ack_then_retry`. Accepted live run is not proof of these failure modes. |
| T06.4 | Manager persists evidence and acknowledges; lab spool retries idempotently | Live successful persistence/ack; retry faults offline | attempt-2 records/uploads.json and lab artifacts/evaluation; `test_upload_idempotent`, `test_upload_failure_no_ack_then_retry` cover failure/retry offline. |
| T06.5 | No lab direct write to primary factory evidence storage | Source review + offline boundary test | `lab_runner.py` writes spool, Manager ingests; `tests/factory/test_lab.py::test_lab_never_writes_store_directly`. Live evidence follows that path; no live attempted direct-write violation. |
| T07.1 | Target revision is a genuine ancestor of the feature branch | Verified local Git ancestry | AI4Research-Main → HEAD merge-base --is-ancestor exit 0 in LINEAGE.md. |
| T07.2 | CC-v2 donor changes and legacy removals are reviewed and recorded | Completed source hunk/inventory review | LINEAGE.md: actual shortstat/dirstat, per-file startup/config changes, rename distinction, feature delta. |
| T07.3 | One native factory execution path; no AI4R adapter or restored fixed-plan pipeline | Implemented; source review + recorded execution | native factory CLI/controller/CCs, AMENDMENT.md and MIGRATION.md; no M1 adapter/pipeline restoration. |
| T07.4 | Unsupported legacy config fails with a migration explanation | Offline subprocess tests only | `tests/factory/test_migration.py` (12 cases); early startup errors with migration explanation. Direct TUI/later dotenv caveats remain. |
| T07.5 | Real factory run through the native JiuwenSwarm entrypoint | Recorded native facade execution; exact root spelling only offline | recordings show JiuwenSwarm codex_subscription adapter and matching task/session IDs. They do not capture the original shell invocation; root `jiuwenswarm factory` dispatch is source/test covered, not separately re-demonstrated live in F08. |
| T07.6 | Shared AI4Research-Main remains unchanged until separately authorized publication/merge | Local refs unchanged by F08; no remote verification | pinned origin target and unchanged HEAD; no commit/push/merge. F08 did not contact the remote to establish its present shared-branch state. |
| T08.1 | CC-only running order fits ten minutes | Script prepared; timed rehearsal NOT demonstrated | [DEMO-10MIN.md](../../docs/architecture/factory/DEMO-10MIN.md) allocations total 10:00; existing recordings are longer historical executions. |
| T08.2 | All required live acceptance evidence is linked and reproducible | Partial; all existing evidence linked, live gaps remain | three bundles, MANIFESTs and recordings; missing live negative/recovery proofs listed above. RUNBOOK supplies reproduction procedures but F08 ran no new inference/build. |
| T08.3 | RSI profiling and second improvement are excluded from readiness | Scope satisfied in documents | DEMO-10MIN.md and this report exclude RSI profiling and second optimization from readiness. |
| T08.4 | Report cc_demo_ready and ai4r_lineage_and_migration_verified without implying a shared-branch merge | Reviewer-owned pending decision | both required status lines remain PENDING-REVIEW; no shared-branch merge implied. |

## Reviewer additions (live, after F08)

| Case | Live receipt | Result |
|---|---|---|
| T02.5 cross-task read denied without grant | `live-negative-receipt.jsonl` `cross_task_read_without_grant` | `ScopeDenied` on the real store |
| T06.3 wrong/bad image distinct outcome | `live-negative-receipt.jsonl` `wrong_image_for_build`, `non_engine_base_image`, `right_tag_wrong_id` | `AdmissionError BAD_DIGEST` ×3 against the real Docker store (wrong-target path not reached because digest check runs first; wrong-target remains offline-tested) |
| T04.4 call without required grant | `live-negative-receipt.jsonl` `call_without_required_grant` | real CC-v2 host receipt state `blocked` |
| T07.4 legacy config through installed entrypoint | `live-entrypoint-receipt.txt` | `JIUWENSWARM_M1_PROFILE=1 jiuwenswarm factory …` → exit 2 + migration message; `jiuwenswarm research` → migration message |
| T07.5 root `jiuwenswarm factory` dispatch | `live-entrypoint-receipt.txt` | status of the accepted task via `jiuwenswarm factory status` |
| T03.5 dependency prep refusal | operator attempt (disk 6.9 GB < 8 GiB) | real `DISK_SPACE_LOW` prep failure; build not started |
| Image identity (F08 sandbox gap) | bundles re-exported outside the sandbox | `image-identity.json` carries live `docker image inspect` (`sha256:f02f8a93…`, arm64) |

Still offline-only (stated, not claimed live): persistence-failure no-ack, stale-revision overwrite, budget exhaustion, failed-correctness evaluation, upload-failure spool retry, cache-miss base-image pull.

## Blockers and limits for reviewer decision

- Native CCs are trusted-local; their grants are host policy, not process isolation.
- Image handoff is same-host local admission. No network image transport is demonstrated.
- Contract scope is identical greedy continuation of one fixed prompt, not model accuracy. The model SHA256 is null in the contract; image and stdout identities do not establish an independent model-file digest.
- One candidate lab run, n=1 timing (745 ms/token); no speedup, statistical benchmark or quality-generalization claim.
- Attempt 1 needed operator intervention for an inspector tool defect. Attempt 2 had an additional inspector input-shape failure and one Manager input rejection, both retained; its controlled K repair was agent-driven.
- Full live acceptance is incomplete: live fault injection for persistence/scope failures, dependency cache-miss acquisition, budget exhaustion, full cancellation container cleanup and duplicate-recovery races is not established. Offline tests remain labelled as such.
- Ten-minute script is prepared; no new timed rehearsal/ten-minute recording was made by F08. Existing `script -T` recordings and scrubbed agent sessions preserve the real runs.
- (Resolved by reviewer re-export) bundles now carry live Docker image identity; the records distinguish index digest, config digest and Docker-reported Id.
- Archives exceed 50 MiB and are listed rather than exported. Accepted archive SHA256 is `3da83cf9adf45a2086ae4ab60144a8780c0ff29bd758dc04b444ae888bf83c24` (1,392,989,184 bytes); attempt-1 archive was pruned, as [PRUNED.md](PRUNED.md) records. Bundles are self-contained for included evidence, not runnable images/models.
- Export-time capsule hashes cannot retrospectively attest which exact release bytes were loaded in a past session. Sanitized content may differ from original bytes; mapping preserves both hashes. Pattern-based secrets scanning is not proof that arbitrary encodings contain no secrets.
- Build preparation requires at least 8 GiB free. The first F08 suite run encountered this real host constraint; successful rerun did not weaken it.
- Intake donor baseline has **10 failures on this host**: 8 from Git 2.34 lacking `git apply --allow-empty`, 1 because compute_service image was not built for arm64, 1 from host process semantics (`test_exited_launcher_does_not_confirm_children_stopped`). They predate factory changes and were not rerun or fixed by F08.
- Residual TUI TypeScript M1 environment reads and the later-dotenv/direct-TUI limits of the early Python migration guard remain documented in LINEAGE.md/MIGRATION.md. No M1 restoration is proposed.

Reviewer should set each pending readiness line independently after reviewing the evidence and deciding whether its explicitly listed gaps meet the requested acceptance boundary. Setup/start/recovery/export procedures: [RUNBOOK.md](../../docs/architecture/factory/RUNBOOK.md).

F10 snapshot note: the reviewer re-export documented above reported live Docker identity. Docker socket/group access is denied in the F10 environment, so the current re-export explicitly records build-record fallback provenance. No fresh live Docker inspection is claimed.
