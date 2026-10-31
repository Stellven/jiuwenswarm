# SIMLAB benchmark and test plan

**Verification · r0.4.1 · October 30, 2026.** How SIMLAB is proven: test benches with known answers, SIMLAB's own benchmark families, official external benchmarks, what each phase tests, and the reports. Exit IDs refer to [Architecture Main](../Architecture_main_body/Architecture_main_body.md).

## Rules

The team's `VERIFICATION.md` applies (levels BLOCK, BOUNDARY, SYSTEM; results PASS, FAIL, BLOCKED, NOT_RUN, STALE, N/A). The team's benchmark requirements v0.12 apply: each case declares objective, inputs, grading and primary metric first (B01); feasible and invalid cases are reported separately (B02); development and held-out cases are separated (B03); an independent oracle grades (B05); failed runs are kept (B08); expected outcomes stay hidden from the builder and AI4R (B12); a hardware inventory precedes each run (B17); three variants per family and three repeats where applicable; results per family, never one weighted score. A benchmark is never graded by the builder or by the model family that built it. Milestone M1 evidence, including SYSTEM evidence, comes from the local workstation. Exact replay is expected only on the same machine and build; comparisons across machines (in M2) or on GPUs use declared tolerances.

## Test benches (known answers)

Each case freezes its model assumptions, initial conditions, measurement definition, horizon and tolerance before it runs; tolerances are [confirm] values. Each case reports its measured error, not only pass or fail.

| ID | Case | Known answer | Phase |
|---|---|---|---|
| TB-01 | Pendulum, small and large swing | 2π√(L/g); elliptic-integral period (0.5%) | 1 |
| TB-02 | Free fall | ½gt² (0.1%) | 1 |
| TB-03 | Block on an incline | Slides when tan θ > μ; a = g(sin θ − μ cos θ) | 1 |
| TB-04 | 1D collisions | Momentum conserved; restitution sets the ratio of relative normal velocities | 1 |
| TB-05 | Damped oscillator | Closed-form decay and frequency | 1 |
| TB-06 | Passive double pendulum | Energy error stays bounded and the motion matches a high-accuracy reference over a short horizon (a frozen or over-damped simulation fails) | 1 |
| TB-07 | Rolling without slipping | a = g sin θ / (1 + I/mr²) | 1 |
| TB-08 | Box stack at rest | Stays still with contact forces balancing gravity (a stack with gravity off fails); penetration bounded | 1 |
| TB-09 | Determinism and checkpoint restore | Identical results; restore-and-continue equals the uninterrupted run | 1 |
| TB-10 | ODEs with closed forms; pendulum in both engines | Closed form for each engine; agreement between engines is corroboration, not a substitute for the analytic answer | 3 |
| TB-11 | Motor step response; actuator delay | Time constant; lag equals the declared delay | 3 |
| TB-12 | Coaxial magnets; hover thrust | 3μ₀m₁m₂/(2πr⁴), acting on the other body; thrust equals weight | 3 |
| TB-13 | Cantilever; hanging cable | FL³/(3EI); catenary sag | 3 |
| TB-14 | LQR on a double integrator | Riccati gain | 3 |
| TB-15 | Released policy adapter | On recorded inputs, its preprocessing, state, outputs and action transforms match the released runtime. Its task performance is a benchmark result, not a pass condition | 3 |
| TB-16 | World-model scoring code | Physics-as-predictor scores zero error; a biased predictor scores its known bias. This checks the scoring, not any real model's quality | 3 |
| TB-17 | Model timing; memory restore | Actions apply when each timing mode says; memory restores identically | 3 |

## SIMLAB-Bench families

| Family | Tests | Oracle | Phase |
|---|---|---|---|
| F1 Known-answer physics | The test benches, frozen as cases | Analytic formulas | 1, 3 |
| F2 Reproduction | First demonstration against the authors' code | Reference code run separately | 2 |
| F3 Planted defects | Wrong units, hollow collision shapes, unstable steps, tampered measurements, changed predicates, ambiguous protocols, hidden grasp welds, repeats with nothing random; each paired with a clean control | The expected finding per defect; clean controls pass; false alarms are reported | 2 |
| F4 Hypothesis cases | Register hypotheses with analytic anchors | Analytic predictions plus an independent implementation | 2 (development), 5 (a separate held-out set never used during development) |
| F5 Agreement | Replay; MuJoCo vs numerical; x86 vs arm64 in M2 | Identity or tolerance | 1–3 |
| F6 Operations | Crash and resume, pause, cancel, limits, timeout and source-change negative controls | Expected statuses and exit codes | 4 |
| F7 Follow-up construction | An experiment plus a scripted next question (new sensor, new objects, an intervention, a model-in-the-loop controller, a branch from a checkpoint) | The follow-up runs, the core is unchanged, and the required changes are present | 2, 4 |
| F8 Models in the loop | Timing modes, budgets, fallbacks, replay, fresh replication | Expected call logs and timings | 3 |
| F9 World models | Evaluation correctness; labeled previews; error against physics | Identity and biased predictors; physics rollouts | 3 |
| F10 Feasibility honesty | Missing weights or code, unverifiable compatibility | Affected arms BLOCKED with the right reason; "ran" or a proxy fails | 2 |

Cases live in `labs/physicalai_sim/benchmarks/` and follow the format of the team's Harbor suite (`benchmarks/harbor_suite/`): `case.json`, an independent `oracle.py`, visible and referee files, frozen releases with SHA-256 manifests, `smoke` and `campaign` profiles, no retries, held-out cases on a private volume, and dated report folders under `labs/physicalai_sim/benchmarks/reports/` with no aggregate score.

## Official external benchmarks

Checked October 30, 2026. The full catalogue, with versions, licenses, sources and rejected candidates, is kept beside this plan as `official-benchmarks-catalogue.md`.

| Adopt | Use in SIMLAB | Phase |
|---|---|---|
| MuJoCo's own engine tests; Drake's inclined-plane and friction tests; the seven analytic tests of arXiv 2603.14634; ContactBench's contact criteria | Patterns and formulas for the test benches; rerun on every MuJoCo upgrade | 1 |
| MuJoCo state and batch API (`mj_getState`, 3.17 batch runs) | Determinism, replay and checkpoint tests | 1 |
| MuJoCo `testspeed`; later MuJoCo Warp benchmarks | Speed and cost records | 1, 4 |
| MuJoCo Menagerie, YCB, Google Scanned Objects | Robots, grippers and objects for the builder (licenses per item) | 2 |
| DeepMind Control Suite, Gymnasium MuJoCo v5 | Well-known scenes for early experiments and frozen policies | 2 |
| PyElastica validation cases; MuJoCo `CantileverIntoCircle` | Independent references for the flexible-parts library | 3 |
| ContactNets cube toss and Acosta et al. impacts (real data, BSD-3) | Simulation against reality; a ready first research run | 3, 5 |
| LIBERO (Hugging Face fork) with LIBERO-PRO and LIBERO-Plus, π0.5 through LeRobot or openpi | First released vision-language-action model in the loop | M2 (needs the Spark) |
| Law-governed videos and rollouts generated by SIMLAB (PhyWorld style); Physics-IQ for large video models | World-model evaluation | 3, 5; Physics-IQ in M2 |
| Drake (arm64 wheels) | A second engine with a different contact model for cross-checks | 3 |
| NewtonBench; the creation-and-audit loop of Gym-Anything for Robotics (arXiv 2610.40565) | Builder and research-agent evaluation design | 2, 4 |

**Constraints found:**

- **Isaac Sim** is not admitted for the M1 laptop, because its published minimum is an RTX 4080-class GPU. It is officially supported on the DGX Spark. Isaac Lab 3.0 can run headless on Newton without RTX hardware.
- **ManiSkill3** runs CPU-only under WSL, without GPU simulation or rendering, so it and the benchmarks built on it are references only in M1.
- **Vision-language-action models** are admitted per checkpoint, task and runtime. π0.5 through openpi needs more than 8 GB of GPU memory, so it waits for M2. Smaller ones such as SmolVLA are designed to run on a CPU, but whether one fits a given task beside AI4R on the laptop must be checked.
- **Licenses:** the MIT Push dataset, RLBench and 1X raw video are non-commercial.
- **Saturated or frozen:** LIBERO alone is saturated (use its PRO and Plus variants), CORE-Bench Hard is solved, and MLE-bench is frozen.
- **A gap SIMLAB could fill:** no MuJoCo-native benchmark exists for memory across episodes.

## What each phase tests

| Phase | BLOCK | BOUNDARY | SYSTEM | Families |
|---|---|---|---|---|
| 1 | Schemas, statuses, measurements, typed errors | Local feasibility (X1.1); TB-01 to TB-09 through the tools; clean controls (X1.3); agent-only use (X1.4); replay, save and branch, fresh-checkout reproduction (X1.5) | | F1, F5 |
| 2 | Builder tools and halts; feasibility inspection | Authors' code (X2.1); builder rebuild (X2.2); defects with clean controls (X2.3); honesty (X2.4); follow-up (X2.5) | Thin AI4R connection (X2.6) | F2, F3, F4, F5, F7, F10 |
| 3 | Library units; TB-16 and TB-17 machinery | TB-10 to TB-15; interacting components and three libraries in one scene (X3.2); a real model (X3.3); a real world model (X3.4) | | F1, F5, F8, F9 |
| 4 | Concurrency, resume and checkpoint units | Payload compatibility; negative controls | X4.1 to X4.5 on the workstation | F6, F7 |
| 5 | | | X5.1, X5.2 | F4 (held-out set) |

Always: no network from executors, and no host port besides 5175.

## Reports and evidence

- **Per check:** `evidence/RUN-ID.md` per the Spec Kit evidence template, linked from tasks.md (not committed).
- **Check-group runs:** `.test_logs/simlab/<group>/<run>/` with `launch.json`, `source-manifest.json`, `pytest.log`, `junit.xml`, `result.json` (not committed).
- **Phase exit snapshot:** `labs/physicalai_sim/missions/PAS-M1/verification/YYYYMMDD/`, with failures kept beside passes (committed byte-exact).
- **Phase report:** `missions/PAS-M1/reports/PAS-M1_Phase<n>_Completion_Report.md`: scope and exits; commit, images and hardware; results per exit linked to evidence; test bench errors; results per benchmark family; official benchmark results; deviations; retained failures and negative controls; blocked items with reasons; capability gaps; limitations; owner approval.
- **Final report:** `missions/PAS-M1/reports/PAS-M1_Final_Test_Report.md`, the authoritative summary across phases.

Reports summarize evidence; they never replace it.

## Check groups

Groups `core`, `executors`, `libraries`, `models`, `builder`, `benchmark`, `operations` and `all`, one command each, following `deploy/m1/capsule_checks.py`. Checks run in a container with no network, a [confirm: 4 GB] memory cap and a read-only source mount. A source change during a run gives exit 2 and a timeout exit 124; each group has these negative controls. Live or model-dependent tests are opt-in and otherwise skipped, never passed with mocks.
