---
type: design
status: draft
version: 2
owner: muk
sources: [../../product/prd-m1-full-2026-10-02.txt]
provides: [research.accept_ideas]
consumes: [cc.type.evidence_bundle, cc.type.verifier_assessment]
depends_on: [../capsule/gate-host.md, pipeline.md]
tags: [m1, gate, profile]
---

# research.accept_ideas.v1 Gate profile

This is a pinned profile for the shared `research.verifier`, not a separate capsule Declaration. Ideas are grounded in cited retained chunks and answer the Brief within scope. Tier 1 verifies source resolution, verbatim local passages, Top-K, one to three ideas and configured size bounds.

The owning [Gate host](../capsule/gate-host.md) evaluates `evaluate(evidence_bundle_ref, gate_profile_ref, request_id) -> verification_ref`. The run plan sets `gate_capsule_name: research.verifier` and this profile's immutable reference. Referee rubrics are trusted profile assets with exact hashes, independently authored from work-capsule prompts and excluded from RSI mutation. Missing/unknown evidence halts; failed persistence cannot release the next step. Output is a durable Verification, while the verifier itself returns verifier_assessment.

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

None directly. It runs as a skill through the runner and M05.

## Tests

Three test cases, one per pattern check. Their bundles are built from the search capsule's fixtures: one well-grounded idea set, and one whose idea claims more than its chunk says. Each carries `model_replies` and its expected assessment.
