# Benchmark guide for the team

Date: 2026-10-02. Owner: Saurav. Derived from `D:\Huawei\Benchmark\reports\Experiment design v5.md` (the full design; v4 and earlier are superseded). v5's eight simplifications are tagged SIMP-1 to SIMP-8 there and are PROPOSED; the team can reject any one. Metric definitions: `D:\Huawei\Benchmark\reports\Metrics that prove our contributions.md`.

**How to read this.** Read section 0, then your own section, then sections 5 and 6. Items marked **DECIDED** are Saurav's decisions and still need team review. Everything else is **PROPOSED**. Nothing here changes a number in the full design. If they disagree, the full design wins.

**Two naming traps.**
- Router metric codes **M1–M6** are not product milestones M1/M2.
- Measurement points are **T0–T2**. They are not milestones either (see 0.4).

---

## 0. One page for everyone

### 0.1 Our hypothesis

**DECIDED (2026-10-02): the main hypothesis is tested on a four-rung ladder, all on one base model, `gpt-6.1-sol` ("Sol").** Capsules are built into AI4Research, so they cannot be switched off on their own. The only way to remove them is to remove the whole platform, which means running stock openJiuwen.

| # | Rung | What it is | The step up to it tests |
|---|---|---|---|
| 1 | **H0** Codex CLI | Stock Codex CLI, same prompt, caps and sandbox | Reference: a standard harness |
| 2 | **B1** stock openJiuwen | Pinned commit, default config, never modified | The platform we build on |
| 3 | **B2-fixed** AI4Research, fixed model | Capsules + planner + gate, every call to Sol | 2→3: the effect of **"our platform"** (capsules, planner and gate together) |
| 4 | **B2** AI4Research + router | Rung 3 with the router on | 3→4: whether the router **holds accuracy** and **cuts cost**, with the stage breakdown |

**We hypothesise** that, on the same model, AI4Research solves more held-out tasks than stock openJiuwen and than Codex CLI, and that the router keeps that accuracy at lower cost.
- **The test passes if**, on ScienceAgentBench held-out (82 tasks × 3 seeds), B2 exceeds B1 by ≥ +10 percentage points at Holm-corrected p < 0.05 (Holm = a correction for testing several comparisons at once), and B2 exceeds H0 at Holm p < 0.05 with a positive estimate.
- **Router step passes if** the lower 95% bound of the accuracy change (rung 3 → 4) is above −10 pp (a non-inferiority test) **and** virtual cost falls by ≥ 30% with the interval excluding 0.
- **It fails** if any of these bounds is missed. MLE-bench and per-domain results are descriptive: no pass/fail, only "same sign on a majority of competitions".
- B0 (plain agent-core ReAct) is an optional diagnostic.

**Secondary toggles (SIMP-1, PROPOSED): exactly two, both on ScienceAgentBench, inside rung 3 (B2-fixed):**

| Toggle | Owner | What it corroborates | Points |
|---|---|---|---|
| S1 Gate off | Ramika | Verifier's end-to-end effect | T1, T2 |
| S2 Library v0 vs vN | Saurav | RSI's end-to-end effect | T1 (v0 vs v1), T2 (v0 vs vN) |

Both are descriptive (no pass/fail). Router baselines such as forced-cheapest and Always-Mid stay in the offline evaluator only.

**What each slide tests (one hypothesis per slide).**

| Slide | We hypothesise that... | The test passes if... |
|---|---|---|
| 1. Ladder per domain | AI4Research solves more held-out tasks than stock openJiuwen and Codex CLI on Sol | B2 − B1 ≥ +10 pp at Holm p < 0.05; B2 − H0 positive at Holm p < 0.05. Per-domain and GIS-control rows are descriptive |
| 2. Capsules | The platform step comes from capsule-covered domains, and hand capsules don't silently rot | B2-fixed − B1 ≥ +10 pp at Holm p < 0.05; median sealed-suite conformance ≥ 0.9 (shown beside the Codex-built tools' median); covered-vs-GIS gap and unplanned-exception rate reported |
| 3. Verifier | Our verifier passes fewer planted defects than a zero-shot judge on Sol, without more false fails | False-pass upper 95% bound < 0.20 (well under the 0.45 cliff, margin shown); ≥ 10 pp below the zero-shot judge at p < 0.05; false-fail not worse by > 5 pp. First-failing-node accuracy and gate-off toggle are descriptive |
| 4. RSI | RSI children beat their parents on never-queried final sets, with no regressions or cheating | Zero losses and Beta lower bound > 0.5 on ≥ 3 capsules; 0 regressions; 0 referee accesses. Curves, dev-final gap, v0 vs vN and hygiene are descriptive; the math → psychology stretch is reported with a bootstrap interval, no p-value |
| 5. Router | The router keeps accuracy and cuts cost | Accuracy lower bound > −10 pp and cost −30% or better; offline cost saved at matched accuracy ≥ 30% (interval above 0) and quality curve above the Zero-router line |
| 6. Process | Agents author a measurable share of our own build | Descriptive only; no pass/fail threshold is set |

### 0.2 Domains

**DECIDED:** bioinformatics, chemistry, psychology, math/physics.
- **GIS runs as a silent control.** It gets no hand capsules. If capsules really cause the gain, the stock → AI4Research-fixed step should show up in the four domains and not in GIS.
- Coding is not a domain. It appears only as the router's Coder slice (LiveCodeBench).

### 0.3 The running benchmarks and the offline router sets

| Benchmark | What it is for | Size and runs |
|---|---|---|
| **ScienceAgentBench** (SAB), verified split | Where **statistical significance** is reached; hosts the ladder and both toggles | 20 dev tasks (ours to tune on), 82 held-out × 3 seeds |
| **MLE-bench** Lite, bio/chem | **Headline end-to-end** result (descriptive) and the **RSI curves** | Five core competitions: nomad2018, leaf-classification, plant-pathology-2020, mlsp-2013-birds, right-whale-redux. **2 seeds**, one Spot L4 VM. B1 once (T1); B2 at T1 and T2; H0 once (T2). RSI dev: paddy, plant-seedlings, invasive-species (if fixed) |
| **SciCode** math/physics | The math/physics domain | Dev = official 15; held-out ≈ 40 main / 170 subproblems; metric: subproblem pass rate |
| Router offline sets | Router tuning at $0 | LLMRouterBench cached outputs (GPQA, MMLU-Pro, LiveCodeBench), seven baselines, at T0. ~200-item live pass over Cedric's pool **once at T1**, ~$26 |
| PaperBench **JudgeEval** only | Verifier calibration | One-time, ~$40, no agent runs; may move to T2 |

**MLE-bench caveats (SIMP-3).** With 2 seeds, per-competition intervals are ~1.22× wider and barely informative, so per-competition bars show both seed values. There is no B2-fixed on MLE-bench, so **the router step is not isolated there**: MLE-bench shows only B1 → B2 and H0 → B2. The platform and router steps are tested on SAB and SciCode.

**DECIDED:** the harness wraps every rung the same way. All model calls go through a **logging proxy** on the harness side that records model served, tokens, latency and cost. Stock openJiuwen is never modified; only its base URL points at the proxy.

### 0.4 Measurement points and cost

**DECIDED:** the benchmark has its own specification, separate from the product PRD. Measurement points are decoupled from product milestones, and each is labelled with the product stages it includes. **SIMP-2 (PROPOSED): three points.** Week 0 = 2026-10-05; dates are placeholders.

| Point | Week (date) | What runs (short) | Rough cost |
|---|---|---|---|
| Smoke | weekly from wk 2 | 10 SAB dev tasks, 1 MLE dev competition at 1–2 h on Spot | ~$2–3 each |
| **T0 baseline** | wk 3 (≈ 2026-10-26) | Needs no product tool execution: Codex CLI on SAB and SciCode, H-ref, router offline, JudgeEval (or at T2), component suites. First SAB ladder only if the runtime is ready | ~$88–113 (+$13–28 if the first ladder runs) |
| **T1 mid-term** | wk 9 (≈ 2026-12-07) | SAB ladder + S1, S2 (v0 vs v1); SciCode ladder; MLE B1 + B2 + RSI round 1; live router pass; verifier on the SAB node | ~$112–132 |
| **T2 final** | wk 15–16 (≈ 2027-01-18) | SAB B2-fixed, B2, S1, S2 (v0 vs vN); SciCode; MLE B2 + H0 + RSI round 2; RSI stretch | ~$86–101 (+$40 if JudgeEval deferred) |

Term ≈ **$320–430**, including smoke and the H-ref run (SAB's reference scaffold on Sol). Every point is under $150. GPU ≈ **300 GPU-hours** (~$155 on Spot).

### 0.5 Setup at a glance (our estimates)

- **Who builds the harness.** Saurav builds the whole benchmark harness (section 3). The other modules only need to expose the interfaces listed in their sections.
- **Critical path.** About **2–2.5 weeks** of harness work to T0. The MLE-bench adapter is off the T0 path (MLE-bench first runs at T1). **T1 gate:** Codex tool execution and the two product hooks by **week 7**.
- **Hardware.** **One Spot L4 VM** for MLE-bench with checkpoint/resume (no quota request expected; verify). A separate CPU machine for SAB and SciCode. MLE data is small (each core competition < 0.3 GB or small).
- **Accounts.** Codex: **~395–690 agent-hours per term**. One seat may suffice **only if it allows ~3 concurrent sessions and ~250–350 agent-hours a week**; measure at T0, add a second seat for T1/T2 if not. An OpenAI key for graders. Keys for the router pool (no Anthropic). Kaggle with rules accepted for 7–8 competitions. A Hugging Face token. A GCP project and bucket.
- **Licences to clear.** Kaggle non-commercial rules, HyperAgents (borrow the protocol, not the code), GPQA, SAB upstream licences.

### 0.6 What we ask from the product (two hooks and the call tags)

1. **Headless entry with a non-interactive halt.** Run one task with no browser. When a gate fails, it records the failure and exits instead of opening a `human_session`.
2. **Components assembled from config.** The harness sets router, gate and library version, and pins the library by hash.

Both run in an **evaluation-mode lane** whose sandbox matches Codex CLI's (PROPOSED). **Model-call tags:** in evaluation mode every call carries `run_id, task_id, seed, obs_id, capsule_name, decl_hash, step_id, role, model_requested, effort, fallback, attempt` in headers or metadata, **never inside the prompt**. A single model-calling abstraction is the only path to a model. Muk is building it.

---

## 1. Muk: capability capsules and planner

> **Your summary (Muk)**
> - The benchmark tests whether your capsules and planner work, and whether they raise held-out success.
> - Hypothesis you test: hand capsules don't silently rot, and the platform step lifts success. Decided by median sealed-suite conformance ≥ 0.9 (beside Codex-built tools) and stock → AI4Research-fixed ≥ +10 pp.
> - Also reported: that gain in capsule domains vs the GIS control (descriptive).
> - Tests: your capsule fixture suite and sealed suites; ScienceAgentBench and MLE-bench held-out sets.
> - The benchmark needs from you: capsule declarations with hashes, and fixture DAGs for the M1 golden requests (T0 ≈ wk 3).
> - The benchmark needs from you: the hand-authored capsules, 3–5 per domain (bio/chem by T1 ≈ wk 9, psych/math by T2 ≈ wk 15–16).
> - The benchmark needs from you: the single model-calling path carrying the evaluation tags (by week 7).
> - Tune on the 20 dev tasks; rerun the fixture suite on every capsule change.
> - Rule: never open held-out tasks; capsules are hashed and frozen before any held-out run.

### What is measured

| Code | Plain name | One line | Test that supplies it |
|---|---|---|---|
| C1 | Sealed-suite conformance and silent rot | Share of hidden test inputs each capsule gets right; rot = capsules scoring 0 | Sealed suites (written before the build) |
| C3 | Held-out success | Pass rate on tasks never seen in tuning; your gain is the stock → AI4Research-fixed step | SAB 82 held-out, MLE-bench held-out |
| C4a / C4b | Plan validity / plan-conditional success | Share of "ready" plans that are really runnable / share of those that succeed | Fixture suite on the M1 golden requests |
| C5 | Node/edge F1 vs fixture DAG | How closely the plan's steps and links match the reference plan | Fixture suite |
| C7 | Unplanned-exception rate | Errors that are neither declared failure modes nor predicted stops | Fixture suite |
| C8 | Predicted-abort precision/recall | Do aborts land on the planted bad combinations, and only there | Fixture suite (Planner Phase 2) |
| C9 | Postcondition violations | "OK" results that fail their own checks, or effects outside the declared ones | Fixture suite |
| C10 | Plan-vs-run catch ratio | Share of problems caught at plan time rather than at run time | Fixture suite (Phase 2) |
| C2 | Library-size drop and shadowing | Does a bigger library do worse; do skills hide each other | SkillsBench Core at Phase 2 (PROPOSED) |
| C6 | Growth curve | Pass rate as the library grows | Fixture suite, later rounds |

C1 target: median conformance ≥ 0.9, reported beside the Codex-built tools' median.

### The hand-authored capsules (PROPOSED families)

They are **library v0**. 3–5 per domain (12–20 in all); bio/chem frozen by T1, psych/math by T2.
- **Bio:** scanpy/AnnData, scvi-tools, omics figure checks, **bio image classifier** (shared with MLE-bench), optional bioacoustic detector.
- **Chem:** deepchem MolNet, RDKit descriptors, DeepPurpose, **materials featurisation + gradient-boosted trees** (shared with nomad2018), molecule visualisation.
- **Psych:** BioPsyKit, **NeuroKit**, **cogsci-jnmf**, **syllogistic-nvc**.
- **Math/physics:** linear algebra with residual checks, ODE/PDE integrators, quantum operators, seeded Monte Carlo, units checker.
- **Tabular featurisation + cross-validation for tiny data** is the strongest SAB/MLE overlap.

**Anti-leakage rules (pre-registered).** You see dev tasks only (SAB dev, MLE dev, SciCode dev, library docs). Capsules are hashed and frozen before any held-out run. Saurav runs a similarity audit against held-out gold programs and top Kaggle kernels (MLE-bench's 60% rule); exclusions are fixed before results are seen.

**Where the capsule evidence comes from.** Capsules cannot be switched off, so the evidence is (1) the fixture suite: sealed-suite conformance against tools Codex CLI builds from the same spec, plan validity and unplanned exceptions; and (2) the stock → AI4Research-fixed step in capsule-covered domains vs the GIS control.

### How to tune
- Run the fixture suite locally on every capsule change. Watch C1 and C7 first.
- Use the **20 SAB dev tasks**. Never open the 82 held-out tasks.

### What the benchmark needs from your module
- **Capsule declarations with hashes.** The library is pinned by hash for every run, so results are reproducible and leakage audits can be checked. Needed from T0.
- **Sealed admission suites per capsule,** authored by someone other than the capsule's builder. They give the conformance number and act as the RSI referee. Needed from T0 for the first capsules. Saurav or Ramika author them; Saurav can build the suite runner on the harness side.
- **The hand-authored capsules, 3–5 per domain.** They are library v0, the subject of the platform step and the parents for RSI. Bio/chem by T1, psych/math by T2.
- **Fixture DAGs for the M1 golden requests.** The reference plans used for plan validity, node/edge match and unplanned exceptions. Needed by T0 (C1) and T1 (the rest). Saurav can build the fixture runner on the harness side if you prefer.
- **The single model-calling path with evaluation tags (0.6).** The logging proxy can only attribute cost and routing per capsule and step if every call goes through one path with tags. Needed by week 7 for T1.

---

## 2. Ramika: verifier

> **Your summary (Ramika)**
> - The benchmark measures how often your verifier lets broken results through, and how often it fails good ones.
> - Hypothesis you test: our verifier passes fewer planted defects than a zero-shot judge, without more false fails. Decided by the false-pass upper 95% bound (passes if < 0.20 and ≥ 10 pp below the zero-shot judge; PROPOSED 0.10 for "calibrated"; 0.45 cliff shown).
> - Also: agreement with human labels on JudgeEval, first-failing-node accuracy, and the gate-off toggle.
> - Tests: the planted-defect audit set (≥ 100 fails per node type), PaperBench JudgeEval, MLE-bench archived candidates.
> - The benchmark needs from you: a stable verdict shape (pass/fail/unknown, reasons) and a decision on the confidence field (T0 ≈ wk 3).
> - The benchmark needs from you: labelled expected-pass/expected-fail cases where you are the domain expert (capsule node by T0, SAB program node by T1 ≈ wk 9).
> - The benchmark needs from you: the two product hooks and the evaluation lane written into the PRD (by week 7).
> - Tune: rerun the audit set on every judge-prompt change; report false-pass and false-fail together.
> - Rule: JudgeEval material never reaches the agent, the capsule library or RSI.

### What is measured

| Code | Plain name | One line | Test that supplies it |
|---|---|---|---|
| V1 | False-pass rate | Share of planted defects the verifier lets through | Your planted-defect audit set |
| V2 | False-fail rate | Share of clean outputs it wrongly fails | Same audit set |
| V3 | F1 / kappa vs humans | Agreement with human labels, corrected for chance | **PaperBench JudgeEval** |
| V4 | Coverage and selective accuracy | How often it decides, and how right it is when it does | Audit set |
| V5 | Consistency | Flip on answer-order swap, same verdict on reruns, bias toward its own model | Audit set, 3 runs |
| V6 | Gate false-accepts, first-failing-node accuracy, best-of-N gain | Bad children admitted; does the first fail land on the broken step; gain from picking by verdict | MLE-bench archived candidates |
| S1 | Gate-off toggle | SAB success with the gate always passing, vs rung 3 | SAB, T1 and T2, descriptive |

**Audit set size.** At least 100 fails (plus ≥ 40 clean) per node type: the M1 capsule node at T0, the SAB program node at T1.

**Thresholds.**
- **The 0.45 cliff.** Above a 0.45 false-pass rate a judge can no longer retire bad skills, at any sample size (Blind Curator).
- **PROPOSED:** a judge counts as calibrated only when the upper 95% bound of its false-pass rate is below **0.10**.
- **H-V target:** upper bound < 0.20; ≥ 10 points below a zero-shot judge on Sol; false-fail not worse by more than 5 points.
- **JudgeEval go/no-go:** any judge used for scoring needs F1 ≥ 0.80.

### How to tune
- Run the audit set on every judge-prompt change.
- Always report false-pass and false-fail together.
- **Never let JudgeEval artefacts reach the agent, the capsule library or RSI.**

**Open item.** The verdict has no `confidence` field. Calibration error and Brier score (part of V4) wait on that decision.

### What the benchmark needs from your module
- **The verdict shape:** pass / fail / unknown, with reasons, and a decision on the `confidence` field. Every verifier metric is computed from verdicts, and calibration metrics need the confidence field. Needed by T0.
- **`verifier_audit` and `negative_control` records.** They let the harness log false-pass and false-fail per dataset without parsing free text. Needed by T0. Saurav can build this on the harness side if you prefer.
- **Labelled expected-pass / expected-fail cases** for the audit set, where you are the domain expert. Labels decide what counts as a false pass. Capsule node by T0, SAB program node by T1. Saurav builds the mutation tooling and the JudgeEval harness around your verifier.
- **The two product hooks and the evaluation lane in the PRD (0.6).** Without them no unattended run can halt cleanly or match Codex CLI's sandbox. Needed by week 7 for T1.

---

## 3. Saurav: RSI engine

> **Your summary (Saurav)**
> - The benchmark measures whether RSI improves capsules on tests it never saw, with no regressions and no cheating.
> - Hypothesis you test: RSI children beat their parents on never-queried final sets. Decided by final-set gain with a lower bound: passes if zero losses and Beta lower bound > 0.5 on ≥ 3 capsules, with 0 regressions.
> - Also: score-vs-iteration curves and the dev-final gap from MLE-bench; library v0 vs vN on SAB; hygiene at zero.
> - Tests: RSI attempt log and capsule fixtures; MLE-bench candidates regraded offline; sealed suites as referee for the stretch.
> - I build for T0 (≈ wk 3): split script, SAB and SciCode adapters, Codex CLI wrapper, archive and scorecard, RSI log, JudgeEval harness, offline router evaluator.
> - I build for T1 (≈ wk 9): logging proxy, MLE-bench adapter with HumanRank scorer, stock and AI4Research adapters, process scripts.
> - Week 0: GCP project and one Spot VM, Kaggle rules, SAB split published.
> - Rule: RSI tunes only on fixtures and dev splits; the referee stays sealed; held-out sets are never queried in the loop.

### What is measured

| Code | Plain name | One line | Test that supplies it |
|---|---|---|---|
| R1 | Final-set gain with lower bound | Child beats parent on a never-queried final set; accept only with zero losses and a Beta lower bound > 0.5 | Attempt log and capsule fixtures |
| R2 | Score-vs-iteration and plateau | Best-so-far score per round; when it stops improving | MLE-bench candidates regraded offline |
| R3 | Dev–final gap | Gain on tuning data minus gain on held-out; also validation vs private | MLE-bench candidates |
| R4 | Regression and rollback rate | Children rejected or reverted for breaking the parent's cases | Attempt log; MLE-bench |
| R5 | Improver improvement@k | Does improver v1 make better children than v0 on held-out improvement tasks | Stretch: math → psychology transfer |
| R6 | Hygiene bundle | Reward-hacking rate, referee canary hits (target 0), budget-stop compliance | Fixtures; MLE rule checks |
| S2 | Library v0 vs vN | SAB success of rung 3 with the hand library vs the RSI-improved one | SAB, T1 (v0 vs v1), T2 (v0 vs vN) |

H-R target: on ≥ 3 capsules, zero losses and the Beta rule met; 0 regressions; 0 referee accesses. Stretch: an improver evolved on math/physics capsules, frozen, then tested on psychology copies with planted defects, reported with C1 and the hygiene bundle.

### Rules
- RSI tunes **only** on its fixtures and dev splits. The referee is sealed. Held-out sets are never queried in the loop.
- MLE-bench curves come from **archived candidates regraded offline**.

### How to tune
- Iterate on loop fixtures and the MLE dev competitions (~$9 per round on Spot; one round at T1, one at T2). Check R3 every round.

### What I build (the whole harness)
- **By T0:** SAB split script (published and hashed); SAB adapter; SciCode adapter; Codex CLI wrapper; run archive and scorecard; RSI attempt log; JudgeEval harness (our verifier as a judge); offline router evaluator with the seven baselines; sealed-suite and fixture runners.
- **By T1:** logging proxy; MLE-bench adapter (6 h cap, checkpoint and resume, HumanRank scorer, candidate archive and regrade, Spot watchdog); stock agent-core adapter; AI4Research adapter (uses the two hooks); verifier mutation tooling; process (P1–P5) and audit-log scripts; live router pass.
- **By T2:** RSI meta_test tasks for the stretch.
- **Week 0:** GCP project and one Spot VM, Kaggle rules for 7 competitions, SAB split published.

---

## 4. Cedric: model router and dev lead

> **Your summary (Cedric)**
> - The benchmark measures whether the router keeps accuracy while cutting cost.
> - Hypothesis you test: the router keeps accuracy and cuts cost. Decided by virtual cost (passes if −30% or better) with the accuracy lower bound above −10 pp vs AI4Research-fixed; strong-call fraction by stage explains it.
> - Offline test passes if cost saved at matched accuracy ≥ 30%, compared with seven baselines including the Zero router and Always-Mid.
> - Tests: LLMRouterBench cached outputs ($0), one live pass over your pool at T1 (~$26), SAB and SciCode through the logging proxy (MLE-bench does not isolate the router step).
> - The benchmark needs from you: the router pool with tier labels (cheap, base, mid, strong) by T0 (≈ wk 3), for the offline evaluator.
> - The benchmark needs from you: per-call tags passing through the model client, and config toggles with a library hash pin (by week 7).
> - The benchmark needs from you: the headless entry with non-interactive halt and Codex tool execution by week 7. This gates T1 (≈ wk 9).
> - Rule: build routing rules from per-task wins on the dev split, never from held-out ids or aggregate leaderboards.

### What is measured

| Code | Plain name | One line | Test that supplies it |
|---|---|---|---|
| M1 | Cost saved at matched accuracy | Cost cut vs always-strongest, at its accuracy | LLMRouterBench cached ($0); live pass at T1 |
| M2 | Gain at matched budget | Accuracy gain over always-cheapest at 1× or 2× its cost | Offline sets |
| M3 | Area under the cost-quality curve | Overall quality across all thresholds | Offline sets |
| M4 | Gap to oracle | Distance to a perfect per-item picker | Offline sets |
| M5 | Strong-call fraction, by stage | Share of calls sent to the top tier | Proxy log, router step (rung 3→4) on SAB and SciCode |
| M6 | Router overhead | Extra latency and tokens the router itself costs | Proxy log |

Agent-level target (router step, rung 3→4): lower 95% bound of the accuracy change > −10 pp **and** cost −30% or better. Offline: CostSave ≥ 30% with the interval above 0; quality curve above the Zero-router line.

### The pool and baselines

**DECIDED:** the pool is your choice. It must have a cheap tier, base Sol, a mid tier at Sol's price or lower, and a strong tier above Sol. It is compared with seven baselines: always-strongest, always-cheapest, **Always-Mid**, random at matched budget, stock IntelliRouter failover, the **Zero router** line, and the per-item oracle.

**Expected shape (PROPOSED).** Cheap models save cost on the many short stages (intake, intent, requirement, plan, review, report). Strong models hold accuracy on hard builder calls. **The strong-call fraction by stage is the slide that explains it.**

### Seed examples (from `research_notes\router_niche_examples.md`)

| # | Niche | Candidate | Verify (under $5) |
|---|---|---|---|
| 1 | Bio scanpy plotting scripts | gpt-6-luna | 7 tasks × {Sol, Luna, DeepSeek Flash} × 3 seeds |
| 2 | Same, non-OpenAI hedge | gemini-3.5-flash | Only if Luna misses |
| 3 | Light chem tasks (RDKit viz, correlations) | gpt-6-luna | 5 tasks × {Sol, Luna} × 3 seeds |
| 4 | Library-free psych plotting | gpt-6-luna / glm-5.3-flash | 5 tasks + 2 controls × 3 arms × 3 seeds |
| 5 | SciCode numerical subproblems | gemini-3.5-flash, deepseek-v4.1-flash, luna | 25 dev subproblems × 4 arms |
| 6 | Coder role, short repairs | gpt-6-luna, deepseek-v4-pro | 10 SAB dev tasks, Coder forced, 2 seeds |

Keep Sol for deep-learning training pipelines, library-specific psych pipelines, long agentic loops and reviewing cheap output. **Build the library from per-task wins on the dev split, not from aggregate leaderboards.** If a seed test names held-out ids, swap them for dev ids.

### How to tune
- Run the offline evaluator on every routing-rule change.
- Check strong-call fraction by stage on dev tasks; freeze the router threshold in `spec.md` before T1.

### What the benchmark needs from your module
- **Headless entry with a non-interactive halt (hook 1).** Every AI4Research run is launched unattended; a gate failure must record and exit. Needed by week 7 for T1.
- **Config-assembled components (hook 2):** router, gate and library version as toggles, with the library pinned by hash. The ladder and both toggles are config switches on one commit. Needed by week 7.
- **The router pool and tier labels.** The offline evaluator and the cost table need to know which model is cheap, base, mid and strong, with dated prices. Needed by T0; the live pass runs at T1.
- **Per-call tags passing through the model client (0.6).** The logging proxy reads them to attribute cost and routing by stage. Needed by week 7. Saurav can build the proxy-side check on the harness side.
- **Codex tool execution timing.** T1 cannot run any AI4Research rung until it works; tell Saurav early if week 7 slips, so the API-key fallback can be costed.

---

## 5. Everyone: documents-first process metrics

| Code | Plain name | One line |
|---|---|---|
| P1 | Agent-authored share | Share of merged code written by the agent |
| P2 | Interventions per feature | Human turns after the spec hand-off, per acceptance criterion |
| P3 | Requirement coverage | Share of PRD clauses with an acceptance test, and share passed |
| P4 | Rework | Passed criteria that later break; PRs needing a fix within 7 days |
| P5 | Time-to-feature | Hours and Codex sessions from task registration to pass |

**What you do.** From your first pilot commit, mark agent authorship with a commit trailer or git-ai. Keep a tally of your human turns per session.

---

## 6. Rules for all

1. Never touch held-out task ids (SAB 82, SciCode held-out, MLE held-out).
2. Seeds are fixed.
3. Archive every run (team GCS bucket, indexed in `jiuwenswarm/docs/verify/`).
4. Pre-register thresholds in `spec.md` before the run.
5. The tracking set is frozen at T0.
6. Label each measurement point with the product stages it contains.

---

## 7. Open questions by owner

| Owner | Question | Default |
|---|---|---|
| Supervisor | Drop PaperBench from tracking? | MLE-bench is the headline; PaperBench is JudgeEval only |
| Supervisor | $150 per point | v5 keeps every point under $150; treat it as the cap |
| Team | Accept or reject each of SIMP-1 to SIMP-8 | Accept all; most worth debating: SIMP-3 (2 seeds, no MLE B2-fixed) and SIMP-2 (one fewer trend point) |
| Saurav | Codex CLI with an API key, and does it accept our proxy's base_url? | Subscription + Codex's own logs if not |
| Saurav | Astra API call | Excluded until a key call works |
| Cedric | Final pool; what the subscription can serve | Four tiers; others via API keys, counted in cost; no Anthropic models |
| Cedric | One Codex seat: ~3 concurrent sessions and ~250–350 agent-hours a week? | Measure at T0; add a second seat for T1/T2 only if needed |
| Cedric, Muk | Product hooks and the evaluation-mode lane | In the benchmark spec, by wk 7 |
| Muk | How many hand capsules per domain? | 3 per domain + bio image classifier |
| Ramika | Add a `confidence` field to the verdict? | Calibration metrics wait on it |
| Team | Chinese-endpoint clearance | Plan without; public items only |
| Team | Is H0 a primary comparison? | Yes, Holm-corrected |
| Team | Archive location; unattended-use terms | GCS bucket; no tracking run until terms are confirmed in writing |
