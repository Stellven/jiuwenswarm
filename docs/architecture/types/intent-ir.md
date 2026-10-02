---
type: payload-type
id: cc.type.intent_ir
version: 1
status: checked
tags: [types, m1]
---

> **Checked, not yet approved.** Compiles, its example validates, and it has been through review.

# `intent_ir`: what a request means · version 1

What the user's prompt asks for, split into goals, outcomes, constraints, open questions, contradictions and unknowns. Every item points at the exact characters of the prompt it came from, so it can be checked against what was asked.

**Made by** `research.compile_intent` at the `intent` step ([intent capsule](../m1/intent-capsule.md)). **Read by** `research.compile_brief` at the `requirement` step, as hints ([requirement capsule](../m1/requirement-capsule.md)). Later, by the Phase 2 Intention Compiler track (PRD 3.2 flag).

**Spans.** A span is `[start, end]`: Unicode-code-point offsets into the producing `source_text.text`, end exclusive, so the quoted text is `text[start:end]` in Python. The exact source Artifact is recorded in the producing Observation inputs rather than copied into the value (INV-5).

## Fields

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `generation` | `integer` | req | checked |  | 0 for the first compilation. A repair writes a new value with this number one higher (INV-2). M1 has no repair loop, so it is always 0 |
| `goals` | `list<object>` | req | checked |  | What the user wants achieved. May be empty |
| `goals[].goal_id` | `id` | req | checked |  | Unique within the value. Example: `G1` |
| `goals[].statement` | `text` | req | checked |  | The goal in words. Example: `Find a way to quantise the 7B model with little accuracy loss.` |
| `goals[].source_spans` | `list<list<integer>>` | req | checked |  | At least one. Where the prompt states it |
| `outcomes` | `list<object>` | req | checked |  | What should exist at the end. May be empty |
| `outcomes[].outcome_id` | `id` | req | checked |  | Unique within the value. Example: `D1` |
| `outcomes[].class` | `enum(information, artifact, action)` | req | checked |  | An answer, a made thing, or a change to the world |
| `outcomes[].description` | `text` | req | checked |  | The outcome in words |
| `outcomes[].source_spans` | `list<list<integer>>` | req | checked |  | At least one. Where the prompt states it |
| `constraints` | `list<object>` | req | checked |  | Limits on the answer. May be empty |
| `constraints[].constraint_id` | `id` | req | checked |  | Unique within the value. Example: `C1` |
| `constraints[].category` | `reg(constraint_category)` | req | checked |  | The kind of limit, from the policy registry. Example: `prohibition` |
| `constraints[].statement` | `text` | req | checked |  | The constraint in words |
| `constraints[].expression` | `object` | req | checked |  | The constraint in a form code can read. Version 1 has one form, the literal statement |
| `constraints[].expression.literal` | `text` | req | checked |  | The constraint's text, as stated |
| `constraints[].source_spans` | `list<list<integer>>` | req | checked |  | At least one. Where the prompt states it |
| `ambiguities` | `list<object>` | req | checked |  | Questions the prompt leaves open. May be empty |
| `ambiguities[].ambiguity_id` | `id` | req | checked |  | Unique within the value. Example: `A1` |
| `ambiguities[].question` | `text` | req | checked |  | The open question |
| `ambiguities[].blocking` | `boolean` | req | checked |  | Whether the work cannot sensibly go on without an answer. M1 has no clarification dialogue (PRD 3.2.3), so a blocking ambiguity becomes a default or an `issues` entry downstream, never a question to the user |
| `ambiguities[].source_spans` | `list<list<integer>>` | req | checked |  | At least one. Where the prompt raises it |
| `conflicts` | `list<object>` | req | checked |  | Parts of the prompt that contradict each other. May be empty |
| `conflicts[].conflict_id` | `id` | req | checked |  | Unique within the value. Example: `K1` |
| `conflicts[].description` | `text` | req | checked |  | What contradicts what |
| `conflicts[].resolution` | `enum(clarify, reject)` | req | checked |  | The producer's proposal: ask, or treat the request as impossible. The gate and later steps decide; the value only proposes |
| `conflicts[].source_spans` | `list<list<integer>>` | req | checked |  | At least one. Where the prompt states the conflicting parts |
| `conflicts[].derived_from_ids` | `list<id>` | req | checked |  | Ids of goals, outcomes or constraints in this value that the conflict is between. May be empty |
| `unknowns` | `list<object>` | req | checked |  | Facts nobody stated that the work depends on. May be empty |
| `unknowns[].unknown_id` | `id` | req | checked |  | Unique within the value. Example: `U1` |
| `unknowns[].question` | `text` | req | checked |  | What is unknown, as a question |
| `unknowns[].kind` | `reg(unknown_kind)` | req | checked |  | The kind of unknown, from the policy registry. Example: `design_parameter` |
| `unknowns[].derived_from_ids` | `list<id>` | req | checked |  | Ids of goals, outcomes or constraints in this value that raise it. May be empty |
| `ext` | `map<string, json>` | opt | checked |  | Extensions keyed by producer; consumers ignore them |

**Registries** (policy `registries`, first epoch): `constraint_category` is `limit`, `scope`, `prohibition`, `format`, `temporal`, `preference`, `content`. `unknown_kind` is `design_parameter`, `selection_decision`, `discoverable_fact`.

## Type checks

| Check | Anchor | Over | Applies at | Runner | Author | What passes |
|---|---|---|---|---|---|---|
| `check.value_matches_type.v1` | deterministic | `outputs` | `both` | `cc/checks/registry/common.py:value_matches_type` | muk | the value matches the generated schema |
| `check.intent_ir_ids_unique.v1` | deterministic | `outputs` | `both` | `cc/checks/registry/intent_ir.py:intent_ir_ids_unique` | muk | every `*_id` is unique across the whole value |
| `check.intent_ir_references_resolve.v1` | deterministic | `outputs` | `both` | `cc/checks/registry/intent_ir.py:intent_ir_references_resolve` | muk | every id in a `derived_from_ids` names a goal, outcome or constraint in the same value |
| `check.intent_ir_spans_well_formed.v1` | deterministic | `outputs` | `both` | `cc/checks/registry/intent_ir.py:intent_ir_spans_well_formed` | muk | every span is two integers with `0 <= start < end`, and every list of spans that the table requires is non-empty |

Whether each span reproduces the right text of the prompt needs the input, so it is a capsule check of the producer (`source_spans_exact` in the [intent capsule](../m1/intent-capsule.md)), not a type check.

## Example

For the prompt `Compare 4-bit and 8-bit quantisation; the report must cover both. Which GPU should we use? Budget is TBD.`:

```json
{
  "generation": 0,
  "goals": [],
  "outcomes": [],
  "constraints": [{"constraint_id": "C1", "category": "scope", "statement": "Compare 4-bit and 8-bit quantisation; the report must cover both.", "expression": {"literal": "Compare 4-bit and 8-bit quantisation; the report must cover both."}, "source_spans": [[0, 65]]}],
  "ambiguities": [{"ambiguity_id": "A1", "question": "Which GPU should we use?", "blocking": false, "source_spans": [[66, 90]]}],
  "conflicts": [],
  "unknowns": [{"unknown_id": "U1", "question": "The request leaves this unresolved: 'Budget is TBD.'", "kind": "discoverable_fact", "derived_from_ids": []}]
}
```

## History

The shape is what our own `compile_intent` capsule produces, checked field by field against its code. It supersedes an earlier draft, `cc.intent.ir.v1`, parked in obby. Spans point into the bound `source_text`; `expression` has one M1 form, `{literal}`; registry lists come from policy; `derived_from` became `derived_from_ids`; `ext` is added.
