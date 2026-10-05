---
type: payload-type
id: cc.type.intent_ir
version: 1
status: checked
tags: [types, m1]
prd: [3.2.1, 4.7.1]
level: detail
---

# `intent_ir`: what a request means · version 1

PRD: 3.2.1, 4.7.1

What the user's prompt asks for, split into goals, outcomes, constraints, open questions, contradictions and unknowns. Every item points at the exact characters of the prompt it came from, so it can be checked against what was asked.

**Made by** the intent CC `research.compile_intent` ([intent-compile](../capabilities/intent-compile.md)), model-backed: bounded compile, validate, nested review and repair (policy `intent.max_repairs`), with a compile and a repair prompt. **Read by** the requirement [capsule](../capsule/capsule.md#term-capability-capsule) `research.compile_brief` as a required, Gate-accepted input ([requirement](../capabilities/requirement-capsule.md)). The type is unchanged; the [task DAG](run-plan.md#term-planned-plan) wires the accepted `intent_ir` into the requirement call.

**Spans.** A span is `[start, end]`: Unicode-code-point offsets into the producing `source_text.text`, end exclusive, so the quoted text is `text[start:end]` in Python. The exact source Artifact is recorded in the producing [Observation](../schemas/observation.md#term-observation) inputs rather than copied into the value (INV-5).

## Key terms

| Term | Meaning |
|---|---|
| <a id="term-intentir"></a>**IntentIR** (also: intent_ir) | What the user's prompt asks for, split into goals, outcomes, constraints, open questions, contradictions and unknowns. Every item points at the exact characters of the prompt it came from, so it can be checked against what was asked. |

## Fields

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `generation` | `integer` | req | checked |  | 0 for the first compilation. Each bounded repair writes a new value with this number one higher (INV-2), up to the policy repair budget (default 1, hard cap 4) |
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
| `constraints[].category` | `reg(constraint_category)` | req | checked |  | The [kind](../capsule/capsule.md#term-capsule-kind) of limit, from the policy registry. Example: `prohibition` |
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
| `conflicts[].resolution` | `enum(clarify, reject)` | req | checked |  | The producer's proposal: ask, or treat the request as impossible. The gate and later [steps](../system/nodes.md#term-step) decide; the value only proposes |
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
| `check.value_matches_type.v1` | deterministic | `outputs` | `both` | `cc/checks/registry/common.py:value_matches_type` | cc-team | the value matches the generated schema |
| `check.intent_ir_ids_unique.v1` | deterministic | `outputs` | `both` | `cc/checks/registry/intent_ir.py:intent_ir_ids_unique` | cc-team | every `*_id` is unique across the whole value |
| `check.intent_ir_references_resolve.v1` | deterministic | `outputs` | `both` | `cc/checks/registry/intent_ir.py:intent_ir_references_resolve` | cc-team | every id in a `derived_from_ids` names a goal, outcome or constraint in the same value |
| `check.intent_ir_spans_well_formed.v1` | deterministic | `outputs` | `both` | `cc/checks/registry/intent_ir.py:intent_ir_spans_well_formed` | cc-team | every span is two integers with `0 <= start < end`, and every list of spans that the table requires is non-empty |

Whether each span reproduces the right text of the prompt needs the input, so it is a capsule check of the producer (`source_spans_exact` in the [intent capsule](../capabilities/intent-compile.md)), not a type check.

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
