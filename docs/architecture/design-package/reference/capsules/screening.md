# Screening CC (`research.screening`)

`Tier 3 · Part of: [Reference](../README.md)`

**Summary for reviewers.**
- Screening reads the candidate set and scores every idea 1 to 5 on three fixed dimensions: novelty, feasibility and compute alignment. A pinned rubric defines the dimensions and what each score means.
- A deterministic filter rejects ideas that need a forbidden dependency. A pure helper, `rank_opportunities`, adds the scores and ranks the eligible ideas. Ties go to the lower `idea_id`.
- It outputs two artifacts: `screening_result` (all scores, reasons, ranking, dispositions) and `opportunity_card` (exactly one selected idea).
- The RSI workbench may change the ranking helper (Target 1), the work prompt `screening_prompt.txt` and the work rubric `screening_rubric.json` (Target 2, conditional). The referee and its rubrics stay frozen.
- The verifier runs once for each output, `screening_result` and `opportunity_card`, each time with the same declaration. The gate accepts the pair together.
- Old names "Idea Screening" and the `screening` declaration name mean this CC. The CC name is `research.screening`.

## Purpose and place in the run

Screening reads a candidate set and selects one opportunity. It does not search and it does not design experiments. The model scores ideas in one pass. The helper then does the arithmetic and ranking in code.

## Declaration

Declaration example: [screening_capsule.json](../examples/screening_capsule.json). It validates against the [declaration schema](../schemas/capsule-declaration.schema.json). It replaces the older declaration of the same name. The older `discovery_capsule.json` is removed. [search_capsule.json](../examples/search_capsule.json) replaces it.

| Item | Value |
|---|---|
| Name and kind | `research.screening`, kind `agent` |
| Inputs | `brief`, `candidate_set`, `screening_rubric` |
| Outputs | `screening_result` (`screening-result:field-contract:2`), `opportunity_card` (`opportunity-card:field-contract:2`). The verifier runs once for each output, each time with this same declaration |
| Needs | The model bridge, text only. Read access to the `original_request` resource. No network. The rubric, the work prompt and the ranking helper are pinned in the body |
| Effect class | `read_only` |
| Budget | 120 s wall time, 1 invocation, 0 tool calls, all hard |
| Checks | The bundle in the deterministic check table below, then the semantic criteria below |
| Evolution | `rsi` `propose`. `may_change` is `files:ranking_*.txt` (the ranking helper), `files:screening_prompt.txt` (the work prompt) and `files:screening_rubric.json` (the work rubric). Nothing else may change ([D34](../../method/decisions.md#d34)) |

## Inputs

| Port | Artifact type | Producer | Required | Use |
|---|---|---|---|---|
| `brief` | `research_brief` | Requirements CC | yes | Hardware and scope constraints for compute alignment. Source of the constraints the card carries |
| `candidate_set` | `candidate_set` | Search CC | yes | The 1 to 3 ideas to score |
| `screening_rubric` | `screening_rubric` | Pinned in the CC version | yes | The frozen scoring policy |

### `screening_rubric` field contract

Purpose: the frozen scoring policy of Screening. It is pinned by hash in the declaration body. Only a new CC version may change it. The RSI workbench may never change it.

`screening-rubric:field-contract:1` (version 1.0.0) · Producer: the Screening CC owner, pinned in the CC body. Consumers: Screening CC, Screening host checks (`rubric_pinned`, `score_range`, `dependency_filter`, `ranking_deterministic`, `selected_is_top1`).

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | `string` | yes | `1.0.0` | Format version |
| `id` | `string` | yes | `screening_rubric` | Record identity |
| `dimensions` | `RubricDimension[]` | yes | Exactly 3 items with `name` values `novelty`, `feasibility`, `compute_alignment`, once each | The scoring dimensions. The set is closed in M1. Each `name` is also the score field name in `IdeaScore`. |
| `total_rule` | `string` | yes | `sum` | A total is the plain sum of the three scores |
| `tie_rule` | `string` | yes | `ascending_idea_id` | Equal totals rank the lower `idea_id` first, compared as plain strings |
| `selection_rule` | `string` | yes | `top_1` | Exactly one idea is selected, the first in the ranking |
| `forbidden_dependencies` | `ForbiddenDependency[]` | yes | 0 or more items. `id` values unique | Dependencies that make an idea ineligible. An empty list means no idea can be filtered out. The host does the term matching, not the model. |
| `reason_max_chars` | `integer` | yes | 50 to 500 | Longest allowed score reason or disposition reason, in characters. Applies to every `*_reason` and `disposition_reason` in the result. |

`RubricDimension`

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `name` | `string` | yes | `novelty`, `feasibility` or `compute_alignment` | Dimension name. It is also the score field name |
| `scale_min` | `integer` | yes | `1` | Lowest score |
| `scale_max` | `integer` | yes | `5` | Highest score |
| `anchors` | `ScoreAnchor[]` | yes | Exactly 5 items, one per score 1 to 5 | What each score means. The scorer picks the anchor that fits and does not invent other levels. |

`ScoreAnchor`

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `score` | `integer` | yes | 1 to 5 | The score this anchor defines |
| `description` | `string` | yes | 1 to 200 characters | What an idea must look like to earn this score |

`ForbiddenDependency`

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `id` | `string` | yes | Pattern `^dep:[a-z0-9_]+$` | The flag ID. It appears in a score row's `dependency_flags` when the dependency applies. |
| `description` | `string` | yes | 1 to 200 characters | What the dependency is and why it is forbidden |
| `match_terms` | `string[]` | yes | 1 or more lowercase phrases | Lowercase phrases that always trigger the flag. The host lowercases idea `title`, `summary`, `assumptions` and `risks` and flags the idea when any phrase occurs as a plain substring. No word boundaries, stemming or model judgment. The model does not decide matches. |

**Enum `RubricDimension.name`**

| Value | Meaning |
|---|---|
| `novelty` | How different the idea is from the baseline approaches |
| `feasibility` | How plausible the idea is in standard Python and PyTorch |
| `compute_alignment` | How well the idea fits the hardware limits in the Brief |

**Enum `total_rule`**

| Value | Meaning |
|---|---|
| `sum` | The total is the plain sum of the three scores |

**Enum `tie_rule`**

| Value | Meaning |
|---|---|
| `ascending_idea_id` | Equal totals rank the lower `idea_id` first, compared as plain strings |

**Enum `selection_rule`**

| Value | Meaning |
|---|---|
| `top_1` | The first idea in the ranking is the only selection |

**Invariants**

- The three dimension names appear once each.
- Each dimension has one anchor for every score from `scale_min` to `scale_max`, so 1 to 5.
- `forbidden_dependencies` IDs are unique.

**Producer obligations (CC owner)**

- Write anchors a scorer can apply without the Brief's wording.
- A new rubric is a new CC version. An RSI child may carry one only through Target 2, when the headless model path exists, and only if it passes admission checks `rubric_structure` and `rubric_dimensions_complete`.

**Host checks**

| Check ID | Rule | Outcome |
|---|---|---|
| `rubric_structure` | The rubric matches `screening-rubric:field-contract:1` | admission rejects the CC version |
| `rubric_dimensions_complete` | The invariants above hold | admission rejects the CC version |
| `rubric_pinned` | The result's `rubric_ref` equals the rubric pinned in the declaration | reject the Screening output |

**Failure outcomes**

| Condition | Outcome | What is kept |
|---|---|---|
| The rubric fails a structure check at admission | The CC version is `rejected` | The admission record |
| A result names another rubric | The Screening output is rejected and the node halts | The output and the check result |

Examples: [valid](../examples/screening_rubric.json)

**Minimum quality bar.** Two scorers who read the same idea and this rubric give the same scores, ranking and selection.

## Output field contract

Version 2 of `screening-result` and `opportunity-card` replaces version 1. Changes are listed in the fragment.

### `screening_result`

`screening-result:field-contract:2`

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | `string` | yes | `2.0.0` | Format version |
| `id` | `string` | yes | `screening_result` | Record identity |
| `candidate_ref` | `Ref` | yes | Equals the `candidate_set` input | The exact set that was scored |
| `brief_ref` | `Ref` | yes | Equals the `brief` input | The Brief used |
| `rubric_ref` | `Ref` | yes | Equals the pinned rubric | The rubric used |
| `scores` | `IdeaScore[]` | yes | Exactly one row for each idea in the candidate set, none extra | Every idea's scores, reasons and fate. Written by the CC (untrusted). The host checks it against the candidate set and recomputes the totals. |
| `ranking` | `Ranking[]` | yes | One row for each idea whose disposition is `selected` or `eligible`. Ordered by `total` descending, then `idea_id` ascending. `rank` counts 1, 2, 3 | The ranked order of the selected and eligible ideas only. The host recomputes the order and rejects any difference (`ranking_deterministic`). |
| `selected_idea_id` | `string` | yes | Equals `ranking[0].idea_id` and is a candidate idea | The single selected idea |

`IdeaScore`

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `idea_id` | `string` | yes | An `idea_id` in the candidate set | The idea scored |
| `novelty` | `integer` | yes | 1 to 5 | How different the idea is from the baseline approaches in the Brief and citations. Scored by the CC with the rubric anchors. Integer, 1 lowest. |
| `feasibility` | `integer` | yes | 1 to 5 | How plausible the idea is in standard Python and PyTorch. Scored by the CC with the rubric anchors. Integer, 1 lowest. |
| `compute_alignment` | `integer` | yes | 1 to 5 | How well the idea fits the hardware limits in the Brief. Scored by the CC with the rubric anchors. Integer, 1 lowest. |
| `total` | `integer` | yes | 3 to 15. Equals `novelty + feasibility + compute_alignment` | The composite score, the plain sum of the three scores. The host checks it (`score_total_sum`). |
| `novelty_reason` | `string` | yes | One sentence, 1 to `reason_max_chars` characters | Why this novelty score and not the next one up or down. Free text for people. A semantic criterion reviews it (`reasons_address_dimension`). No host check parses it. |
| `feasibility_reason` | `string` | yes | Same | Why this feasibility score. Free text reviewed by `reasons_address_dimension`. No host check parses it. |
| `compute_alignment_reason` | `string` | yes | Same | Why this compute alignment score. Free text reviewed by `reasons_address_dimension`. No host check parses it. |
| `citation_ids` | `string[]` | yes | 1 or more. Each is in this idea's `citation_ids` in the candidate set | The evidence ids behind the scores. Each must be one this idea cites in the candidate set (`score_citations_in_idea`). |
| `dependency_flags` | `string[]` | yes | Each is a rubric `ForbiddenDependency.id`. Must include every flag the host term match finds | Forbidden dependencies the idea has. The host finds hits by term match, and the CC must include every one (`dependency_filter`). Empty list means none apply. |
| `eligible` | `boolean` | yes | `false` exactly when `dependency_flags` is not empty | Whether the idea may be ranked. Derived from `dependency_flags`, not a separate judgement. |
| `disposition` | `string` | yes | `selected`, `eligible`, `rejected` or `deferred` | The idea's fate. See the rules below |
| `disposition_reason` | `string` | yes | 1 to `reason_max_chars` characters | Why this fate. Names the cause, not only the label. Free text for people, reviewed by `disposition_reasons_specific`. |

Disposition rules:

| Value | Rule |
|---|---|
| `selected` | The top-ranked eligible idea. Exactly one idea has it |
| `eligible` | Passed the filter and ranked below the selected idea |
| `rejected` | Failed the filter, so `eligible` is `false` |
| `deferred` | Passed the filter but set aside for a recorded reason, so it is not ranked. The M1 helper never produces it. The value is reserved for later portfolio work |

`Ranking`

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `rank` | `integer` | yes | 1 or more. Rows count up from 1 without gaps | Position in the order, counted from 1. |
| `idea_id` | `string` | yes | An idea with disposition `selected` or `eligible` | The ranked idea |
| `total` | `integer` | yes | Equals the idea's `total` in `scores` | The composite used to rank |

Examples: [valid](../examples/screening_result.json)

### `opportunity_card`

`opportunity-card:field-contract:2`. This is the single settled field table. The older summary listed purpose, original scores, ranking refs and dispositions that the older field table lacked. Version 2 includes them all.

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | `string` | yes | `2.0.0` | Format version |
| `id` | `string` | yes | `opportunity_card` | Record identity |
| `candidate_ref` | `Ref` | yes | Equals the `candidate_set` input | The set the idea came from |
| `screening_ref` | `Ref` | yes | Equals the `screening_result` produced with this card | The scoring and ranking behind the selection (the ranking reference) |
| `brief_ref` | `Ref` | yes | Equals the `brief` input | The Brief whose obligations the card carries. Must be the input Brief. |
| `idea_id` | `string` | yes | Equals `screening_result.selected_idea_id` and is a candidate idea | The one selected idea |
| `title` | `string` | yes | Equals the idea's `title` | Readable name |
| `summary` | `string` | yes | 1 to 600 characters | The card's purpose: what would be tested and why, in plain words. Free text written by the CC for the next node. |
| `opportunity_statement` | `string` | yes | 1 to 800 characters | The evidence-grounded bottleneck and why the idea's mechanism addresses it |
| `scores` | `ScoreSet` | yes | Equals the idea's scores in `screening_result` | The original scores, copied unchanged from the idea's row in `screening_result`. Never rescored. |
| `rank` | `integer` | yes | `1` | Rank in the ranking. Always 1 for the selected idea |
| `citation_ids` | `string[]` | yes | 1 or more. Equals the idea's `citation_ids` | Supporting citations |
| `constraints` | `string[]` | yes | Contains the verbatim `text` of every Brief constraint and every Brief mandatory requirement | Limits Hypothesis must respect. Copied verbatim from the Brief, never paraphrased (`card_constraints_carried`). |
| `assumptions` | `string[]` | yes | Equals the idea's `assumptions` | Unproven premises of the idea, copied from the candidate set. |
| `risks` | `string[]` | yes | Equals the idea's `risks` | Known concerns about the idea, copied from the candidate set. |
| `other_dispositions` | `Disposition[]` | yes | One row for each candidate idea except the selected one | What happened to every idea that was not selected, one row each. Empty when the candidate set holds one idea. Must equal the screening dispositions and reasons (`card_dispositions_complete`). |

`ScoreSet`

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `novelty` | `integer` | yes | 1 to 5 | Novelty score, copied from the result. |
| `feasibility` | `integer` | yes | 1 to 5 | Feasibility score, copied from the result. |
| `compute_alignment` | `integer` | yes | 1 to 5 | Compute alignment score, copied from the result. |
| `total` | `integer` | yes | 3 to 15. Equals the sum | Composite, copied from the result. |

`Disposition`

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `idea_id` | `string` | yes | A candidate idea other than the selected one | The idea |
| `disposition` | `string` | yes | `eligible`, `rejected` or `deferred`. Equals the value in `screening_result` | Its fate |
| `reason` | `string` | yes | Equals `disposition_reason` in `screening_result` | Why this fate. Copied unchanged from `disposition_reason` in `screening_result`. |

Examples: [valid](../examples/opportunity_card.json)

## Producer obligations

Screening must:

1. Score each idea once, using only the rubric anchors. It must not add dimensions or change the scale.
2. Write a one-sentence reason for each score. The reason says why that anchor fits.
3. Record `dependency_flags` for forbidden dependencies. Flag an idea when the host term match would hit and also when its reading shows another rubric dependency.
4. Call the pinned helper `rank_opportunities` to compute totals, order and selection. It must not hand-edit the helper's output.
5. Build the card from the selected idea and the scores. Copy scores, citations, assumptions and risks unchanged. Write `summary` and `opportunity_statement` itself.
6. Run its own self-review before output. Re-read each idea against the rubric anchors. Confirm every Brief constraint appears in the card. Confirm every non-selected idea has a disposition and reason.

Screening must not invent ideas, cite sources outside the candidate set, re-verify literature claims or run code (PRD 3.4 blacklist).

## Deterministic check bundle

| Check ID | Rule | Outcome on failure |
|---|---|---|
| `screening_result_schema` | The `screening_result` parses and matches its table, including enums, ranges and lengths | reject |
| `opportunity_card_schema` | The `opportunity_card` parses and matches its table, including enums, ranges and lengths | reject |
| `candidate_binding` | `candidate_ref` and `brief_ref` in both outputs equal the inputs | reject |
| `rubric_pinned` | `rubric_ref` equals the rubric pinned in the declaration | reject |
| `scores_cover_candidates` | One `scores` row for each candidate idea, no missing, duplicate or extra row | reject |
| `score_range` | Each dimension score is an integer from 1 to 5 | reject |
| `score_total_sum` | Each `total` equals the sum. Each ranking `total` equals the score row `total` | reject |
| `score_citations_in_idea` | Each score row cites only citations that its idea cites | reject |
| `dependency_filter` | The host finds each rubric term in the idea text. Every hit is in `dependency_flags`. `eligible` is `false` exactly when flags exist | reject |
| `disposition_consistency` | Exactly one `selected`. `rejected` matches `eligible` false. `ranking` rows are exactly the `selected` and `eligible` ideas | reject |
| `ranking_deterministic` | The host recomputes order by `total` descending then `idea_id` ascending. It must equal `ranking` | reject |
| `selected_is_top1` | `selected_idea_id` equals `ranking[0].idea_id` | reject |
| `selected_in_candidates` | `selected_idea_id` and the card `idea_id` are ideas in the candidate set | reject |
| `card_matches_selection` | Card `idea_id`, `title`, `scores`, `rank`, `citation_ids`, `assumptions` and `risks` equal the selected idea's values. `screening_ref` is the produced result | reject |
| `card_constraints_carried` | Card `constraints` contains each Brief constraint and mandatory requirement text verbatim | reject |
| `card_dispositions_complete` | `other_dispositions` covers every non-selected idea once and equals the screening dispositions and reasons | reject |

If no idea is eligible, no result is committed. See failure outcomes.

## Verifier criteria

The verifier runs once for each output artifact, `screening_result` and `opportunity_card`. Each call carries the same pinned declaration and the same checking profile, and one exact output. The verifier judges how the text reads, not whether the scores are right for the inputs. Reduced assurance: it cannot see the candidate set or the rubric. The generic criteria of the [checking profile](verifier.md#checking_profile-contract) apply to both runs.

| Criterion ID | Output | Question | Blocking |
|---|---|---|---|
| `reasons_address_dimension` | `screening_result` | Does each score reason speak to its own dimension and give a basis, rather than repeating the score or another dimension? | yes |
| `opportunity_statement_complete` | `opportunity_card` | Does `opportunity_statement` name a bottleneck and the mechanism that addresses it? | yes |
| `disposition_reasons_specific` | `screening_result` | Does each disposition reason name a cause specific to its idea? | no |

## Gate rule

The gate accepts when all checks pass and both blocking criteria pass in the call for their output. It accepts only the pair together. It rejects on any failed check or criterion. It halts when a check cannot run.

## Failure outcomes

| Condition | Outcome | Kept |
|---|---|---|
| No idea is eligible | Halt with reason `no_eligible_idea`. Do not invent an alternative | The scores and filter flags |
| Any check fails | Reject. No retry loop | The rejected pair and check results |
| A score is missing, duplicated or out of range | Reject. Do not impute | The rejected pair |
| Rubric hash differs from the pin | Halt | Run records |

## Examples

| File | Role | Rejected by |
|---|---|---|
| [screening_rubric.json](../examples/screening_rubric.json) | valid pinned input | none |

| [screening_result.json](../examples/screening_result.json) | valid output | none |

| [opportunity_card.json](../examples/opportunity_card.json) | valid output | none |

| [screening_capsule.json](../examples/screening_capsule.json) | declaration | none |

## Future seams

- **RSI seam.** Target 1 is the pure `rank_opportunities` helper, pinned in the declaration body as `ranking_parent.txt`. Target 2 is the work prompt `screening_prompt.txt` and the work rubric `screening_rubric.json`. Target 2 is conditional M1 work, available when the headless model path exists, which in M1 is the Codex CLI. The declaration allows both with `evolution.rsi` `propose` and `evolution.may_change` (`files:ranking_*.txt`, `files:screening_prompt.txt`, `files:screening_rubric.json`). The [target profile](../rsi-contracts.md#rsi-target-profile) `mutable_paths` stay inside that list. The Target 1 profile lists only the ranking helper. A Target 2 profile lists only the prompt and the work rubric. A Target 2 child must still pass the rubric invariants above. Referee-owned rubrics live outside every CC and are never mutable (PRD 4.4.9). The checks `rubric_dimensions_complete`, `score_total_sum`, `ranking_deterministic` and `selected_is_top1` keep any child honest.
- The `deferred` disposition and the `rank` field leave room for a multi-opportunity portfolio without changing the card shape.
- The model router (an M1 side system behind `RouterPort`) may pick the scoring model when enabled. The declaration names none.
- More dimensions (evidence maturity, verification path in PRD 3.4.5) need a new rubric version and a new contract major version.
- The RSI examples [ranking_declaration.json](../examples/ranking_declaration.json) and [ranking_child_declaration.json](../examples/ranking_child_declaration.json) now point at `screening-result:field-contract:2`. Only the port reference changed. The RSI owner must still move the helper text to the version 2 score shape.

## M1 placement

The CC page above does not depend on where Screening runs. In M1 the rules below apply.

- Screening consumes the `candidate_set` of [Search](search.md) and feeds Hypothesis through its `opportunity_card`. The ports decide the order.
- Every plan holds Screening in exactly one node, so the Planner may not skip it or add a second selection. The plan policy lists `research.screening` in `required_stages` ([run plan](../run-plan.md#plan-policy)).
- Enforced by the plan policy and the protected binder check `delivery_leaf_coverage` ([D42](../../method/decisions.md#d42)).
