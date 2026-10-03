---
type: design
status: draft
version: 1
owner: muk
sources: [../../product/prd-m1-full-2026-10-02.txt]
provides: [research.accept_hypothesis, research.accept_poc, research.accept_benchmark, research.accept_evaluation, research.accept_report, publication.manifest.v1]
consumes: [cc.type.evidence_bundle, cc.type.verifier_assessment]
depends_on: [../capsule/gate-capsules.md, ../capsule/gate-host.md, measurement-protocol.md, delivery.md]
tags: [m1, gate, contract]
---

# Gates from Hypothesis through Delivery

Each named profile selects the shared `research.verifier` capability and uses the single [gate capsule pattern](../capsule/gate-capsules.md): input `evidence_bundle`, output `verifier_assessment`, pure semantic assessment with no workspace mutation. The host runs independent deterministic checks first, commits [Verification](../schemas/verification-record.md), and releases work only through [lifecycle](../system/lifecycle.md). The frozen PRD sets semantic scope; architecture adopts the rubric definitions and fixed checks.

| Gate | Deterministic requirements | Judged criterion IDs and scope | Required validation |
|---|---|---|---|
| research.accept_hypothesis | Blueprint v2 valid; all required Brief targets preserved; snapshot kinds/config/method hashes valid; one claim; repeats/seed/hardware supported; approved non-overlapping predicates | hypothesis_grounded: claim/mechanism derive from the selected card; hypothesis_falsifiable: method and binary predicate can refute the stated claim without manufactured data | registered methods and applicable resources |
| research.accept_poc | All four roles and ZIP members; frozen method/dataset references; genuine syntax evidence; prohibited imports/multi-file edits rejected; registered output adapter | poc_matches_blueprint: the single patch and sequential harness implement the admitted mechanism, preserve baseline and do not change scoring/data | confinement and method fixtures |
| research.accept_benchmark | Raw stdout parses exactly; baseline precedes treatment; paired data/device/config/seed; no forged/null required metrics; zero exit; complete retained capture; checked boundary identity/profile | benchmark_protocol_faithful: captured execution followed the frozen method without introducing uncontrolled conditions | platform confinement fixtures |
| research.accept_evaluation | Comparisons and approved classification independently recompute; evidence completeness matches raw capture; exactly one plausibility turn; no new execution | evaluation_grounded: plausibility rationale and residual risks accurately reflect admitted evidence, without inventing data | applicable method validation |
| research.accept_report | Static template sections; scientific label equals admitted evaluation; all citations resolve; benchmark numbers recompute; all recorded material limitations preserved | report_faithful: findings/method/recommendations follow the admitted evidence and preserve contradictions and scientific failure | Rubric review; no missing template blocker |
| publication.manifest.v1 | Every promised output file equals the stored content; manifest is committed as one directory publication; correct workspace path; no external distribution | The pinned mechanical Gate profile has no semantic criteria, so no Tier 2 judge call is applicable | none |

Every stage uses the same Gate API and result schema. A Gate profile lists every applicable deterministic and semantic criterion; an empty semantic list means no semantic judgment applies, rather than creating an exception. The profile IDs in this table are not capsule identities. Gate-rubric files belong to `cc/gate_profiles/<profile>/rubrics/<criterion_id>.md`, are independently authored, submitted in Candidate.files and pinned by freeze in the run plan. No builder or RSI proposal can modify these referee files.

Check target is the named work output; `over` is inputs_and_outputs for the judged criteria above, `applies_at` is node, and author is the independent referee. The run plan supplies all corresponding work inputs as judge_inputs. Rubric hashes are resolved only from the frozen trusted Gate profile. A missing approved rubric/policy is `POLICY_UNRESOLVED`, never a default pass. Invalid evidence blocks only this stage and successors.

A scientific fail or inconclusive classification is admissible if correctly derived and represented. The Gate may read the label to check that computation; it does not require scientific pass. Unknown or infrastructure INCONCLUSIVE halts. Verify all these cases through the shared [failure-injection surface](../system/verification.md).
