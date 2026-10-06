# 3.Y RSI (full version)

**Draft for review.** RSI's answer to section 3.Y of the PRD template, for Ramika's M1 engineering contract. Short version: `PRD - RSI_completed.txt` in the same folder.

- **Status.** Everything is proposed unless marked otherwise. Settled items:
  - **AGREED** (2026-09-29, Ramika's PRD text, Saurav agrees): M1 RSI is decoupled from the live pipeline. It runs in an offline sandbox and mutates capsules against their contracts and hidden fixtures (`rsi-scope.md`, decision log).
  - **Saurav's decision:** RSI never trains or changes model weights, in M1 or later.
  - **Saurav's decision (2026-09-30):** for target 2, `references/rubric.md` is in M1 scope, both its text and its numbers (3.Y.1).
  - **Saurav's decision (2026-09-30), the term goal**, as stated to the team on Discord: *"Target for RSI this term is capsule level RSI. There will be an improver in RSI that also gets improved in the RSI engine/system and for that to work we need observability from the entire platform at different levels. [...] @BigS [Suraj] you will help with observations that can support the RSI system itself get better over time and not simply be an SI system."*
- **Sources.** Saurav's notes (`D:\Huawei\RSI Engine\rsi-scope.md`, `2026-09-29-capsule-rsi-findings.md`), the CC design pages (`jiuwenswarm/docs/architecture/`), Muk's branch `origin/ai4r_muk` (commit `888f0f5e7`, 2026-09-30, not yet merged), the RSI code in `jiuwenswarm/agents/harness/common/rsi/`, design report v0.4, and the engine options review (`rsi-engine-options.md`, option D). Every CC schema page is a draft; the five records in Appendix C are new.
- **Field names.** The schema has no `evolution.frozen`. That was the v2.10b name, replaced by the allow-list `evolution.may_change` (`fields.md:159-167`, commit `36436834a`). This section uses `evolution.may_change` plus an **RSI always-frozen set** (3.Y.5).

**Is it RSI?** M1 is capsule self-improvement: a fixed improver makes one capsule better. The term deliverable is RSI proper: the improver also improves, judged on held-out improvement tasks (`meta_test`) with the referee fixed. That recursive layer runs after M1 (M3, proposed); M1 builds its seams (3.Y.9) and observations (3.Y.8), so it is later a wiring step, not a rewrite. The RSI claim holds only if four conditions do (proposed, 2026-09-30): the changed part is part of the improver, not just its output; the improved improver runs the next round, rather than a fixed meta-tuner adjusting it; the metric is improver quality on held-out improvement tasks (imp@k), not capsule scores; and the referee (hidden fixtures, gates, verifiers) is out of reach of both levels. Widening to more capsules or building new ones broadens the optimizer but is not recursion. Throughout, this is weak RSI: model weights never change, in the sense DGM and STOP use.

**M1 capability statement.** At M1, RSI takes one capsule whose author set `evolution.rsi: propose`, works in an offline sandbox, and produces one child version that changes only what `evolution.may_change` allows, passes every test the parent passed, and scores higher than the parent on the final hidden set. A person activates each child or rolls it back. Both targets come from Muk's M1 order (`m1/order.md:22-25`):
- **Target 1, the M1 commitment (3.Y.3):** code mutation of the pure helper `rank_opportunities` (PRD 3.4.7, Opportunity Portfolio Prioritization) inside `screening_capsule`. Production keeps it fixed (`evolution.rsi: none`, `m1/order.md:31`). In the M1 sandbox, RSI may propose any better version, including a different formula (Saurav's decision). M1's output for target 1 is a sandbox-proven child and its evidence report; whether it reaches production is decided by the existing human-gated admission.
- **Target 2, second (3.Y.1):** text mutation of `screening_capsule`'s `SKILL.md` and `references/rubric.md`. It needs a headless model call to run the child skill; without one it moves to M2.

**Engine goal: generalize (Saurav's decision).** M1's real deliverable is a capsule self-improvement engine that generalizes to other capsules, not two improved capsules. Generalizing widens the optimizer's scope; it does not by itself make it RSI (see "Is it RSI?"). The same engine, with its improver versioned and improved by its own loop, becomes the term's RSI engine. The two targets are chosen to exercise both kinds of change (code for target 1, text for target 2) through one loop core. Everything specific to a target lives in a **target profile**: its Declaration, fixture set and split manifest, a scoring adapter (for example Top-1 match against a known good pick), and the operator and proposer settings in the improver policy. The loop core, write guard, gate, oracle, records and replay contain no target-specific code. Adding a capsule means writing a new profile, not changing the engine. **Any capsule other than these two is an M1 stretch goal** (for example `requirement_capsule`, which Muk's order lists as an easy first proof, and later `search_capsule`, `hypothesis_capsule`).

The referee (gates, verifiers, checks, sealed suites, policy, record stores) is fixed and out of reach. Blacklist items are deferred, not dropped, except those marked permanent.

**M1 exit criteria.** The subsection named after each criterion owns it. They measure capsule self-improvement and the seams for the recursive layer; none of them claims RSI, because a rising capsule score only shows the optimizer ran (condition 3).

1. **Improvement** (3.Y.3, 3.Y.9). On target 1, the best child passes 100% of visible tests and parent suites, and meets the lower-bound rule (3.Y.5) on the final set, scored exactly once. If target 2 runs, the same holds with k = 3.
2. **Admission and a person** (3.Y.9). The child is a valid `cc.candidate.v1` with the parent's `interface_hash` and a diff inside `evolution.may_change` and outside the always-frozen set. For a `propose` mainline parent (target 2, or the toy capsule of criterion 5 if target 2 does not run), admission evaluates `changes_allowed` and `parent_suites_pass` and holds it as `admitted_inactive`; a person activates it through the librarian, and a `REVERTED` move back works. Target 1's child passes the same checks in the sandbox and stays an evidence report.
3. **Refusals** (3.Y.5, 3.Y.10). The golden set and violation suite run in CI with one command; every planted bad child and forbidden access is refused with the expected reason and logged, and every good child passes.
4. **Agreement** (3.Y.5). Sandbox and admission agree on 100% of submitted children's visible and parent suites. A rerun gives the same verdict 3 times out of 3.
5. **Loop calibration** (3.Y.9). On a deterministic capsule with a planted defect, the stub proposer repairs it within N iterations. A `none` parent is refused before any proposer call.
6. **Isolation** (3.Y.10, 3.Y.6). Zero fixture-store reads by the loop process; zero canary hits in proposer prompts, outputs, child files and logs; the loop set appears only as `{passed, total, queries_left}`; no session exceeds 30 loop-set queries.
7. **Records and replay** (3.Y.10). One `rsi.attempt.v1` per proposer call; the hash chain verifies; replay rebuilds 100% of child `decl_hash` values and gate decisions with no model calls.
8. **Provenance** (3.Y.6, 3.Y.5). 100% of submitted Candidates pass the provenance script; every `builder_gate` cites an evaluator manifest hash unchanged during the session.
9. **Data** (3.Y.8, 3.Y.10). The split manifest passes the coverage and contamination tests; the pre-flight probe passes; every lineage step passes the ablation test or is flagged in `builder_gate`.
10. **Resources and model** (3.Y.2, 3.Y.7). Every attempt record has `time_s`, the served model, and tokens and money as numbers or null with `not_reported`, never 0; parent and child share the model; the CI scan finds no trainer.
11. **Workflow unchanged** (3.Y.4). DAG script and non-target Binding hashes are unchanged; the wiring dry run has zero refusals, where the Default DAG exists.
12. **Export** (3.Y.7). `rsi_pairs.jsonl` validates and has zero hash overlap with the final, anchor and tracking sets.
13. **Improver seams** (3.Y.9). Every attempt record carries the improver policy digest; the policy file converts to agent-core `VersionedImproverPolicy` with the same digest; the record-shape contract test (a stub run with k = 2 turned into a `paired_meta_validate` checkpoint record) returns `accepted` in CI.
14. **Observations** (3.Y.8). Every RSI attempt and session record carries the join keys of the observation contract, and the session report shows yield per improver version.
15. **Generality** (3.Y.9). Both targets run through the same loop core, each from its own target profile. A CI check finds no target capsule name or target-specific branch in the loop core, guard, gate, oracle or record code. A third, deterministic test profile (the toy capsule of criterion 5) runs end to end with a new profile only and no engine code change.

**Shared dependencies.** Subsections cite these by id, adding only what differs.

- **S1. Target capsules.** `screening_capsule` (`research.screen_ideas`) with its pure helper `rank_opportunities`: Declarations, files by hash, visible tests, Verdict `test_suites`. Target 2 uses the mainline Declaration (`propose`); target 1 uses Saurav's sandbox copy of the helper (3.Y.3). Muk. Missing: designed in `m1/order.md` and `capsule/make-capsule.md`, not built.
- **S2. Hidden fixtures and the RSI dev set.** `rsi.fixture.v1` loop and final sets, at least 20 each, meeting the headroom rule, each with a known good pick: scored Idea Card sets (target 1); Idea Card sets with a Research Brief (target 2). Held by the fixture oracle (3.Y.10). Suraj (to confirm) or the capsule author. Missing.
- **S3. Headless Codex text call.** `CodexTextService` (AI4R-001 gate G2): text only, no token usage. Model Routing owner. Missing; the runtime is browser-only (`CODEX_DEMO.md:3,16`).
- **S4. Admission for RSI Candidates.** `cc.candidate.v1` with `submitted_by.kind: rsi` and `builder_evidence.builder_gate`; rules `rsi_permitted`, `changes_allowed`, `rsi_cannot_grant`, `parent_admitted`, `parent_suites_pass` (`policy.md:31`; guards in `capsule/guards.md:131-134,300,304`). Muk. Draft; tool not built.
- **S5. Sample runs from the fixed pipeline.** Bindings, Observations, Artifacts, Verifications per run. Muk's runner. Missing until it runs.
- **S6. Offline replay hook and `caller: rsi`.** One call that runs a capsule on recorded inputs; a `caller: rsi` registry row and a sandbox `scope` (`policy.md:70`, `observation.md:16`). Muk. Missing; RSI ships a thin hook if needed.
- **S7. RSI records.** `rsi.attempt.v1`, `rsi.session.v1`, `rsi.improver_policy.v1` (3.Y.9, 3.Y.10; journal exists, `event_journal.py:15`). Saurav. Proposed.
- **S8. Code location, CI, fixture store and oracle OS account.** Cedric. TBD.
- **S9. Observation contract** (3.Y.8): levels, fields, join keys, storage, cadence. Suraj (part-time intern, data observability for RSI) with Saurav. Missing; proposed.

---

## 3.Y.1 Text-Based Artifacts (GEPA / MIProV2 / TextGrad)

**Definition & Expectation:** Improves prompts, rules, and rubrics[cite: 7]. Validate with holdout tasks, A/B tests, and regression checks[cite: 7].

**M1 stance.** M1 target 2. The target is `screening_capsule` (`research.screen_ideas`, `kind: skill`, `rsi: propose`, `may_change: files:SKILL.md, files:references/rubric.md`; `capsule/make-capsule.md:47-114` on Muk's branch). Muk calls it "a harder RSI target: a scoring rubric whose quality is measurable on fixtures with known good picks" (`m1/order.md:25`). Running a child skill needs a headless model call (S3); without one, the subsection moves to M2. Of the three methods, M1 builds only reflective mutation, the step GEPA and TextGrad share.

**Whitelist (M1 Scope)**

*Artifacts*
- **Prompts.** `SKILL.md`, the skill the model follows (`make-capsule.md:21`).
- **Rules inside the skill text.** Instructions such as how to justify each score may be edited, reordered or added. Policy `rules` are blacklisted.
- **Rubrics: `references/rubric.md`, text and numbers** (**Saurav's decision**, 2026-09-30). It is the model's scoring instruction, not a check. RSI may change its wording and its numbers: dimension scales (for example 1-5), anchors, thresholds and any weights.
- **The dimension set stays.** The three PRD dimensions (novelty, feasibility, compute alignment; PRD 3.4.5, `prd-m1-section3.md:319-322`) stay, as Muk's note asks: "keep the three dimensions the PRD names" (`make-capsule.md:106`). So the edit cannot move `scores_cover_ideas`, which requires every rubric dimension (`:81`). A new write-guard check refuses a `rubric.md` child that drops, adds or renames a dimension *(proposed)*.
- **Worked examples** inside `SKILL.md`, from visible tests only; **model-selection lines** stay unchanged (3.Y.5).

*Method*
- **Reflective mutation, one child per iteration.** The proposer gets the parent text, the failing visible tests with outputs, sample-run Observations and `evolution.notes` (for example "the novelty dimension is the weakest", `make-capsule.md:106`). It returns one `ChangeSet` (3.Y.9) with one rewritten file and a short rationale, stored as `RsiChange` in the Candidate's `ext.rsi` (`candidate.md:56`).
- **Reuse agent-core's prompt templates, not its optimizer class** *(proposed)*. The text proposer uses the reflective-rewrite templates in `agent_evolving/optimizer/llm_call/templates.py` and the placeholder-restore step of `InstructionOptimizer` (`instruction_optimizer.py:242-272`). It does not wrap the class: the class builds its own `Model` client (`:54`) and calls `Model.invoke` (`:140,145`), which the Codex runtime rules out (`specs/AI4R-001-codex-subscription/plan.md:125,129`). Not agent-core's `Trainer` either (`rsi-survey.md:288`).
- **Feedback.** Full detail for visible tests; loop-set counts only (30-query cap, 3.Y.10); the final set never in the loop.
- **Repeats.** k = 3 runs per fixture for parent and child; a fixture passes only if all 3 pass.

*Scoring (rule in 3.Y.5)*
- **What counts.** A fixture passes when the tier 1 checks `scores_cover_ideas`, `chosen_in_scores` and `brief_limits_respected` pass and `chosen_id` equals the fixture's known good pick (`make-capsule.md:79-83`). The score is the pick, not the rubric's own scores, so an easier rubric cannot grade itself better.
- **The judged check is left out.** The tier 2 check `rationale_grounded` (`make-capsule.md:85-89`) is excluded from RSI's score: no judge is calibrated in M1. It still runs at the gate on live calls.
- **Never edited.** Tier 1 checks, `checks/screening.py` and `rationale_grounded` are outside `may_change` and in the always-frozen set.

*Validation*
- **Holdout tasks.** The best child is scored once on the final set under the lower-bound rule (3.Y.5).
- **A/B tests, offline and paired.** Parent and child on the same fixtures, model and settings, k = 3, compared per fixture (3.Y.5). The only A/B form at M1.
- **Regression checks.** Any failure on the parent's suites rejects the child; admission repeats this as `parent_suites_pass` (`fields.md:176`).

**Blacklist (Excluded from M1)**
- **Tier 1 checks, `checks/screening.py` and the judged check `rationale_grounded`.** Permanent; referee (INV-10, `fields.md:145`).
- **The judged check in RSI's score.** M3, scored by a frozen, calibrated judge (3.Y.5).
- **The verifier's tier 2 rubrics, policy `rules` and `levels`.** Permanent; referee (`referee_no_rsi`, `policy.md:31`; `rsi.md:90`).
- **Changing the rubric's dimension set.** M3, with Muk and Ramika. It would move `scores_cover_ideas` and the PRD 3.4.5 definition.
- **Shared `prompt_section` rubric text** (`m1-design.md:285`). M3. One edit reaches every capsule that includes it.
- **`needs.when`, ports (including the `scored_ideas` payload schema) and `effect_class`.** Interface changes, M3 (3.Y.3).
- **GEPA Pareto population and merging; MIPROv2 search.** M2. Several children per iteration exceed the query cap, and neither exists in agent-core (`rsi-survey.md:262-264`).
- **TextGrad across several nodes.** M3, with 3.Y.4.
- **LLM-judge feedback as a critic.** M2, after calibration. **LLM-judge loss as the objective, judged A/B:** M3 (`judge_unmeasured`, `policy.md:56`).
- **Live or shadow A/B.** M2.
- **Online skill evolution (`SkillEvolutionRail`) on the target.** M2; one writer per skill.
- **Worked examples drawn from hidden fixtures.** Permanent.
- **Code and dependency edits.** 3.Y.3.
- **Text mutation itself, if no headless model call exists in time.** M2.

**Dependencies**
- **Shared:** S1, S2 (Idea Card sets with a Research Brief and known good picks), S3 (proposer and child-skill turns, k = 3), S4.
- **`screening_capsule`.** Declaration, `SKILL.md` and `references/rubric.md` (ported from `sciencediscovery/assessment-screening`, `make-capsule.md:21-22`), `checks/screening.py`, `tests/cases.json`, an admitted Verdict. Muk. Missing; example only.
- **Payload schemas** `idea_set`, `research_brief`, `scored_ideas` (`make-capsule.md:66-73`). Muk. Missing.
- **Text proposer** (the `rewrite_file` operator for body files) over the agent-core templates. Saurav. Missing, new.
- **Loop and gate.** 3.Y.9, 3.Y.5.

*M1 exit check:* if the step runs, criteria 1, 2 and 6 apply to the text child with k = 3. If not, it is recorded as moved to M2.

---

## 3.Y.2 Runtime and Resource Routing (Bayesian Optimization / Bandits / Cost-Aware RL)

**Definition & Expectation:** Optimizes model, tool, budget, retry, and concurrency decisions[cite: 7]. Validate with traces, load tests, and cost-latency metrics[cite: 7].

**M1 stance.** Measure, do not optimize. 3.X.2 blacklists bandit, RL and online routing; a capsule's model is set in its hashed files, so a model change is a child version (`fields.md:102`); Codex reports no token usage (`b1-design.md:409`). M1 records every resource decision and holds each fixed per session.

**Whitelist (M1 Scope)**
- **Per-call trace.** Each sandbox call leaves an Observation-shaped record (3.Y.10) with `obs_id`, `outcome`, `reason`, `cost.time_s` and `model`, outside the shared stores.
- **Per-attempt resource fields** in `rsi.attempt.v1`: proposer model and config hash, call count, proposer and test time, `obs_id` list, 3.X.3 audit record ids.
- **Tokens and money as explicit nulls,** with reason `not_reported`, never 0; subscription usage is never labelled API spend (`specs/AI4R-001-codex-subscription/plan.md:113`). The existing service turns unknown tokens into 0 (`Tokens` defaults, `models.py:58-66`; `_safe_int`, `artifact_adapter.py:450-456`; `usage_recorder.py:93-96`), so RSI writes the nulls in `rsi.attempt.v1` itself and labels the service figure "not reported".
- **Budgets in calls and time,** per session; limits in 3.Y.9.
- **Fixed runtime settings per session** in `rsi.session.v1`: proposer model and `config_sha256` (as `model_resolver.py` produces), served model, `needs.resources.timeout_s`, Binding `budget.time_s`, retries 0, concurrency 1.
- **Budget check reused.** A child is kept only if every call passes `check.within_budget.v1` (`policy.md:44,52`); `BUDGET_EXCEEDED` is the child's fault (`policy.md:77`).
- **Runtime failures are not child failures.** `RUNTIME_UNAVAILABLE` or `TIMEOUT` marks the attempt `blocked`: not a fail, not a win, not retried. Runs of blocked attempts feed the stop rule (3.Y.9).
- **Fallback or model mismatch makes an attempt `not_comparable`** and excludes it from the decision (3.Y.7).
- **Cost-latency metric.** Child vs parent `time_s` p50 and p95, and proposer time per kept child, in the session report; in the gate, time is only the 3.Y.5 tie-break.
- **Traces are the sandbox Observations plus the attempt log;** agent-core spans are off in Codex mode (`b1-design.md:406`).

**Blacklist (Excluded from M1)**
- **Bayesian optimization of runtime settings.** M3, offline over attempt logs.
- **Bandit routing.** M3+, as offline replay the Model Routing owner reviews; online bandits stay excluded (3.X.2). **Cost-aware RL:** later, a learned router.
- **Model swap as a mutation.** M2, as a child version naming another 3.X.1-registered model (`m1-design.md:381`: one model in M1).
- **Mid-execution model switching by RSI.** Permanent.
- **Tool and operator choice** (`needs.external`, operator pins). M2+.
- **RSI editing budgets or timeouts.** Permanent; always-frozen set. A person may still change them.
- **Retry and repair policy.** M2+. Reused agent-core retry defaults (`materializer.py:301,304`) are set to 0.
- **Concurrency above 1 and load tests.** M3. All calls share one Codex child (`m1-design.md:356`); `diagnosis_agent_max_concurrency: 5` (`materializer.py:305`) is set to 1.
- **Token and money budgets, cost gating, measured cost from `measurement` Findings.** M2, once usage is reported (`capsule-3w-full.md:393`, `finding.md:38`).
- **Cost shown to the proposer as a target.** M2+. The budget is a hard limit, never a price (`rsi.md:74`).

**Dependencies**
- **Shared:** S3 (text turns; no token usage), S7.
- **Sandbox Observations** (`cc.observation.v1`). Muk. Draft; `caller: rsi` missing (S6).
- **Binding `budget`, policy `budgets`** (`binding.md:32`; `policy.md:37`: default 600 s, cap 1800 s) and **`check.within_budget.v1`** (`policy.md:44`). Muk. Draft.
- **Model Usage Audit record (3.X.3)** with a fallback flag and a new join key to `obs_id`. Model Routing owner. Missing; PRD text only.
- **`rsi/usage_recorder.py`** (proposer call count). Saurav, reuse. Exists; `cost_estimate` is a 0.0 placeholder.
- **Proposer model choice and cost.** Cedric. TBD.

*M1 exit check:* criterion 10; the session report lists child vs parent `time_s` p50/p95 and every `blocked` and `not_comparable` attempt with its reason.

---

## 3.Y.3 Capability Capsules and Physical Operators (Trajectory Mining / Code Evolution / CEGIS)

**Definition & Expectation:** Improves reusable capability contracts and implementations[cite: 7]. Validate with compatibility tests, sandbox runs, and performance benchmarks[cite: 7].

**M1 stance.** M1's commitment: one capsule, one kind of change. Target 1 is the pure helper `rank_opportunities` (PRD 3.4.7, Opportunity Portfolio Prioritization) inside `screening_capsule` (`m1/order.md:25`). RSI evolves its code. Scoring is deterministic: fixtures are scored Idea Card sets with known good picks, so no model is needed to score a child; only the proposer uses one. Contracts stay fixed.

**Production stays fixed; the sandbox is RSI's own (Saurav's decision).** In production, pure helpers stay pinned with `evolution.rsi: none`, so the PRD's arithmetic does not drift (`m1/order.md:31`). The M1 sandbox is separate: Saurav sets `evolution.rsi: propose` and a `may_change` over the helper's code on a **sandbox copy**, and RSI may propose any better version there, including a different formula, weights or tie-breaks. **M1 output for target 1 is a sandbox-proven child plus its evidence report.** Nothing reaches production except through the existing human-gated admission: a person decides whether a proposal is taken up, and if so the change is made on the production Declaration and admitted like any other version. As mechanics, admission refuses an RSI child of a `none` parent (`rsi_permitted`, `guards.md:131`) and never admits the sandbox copy (`parent_admitted`, `guards.md:300`), so the sandbox cannot leak into production by accident.

**Whitelist (M1 Scope)**

*Target*
- **`rank_opportunities`, code only.** A child changes only the helper's code file (path TBD with Muk), as one `ChangeSet` with one file and an empty Declaration patch (3.Y.9).
- **What may change.** The composite scoring function (PRD: `Score = Novelty + Feasibility + ComputeAlignment`, `prd-m1-section3.md:338`), its weights and arithmetic; tie-breaks; the bounded, diverse selection the 3.4.7 Definition asks for (`:336`); and the rejection and deferral rationales (`:340`).
- **What stays fixed.** The interface: Idea Cards scored 1-5 by 3.4.5 in (`:319-322`), `Opportunity_Card.json` with the Top-1 card and rationales out (`:339-341`). Diversity may only shape the order and the deferral reasons.
- **Readiness gate.** Work starts only when the helper has a Declaration, code, tier 1 checks and a visible suite with a case per check, and the sandbox copy exists. None exists yet.

*Contracts vs implementations*
- **Implementations are the target** (code evolution).
- **Contracts stay fixed.** The child's Declaration differs from the sandbox parent only in derived values: file hashes, `identity.lineage` and the computed hashes (`guards.md:133`).
- **Interface guard.** RSI computes the child's `interface_hash` and refuses a mismatch. It refuses any change to `changes.*` (the helper is `pure`) or to the `Opportunity_Card.json` schema. The general rule holds for every target: RSI refuses interface and effect changes whatever `may_change` says (always-frozen set, 3.Y.5).
- **Scope guard.** The write guard (3.Y.9) mirrors admission's `changes_allowed` and `rsi_cannot_grant`, so a bad child never reaches admission.
- **Static import check.** Standard library only, unless `needs.dependencies` lists more.

*Methods*
- **Trajectory mining, offline and deterministic.** Code groups the target's Observations and failed `check_id`s by reason and check into a failure summary. Until the pipeline has runs, the source is the RSI dev set.
- **Code evolution, one change per child.** A proposer model returns one `ChangeSet` (3.Y.9) that rewrites the helper's file, from the parent's code, the Declaration, the visible cases, `evolution.notes` and the failure summary. In M1 the write guard allows one file and an empty patch; multi-file (M2) and interface changes (M3) only widen the guard rule.
- **Minimal CEGIS.** Propose, verify, return a counterexample, repeat. Counterexamples come only from failing visible, parent-suite and dev cases.

*Validation*
- **Compatibility tests.** The parent Verdict's `test_suites` and carried-over visible cases, in the sandbox (and at admission once mainline allows RSI; `parent_suites_pass`, `guards.md:304`). Any regression rejects.
- **The child's tests are the parent's cases;** RSI writes no certifying case (INV-10).
- **Sandbox runs.** A separate process and temp directory, a per-call time limit, no network. Results stay in the RSI session store (3.Y.10).
- **Performance benchmark.** A fixture passes when the child's output validates against the `Opportunity_Card.json` schema, passes the helper's tier 1 checks, and its Top-1 equals the known good pick. The benchmark is the final-set pass count under the lower-bound rule. Rank metrics (the known good pick's rank, rank agreement with the fixture's order) and `cost.time_s` p50 are diagnostics only.
- **Headroom, stated honestly.** The parent picks the argmax of the PRD sum, so the headroom rule (3.Y.5) needs at least 20% of known good picks to differ from it (ties, compute limits, near-duplicates). Any improvement departs from the PRD formula; that is allowed in the sandbox, and the person at admission decides whether it is adopted.

*Output*
- **One evidence report per submitted child:** the Candidate built by 3.Y.9 with its `builder_gate`, attempt log and final-set result, held in the session store while mainline says `none`.

**Blacklist (Excluded from M1)**
- **Mainline admission or activation of a `rank_opportunities` child** without going through human-gated admission. A person decides whether a sandbox proposal is adopted (see above).
- **Contract changes that alter `interface_hash`** (ports, `needs.when`, `changes.effect_class`, check `id`, `target`, `anchor`, `applies_at`), including the `Opportunity_Card.json` schema. M3, with a person's approval and cases from a separate suite author (`rsi.md:47-54`).
- **A multi-card portfolio output instead of Top-1.** An interface change and a PRD change (3.4.7 fixes Top-1). M3, with Ramika.
- **`changes.effects` and any permission widening.** M3.
- **Summary, port descriptions and `failure_modes` additions.** M2.
- **Check runner edits** (`guarantees.checks[].runner`). Permanent; referee, even though `interface_hash` is unchanged.
- **Multi-file `body` capsules and model-backed code capsules.** M2.
- **Capsules checked only by a judge.** M3.
- **Physical operators** (DeepSearch, CodeSearch, workspace I/O; `m1-design.md:283`). M3+.
- **Dependency re-pins.** M2+ (3.W.5; `repin_needs_purpose` unchecked, `guards.md:137`).
- **New capsules from gap Findings.** M4. **Mining live runs, trajectories and `measurement` Findings:** M2.
- **Formal CEGIS.** Later. **Counterexamples from hidden fixtures:** permanent. **Merges and composites:** M4+, the composer's.
- **Owned elsewhere:** skill text and rubric (3.Y.1); sealed suites at admission and jiuwenbox (M2, 3.Y.10); whole-workflow benchmarks for children (M3/M4, 3.Y.8); token and money metrics (3.Y.2); `submit`-level RSI (M4, 3.Y.9); improving the improver (term goal, executed M3; M1 builds only its seams, 3.Y.9).

**Dependencies**
- **Shared:** S1, S2 (scored Idea Card sets with known good picks, plus the RSI dev set), S3 (proposer only), S4, S5, S7; loop and gate in 3.Y.9 and 3.Y.5.
- **`rank_opportunities`** Declaration (`evolution.rsi: none`), code, tier 1 checks and visible cases, inside `screening_capsule`. Muk. Missing: named in `m1/order.md:25,31` only; the `make-capsule.md` example lists no helper file (`:108-114`).
- **Sandbox copy** with `propose` and `may_change` over the helper's code file. Saurav. New; it never leaves the RSI sandbox.
- **`Opportunity_Card.json` schema and the 3.4.7 formula.** Ramika (PRD owner). The formula exists in PRD text; the schema is missing.
- **CC runner and author kit** with the `interface_hash` code the guard reuses. Muk. Missing.
- **Integration Gate** (PRD section 2). Ramika.

*M1 exit check:* criterion 1, and criterion 2's Candidate checks run in the sandbox. The golden set (criterion 3) refuses a child that changes the `Opportunity_Card.json` schema or the effect class, one that edits outside `may_change`, and one whose code opens a socket or reads the fixture store.

---

## 3.Y.4 DAG and Agent Organization (AFlow / MCTS / ADAS)

**Definition & Expectation:** Optimizes workflow structure, agent roles, and coordination[cite: 7]. Validate with replay tests, simulations, and success-cost comparisons[cite: 7].

**M1 stance.** The workflow is RSI's input, never its output. M1 orchestration is a hardcoded Default DAG, 3.W.5 blacklists evolving the whole workflow, and gates are never RSI-able. M1 builds the named validations at node level so later workflow-level work can reuse them.

**Term.** *Sample DAG* (PRD §2): the records of one finished Default DAG run, by `run_id`: Bindings, Observations, Artifacts, Verifications. Existing records, not a new schema; the PRD does not define it, so Ramika and Muk must agree.

**Whitelist (M1 Scope)**
- **Workflow structure: read-only.** RSI reads the Default DAG script and Bindings to find the target's `step_id`, input ports and output checks, and writes neither.
- **Sample DAGs as fixed context.** The Artifacts in each Sample DAG Observation's `inputs` for the target call site become recorded inputs; upstream nodes are not re-run. They are visible dev data unless the fixture owner assigns them to a hidden set (3.Y.8).
- **Replay tests, node level.** Parent and child on the same recorded inputs, scored with the call site's Binding `checks` and `step_checks` (tier 1). k = 1 for deterministic targets (target 1); k = 3 for model-backed ones (target 2).
- **Wiring dry run (the M1 "simulation").** A trial Binding for the child at its `step_id` in the unchanged Default DAG must raise zero `PORT_TYPE_MISMATCH` and `CARRIER_CHANGED` refusals. Nothing runs; no model call.
- **Success-cost comparison, node level.** A paired table per recorded input: tier 1 pass or fail and `cost.time_s`. No tokens or money (3.Y.2).
- **Structural freeze check.** `rsi.session.v1` records the Default DAG script hash and every non-target Binding hash at start and end; both must match.
- **Agent roles: recorded, not changed.** The Binding's optional `role` is copied unchanged into the trial Binding.
- **Every replay is logged** in `rsi.attempt.v1`, so the table regenerates from the log.

**Blacklist (Excluded from M1)**
- **Workflow structure changes by RSI** (nodes, edges, order, parallel branches, routing). M3 at earliest, after the Planner is on the main path. **Whole-workflow evolution:** M4 or stretch (3.W.5).
- **AFlow and MCTS over DAG variants, and simulations that execute them.** M3. Needs variable Swarmflow scripts, a whole-workflow replay harness and a per-candidate budget.
- **ADAS** (a meta agent designing agents or roles). M4 in the build loop, or stretch.
- **Agent-role changes and other coordination changes** (team formation, fan-out, handoff order). M3; 3.X.2 also blacklists team formation.
- **Adding, moving or removing gates.** Permanent; referee.
- **Downstream replay** (child plus later nodes). M2. **Whole-workflow win rate as a promotion gate:** M4.
- **Composites, fusion and merged versions.** Never by RSI; the composer proposes them after M1 and a person approves each.
- **Optimising the Planner Agent.** The Planner's own track; M3 at earliest.
- **Porting AI4R's AFlow, MCTS and ADAS toys or `evolve_workflow`.** Reference only.

**Dependencies**
- **Shared:** S3 (target 2 only), S5 (Artifacts kept; spans expire after 7 days, `observation.md:10`).
- **Default DAG Swarmflow script,** run by `run_workflow(path, backend=...)` with the CC runner as `AgentBackend`. Muk. Designed (`m1-design.md`), not built.
- **Sample DAG inputs in the split manifest.** Suraj, to confirm. Missing.
- **Binding writer refusals** `PORT_TYPE_MISMATCH`, `CARRIER_CHANGED`, callable offline (`binding.md:10`). Muk. Specified; code missing.
- **Per-call-site tier 1 checks** (Binding `checks`, `step_checks`). Ramika with Muk. Draft.

*M1 exit check:* criterion 11. If the pipeline has runs, at least 10 Sample DAG inputs are replayed through parent and child, and the table regenerates identically from the log.

---

## 3.Y.5 Evaluator, Reward, Contract, and Governance (Judge Calibration / Reward Modeling / CEGIS)

**Definition & Expectation:** Improves acceptance rules, rewards, gates, and policies[cite: 7]. Validate with golden sets, agreement rates, and violation tests[cite: 7].

**M1 stance.** This is the referee: the actor may improve, the referee may not (`trust.md:45`, `rsi.md:23,88-92`). The M1 loop improves none of the four nouns. The evaluator changes only through a human-signed epoch track (v0.4 §3.6) from M2/M3; M1 needs it fixed, hashed and out of reach. No judge is calibrated (`policy.md:33,56`), so no judged check enters RSI's score: target 1 has only deterministic checks, and target 2's judged `rationale_grounded` is left out.

**Whitelist (M1 Scope)**

*Acceptance rules and governance*
- **Admission stays the only way in** (`policy.md:31`); a person activates (3.Y.9).
- **The sandbox acceptance rule is a file written before any session,** hashed into the evaluator manifest; only a person changes it.

*Rewards: the scoring rule.* One hand-written lexicographic rule, no learned reward: a later step never pays for an earlier failure (v0.4 §1.4). The **incumbent** is the parent or the best child kept so far.
- **Step 1, hard gate.** Every visible test and parent suite passes.
- **Step 2, loop set.** Wins w (child passes, incumbent fails) and losses l. Kept only if w ≥ 1 and l = 0.
- **Step 3, tie-break.** At equal loop-set results, kept only if median `time_s` is at least 10% lower. Time never offsets a loss.
- **Step 4, final set, once: the lower-bound rule.** At close, best child and parent are scored once, paired per case. Better only if l = 0 and the 5th percentile of Beta(1 + w, 1 + l) is above 0.5, a one-sided 95% lower bound (v0.4 §9.4). With l = 0 this needs w ≥ 4 (0.05^(1/5) ≈ 0.55). Otherwise the session ends `no_candidate`.
- **Fixture pass, for a ranking.** A fixture passes when its tier 1 checks pass and the Top-1 pick matches its known good pick (3.Y.1, 3.Y.3); target 2 runs k = 3. Rank metrics are diagnostics, never part of w or l.
- **Headroom rule.** A target is valid only if the parent fails at least 20% of each hidden set and at least 5 final-set cases. Otherwise the session does not start; the fix is harder fixtures from the fixture owner.

*Gates*
- **Gate before commit.** Steps 1-3 run before any Candidate exists (When Self-Evolution Backfires, `message.txt:23`), in cost order (3.Y.9).
- **The score is a label.** It goes into `builder_evidence.builder_gate` (`candidate.md:39`), kept and never counted (INV-10).

*Policies*
- **Evaluator manifest, pinned per session,** in `rsi.session.v1`: policy epoch and sha256 (`policy_ref`), oracle code sha256, loop-set and final-set hashes, scoring-rule sha256, parent `decl_hash`, `verifier: null`. Its hash `evaluator_sha256` is cited by every attempt record and `builder_gate`. Only a person makes a new manifest, between sessions.

*The RSI always-frozen set.* Beyond what `evolution.may_change` leaves out (`fields.md:160-167`), the sandbox refuses in every M1 session a child that changes:
- `evolution.*` (permanent);
- `guarantees.checks[*]`, including `.runner` (permanent; referee);
- `guarantees.quality` (M2);
- `needs.secrets`, `needs.network` (permanent for RSI);
- `needs.resources` and any budget field (permanent for RSI);
- interface fields: ports, `needs.when`, all of `changes.*` (M3, 3.Y.3);
- model-selection text or config in any file (M2, 3.Y.7).

*Judge calibration*
- **M1 avoids needing it.** Judged checks never enter the score, the fixtures or an expected output, and a target whose only checks are judged is refused. A tier 2 verdict on a sample run is never an expected output.

*CEGIS*
- **Counterexample capture only.** A rejected child's failing visible case is logged by id, never a hidden one (`policy.md:58`).

*Independence*
- **Enforced by access, not trust.** Fixtures, oracle code and scoring rule are read only by the oracle (3.Y.10); the loop gets counts under the 30-query cap (`rsi.md:53`).
- **Second reviewer** (Suraj or Ramika) for oracle and scoring-rule changes, since Saurav writes both sides.

*Validation*
- **Golden set: the final set,** written by someone other than Saurav (3.Y.10).
- **Golden set: planted children.** At least 10 known-bad and 3 known-good (The Blind Curator, `message.txt:21`). Bad: a parent-test regression; an edit outside `may_change`; a check-runner edit; a changed port or `effect_class`; a `rubric.md` that drops a PRD dimension; a model-selection edit; code that opens a socket or reads the fixture store; a child of a `none` parent; an exact copy of the parent. Good: a real fix; a no-op refactor.
- **Agreement rates.** Golden set 100%; sandbox vs admission on visible and parent suites 100%; rerun 3 of 3, else halt with `flaky` (v0.4 §8.3).
- **Violation tests** in CI, each expecting a refusal: child of a `none` parent (`RSI_NOT_PERMITTED`); change outside `may_change` (`RSI_NOT_PERMITTED`); `may_change` naming `evolution` (`SCHEMA_NONCONFORMANT`); always-frozen change (`RSI_FROZEN_PATH`, new); a bound verifier not `none` (`REFEREE_RSI_PERMITTED`); RSI activating its own child (stays `admitted_inactive`). Access tests are 3.Y.10's.

**Blacklist (Excluded from M1)**
- **RSI editing the referee** (admission, gates, verifiers, checks and their runners, check rubrics, sealed suites, policy epochs, record stores). Permanent.
- **New check rubrics.** M3, epoch track: a suite author writes it, it is checked on the anchor set, a person signs it. A work capsule's rubric file that its `may_change` lists (target 2's `references/rubric.md`) is not a check and is in M1 scope (3.Y.1).
- **Acceptance-rule and policy changes proposed by RSI.** M3, as text a person turns into an epoch. **Learned reward models:** M3, critic only. **RSI tuning its own scoring rule:** permanent.
- **Judge calibration, judge-human agreement and the anchor set.** M2: a `verifier_audit` Finding (`finding.md:37`) per judge version on about 50-100 human judgements, with a 95% lower bound and bias probes; M1 reserves the split (3.Y.8).
- **Judged checks in RSI's score, and judge-only targets.** M3, scored by a frozen judge in the manifest.
- **Epoch checkpoints and challenger promotion.** M3. A challenger replaces the judge only at a checkpoint, if its anchor-set lower bound beats the current judge's, with Verifier and RSI owner sign-off.
- **A fine-tuned verifier as referee mid-epoch.** Permanent.
- **The 3.X.4 Reviewer Agent in the RSI gate.** Not in M1; from M2 at most a critic under the verifier's calibration rule, never referee.
- **CEGIS synthesis** of checks, contracts or cases. M3, by a separate suite author (`rsi.md:47-54`). **Pairwise judging:** M3. **Whole-workflow win rate, `submit`-level RSI:** M4. **Hidden tests at admission:** M2 (3.Y.10).
- **Absolute rubric scores as the objective.** Permanent; diagnostic only.

**Dependencies**
- **Shared:** S1 (judged checks kept out of the score), S2 (meeting the headroom rule), S4, S8.
- **Policy epoch `e1`** (`cc.policy.v1` with the RSI rules, `referee_no_rsi`, `levels`; `policy.md:31,34`). Muk. Proposed; the always-frozen set as a rule is an open point.
- **Librarian command** (`policy.md:38`). Muk. Draft.
- **Verifier.** M1: confirmation that RSI makes no verifier call. M2: its Declaration with score, confidence, rationale. Ramika. Missing.
- **Verifier fine-tuning.** None in M1; from M3 each judge version is a challenger. James. No artifact.

*M1 exit check:* criteria 3, 4 and 8.

---

## 3.Y.6 Memory, Retrieval, and Evidence (Memory Learning / Self-RAG / Reranker Training)

**Definition & Expectation:** Improves storage, retrieval, citation, and evidence binding[cite: 7]. Validate with recall, precision, citation accuracy, and provenance checks[cite: 7].

**M1 stance.** (A) Product memory and retrieval (`search`, DeepSearch, CodeSearch, memory rails, report citations): not improved in M1; none runs on Codex yet (`CODEX_DEMO.md:3`), there are no relevance labels, and citation checks are referees. (B) RSI's own memory (attempt log, lineage, proposer feedback, evidence): small, deterministic and needed for a safe loop, so whitelisted.

**Whitelist (M1 Scope)**
- **Storage: the attempt log.** One `rsi.attempt.v1` per attempt, rejected and failed ones included, each written once (INV-2) and hash-chained (3.Y.10).
- **Final-set result stored once,** in `rsi.session.v1` and `builder_gate`; never in attempt records or proposer memory.
- **Lineage.** Every child carries `identity.lineage.parent_hash` and `relation: supersedes` (`fields.md:50-52`). The version tree is built from those plus the log; no second copy (INV-5).
- **Evidence binding.** `builder_gate` cites the attempt ids behind each kept step, the `evaluator_sha256`, and sample-run Artifacts by `Ref(artifact)`; `prompt_ref` and `trajectory_ref` point to the proposer session. No `test_aids` (3.Y.9). All a label (INV-10).
- **Sandbox values stored as Artifacts** (`cc.artifact.v1`, keyed by `content_sha256`) in the session store.
- **Proposer memory within one session.** A summary of earlier attempts: what changed, visible and parent-suite results, the loop-set count. Never which hidden cases failed, their inputs or expected values (`rsi.md:53`). Built by code from record fields and length-capped (`rsi-survey-2.md:374`).
- **Provenance checks before submission.** A failing script blocks submission. It checks that `parent_hash` resolves to the parent pinned in `rsi.session.v1` (admitted, or target 1's sandbox copy); every `files[].sha256` matches; every `builder_evidence` reference resolves with a matching hash (citation accuracy of RSI's own claims); every claimed score equals the score recomputed from the records.

**Blacklist (Excluded from M1)**
- **Memory learning on product memory** (`MemoryRail`, TaskMemory, agent-memory). M3; not versioned by `decl_hash`, so a change would bypass admission.
- **Prompted Self-RAG in `search` or `write_report` skill text.** M2, as a 3.Y.1 mutation.
- **Self-RAG reflection-token and reranker training.** Permanent; weights.
- **Retrieval settings** (top-k, embeddings, chunking, index). M3.
- **Product recall and precision (M2) and report citation accuracy (M2/M3) as objectives.** Need labelled sets and a calibrated judge.
- **Cross-session lesson memory; learning from live Observations.** M2.
- **Hidden-fixture content or final-set results in proposer memory or prompts.** Permanent.
- **Editing record stores, citation gates (`m1-design.md:196,201`) or the verifier.** Permanent.
- **Writing RSI memory into product memory.** Permanent; proposer sessions run with TaskMemory and memory rails off.

**Dependencies**
- **Shared:** S3 (proposer session with `task_memory.enabled: false` and no memory rails; to confirm), S4 (`builder_evidence`, `candidate.md:20-40`, unchecked, so the provenance script is the only enforcement), S5, S6, S7.
- **Lineage fields** (`fields.md:50-53`). Muk. Draft; checked.
- **Artifact and hashing** (`content_sha256`, `Ref.sha256`, INV-15). Muk. Draft.

*M1 exit check:* criteria 6, 7 and 8.

---

## 3.Y.7 Model Policies and Weights (SFT / LoRA / DPO / GRPO / Agent RL)

**Definition & Expectation:** Learns stronger planning, tool use, and evaluation behavior[cite: 7]. Validate with holdout benchmarks, robustness tests, and regressions[cite: 7].

**M1 stance.** RSI never trains or changes model weights (**Saurav's decision**; matches `rsi.md:91`, v0.4 §1.6, §5.3). "Model policy" is wider than weights: a child could swap models in its hashed files. M1 has one model (`m1-design.md:381`) and 3.X owns model choice, so RSI does not change models in M1. M1 delivers guards against training and model drift, training-ready logs, and a data rule that protects the verifier track. This makes the whole design **weak RSI**: weights stay fixed and only capsule contents and improver parts change, the same sense as DGM and STOP ("Is it RSI?").

**Whitelist (M1 Scope)**
- **No-training guarantee.** The RSI package imports no training module (such as agent-core `agent_evolving/agent_rl/`) and calls no fine-tuning API; a CI scan checks it.
- **One pinned model per session,** recorded as `{id, version}` in the Observation `model` field (`observation.md:32`) for every parent and child call.
- **Regressions: model mismatch.** Different models on parent and child calls make the attempt `not_comparable` with reason `MODEL_MISMATCH` (new).
- **Model-selection text is frozen** (always-frozen set, 3.Y.5), even when `may_change` lists the file. The capsule layer cannot see models (`fields.md:102`), so the check sits in the sandbox.
- **Training-ready logs, no training.** `rsi_pairs.jsonl`, an export view of `rsi.attempt.v1`: per line, parent and child `decl_hash`, diff reference, visible, parent-suite and loop-set counts, `generating_model`, `trajectory_ref`, split tag, label `not_training_data_m1`. No hidden-fixture content.
- **Holdout rule.** The final, anchor and tracking sets are listed by content hash in the split manifest (3.Y.8). Any training set, James's included, must have zero overlap. Checked on RSI exports in M1 and on James's data once his manifest exists.
- **Evaluation behavior: the referee stays fixed.** The verifier stays `evolution.rsi: none`; RSI never submits a child of it or feeds it training data.
- **Wording fix (docs).** Replace "never weights" (`rsi.md:91`) and 3.W's "the system never changes model weights" with: "RSI and the capsule system never change model weights. The verifier's judge model may be fine-tuned offline by a separate track (James). Each version enters only as a new verifier capsule version through admission, as a challenger at an epoch checkpoint under the anchor-set rule." Needs Muk's agreement.

**Blacklist (Excluded from M1)**
- **SFT, LoRA, DPO, GRPO and Agent RL by RSI.** Permanent. A model judging its own outputs invites reward hacking (v0.4 §5.3); a separate future track may read `rsi_pairs.jsonl` with its own PRD decision.
- **Planning behavior through weights.** Permanent for RSI.
- **Tool-use behavior.** Prompt-level: M2, once Codex runs tools. Weight-level: permanent.
- **Evaluation behavior (the judge).** Never RSI's; James's track.
- **Fine-tuned judges in gates.** M3, as challengers at epoch checkpoints (3.Y.5). Critic only from M2, never referee.
- **RSI changing a capsule's model through a child.** M2, among 3.X.1-registered models, with a person activating.
- **RSI tuning routing policy or router config.** M3+, reviewed by the Model Routing owner.
- **Holdout-benchmark (M2/M3) and robustness tests (M3) of model changes.**
- **Locally hosted weights.** 3.X decides; RSI takes no position.

**Dependencies**
- **Shared:** S3 (reports the served model id and version: unconfirmed; if not, the pin check uses the configured model), S7.
- **Observation `model`** (`observation.md:32`) and **Candidate `generating_model`, `trajectory_ref`, `builder_gate`** (`candidate.md:35-39`). Muk. Draft.
- **Split manifest with content hashes.** Suraj, to confirm. Missing.
- **Verifier Declaration with `evolution.rsi: none`.** Ramika with Muk. Missing; `referee_no_rsi` drafted.
- **Anchor set** (Ramika with Saurav; from M2), **James's training-data manifest** (James), **3.X.1 registry** (Model Routing owner; from M2). Missing.
- **agent-core `agent_evolving/agent_rl`.** Exists, unused; listed so the scan knows what to forbid.

*M1 exit check:* criteria 10 and 12; a planted model-selection edit is refused in 5 of 5 trials.

---

## 3.Y.8 Data, Benchmarks, Curriculum, and Observability (Active Learning / Hard-Case Mining / Credit Assignment)

**Definition & Expectation:** Improves task coverage, difficulty, data quality, and change attribution[cite: 7]. Validate with coverage, contamination, trace, and ablation tests[cite: 7].

**M1 stance.** M1 builds the data scaffolding for a trustworthy result on each target, not learning over data. RSI's fixture sets stay apart from the milestone tracking set, which no loop ever sees. Observability for RSI spans the platform (the term goal needs it to judge the improver); M1 writes the RSI-level records and a join key to the rest.

**Whitelist (M1 Scope)**
- **Split manifest** (new, one per target). Every fixture by id and sha256, in exactly one split; hidden sets referenced by `rsi.fixture_set.v1` hashes.

  | Split | Used by | Who sees the cases | M1 |
  |---|---|---|---|
  | RSI dev set | proposer context, CEGIS | RSI (visible) | whitelisted |
  | hidden loop set | keep-or-reject | oracle only; loop sees counts, 30 queries per session | whitelisted |
  | hidden final set | scoring the best child once | oracle only; once per session | whitelisted |
  | verifier train | James's fine-tuning | fine-tuning only | listed for disjointness |
  | anchor set | judge promotion, calibration | nobody being judged | listed (M2/M3) |
  | meta_test | judging improver versions | nobody; own fixtures, disjoint by hash | reserved, empty in M1 (M3) |
  | tracking set | milestone benchmark | no loop, ever | listed |

- **Sizes.** At least 20 loop-set and 20 final-set fixtures (v0.4 §11), meeting the headroom rule (3.Y.5). Dev set size TBD with Suraj.
- **Coverage.** Fixture tags `check_id`, `failure_mode`, `difficulty` (static, checked against the parent) and `source`. Every check has a fixture in each of the dev, loop and final sets, or the session is blocked.
- **Data-quality checks.** Input validates against the port schema; the known good pick names an idea in the input; duplicates removed by input hash.
- **Contamination test.** Zero sha256 overlap of fixture inputs across all splits, tracking-set task ids included. A pipeline sample feeds one split only, never both proposer context and a hidden set. Canary scans are 3.Y.10's.
- **Change attribution: credit assignment.** Each child is one change with lineage; its credit is the diff plus the dev fixtures it fixed and broke against the incumbent.
- **Ablation test.** At close, before the final set, the oracle re-runs the loop set on the submitted child with each lineage step reverted in turn. A step whose removal changes neither count nor median `time_s` is flagged in `builder_gate`. Outside the query cap; never shown to the proposer.
- **Trace test.** Replaying one kept child from the log reproduces its visible and dev results and loop-set count (3.Y.10).
- **Hard-case mining, proposals only.** RSI lists candidate hard cases; the fixture owner labels them and picks the split (a hidden set only in a new fixture-set version).
- **Benchmarks: an M1 acceptance result instead of external benchmarks.** Per `AGENTS.md`, M1 probably cannot be measured by PaperBench, ScienceAgentBench or MLE-bench. RSI's M1 evidence is the final-set result under the lower-bound rule. Not agreed.
- **Held-out rule for benchmarks.** The manifest excludes every tracking-set task, fixing "RSI may tune only on dev splits" (`benchmark-review.md`) before any run.

*Observability for RSI* *(proposed; contract with Suraj, S9)*
- **Six levels,** which must join up for the improver to be judged:

  | Level | Record | Status | What the improver learns from it | M1 |
  |---|---|---|---|---|
  | Capsule call | Observation (`cc.observation.v1`) | schema draft | failures, cost, served model per call | sandbox calls; `obs_id` join key |
  | Stage and gate | Binding, Verification | schema draft | which checks fail at which call site | read from sample runs; join key |
  | DAG run | Sample DAG records by `run_id` | missing until the pipeline runs | where inputs and failures come from | `run_id` join key only |
  | RSI attempt | `rsi.attempt.v1` | new | kept or rejected, cost per proposal | written |
  | RSI session | `rsi.session.v1` | new | outcome, stop reason, final-set result | written |
  | Improver version | improver digest, `rsi.improver_policy.v1` | new | yield per version | written |

- **Join keys.** Every RSI record carries the parent `decl_hash`, its `obs_id`s and any Sample DAG `run_id`.
- **Improver yield per improver version,** in the session report, grouped by `improver_version`: kept children per proposer call; calls and time to the first kept child; regressions caught (step 1 rejections); imp@k from M3.
- **Minimal observation contract,** agreed with Suraj: levels, fields, join keys, storage, cadence.

**Blacklist (Excluded from M1)**
- **Active learning** (uncertainty sampling). M2; needs a calibrated critic.
- **Curriculum** (adaptive ordering; a learnability-based task proposer). M3.
- **RSI writing hidden fixtures, or adding mined cases to a hidden set.** Permanent (INV-10; `rsi.md:49-54`).
- **Sealed suites at admission.** M2 (3.Y.10).
- **RSI tuning on external benchmark dev splits.** M3/M4.
- **External tracking runs as the M1 gate** (about $107-122 per run). M2/M3; needs harness adapters, a headless entry, Codex tools, a shared account, terms and a grader key.
- **Hard-case mining from live runs.** M2.
- **Cross-capsule credit assignment.** M4. **Judged metrics:** M2/M3. **Pretraining contamination checks:** later.
- **Platform-wide observation collection from the live pipeline.** M2, once the fixed pipeline is stable.
- **Observations driving improver changes.** M3, with the recursive layer (3.Y.9).
- **Dashboards** (later) and **token cost attribution** (once reported).

**Dependencies**
- **Shared:** S1, S2 (with tags and the split manifest; format TBD; custody, canaries and query cap in 3.Y.10), S4, S5, S6, S8 (coverage and contamination checks), S9.
- **Tracking-set definition** (`D:\Huawei\Benchmark\benchmark-review.md`). Saurav. Draft; supervisor to confirm.
- **Codex headless entry and tool execution** (AI4R-001 G1-G4). Model Routing owner, with Cedric. Missing.

*M1 exit check:* criteria 9 and 14, and criterion 7's replay of a kept child.

---

## 3.Y.9 RSI Loop Core, Promotion Gate & Rollback *(added for M1)*

**Definition & Expectation:** Runs the offline improve loop on one admitted capsule: it turns the capsule into an RSI task, proposes one change per child version, gates each child before commit on the parent's suites and the hidden loop set, stops on budget, iteration cap or plateau, scores the best child once on the final set, and submits it as a Candidate that a person activates or rolls back. Validate with a planted-defect run, log replay and an access check.

**M1 stance.** The engine 3.Y.3 (code) and 3.Y.1 (text) plug into. M1 is capsule self-improvement. The term goal is RSI proper, where the improver improves too (Saurav, 2026-09-30), and the claim holds only under the four conditions in "Is it RSI?". The recursive layer is not executed in M1, but M1 builds its seams so that adding it is wiring, not a rewrite (option D, `rsi-engine-options.md` §3-§4).

**Whitelist (M1 Scope)**

*Engine*
- **Own loop, borrowed parts, behind the existing seam** *(proposed)*. The loop core is a plain library with a CLI, so CI and headless sessions run it without AgentServer; a thin `CapsuleEngineAdapter` wraps it for the task store, journal and worker. The `RsiEngineAdapter` protocol (`adapter.py:60-95`) is harness-shaped (`adapter.py:32-44`; `models.py:43-50`), so a `CAPSULE` scenario needs small shared-file edits, agreed with Cedric. Steps: load parent, propose, apply, test, gate, log, stop, final score, submit.
- **Not agent-core `single_harness`** (forces `candidate_holdout_cases=0`, `iterative.py:164`; gates on seen cases, `:1270-1300`; needs tools) **or `program_opt` as is** (the drafting model writes the evaluator, `script_domain.py`). Both are references.
- **Reuse agent-core as libraries, at the pin.** `RsiChange`, `ArtifactRef` (`openjiuwen/rsi/schema.py:86,152`) for the Candidate; `VersionedImproverPolicy`, `canonical_policy_digest`, `score_static_priority` (`improver_evolution/policy.py`) for the improver policy and ranking; `paired_meta_validate` (`meta_validation.py`) later, with a contract test in M1. No agent-core orchestrator is used.

*Improver seams* *(proposed; option D)*
- **Improver parts behind interfaces.** Proposer (`StubProposer`, `TextProposer`), operators (`rewrite_file`), ranker (`static_priority_v1`), parent selector (incumbent only) and budget policy (`k = 1, top_m = 1`). One implementation each in M1. Improver parts are not capsules before M3.
- **`ChangeSet`,** the only change type every proposer returns: `operator_id`, `rationale`, `files` (path to `{sha256, content_ref}`, each path matching `files:<glob>` in `may_change`), `deleted`, `decl_patch`, `fingerprint`. M1 guard rule: exactly one file and an empty `decl_patch`.
- **Improver policy file I0** (`rsi.improver_policy.v1`, Appendix C). Hashed, loaded by path, never constants in code, and never inside a capsule's `may_change`. A superset of agent-core `VersionedImproverPolicy` (`improver_evolution/policy.py:64`) that converts to it losslessly: our extra parts go in its free `generation_directives` mapping (`:72,91`), and its `budget_policy` needs only `top_m` and `min_pattern_support` (`:461`).
- **Referee code separate from improver code.** Oracle, gate, write guard, hard caps and the record writer form one package, hashed into the evaluator manifest (3.Y.5), outside every `may_change` and every improver policy. The policy may request `k` and `top_m`; the hard caps (N, call and wall-clock budgets, 30 queries) clamp them.

*Adapters*
- **Capsule-to-task adapter** (new). Reads the parent by `decl_hash`, copies only `may_change` files into a fresh workdir, and holds fixture sets as opaque ids.
- **Access check before any model call.** Refuses `evolution.rsi: none` (`RSI_NOT_PERMITTED`), an empty `may_change`, and in M1 `submit` parents: a `submit` child becomes current on admission (`fields.md:165`), but 3.W.5 says a person activates each version.
- **Write guard.** `may_change` minus the always-frozen set (3.Y.5), plus 3.Y.3's interface and import checks. A failing diff ends the attempt as a security event (`RSI_FROZEN_PATH` or `RSI_NOT_PERMITTED`).
- **Result-to-Candidate adapter** (new). Writes `cc.candidate.v1`: `submitted_by: {kind: rsi, id: <session_id>}`; the parent's Declaration with new file hashes and `identity.lineage`; `files[]`; `tests` = the parent's visible cases; `builder_evidence` (`generating_model`, `prompt_ref`, `trajectory_ref`, `builder_gate` per Appendix C); no `test_aids`. For target 1 the Candidate stays in the session store as the evidence report (3.Y.3).

*The loop* (`rsi-scope.md` steps 1-8; `m1-design.md:159-185`)
- **One change per child:** one `ChangeSet` with one file.
- **Gate before commit, in cost order:** write guard; visible tests 100%; parent `test_suites` 100%; loop set via the oracle. The rule is 3.Y.5's.
- **Rejected children are records, never versions.** The next proposal branches from the incumbent.
- **Stops:** model-call budget, wall-clock budget, iteration cap N, plateau (no kept child in P iterations), the 30-query cap, a run of `blocked` attempts (3.Y.2), a `flaky` result (3.Y.5), a stop file. Values TBD except the cap.
- **Session close:** stop reason; ablation (3.Y.8); final set once; lower-bound rule. If it holds, the provenance script (3.Y.6) and wiring dry run (3.Y.4) run and the Candidate is submitted (target 1: kept as the evidence report); otherwise `no_candidate`.

*Generality (the M1 goal)*
- **Capsule-agnostic core.** The loop core knows capsules only through the Declaration (`evolution.rsi`, `evolution.may_change`, ports, checks) and a target profile: fixture set and split manifest, scoring adapter, and operator and proposer settings in the improver policy. No target-specific code in the loop core, guard, gate, oracle or records (criterion 15).
- **Profiles, not branches.** Target 1 and target 2 are two profiles over one engine. A new capsule is a new profile; any capsule beyond the two targets is an M1 stretch goal.

*Promotion and rollback*
- **Admission, then a person.** A `propose` child is admitted as `admitted_inactive` (`library.md:70`, `standing.md:10`); a person activates it with the librarian command. RSI never admits or activates its own children.
- **Rollback.** A Standing entry whose `current_hash` names the parent, reason `REVERTED` (`standing.md:23`). Nothing is deleted.

*Proposer, runtime and validation*
- **Codex subscription, text only.** A one-shot call with the parent file, `evolution.notes`, failure summary, visible results and in-session summary; returns one `ChangeSet` as JSON. No tools needed.
- **Stub proposer for CI; planted-defect run** on a deterministic toy capsule, an engine test fixture and not an RSI target (criterion 5); **log replay** of every gate decision (3.Y.10).
- **Improver version.** The digest of the improver policy file I0, pinned at session start and written to every `rsi.attempt.v1` and to `rsi.session.v1`. The loop cannot write the file during a session.
- **Sibling-ready records.** `rsi.attempt.v1` carries `step`, `sibling_index`, `k`, `top_m`, `ranking_features`, `predicted_rank`, `fingerprint`, `queried` (Appendix C). A contract test turns a stub run with k = 2 into a `paired_meta_validate` checkpoint record and expects `accepted` (criterion 13).

*Code and CI* (TBD with Cedric)
- **Location.** `jiuwenswarm/agents/harness/common/rsi/capsule/`, tests in `tests/unit_tests/rsi/`, branch `ai4r_saurav`; merge into `ai4r_main_branch` after the PRD §2 Integration Gate.
- **CI.** None today (`run_tests.sh`, `pytest.ini`). Proposed: stub loop, guard, golden set, violation suite and contract test on every PR; real sessions by hand.

**Blacklist (Excluded from M1)**
- **`submit` and automatic promotion.** M4, with the whole-workflow gate.
- **Live-pipeline runs; learning from real Observations and gap Findings.** M2.
- **Several capsules per session, several changes per child, population search** (`program_opt` PUCT). M2.
- **Search with k of 2 or more siblings per step, ranker-chosen oracle queries.** M2.
- **Interface changes.** M3. **Hidden fixtures at admission:** M2. **Whole-workflow gate:** M4.
- **Check, check-rubric and test-suite edits.** Permanent.
- **Judged capsules.** M3. **The verifier as critic:** M2.
- **Tool-using proposer agents.** M2, after Codex G1 and a headless entry.
- **The recursive layer:** improver versions judged on held-out improvement tasks (`meta_test` split) with `paired_meta_validate` (k of 2 or more, at least 3 unseen checkpoints, `meta_validation.py:50`) and imp@k, with a person approving each new improver version. To count as RSI it must meet all four conditions: (1) what changes are improver parts (proposer prompts, mutation operators, candidate ranking and selection, suite author, how it reads observations), not only the capsules it outputs; (2) the improved improver runs the next round itself, so the proposals for improver version N+1 come from the same loop running improver version N, not from a separate fixed meta-tuner (that would be two-level meta-optimization); (3) the metric is improver quality (better children, faster, on `meta_test`), not capsule scores; (4) hidden fixtures, gates and verifiers stay out of reach of both levels, including the logs and records the referee reads (the DGM incident). Term goal, executed in M3 *(proposed)*; M1 builds only the seams above.
- **Improver parts as capsules.** M3 at the earliest, with Muk. The schema has one `evolution.rsi` per capsule, and a proposer capsule would need `none` for the inner loop but `propose` for the meta loop.
- **`test_aids` on RSI Candidates; `caller: rsi` Observations in shared stores.** M2.
- **Changing model weights,** including the verifier's. Permanent.

**Dependencies**
- **Shared:** S1 (plus a deterministic toy capsule for the planted-defect run), S2, S3 (`CodexTextService`, `plan.md:129`, gate G2), S4 (writes `admitted_inactive`), S6, S8.
- **Librarian command** (activation, `REVERTED`). Muk. Draft.
- **`CAPSULE` scenario in the shared RSI service** (`models.py`, `adapter.py`, `services.py`, `provider_factory.py`). Cedric. Missing; not blocking, since the CLI runs without it.
- **agent-core `improver_evolution`** at the pin (`policy.py`, `meta_validation.py`; stdlib plus yaml). Exists; the pin is not installed locally.
- **Budget values** N, P, call and time limits. Saurav with the supervisor. TBD.
- **Integration Gate** (PRD §2). Ramika. Draft.

*M1 exit check:* criteria 1, 2, 5 and 13.

---

## 3.Y.10 Offline Sandbox, Hidden Fixtures & Audit Trail *(added for M1)*

**Definition & Expectation:** Runs the RSI loop in an offline sandbox that scores child versions on hidden fixtures (loop set / final set), which the loop can query only for capped pass counts, and logs every attempt so a session can be replayed. Validate with violation tests, canary leak scans and a replay determinism check.

**M1 stance.** **AGREED** (2026-09-29): M1 RSI runs "in an offline sandbox, running mutations directly against static `make_capsule.md` schemas and hidden test fixtures" (`rsi-scope.md`). 3.W.5 blacklists hidden tests at admission, so the hidden fixtures are RSI's own pre-submission gate, not a sealed suite. Admission stays as in 3.W.2 (visible and parent suites, `provisional`). Access is enforced by what the loop process can reach. M1 has no sandbox for child code (3.W Appendix C), so protection is weaker for code the child runs.

**Whitelist (M1 Scope)**

*The sandbox*
- **What runs.** The loop driver, the proposer call, and the child on visible tests and parent suites. Not the Default DAG, gates or admission.
- **What it reads.** A read-only snapshot pinned by sha256 in `rsi.session.v1`: the parent's Declaration, files, Verdict `test_suites`, and a sample-run export (Observations, Artifacts).
- **What it writes.** Only `.jiuwenswarm/rsi/tasks/<task_id>/` (the existing `RsiTaskStore` and `RsiEventJournal` root) and one throwaway temporary directory per attempt. Not agent-core's `WorktreeManager`, which needs GitCode credentials (`worktree_manager.py:84-85`).
- **Sandbox Observations.** `cc.observation.v1`-shaped, `caller: rsi` (proposed), in the session store only; oracle records are `builder_hidden`. No Verification (INV-3) or Finding per attempt (`finding.md:41`).
- **Network.** The loop's HTTP client allows only the session's model endpoints (a client allow-list, not an OS rule).
- **Judged checks never scored** (3.Y.5).

*Hidden fixtures*
- **`rsi.fixture.v1` (new),** one per fixture, shaped on `cc.check.case.v1` so it can become a sealed case at M2.
- **`rsi.fixture_set.v1` (new),** one per capsule and split; a session pins one loop and one final set by hash. A candidate for the missing sealed-suite submission record (`schemas.md:131`).
- **Custody: who writes.** A person other than the builder: Suraj (to confirm) or the capsule author. Saurav does not read the final set.
- **Custody: where.** A fixture store outside the RSI task root and the fork's git tree (the fork is public); only set hashes go in the repo. Path and an OS account the loop does not run as: TBD with Cedric.
- **Custody: the fixture oracle.** A separate process owning the store, called with a child's `decl_hash` and file hashes, never a path. It runs the child per fixture in a fresh subprocess, compares with `expected` (the known good pick), and keeps outputs in its own store. Its code is pinned in the evaluator manifest with a second reviewer (3.Y.5).
- **What the loop gets back.** Loop set: `{passed, total, queries_left}` only. The gate code gets per-case pass or fail by opaque id, for the no-loss rule; the proposer never does. Final set: the same counts, once, at close.
- **No hidden data through the materializer.** `RsiTaskMaterializer.materialize_dataset` copies datasets into `<task>/input/` (`materializer.py:108-127`), inside the loop's reach. Only visible and dev sets may go through it.
- **Query cap.** 30 loop-set queries per session; the next is refused with `QUERY_CAP_EXCEEDED` (new) and ends the session with `query_cap`. The pre-flight probe and close-time ablation do not count.
- **Stand-in for sealed suites.** `m1-design.md:169` ("run the sealed suite") is implemented by the oracle, before a Candidate exists. The final-set result reaches the Candidate only as `builder_gate` (INV-10).
- **Contamination rule.** No hidden-fixture input sha256 may appear in the sample-run export, visible suites or dev set; checked at session start (3.Y.8).
- **Canary strings.** One per hidden fixture. After each session, a scan of proposer prompts, outputs, child files and logs must find none.
- **Pre-flight probe.** The parent and a broken copy are scored on the loop set; the session starts only if the copy scores lower (agent-core `program_opt/probe.py`; The Blind Curator).

*Audit trail*
- **`rsi.attempt.v1` (new),** one per attempt including rejected, blocked and errored ones, hash-chained via `prev_sha256`. Maps onto v0.4's Receipt (§10.1) and agent-core's `RsiTreeNode`.
- **`rsi.session.v1` (new),** one per session: hashes, evaluator manifest, runtime settings, stop reason, final-set result, outcome.
- **Where records go.** JSON lines through `RsiEventJournal` (`events.jsonl` per task). `rsi_pairs.jsonl` is an export view. `cc.candidate.v1` and the Verdict are reused as is. Fields in Appendix C.
- **Offline replay hook** (S6): runs a capsule by hash on recorded inputs and writes an Observation; used by sandbox, oracle and replay.
- **Replay from the log.** Rebuilds each child from parent files plus `diff_ref`, checks `child_decl_hash`, and re-scores stored outputs. Model calls are not re-run (v0.4 §10.3); a deterministic-code child must also match on re-execution.

*Validation*
- **Violation tests,** all passing before a session counts. The loop process tries to: open a fixture-store path (refused by the OS, logged); get per-case detail or content (no such call); exceed the cap (`QUERY_CAP_EXCEEDED`); call the final set before the stop reason (refused); write the fixture or a record store (refused); reach an endpoint off the allow-list (refused).
- **Replay determinism check.** For one full session, rebuilt child hashes, re-scored results and loop-set counts match 100%, and so does re-execution of a deterministic-code child.

**Blacklist (Excluded from M1)**
- **Live pipeline access during a session.** M2.
- **Writing the library, record stores, policy, test suites or main branch.** Permanent. Admission and the librarian are the only ways in and out.
- **jiuwenbox confinement of child code and OS-level network blocking.** M2. Until then the final set is the backstop.
- **Hidden fixtures as sealed suites at admission, and `certified`.** M2, once a submission record exists and `cc.check.suite.v1` `access` is checked.
- **Per-case hidden results, inputs or outputs reaching the loop or proposer.** Permanent.
- **Judged fixtures** (`expected` as a rubric). M3.
- **Model-written fixtures, fixture rotation, model-call record-and-replay, a write-once KV store, token stop rules.** M2.
- **Signed audit logs and audit UI.** Later.

**Dependencies**
- **Shared:** S1, S2 (at least 20 each), S3 (or an OpenAI API key), S5, S6, S8 (plus the fixture store path and oracle OS account).
- **The five new records.** Saurav with Suraj; Muk reviews alignment with `cc.check.case.v1` and `cc.common.v1`. Proposed.
- **`visibility: builder_hidden`** (`common.md:40`). Exists, unchecked.
- **`task_store.py`, `event_journal.py`, `usage_recorder.py`** in `jiuwenswarm/agents/harness/common/rsi/`. Exist.

*M1 exit check:* criteria 6 and 7, and the violation-suite half of criterion 3.

---

## Open points

Grouped by owner, deduplicated. Paths marked "Muk's branch" are on `origin/ai4r_muk` (`888f0f5e7`).

**Muk (Capability Capsule)**
1. **Target readiness.** `screening_capsule` and `rank_opportunities` are design only (`m1/order.md:25`, `capsule/make-capsule.md:44-115`, Muk's branch): no helper Declaration, code, tests or Verdict. When will they be admitted?
2. **Target 1 sandbox copy (for information, not a blocker).** Production `rank_opportunities` stays fixed per `m1/order.md:31`. RSI works on a sandbox copy and proposes; adoption goes through human-gated admission (Saurav's decision). Please confirm the helper's Declaration, file path and tier 1 checks so the sandbox copy matches production.
3. **Helper and output shape.** The screening example outputs `scored_ideas` with `chosen_id` (`make-capsule.md:73,82`) and lists no helper file (`:108-114`); PRD 3.4.7 outputs `Opportunity_Card.json` with rationales (`prd-m1-section3.md:340-341`). Which port does `rank_opportunities` produce, and where does its code live?
4. **Rubric scales and the interface.** If `scored_ideas.schema.json` fixes scores to 1-5, a scale change moves that port's schema hash and so `interface_hash` (`fields.md:176`), which RSI refuses; RSI could then change only anchors, thresholds and weights. Does the schema fix the range? Your note "keep the three dimensions the PRD names" (`make-capsule.md:106`) is kept.
5. **Order (resolved, for information).** `m1/order.md:24,29` makes `requirement_capsule` RSI's easy first proof (`m1/requirement-capsule.md:245-251`). Saurav's decision: M1 targets are `rank_opportunities` and `screening_capsule`; `requirement_capsule` and every other capsule are M1 stretch goals, added as new target profiles once the engine works (3.Y.9).
6. **Suraj's role wording.** 3.W.5 (`capsule-3w-full.md:90,202`, unchanged on your branch) and `guards.md:383` say "RSI data foundation (Suraj): the fixtures". Suraj is now part-time on data observability for RSI; fixture authorship is to confirm.
7. **Always-frozen set as policy.** `fields.md:166` allows a check `runner` in `may_change`, and a runner edit keeps `interface_hash` (`:176`), against INV-10. Add an epoch `e1` rule refusing RSI diffs under `guarantees.checks` and the rest of 3.Y.5's set?
8. **Admission rules in M1.** `guards.md:131-134,300,304` mark the RSI rules M1; `m1-design.md:184` says lineage and `parent_suites_pass` are unchecked. Criterion 2 needs them checked.
9. **Hidden fixtures and sealed suites.** `m1-design.md:169,183` maps them to sealed suites; 3.W blacklists that at admission. Is the oracle acceptable as M1's stand-in, with `rsi.fixture_set.v1` as the M2 submission record?
10. **`caller: rsi`, a sandbox `scope` and the offline replay hook** (S6; `policy.md:70`, `observation.md:16`) for M1?
11. **Weights wording.** `rsi.md:91` and 3.W say the system never changes weights, while `m1-design.md:185` includes James's judge versions. Accept 3.Y.7's rewording?
12. **Rubric mutation.** `m1-design.md:165` says "prompt, code, rubric"; INV-10 and `rsi.md:90` exclude check rubrics. This section allows a work capsule's rubric file listed in its `may_change` and keeps check rubrics out.
13. **Wiring dry run.** Can `PORT_TYPE_MISMATCH` and `CARRIER_CHANGED` (`binding.md:10`) be called offline?
14. **Smaller points.** `rsi_no_copy` is deferred (`guards.md:132`): M1 submits only lineage children of a `propose` parent, never the sandbox copy. Improver parts as capsules would need `evolution.rsi` per loop (inner vs meta), M3 at the earliest.

**Ramika (Verifier, PRD)**
1. **Which M1, and is RSI in it?** `m1.md:53,57` strikes RSI; `m1-design.md:159-185` and the PRD put it in M1 as a parallel track.
2. **RSI changes PRD-specified numbers.** 3.4.7 fixes `Score = Novelty + Feasibility + ComputeAlignment` and Top-1 (`prd-m1-section3.md:338-339`); 3.4.5 fixes three 1-5 scales (`:319-322`). RSI may propose changes to the formula (target 1, sandbox) and the rubric's numbers (target 2); adoption goes through human-gated admission, so no prior agreement is needed (Saurav's decision). For information only. Is a Top-1 match against a known good pick, with rank metrics as diagnostics, an acceptable benchmark?
3. **"Deterministic" screening.** Muk's review (`prd-review.md:37`, item 11) notes model rubric scoring is not deterministic. RSI treats target 2 as model-backed (k = 3), scored on tier 1 checks and known good picks only.
4. **No verifier call in M1 RSI,** with `rationale_grounded` out of the score, until M2. Confirm.
5. **What the person sees.** Is a `builder_gate` label enough evidence at activation, given admission never vouches for it (INV-10)?
6. **"Rules" and rubrics.** Read as rules inside prompt text, and a work capsule's rubric file where `may_change` lists it; never check or tier 2 rubrics (`capsule-3w-full.md:276`). Confirm.
7. **Planner in M1** (PRD `:9,66` vs `m1-design.md:24,124`) and the **Sample DAG definition** (3.Y.4).
8. **Reviews.** Will you or Suraj review oracle and scoring-rule changes, and will you own the M2 judge-promotion threshold?

**Model Routing owner (Xiaoyang per the capsule PRD; Cedric per AGENTS.md; to confirm)**
`capsule-3w-full.md:49` and `plan.md:34-37` name Xiaoyang; `D:\Huawei\AGENTS.md` names Cedric.
1. **Headless text call** (S3). When does `CodexTextService` (`plan.md:129`) land? Target 2 needs it. Until then, may RSI use an OpenAI API key, with what budget?
2. **Usage limits and terms** for unattended sessions. Until answered, sessions run attended.
3. **3.X.3 audit record** schema, with an `obs_id` join key; Codex reports no tokens (`b1-design.md:409`).
4. **Served model and fallback.** Is the model id reported per call? Is 3.X.2 fallback on in M1?
5. **Who owns a capsule's model** (`fields.md:102`): a child version (M2) or a routing decision?
6. **Proposer session** with TaskMemory and memory rails off, and the 3.X.4 Reviewer never gating RSI children in M1.

**Suraj (part-time intern, data observability for RSI)**
1. **Observation contract** (S9, 3.Y.8): agree the levels, fields, join keys, storage and cadence.
2. **Fixture author, to confirm** (`capsule-3w-full.md:90`, `guards.md:383`; `rsi-scope.md` says TBD).
3. **Sizes and date.** At least 20 loop and 20 final fixtures per target, each with a known good pick, meeting the headroom rule, plus a dev set. By when?
4. **Split manifest format,** with a reserved `meta_test` split whose fixtures are disjoint by hash from every inner set (meta-level Goodhart).
5. **"Records become fixtures"** (`capsule-3w-full.md:185`): labelling by the fixture owner, one split per run? Second reviewer of oracle changes?

**James (verifier fine-tuning)**
1. **Disjointness** of your training data from the anchor, final and tracking sets, checked by hash?
2. **Methods, serving and first checkpoint.**

**Cedric (development lead)**
1. **Code location and CI** (S8): `jiuwenswarm/agents/harness/common/rsi/capsule/`? Where do the golden set, violation suite, contract test and data checks run?
2. **Fixture store** path and an OS account the loop does not run as.
3. **"Competing orchestration loop."** `plan.md:75` forbids one. Does an offline RSI batch loop with its own CLI count?
4. **`CAPSULE` scenario** in the shared RSI service files (3.Y.9).
5. **Proposer model and cost.**

**Saurav and team**
1. **Numbers.** Confirm the 30-query cap, 10% tie-break, headroom rule (20% and 5 cases), 20/20 sizes and k = 3; set N, P and the session budget with the supervisor.
2. **Loop-set feedback:** counts only, or pass or fail per anonymous case?
3. **Improver promotion rule.** `paired_meta_validate` also requires lower selection regret (`min_selection_regret_improvement`, `meta_validation.py:52`). Decide the rule for improver versions before M3, with Ramika reviewing.
4. **Retention** of rejected children's files (v0.4 §10.2), and whether a training track exists.
5. **Own notes** still using `evolution.frozen`: `rsi-scope.md`, findings §2, `HANDOFF-capsule-rsi.md:60,75`.
6. **agent-core pin** `9e33901` is not installed locally; install it before coding.

---

# Appendices

## Appendix A. Terms

Terms defined in 3.W Appendix A (admission, Candidate, Declaration, Observation, Finding, Verification, sealed suite, librarian, epoch) keep that meaning. `make_capsule.md` is the readable form generated from the Declaration (`capsule/make-capsule.md:11-13`, Muk's branch).

| Term | Meaning |
|---|---|
| child version | a new version built from a parent, named by `identity.lineage.parent_hash` |
| `evolution.may_change` | the allow-list of paths a child may change; `evolution.frozen` was the v2.10b deny-list |
| RSI always-frozen set | paths RSI refuses in every M1 session whatever `may_change` says (3.Y.5) |
| sandbox copy | target 1's helper with `evolution.rsi: propose` set by Saurav; it never leaves the sandbox (3.Y.3) |
| known good pick | the idea a fixture's author says should be chosen; a fixture passes when Top-1 matches it |
| hidden fixtures | cases the loop cannot read: the loop set (at most 30 queries, counts only) and the final set (scored once) |
| fixture oracle | the separate process that holds hidden fixtures and scores children |
| evaluator manifest | the hashed list of everything that scores a session (3.Y.5) |
| `builder_gate` | `builder_evidence.builder_gate`: RSI's own scores, a label never counted (INV-10) |
| `ChangeSet` | the one change type a proposer returns; M1 allows one file and no Declaration patch (3.Y.9) |
| improver, improver version | the proposer, operators, ranker, parent selector and budget policy; a version is the digest of its policy file (3.Y.9) |
| recursive layer | improving the improver itself, judged on `meta_test` tasks with the referee fixed (term goal, M3). Counts as RSI only if the improver's parts change, the improved improver runs the next round, the metric is improver quality (imp@k), and the referee is untouchable |
| weak RSI | RSI where model weights never change; only capsule contents and improver parts do (the sense DGM and STOP use). Everything in 3.Y is weak RSI |
| Sample DAG | the records of one finished Default DAG run (3.Y.4, proposed) |

## Appendix B. The M1 loop end to end

| # | Step | Owner |
|---|---|---|
| 0a | Target passes the readiness gate (Declaration, Verdict, visible suite, code; target 1: sandbox copy set to `propose`) | 3.Y.3, 3.Y.1 |
| 0b | Split manifest passes coverage and contamination tests | 3.Y.8 |
| 0c | Target passes the headroom rule; judged checks kept out of the score | 3.Y.5 |
| 0d | Violation suite, golden set and record-shape contract test pass in CI | 3.Y.5, 3.Y.10, 3.Y.9 |
| 1 | Load parent by `decl_hash`; refuse `none`, `submit` and empty `may_change` before any model call | 3.Y.9 |
| 2 | Snapshot; pin evaluator manifest, improver policy digest and runtime settings; open `rsi.session.v1`; record DAG and Binding hashes | 3.Y.10, 3.Y.5, 3.Y.9, 3.Y.2, 3.Y.4 |
| 3 | Pre-flight probe | 3.Y.10 |
| 4 | Build proposer context (parent file, notes, failing visible and dev cases, failure summary, in-session summary) | 3.Y.3, 3.Y.6 |
| 5 | Propose one `ChangeSet` (headless Codex text call, or stub in CI) | 3.Y.9 (code 3.Y.3; text 3.Y.1) |
| 6 | Write guard, interface hash, import check, rubric dimension check | 3.Y.9, 3.Y.5, 3.Y.3, 3.Y.1 |
| 7 | Visible tests and parent suites; `check.within_budget.v1`; mark `blocked` and `not_comparable` | 3.Y.9, 3.Y.2, 3.Y.7 |
| 8 | Oracle on the loop set (Top-1 vs known good pick, tier 1 checks); scoring steps 2-3 | 3.Y.10, 3.Y.5 |
| 9 | Append `rsi.attempt.v1` with join keys; keep or reject; update incumbent | 3.Y.10, 3.Y.6, 3.Y.8 |
| 10 | Check stops; if none, go to 4 | 3.Y.9 |
| 11 | Write stop reason; ablation | 3.Y.9, 3.Y.8 |
| 12 | Final set once; lower-bound rule; else `no_candidate` | 3.Y.10, 3.Y.5 |
| 13 | Provenance script; wiring dry run | 3.Y.6, 3.Y.4 |
| 14 | Build the Candidate with `builder_gate`; target 1: keep it as the evidence report; target 2: submit | 3.Y.9, 3.Y.3 |
| 15 | Admission runs RSI rules and parent suites; writes `admitted_inactive` (target 2 only) | Muk (3.W.2) |
| 16 | A person activates or leaves it; rollback is `REVERTED` | 3.Y.9 (librarian: Muk) |
| 17 | Canary scan, replay check, freeze check, `rsi_pairs.jsonl` export and overlap check, session report with improver yield | 3.Y.10, 3.Y.4, 3.Y.7, 3.Y.8, 3.Y.2 |

## Appendix C. Proposed new records

All new and proposed. They extend the `cc.common.v1` envelope (`id`, `at`, `producer`, `visibility`) and hash per INV-15. Attempt and session records are JSON lines in `RsiEventJournal`.

**`rsi.fixture.v1`** (3.Y.10): envelope with `visibility: builder_hidden`; from `cc.check.case.v1`: `check_id`, `interface_hash`, `inputs`, `expected` (for both M1 targets, the known good pick), `fixtures`, `negative_control`; `capsule_name`; `split` (`loop` or `final`); `author` (a person, never RSI or the builder; INV-10); `source` (`hand_written`, or `from_observation` with `obs_id`); tags `difficulty`, `failure_mode`; `canary`; `sha256`.

**`rsi.fixture_set.v1`** (3.Y.10): `capsule_name`, `interface_hash`, `split`; `fixtures` (list of `Ref`); `frozen_at`, `custodian`; `set_sha256`.

**`rsi.attempt.v1`** (3.Y.10; read by 3.Y.2, 3.Y.6, 3.Y.7, 3.Y.8):
- envelope; `session_id`; `attempt`; `step`, `sibling_index`, `k`, `top_m`; `incumbent_decl_hash`; `child_decl_hash` (null if none built)
- `change`: `kind` (`code` or `text`), `operator_id`, `paths_changed` (subset of `may_change`), `fingerprint`, `rsi_change_ref`; `diff_ref` (unified diff as an Artifact)
- `ranking_features` (`executable`, `coverage`, `atomicity`, `duplicate`), `predicted_rank`, `queried`
- `proposer`: `model {id, version}`, `config_sha256`, `prompt_ref`, `output_ref`, `calls`; `served_model {id, version}`
- `gate`: `write_guard`, `visible {pass, fail}`, `parent_suites {pass, fail}`, `loop_set {passed, total, query_no}` or null, `tie_break {incumbent_median_s, child_median_s}` or null
- `dev_flips` (dev ids only, never loop-set ids); `decision` (`kept`, `rejected`, `blocked`, `not_comparable`, `error`) with a `Reason`
- join keys: `obs_ids`, `run_ids`; `usage_audit_refs` (3.X.3); `cost` (`time_s`, `proposer_time_s`, `test_time_s`, `calls`, `tokens`, `money`; null with `null_reason: not_reported` on Codex)
- `evaluator_sha256`; `improver_version` (the improver policy digest); `prev_sha256`

**`rsi.session.v1`** (3.Y.10):
- envelope; `session_id`; `started_at`, `ended_at`; `target` (1 or 2); `parent` (`name`, `decl_hash`, `code_sha256`, `sandbox_copy: bool`); `snapshot` hashes
- `split_manifest_sha256`, `loop_set_sha256`, `final_set_sha256`
- `evaluator` (`policy_ref`, `oracle_sha256`, `scoring_rule_sha256`, `parent_decl_hash`, `verifier: null`) and `evaluator_sha256`
- `workflow`: DAG script and non-target Binding hashes at start and end
- `runtime`: proposer model and `config_sha256`, served model, `timeout_s`, `budget_time_s`, `retries: 0`, `concurrency: 1`
- `config`: call budget, wall-clock budget, N, P, query cap (30), seed, agent-core commit, `improver_version`
- `stop_reason`: `budget`, `iteration_cap`, `plateau`, `query_cap`, `blocked`, `flaky`, `error`, `manual`
- `final_set`: `parent_passed`, `child_passed`, `total`, `wins`, `losses`, `lower_bound`; `outcome` (`candidate_submitted`, `evidence_report` or `no_candidate`), `candidate_id`
- `improver_yield`: kept children per proposer call, calls and time to first kept child, step 1 rejections

**`rsi.improver_policy.v1`** (3.Y.9): `schema_version`; `version_id` (for example `CI0`), `parent_version_id`; `policy_digest` (sha256 over canonical JSON, as `canonical_policy_digest`, `policy.py:152`); `proposer` (`kind`, `prompt_ref`, `prompt_sha256`, `template_set`, `context_recipe`, `output_schema_sha256`, `model_id` recorded only); `operators[]` (`id`, `kind`, `applies_to`, `instructions_sha256`, `weight`); `ranker` (`ranking_policy: static_priority_v1`, `ranking_weights`); `selector` (`parent_choice`); `budget_policy` (`k`, `top_m`, `min_pattern_support`, `plateau_P`; soft values the hard caps clamp); `code_ref` (null until the recursive layer); `training_ledger_digest`; `evidence_refs[]`. Converts to agent-core `VersionedImproverPolicy`, with the parts it lacks under `generation_directives`.

**Existing field, new content: `builder_evidence.builder_gate`** (3.Y.9): `session_id`, `evaluator_sha256`, `improver_version`; loop-set and final-set counts as in `rsi.session.v1`; `iterations`, `stop_reason`, `ablation_flags`, `attempt_refs`, `artifact_refs`.

**Other new files and codes:** split manifest (3.Y.8; format TBD with Suraj); observation contract (3.Y.8, S9); `rsi_pairs.jsonl` (3.Y.7; export view); hard-case proposals file (3.Y.8); reason codes `QUERY_CAP_EXCEEDED`, `RSI_FROZEN_PATH`, `MODEL_MISMATCH`; attempt statuses `blocked`, `not_comparable`; registry row `caller: rsi` plus a sandbox `scope` (Muk).

## Appendix D. Blacklist by destination

"Permanent" means never for RSI; everything else is deferred, not dropped. Each subsection's blacklist gives the reasons; this index lists only where items go.

- **Permanent.** Model weights by any method (3.Y.6, 3.Y.7). Editing the referee: gates, verifiers, checks and runners, tier 2 rubrics, sealed suites, policy, record stores, citation gates, RSI's own scoring rule (3.Y.1, 3.Y.4, 3.Y.5, 3.Y.6). Mid-run model switching and RSI editing budgets (3.Y.2). `evolution.*`, `needs.secrets`, `needs.network` (3.Y.5). Hidden-fixture content reaching the loop or proposer; RSI writing hidden fixtures, the library or main (3.Y.1, 3.Y.3, 3.Y.6, 3.Y.8, 3.Y.10).
- **Through human-gated admission only.** Adoption of target 1 proposals in production (3.Y.3).
- **M2.** Target 2 without a headless model call; GEPA, MIPROv2 (3.Y.1). Critic signals (3.Y.1, 3.Y.5, 3.Y.9). Live runs and live data (3.Y.1, 3.Y.6, 3.Y.8, 3.Y.9, 3.Y.10). Model swaps and token budgets (3.Y.2, 3.Y.7). Multi-file and model-backed code (3.Y.3). Sealed suites, `certified`, jiuwenbox (3.Y.5, 3.Y.10). Judge calibration (3.Y.5). Platform-wide observation collection (3.Y.8). k of 2 or more, several capsules or changes per session (3.Y.9).
- **M3.** The recursive layer, executed; observations driving improver changes; improver parts as capsules at the earliest (3.Y.8, 3.Y.9). The rubric's dimension set; judged checks in the score (3.Y.1, 3.Y.5). Interface changes and multi-card portfolios (3.Y.3). Workflow structure (3.Y.4). Epoch-track rubrics, learned rewards, challengers (3.Y.5, 3.Y.7). Product memory (3.Y.6). Curriculum (3.Y.8).
- **M4 and later.** `submit`-level RSI and automatic promotion; new capsules from gaps; cross-capsule credit; merges (3.Y.3, 3.Y.4, 3.Y.8, 3.Y.9). Formal CEGIS, cost-aware RL, signed logs, dashboards: later.

## Appendix E. Consistency with 3.W and 3.X

3.W.5 (`capsule-3w-full.md:177-205`; the copy on Muk's branch is identical):

| 3.W.5 line | 3.Y |
|---|---|
| RSI only where the author allows it | Refuses `none`, `submit` and empty `may_change`; always-frozen set. Target 1's sandbox copy never reaches mainline admission, so the author's `none` holds (3.Y.3). |
| The verifier never evolves | `referee_no_rsi` in the violation suite (3.Y.5). |
| Run records become sample fixtures | Dev data; hidden only if the fixture owner labels them, one split per run (3.Y.8). |
| Same admission, plus rules; a person activates | `cc.candidate.v1`, `admitted_inactive`, `REVERTED` (3.Y.9). |
| Blacklist: hidden tests at admission | Hidden fixtures stay in the RSI oracle; `builder_gate` label only (3.Y.10). |
| Blacklist: whole workflow; weights | Structure read-only (3.Y.4); weights permanent (3.Y.7; Muk open point 11). |
| Dependencies: Suraj, James, librarian | S2, S9, Suraj's new role (Muk open point 6); challengers only (3.Y.5); activation (3.Y.9). |

3.X: fallback makes an attempt `not_comparable`, audit ids join attempts (3.Y.2), the Reviewer is not in the gate (3.Y.5).

## Appendix F. Sources

Architecture paths are in `D:\Huawei\jiuwenswarm\docs\architecture\` unless stated. "Muk's branch" means `git -C D:\Huawei\jiuwenswarm show origin/ai4r_muk:<path>` at `888f0f5e7`, read only. agent-core paths were read in `D:\agent-core` (`d0bd8335`); option D checked them against the pin `9e33901` (`jiuwenswarm/pyproject.toml:20`).

**Historical note.** The earlier first target was `compile_intent` (`capsule/example-compile-intent.md`); Muk now calls it a built reference that another person may take on (`m1/order.md:46`), so it is no longer an RSI target.

**All subsections.** Template `PRD - RSI.txt`; style `PRD - Model Routing_completed.txt`; sibling `capsule-3w-full.md` (3.W.5 `:177-205`, Suraj `:90,202`, token gap `:215`, Appendix D `:344-358`); `D:\Huawei\RSI Engine\rsi-scope.md`, `2026-09-29-capsule-rsi-findings.md`; `D:\rsi-survey\RSI-Design-Report-v0.4.pdf`; `D:\Huawei\RSI Engine\Capabiltiy Capsule\message.txt`; `D:\Huawei\AGENTS.md`; scratchpad `rsi-engine-options.md` (option D, §3-§5) and `CHANGES-2.md`.

**Muk's branch.** `docs/architecture/m1/order.md:20-31,46`; `docs/architecture/m1/requirement-capsule.md:132-134,245-251`; `docs/architecture/capsule/make-capsule.md:11-27,44-115`; `docs/architecture/capsule/guards.md:32,131-137,300,304,383`; `docs/architecture/capsule/fields.md:170-176`; `docs/architecture/prd/capsule-3w-full.md` (identical to the local copy); `docs/architecture/prd/prd-review.md:37` (item 11); `docs/product/prd-m1-section3.md:279-345` (PRD 3.4.1-3.4.7).

- **3.Y.1.** `make-capsule.md:21-22,47-114`; `m1/order.md:25`; `prd-m1-section3.md:316-326`; `capsule/fields.md:141-145,159-167,176`; `schemas/candidate.md:18-57`; `schemas/policy.md:31-34,56`; `m1-design.md:285`; `capsule/rsi.md:88-92`; agent-core `agent_evolving/optimizer/llm_call/instruction_optimizer.py:54,140,145,242-272`, `llm_call/templates.py:9,116,154`; `specs/AI4R-001-codex-subscription/plan.md:125,129`; `D:\rsi-survey\rsi-survey.md:262-264,288`.
- **3.Y.2.** `schemas/observation.md:10-36`; `schemas/binding.md:32,38`; `schemas/policy.md:37,44,52,77`; `schemas/finding.md:38`; `capsule/fields.md:98-102`; `capsule/rsi.md:74`; `m1-design.md:356,381`; `b1-design.md:406,409`; `plan.md:113`; `jiuwenswarm/agents/harness/common/rsi/models.py:58-66`, `artifact_adapter.py:450-456`, `usage_recorder.py:93-96`, `materializer.py:298-334`, `model_resolver.py:25-45`.
- **3.Y.3.** `m1/order.md:25,31`; `prd-m1-section3.md:316-345`; `guards.md:131-137,300,304`; `make-capsule.md:98-114`; `capsule/fields.md:50-53,161-177`; `schemas/checks.md:18-41`; `schemas/policy.md:31,36,70`; `capsule/library.md:57-70`; `capsule/rsi.md:40-54,90-91`; `m1-design.md:283`.
- **3.Y.4.** `m1-design.md:23-24,124-157,192-203,368-379`; `big-picture.md:143-158`; `m1.md:36,52`; `schemas/binding.md:10,31,38`; PRD `FeaturesList_PRD_AI4RESEARCH - Ramika.txt:9-10,61-67`; `D:\rsi-survey\rsi-survey.md:269,275-276`.
- **3.Y.5.** `capsule/trust.md:41,45`; `capsule/rsi.md:8,23,47-54,88-92`; `capsule/fields.md:126-128,160-167`; `schemas/policy.md:31-58,70,75`; `schemas/invariants.md:18-25`; `schemas/candidate.md:21,35-39`; `schemas/finding.md:37`; `make-capsule.md:79-89`; v0.4 §1.4, §3.6, §8.3, §9.4; `message.txt:19-23`.
- **3.Y.6.** `schemas/candidate.md:20-40,55-56`; `schemas/artifact.md`; `schemas/finding.md:41`; `schemas/invariants.md:17-25`; `m1-design.md:196,201,283`; `rsi/event_journal.py:1-16`, `task_store.py:3`; `D:\rsi-survey\rsi-survey-2.md:374`; v0.4 §10.2, §10.3.
- **3.Y.7.** `capsule/rsi.md:91`; `capsule/fields.md:102,161-166`; `schemas/observation.md:32,34`; `schemas/candidate.md:35-39`; `big-picture.md:145-146`; `m1-design.md:185,381`; findings §6, §7, gaps 8, 9; v0.4 §1.6, §3.6, §5.3.
- **3.Y.8.** Findings split table and gaps 10, 11, 14, 20; `schemas/checks.md:29,36,45`; `capsule/rsi.md:40-54`; `capsule/observability.md` (Muk's branch: records per call, joined by `run_id` and `obs_id`); `D:\Huawei\Benchmark\benchmark-review.md:43-53`; v0.4 §9.4, §11; option D §4 items 5, 7; `HANDOFF-capsule-rsi.md:78`.
- **3.Y.9.** `rsi/adapter.py:32-44,60-95`, `models.py:43-50`; agent-core `rsi/schema.py:86,152`, `harness_rsi/improver_evolution/policy.py:64,72,91,152,461`, `meta_validation.py:50,52`, `single_harness/iterative.py:130-175,1270-1300`, `artifact_rsi/program_opt/script_domain.py:14-60`; `capsule/library.md:60-84`; `schemas/standing.md:10,23`; `plan.md:34-37,75,129`; `.gitcode/`, `run_tests.sh`, `pytest.ini`.
- **3.Y.10.** `schemas/checks.md:18-37`; `schemas/schemas.md:123,131`; `schemas/common.md:40`; `schemas/policy.md:58,70`; `schemas/observation.md:16-39`; `capsule/library.md:57`; `rsi/event_journal.py:15-53`, `task_store.py:3`, `materializer.py:108-127`; agent-core `auto_harness/infra/worktree_manager.py:84-85`; v0.4 §10.1, §10.3, §11.
