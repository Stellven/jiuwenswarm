# PAS-M1 Phase 1 completion report: base simulator

**Milestone PAS-M1 · Phase 1 (PAS-M1-001) · 2026-11-01 · Sources r0.4.3.** This report summarizes evidence; it does not replace it. Every claim links to an evidence record in `PAS-M1-001/evidence/` (not committed) or its byte-exact copy in [`../verification/20261101/`](../verification/20261101/README.md) (committed with the work).

**Phase 1 is not complete.** Three of six exits pass (X1.3, X1.4, X1.5). X1.1 has not passed: the model account that signed in cannot serve the model AI4R's route requires. X1.2 is blocked only on the owner's confirmation of tolerances. X1.6 is blocked only on an owner commit. Everything SIMLAB-side that the exits need is built and passing.

## 1. Scope and exits

Scope: Architecture Main "Build order" phase 1: a first check that the real local setup fits (AI4R, model route and simulator together); experiment core, MuJoCo, authoring tools, records, checks, world-state save and branch, traces, tool interface, doctor. Spec Kit records: [TASK](../PAS-M1-001/TASK.md), [spec](../PAS-M1-001/spec.md), [plan](../PAS-M1-001/plan.md), [tasks](../PAS-M1-001/tasks.md).

| Exit | Required observable result | Level | Result | Evidence |
|---|---|---|---|---|
| X1.1 | AI4R, one real model-route request and a simulator process run together on the laptop; resource use and failures recorded | BOUNDARY | **FAIL** (not passed). AI4R (530 MB) and the simulator (48 MB) ran together with 1.6 GB of WSL memory still free; the governed request reached Codex, which failed the turn because the signed-in Free account offers no `gpt-6.1-sol` | [RUN-x11-20261101](../verification/20261101/evidence/RUN-x11-20261101.md) |
| X1.2 | Phase 1 test benches pass to their frozen specifications | BOUNDARY | **BLOCKED** on the owner's confirmation of the [confirm] tolerances. All 30 F1 variants (90 cells) and 3 F5 variants (9 cells) pass to the frozen release, inside check groups `benchmark` and `all` and in the runner | [RUN-cg-20261101](../verification/20261101/evidence/RUN-cg-20261101.md), [RUN-bench-20261101](../verification/20261101/evidence/RUN-bench-20261101.md) |
| X1.3 | A malformed experiment returns all findings at once with typed errors; clean controls pass | BLOCK, BOUNDARY | **PASS**. Six planted defects of different kinds come back in one `validate` response, `submit` creates no run, paired clean controls complete on real MuJoCo | [RUN-cg-20261101](../verification/20261101/evidence/RUN-cg-20261101.md) |
| X1.4 | A coding agent with no other access builds, runs and inspects an experiment only through the tools | BOUNDARY | **PASS**. (a) MCP, Python client and CLI expose the same 24 operations with equal results and errors. (b) A headless agent with only the SIMLAB MCP tools built, ran and inspected a two-arm experiment (41 SIMLAB calls, no other tool) | [RUN-cg-20261101](../verification/20261101/evidence/RUN-cg-20261101.md), [RUN-x14b-20261101](../verification/20261101/evidence/RUN-x14b-20261101.md) |
| X1.5 | Replay identical on the same machine and build; save, restore and branch reproduce the continuation; each with its own rule | BOUNDARY | **PASS**. Replay bitwise identical (state digests and measurements); a changed-seed control is detected as different; replay across builds is refused; restore-and-continue bitwise equal; a what-if branch is identical up to its changed intervention | [RUN-cg-20261101](../verification/20261101/evidence/RUN-cg-20261101.md), [RUN-bench-20261101](../verification/20261101/evidence/RUN-bench-20261101.md) |
| X1.6 | A fresh checkout rebuilds the images from the lockfile and reproduces a recorded result with no hidden files | BOUNDARY | **BLOCKED** on an owner commit (no commit contains SIMLAB). A rehearsal from a clean export rebuilt with `--no-cache` and reproduced a recorded run bit for bit (not PASS) | [RUN-x16-rehearsal-20261101](../verification/20261101/evidence/RUN-x16-rehearsal-20261101.md) |

AC status ([tasks.md matrix](../PAS-M1-001/tasks.md#acceptance-and-evidence-matrix)): 18 of 22 PASS; AC-001 FAIL; AC-010 and AC-017 BLOCKED; AC-022 (this report) PASS as a document check over runtime evidence.

## 2. Commit, images and hardware

| Item | Value |
|---|---|
| Git | branch `PhysicalAI-Sim`, HEAD `d3054741d2cd` (owner). All SIMLAB code and records are uncommitted; no commit or push by the agent. The AI4R tree is unmodified |
| SIMLAB image | `simlab-runner:dev` `sha256:daeb5923f7f0…` (174 MB), build_id `d5339f6d04a9…` (content digest of `src/`, `uv.lock`, `pyproject.toml`); base `python:3.12-slim@sha256:aa943ce41142…`, uv `0.5.9@sha256:ba36ea627a75…` |
| Locked dependencies | MuJoCo 3.17.0, NumPy 2.5.4, Pydantic 2.14.2, mcp 2.3.0, pytest 9.2.0 (46 packages in `uv.lock`), Python 3.12.16 |
| AI4R image (X1.1) | `ai4r:local` `sha256:3dece40036aa…`, built unmodified from `deploy/m1/Dockerfile.app --target production` |
| Benchmark release | SIMLAB-Bench `pas-m1-phase1-r1` (85 files, sha256 `1f1d345d5645…`), frozen before any campaign |
| Hardware | AMD Ryzen 7 8845HS, 16 threads; WSL2 6.6.114.1 capped at 5924 MB (shared with Docker Desktop 28.3.2); RTX 3050 Laptop GPU 6 GB (unused: MuJoCo runs on the CPU); 622 GB free disk |
| Placement | `simlab-runner`: `network_mode: none`, no published port, read-only root, no secrets, data in `~/simlab-data` (outside the repository); AI4R alone on `127.0.0.1:5175` when running (X1.1 only) |

## 3. Results per exit, linked to evidence

| Evidence record | What it covers | Result |
|---|---|---|
| [RUN-x11-20261101](../verification/20261101/evidence/RUN-x11-20261101.md) | V-X1.1: AI4R build and start, owner sign-in, one governed `codex.chat` request during a MuJoCo run, resource samples | FAIL (three attempts kept: AI4R local-research capture needs a dataset; a tool defect, fixed; model entitlement) |
| [RUN-cg-20261101](../verification/20261101/evidence/RUN-cg-20261101.md) | Check groups `core` 88, `executors` 7, `benchmark` 35, `all` 130 tests, all passed on the final build; negative controls exit 124 and 2 for each group; every phase 1 BLOCK and BOUNDARY check | PASS |
| [RUN-bench-20261101](../verification/20261101/evidence/RUN-bench-20261101.md) | F1 and F5 campaigns, measured errors, speed record, registry admission | PASS against the frozen release; AC-010 awaits tolerance confirmation |
| [RUN-x14b-20261101](../verification/20261101/evidence/RUN-x14b-20261101.md) | V-X1.4 (b) agent-only run | PASS |
| [RUN-ops-20261101](../verification/20261101/evidence/RUN-ops-20261101.md) | Runner doctor, host port audit during a run, runner environment | PASS |
| [RUN-x16-rehearsal-20261101](../verification/20261101/evidence/RUN-x16-rehearsal-20261101.md) | Fresh-checkout rehearsal | Rehearsal reproduced; X1.6 BLOCKED |

## 4. Test bench errors

Final campaign `20261101T233110-a7f1aa` on the final build, every variant, three repeats; measured by SIMLAB through its tools, graded by each case's independent stdlib oracle, which also recomputes each measurement from the raw traces. The first campaign on the previous build gave the same values in all 99 cells.

| Bench | Variant | Cells PASS | Primary metric | Measured error (all 3 repeats identical) | Frozen tolerance | Source of the tolerance |
|---|---|---|---|---|---|---|
| TB-01 | small-swing | 3/3 | period relative error | 1.56e-04 | 0.005 | test plan [confirm] |
| TB-01 | large-swing-1p2 | 3/3 | period relative error | 7.81e-10 | 0.005 | test plan [confirm] |
| TB-01 | large-swing-2p6 | 3/3 | period relative error | 3.46e-10 | 0.005 | test plan [confirm] |
| TB-02 | earth-1s | 3/3 | fall distance relative error | 6.52e-15 | 0.001 | test plan |
| TB-02 | moon-0p5s | 3/3 | fall distance relative error | 6.03e-15 | 0.001 | test plan |
| TB-02 | earth-2s-euler | 3/3 | fall distance relative error | 5.00e-05 | 0.001 | test plan |
| TB-03 | slide-30deg-mu0p2 | 3/3 | acceleration relative error | 1.18e-05 | 0.01 | proposed [confirm] |
| TB-03 | slide-40deg-mu0p5 | 3/3 | acceleration relative error | 2.69e-04 | 0.01 | proposed [confirm] |
| TB-03 | stick-20deg-mu0p5 | 3/3 | displacement while sticking (m) | 7.88e-05 | 0.001 | proposed [confirm] |
| TB-04 | elastic-1to1 | 3/3 | restitution absolute error | 1.27e-06 | 0.005 | proposed [confirm] |
| TB-04 | damped-1to3 | 3/3 | restitution absolute error | 3.96e-04 | 0.005 | proposed [confirm] |
| TB-04 | damped-2to1 | 3/3 | restitution absolute error | 1.90e-04 | 0.005 | proposed [confirm] |
| TB-05 | light-damping | 3/3 | max relative error of period and decay rate | 3.97e-10 | 0.005 | proposed [confirm] |
| TB-05 | medium-damping | 3/3 | max relative error of period and decay rate | 5.12e-10 | 0.005 | proposed [confirm] |
| TB-05 | stiff-light | 3/3 | max relative error of period and decay rate | 9.21e-11 | 0.005 | proposed [confirm] |
| TB-06 | swing-a | 3/3 | max absolute angle error vs reference (rad) | 2.96e-09 | 0.001 | proposed [confirm] |
| TB-06 | swing-b | 3/3 | max absolute angle error vs reference (rad) | 1.15e-08 | 0.001 | proposed [confirm] |
| TB-06 | swing-c | 3/3 | max absolute angle error vs reference (rad) | 5.11e-09 | 0.001 | proposed [confirm] |
| TB-06 | frozen-gravity-off | 3/3 | max absolute angle error vs reference (rad) | 2.33 (caught) | 0.001 | negative control: must fail |
| TB-06 | over-damped | 3/3 | max absolute angle error vs reference (rad) | 0.581 (caught) | 0.001 | negative control: must fail |
| TB-07 | solid-sphere | 3/3 | acceleration relative error | 1.00e-03 | 0.005 | proposed [confirm] |
| TB-07 | hollow-sphere | 3/3 | acceleration relative error | 1.40e-03 | 0.005 | proposed [confirm] |
| TB-07 | solid-cylinder | 3/3 | acceleration relative error | 6.54e-04 | 0.005 | proposed [confirm] |
| TB-08 | equal-masses | 3/3 | floor contact force relative error | 0.00e+00 | 0.01 | proposed [confirm] |
| TB-08 | heavy-bottom | 3/3 | floor contact force relative error | 4.14e-16 | 0.01 | proposed [confirm] |
| TB-08 | heavy-top | 3/3 | floor contact force relative error | 0.00e+00 | 0.01 | proposed [confirm] |
| TB-08 | gravity-off | 3/3 | floor contact force relative error | 1 (caught) | 0.01 | negative control: must fail |
| TB-09 | controlled-noisy | 3/3 | identity (all comparisons bitwise equal) | bitwise identical | identity | identity rule (test plan) |
| TB-09 | contact-rich | 3/3 | identity (all comparisons bitwise equal) | bitwise identical | identity | identity rule (test plan) |
| TB-09 | factor-random | 3/3 | identity (all comparisons bitwise equal) | bitwise identical | identity | identity rule (test plan) |
| F5 | controlled-noisy | 3/3 | identity (all comparisons bitwise equal) | bitwise identical | identity | identity rule (test plan) |
| F5 | contact-rich | 3/3 | identity (all comparisons bitwise equal) | bitwise identical | identity | identity rule (test plan) |
| F5 | factor-random | 3/3 | identity (all comparisons bitwise equal) | bitwise identical | identity | identity rule (test plan) |

Notes: TB-01's small-swing error (1.6e-4) is the small-angle formula's own offset (theta0^2/16) against the exact period, which the large-swing variants match to 1e-9. TB-04's expected restitution is the contact law's closed form (linear spring-dashpot with force-based separation, Schwager and Poeschel 2007), which MuJoCo's direct contact parameters follow. TB-06's reference is an independent pure-Python RK4 at a tenth of the step, with its own convergence test.

**Tolerances that need the owner's confirmation** (spec Clarifications 2026-10-30; TASKS §6 Q-01, Q-02). Each is frozen in `benchmarks/simlab_bench/cases/<case>/referee/criteria.json` with its reason:

| Bench | Proposed tolerance | Reason (short) |
|---|---|---|
| TB-01 | 0.5% period (the source's own [confirm] value) | Source value |
| TB-03 | 1% acceleration when sliding; 1 mm travel in 0.9 s when sticking | Soft regularized friction; observed at most 0.03% and 0.08 mm; a frictionless or sliding block misses by far more |
| TB-04 | 0.005 absolute restitution; 1e-9 relative momentum drift | Impedance 0.9999 and step size; observed at most 4e-4 and 1.6e-15 |
| TB-05 | 0.5% for period and decay rate | Same as the source's pendulum tolerance; observed 5e-10 |
| TB-06 | 1e-3 rad over 2 s; 1e-6 relative energy drift | Observed at most 1.1e-8 rad and 6.2e-14 energy drift; frozen and over-damped controls miss by 0.58 to 2.3 rad |
| TB-07 | 0.5% acceleration | Soft-contact slip; observed at most 0.14%; the three inertias differ by 6% or more |
| TB-08 | 1% floor force; 0.1 mm top-box height range after settling; 1 mm penetration | Observed force exact to rounding, zero top-box height change after settling, penetration up to 0.64 mm; gravity-off control fails by 100% |

## 5. Results per SIMLAB-Bench family

| Family | Cases | Cells (variants x 3 repeats) | PASS | FAIL | BLOCKED | Report |
|---|---|---|---|---|---|---|
| F1 Known-answer physics | TB-01 to TB-09 | 90 (30 variants, including 3 negative controls) | 90 | 0 | 0 | [`family_F1.md`](../../../benchmarks/reports/20261101/campaign-F1-F5/family_F1.md) |
| F5 Agreement (replay, same machine and build) | `f5-replay` | 9 | 9 | 0 | 0 | [`family_F5.md`](../../../benchmarks/reports/20261101/campaign-F1-F5/family_F5.md) |

There is no aggregate score. Raw per-cell evidence stays in `~/simlab-data/bench-reports/20261101T233110-a7f1aa/`; the repository report indexes it by SHA-256.

## 6. Official benchmark results (phase 1 adoptions)

| Adopted benchmark (test plan) | Use in phase 1 | Result |
|---|---|---|
| MuJoCo engine tests; Drake inclined-plane and friction tests; the seven analytic tests of arXiv 2603.14634; ContactBench criteria | Patterns and formulas of TB-01 to TB-08, cited in each case | Used; every case cites its reference; the release records MuJoCo 3.17.0, so an upgrade fails the release check and forces a rerun |
| MuJoCo state and batch API (`mj_getState`, 3.17) | Determinism, replay and checkpoints (`mjSTATE_INTEGRATION`) | TB-09 and F5: 27 of 27 cells identical |
| MuJoCo `testspeed` | Speed and cost record | The 3.17.0 wheel ships no `testspeed` binary (plan U-06); a Python-loop equivalent on 20 free boxes plus an actuated hinge with random control: 14984 steps/s, 30 times real time, mean 79.9 contacts, 65.5 MB ([speed.json](../../../benchmarks/reports/20261101/speed.json)). An earlier record gave 8096 steps/s while the shared laptop was busier |

## 7. Deviations

| Deviation | Reason | Recorded in |
|---|---|---|
| X1.1 ran AI4R with `AI4R_LOCAL_RESEARCH=0` | The compose default's local-research capture fails on a fresh volume without an imported public dataset; X1.1 needs only the app, its route and one governed call | RUN-x11-20261101; TASKS §6 Q-08 |
| X1.1 signed in with a personal Free account, not the team account | The AI4Research workspace disallows device-code sign-in | TASKS §6 Q-09 |
| IF-001@r1 details fixed by the implementation (3 operations, 15 error codes, optional fields, content-derived `experiment_id` assigned by `bind`) | The field table leaves exact schemas to this TASK; all additive within r1 | TASK §5 A3; contracts/ |
| Analyze findings A1 (`tolerance` on checks) and A2 (check-group assignment) applied | Owner approval 2026-10-31 | TASK §5 A1; plan r2 |
| The full campaign runs inside check groups `benchmark` and `all` | AC-018 requires the benches to pass in the groups | tasks.md, state.md |
| Speed record by a Python loop, not `testspeed` | No binary in the wheel (U-06) | RUN-bench-20261101 |
| No AI4R change | ARCH "AI4R connection" and coding prompt (TASKS §6 C-05) | — |

## 8. Retained failures and negative controls

- **Failures kept:** X1.1 attempt 1 (AI4R startup capture), run 1 (tool used an invented session ID; fixed by creating the conversation first), run 2 (model entitlement); the first container `core` run (86 of 88: import check needed a repository; fixed with a static fallback); development bench runs before freezing (socket path length, a missing `gravity` field, two oracle definition mismatches). All are in evidence or `.test_logs/` and listed in the [snapshot](../verification/20261101/README.md).
- **Negative controls:** every check group exits 124 on a 5 s timeout and exits 2 on a source change made during the run, naming the changed file; the TB-06 frozen and over-damped simulations and the TB-08 gravity-off stack are caught by their oracles (3 variants, 9 cells); SIMLAB's own planted controls are caught (a wrong known-answer expectation marks its measurement invalid; a changed seed differs; tampered traces become `corrupted_record`; a planted AI4R import fails the import check; a planted credential never reaches a worker).

## 9. Blocked items with reasons

| Item | Reason | Owner action |
|---|---|---|
| X1.1 / AC-001 | AI4R's route needs `gpt-6.1-sol`; the signed-in Free account has `gpt-6-luna`, `gpt-5.6-terra` and `gpt-5.6-luna` only; the team workspace blocks device-code sign-in | Ask the AI4Research workspace admin to enable device-code authentication for Codex, or sign in with an entitled plan; then the agent reruns V-X1.1 (about 3 minutes) |
| X1.2 / AC-010 | Tolerances marked [confirm] (TB-01 source value; TB-03 to TB-08 proposals above) | Confirm or change them; a changed value is re-frozen in a new release and its cases rerun |
| X1.6 / AC-017 | No commit contains the SIMLAB code (owner: no commits) | Commit when ready; then `python tools/fresh_checkout.py --commit <sha> --run <run_id> --output …` |
| Phase 2 inputs (not phase 1 blockers) | Fit2Form code and data (Q-03); AI4R local-research dataset (Q-08); coding prompt versus r0.4.3 on AI4R patches (C-05) | Before phase 2 |

## 10. Capability gaps

None recorded in phase 1: no requested change needed a core edit. Phase 1 registry `missing` entries are planned work for later TASKs (numerical engine, libraries, models under test, preview and pilot, fresh replication, pause, resume and stream, whole-state checkpoints with controllers, memory and model-call history).

## 11. Limitations

- **Same machine and build only.** Replay and checkpoint identity are claimed for the same host, CPU model and build. Cross-machine agreement is M2. The fresh-build rehearsal still reproduced bit for bit with a different image ID and the same build identity.
- **Component measurements are not recomputed.** Custom (component) measurements are not independently recomputed; the recomputation check reports `not_run` for them.
- **Confinement by layer.** Seccomp blocks sockets and process creation in workers at the kernel. File reads are refused and recorded at the Python level. The runner container holds no credential files, and phase 1 adds no filesystem sandbox (no Landlock).
- **Image-build compute rows.** These record host-side wall time and WSL VM memory, not BuildKit CPU (Convergence T077).
- **Clock jump.** The WSL clock jumped forward about 16.6 hours during the session, after the host slept. Durations come from monotonic clocks; wall timestamps recorded before the jump lag real time.
- **Shared laptop.** Speed and wall-time figures vary with the other sessions running on this laptop.
- **Port audit with AI4R up.** The audit with AI4R running beside the simulator waits for the X1.1 rerun (Convergence T076).

## System contribution (for PAS-M1-SYSTEM)

On the integrated candidate, rerun: `python tools/check_groups.py --group all` (V-X1.2; includes the frozen F1 and F5 campaign), the runner port audit during a run (V-ALWAYS), and `tests/boundary/test_x15_replay_branch.py` (V-X1.5), as tasks.md T068 records.

## Owner approval

Pending. The owner has not reviewed or approved this report. The agent cannot approve it. Approval does not replace the three owner actions in section 9.

## Compute summary

From [`compute-log.csv`](../compute-log.csv) (224 rows, one per run; snapshot copy in `verification/20261101/`) and the evidence records. GPU memory stayed at 0 MiB throughout: phase 1 MuJoCo runs on the CPU.

| Category | Runs | Wall time (s) | CPU (s) | Peak memory (MB) | Disk written (MB) |
|---|---|---|---|---|---|
| Image builds (SIMLAB 3, AI4R 1) and fresh-checkout rehearsals (2) | 6 | 1221 | not measured (BuildKit runs in Docker's VM; T077) | 5297 WSL VM, during the AI4R build | 174 per SIMLAB image; AI4R image 977 MB compressed |
| X1.1 feasibility runs (AI4R plus simulator plus one request) | 2 | 210 | 191 (simulator) | 4296 WSL VM; AI4R container 530; simulator 48 | 0 |
| Check groups (4 groups on 2 builds, 6 negative controls, 2 development runs) | 16 | 1821 | 1699 (container cgroups) | 419 (cgroup peak, cap 4096) | 0.5 of evidence |
| Bench campaign cells (2 campaigns, 99 cells each; plus in-group campaigns inside the check-group rows) | 198 | 529 | 109 (SIMLAB run records) | 120 (per run) | 57 in the store |
| Bench totals and speed records | 2 | 324 | 2 | 64 | 80 raw evidence (data directory) |
| **Total measured** | **224** | **about 3780 (63 min)** | **about 2000 measured** | **5297 WSL VM peak** | **about 1.2 GB including images** |

**Heaviest runs:**
1. The AI4R image build, 968 s, with the WSL VM at 5297 of 5924 MB, 627 MB minimum available and 2048 of 2048 MB swap.
2. Check group `all` with the in-group campaign, 420 s, 419 MB.
3. The first F1 and F5 campaign, 322 s.
4. Check group `benchmark`, 264 s.
5. Check group `core`, 151 to 219 s, about 300 MB.

**Against the laptop limits:**
- *6 GB WSL (shared with Docker):* only the AI4R image build came close, at 89% with swap full. With AI4R and the simulator running together during X1.1, the VM peaked at 4.3 GB and 1.6 GB stayed free. That is the A-13 measurement: the pair fits.
- *Other SIMLAB work:* check groups and campaigns never exceeded 0.42 GB, and the 4 GB check-group cap ([confirm]) was never approached.
- *GPU (6 GB):* unused, 0 MiB.
- *Background load:* about 2.3 GB of WSL memory was held throughout by the owner's other Claude Code and Codex sessions, and is included in the VM figures above.
