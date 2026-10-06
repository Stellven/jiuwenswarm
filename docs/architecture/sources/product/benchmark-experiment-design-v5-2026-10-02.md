# Experiment design v5: simplified end-of-term benchmark for AI4Research on openJiuwen

**Status.** **PROPOSED** throughout, except items marked **DECIDED (Saurav, date)**. Decided items still need team review before they go into the decision log of `D:\Huawei\AGENTS.md`. v1–v4 are unchanged in this folder.

**Why v5.** Saurav (2026-10-02): "make the benchmark simpler so it is easier to set up and costs less." v5 applies eight simplifications, each tagged **SIMP-n (PROPOSED)** so the team can reject any one of them on its own. §14 lists what each one saves and what evidence it costs. Everything else is carried over from v4: the hypothesis framing, the presentation story, the setup analysis, RSI on MLE-bench and the §13 stretch.

| Tag | Simplification |
|---|---|
| SIMP-1 | Exactly two toggles, both on ScienceAgentBench: gate off and library v0 vs vN. The router-on-stock toggle (S3) is removed. The forced-tier toggle (S4) is removed because it is not free from existing runs; its baselines stay offline |
| SIMP-2 | Three measurement points instead of four: T0 baseline, T1 mid-term, T2 final. Weekly smoke continues |
| SIMP-3 | MLE-bench runs on **one Spot L4 VM** with no quota request. Only the five core competitions, 2 seeds. B1 runs once; B2 runs at T1 and T2; H0 runs once at T2. No B2-fixed on MLE-bench. No medical competitions and no timing run |
| SIMP-4 | Claude Code (H1) is removed completely, including the Anthropic clearance item |
| SIMP-5 | The optional PaperBench final run is removed. JudgeEval stays and may be deferred to T2 |
| SIMP-6 | ScienceAgentBench, SciCode and the offline router evaluator are unchanged. The ~200-item live router pass runs once, at T1 |
| SIMP-7 | Codex agent-hours are recomputed. One seat may suffice, under the conditions in §9c |
| SIMP-8 | Harness build list is recomputed: no medical timing run, no Claude Code wrapper, no MLE B2-fixed, no S3/S4 adapters, no PaperBench solver |

**Sources.**
- Metric codes: `reports\Metrics that prove our contributions.md`.
- Coverage notes: `reports\Benchmark coverage of shortlist metrics.md`; `research_notes\Benchmark coverage of shortlist metrics\` (`mle_bench.md`, `scienceagentbench.md`).
- Templates: `research_notes\Templates for custom test suites\`.
- Models and router pool: `research_notes\openai_api_models_2026-10-01.md`, `research_notes\router_pool_proposal.md`.
- Earlier benchmark plan: `benchmark-review.md`, `setup.md`.
- PRD cross-check: `reports\PRD benchmark sync check.md`.
- Team guide: `reports\Benchmark guide for the team.md` §0.

All paths are under `D:\Huawei\Benchmark\`. Measurement points are T0–T2. Router metrics keep the codes M1–M6.

**Scope (supervisor).** Test by score whether what the team built beats **stock openJiuwen** and a **standard AI harness**.

**Carried over from guide §0 (DECIDED 2026-10-01/02):**
- The benchmark has its own spec, decoupled from M1/M2. Each measurement point is labelled with the product stages it includes.
- Every system goes through the same harness-side **logging proxy**.
- **Stock openJiuwen is never modified.**
- **Two product hooks:** a headless entry with a non-interactive halt, and components assembled from config (router, gate, library version), with the library pinned by hash.
- **Model-call tags** go in headers or metadata, never in the prompt: `run_id, task_id, seed, obs_id, capsule_name, decl_hash, step_id, role, model_requested, effort, fallback, attempt`.
- **PaperBench is JudgeEval-only.**

---

## 1. The hypothesis we test: a four-rung ladder on one model

**DECIDED (Saurav, 2026-10-02).** The ladder is the headline. The primary capsules are built into AI4Research, so removing them means running stock openJiuwen. The H0+K rung is removed. Every rung runs on **gpt-6.1-sol** (medium effort).

| # | Rung | What it is | What the step up to it tests |
|---|---|---|---|
| 1 | **H0** Codex CLI | Stock Codex CLI, same prompt, caps and sandbox | Reference: a standard harness |
| 2 | **B1** stock openJiuwen | agent-core at a pinned commit, default config, never modified | The platform we build on |
| 3 | **B2-fixed** AI4Research, fixed model | Capsules + planner + gate, every call to Sol | 2→3: the effect of **"our platform"** (capsules, planner and gate together) |
| 4 | **B2** AI4Research + router | Rung 3 with the router on | 3→4: whether the router **holds accuracy** (non-inferior within 10 pp) and **cuts cost**, with the strong-call fraction broken down by stage |

**The hypothesis (H-E2E and its parts):**

> We hypothesise that in bioinformatics, computational chemistry, psychology and math/physics, AI4Research on gpt-6.1-sol solves more held-out tasks than stock openJiuwen and than Codex CLI on the same model.
>
> - **Where it is tested:** ScienceAgentBench (verified split, 82 held-out × 3 seeds) and the SciCode math/physics subset.
> - **The test passes if:** B2 − B1 ≥ +10 pp with Holm p < 0.05, **and** B2 − H0 > 0 with Holm p < 0.05.
> - **Platform step (H-C):** we hypothesise that most of any gain comes from B1 → B2-fixed, and that it shows in the capsule-covered domains but not in the GIS control.
> - **Router step (H-M):** we hypothesise that the router keeps accuracy within 10 pp while cutting virtual cost by ≥ 30%. This is tested on ScienceAgentBench and SciCode only (SIMP-3).
> - **Verifier and RSI (H-V, H-R):** tested on their own suites. The two ScienceAgentBench toggles corroborate them end to end.
> - **MLE-bench:** descriptive only. We report the leaderboard percentile for B1, B2 and H0 on five bio/chem Lite competitions.

**What the presentation shows either way.**
- **If the hypothesis holds,** the ladder is shown with the significant steps marked.
- **If it does not,** we report step by step what held and what did not. For example: a platform gain with no router saving; a gain over B1 but not over H0; or a gain in GIS too, which would mean it is not capsule-specific.
- Slides 2–6 of §2a are shown regardless of the ladder outcome.

**Reading the ladder honestly.**
- Step 2→3 bundles capsules, planner and gate. The gate's share is bounded by the gate-off toggle. The share from the library's evolution is bounded by the v0-vs-vN toggle. Capsule mechanisms are tested directly (C1, C4b, C7, C9).
- The covered-domains-vs-GIS contrast is the only end-to-end evidence that the gain is specific to the capsules.
- Significance can be reached only on pooled ScienceAgentBench held-out and SciCode. Per-domain results and MLE-bench are descriptive.

---

## 2. Hypotheses

**MDE.** Our own simulation, with these assumptions: Beta(0.6, 1.4) task difficulty, a uniform logit shift, 3 seeds, a paired sign-flip test on task means, α = 0.05, 80% power. Results:

| n | MDE |
|---|---|
| 82 | ~10 pp |
| 61 | ~12 pp |
| 22 | ~22 pp |
| 180 | ~6 pp |

With **5 paired MLE-bench competitions**, a two-sided sign test cannot reach p < 0.05 even if all five move the same way (p = 0.0625). MLE-bench is therefore descriptive by construction.

| ID | Hypothesis | Primary metric | Paired against | Sample | MDE | Pre-registered success threshold |
|---|---|---|---|---|---|---|
| **H-E2E** | B2 beats stock openJiuwen and Codex CLI on the same model | SAB SR (per-seed mean), paired by task | B1; H0 (Holm across H-E2E, H-C(a), H-M) | SAB 82 × 3; SciCode secondary; MLE HumanRank descriptive (5 × 2) | ~10 pp | vs B1: Holm p < 0.05 **and** ≥ +10 pp. vs H0: Holm p < 0.05 with a positive estimate. MLE: same sign on ≥ 3 of 5 competitions, no test |
| **H-C** | (a) **Platform step:** B2-fixed beats B1, concentrated in covered domains. (b) **Direct:** hand capsules' sealed suites don't rot; the fixture suite shows few unplanned failures | (a) ΔSR B2-fixed − B1; covered vs GIS. (b) C1; C4b, C7, C9(a) | (a) B1; (b) tools Codex CLI builds from the same spec; stock Symphony `flow` (no sealed suite: not measurable) | (a) SAB 82 × 3 + SciCode; (b) 12–20 capsules × 10–22 sealed inputs; M1 fixtures | (a) ~10 pp; covered vs GIS ~20 pp (descriptive) | (a) Holm p < 0.05 and ≥ +10 pp; (b) median C ≥ 0.9 beside the H0-tool median; C7 reported |
| **H-M** | Step 3→4: the router holds accuracy and cuts cost. Offline, it beats Best Single and the Zero router | Agent: ΔSR (B2 − B2-fixed); Δ virtual cost incl. router-judge calls (M6); strong-call fraction by stage (M5). Offline: CostSave@Match (M1), AIQ (M3) | B2-fixed; seven offline baselines | SAB 82 × 3 + SciCode; LLMRouterBench + live ~200 items | NI margin 10 pp; offline ~2–3 pp | Lower 95% bound of ΔSR > −10 pp **and** cost −30% or better. Offline: CostSave ≥ 30% with CI > 0; AIQ above the Zero line |
| **H-V** | Our verifier passes fewer planted defects than a zero-shot judge, without more false fails | V1 ρ_F→P (V2 beside it); V3 JudgeEval F1/κ | Zero-shot judge on Sol (McNemar); deterministic-only; JudgeEval rows (o3-mini 0.83, gpt-4o-mini 0.59) | ≥ 100 fails + ≥ 40 clean per node type, 2 types; JudgeEval 5 papers | ~10–12 pp | Upper Wilson bound < 0.20; ≥ 10 pp below zero-shot at p < 0.05; V2 not worse by > 5 pp. Gate-off toggle descriptive |
| **H-R** | RSI children beat parents on never-queried final sets with zero regressions; MLE dev gains carry to held-out | R1 Beta rule (fixtures); R3, R4/V6 on MLE (§10) | Parent; naive loop; stock `single_harness` + PR #1362 | ≥ 3 capsules × ≥ 20 final fixtures; MLE dev 2–3 + held-out 5 | rule-bound | l = 0 and P5[Beta(1+w, 1+l)] > 0.5 on ≥ 3 capsules; 0 regressions; 0 referee accesses. v0-vs-vN toggle descriptive. Stretch §13 |

---

## 2a. Presentation story: one slide per hypothesis test

Each slide is the test of one hypothesis. It states the pass criterion fixed before the run, the numbers and baseline shown, the run that produced them, and the outcome whichever way it falls.

Reading conventions:
- **"Not measurable in stock"** means stock openJiuwen or Codex CLI has no mechanism that produces the number.
- **Significant** means a pre-registered test from §2 or §8. Everything else is descriptive with CIs.

**Slide 1: Ladder (tests H-E2E, H-C(a), H-M agent part)**

| | |
|---|---|
| **Numbers** | Held-out SR per domain (GIS greyed as the control) for H0 → B1 → B2-fixed → B2; virtual cost per task; strong-call fraction **by stage** for the router step. MLE-bench HumanRank per competition for H0, B1 and B2 |
| **Baselines shown** | H0 and B1, same model |
| **Runs** | SAB and SciCode ladder at T2 (H0 from T0, B1 from T0 or T1); MLE: B1 (T1), B2 (T1, T2), H0 (T2); proxy logs |
| **Pass if** | B2 − B1 ≥ +10 pp, Holm p < 0.05; B2 − H0 > 0, Holm p < 0.05; B2-fixed − B1 ≥ +10 pp, Holm p < 0.05; router lower bound of ΔSR > −10 pp **and** cost −30% |
| **Comparison read** | B2 − B1 vs stock openJiuwen; B2 − H0 vs Codex. On MLE-bench the router step is not isolated (no B2-fixed) |
| **Significant / descriptive** | Pooled SAB steps and router non-inferiority are significant. Per-domain results and MLE-bench are descriptive |

**Slide 2: Capability capsules (tests H-C)**

| | |
|---|---|
| **Numbers** | (a) C1 conformance of hand capsules (median, silent-rot share) **vs tools Codex CLI builds from the same spec**. (b) C4b P(success \| ready) and C7 unplanned-exception rate from the fixture suite. (c) B1 → B2-fixed in covered domains vs GIS |
| **Baselines shown** | H0-built tools (the literature reports 96.8% rot for agent-built tools); B1 |
| **Runs** | Sealed-suite replay (T0 on); fixture suite (T1); SAB ladder (T2) |
| **Pass if** | Median C ≥ 0.9; C7 reported against its pre-registered value; covered step larger than GIS step (descriptive) |
| **Comparison read** | Stock has no sealed suite, so C1 is **not measurable in stock**. Every stock exception counts as unplanned |
| **Significant / descriptive** | Pooled platform step significant; the rest descriptive |

**Slide 3: Verifier (tests H-V)**

| | |
|---|---|
| **Numbers** | (a) V1 false-pass and V2 false-fail with Wilson CIs, ours vs a zero-shot judge on Sol. (b) The **0.45 retirement cliff** with the margin (1 − τ)/2 − ρ̂. (c) First-failing-node accuracy (V6). (d) JudgeEval F1 (V3). (e) Gate-off toggle on SAB. (f) Coverage and selective accuracy (V4), if a `confidence` field exists |
| **Baselines shown** | Zero-shot judge; deterministic-only checks; published JudgeEval rows |
| **Runs** | Audit set (T0 M1 node, T1 SAB node); JudgeEval (T0, or T2 if deferred); gate-off (T1, T2) |
| **Pass if** | Upper Wilson bound of ρ_F→P < 0.20; ≥ 10 pp below zero-shot at McNemar p < 0.05; V2 not worse by > 5 pp |
| **Comparison read** | ScienceDiscovery reviewers are wrapped to binary and scored on the same set. Codex has no verifier: **not measurable** |
| **Significant / descriptive** | V1 vs zero-shot significant; the rest descriptive |

**Slide 4: RSI engine (tests H-R)**

| | |
|---|---|
| **Numbers** | (a) Score-vs-iteration curves (R2) on fixtures and on regraded MLE candidates. (b) R1 final-set gain with lower bound. (c) Dev–final gap (R3) and validation-vs-private per MLE candidate. (d) Regression and rollback rate (R4). (e) v0 vs vN toggle on SAB. (f) Hygiene (R6): hacking rate, referee-access canaries, manifest hash. **Stretch:** math → psychology imp@k beside children's C1 |
| **Baselines shown** | Parent; naive loop; stock `single_harness` + PR #1362 |
| **Runs** | `rsi.attempt.v1` (T0 on); MLE dev rounds (T1, T2); v0-vs-vN toggle (T1 v0 vs v1, T2 v0 vs vN); §13 (T2) |
| **Pass if** | l = 0 and P5[Beta] > 0.5 on ≥ 3 capsules; 0 regressions; canaries = 0. Stretch: CI only |
| **Comparison read** | Stock `improver_evolution` is unwired, so imp@k is **not measurable in stock**. Stock `single_harness` is measured for R1/R4. Codex has no loop |
| **Significant / descriptive** | R1 is a decision rule; the rest is descriptive |

**Slide 5: Model router (tests H-M)**

| | |
|---|---|
| **Numbers** | Cost–accuracy Pareto per domain with the seven baselines and the Zero-router line; CostSave@Match and PerfGain@Budget offline (LLMRouterBench + live pass; LiveCodeBench as the Coder slice) and in-agent (B2 vs B2-fixed on SAB/SciCode); overhead (M6) |
| **Baselines shown** | Always-strongest, always-cheapest, Always-Mid, random at matched budget, IntelliRouter ordered-failover, Zero router, oracle (**offline only**, SIMP-1) |
| **Runs** | Offline evaluator (T0); live pass (T1); SAB/SciCode step 3→4 (T1, T2) |
| **Pass if** | Offline CostSave ≥ 30% with CI > 0 and AIQ above the Zero line; in-agent as on slide 1 |
| **Comparison read** | IntelliRouter has no cost axis, so it is a single point. Codex CLI is single-model |
| **Significant / descriptive** | Offline CostSave CI and in-agent non-inferiority are significant; per-domain points are descriptive |

**Slide 6: Process (P1–P5).**
- Metrics: agent-authored share, interventions per feature, requirement coverage and AC pass rate, rework rate, time and cost per feature.
- Anchors: Anthropic > 80% agent-authored; E2EDevBench ~50% requirement fulfilment.
- Source: Git and Code SOP scripts.
- Descriptive only, with no threshold.

---

## 3. Ladder details

**Base model.** `gpt-6.1-sol` (DECIDED, Saurav 2026-10-01). It is the Codex CLI subscription default, priced at $2 / $10 per 1M tokens on the API.

**Rungs outside the four.**
- **B0** (agent-core ReAct, nothing added) is an optional SAB diagnostic at T1.
- Claude Code is removed (SIMP-4). Published HAL rows for Claude models stay in the leaderboard tables as published numbers only.

**Equal wrapping.** Every rung uses the same harness, prompt, caps, sandbox, internet setting (off), `domain_knowledge` setting (off) and seeds. All calls go through the proxy.
- **B1** is never patched. Only its base URL points to the proxy.
- **B2-fixed and B2** use the same commit and library hash. They differ only in the router flag (hook 2).

**One-minute tests at T0.**
1. Codex CLI with an API key and a custom base_url.
2. One gpt-6-astra API call. Astra stays a candidate until that call succeeds.

**Product conflicts** (`PRD benchmark sync check.md` C1, C2, C9):
- Phase 1 Builder rules (no training, no `subprocess`, no runtime pip, no repair loops) and the gate's `human_session` would block B2 on SAB and MLE-bench.
- **Proposed fix:** an evaluation-mode lane in the benchmark spec, with a sandbox identical to H0's and hook 1's non-interactive halt.

---

## 4. Secondary toggles (ScienceAgentBench only)

**SIMP-1 (PROPOSED): exactly two toggles,** both inside rung 3 (B2-fixed). Each is end-to-end corroboration of a component tested directly on its own suite.

| # | Toggle | Owner | Corroborates | Seeds | Points |
|---|---|---|---|---|---|
| S1 | **Gate off** (gate always passes, no judged checks) | Ramika | Verifier's end-to-end effect | 3 | T1, T2 |
| S2 | **Library v0 vs vN** (v0 = hand-authored start, vN = after RSI) | Saurav | RSI's end-to-end effect | 3 | T1 (v0 vs v1), T2 (v0 vs vN) |

**Removed.**
- **S3, router-on-stock:** removed entirely.
- **S4, forced cheapest / Always-Mid:** removed. It would need its own agent runs, so it is **not free** from the existing runs. Its baselines remain in the offline evaluator, where they cost nothing.

**Statistics.** Paired sign-flip test against rung 3, with bootstrap CIs. These comparisons are descriptive.

**Hand-authored capsules.**
- v0 *is* Muk's hand library, 3–5 capsules per domain.
- They are tested by step 2→3 in covered domains vs GIS, by C1/C4b/C7/C9, and by S2.
- These tests do **not** show that automated authoring reaches the same level. §13 is the only evidence on that.

**Anti-leakage (pre-registered).**
- Muk sees only dev tasks, MLE dev competitions, library docs and SciCode dev problems.
- Capsules are hashed and frozen before held-out runs.
- Similarity audit against held-out gold programs and top Kaggle kernels, using the 60% Dolos rule. Exclusions are decided before unblinding.
- The SAB canary is checked.

---

## 5. Domain plan

**DECIDED (Saurav, 2026-10-01).**
- Domains: bioinformatics, chemistry, psychology, math/physics.
- GIS is a silent no-capsule control.
- Coding appears only as the router's LiveCodeBench Coder slice.

**SAB split.** 20 dev / 82 held-out, stratified by `github_name` and discipline, published before the first run, run with `--split verified`. Held-out counts: bio 22, chem 16, GIS 22, psych 22.

| Domain | SAB / SciCode tasks | MLE-bench held-out | Hand capsules (Muk; families PROPOSED) | Offline router slice |
|---|---|---|---|---|
| **Bioinformatics** | SAB bio (~22): scanpy-tutorials 7, scvi (id 70), small repos | leaf-classification, plant-pathology-2020-fgvc7, mlsp-2013-birds, right-whale-redux | (1) scanpy pipeline; (2) scvi-tools VAE + DE; (3) omics figure with output-spec checks; (4) bio image classifier (MLE-shared); (5) bioacoustic detector (optional) | MMLU-Pro bio, GPQA bio |
| **Chemistry** | SAB chem (~16): deepchem 9 (id 1), DeepPurpose (id 12), MAST-ML (id 2), MODNet (id 101) | nomad2018-predict-transparent-conductors | (1) deepchem MolNet; (2) RDKit descriptors; (3) DeepPurpose; (4) materials featurisation + GBDT (MLE-shared); (5) molecule visualisation | MMLU-Pro chem, GPQA chem |
| **Psychology** | SAB psych (~22): BioPsyKit 7 (id 45), NeuroKit 6, cogsci-jnmf 7, syllogistic-nvc 6 | — | (1) BioPsyKit scoring; (2) NeuroKit ECG/EDA/RSP; (3) JNMF fitting; (4) syllogistic evaluation; (5) optional stats + plot | MMLU-Pro psych |
| **Math / physics** | **SciCode**: 37 physics + 14 math of 80 ([repo](https://github.com/scicode-bench/SciCode); [paper](https://arxiv.org/html/2407.13168)); dev = official 15; held-out ≈ 40 main / 170 sub; metric = subproblem pass rate | — | (1) numerical linear algebra; (2) ODE/PDE integrators; (3) quantum operators; (4) seeded Monte Carlo; (5) units/tolerance | MMLU-Pro physics + math, GPQA physics |
| GIS (control) | SAB GIS (~22) | — | none | — |

**Capsule families shared between SAB and MLE-bench:**
- tabular featurisation with small-data cross-validation (nomad2018, leaf; SAB ids 2, 101);
- materials descriptors;
- output-spec and calibration checks;
- image loaders (MLE only in practice).

---

## 6. Benchmark set and router pool

**SIMP-6 (PROPOSED).** ScienceAgentBench, SciCode and the offline router evaluator are unchanged. They host the significance tests and are the cheap evidence.

| Benchmark | Role | Tasks | Seeds | Rungs |
|---|---|---|---|---|
| **ScienceAgentBench** verified | Significance; ladder; 2 toggles | 82 held-out (20 dev) | 3 | H0 (T0); B1 (T0 or T1); B0 (T1, optional); B2-fixed, B2, S1, S2 (T1, T2) |
| **MLE-bench** Lite, 5 core | Headline end-to-end (descriptive); RSI curves | 5 held-out; 2–3 RSI dev | **2** | B1 once (T1); B2 at T1 and T2; H0 once (T2) |
| **SciCode** math+physics | Domain extension | ~40 main / ~170 sub | 3 | H0 (T0); B1 (T1); B2-fixed, B2 (T1, T2) |
| Router offline | Router policy at $0 | LLMRouterBench cached (GPQA 198, MMLU-Pro 3,000, LiveCodeBench 1,055) | 70/30 × 5 | Seven baselines (T0) |
| Router live pass | Place Sol and the live pool | ~200 items | 1 | **Once at T1** (SIMP-6) |

**SIMP-3 (PROPOSED): the MLE-bench plan.**

| Status | Competitions | Size (from `mle_bench.md` Q1) |
|---|---|---|
| **Held-out (all)** | nomad2018-predict-transparent-conductors | 3,000 rows |
| | leaf-classification | 1,584 samples |
| | plant-pathology-2020-fgvc7 | 3,642 images |
| | mlsp-2013-birds | 645 clips |
| | the-icml-2013-whale-challenge-right-whale-redux | audio, < 0.3 GB |
| **Dropped** | histopathologic-cancer-detection, aptos2019 | Along with their timing run |
| **Excluded** | ranzcr, siim-isic, random-acts-of-pizza | — |
| **RSI dev** | paddy-disease-classification, plant-seedlings-classification; invasive-species-monitoring only if fixed | — |

**What 2 seeds costs in variance.** The standard error of a per-competition mean grows by √(3/2) ≈ **1.22×** (CIs about 22% wider). With 2 seeds, the seed SD rests on a single degree of freedom, so a per-competition CI is barely informative. Per-competition bars therefore show both seed values rather than a CI. The term-level pooled HumanRank (5 × 2 = 10 runs per system) remains a usable descriptive mean.

**Router step on MLE-bench.** With no B2-fixed on MLE-bench, the router step is not isolated there. MLE-bench shows B1 → B2 and H0 → B2 only. The platform step and router step are tested on ScienceAgentBench and SciCode.

**MLE-bench reporting rules:**
- HumanRank scorer, with a pre-registered rule for invalid submissions;
- archive-and-regrade adapter;
- `awards_medals: false` caveat (medals are synthetic);
- 6 h cap enforced in `start.sh`;
- L4 deviation reported;
- Dolos and the rule checker.

**PaperBench** is JudgeEval-only (DECIDED, Saurav 2026-10-01). **SIMP-5 (PROPOSED):** the optional final B2 run is removed. JudgeEval (~$40, one time) may be deferred to T2. This changes the supervisor's 2026-09-29 plan and needs the supervisor's agreement (open question 1).

**Router pool** is Cedric's decision (DECIDED, Saurav 2026-10-01). It must include:
- a cheap tier;
- Sol;
- a mid model at or below Sol's price;
- a strong tier above Sol.

The seven baselines are evaluated offline. `router_pool_proposal.md` is a candidate list only. With Claude removed (SIMP-4), the live pass costs **~$26**. Expected shape: the cost cut comes from Planner/Reviewer calls, and accuracy is held by Coder calls (HAL SAB: Haiku 4.5 18.6% vs Sonnet 4.5 29.4%). Router-judge calls count in cost (M6).

**Recognised-leaderboard story.** Our rows (B2, B2-fixed, B1, H0, plus H-ref = each benchmark's reference scaffold on Sol) sit above marked published rows.

| Benchmark | Published rows | Caveats |
|---|---|---|
| **MLE-bench Lite** | Leaderboard paused since 2026-04-24 ([README](https://github.com/openai/mle-bench)); paper AIDE/o1-preview 16.9 ± 1.1% any medal on 75 ([paper](https://arxiv.org/html/2410.07095v5)); aggregator Lite 80.3%, self-reported ([sota2](https://www.sota2.com/research/sota/machine-learning-engineering-on-mle-bench-lite-22-competition-june-2026)); MLE-Dojo Lite HumanRank 61.95% | 5 of 22 competitions; 2 seeds; synthetic medals; 6 h on L4 |
| **ScienceAgentBench** | HAL (single run, old split): o3 medium 33.33%; Claude Sonnet 4.5 high 30.39%; o4-mini low 27.45%; Gemini 2.0 Flash 12.75% ([HAL](https://hal.cs.princeton.edu/scienceagentbench)) | Old split; single runs |
| **SciCode** | HAL, main problems, 65 test: o4-mini low 9.23%; o3 medium 9.23%; Claude Opus 4.1 7.69%; GPT-5 medium 6.15% ([HAL](https://hal.cs.princeton.edu/scicode)) | Model vintage |
| **LiveCodeBench** | Router number only | — |

---

## 7. Measurement schedule and cost

**SIMP-2 (PROPOSED): three points.** Week 0 = 2026-10-05. Dates are placeholders. Each point is labelled with the product stages it includes.

| Point | Week (date) | Gates | Runs |
|---|---|---|---|
| Smoke | weekly from wk 2 | — | 10 SAB dev tasks; 1 MLE dev competition at 1–2 h on Spot; 1 seed |
| **T0 baseline** | **wk 3 (≈ 2026-10-26)** | Split published; H0 wrapper; Astra and API-key tests | **Needs no product tool execution:**<br>• H0 on SAB (102 × 3) and SciCode<br>• H-ref<br>• router offline<br>• JudgeEval V3 (or defer to T2)<br>• verifier V1/V2/V5 on the M1 node<br>• C1, C4b/C7/C9(a); R1/R2/R4/R6 on capsules<br>• P1–P5<br><br>**If the runtime is ready:** first SAB ladder (B1, B2-fixed, B2). **If not:** optional Tier 0b on API keys |
| **T1 mid-term** | wk 9 (≈ 2026-12-07) | Codex tool execution; hooks 1–2; unattended-use OK; proxy completeness | • SAB: B1 (if not at T0), B0 (optional), B2-fixed, B2, S1, S2 (v0 vs v1)<br>• SciCode: B1, B2-fixed, B2<br>• MLE: B1 + B2 + RSI dev round 1<br>• live router pass<br>• verifier on the SAB node |
| **T2 final** | wk 15–16 (≈ 2027-01-18) | All capsules frozen; §13 tasks built | • SAB: B2-fixed, B2, S1, S2 (v0 vs vN)<br>• SciCode: B2-fixed, B2<br>• MLE: B2 + H0 + RSI round 2<br>• §13 stretch<br>• leaderboards<br>• JudgeEval if deferred |

**Unit costs (our estimates).**
- **SAB system** (82 × 3): ~$2.5 grading, 10–30 Codex agent-hours.
- **SciCode system:** $0 grading, ~3–10 agent-hours.
- **MLE system** (5 × 2 × 6 h = **60 GPU-h**): **$30.7 Spot** ($51.2 on-demand), ≤ 60 agent-hours.
- **RSI dev round** (3 × 1 × 6 h = 18 GPU-h): $9.2 Spot.
- **Router API** in B2: ~$5–20 per point.
- **H-ref** (SAB reference scaffold on Sol via API, 102 × 3): ~$30–35. This was left uncosted in v4 and is included here.

| Point | SAB / SciCode systems | MLE GPU-h | API $ | GPU $ (Spot) | **Total $** | Codex agent-h |
|---|---|---|---|---|---|---|
| T0 | H0 SAB + H-ref; H0 SciCode (+ B1, B2-fixed, B2 if runtime ready) | 0 | JudgeEval ~$40 (or at T2); audits $15–35; grading ~$3; H-ref $30–35 (+ ~$13–28 if the first ladder runs) | 0 | **~$88–113** (+$13–28) | 15–47 (+30–90) |
| T1 | SAB 4–6 (B1/B0 if not at T0, B2-fixed, B2, S1, S2); SciCode 3 | B1 60 + B2 60 + RSI 18 = **138** | live pass ~$26; grading ~$10–15; router $5–20 | $70.7 | **~$112–132** | SAB 40–180 + SciCode 9–30 + MLE ≤ 138 = **~190–350** |
| T2 | SAB 4 (B2-fixed, B2, S1, S2); SciCode 2 | B2 60 + H0 60 + RSI 18 = **138** | grading ~$10; router $5–20 (+$40 JudgeEval if deferred) | $70.7 | **~$86–101** (+$40) | SAB 40–120 + SciCode 6–20 + MLE ≤ 138 + §13 ~5–15 = **~190–290** |
| Smoke (× ~13) | — | ~2 each (~26) | <$1 each | ~$1 each | **~$2–3 each (~$30–40 term)** | 3–6 each |

**Term:** **~$290–390 + ~$30–40 smoke ≈ $320–430.** GPU: **276 GPU-h + ~26 smoke ≈ 300 GPU-h** (~$155 Spot). Codex: **~395–690 agent-hours** (up to ~780 if the first ladder runs at T0).

**Spot by default (SIMP-3), with checkpoint and resume.** All MLE runs use Spot on one g2-standard-8 with a persistent boot and data disk; the disk survives preemption. Two layers of protection:
- **VM restart:** a watchdog script restarts a preempted VM.
- **Run recovery:** `start.sh` has the agent write `submission.csv` and its working directory to the persistent disk every 30 min. On restart, the harness either resumes the container with the remaining time budget, which needs resume support in our agent directory (planned for B1/B2), or reruns the attempt from scratch. H0 (Codex CLI) cannot resume mid-session, so it reruns.

Either way a preemption counts as an infrastructure failure: rerun up to twice, at about $3 per 6 h attempt. If preemptions exceed ~20% of attempts at T1, switch B2 to on-demand (+$20 per point).

---

## 8. Statistics and pre-registration

| Metric | Unit | Test | CI | Seeds |
|---|---|---|---|---|
| SAB SR, SciCode subproblems | Per-task mean | Sign-flip (10k); McNemar on seed 1; SciCode permuted by main problem | Task-cluster bootstrap | 3 |
| Step 3→4 router | Same | Non-inferiority, lower bound > −10 pp; cost Δ by bootstrap | Bootstrap | 3 |
| Primaries | — | Holm across B2 vs B1, B2 vs H0, B2-fixed vs B1, router NI | — | — |
| S1, S2; covered vs GIS | Per-task | Descriptive | Bootstrap | 3 |
| MLE-bench | HumanRank; above-median, synthetic medals, valid rate | Descriptive; both seed values shown | Pooled-mean bootstrap only | **2** |
| MLE candidates (R2/R3/R4/V6) | Archived nodes | Spearman (validation vs private); hacking rate | Run-cluster bootstrap | all |
| Verifier | Items | McNemar; κ, macro-F1 | Wilson | 3 (V5) |
| RSI R1 | Fixtures | Beta rule | Beta CI | per session |
| Router offline | Items | 70/30 × 5 | Bootstrap | 5 |

**Rules.**
- No best-of-N.
- Never compare pass@k with pass@1.
- Infrastructure failures (including Spot preemption) are rerun up to twice, then counted as a fail.
- Agent failures are never rerun.

**Frozen in the benchmark `spec.md` before each run:**
1. Task ids and splits.
2. Seeds and caps.
3. Versions: Codex CLI; Sol at medium effort; B1 and B2 commits; library hash; router pool, role policy and dated prices; verifier, RSI and proxy versions.
4. Graders and data hashes.
5. Settings and prompts.
6. Thresholds, analysis script, exclusions.
7. Leakage audit.
8. Product stages covered.

**Archive.** SAB programs; MLE submissions, candidates and validation scores; SciCode code; JudgeEval verdicts; proxy logs; transcripts; library snapshots. Stored in a GCS bucket indexed in `jiuwenswarm/docs/verify/`. If a grader changes, every point is re-scored. Graders are never mixed within one table.

---

## 9. Setup analysis

All hours, sizes and wall-clock figures are **our own estimates**. Template hours come from `research_notes\Templates for custom test suites\`. Setup facts come from `setup.md` and `benchmark-review.md`.

### 9a. Harness build (SIMP-8, PROPOSED)

**Capacity:** Saurav ~30 h/week on the benchmark; Cedric part-time, ~8–10 h/week; Ramika and Muk own their suites.

| # | Component | What it does | Owner | Est. h | Needed by |
|---|---|---|---|---|---|
| H1 | **Logging proxy** | OpenAI-compatible pass-through. Records model served, tokens, latency, cost (dated price table) and tags; fails closed in eval mode; JSONL per run | Cedric | 12–20 | T1 (T0 for H0 only if Codex CLI accepts a custom base_url; otherwise Codex's own logs) |
| H2 | **SAB adapter** | `pred_<name>.py` + cost JSONL; `--split verified`; stratified 20/82 split script; per-seed scoring | Saurav | 14–22 | T0 |
| H3 | **MLE-bench adapter** | `agents/<id>/` with `start.sh` 6 h cap and **30-min checkpoint + resume**; HumanRank; candidate archive and regrade; Dolos/rule extras; Spot watchdog. No timing-run logic, no multi-VM orchestration | Saurav | 16–24 | **T1** |
| H4 | SciCode adapter | inspect_ai task, subset file, subproblem scoring | Saurav | 6–10 | T0 |
| H5 | **Codex CLI wrapper** | `codex exec`; custom provider base_url → proxy; pinned version (SAB, SciCode, MLE `agents/codex/`) | Saurav | 8–12 | T0 |
| H6 | Stock agent-core adapter | Pinned commit, default config, headless, base_url → proxy | Cedric | 8–14 | T1 (T0 if the first ladder runs) |
| H7 | **AI4Research adapter** | Hook 1 headless entry; hook 2 config (router, gate, library version); hash pin; tags. No S3/S4 paths | Saurav (+ product hooks) | 6–10 + hooks | T1 |
| H8 | Run archive + scorecard | GCS, index, ladder and toggle tables, stats, leaderboards | Saurav | 14–18 | T0 |
| H9 | Offline router evaluator | LLMRouterBench + Zero router + seven baselines + slices; live-pass collector | Cedric | 12–18 | T0 (live pass T1) |
| H10 | JudgeEval harness | Our verifier as a judge, code-only | Ramika | 6–10 | T0 or T2 |
| H11 | Capsule suites | Sealed-suite harness 10–20; C4b 3–5, C7 8–12, C9 10–15 | Muk (suites by Ramika/Saurav) | 31–52 | T0 (C1), T1 |
| H12 | Verifier audit set | V1 20–30, V2 +3, V4 6–8, V5 3–4, V6 18–24 | Ramika | 50–69 | T0 (M1 node), T1 (SAB node) |
| H13 | RSI log + meta_test | Log 2, R1 3–5, R2 3–4, R4 2–3, R6 8–12; MLE round driver 8–10; §13 tasks 15–25 | Saurav | 41–61 | T0 / T1 / T2 |
| H14 | Process + audit-log scripts | P1–P5 24–39; M5/M6 8–14 | Cedric | 32–53 | T1 |
| — | Hand capsules (not harness) | 12–20 + MLE-shared | Muk | 84–220 | T1 (bio/chem), T2 (psych/math) |

**Harness total: ~256–393 h.**

**Removed from v4's build (SIMP-8):**
| Item | Hours saved |
|---|---|
| Medical timing-run logic and multi-VM orchestration / quota | 4–8 |
| Claude Code wrapper (unbudgeted in v4) | 6–10 |
| S3 router-on-stock adapter | 8–12 |
| S4 forced-tier configuration | 2–4 |
| PaperBench solver (optional, 12–20) | 12–20 |
| **Total** | **~32–54** |

Added back: the Spot checkpoint and resume script, about 4 h, inside H3.

**Saurav's T0 critical path: ~55–75 h, about 2–2.5 weeks.** The MLE adapter is off it, because MLE-bench first runs at T1.

| Weeks | Work |
|---|---|
| wk 0 | GCP project and one Spot VM; Kaggle rules for 7 competitions; `mlebench prepare` for 5 + 2–3 dev; split script → **split published**; Codex wrapper |
| wk 1 | SAB adapter (dry run on 10 dev tasks with H0); SciCode adapter |
| wk 2 | Scorecard; RSI log; one-minute tests |
| **wk 3** | **T0 runs** (~3 days; CPU only) |
| wk 3–8 | MLE adapter with resume (dummy → Codex agent on a dev competition); proxy; stock and AI4Research adapters; process scripts |

**Cedric's chain.** H9 by T0 (~12–18 h, 2 weeks part-time). H1 and H6 by T1.

**T1 gate.** It sits outside the benchmark team: Codex tool execution (G1/G2) and product hooks 1–2 must land by wk 7.

**Must exist before T0:** H2, H4, H5, H8, H9, H10 (or defer), H11 (C1), H13 (log), and the published split.

**Before T1:** H1, H3, H6, H7, the rest of H11, H12 (SAB node), H14, the hooks, and the runtime.

### 9b. Hardware

| Need | Spec | Notes |
|---|---|---|
| MLE-bench GPU | **One** GCP g2-standard-8 (1× L4 24 GB, 8 vCPU / 32 GB); **Spot $0.512/h** (on-demand $0.854/h), plus a persistent 250–500 GB disk (`setup.md`, `benchmark-review.md`) | **No quota request** beyond the default single GPU. Verify on the project; new projects may still need one. One container at a time: T1 and T2 are each 23 runs × 6 h = **138 h ≈ 5.75 days** wall-clock. nvidia/runc runtime, because Sysbox GPU passthrough is unresolved |
| SAB CPU | 16 cores, 32 GB, 200+ GB, 8 workers; 102 tasks grade in ~22–32 min (`setup.md`) | One CPU VM or a team workstation (WSL2 + Docker). Agent time dominates: 246 tasks × 3–8 min per system |
| SciCode CPU | Light; `.h5` test data, size unknown (check at setup) | Same CPU machine |
| MLE disk | The 5 core competitions are each < 0.3 GB, or small (counts above). Dev sets: size unknown, read from `prepare` | 250 GB is likely enough; 500 GB per `setup.md` is safe |
| Archives | ~1–6 GB per point (estimate) | GCS bucket |

**GPU-hours:** T0 0, T1 138, T2 138, smoke ~26. **Term ≈ 300 GPU-h, ~$155 on Spot.**

**Second machine:** yes, a CPU machine for SAB and SciCode. It runs in parallel with the single GPU VM.

### 9c. Subscriptions, keys and licences

| Item | For | Status / action |
|---|---|---|
| **Codex subscription** | H0 and every B rung | Must be a shared account, with written OK for unattended use. Usage limits TBD. **SIMP-7, agent-hours per point:** T0 ~15–47 (up to ~137 if the first ladder runs); T1 ~190–350; T2 ~190–290. Over a ~6-day window, MLE alone holds one session 24 h/day, and SAB/SciCode add ~5–35 h/day. **One seat suffices only if it allows ~3 concurrent sessions and ~250–350 agent-hours a week.** Measure at T0. If not, add a second seat for T1/T2 only |
| **OpenAI API key (graders)** | SAB figure judge `gpt-4o-2024-05-13`; JudgeEval; live pass; MLE rule checker (optional) | Separate from agent keys |
| **OpenAI API key (fallback agents)** | Tier 0b; H-ref; non-subscription router tiers | Tier 0b ≈ $25–35 per SAB system; H-ref ≈ $30–35 |
| Router-pool keys | One per provider in Cedric's pool (no Anthropic) | Regional and legal clearance for non-OpenAI providers; public items only |
| Kaggle | MLE-bench | Accept rules for 7–8 competitions (5 + 2–3 dev); API token |
| Hugging Face | SAB, LLMRouterBench | Read token |
| GCP | One Spot VM, bucket | Project and billing |
| **Licences** | — | Kaggle non-commercial rules; HyperAgents CC BY-NC-SA (use the protocol, not the code); Lurume provisional ODC-BY; GPQA no-plaintext; SAB upstream licences |

### 9d. Per-point run plan

| Point | Go/no-go | Ordered runs | Wall-clock | Babysits |
|---|---|---|---|---|
| **T0** | Split published and hashed; H0 passes 10 dev tasks; `gpt-4o-2024-05-13` served; tag completeness ≥ 99% if H0 goes through the proxy | 1. H0 SAB 102 × 3, H-ref, H0 SciCode (CPU, parallel). 2. Router offline. 3. JudgeEval (**go/no-go: any judge used for scoring needs F1 ≥ 0.80**), or defer. 4. Component suites. 5. First SAB ladder if the runtime is ready | ~3 days | Saurav; Cedric (router); Ramika (verifier) |
| **T1** | 10-task dry run per rung passes; proxy completeness ≥ 99%; unattended-use OK; spec frozen; bio/chem capsules hashed | 1. MLE on the Spot VM, sequential: B2 → B1 → RSI round 1 (~5.75 days). 2. In parallel on CPU: SAB B1/B0 → B2-fixed → B2 → S1 → S2; SciCode B1, B2-fixed, B2. 3. Live router pass | ~6 days | Saurav; Cedric on call; Ramika (S1) |
| **T2** | All capsules hashed and audited; verifier frozen; §13 tasks built | 1. MLE: B2 → H0 → RSI round 2 (~5.75 days). 2. SAB B2-fixed, B2, S1, S2; SciCode B2-fixed, B2. 3. §13. 4. JudgeEval if deferred | ~6 days | All four |

### 9e. Setup risks

| Risk | Effect | Mitigation |
|---|---|---|
| Codex tool execution late | No B rungs at T1 | Tier 0b: B1/B2-fixed/B2 on SAB via API at ~$25–35 per system. MLE B rungs slip to T2 (B1 + B2 there, H0 dropped) |
| Codex CLI ignores a custom base_url | H0 bypasses the proxy | Codex session logs, or an API key if the test passes |
| Spot preemption | Lost attempts; longer wall-clock on one VM | Checkpoint/resume; watchdog; switch B2 to on-demand if > 20% preempted |
| One VM too slow | A point takes ~6 days | Start MLE first at each point; a second Spot VM is possible if quota allows |
| Data download | Small for our 5 + dev | Start in wk 0 |
| Docker + GPU passthrough | Sysbox conflict | nvidia/runc runtime; `nvidia-smi` check inside the agent container in wk 0 |
| Judge deprecation | 64 SAB figure tasks | Archives + full re-score; the 38 non-figure tasks as a judge-free secondary |
| Product hooks late | No AI4Research adapter | T1 gate; escalate at wk 6 |

---

## 10. RSI on MLE-bench

Rounds run on the dev competitions. Every candidate is regraded offline for free. There is one round at T1 and one at T2, each 18 GPU-h (~$9 on Spot).

| Metric | From MLE-bench | Direct? |
|---|---|---|
| **R2** curve, plateau, AUC | Best-so-far private HumanRank per node | **Yes** (archive) |
| **R3** gap / hacking | Validation − private per candidate; hacking rate; dev gain − held-out gain | **Yes** |
| **R1** across rounds | Dev = loop set, 5 held-out = final set | Descriptive; the Beta rule stays on fixtures |
| **R4 / V6** | Promoted candidates whose private score fell; best-of-N vs oracle | **Yes** |
| **R5** imp@k | Not affordable | **No**: §13 |
| **R6** | Rule checker + Dolos only | **No** for canaries and hashes |

The candidate pool shrinks with 5 competitions × 2 seeds, but each run still holds dozens of AIDE-style nodes, so R3 and R4/V6 keep most of their power.

---

## 11. Open questions (with recommended defaults)

1. **Supervisor's agreement to drop PaperBench from tracking.** It was part of the 2026-09-29 $150 plan. *Default:* MLE-bench bio/chem is the headline and PaperBench is JudgeEval only.
2. **Accept or reject each SIMP-1 to SIMP-8.** *Default:* accept all. The ones most worth debating are SIMP-3 (2 seeds, no MLE B2-fixed) and SIMP-2 (one fewer trend point).
3. **Astra API access test.** *Default:* exclude until a key call succeeds.
4. **Codex CLI with an API key and a custom base_url.** *Default:* subscription plus Codex's own logs.
5. **Cedric's final pool, and which models the subscription runtime can serve.** *Default:* the four tiers, non-subscription tiers via API keys, no Anthropic models.
6. **Chinese-endpoint clearance.** *Default:* plan without; public items only.
7. **One Codex seat: concurrency and weekly quota.** *Default:* measure at T0; add a second seat for T1/T2 only if needed.
8. **Product hooks and the evaluation-mode lane.** *Default:* in the benchmark spec, by wk 7.
9. **Muk's capacity** (84–220 h). *Default:* 3 per domain plus the bio image classifier.
10. **Is H0 a primary comparison?** *Default:* yes, Holm-corrected.
11. **$150 per point.** v5 keeps every point under $150. *Default:* treat $150 as the cap.
12. **Archive location and unattended-use terms.** *Default:* GCS; no tracking run before written terms.

---

## 12. Risks (beyond setup)

| Risk | Fallback |
|---|---|
| Supervisor keeps PaperBench in tracking | B2 only, 2 seeds, at T1 and T2 (~$30–40 per point), still under $150 |
| Kaggle licensing blocks MLE-bench | Headline falls back to SAB + SciCode |
| No strong router tier cleared | Router step still tested (non-inferiority + cost), with a smaller expected cut |
| Platform gain absent in covered domains, or equal in GIS | Reported as not capsule-specific; the capsule hypothesis is then tested by C1/C7/C8 only |
| MLE-bench 2-seed results contradict SAB | Shown as descriptive, with both seeds; no inference drawn |
| Hand-capsule leakage | Protocol + audit; exclusions fixed before unblinding |
| Psychology capsules slip | §13 fallback; platform step on 3 domains |

---

## 13. PROPOSED stretch for RSI: cross-domain improver transfer

DECIDED (Saurav, 2026-10-01) as a stretch. It follows HyperAgents' transfer protocol ([HyperAgents](https://arxiv.org/html/2603.19461v1)) and runs at T2.

1. **Source: math/physics.** The weak parents are the math/physics hand capsules with 2–3 planted defects. I₀ runs on SciCode-dev loop fixtures and proposes I₁. The referee is fixed.
2. **Freeze I₁.**
3. **Target: psychology.** The weak parents are defect-planted copies of the psychology hand capsules. **Their sealed suites are the referee**: the improver sees only pass/fail on the loop fixtures. This means `meta_test` falls out of the hand-capsule build.
4. **Measure** imp@k(I₁) vs imp@k(I₀) on 3–5 tasks, with k = 10–20 and ≤ 600 proposer calls.
5. **Statistics:** bootstrap CI and medians, with **no p-value**.
6. **Report beside it:** the children's C1, the hygiene bundle, and the MLE R2/R3 curves.
7. **Fallback:** math → bioinformatics. Saurav named deepchem as the example, but deepchem is chemistry in SAB, so the family needs confirming.

**Cheap variant.** Toggle S2: the SAB held-out gain of vN over hand-authored v0 inside rung 3, across RSI versions, with bootstrap CIs. It reuses runs that already exist.

---

## 14. v4 vs v5

All figures are our estimates. Dollars cover API and GPU; Codex figures are agent-hours.

| Tag | $ saved (term) | GPU-h saved | Codex h saved | Build h saved | Evidence lost or weakened |
|---|---|---|---|---|---|
| **SIMP-1** drop S3 and S4 | ~$5–8 grading + router API | 0 | ~20–60 (S3 10–30; S4 10–30 at 2 seeds) | ~10–16 | No in-agent router-on-stock number for Cedric's section. Forced-tier baselines exist only offline, not inside the agent |
| **SIMP-2** three points | ~$60–80 (one fewer point of grading, router API, audits; GPU counted under SIMP-3) | (in SIMP-3) | ~90–200 (one fewer set of SAB/SciCode ladder and toggle runs) | 0 | **One fewer trend sample:** the curve across the term has 3 points, not 4. The RSI v0-vs-vN toggle has 2 readings, not 3 |
| **SIMP-3** one Spot VM, 5 competitions, 2 seeds, B1 once, B2 at T1/T2, H0 once, no MLE B2-fixed, no timing run | ~$400–440 (v4 MLE GPU ~$560–600 → v5 ~$155) | **~490–520** (v4 ~790–820 → ~300) | ~350–480 (v4 MLE ≤ 126 h per system → ≤ 60) | ~4–8 (timing logic, multi-VM; +4 resume) | **2 seeds widen per-competition CIs by ~1.22×** and leave a single degree of freedom for seed SD. **5 competitions** cannot reach sign-test significance even at 5/5, and leave no medical-imaging coverage. **No MLE B2-fixed,** so the router step is not isolated on the headline benchmark. Fewer RSI candidates per round |
| **SIMP-4** remove Claude Code | $0–60 (H1 runs and Claude in the live pass, ~$17) | 0 | 0 (on a Claude plan) | ~6–10 | No in-run Claude reference row (published HAL rows remain); no Claude tier in the router pool |
| **SIMP-5** remove the optional PaperBench run | ~$40–55 (if it would have run) | ~6–12 | ~6–9 | ~12–20 | No PaperBench name on the slide. JudgeEval V3 calibration is unaffected |
| **SIMP-6** live pass once, at T1 | $0 (it was once in v4 too; only moved) | 0 | 0 | 0 | The live pass cannot inform T0 router tuning; offline cached data must do that |
| **SIMP-7** seat recompute | Possibly one fewer seat (subscription cost not in our $) | 0 | — | 0 | None. Risk: a seat's concurrency may still bind |
| **SIMP-8** build list | — | — | — | **~32–54 total** (overlaps the rows above) | None beyond the removed features |

**Totals.**

| | v4 | v5 |
|---|---|---|
| Measurement points | 4 + smoke | 3 + smoke |
| **Term $** (API + GPU) | ~$690–780 + ~$70 smoke (+ ~$30–35 H-ref uncosted) ≈ **$790–885** | **~$320–430** (incl. H-ref and smoke) |
| Max per point | ~$218 | ~$132 (all ≤ $150) |
| **GPU-h** | ~790–820, 2–3 L4 VMs, quota needed | **~300, one Spot L4, no quota** |
| **Codex agent-h** | ~895–1,270 | **~395–690** (≤ ~780 with the T0 ladder) |
| **Harness build h** | ~290–445 (H1–H14 + unlisted wrappers, S3/S4 and PaperBench solver) | **~256–393** |
| **T0 date** | end of wk 4 (≈ 2026-11-06) | **wk 3 (≈ 2026-10-26)** |
| Codex seats | 2–3 | 1–2 (measure at T0) |
| Evidence retained | — | All significance tests (SAB and SciCode ladder, router NI, verifier, RSI Beta rule) are unchanged. Losses are confined to MLE-bench precision, the MLE router isolation, one trend sample, and in-agent router baselines |

---

## Summary (15 lines)

1. v5 simplifies v4 with eight separately rejectable PROPOSED changes (SIMP-1 to SIMP-8) to cut setup work and cost.
2. Hypothesis: on gpt-6.1-sol, the ladder H0 Codex CLI → B1 stock openJiuwen → B2-fixed → B2 (+ router) shows rising held-out success.
3. The test passes if B2 − B1 ≥ +10 pp (Holm) and B2 > H0 (Holm), on ScienceAgentBench (82 × 3) and SciCode. If not, we report what held.
4. Router step: non-inferiority within 10 pp and ≥ 30% cost cut, on SAB and SciCode. It is not isolated on MLE-bench, which drops B2-fixed.
5. Two toggles only, both on SAB: gate off (verifier) and library v0 vs vN (RSI). S3 and S4 are gone; router baselines stay offline.
6. Three points: T0 wk 3 (≈ 2026-10-26, no tool execution needed), T1 wk 9 mid-term, T2 wk 15–16 final. Weekly smoke continues.
7. MLE-bench: one Spot L4 VM, 5 core bio/chem competitions, 2 seeds, B1 once, B2 at T1/T2, H0 once at T2. Descriptive, with checkpoint/resume.
8. Claude Code and the optional PaperBench run are removed. JudgeEval stays (it may move to T2). The live router pass runs once, at T1.
9. Six slides test the ladder, capsules, verifier (0.45 cliff margin), RSI (Beta rule, zero regressions, hygiene), router (Pareto vs seven offline baselines) and process.
10. Cost per point: T0 ~$88–113, T1 ~$112–132, T2 ~$86–101. Term ≈ $320–430 against v4's ≈ $790–885.
11. GPU: ≈ 300 GPU-h per term (v4 ≈ 790–820), one VM, no quota request.
12. Codex: ≈ 395–690 agent-hours per term (v4 ≈ 895–1,270). One seat may suffice if it allows about 3 concurrent sessions.
13. Harness build ≈ 256–393 h (v4 ≈ 290–445). The T0 critical path is ~2–2.5 weeks of Saurav's time because the MLE adapter moves to T1.
14. Main losses: MLE per-competition CIs ~1.22× wider, no medical competitions, no router isolation on MLE-bench, one fewer trend point. All significance tests are intact.
15. Open questions: supervisor on PaperBench, accept or reject each SIMP, Astra and base_url tests, Cedric's pool, Codex seat concurrency, product hooks, Muk's hours.
