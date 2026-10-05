---
id: cap.search-gate
type: gate-profile
status: draft
version: 2
sources: [../../product/prd-m1-full-2026-10-02.txt]
provides: [research.accept_ideas]
consumes: [cc.type.evidence_bundle, cc.type.verifier_assessment]
depends_on: [../capsule/gate-host.md, README.md]
tags: [m1, gate, profile]
level: detail
prd: [3.3.3, 3.3.6, 4.2.1, 4.2.8]
---

# research.accept_ideas.v1 Gate profile

PRD: 3.3.3, 3.3.6, 4.2.1, 4.2.8

> Answers: Which checks decide whether the candidate idea set is accepted?

This is a pinned profile for the shared `research.verifier`, not a separate [capsule kind](../capsule/capsule.md#term-capsule-kind). Ideas are grounded in cited retained chunks and answer the [Brief](../types/research-brief.md#term-research-brief) within scope. [Tier 1](../verification.md#term-tier-1) verifies source resolution, verbatim local passages, Top-K, one to three ideas and configured size bounds.

The owning [Gate host](../capsule/gate-host.md) evaluates `evaluate(evidence_bundle_ref, gate_profile_ref, request_id) -> verification_ref`. The [frozen](../system/lifecycle.md#term-freeze) bound plan sets `gate_capsule_name: research.verifier` and this profile's immutable reference. Referee rubrics are trusted profile assets with exact hashes, independently authored from work-capsule prompts and excluded from [RSI](../rsi.md#term-rsi) mutation. Missing/unknown evidence [halts](../system/lifecycle.md#term-halt); failed persistence cannot release the next step. Output is a durable [Verification](../schemas/verification-record.md#term-verification), while the verifier itself returns [verifier_assessment](../types/verifier-assessment.md#term-verifier-assessment).

## Criteria

Tier 1 [checks](../capsule/fields.md#term-check) are in the paragraph above. The two judged criteria and their rubrics follow.

## `rubrics/ideas_grounded.md`

```text
Criterion: ideas_grounded.

For each idea, read the chunks its cited_chunk_ids name, in the idea set's groups.

Pass when every idea's summary and mechanism follow from its cited chunks: each claim the idea makes
about what works, or why, is stated or directly implied by a cited chunk.

Fail when any idea claims something no cited chunk supports, or proposes a speculative or contrarian
direction the chunks do not support. Quote the idea's claim, and say which cited chunks fail to support it.

Unknown when the cited chunks are too short to tell.
```

## `rubrics/ideas_answer_brief.md`

```text
Criterion: ideas_answer_brief.

The Research Brief is the research_brief in the bundle's inputs.

Pass when every idea would, if it worked, advance the Brief's objective, and needs nothing the Brief
puts out of scope (out_of_scope_items) or rules out by its constraints.

Fail when any idea answers a different problem, or needs something out of scope or against a constraint.
Quote the idea and the part of the Brief it conflicts with.

Unknown when the Brief's objective is too vague to tell.
```

## `SKILL.md`

```text
---
name: research.verifier
---
You judge a set of candidate research ideas, with the evidence they cite. When a criterion looks at
inputs, the Research Brief is in the bundle's inputs. Follow the judging instructions, and each
criterion's rubric.
```

## Existing code it touches

None directly. It [runs](../system/lifecycle.md#term-run) as a skill through the runner and M05.

## Tests

Three [test cases](../schemas/checks.md#term-test-case), one per pattern check. Their bundles are built from the search [capsule](../capsule/capsule.md#term-capability-capsule)'s [fixtures](../system/test-surfaces.md#term-fixture): one well-grounded [idea set](../types/idea-set.md#term-idea-set), and one whose idea claims more than its chunk says. Each carries `model_replies` and its expected assessment.

## Acceptance seeds

These rows seed the spec AC table. Each is derived from the behavior on this page; the coding spec sets final thresholds and fixtures. Level is [BLOCK](../v-model.md#term-block), [BOUNDARY](../v-model.md#term-boundary) or [SYSTEM](../v-model.md#term-system).

| AC ID | Source | Observable criterion | Level |
|---|---|---|---|
| cap.search-gate.AC-01 | G_node | A well-grounded idea set gives PASS on ideas_grounded and ideas_answer_brief with recorded replies. | BLOCK |
| cap.search-gate.AC-02 | G_node | An idea that claims more than its cited chunk supports gives FAIL on ideas_grounded with the idea claim and the failing chunk ids quoted. | BLOCK |
| cap.search-gate.AC-03 | G_node | An idea that needs something the Brief puts out of scope gives FAIL on ideas_answer_brief. | BLOCK |
| cap.search-gate.AC-04 | G_node | Chunk too short, or Brief objective too vague, gives unknown, so the verdict is INCONCLUSIVE. | BLOCK |
| cap.search-gate.AC-05 | G_node | Tier 1 failure (unresolved source, non-verbatim local passage, Top-K exceeded, 0 or more than 3 ideas, size bound) yields FAIL with 0 verifier calls. | BLOCK |
| cap.search-gate.AC-06 | US-07 | After a failed ideas [Gate](../verification.md#term-gate), 0 screening calls start. | SYSTEM |
