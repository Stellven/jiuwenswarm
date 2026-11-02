# PAS-M1 state and evaluation log

Working notes for later evaluation of the spec and the development workflow. TASKS.md, each TASK's tasks.md and evidence/ remain the authority.

## Current state (updated in place)

| Field | Value |
|---|---|
| Updated | 2026-11-01 18:45 EST (after the WSL clock resync), end of Session 2 |
| Current phase / task | Phase 1, PAS-M1-001 (base simulator): implemented, converged, phase 1 report written. Phase 2 not started |
| Exits passed | X1.3, X1.4 (both parts), X1.5 |
| Exits failed | X1.1 (run 2: the signed-in Free ChatGPT account has no `gpt-6.1-sol`, which AI4R's route requires) |
| Exits blocked | X1.2 (owner confirmation of the [confirm] tolerances; every bench is within its frozen tolerance), X1.6 (needs an owner commit; rehearsal reproduced bit for bit) |
| Open blockers | Owner: an entitled model sign-in for X1.1 (AI4Research workspace admin to enable device-code authentication, Q-09); confirm TB-01 0.5% and the TB-03 to TB-08 proposed tolerances (Q-01, Q-02); a commit for X1.6 (U-02); AI4R local-research dataset for phases 2 and 4 (Q-08); Fit2Form for phase 2 (Q-03) |
| Open questions | Q-01 to Q-09 (TASKS §6); C-05 coding prompt versus r0.4.3 on AI4R patches |
| Last commit | `d3054741d` (owner). No commits by the coding agent; all SIMLAB code and records are uncommitted |

## Evaluation log (append-only)

Tags: SPEC-HELPED, SPEC-GAP, SPEC-AMBIGUOUS, SPEC-CONFLICT (spec vs repo), SPEC-WRONG, WORKFLOW-HELPED, WORKFLOW-FRICTION, REWORK, NEEDED-HUMAN. Decision sources: **spec** (source section), **repo** (team doc path) or **judgment**.

### 2026-10-30 20:26 EDT · SPEC-HELPED
- **Where:** `source-baseline.json`; coding prompt step 0 ("Register all sources with sizes and SHA-256").
- **What happened:** All 11 files under `source/` hash-match the baseline, and its aggregate digest (`3d2308fc…67a1`) recomputes from the documented method.
- **What I did:** Took sizes and hashes from a fresh `sha256sum` and confirmed they match the baseline.
- **Cost:** 1 attempt, no rework.

### 2026-10-30 20:26 EDT · SPEC-GAP
- **Where:** `source-baseline.json` field `revision`.
- **What happened:** It reads `r0.4`, but every page header and the source README say r0.4.2.
- **What I did:** Registered the files by hash, which is unambiguous. Recorded the mismatch in TASKS §6 and left the file unchanged, since it belongs to the owner.
- **Decision source:** judgment (sources are owner-maintained; AGENTS working rule 11, preserve unrelated work).
- **Cost:** none.

### 2026-10-30 20:30 EDT · WORKFLOW-FRICTION
- **Where:** Coding prompt, "SPEC KIT UNDER CLAUDE CODE" (also the local CLAUDE.md note): skills at `plugins/spec-kit/skills/<name>/SKILL.md`.
- **What happened:** The real folders are named `plugins/spec-kit/skills/speckit-<name>/`, so `skills/register/` does not exist.
- **What I did:** Used `skills/speckit-<name>/SKILL.md`.
- **Decision source:** repo (`plugins/spec-kit/skills/` listing).
- **Cost:** 1 failed listing.

### 2026-10-30 20:35 EDT · SPEC-CONFLICT
- **Where:** Architecture Context, "Required reading by dependency", row 2: `placement.md`, `capsules.md`.
- **What happened:** The design package has no `placement.md` or `capsules.md`. Placement is in `docs/architecture/design-package/platform/README.md`, and capsules are in `2-capability-capsules.md` plus `capability-capsules/`. The other required-reading paths exist (`design-method.md` and `principles.md` under `method/`, `reference/field-catalog.md`, `docs/capsules/agentic-builder.md`, `typed-planner-m1.md`, `benchmarks/harbor_suite/`, `deploy/m1/capsule_checks.py`, benchmark requirements v0.12 at `docs/verify/BENCHMARK_REQUIREMENTS_Oct_14.md`).
- **What I did:** Read the pages that carry that content and recorded the mapping in TASKS §6.
- **Decision source:** repo (paths above).
- **Cost:** 2 extra searches.

### 2026-10-30 20:37 EDT · SPEC-HELPED
- **Where:** Architecture Context, open input A-13; Architecture Main X1.1.
- **What happened:** The AI4R platform design runs M1 on the GB10 server ("M1 never runs on a user's computer", `platform/README.md`, D35) and publishes container port 5173 on a private address. SIMLAB M1 runs AI4R on the laptop at `127.0.0.1:5175`. The source already flags this as A-13 and makes X1.1 check it first, so it did not need to be resolved here.
- **What I did:** Made X1.1 the first block of PAS-M1-001, with the owner deciding if it fails. The port follows the SIMLAB source and AGENTS.md ("5175 is our only local host").
- **Decision source:** spec (Architecture Main, Placement and X1.1; Architecture Context, A-13) and repo (`AGENTS.md`).
- **Cost:** none.

### 2026-10-30 20:38 EDT · WORKFLOW-FRICTION
- **Where:** Coding prompt RULES ("Do not add checklist … cards") versus SESSION 1 step 3 (`$speckit-checklist`); the checklist skill (items are reviewer-owned and never marked `[x]`) versus the v2 process (no reviewer gate).
- **What happened:** The instructions seem to conflict.
- **What I did:** Followed `docs/code/SPEC_KIT_WORKFLOW.md` §3: Spec Kit's requirements checklist is a generated diagnostic, not the removed implementation checklist. The checklist goes in the feature's `checklists/`, its items stay unchecked as the skill requires, and the gaps it finds are fixed in spec.md and plan.md. It gates nothing.
- **Decision source:** repo (`docs/code/SPEC_KIT_WORKFLOW.md` §3; `.specify/memory/constitution.md` VII).
- **Cost:** none.

### 2026-10-30 20:40 EDT · SPEC-GAP
- **Where:** Verification, benchmark and test plan, "Test benches": "tolerances are [confirm] values".
- **What happened:** Only TB-01 (0.5%) and TB-02 (0.1%) give a tolerance. TB-03 to TB-09 have known answers but no tolerance.
- **What I did:** Carried it into `$speckit-clarify` for PAS-M1-001 and did not invent numbers.
- **Decision source:** spec (test plan, "Test benches"); AGENTS working rule 7 (do not fabricate thresholds).
- **Cost:** none yet.

### 2026-10-30 20:40 EDT · SPEC-GAP
- **Where:** PRD Main SL-5 ("Each library passes its known-answer case before research use") versus test plan TB-12 (magnets and hover thrust only).
- **What happened:** The extra-forces library includes tires, which have no known-answer case.
- **What I did:** Recorded it as PENDING_SOURCE on PAS-M1-006. It affects only that library's tire admission.
- **Decision source:** spec (PRD SL-5; test plan TB-12).
- **Cost:** none.

### 2026-10-30 20:42 EDT · SPEC-AMBIGUOUS
- **Where:** Coding prompt's suggested TASK list ("builder and first demonstration … AI4R connection") versus Architecture Main build order (phase 2 includes "a thin AI4R connection", exit X2.6).
- **What happened:** It was unclear whether X2.6 belongs to the phase 2 TASK or to the AI4R connection TASK.
- **What I did:** Gave X2.6 and the SIMLAB-IF-002 capsule ports to PAS-M1-002, because phase 2 exits close in the phase 2 report. PAS-M1-012 (AI4R journey connection) owns X4.1, X4.2 and X4.5 and uses IF-002.
- **Decision source:** spec (Architecture Main, build order and Required proof) plus judgment (one phase report per phase TASK).
- **Cost:** none.

### 2026-10-30 20:42 EDT · SPEC-AMBIGUOUS
- **Where:** Architecture Context SIMLAB-IF-001 "Operations": phase 1, 2, 3 and 4 operation sets; Code SOP §6 (one owning TASK per IF).
- **What happened:** The operations are built by four different TASKs, but an IF has a single owner.
- **What I did:** PAS-M1-001 owns all of IF-001@r1, which lists every operation with its phase and providing TASK. Later TASKs implement their operations against it, and any change goes through PAS-M1-001's change table.
- **Decision source:** repo (`docs/code/Code_SOP.md` §6) plus judgment.
- **Cost:** none.

### 2026-10-30 20:43 EDT · NEEDED-HUMAN
- **Where:** Coding prompt, OWNER PREFLIGHT: "Fetch Fit2Form code and data at a pinned commit; record licenses."
- **What happened:** No Fit2Form checkout or data is on the machine.
- **What I did:** Recorded it as an open input for PAS-M1-002 (X2.1 and X2.2). It does not affect phase 1.
- **Decision source:** spec (Architecture Context, O-12; coding prompt preflight).
- **Cost:** none.

### 2026-10-30 20:44 EDT · WORKFLOW-FRICTION
- **Where:** Session instructions.
- **What happened:** During the session the coding prompt gained a SESSION NOTES requirement (`notes/session-log.md`), and the user added this `notes/state.md` requirement.
- **What I did:** Created both files and backfilled this log from the session's events.
- **Decision source:** user instruction.
- **Cost:** 1 backfill pass.

### 2026-10-30 20:52 EDT · SPEC-CONFLICT
- **Where:** Architecture Context SIMLAB-IF-002 ("Run capsule: … the AI4R benchmark payload … out") versus the repo's `docs/architecture/design-package/reference/capsules/research-benchmark.md` §4.1 (`benchmark-payload:field-contract:2`).
- **What happened:** The AI4R payload allows only the `baseline` and `treatment` roles, each with `repeat_count` runs in a fixed order, and requires `blueprint_ref`, `poc_ref`, `environment_lock_ref` and `provisioning_receipt_ref`. SIMLAB experiments can have any number of arms, factors and conditions. The coding prompt forbids modifying AI4R contracts.
- **What I did:** Recorded it as TASKS §6 Q-05 and as the open question on IF-002@r1. The mapping is left for PAS-M1-002's plan; no phase 1 work depends on it.
- **Decision source:** spec (Architecture Context IF-002; coding prompt RULES) and repo (`research-benchmark.md` §4.1).
- **Cost:** 1 extra read.

### 2026-10-30 20:58 EDT · WORKFLOW-HELPED
- **Where:** `$speckit-register`; TASKS template §3 ("Each AC has exactly one owning spec").
- **What happened:** The template's coverage table forced every SL part, exit, phase row and family onto an owning AC before any spec existed, and exposed four clauses that would otherwise have had no home: the tire known answer, evidence levels, the compute-tracking instruction, and phase reports for phases spanning two TASKs.
- **What I did:** Reserved AC IDs in each TASK.md and cross-checked them with a script; nothing was missing.
- **Decision source:** repo (`plugins/spec-kit/templates/TASKS_TEMPLATE.md`; `docs/code/Code_SOP.md` §2).
- **Cost:** 1 edit to add the compute-tracking row.

### 2026-10-30 21:08 EDT · NEEDED-HUMAN
- **Where:** `$speckit-clarify` for PAS-M1-001; test plan "Test benches" ("tolerances are [confirm] values").
- **What happened:** Asked the owner one question: how should the TB-03 to TB-08 tolerances be fixed? The owner chose the recommended option: the agent proposes each tolerance with a reason, frozen and marked [confirm] before the case's first run, and the owner confirms before X1.2 is claimed.
- **What I did:** Recorded it in spec.md Clarifications and AC-010, TASKS §6 Q-02 and TASK §5, and re-validated the spec-quality checklist (16/16).
- **Decision source:** owner answer; spec (test plan "Test benches").
- **Cost:** 1 question, 4 edits.

### 2026-10-30 21:05 EDT · SPEC-GAP
- **Where:** Architecture Main X1.1 and Placement; test plan "Check groups" ([confirm: 4 GB] cap); repo `deploy/m1/OPERATIONS.md` (AI4R app container "has a 4 GiB / 256 PID envelope"; the model route needs the owner to "complete the app's model authentication" through the bootstrap URL).
- **What happened:** The AI4R container's 4 GiB plus a 4 GB check-group container exceed the 6 GB WSL limit, and there is no Codex credential in WSL (`~/.codex/auth.json` absent). X1.1 therefore needs an owner sign-in, and check groups cannot run beside AI4R at those caps.
- **What I did:** No spec change. The plan will run check groups with AI4R stopped, run X1.1 with AI4R and a lightweight simulator process, and list owner sign-in as an X1.1 prerequisite.
- **Decision source:** repo (`deploy/m1/OPERATIONS.md`); judgment (scheduling).
- **Cost:** 2 extra reads.

### 2026-10-30 21:12 EDT · WORKFLOW-FRICTION
- **Where:** `$speckit-checklist` step 1 (`check-prerequisites.ps1 -Json -Template checklist-template`) versus the coding prompt's order (checklist is step 3, before plan at step 4).
- **What happened:** The helper exits with "plan.md not found … Run $speckit-plan first", so the prompt's order cannot run the skill's setup command as written.
- **What I did:** Resolved paths with `-PathsOnly` and generated the checklist from spec.md, which is the only artifact it needs before planning.
- **Decision source:** coding prompt (order); repo (`plugins/spec-kit/scripts/powershell/check-prerequisites.ps1`).
- **Cost:** 1 failed helper call.

### 2026-10-30 21:15 EDT · WORKFLOW-HELPED
- **Where:** `$speckit-checklist` (requirements-quality "unit tests for English"), file `PAS-M1-001/checklists/reproducibility-and-failure.md`.
- **What happened:** Of 31 items, 7 exposed real spec gaps: build identity for replay, rerun pass/fail semantics, watchdog triggers, limits for confined code, cancelling a queued run, zero-trial designs, undeclared checkpoint points. 11 more were left for the plan to resolve.
- **What I did:** Fixed the 7 in spec.md (AC-004, AC-007, AC-009, AC-011, Edge Cases) and resolved the 11 in plan.md and research.md. The markers stay unchecked because the skill reserves them for a reviewer; under v2 they gate nothing.
- **Decision source:** repo (`plugins/spec-kit/skills/speckit-checklist/SKILL.md`; `docs/code/SPEC_KIT_WORKFLOW.md` §3).
- **Cost:** 5 spec edits.

### 2026-10-30 21:25 EDT · SPEC-HELPED
- **Where:** test plan "Check groups" and "Reports and evidence"; repo `deploy/m1/capsule_checks.py`; `benchmarks/harbor_suite/AUTHORING.md`.
- **What happened:** The source names the exact evidence files, exit codes and case layout, and the repo has working patterns for both, so B11 and B12 could be planned with no invention.
- **What I did:** Planned `tools/check_groups.py` after `capsule_checks.py` and the SIMLAB-Bench layout after the Harbor contract (stdlib oracles).
- **Decision source:** spec plus repo.
- **Cost:** none.

### 2026-10-30 21:25 EDT · SPEC-AMBIGUOUS
- **Where:** Architecture Placement ("Agent-authored code is always confined (no network, no credentials, declared limits)"); test plan "Always: no network from executors".
- **What happened:** The enforcement mechanism is left open. The runner needs a model route in phase 3, so whole-container `network: none` alone will not stay sufficient.
- **What I did:** Planned a per-worker seccomp filter (deny `AF_INET`/`AF_INET6` sockets) plus rlimits inside a network-less container (research.md R6), so executors stay network-less after PAS-M1-011.
- **Decision source:** judgment, constrained by spec and repo (`docs/architecture/design-package/platform/README.md`: packaging alone is not confinement).
- **Cost:** none.

### 2026-10-30 21:28 EDT · SPEC-CONFLICT
- **Where:** Architecture Main X1.6 ("A fresh checkout … reproduces a recorded result") versus the coding prompt and CLAUDE.md ("No commits or pushes unless I ask").
- **What happened:** A fresh checkout needs a commit that contains the SIMLAB code, and the agent may not commit.
- **What I did:** Planned a rehearsal from a clean export, recorded as a rehearsal and not PASS, with V-X1.6 run only after an owner commit (plan U-02; tasks T066, T067).
- **Decision source:** spec plus owner rule.
- **Cost:** none.

### 2026-10-30 21:32 EDT · WORKFLOW-FRICTION
- **Where:** `$speckit-analyze` ("STRICTLY READ-ONLY … user must explicitly approve" remediation) versus `docs/code/SPEC_KIT_WORKFLOW.md` §4 ("Generated quality findings are diagnostic: resolve them in those files").
- **What happened:** The skill forbids applying fixes while the project process expects them.
- **What I did:** Kept analyze read-only and reported the findings, with remediation offered for owner approval. The only edit after analysis was the ordinary progress line for T004.
- **Decision source:** repo (both documents); the stricter rule followed.
- **Cost:** none.

### 2026-10-30 21:36 EDT · REWORK
- **Where:** TASKS §1, PAS-M1-001 TASK §1 and §3, plan header and B13.
- **What happened:** The owner committed the r0.4.2 sources (`d3054741d`, 20:28) while the session was running, so references to base `0b5292625` and to "uncommitted owner edits" went stale.
- **What I did:** Re-hashed the sources (unchanged) and confirmed `d3054741d` touches nothing outside `labs/physicalai_sim/` (AI4R tree identical). Updated 6 references.
- **Decision source:** repo (`git log`, `git diff --stat`).
- **Cost:** 1 scripted edit pass.

### 2026-10-31 18:45 EDT · SPEC-HELPED
- **Where:** `source-baseline.json` r0.4.3; owner message "re-verify the source hashes".
- **What happened:** All 11 files match by size and SHA-256 and the aggregate `3049f0bc…3aba` recomputes. The baseline `revision` now reads `r0.4.3` (C-01 resolved) and the required-reading paths now exist (C-02 resolved).
- **What I did:** Re-registered TASKS §1; closed C-01 and C-02.
- **Decision source:** spec (`source-baseline.json`; ARCHC "Required reading").
- **Cost:** 1 attempt.

### 2026-10-31 18:47 EDT · SPEC-CONFLICT
- **Where:** ARCH "AI4R connection and prompt use" (r0.4.3) versus owner coding prompt r0.4.2 RULES ("Do not modify AI4R stages, contracts, PRD or design").
- **What happened:** r0.4.3 allows a small recorded AI4R patch on `PhysicalAI-Sim` when the capsules cannot bridge a gap; the prompt still forbids AI4R changes to stages, contracts, PRD and design.
- **What I did:** Updated Q-05 to the adapter direction (the capsule translates, untranslatable content goes by reference or is reported) and recorded C-05: until the owner reconciles the prompt, any AI4R patch needs the owner's explicit go-ahead. No phase 1 impact.
- **Decision source:** spec (ARCH "AI4R connection") and the owner message; judgment for the interim rule.
- **Cost:** none.

### 2026-10-31 18:48 EDT · WORKFLOW-HELPED
- **Where:** `$speckit-analyze` findings A1 and A2 (Session 1), approved by the owner.
- **What happened:** The read-only analyze step left two fixes waiting for approval; with approval they took one small edit each.
- **What I did:** A1: IF-001 `checks` entries gain an optional `tolerance` {abs, rel} (TASK §5 A1, additive within r1). A2: the boundary checks of the experiment core moved to group `core` (plan r2).
- **Decision source:** owner approval; repo (`docs/code/SPEC_KIT_WORKFLOW.md` §4).
- **Cost:** 2 edits.

### 2026-10-31 19:40 EDT · SPEC-HELPED
- **Where:** Architecture Main build order ("a first check that the real local setup fits") and plan B13 (X1.1 first).
- **What happened:** Building and starting AI4R first exposed three real laptop facts before any SIMLAB core existed: the AI4R image build peaks at 5.3 of 5.9 GB of WSL memory (swap full), the local-research profile needs an imported public dataset, and the owner's team workspace disallows device-code sign-in.
- **What I did:** Recorded each as evidence (`evidence/RUN-x11-20261101.md`) and continued phase 1 with X1.1 not passed.
- **Decision source:** spec (ARCH build order, A-13).
- **Cost:** 1 AI4R build (968 s), 3 X1.1 attempts.

### 2026-10-31 19:55 EDT · SPEC-CONFLICT
- **Where:** `deploy/m1/compose.benchmark-runner.yaml` defaults (`AI4R_PLAN_SOURCE=static`, `AI4R_LOCAL_RESEARCH=1`) versus `deploy/m1/OPERATIONS.md` ("Start here: ordinary Docker").
- **What happened:** On a fresh state volume the documented start fails (`LOCAL_RESEARCH_CAPTURE_FAILED`): the capture needs `JIUWENSWARM_M1_EXTERNAL_DATASET` science resources for either plan source.
- **What I did:** Ran X1.1 with `AI4R_LOCAL_RESEARCH=0` (AI4R's own refusal-only research mode; local chat available), which X1.1 needs; recorded the dataset need for phases 2 and 4.
- **Decision source:** repo (`jiuwenswarm/research/bootstrap.py`, `local_profile.py`) plus judgment.
- **Cost:** 2 diagnostic runs of AI4R's capture module.

### 2026-11-01 01:31 UTC · NEEDED-HUMAN
- **Where:** X1.1 model route (U-01).
- **What happened:** The owner could not use device-code sign-in in the AI4Research team workspace ("contact your workspace admin to enable device code authentication") and signed in with a personal Free account. The Free plan has no GPT-6.1 Sol, which AI4R's route requires, so Codex failed the turn (`TURN_FAILED`).
- **What I did:** Recorded X1.1 run 2 as FAIL with the entitlement evidence (`codex.models.list`); asked the owner for an entitled sign-in; continued.
- **Decision source:** owner; repo (`jiuwenswarm/research/local_chat.py` model pin).
- **Cost:** 3 owner interactions (UI language, settings location, workspace choice).

### 2026-11-01 02:10 UTC · REWORK
- **Where:** tool interface (B09), AF_UNIX socket path.
- **What happened:** A data directory with a long path exceeded the 108-byte Unix-socket limit and broke the service.
- **What I did:** Made `socket_path` fall back to a private per-user runtime directory (mode 0700) keyed by the data directory, shared by server and clients; general, not a workaround for one path.
- **Decision source:** judgment.
- **Cost:** 1 failed bench run.

### 2026-11-01 02:20 UTC · SPEC-GAP
- **Where:** IF-001 Experiment `resolved_configuration` ("every effective engine and runner setting").
- **What happened:** Gravity is an engine setting the bench cases vary (tilted gravity for inclines; zero gravity for collisions), but the first schema omitted it, so validation correctly rejected those experiments.
- **What I did:** Added optional `gravity` (TASK §5 A3, additive within r1); validation keeps rejecting unknown fields.
- **Decision source:** spec (IF-001 "nothing implicit") plus judgment.
- **Cost:** 1 rerun.

### 2026-11-01 02:30 UTC · WORKFLOW-HELPED
- **Where:** test plan "Test benches" (each case reports its measured error) and the Harbor oracle contract ("missing evidence must never pass").
- **What happened:** Oracles that recompute each measurement from SIMLAB's raw traces caught two oracle-side definition mismatches (TB-04 restitution window, TB-09 comparison signal) before the release was frozen, and the negative controls (frozen and over-damped double pendulum, gravity-off stack) were caught by large margins.
- **What I did:** Fixed the oracles, reran a development pass (30 of 30 cells PASS), then froze release `pas-m1-phase1-r1`.
- **Decision source:** repo (`benchmarks/harbor_suite/AUTHORING.md`); spec (TP).
- **Cost:** 2 development reruns.

### 2026-11-01 23:23 UTC · WORKFLOW-FRICTION
- **Where:** environment clock (WSL2).
- **What happened:** The WSL clock jumped forward about 16.6 hours during a check-group run (started 06:44Z by the old clock, ended 23:23Z, 264 s monotonic), after the host slept (the owner's connection dropped).
- **What I did:** Kept monotonic durations (unaffected) and noted that wall-clock timestamps before the jump lag real time; no evidence was rerun for it.
- **Decision source:** judgment.
- **Cost:** none.

### 2026-11-01 23:35 UTC · REWORK
- **Where:** AC-018 ("X1.2 passes only when every phase 1 test bench passes to its frozen specification in these groups").
- **What happened:** The first full campaign ran in the runner container while the benchmark group held only a smoke run, which does not meet the AC's wording.
- **What I did:** Added the frozen-release campaign to the benchmark group (`tests/bench/test_campaign.py`), rebuilt, reran all four groups and the runner campaign (values identical across builds, 0 differences in 99 cells), re-admitted MuJoCo for the new build and repeated the fresh-checkout rehearsal.
- **Decision source:** spec (AC-018; plan V-X1.2).
- **Cost:** 1 rebuild, about 25 minutes of reruns.

### 2026-11-01 23:45 UTC · WORKFLOW-HELPED
- **Where:** `$speckit-converge` after `$speckit-implement`.
- **What happened:** Re-reading spec, plan and tasks against the code and evidence found three small gaps no open task covered: the port audit with AI4R running, BuildKit CPU in compute rows, and unrecorded plan additions.
- **What I did:** Appended T076 to T078; did T078 (plan.md "Implementation additions"); T076 waits for the X1.1 rerun and T077 is a documented limitation.
- **Decision source:** repo (`plugins/spec-kit/skills/speckit-converge/SKILL.md`).
- **Cost:** none.
