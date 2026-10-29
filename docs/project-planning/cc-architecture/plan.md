# Human plan: CC and Architecture

**Planning date:** October 14, 2026. **Row-level schedule:** [workbook handoff](workbook-handoff.md). This page is the human summary: what we are doing, in what order, and what to work out for M2. The design itself lives in the [design package](../../architecture/design-package/README.md).

## October: the bounded core

October 30 target: one working path from the Intention Compiler through a static fixed DAG, then a Planner-made fixed DAG, verifiers, gates and Delivery, with a benchmark baseline. It uses the fixed Codex route. RSI and new Router work get no human effort before this gate. This is narrower than full PRD M1, and we report it that way.

| Window | Work | Why it sits there |
|---|---|---|
| Oct 13 to 16 | Close one-shot readiness: per-CC contracts, run plan, verifier records, benchmark runner, compact sync | Coding starts Oct 16 from a package an agent can build without guessing. See [one-shot readiness](oneshot-readiness.md) |
| Oct 19 | Investigate the one-shot output (CC) | The busiest day. Architecture stays off it |
| Oct 20 | Classify design defects versus code defects (Architecture) | Uses the first day's findings |
| Oct 21 to 23 | Verifier assignments (CC owner) | Architecture is deliberately free |
| Oct 26 to 28 | Revise the M2 draft and fold in verifier and benchmark results | Uses the M2 PRD draft and the midweek benchmark review |
| Oct 29 to 30 | Feedback form, evidence index, demo | Feeds the Nov 2 to 3 review session |

## November: one feature at a time (M2)

Generalist, then generated capsules, then automatic admission, then better planning, then MCTS. Each increment has its own acceptance before the next starts. Architecture designs December's composition block in parallel and gives support where a critical CC increment lands (admission contract, Planner interfaces).

## Monthly rhythm from December

Each month the Architect designs the next block while the current block is built. The steps are always the same and in the same order: revise and share the draft, merge module-owner designs, adjust from current results and benchmark, release for review, revise and align with the PRD, then freeze. The design can start before the PRD is final, but it does not freeze until it is. Architecture uses Mondays and Tuesdays, and CC uses Wednesdays to Fridays. The gaps give module owners time to write their designs. Later months are provisional, because the Architect role may rotate.

## M2 topics to work out

These are the design questions and analyses for the November block. Settle each one at the step named.

| Topic | What to decide or measure | Where |
|---|---|---|
| Admission gate strictness | Which checks every automatic admission must pass, the cost and time ceiling per admission, rollback, who may override. Trade-off: strict means reliable but slow and costly | CC 1.12.3 with the RSI owner and Benchmark owner. Revisit in 1.13.3 |
| Eligibility semantics | When a new version becomes selectable, how plans pin it, how a version is deprecated, and that running plans never change | Architecture 8.3.5 |
| Generalist contract | Declaration and check bundle for an open-ended capsule. Bounded permissions. How generic outputs are checked | M2 freeze (8.2.4), then 1.4.1 |
| Generation to RSI link | Generalist candidate, then offline RSI improvement, then admission. What RSI may change and who owns the referee | 1.12.1 with the RSI owner |
| Planner quality | Valid-plan rate, coverage, cost and time per plan, rejection reasons, against the October baseline | 1.13.1 |
| MCTS bounds | Search budget, evaluation function (cheap proxy or benchmark), seeds, and proof that the binder keeps authority | 1.13.2 and 8.3.6 |
| Verifier cost | Cost of one verifier call per output across more CCs. Where deterministic checks can be cached | 1.13.3 |
| Benchmark comparability | Frozen case set and repeats so M1 to M2 deltas are fair | Benchmark owner, 1.13.3 |

Analyses to run on M1 data before the Nov 2 review: cost per run by role, failure taxonomy from the benchmark, verifier false-pass and false-block rates, plan rejection reasons, time per node.

## Rules we keep

- Dates are work windows. Overlaps are fine when dependencies hold.
- No subtask is longer than three working days. Milestones are zero days.
- Missing code, access, cases or PRD sections hold the dependent gate. They are never counted as a pass.
- The benchmark sidecar is development tooling and never a product dependency.
- The scientific Research Benchmark CC and the platform benchmark are different things.
