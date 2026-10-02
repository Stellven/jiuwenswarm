---
type: capsule
tags: [capsule, example]
---

# A complete example: `compile_intent` (tool)

> **Superseded 2026-10-01** by the [intent capsule](../m1/intent-capsule.md), which reads the shared `intake` type. Kept for the porting history; build from the intent capsule page.

[Declaration](fields.md) defines every field. This page shows one complete example that follows the schema. It mirrors the real, built capsule at `capsules-build/compile_intent/`, ported to the current schema in `PORT-NOTES.md` there. It is `kind: tool`, not a skill. It extracts goals, outcomes, constraints, ambiguities, conflicts, and unknowns by fixed rule, with no model call. Compiling it twice on the same input gives the same output.

The `raw_intent` and `intent_ir` port types are not yet entries in the [port type vocabulary](../schemas/port-types.md). Their field shape comes from `cc.intent.v1`, which itself adopts AI4Research's `intent-ir.v3.schema.json`. This capsule's output matches that shape.

## The Declaration

```json
{
  "schema_version": "cc.declaration.v1",
  "identity": {
    "name": "compile_intent",
    "kind": "tool",
    "carrier": {
      "ref": "compile_intent.py:compile_intent",
      "sha256": "17f8dd2cf434a2a134ae5575b83a0518bcd1297c726322fe3cf928e51c9ddae4"
    },
    "owner": "muk",
    "tags": ["intent", "request-to-contract", "deterministic", "b2"],
    "summary": "Extract goals, outcomes, constraints, ambiguities, conflicts and unknowns from a request's raw text into an IntentIR, each item citing an exact source span, using fixed rules and no model call."
  },
  "ports": {
    "inputs": [
      {
        "name": "raw_intent",
        "type": "raw_intent",
        "required": true,
        "description": "The request as given, per cc.intent.raw.v1."
      }
    ],
    "outputs": [
      {
        "name": "intent_ir",
        "type": "intent_ir",
        "check_id": "intent_ir_well_formed",
        "description": "What the request means, per cc.intent.ir.v1, generation 0."
      }
    ]
  },
  "needs": {
    "when": [
      {
        "id": "raw_text_present",
        "path": "inputs.raw_intent.text",
        "op": "present",
        "evaluable_at": "both"
      },
      {
        "id": "raw_text_nonblank",
        "path": "inputs.raw_intent.text",
        "op": "matches",
        "value": "\\S",
        "evaluable_at": "both"
      }
    ],
    "external": [],
    "network": "none"
  },
  "changes": {
    "effect_class": "pure",
    "effects": [],
    "state_kind": "none"
  },
  "guarantees": {
    "checks": [
      {
        "id": "intent_ir_well_formed",
        "anchor": "deterministic",
        "target": "ports.outputs.intent_ir",
        "over": "outputs",
        "applies_at": "both",
        "runner": {
          "ref": "checks/intent_ir_checks.py:well_formed",
          "sha256": "79e952ad0a6102b7dd4f585e1a3955928c369cf248863262b32052909a33ca82"
        },
        "description": "The output matches cc.intent.ir.v1's shape exactly. Generation is 0. Every required list is present, possibly empty. No other field is carried.",
        "author": "muk"
      },
      {
        "id": "source_spans_exact",
        "anchor": "deterministic",
        "target": "ports.outputs.intent_ir",
        "over": "inputs_and_outputs",
        "applies_at": "both",
        "runner": {
          "ref": "checks/intent_ir_checks.py:source_spans_exact",
          "sha256": "79e952ad0a6102b7dd4f585e1a3955928c369cf248863262b32052909a33ca82"
        },
        "description": "Every source_spans range is a valid, in-bounds slice of the RawIntent's text. It exactly reproduces that substring. No span is empty or reversed.",
        "author": "muk"
      },
      {
        "id": "ids_unique",
        "anchor": "deterministic",
        "target": "ports.outputs.intent_ir",
        "over": "outputs",
        "applies_at": "both",
        "runner": {
          "ref": "checks/intent_ir_checks.py:ids_unique",
          "sha256": "79e952ad0a6102b7dd4f585e1a3955928c369cf248863262b32052909a33ca82"
        },
        "description": "Every goal_id, outcome_id, constraint_id, ambiguity_id, conflict_id and unknown_id is unique within the IntentIR.",
        "author": "muk"
      },
      {
        "id": "references_resolve",
        "anchor": "deterministic",
        "target": "ports.outputs.intent_ir",
        "over": "outputs",
        "applies_at": "both",
        "runner": {
          "ref": "checks/intent_ir_checks.py:references_resolve",
          "sha256": "79e952ad0a6102b7dd4f585e1a3955928c369cf248863262b32052909a33ca82"
        },
        "description": "Every id in a conflict's or unknown's derived_from names a goal, outcome or constraint id that exists in the same IntentIR.",
        "author": "muk"
      },
      {
        "id": "blocking_ambiguities_answerable",
        "anchor": "deterministic",
        "target": "ports.outputs.intent_ir",
        "over": "outputs",
        "applies_at": "both",
        "runner": {
          "ref": "checks/intent_ir_checks.py:blocking_ambiguities_answerable",
          "sha256": "79e952ad0a6102b7dd4f585e1a3955928c369cf248863262b32052909a33ca82"
        },
        "description": "Every ambiguity carries a non-empty question and a boolean blocking field. Never omitted or null.",
        "author": "muk"
      },
      {
        "id": "conflicts_never_self_rejected",
        "anchor": "deterministic",
        "target": "ports.outputs.intent_ir",
        "over": "outputs",
        "applies_at": "both",
        "runner": {
          "ref": "checks/intent_ir_checks.py:conflicts_never_self_rejected",
          "sha256": "79e952ad0a6102b7dd4f585e1a3955928c369cf248863262b32052909a33ca82"
        },
        "description": "No conflict's resolution is reject. A deterministic compiler with no judgment defers every conflict to a human, and never decides one side is impossible.",
        "author": "muk"
      },
      {
        "id": "deterministic_on_repeat",
        "anchor": "deterministic",
        "target": "ports.outputs.intent_ir",
        "over": "inputs_and_outputs",
        "applies_at": "node",
        "runner": {
          "ref": "checks/intent_ir_checks.py:deterministic_on_repeat",
          "sha256": "79e952ad0a6102b7dd4f585e1a3955928c369cf248863262b32052909a33ca82"
        },
        "description": "Calling compile_intent twice on the same RawIntent value produces byte-identical IntentIR content in canonical JSON.",
        "author": "muk"
      }
    ],
    "failure_modes": [
      {
        "reason_code": "INTENT_INPUT_MISSING",
        "when": "raw_intent.text is absent, null, or empty or whitespace only.",
        "retriable": false
      },
      {
        "reason_code": "INTENT_INPUT_NOT_STRING",
        "when": "raw_intent.text is present but is not a string.",
        "retriable": false
      }
    ]
  },
  "evolution": {
    "rsi": "propose",
    "may_change": ["files:compile_intent.py", "changes.effect_class", "changes.effects"]
  }
}
```

Every `sha256` above is real. It is the actual hash of the file it names in `capsules-build/compile_intent/`, computed the same way the runner will check it later.

## Computed fields, still unset

`decl_hash`, `interface_hash`, and `code_sha256` are never written by the author. Admission computes them from the Declaration above, once it exists. No author kit exists yet, so they are still unset. Shown here with placeholder values, only to complete the picture of what a Binding will pin later.

```json
{
  "decl_hash": "df4977d00977040b6c81813e9aaee9650eb66ebaf8a62563c1b56339c7e15dba",
  "interface_hash": "d127849622eefe2882ec9b7abf54acca091a48d21acfeb7830448c899705e9af",
  "code_sha256": "d5f1131e5dd7922340690bed0ac2b10f5215e4eaeded88bd87a71e5754849003"
}
```

## What RSI may change here, and what it may not

`evolution.may_change` names three things: the code file `compile_intent.py` itself, `changes.effect_class`, and `changes.effects`. So RSI may submit a child that rewrites the extraction rules, or that reclassifies this capsule's effect class, for example if a later version starts writing a cache file and needs `read_only` or `idempotent` instead of `pure`.

`ports` is not in that list, so it is locked. An RSI child cannot add, remove, rename, or retype `raw_intent` or `intent_ir`. It cannot add a new port either, since `ports.inputs` and `ports.outputs` are both under the single path `ports`, and neither one is named. Anything that calls this capsule today can keep calling it the same way, no matter how many RSI children it goes through. `guarantees.checks` is also locked. RSI can change how the rules extract an IntentIR, but it cannot change what counts as a valid one, since that is what the checks test.

`rsi_cannot_grant` blocks one more thing on its own, with no need for this capsule to list it: a child can never add `evolution` to its own `may_change`, so RSI can never widen its own future permissions.

## How this was ported from an earlier schema shape

This capsule was first written against an earlier shape of the schema. Three things had to change to match the current one.

- Both `carrier` and `body` were set at first. The schema allows only one. Every check already pins `checks/intent_ir_checks.py` by its own hash, so `body` repeated a pin the checks already carried. Removed.
- `identity.lineage` used a field name, `parent`, that the current schema does not have. This is a first version with no parent, so `lineage` is left out entirely now, rather than filled with a shape that does not match.
- `evolution.rsi` was missing outright. It is required now. Set to `propose`, and later given the `may_change` list above once that field existed.

`guarantees.failure_modes` was added at the same time: the two reason codes the carrier actually raises, `INTENT_INPUT_MISSING` and `INTENT_INPUT_NOT_STRING`. A third code, `INTENT_INPUT_ID_MISSING`, is documented in the capsule's own exception notes but never actually raised by the code. Left out here rather than declared falsely. Either the code should gain that check, or the exception notes should drop the code. Not decided yet.

## Fields left out, and why

- **`identity.lineage`**. Left out, not set to a placeholder. This is a first version. The field only appears when a real parent exists.
- **`identity.body`, `identity.remote`, `members`, `wiring`**. This capsule's code is one file, so `carrier` is enough. It is not a remote capsule or a composite capsule either. Only one of `carrier`, `body`, `remote`, or `members` is set, never more than one.
- **`needs.external`**. Empty here. This capsule calls no other capsules.
- **`needs.dependencies`, `needs.config`, `needs.secrets`, `needs.resources`**. This tool is plain Python with no packages beyond the standard library, so there is nothing to pin.
- **`guarantees.quality`**. This field names a `judged` check as its criterion. B1's gate uses deterministic checks only. See [b1-design.md](../b1-design.md#inside-a-capsule-and-its-gate). There is no judged check for this capsule to point at.

## Why `tool`, not `skill`

A `skill` capsule hands the whole task to a model, through Markdown instructions the runner turns into a prompt. This capsule does not. It is a plain Python function with fixed rules, and it makes the same claim `intent_compiler.py` in AI4Research once made for its deterministic half, that source spans, structure and ids can all be produced and checked without a model in the loop. The one open question this leaves, whether B1's real `compile_intent` node stays this deterministic capsule or later gains a model-assisted step for genuinely ambiguous language, is `b1-design.md`'s own Open item 2. That page's node table still lists `compile_intent` as "CC, model", which now reads as unsettled rather than settled, given this example.
