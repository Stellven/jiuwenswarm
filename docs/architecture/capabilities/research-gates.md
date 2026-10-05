---
id: cap.research-gates
type: gate-profile
status: draft
version: 1
sources: [../../product/prd-m1-full-2026-10-02.txt]
provides: [research.accept_hypothesis, research.accept_poc, research.accept_benchmark, research.accept_evaluation, research.accept_report]
consumes: [cc.type.evidence_bundle, cc.type.verifier_assessment]
depends_on: [../capsule/gate-capsules.md, ../capsule/gate-host.md, measurement-protocol.md, write-report.md]
tags: [m1, gate, contract]
level: detail
prd: [4.2.1, 4.2.8, 3.5.4, 3.6.4, 3.7.4, 3.8.5, 3.9.2, 3.9.4]
---

# Gates from Hypothesis through Report

PRD: 4.2.1, 4.2.8, 3.5.4, 3.6.4, 3.7.4, 3.8.5, 3.9.2, 3.9.4

> Answers: Which deterministic and judged criteria does each Gate profile from Hypothesis through Report apply?

These are profiles of the one shared verifier, not separate [capsules](../capsule/capsule.md#term-capability-capsule). Each named profile selects the shared `research.verifier` capability and uses the single [gate capsule pattern](../capsule/gate-capsules.md): input `evidence_bundle`, output `verifier_assessment`, pure semantic assessment with no workspace mutation. The host [runs](../system/lifecycle.md#term-run) independent deterministic [checks](../capsule/fields.md#term-check) first, commits [Verification](../schemas/verification-record.md), and [releases](../system/lifecycle.md#term-release) work only through [lifecycle](../system/lifecycle.md). The [frozen](../system/lifecycle.md#term-freeze) PRD sets semantic scope; architecture adopts the rubric definitions and fixed checks.

## Criteria

| [Gate](../verification.md#term-gate) | Deterministic requirements | Judged criterion IDs and scope | Required validation |
|---|---|---|---|
| research.accept_hypothesis | Blueprint v2 valid; all required [Brief](../types/research-brief.md#term-research-brief) targets preserved; [snapshot](../capsule/library.md#term-library-snapshot) kinds/config/method hashes valid; one claim; repeats/seed/hardware supported; approved non-overlapping predicates | hypothesis_grounded: claim/mechanism derive from the selected card; hypothesis_falsifiable: method and binary predicate can refute the stated claim without manufactured data | registered methods and applicable resources |
| research.accept_poc | All four roles and ZIP members; frozen method/dataset references; genuine syntax evidence; prohibited imports/multi-file edits rejected; registered output adapter | poc_matches_blueprint: the single patch and sequential harness implement the admitted mechanism, preserve baseline and do not change scoring/data | confinement and method [fixtures](../system/test-surfaces.md#term-fixture) |
| research.accept_benchmark | Raw stdout parses exactly; baseline precedes treatment; paired data/device/config/seed; no forged/null required metrics; zero exit; complete retained capture; checked boundary identity/profile | benchmark_protocol_faithful: captured execution followed the frozen method without introducing uncontrolled conditions | platform confinement fixtures |
| research.accept_evaluation | Comparisons and approved classification independently recompute; evidence completeness matches raw capture; exactly one plausibility [turn](../system/model-bridge.md#term-model-turn); no new execution | evaluation_grounded: plausibility rationale and residual risks accurately reflect admitted evidence, without inventing data | applicable method validation |
| research.accept_report | Static template sections; scientific label equals admitted evaluation; all citations resolve; benchmark numbers recompute; all recorded material limitations preserved | report_faithful: findings/method/recommendations follow the admitted evidence and preserve contradictions and scientific failure | Rubric review; no missing template blocker |

Delivery has no [Gate profile](../schemas/profiles.md#term-gateprofile): its [Tier 1](../verification.md#term-tier-1) check lives in [delivery](delivery.md#publication-manifest-check). Every Gate stage uses the same Gate API and result schema. A Gate profile lists every applicable deterministic and semantic criterion; an empty semantic list means no semantic judgment applies, rather than creating an exception. The profile IDs in this table are not capsule identities. Gate-rubric files live in `cc/gate_profiles/<profile>/rubrics/<criterion_id>.md`, are independently authored, submitted in Candidate.files and pinned by freeze in the bound plan. No builder or [RSI](../rsi.md#term-rsi) proposal can modify these referee files.

Check target is the named work output; `over` is inputs_and_outputs for the judged criteria above, `applies_at` is node, and author is the independent referee. The frozen bound plan supplies all corresponding work inputs as judge_inputs. Rubric hashes are resolved only from the frozen trusted Gate profile. A missing approved rubric/policy is `POLICY_UNRESOLVED`, never a default pass. Invalid evidence [blocks](../system/modules.md#term-block) only this stage and successors.

A scientific fail or inconclusive classification is admissible if correctly derived and represented. The Gate may read the label to check that computation; it does not require scientific pass. Unknown or infrastructure INCONCLUSIVE [halts](../system/lifecycle.md#term-halt). Verify all these cases through the shared [failure-injection surface](../system/test-surfaces.md).

## Acceptance seeds

These rows seed the spec AC table. Each is derived from the criteria table above; the coding spec sets final thresholds and fixtures. Level is BLOCK, [BOUNDARY](../v-model.md#term-boundary) or [SYSTEM](../v-model.md#term-system).

| AC ID | Source | Observable criterion | Level |
|---|---|---|---|
| cap.research-gates.AC-01 | PRD 3.5.4 | The hypothesis profile applies the deterministic checks and judged criteria in its row; a missing approved rubric or policy is POLICY_UNRESOLVED, never a default pass. | BOUNDARY |
| cap.research-gates.AC-02 | PRD 3.7.4 | A scientific fail or inconclusive classification that is correctly derived and represented passes the Gate; an unknown or infrastructure INCONCLUSIVE halts. | BOUNDARY |
| cap.research-gates.AC-03 | PRD 4.2.8 | Each stage uses the same Gate API and result schema; invalid evidence blocks only that stage and its successors. | SYSTEM |
| cap.research-gates.AC-04 | PRD 3.9.4 | The report Gate profile is the last Gate profile in this table; publication.manifest.v1 is not a Gate profile and is checked by the delivery module ([delivery](delivery.md#publication-manifest-check)). | BLOCK |
