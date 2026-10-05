---
id: cap.screening
type: capability
status: draft
version: 2
sources: [../../product/prd-m1-full-2026-10-02.txt, ../types/idea-set.md, ../types/research-brief.md, ../types/screening-assessments.md, ../types/opportunity-card.md, op-rank-opportunities.md, ../capsule/runner.md]
provides: [research.select_opportunity]
consumes: [cc.type.idea_set, cc.type.research_brief, cc.type.screening_assessments, cc.type.opportunity_card, op.rank_opportunities]
depends_on: [../types/idea-set.md, ../types/research-brief.md, ../types/screening-assessments.md, ../types/opportunity-card.md, op-rank-opportunities.md, screening-gate.md, README.md]
tags: [m1, capsule, screening]
level: detail
prd: [3.4.1, 3.4.3, 3.4.4, 3.4.5, 3.4.6, 3.4.7]
---

This page is the home of Screening, the only M1 RSI target ([rsi](../rsi.md)): the rank helper is Target 1, the prompt/rubric text is Target 2 (conditional). Sourced, replaceable defaults are recorded in [decisions](../decisions.md). It is a task node in the research chain template ([capabilities](README.md)).

# `research.select_opportunity`: Screening (PRD 3.4)

PRD: 3.4.1, 3.4.3, 3.4.4, 3.4.5, 3.4.6, 3.4.7

> Answers: How does Screening pick one opportunity from the idea set, and what may RSI change?

## What it does

Screening consolidates the `idea_set`, assesses every consolidated candidate against the [Research Brief](../types/research-brief.md#term-research-brief), asks the deterministic ranking [operator](README.md#term-operator) to apply the dependency filter and ordering, and emits exactly one [`opportunity_card`](../types/opportunity-card.md). It does not search for new evidence or change intake, repository, or dataset state. Its capability name is independent of the M1 stage that currently calls it, following the reusable typed-component style of [Kubeflow](https://www.kubeflow.org/docs/components/pipelines/reference/component-spec/).

The main-path [ports](../capsule/fields.md#term-port) are `idea_set` and `research_brief` in, and `opportunity_card` out. The [capsule](../capsule/capsule.md#term-capability-capsule)'s internal typed handoff to [`op.rank_opportunities`](op-rank-opportunities.md) is `screening_assessments`; that value is not a pipeline Artifact. The producer of `idea_set`, this capsule, the helper, and the consumer at Hypothesis all use the one canonical page for each type.

## Where it sits (ports and contract)

| Port / effect | Contract |
|---|---|
| Input `idea_set` | Required `cc.type.idea_set`, produced by `research.search_ideas`; every idea must be represented exactly once in the consolidated candidate groups. |
| Input `research_brief` | Required `cc.type.research_brief`, produced by `research.compile_brief`; supplies the objective, scope, and compute constraints used for relevance and scoring. |
| Internal helper input `assessments` | Required cc.type.screening_assessments value; contains consolidated candidate content, evidence references, dependencies, scores and justifications. Idea/citation/chunk references must resolve to the two capsule inputs. This local function call creates no nested CC [Observation](../schemas/observation.md#term-observation) |
| Internal helper result `opportunity_card` | Required cc.type.opportunity_card value; selected card and one ordered score/disposition row per consolidated candidate. The wrapper returns it through the sole public output port |
| Main output `opportunity_card` | Required `cc.type.opportunity_card`; emitted only after the helper succeeds. Hypothesis consumes this exact named type. |
| Effects | `read_only`, `reads_external`; no direct network access, filesystem writes, or user interaction. The helper is pure. |
| Failure | All candidates filtered: end the call with the declared failure NO_ELIGIBLE_OPPORTUNITY (Verdict INCONCLUSIVE, halt), emit no output Artifact and halt before Hypothesis. Broker-backed model/runtime failures retain trusted attribution and halt/resume semantics |

The [`opportunity_card`](../types/opportunity-card.md) page defines the complete output shape and deterministic type [checks](../capsule/fields.md#term-check). [`screening_assessments`](../types/screening-assessments.md) defines the private helper input. No second schema is defined here.

## PRD 3.4 behavior promised at the boundary

1. Make one bounded, single-pass consolidation of the at-most-three input ideas, retaining every source idea id and material difference; preserve variants that rely on different mechanisms or baseline papers. Each input idea occurs in exactly one consolidated candidate. Do not iteratively cluster or re-index sources.
2. Form a candidate card from the input ideas and their cited evidence. Preserve all source and chunk references. The candidate carries the PRD 3.4.3/3.4.4 content: title, summary, problem, mechanism, opportunity, relevance, assumptions, evidence maturity, verification path, uncertainties, risks, and open questions.
3. In one bounded LLM [turn](../system/model-bridge.md#term-model-turn) over the full consolidated candidate set, assess each candidate against exactly the PRD's fixed 1–5 dimensions `novelty`, `feasibility`, and `compute_alignment`, with an evidence-grounded one-sentence justification for each. `evidence_maturity` and `verification_path` are required qualitative fields and do not add hidden numeric weights. Novelty compares the candidate to the Brief's cited evidence and the cited Idea evidence. There is no follow-up debate, vote, or live feasibility execution.
4. Declare package, model and dataset dependencies with canonical registry identifiers. The pure helper assesses each against the [frozen](../system/lifecycle.md#term-freeze) registry. Only `compatible` dependencies remain eligible; `conflict` and `unknown` are ineligible. User value, timing, safety, licensing exposure and resource implications remain visible context in the card and rationale; only the [dependency assessment](../types/dependency-assessment.md#term-dependency-assessment) changes M1 eligibility.
5. Call `op.rank_opportunities` once as `rank_opportunities(assessments=<screening_assessments value>)`. It sums the three scores without weights, orders by composite descending and then the ascending lexicographic tuple of sorted source `idea_ids`, and selects the first eligible candidate. Sorting implementation is unspecified.
6. Run deterministic type/provenance checks and the Screening gate. Only an accepted output reaches Hypothesis.

## Declaration (`capsule.json`)

This prompt-led capsule is `kind: tool`: `screening.py:run` is the bounded Python wrapper. It reads its pinned SKILL.md/rubric, makes exactly one brokered cc.model call returning [screening_assessments](../types/screening-assessments.md#term-screening-assessments), validates that internal value against the canonical schema and input references, invokes helpers/rank_opportunities.py once with the frozen dependency registry, and returns the card value. The single-output tool host wraps that value as outputs: {[opportunity_card](../types/opportunity-card.md#term-opportunity-card): card} in its result frame. The intermediate assessments are retained in required model capture, not declared as a pipeline output. No model-directed tool loop or second model turn occurs. The wrapper receives no workflow/release authority.

The generic Markdown skill handler returns declared ports or invokes separately admitted dependencies; it has no local Python postprocessing hook. Reuse the existing [tool handler and SDK](../capsule/runner-handlers.md#tool-a-python-function-in-its-own-process) for this mixed prompt/code implementation. This follows the separation of typed component interfaces from implementation entrypoints in [Kubeflow component specifications](https://www.kubeflow.org/docs/components/pipelines/reference/component-spec/); no new handler profile or capsule is introduced. The required offline [RSI target](../capsule/rsi.md#term-rsi-target) may propose helper code changes preserving exact reference outcomes. Conditional text [RSI](../rsi.md#term-rsi) may propose SKILL.md/rubric changes. The wrapper, provenance checks, dependency policy, schemas and [Gate](../verification.md#term-gate) rubrics stay protected.

```json
{
  "schema_version": "cc.declaration.v1",
  "identity": {
    "name": "research.select_opportunity",
    "kind": "tool",
    "body": [
      {"path": "screening.py", "sha256": "<author kit>"},
      {"path": "SKILL.md", "sha256": "<author kit>"},
      {"path": "rubrics/assess_opportunities.md", "sha256": "<author kit>"},
      {"path": "helpers/rank_opportunities.py", "sha256": "<author kit>"},
      {"path": "references/dependency-registry.json", "sha256": "<canonical frozen registry hash>"}
    ],
    "summary": "Consolidate searched ideas, form evidence-linked opportunity assessments against the Research Brief, and return the top eligible opportunity with a complete deterministic ranking record."
  },
  "ports": {
    "inputs": [
      {"name": "idea_set", "type": "idea_set", "required": true, "description": "The searched candidate ideas and the evidence passages and sources they cite."},
      {"name": "research_brief", "type": "research_brief", "required": true, "description": "The objective, scope, and constraints candidates must answer."}
    ],
    "outputs": [
      {"name": "opportunity_card", "type": "opportunity_card", "check_id": "screening_provenance", "description": "The selected opportunity and the ordered score and eligibility record for every consolidated candidate."}
    ]
  },
  "needs": {
    "when": [],
    "external": [],
    "network": "none",
    "human_interaction": "none",
    "resources": {"timeout_s": 600}
  },
  "changes": {"effect_class": "read_only", "effects": [], "state_kind": "reads_external"},
  "guarantees": {
    "checks": [
      {"id": "screening_provenance", "anchor": "deterministic", "target": "ports.outputs.opportunity_card", "over": "inputs_and_outputs", "applies_at": "both", "runner": {"ref": "checks/screening_checks.py:provenance_is_complete", "sha256": "<author kit>"}, "description": "Every input idea occurs in exactly one consolidated candidate; every output idea id, citation and chunk reference resolves to the idea_set; score rows cover the consolidated groups exactly once; and the selected card equals the first eligible row.", "author": "cc-team"},
      {"id": "matches_reference", "anchor": "reference", "target": "ports.outputs.opportunity_card", "over": "inputs_and_outputs", "applies_at": "admission", "runner": {"ref": "checks/screening_checks.py:matches_reference", "sha256": "<author kit>"}, "description": "On each fixture, the consolidated assessments and final opportunity card match the expected reference values.", "author": "cc-team"}
    ],
    "failure_modes": [{"reason_code": "NO_ELIGIBLE_OPPORTUNITY", "when": "Every consolidated candidate is ineligible under the frozen dependency registry.", "retriable": false}]
  },
  "evolution": {"rsi": "propose", "may_change": ["files:helpers/rank_opportunities.py", "files:SKILL.md", "files:rubrics/assess_opportunities.md"], "notes": "Only offline implementation optimization preserving the rank reference contract and conditional text mutation are allowed; wrapper, checks, dependency policy, output schema and Gate rubrics remain protected."},
  "ext": {"cc": {"entry": "screening.py:run"}}
}
```

## Checks

The checks are the `checks` array in the [Declaration](../capsule/fields.md#term-declaration) above. Gate [Tier 1](../verification.md#term-tier-1) and [Tier 2](../verification.md#term-tier-2) checks are in [Gate and failure semantics](#gate-and-failure-semantics) and the [screening gate](screening-gate.md).

## Gate and failure semantics

The wrapper reads references/dependency-registry.json from its verified read-only capsule root. Author kit materializes the exact canonical policy-registry bytes, not a second registry interpretation; admission/freeze verify that body hash equals the registry selected by the accepted [policy epoch](../schemas/policy.md#term-epoch). This supplies the helper's frozen registry view without adding a public input port, unlisted nested capability or arbitrary filesystem API. Registry shape and eligibility stay defined in [dependency assessment](op-assess-dependency.md). Missing/mismatched registry refuses before the model/helper. RSI freezes this reference file and the wrapper. A registry revision therefore creates a new capsule body/Declaration hash and new run; a future registry broker can replace this materialization boundary through an explicit capsule version.

The step gate is [`research.verifier` with profile `research.accept_card.v1`](screening-gate.md), following the [gate capsule pattern](../capsule/gate-capsules.md). Tier 1 validates type, score arithmetic, ordering, dependency decisions and provenance. Tier 2 assesses that candidates answer the Brief, use its evidence fairly, and that the selected card truthfully represents its source ideas. The [Gate profile](../schemas/profiles.md#term-gateprofile) pins both sets.

`NO_ELIGIBLE_OPPORTUNITY` is a documented work outcome failure, not an empty successful result. There is no `opportunity_card` artifact to judge or pass to Hypothesis. A malformed assessment, unresolved reference, or model reply that cannot be parsed is a capsule error. A local helper or model runtime failure is propagated with its original reason.

The wrapper raises cc.Failure with the declared NO_ELIGIBLE_OPPORTUNITY code when the helper finds no winner. The call ends with outcome error and the declared failure_code NO_ELIGIBLE_OPPORTUNITY, with attributable diagnostics. Because the code is a declared failure mode, the [Gate host](../capsule/gate-host.md#term-gate-host) maps it to decision INCONCLUSIVE with routing HALT and ESCALATE_TO_HUMAN: not FAIL, not a capsule fault and not a scientific negative result. The Gate cannot release, and the run [halts](../system/lifecycle.md#term-halt) before Hypothesis. This single declared mode represents an already required no-winner case and uses its existing verification fixture. It does not enable retries. Malformed assessments remain ordinary capsule errors rather than new declared modes.

## Tests

Recorded model replies and expected assessments, one case per check, as set in the Done-when row of the [prompt brief](#prompt-brief) below; the rank helper has its own [fixtures](../system/test-surfaces.md#term-fixture) in [op-rank-opportunities](op-rank-opportunities.md). Entry points and injectable failures: [test surfaces](../system/test-surfaces.md).

## Prompt brief

The rows of the [prompt brief](../capsule/prompt-brief.md) for `SKILL.md` and `rubrics/assess_opportunities.md`. The wording is the prompt layer's; everything here is fixed. The behaviour is the six promises above.

| Row | Brief |
|---|---|
| Job | Consolidate and assess the input ideas against the Research Brief in one model reply. The Python wrapper validates assessments and invokes the local ranking helper once; model text never overrides its selection |
| Inputs | `idea_set`: the ideas and the evidence passages and sources they cite. `research_brief`: objective, scope and compute constraints |
| Output | Model reply: the [`screening_assessments`](../types/screening-assessments.md) value. Capsule output: the wrapper returns the helper's one opportunity_card through its declared output port |
| Rules | One bounded pass over at most three ideas. Every input idea appears in exactly one consolidated candidate, with every source idea id and chunk reference kept. Variants that rely on different mechanisms or baseline papers stay separate. Score `novelty`, `feasibility` and `compute_alignment` from 1 to 5, each with a one-sentence justification grounded in evidence. `evidence_maturity` and `verification_path` are written, not scored. No hidden weights |
| Grounding | Cite only evidence in the `idea_set` and the Brief. Novelty is judged against the Brief's cited evidence and the ideas' cited evidence |
| Gaps | Declare dependencies by canonical registry id, as decisions 48 to 53 in [decisions](../decisions.md) set. Whether a dependency is eligible is the helper's decision, not the skill's |
| Issue codes | Trusted wrapper emits NO_ELIGIBLE_OPPORTUNITY when local ranking reports no winner; malformed helper input/output becomes OUTPUT_INVALID. Model/helper timeouts use the shared lifecycle. No card is emitted after no-winner |
| Tools | No model-directed tools. Wrapper calls brokered cc.model once, then the pinned ordinary rank_opportunities helper with the frozen registry |
| Must not | Iterate, cluster again, debate or vote. Run a live feasibility test. Add weights. Let value, timing or licensing change eligibility. Search for new evidence. Change intake, repository or dataset state |
| Examples wanted | Three distinct ideas. Two variants of one mechanism. Every candidate in dependency conflict. Equal composite scores, which the helper orders by ascending sorted source idea ids |
| RSI surface | Required offline target: permitted helper-code mutation preserving exact reference outcomes. Conditional text target: `SKILL.md` and `rubrics/assess_opportunities.md`. Checks, ranking semantics, dependency policy, schemas and Gate rubrics stay frozen; mutation modes are separate sessions |
| Done when | The recorded replies reproduce the expected assessments on the fixtures, the provenance checks pass, and the [screening gate](screening-gate.md) accepts |

## Readiness

Generated schemas and example/canary checks exist; runtime evidence is separate. Runtime validation remains a separate obligation. The dependency registry is replaceable through its pinned policy artifact; changing its contents creates a new hash, while changing assessment semantics creates a new operator/profile version.

## Acceptance seeds

These rows seed the spec AC table. Each is derived from the behavior on this page; the coding spec sets final thresholds and fixtures. Level is [BLOCK](../v-model.md#term-block), [BOUNDARY](../v-model.md#term-boundary) or [SYSTEM](../v-model.md#term-system).

| AC ID | Source | Observable criterion | Level |
|---|---|---|---|
| cap.screening.AC-01 | PRD 3.4.1 | Every input idea appears in exactly one consolidated candidate; a missing or duplicated idea id is an output error. | BLOCK |
| cap.screening.AC-02 | PRD 3.4.5 | Each candidate has integer scores 1..5 for novelty, feasibility and compute_alignment, each with a one-sentence justification; the assessment is made in 1 model turn. | BLOCK |
| cap.screening.AC-03 | PRD 3.4.7 | op.rank_opportunities is called exactly once; composite is the unweighted sum; ties break by ascending sorted idea_ids tuple; the first eligible row is selected. | BLOCK |
| cap.screening.AC-04 | PRD 3.4.6, US-10 | When every candidate is conflict or unknown on dependency, the capsule ends with the declared failure NO_ELIGIBLE_OPPORTUNITY, emits no opportunity_card, the Gate host returns INCONCLUSIVE with routing HALT, and the run halts before Hypothesis. | BOUNDARY |
| cap.screening.AC-05 | N_node | A malformed assessment or unresolved reference is an ordinary capsule error, not a declared no-winner mode. | BLOCK |
| cap.screening.AC-06 | N_node | A missing or hash-mismatched dependency registry refuses the call before any model turn. | BLOCK |
| cap.screening.AC-07 | G_node | The card Gate recomputes score arithmetic, order and dependency decisions at Tier 1 and matches the capsule output exactly. | BOUNDARY |
| cap.screening.AC-08 | US-10, V40 | A run with no eligible idea records NO_ELIGIBLE_OPPORTUNITY, creates no empty card, and the Gate host maps the declared failure mode to an INCONCLUSIVE halt ([V40](../system/test-surfaces.md#verification-table)). | SYSTEM |
