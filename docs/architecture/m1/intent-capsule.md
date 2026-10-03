---
type: design
status: past
tags: [design, draft, m1, capsule]
---

# Historical deterministic intent capsule design

> Superseded for production by ordinary optional launcher hints and the one-pass [Requirement Compilation](requirement-capsule.md). This document is a reference pattern, not a current admitted capability or coding requirement.

> **Draft recheck.** The `compile_intent` reference capsule now consumes the composable [`source_text`](../types/source-text.md) projection and gives the shared [`intent_ir`](../types/intent-ir.md). Hashes are shown as `<author kit>`.

## What it does

It reads the user's prompt and lists, with exact character spans, what the prompt asks for: goals, outcomes, constraints, open questions, contradictions and unknowns. It uses fixed rules and no model, so the same prompt always gives the same IntentIR.

It runs at step `intent`, before the requirement step, which reads its IntentIR as hints ([M1 pipeline](pipeline.md)). PRD 3.2's "Intention Compiler" flag puts dynamic intent work on the Phase 2 track. This capsule is the deterministic Phase 1 piece, so Phase 2 has a fixed baseline to beat. Adding it as its own step is a design choice to confirm with the PRD owner ([open issues](../open-issues.md)).

## Run-plan entry

Step `intent` on [the M1 pipeline](pipeline.md): work capsule `research.compile_intent`, gate capsule `research.accept_intent`, input `source_text` from `source.source_text`. A compatible direct-text launcher may supply the same type without changing this capsule.

## Gate

- **Gate capsule:** [`research.accept_intent`](intent-gate.md), following [the gate capsule pattern](../capsule/gate-capsules.md).
- **Tier 1:** this capsule's deterministic checks below, and the `intent_ir` type's checks.
- **Tier 2:** the step's judged check `intent_fidelity`, defined in [the M1 run plan](pipeline.md#the-plan-as-recorded).

Its rubric, `rubrics/intent_fidelity.md`, is one of the gate capsule's `body` files, and freeze checks that ([gate capsules](../capsule/gate-capsules.md#what-every-gate-capsule-declares)). A fail halts the run before `requirement`.

## Existing code it touches

None directly. It runs in a tool host through the runner ([runner](../capsule/runner.md#tool-a-python-function-in-its-own-process)), and touches no adapter.

## The Declaration (`capsule.json`)

```json
{
  "schema_version": "cc.declaration.v1",
  "identity": {
    "name": "research.compile_intent",
    "kind": "tool",
    "carrier": {"ref": "compile_intent.py:compile_intent", "sha256": "<author kit>"},
    "summary": "Extract goals, outcomes, constraints, ambiguities, conflicts and unknowns from a request's prompt into an IntentIR, each item citing an exact source span, using fixed rules and no model call."
  },
  "ports": {
    "inputs": [
      {"name": "source_text", "type": "source_text", "required": true,
       "description": "Exact text, source identity, content hash and offset basis."}
    ],
    "outputs": [
      {"name": "intent_ir", "type": "intent_ir", "check_id": "source_spans_exact",
       "description": "What the prompt means, generation 0."}
    ]
  },
  "needs": {"when": [], "external": [], "network": "none", "human_interaction": "none"},
  "changes": {"effect_class": "pure", "effects": [], "state_kind": "none"},
  "guarantees": {
    "checks": [
      {"id": "source_spans_exact", "anchor": "deterministic", "target": "ports.outputs.intent_ir",
       "over": "inputs_and_outputs", "applies_at": "both",
       "runner": {"ref": "checks/intent_ir_checks.py:source_spans_exact", "sha256": "<author kit>"},
       "description": "Every span lies inside source_text.text: 0 <= start < end <= the text's length and uses its declared offset basis.", "author": "muk"},
      {"id": "first_generation", "anchor": "deterministic", "target": "ports.outputs.intent_ir",
       "over": "outputs", "applies_at": "both",
       "runner": {"ref": "checks/intent_ir_checks.py:first_generation", "sha256": "<author kit>"},
       "description": "generation is 0: this capsule compiles, it never repairs.", "author": "muk"},
      {"id": "conflicts_never_self_rejected", "anchor": "deterministic", "target": "ports.outputs.intent_ir",
       "over": "outputs", "applies_at": "both",
       "runner": {"ref": "checks/intent_ir_checks.py:conflicts_never_self_rejected", "sha256": "<author kit>"},
       "description": "No conflict's resolution is reject: a rule-based compiler defers every conflict by proposing clarify.", "author": "muk"},
      {"id": "matches_reference", "anchor": "reference", "target": "ports.outputs.intent_ir",
       "over": "inputs_and_outputs", "applies_at": "admission",
       "runner": {"ref": "checks/intent_ir_checks.py:matches_reference", "sha256": "<author kit>"},
       "description": "On a test case, the IntentIR equals the expected one in canonical JSON.", "author": "muk"}
    ]
  },
  "evolution": {
    "rsi": "propose",
    "may_change": ["files:compile_intent.py", "changes.effect_class", "changes.effects"],
    "notes": "The rule set in compile_intent.py is the lever. Ports and checks stay fixed."
  }
}
```

## Which checks run where

| Check | Source | Why there |
|---|---|---|
| `check.value_matches_type.v1` | type `intent_ir` | the shape, for any producer |
| `check.intent_ir_ids_unique.v1`, `check.intent_ir_references_resolve.v1`, `check.intent_ir_spans_well_formed.v1` | type `intent_ir` | true of every IntentIR, whoever makes it |
| `source_spans_exact` | this capsule | needs the input prompt |
| `first_generation`, `conflicts_never_self_rejected` | this capsule | this capsule's own promises, not every IntentIR's |
| `matches_reference` | this capsule, admission only | compares with a test case's expected output |

## What changed from `compile_intent`, and why

| Change | Why |
|---|---|
| input port becomes `source_text` | the compiler depends on text and an offset/source identity, not the complete intake package; an adapter projects it and later planners may bind any compatible producer |
| name `compile_intent` became `research.compile_intent` | names are dot-separated handles, as `research.compile_brief` |
| preconditions and input failure modes removed | the `source_text` type is checked before invocation; repeating unreachable runner failures would add test cost without observable behavior |
| `intent_ir_well_formed`, `ids_unique`, `references_resolve` moved to the type | they hold for every IntentIR, so they belong to the type, written once |
| `blocking_ambiguities_answerable` removed | the type's schema now requires a non-blank `question` and a boolean `blocking` |
| `deterministic_on_repeat` removed | it called the capsule's code from inside a check, outside the runner, so the call was never recorded. Determinism has no place in the Declaration yet ([open issues](../open-issues.md)) |
| `matches_reference` added | a deterministic check cannot test a known answer; the rule `one_test_per_admission_check` then needs a test case for it, as for every `admission` or `both` check |
| `owner`, `tags` dropped | unchecked fields with no reader at M1; they can return with the store |

## Code changes this needs

Small, and listed so a coding task can pick them up. They do not change what the code does.

1. `compile_intent(raw_intent)` becomes `compile_intent(source_text)`, reading `source_text["text"]` (the runner calls `fn(**inputs)` by port name).
2. Every check function takes the [calling convention](../schemas/checks.md#calling-convention) `(*, inputs, outputs, observation, expected)` and returns `{result, message, evidence}`.
3. `ids_unique` and `references_resolve` move to the type check library as `check.intent_ir_ids_unique.v1` and `check.intent_ir_references_resolve.v1` ([toolchain](../capsule/toolchain.md#where-code-lives)).
4. The output key `derived_from` becomes `derived_from_ids` on conflicts and unknowns ([`intent_ir`](../types/intent-ir.md)).
5. The folder takes the [capsule folder layout](../capsule/toolchain.md#the-capsule-folder): `declaration.json` becomes `capsule.json`, and the fixtures become `tests/cases.json`. The author's own pytest suite, `run_checks.py` and notes stay as author files outside the capsule.

## Tests

Four test cases, one for each `admission` or `both` check: `source_spans_exact`, `first_generation`, `conflicts_never_self_rejected`, `matches_reference`. Each input is a [`source_text`](../types/source-text.md) fixture with an exact hash and offset basis. Each expected result is the current code's canonical IntentIR output.
