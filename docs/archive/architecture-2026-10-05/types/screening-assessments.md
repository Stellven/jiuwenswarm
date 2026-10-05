---
type: payload-type
id: cc.type.screening_assessments
version: 2
status: draft
tags: [types, m1, screening]
prd: [3.4.5]
level: detail
---

> **Draft coding-handoff contract.** The typed handoff from `research.select_opportunity` to the pure ranking/filter helper.

# `screening_assessments`: assessed consolidated opportunities · version 2

PRD: 3.4.5

The model-backed screening [capsule](../capsule/capsule.md#term-capability-capsule)'s structured assessments, before deterministic dependency filtering, score addition, ranking, and winner selection. This value is passed only to [`op.rank_opportunities`](../capabilities/op-rank-opportunities.md); it is not a pipeline artifact.

**Made by** `research.select_opportunity`. **Read by** `op.rank_opportunities` through a nested CC call.

## Key terms

| Term | Meaning |
|---|---|
| <a id="term-screening-assessments"></a>**screening_assessments** (also: screening assessments) | The model-backed screening capsule's structured assessments, before deterministic filtering, scoring and ranking. It is passed only to the ranking operator and is not a pipeline artifact. |

## Fields

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `candidates` | `list<object>` | req | checked |  | At least one. One entry per consolidated input candidate, in first-source-idea order; never more candidates than input ideas |
| `candidates[].idea_ids` | `list<id>` | req | checked |  | At least one. Unique input `idea_set.ideas[].idea_id` values represented by this candidate, sorted lexicographically |
| `candidates[].title` | `text` | req | checked |  | Candidate title (3.4.3) |
| `candidates[].summary` | `text` | req | checked |  | Candidate summary in two or three sentences (3.4.3) |
| `candidates[].problem_statement` | `text` | req | checked |  | The technical problem or bottleneck (3.4.2, 3.4.4) |
| `candidates[].mechanism` | `text` | req | checked |  | Proposed mechanism grounded in the input idea (3.4.2) |
| `candidates[].opportunity_statement` | `text` | req | checked |  | The unmet need or bottleneck and why the method addresses it (3.4.4) |
| `candidates[].relevance` | `text` | req | checked |  | Alignment to the [Research Brief](research-brief.md#term-research-brief) objective, scope, and constraints |
| `candidates[].linked_citations` | `list<id>` | req | checked |  | At least one. Source ids from `idea_set.sources`, sorted and unique |
| `candidates[].linked_chunk_ids` | `list<id>` | req | checked |  | At least one. Supporting chunk ids from the represented ideas, sorted and unique |
| `candidates[].core_assumptions` | `list<text>` | req | checked |  | Assumptions retained from represented ideas |
| `candidates[].evidence_maturity` | `text` | req | checked |  | Qualitative evidence-strength assessment; it is context, not a fourth score |
| `candidates[].verification_path` | `text` | req | checked |  | A credible bounded path to test the candidate; it is context, not a fourth score |
| `candidates[].strategic_context` | `object` | req | checked |  | Visible non-ranking context from PRD 3.4.6 |
| `candidates[].strategic_context.user_value` | `text` | req | checked |  | Expected technical user value |
| `candidates[].strategic_context.timing` | `text` | req | checked |  | Time-sensitive assumptions or readiness |
| `candidates[].strategic_context.safety` | `text` | req | checked |  | Safety considerations without inventing a formal audit |
| `candidates[].strategic_context.legal_license` | `text` | req | checked |  | Known licensing exposure; deterministic eligibility still comes only from registry facts |
| `candidates[].strategic_context.resources` | `text` | req | checked |  | Resource implications beyond the numeric compute score |
| `candidates[].uncertainties` | `list<text>` | req | checked |  | Known uncertainties (3.4.3) |
| `candidates[].identified_risks` | `list<text>` | req | checked |  | Risks that could prevent the opportunity from working (3.4.3) |
| `candidates[].open_questions` | `list<text>` | req | checked |  | Questions that remain (3.4.3) |
| `candidates[].dependencies` | `list<object>` | req | checked |  | Declared package, model and dataset requirements for deterministic assessment |
| `candidates[].dependencies[].kind` | `enum(package, model, dataset)` | req | checked |  | Registry namespace |
| `candidates[].dependencies[].identifier` | `string` | req | checked |  | Canonical registry identity, never a display name |
| `candidates[].dependencies[].version` | `string` | opt | checked |  | Exact version or revision when required |
| `candidates[].dependencies[].evidence` | `text` | req | checked |  | Candidate text supporting the dependency declaration |
| `candidates[].novelty` | `integer` | req | checked |  | Score from 1 to 5 against baseline approaches in Brief evidence and cited Idea evidence |
| `candidates[].feasibility` | `integer` | req | checked |  | Score from 1 to 5 (3.4.5) |
| `candidates[].compute_alignment` | `integer` | req | checked |  | Score from 1 to 5 against Research Brief compute constraints (3.4.5) |
| `candidates[].justifications` | `map<string, text>` | req | checked |  | One evidence-grounded sentence per scored dimension, keyed by its score name (3.4.5) |
| `ext` | `map<string, json>` | opt | checked |  | Extensions keyed by producer; consumers ignore them |

## Type checks

| Check | Anchor | Over | Applies at | Runner | Author | What passes |
|---|---|---|---|---|---|---|
| `check.value_matches_type.v1` | deterministic | `outputs` | `both` | `cc/checks/registry/common.py:value_matches_type` | cc-team | the value matches the generated schema |
| `check.screening_assessments_valid.v1` | deterministic | `outputs` | `both` | `cc/checks/registry/screening.py:screening_assessments_valid` | cc-team | there are at most three candidates; scores are 1–5; each candidate has exactly the three defined score keys and matching justification keys; candidate `idea_ids` groups are sorted, disjoint, and partition the input ideas; all candidate, citation, and chunk references resolve against the capsule inputs |

## Example

```json
{
  "candidates": [
    {
      "idea_ids": ["I1"],
      "title": "IO-aware tiled attention",
      "summary": "Compute exact attention in tiles that stay in on-chip memory. Avoid materializing the full attention matrix.",
      "problem_statement": "Attention memory grows quadratically with sequence length.",
      "mechanism": "Use tiled exact attention and recompute softmax statistics per tile.",
      "opportunity_statement": "Tiling addresses the memory bottleneck by avoiding storage of the full attention matrix.",
      "relevance": "Targets the Brief's attention-memory objective and single-GPU constraint.",
      "linked_citations": ["arxiv:2205.14135"],
      "linked_chunk_ids": ["Q1-C1"],
      "core_assumptions": ["The baseline uses standard softmax attention."],
      "evidence_maturity": "The mechanism is described in a cited peer-reviewed paper.",
      "verification_path": "Run baseline and treatment on the same validation inputs and measure peak VRAM.",
      "strategic_context": {
        "user_value": "Reduces the user's stated attention-memory bottleneck.",
        "timing": "Depends on the currently bound PyTorch baseline.",
        "safety": "Changes only the bounded experiment workspace.",
        "legal_license": "Requires only dependencies marked permitted in the registry.",
        "resources": "Requires the bound single GPU and validation split."
      },
      "uncertainties": ["The custom kernel may not be available on the target GPU."],
      "identified_risks": ["Hardware-specific kernels may reduce portability."],
      "open_questions": ["Does the user's baseline use a compatible attention interface?"],
      "dependencies": [],
      "novelty": 3,
      "feasibility": 4,
      "compute_alignment": 5,
      "justifications": {
        "novelty": "The cited source establishes tiled attention; its fit to the supplied baseline needs comparison.",
        "feasibility": "The mechanism is implementable in a bounded Python/PyTorch change, subject to kernel availability.",
        "compute_alignment": "The stated approach fits the Brief's single-GPU constraint."
      }
    }
  ]
}
```

## History

Version 2 fixes the three numeric dimensions, keeps maturity, verification and strategic factors as qualitative context, adds package dependencies and canonical identifiers, and binds eligibility to the policy-owned registry.
