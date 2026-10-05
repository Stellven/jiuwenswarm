---
type: payload-type
id: cc.type.opportunity_card
version: 2
status: draft
tags: [types, m1, screening]
prd: [3.4.4, 3.4.7]
level: detail
---

> **Draft coding-handoff contract.** The canonical architecture shape for PRD 3.4's `Opportunity_Card.json`, with decisions 48–53 fixed in the decision ledger.

# `opportunity_card`: the selected opportunity and screening record · version 2

PRD: 3.4.4, 3.4.7

The winning consolidated opportunity, with its evidence references and the ordered scores and dispositions for every consolidated candidate. It is PRD 3.4's `Opportunity_Card.json`.

**Made by** `research.select_opportunity` at step `screening` ([screening](../capabilities/screening.md)). **Read by** `research.form_hypothesis` at step `hypothesis` ([hypothesis](../capabilities/hypothesis.md)).

## Key terms

| Term | Meaning |
|---|---|
| <a id="term-opportunity-card"></a>**opportunity_card** (also: opportunity card) | The winning consolidated opportunity with its evidence references, plus the ordered scores and dispositions of every consolidated candidate. Screening makes it and the Hypothesis step reads it. |

## Fields

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `card` | `object` | req | checked |  | The selected winning consolidated idea (3.4.7) |
| `card.idea_ids` | `list<id>` | req | checked |  | At least one. Input idea ids represented by this card, sorted lexicographically; more than one means consolidation merged those near-duplicates |
| `card.title` | `text` | req | checked |  | The selected idea's short title (3.4.3) |
| `card.summary` | `text` | req | checked |  | The selected idea in two or three sentences (3.4.3) |
| `card.problem_statement` | `text` | req | checked |  | The technical problem or bottleneck being addressed (3.4.2, 3.4.4) |
| `card.mechanism` | `text` | req | checked |  | The proposed mechanism of action, grounded in the input idea (3.4.2) |
| `card.opportunity_statement` | `text` | req | checked |  | The unmet need or bottleneck and why the proposed method addresses it (3.4.4) |
| `card.relevance` | `text` | req | checked |  | Why this opportunity advances the [Research Brief](research-brief.md#term-research-brief) objective within its scope and constraints |
| `card.linked_citations` | `list<id>` | req | checked |  | Source ids from `idea_set.sources`, sorted and unique (3.4.3) |
| `card.linked_chunk_ids` | `list<id>` | req | checked |  | At least one. Evidence chunk ids cited by the represented input ideas, sorted and unique; these and Brief evidence are the novelty comparison set |
| `card.core_assumptions` | `list<text>` | req | checked |  | Assumptions retained from the represented input ideas (3.4.3) |
| `card.evidence_maturity` | `text` | req | checked |  | Qualitative evidence-strength assessment; not a numeric score |
| `card.verification_path` | `text` | req | checked |  | A credible way to test the opportunity; not a numeric score |
| `card.strategic_context` | `object` | req | checked |  | User value, timing, safety, licensing and resource context preserved for Hypothesis; only dependency assessments control eligibility |
| `card.strategic_context.user_value` | `text` | req | checked |  | Expected technical user value |
| `card.strategic_context.timing` | `text` | req | checked |  | Time-sensitive assumptions or readiness |
| `card.strategic_context.safety` | `text` | req | checked |  | Safety considerations |
| `card.strategic_context.legal_license` | `text` | req | checked |  | Known licensing exposure |
| `card.strategic_context.resources` | `text` | req | checked |  | Resource implications |
| `card.uncertainties` | `list<text>` | req | checked |  | Known uncertainties in the opportunity (3.4.3) |
| `card.identified_risks` | `list<text>` | req | checked |  | Risks that could prevent the opportunity from working (3.4.3) |
| `card.open_questions` | `list<text>` | req | checked |  | Questions that remain about the selected opportunity (3.4.3) |
| `scores` | `list<object>` | req | checked |  | At least one. One row per consolidated candidate, ordered by composite descending then ascending lexicographic sorted `idea_ids` tuple |
| `scores[].idea_ids` | `list<id>` | req | checked |  | At least one. The sorted, unique input idea ids represented by this consolidated candidate |
| `scores[].novelty` | `integer` | req | checked |  | Score from 1 to 5 against Brief and cited Idea evidence |
| `scores[].feasibility` | `integer` | req | checked |  | Score from 1 to 5 for technical feasibility within the stated M1 scope (3.4.5) |
| `scores[].compute_alignment` | `integer` | req | checked |  | Score from 1 to 5 against the Research Brief's compute constraints (3.4.5) |
| `scores[].justifications` | `map<string, text>` | req | checked |  | One evidence-grounded sentence per scored dimension, keyed `novelty`, `feasibility`, and `compute_alignment` (3.4.5) |
| `scores[].composite` | `integer` | req | checked |  | Sum of the three scores, calculated by fixed code; range 3 to 15 (3.4.7) |
| `scores[].rank` | `integer` | req | checked |  | One-based position in the complete ordering; ineligible candidates remain in the ordered record but cannot be selected |
| `scores[].eligible` | `boolean` | req | checked |  | True only when every [dependency assessment](dependency-assessment.md#term-dependency-assessment) is `compatible` |
| `scores[].dependency_assessments` | `list<object>` | req | checked |  | One deterministic policy result per declared dependency; may be empty |
| `scores[].dependency_assessments[].kind` | `enum(package, model, dataset)` | req | checked |  | Registry namespace |
| `scores[].dependency_assessments[].identifier` | `string` | req | checked |  | Canonical registry identity |
| `scores[].dependency_assessments[].version` | `string` | opt | checked |  | Requested version or revision |
| `scores[].dependency_assessments[].status` | `enum(compatible, conflict, unknown)` | req | checked |  | Only compatible preserves eligibility |
| `scores[].dependency_assessments[].registry_entry_ref` | `EvidenceRef?` | req | checked |  | Exact registry evidence, or null for unknown |
| `scores[].dependency_assessments[].reason` | `text` | req | checked |  | Deterministic disposition reason |
| `scores[].dependency_assessments[].registry_sha256` | `sha256` | req | checked |  | Frozen registry version |
| `scores[].rationale` | `text` | req | checked |  | Why the candidate won, or why it was deferred or rejected (3.4.7) |
| `ext` | `map<string, json>` | opt | checked |  | Extensions keyed by producer; consumers ignore them |

## Type checks

| Check | Anchor | Over | Applies at | Runner | Author | What passes |
|---|---|---|---|---|---|---|
| `check.value_matches_type.v1` | deterministic | `outputs` | `both` | `cc/checks/registry/common.py:value_matches_type` | cc-team | the value matches the generated schema |
| `check.opportunity_card_scores_valid.v2` | deterministic | `outputs` | both | `cc/checks/registry/opportunity_card.py:opportunity_card_scores_valid` | cc-team | every score is within 1–5; each row has exactly three justifications; composite equals the sum; ranks follow composite then idea-id tuple; candidate groups are disjoint; eligibility equals all dependency statuses being compatible; the selected card matches the first eligible row |

The producer also has an input-aware check that every `idea_id`, citation, and chunk resolves to the `idea_set`, the linked citations and chunks are supported by the represented input ideas, and every input idea occurs in exactly one score row. That check belongs to the screening [capsule](../capsule/capsule.md#term-capability-capsule) because it needs the input value.

## Example

```json
{
  "card": {
    "idea_ids": ["I1"],
    "title": "IO-aware tiled attention",
    "summary": "Compute attention in tiles that stay in on-chip memory. Avoid materializing the full attention matrix.",
    "problem_statement": "Attention memory grows quadratically with sequence length.",
    "mechanism": "Use tiled exact attention and recompute softmax statistics per tile.",
    "opportunity_statement": "Tiling addresses the memory bottleneck by avoiding storage of the full attention matrix.",
    "relevance": "Targets the Brief's attention-memory objective and its single-GPU constraint.",
    "linked_citations": ["arxiv:2205.14135"],
    "linked_chunk_ids": ["Q1-C1"],
    "core_assumptions": ["The baseline uses standard softmax attention."],
    "evidence_maturity": "The mechanism is described in a cited peer-reviewed paper.",
      "verification_path": "Run baseline and treatment on the same validation inputs and measure peak VRAM.",
      "strategic_context": {
        "user_value": "Reduces the user's stated attention-memory bottleneck.",
        "timing": "Depends on the currently bound PyTorch baseline.",
        "safety": "Changes only the bounded experiment workspace.",
        "legal_license": "Requires only permitted local dependencies.",
        "resources": "Requires the bound single GPU and validation split."
      },
    "uncertainties": ["The custom kernel may not be available on the target GPU."],
    "identified_risks": ["Hardware-specific kernels may reduce portability."],
    "open_questions": ["Does the user's baseline use a compatible attention interface?"]
  },
  "scores": [
    {
      "idea_ids": ["I1"],
      "novelty": 3,
      "feasibility": 4,
      "compute_alignment": 5,
      "justifications": {
        "novelty": "The cited source establishes the tiled approach; its fit to the supplied baseline needs verification.",
        "feasibility": "The mechanism is implementable in a bounded Python/PyTorch patch, subject to kernel availability.",
        "compute_alignment": "The stated approach fits the Brief's single-GPU constraint."
      },
      "composite": 12,
      "rank": 1,
      "eligible": true,
      "dependency_assessments": [],
      "rationale": "Highest-ranked eligible candidate."
    }
  ]
}
```

## History

Version 2 resolves Screening decisions 48–53: three numeric dimensions only, policy-owned dependency assessments, qualitative strategic context, prompt-led skill ownership, deterministic tie-break and explicit no-winner failure.
