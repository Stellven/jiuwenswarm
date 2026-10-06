# Offline RSI: a separate, reusable improvement path

**M1 commitment:** improve a sandbox copy of Screening's pure `rank_opportunities` helper with a fixed improver, retain comparable evidence, and leave live production unchanged. This demonstrates governed capsule self-improvement, not an already self-improving improver. The [master §4.4](sources/product/prd-m1-current-2026-10-06.txt) and [RSI owner source](sources/product/prd-m1-rsi-full.md) define the required behavior; [placement](placement.md#offline-rsi) defines isolation.

## Responsibilities and semantic connections

| Responsibility | Inputs / outputs | Boundary |
|---|---|---|
| Target profile | Eligible immutable parent, explicit mutable files/paths, fixed contract, visible tests, fixture split identities, scoring adapter and improver settings | Target-specific content stays here. Shared engine does not branch on a capsule name. |
| Session controller | Profile, frozen policy/evaluator/configuration, resource budget / session and ordered attempts | One bounded candidate change per iteration; no production DAG participation. Parent/child use comparable effective settings. |
| Proposer | Authorized implementation copy, visible failures and approved aggregate feedback / candidate change and rationale | No hidden cases, oracle secrets, gate/check edits or activation permission. |
| Write guard and isolated child runner | Candidate diff and parent contract / allowed candidate plus visible/parent-test results, or refusal | Trusted enforcement outside mutable code; validate full affected dependency closure. A declaration cannot grant more authority. |
| Fixture oracle and independent referee | Exact parent/child and sealed split identity / permitted counts and protected scoring evidence | Custodian owns hidden data, scoring and lifetime query count. Child runs cannot read expected outputs or the fixture store. |
| Evidence/export builder | Session, attempts, parent/child identities, scoring, limits and violations / reconciled report and allowed paired records | Raw evidence is protected; proposer receives only its permitted view. General export never copies hidden content. |
| Admission and human activation | Candidate, lineage, compatibility and protected evaluation evidence / admitted inactive version or refusal | Explicit human selection affects future runs only; preserve rollback. Target 1's M1 deliverable remains sandbox child/evidence, not a changed live sum/ranking policy. |

No dependency on a finished planner is needed to define these interfaces. The pure helper, fixed parent contract and meaningful fixtures are runtime prerequisites for actual optimization. Native headless calls and existing RSI components are reuse leads; they must cross the shared audited model/evidence boundary rather than create another unaudited model client.

Target 2 may mutate explicitly permitted Screening implementation prompt/rubric text, including approved numerical work-rubric content, while required dimensions and downstream interface remain fixed. A **work scoring rubric** is distinct from a **Verifier/referee rubric**. The latter is always frozen. If bounded headless model execution is unavailable, defer Target 2 to M2 without waiving Target 1.

## Data needed from day one

Keep parent/candidate declaration and implementation identities, interface/frozen-contract identity, target profile, diff/rationale, improver version/policy, evaluator/scoring/split identities, model/configuration identity, call/time observations, visible and protected comparison outcomes, query counters, stop reason, violations, admission and activation history. Associate all evidence with session/attempt and applicable run/export provenance. Record unsupported fields as unavailable, not invented measurements.

Development data, hidden-loop, hidden-final and milestone/platform data are distinct partitions with overlap checks and explicit permitted consumers. An exported failure case can become development material only through its allowed audience; it does not become a hidden expected answer in the proposer context. Keep hidden-final results out of future proposal feedback.

The owner source's M1 protocol includes **30 hidden-loop queries per session and 90 per loop-set lifetime**, loop feedback restricted to passed/total/queries-left, and final evaluation once per session by the custodian. Preserve its fixture-size/headroom and planted-child calibration requirements (including at least 20 cases per hidden split, 10 known-bad and 3 known-good planted children), paired comparison rules and model-backed repeated-fixture aggregation. These are supplied requirements, not newly chosen architecture thresholds. Concrete scoring/repetition procedures must be copied from the exact current owner clauses into native specifications; no majority-vote shortcut or success-rate claim may replace them.

Admission follows allowed change, parent-test preservation, contract compatibility and evidence integrity. A stronger score alone is insufficient. Execute and reconcile the required security/violation suite: hidden reads/leaks, referee tampering, forbidden mutation, permission escalation, evidence tampering, resource abuse and promotion bypass. [Callback rules](failure-and-human.md#offline-rsi-is-a-separate-callback-policy) distinguish expected candidate rejection from session/security failure and human activation.

## Future recursion without weakening the referee

Version the improver's proposal policy, target selection, context recipe and decision evidence now, even though M1 keeps them fixed. A future eligible improver change is itself a candidate evaluated on held-out **improvement tasks**, with improver-quality measures separate from capsule score. The improved component must actually drive later rounds to justify a recursive claim. Keep referee, hidden-suite author, oracle, hard limits, security, contracts and evidence authority outside both mutation levels.

A shared loop plus target profiles should allow a new deterministic development target without rewriting oracle, guard or record logic. Richer optimizers, multiple candidates, learned judges, new hidden-suite generation, cross-capsule credit, fusion and live installation remain separate future decisions. Preserve the interfaces and observations now; do not implement speculative optimization machinery to fill out a field list.

## Approved reference retrieval

“Offline” means outside the live research DAG, with controlled isolated evaluation; it is not an absolute ban on approved reference access. Latest §§1.3/4.4.9 permit allowlisted read-only public benchmark/repository retrieval. Protected preparation records origin, license/provenance, immutable revision/content hash and local snapshot before session use. Public references remain separate from hidden-loop/final data; no uncontrolled network, external write or hidden-data transmission is authorized. A missing approved reference blocks only the dependent profile; locally prepared Target 1 fixtures need not wait for network access.
