---
type: design
status: checked
tags: [design, draft, m1, capsule]
---

# `requirement_capsule`: design

> **Checked, not yet approved.** The first M1 capsule, designed from PRD 3.2 Requirement Compilation ([full PRD](../../product/prd-m1-full-2026-10-01.txt)). It follows the [Declaration](../capsule/fields.md) and the [`make_capsule.md`](../capsule/make-capsule.md) format. Hashes are shown as `<author kit>`: the author kit computes them once the files exist.

## What it does

It turns the Qualified Intake Package from Ingestion (3.1.5) into the **Research Brief**: the contract every later stage reads. It makes one model call, with no clarification dialogue, and does not wait for approval (3.2.3, 3.2.7).

| PRD step | What the capsule does |
|---|---|
| 3.2.1 Intent Interpretation | states the core research objective, without choosing a solution |
| 3.2.2 Context Scoping | lists `in_scope_items` and `out_of_scope_items` (the PRD's `in_scope` and `out_of_scope`), taken only from the intake text |
| 3.2.3 Ambiguity Resolution | fills missing parameters from a fixed table of conservative defaults, such as `single_gpu`, and records each default it applied |
| 3.2.4 Constraint Resolution | extracts stated compute limits: hardware, runtime, token budget |
| 3.2.5 Requirement Prioritization | splits requirements into `mandatory_requirements` and `optional_preferences` |
| 3.2.6 Acceptance Definition | defines concrete target metrics, each with a comparator and a threshold |
| 3.2.7 Contract Confirmation | returns everything as one Research Brief JSON, which goes to the Evaluator Gate (4.2) |

**The design choice that matters:** every item the Brief says the user *stated* carries a short quote from the intake text. A deterministic check then confirms the quote is really there. So the model cannot invent a requirement and present it as the user's. Anything not stated is either a recorded default or absent. `compile_intent` grounds its output the same way, with source spans.

## The Research Brief

The Brief is the shared payload type [`research_brief`](../types/research-brief.md). That page is its only definition: fields, type checks and an example. This capsule's input types are [`intake`](../types/intake.md) and [`intent_ir`](../types/intent-ir.md).

## Run-plan entry

Step `requirement` on [the M1 pipeline](pipeline.md): work capsule `research.compile_brief`, gate capsule `research.accept_brief`, inputs `intake` from `launcher.intake` and `intent_ir` from `intent.intent_ir`.

## Gate

- **Gate capsule:** [`research.accept_brief`](brief-gate.md), following [the gate capsule pattern](../capsule/gate-capsules.md).
- **Tier 1:** this capsule's deterministic checks below, and the `research_brief` type's checks.
- **Tier 2:** the step check `brief_objective_faithful`, defined in [the M1 run plan](pipeline.md#the-plan-as-recorded). A fail halts the run before `search`.

## Existing code it touches

Its model turns go through M05 and `cc.adapters.codex` ([integration](../system/integration.md#codex-the-model-for-m05)). Nothing else.

## The Declaration (`capsule.json`)

```json
{
  "schema_version": "cc.declaration.v1",
  "identity": {
    "name": "research.compile_brief",
    "kind": "skill",
    "body": [
      {"path": "SKILL.md", "sha256": "<author kit>"},
      {"path": "references/defaults.json", "sha256": "<author kit>"},
      {"path": "references/brief_example.json", "sha256": "<author kit>"}
    ],
    "summary": "Compile a research request and its reference text into a Research Brief: objective, scope, constraints, prioritised requirements and acceptance metrics, each stated item quoted from the request, gaps filled from a fixed defaults table."
  },
  "ports": {
    "inputs": [
      {"name": "intake", "type": "intake", "required": true,
       "description": "The Qualified Intake Package: the prompt, and the extracted text of each reference document."},
      {"name": "intent_ir", "type": "intent_ir", "required": false,
       "description": "An IntentIR of the same prompt, used as hints only."}
    ],
    "outputs": [
      {"name": "research_brief", "type": "research_brief", "check_id": "brief_evidence_grounded",
       "description": "The Research Brief."}
    ]
  },
  "needs": {
    "when": [],
    "external": [],
    "network": "none",
    "resources": {"timeout_s": 300},
    "human_interaction": "none"
  },
  "changes": {"effect_class": "pure", "effects": [], "state_kind": "none"},
  "guarantees": {
    "checks": [
      {"id": "brief_evidence_grounded", "anchor": "deterministic", "target": "ports.outputs.research_brief",
       "over": "inputs_and_outputs", "applies_at": "both",
       "runner": {"ref": "checks/brief_checks.py:evidence_grounded", "sha256": "<author kit>"},
       "description": "Every evidence quote appears verbatim in its evidence_source_id: the intake prompt, or the text of the named document. The objective, every requirement and every metric cite the prompt.", "author": "muk"},
      {"id": "defaults_only_when_silent", "anchor": "deterministic", "target": "ports.outputs.research_brief",
       "over": "outputs", "applies_at": "both",
       "runner": {"ref": "checks/brief_checks.py:defaults_only_when_silent", "sha256": "<author kit>"},
       "description": "A structural check on the Brief alone, not a judgment about the intake: a field listed in defaults_applied has no evidence quote anywhere and its value equals the defaults table's value; a field with an evidence quote is never also in defaults_applied.", "author": "muk"},
      {"id": "requirements_and_metrics_present", "anchor": "deterministic", "target": "ports.outputs.research_brief",
       "over": "outputs", "applies_at": "both",
       "runner": {"ref": "checks/brief_checks.py:requirements_and_metrics_present", "sha256": "<author kit>"},
       "description": "At least one metric, unless every mandatory requirement is qualitative and `issues` records an `INPUT_INCOMPLETE` explaining why no metric was written. The shape, the id rules and at least one mandatory requirement are the type's checks.", "author": "muk"},
      {"id": "metric_target_grounded", "anchor": "deterministic", "target": "ports.outputs.research_brief",
       "over": "outputs", "applies_at": "both",
       "runner": {"ref": "checks/brief_checks.py:metric_target_grounded", "sha256": "<author kit>"},
       "description": "Each metric's target number appears in its own evidence quote (after normalizing things like '30%' and '30 percent'), so a metric's threshold cannot silently diverge from the requirement it operationalizes.", "author": "muk"},
      {"id": "brief_matches_reference", "anchor": "reference", "target": "ports.outputs.research_brief",
       "over": "inputs_and_outputs", "applies_at": "admission",
       "runner": {"ref": "checks/brief_checks.py:matches_reference", "sha256": "<author kit>"},
       "description": "On a test case, the Brief's metrics match the expected ones by requirement_id, comparator and target, not by name (a name mismatch such as vram_reduction vs vram_reduction_pct must not fail the fixture).", "author": "muk"}
    ]
  },
  "evolution": {
    "rsi": "propose",
    "may_change": ["files:SKILL.md", "files:references/brief_example.json"],
    "notes": "The prompt is the main lever. The defaults table is policy, not prompt: change it by hand."
  }
}
```

**Why these choices:**

- **`kind: skill`,** because PRD 3.2.1 calls for one LLM generation. The model is named in `SKILL.md`'s front matter, chosen by the author. Model Routing may route it; CC only needs the call recorded, and replayable in tests.
- **`effect_class: pure`:** it writes nothing outside its output.
- **`intent_ir` is optional:** the PRD's Phase 1 path does not produce it. When `compile_intent` runs, its IntentIR is passed as hints. The Intention Compiler sync (PRD 3.2 flag) may change this.
- **RSI may change the prompt and its worked example, not the defaults table.** The defaults are conservative policy (3.2.3), and they decide what the Brief assumes. The `defaults_only_when_silent` check reads them. So they change by hand, as a new version.
- **The checks' code (`checks/`) is not in `may_change`.** The referee stays fixed.
- **No judged check of its own.** The judgement "the objective says what the user asked" is the step's, so it is a step check judged by the brief gate ([brief gate](brief-gate.md)). The capsule is then admitted with deterministic checks only, and needs no admission judge.

## `make_capsule.md`

Generated by the author kit from `capsule.json` ([make_capsule.md](../capsule/make-capsule.md)); not reproduced here, so it cannot drift from the Declaration above.

## The defaults table (`references/defaults.json`)

A draft, taken from PRD 3.2.3's example. The rule: choose the most conservative value, so the POC stays small.

| Field | Default | Why |
|---|---|---|
| `constraints.compute.hardware` | `single_gpu` | the PRD's example |
| `constraints.compute.runtime_limit_s` | `3600` | one hour per benchmark run keeps a run bounded |
| `constraints.other_limits` | `[]` | nothing is assumed |

`constraints.other_limits: []` is the natural empty state, not a value worth recording in `defaults_applied` — there is nothing there to have come from the text instead. The two scalar defaults above are the ones `defaults_applied` actually lists.

Whether a compute field is both quoted and defaulted is the type's check `check.research_brief_defaults_disjoint.v1`. This capsule's `defaults_only_when_silent` checks that each defaulted value equals the defaults table.

A missing metric is **not** defaulted. It is recorded as an `INPUT_INCOMPLETE` issue, because inventing an acceptance threshold would move the goalposts (PRD 3.5.4).

## Tests

- **Fixtures.** At least three intake cases, each with a recorded model reply and its expected Brief:
  - a clear request;
  - a request with no hardware stated, which exercises the default;
  - a vague request, which should give an `INPUT_AMBIGUOUS` issue and still a valid Brief.
- **Test cases:** one per admission check. `brief_matches_reference` compares each fixture's output with its expected Brief.
- **Replay.** Tests run on the recorded replies, so they are exact and need no live model.

## What RSI gets

- **A small surface:** `SKILL.md` and one worked example.
- **Exact deterministic checks:** they catch any invented requirement.
- **A measurable score:** how often a new prompt's Briefs match the expected ones on the fixtures, and on hidden fixtures from the RSI data foundation.

That makes this the easy first proof for RSI.

## What Model Routing gets

A real skill call with a known input and output schema. It can be routed to any model and compared on the same fixtures.

## Open

Resolved on 2026-10-01, when the Brief became the shared type [`research_brief`](../types/research-brief.md):

- **Intake shape** (was 3): now the type [`intake`](../types/intake.md).
- **Compute constraints without evidence** (was 6): `constraints.compute.quotes`, checked by `check.research_brief_defaults_disjoint.v1`.
- **Evidence without a source** (was 7): `evidence_source_id` on every quote. The objective, requirements and metrics cite the prompt. A minimum quote length is still open.
- **Open schema** (was 8): closed core plus `ext`; consumers read only declared fields.

Still open, tracked in [open issues](../open-issues.md):

1. **The Brief's owner.** The full PRD (1.6, 6.13) gives exact payload schemas to the Architecture Design; its section 6 is the implementation order, not payload specs. So the type page is the definition, and changes to what the Brief must mean go to Ramika.
2. **The Intention Compiler sync** (PRD 3.2 flag): Phase 2 may add dynamic behaviour; Phase 1 stays one-shot.
3. **Token budgets** (3.2.4) are recorded, not gated, at M1.
4. **What a metric's number means**: absolute, a difference, or a relative change.
5. **`hardware` is a free string** used like a fixed list.
6. **Contradictory input**: what the Brief holds when two stated constraints conflict.
7. **`constraints.frameworks`** comes from PRD 3.6.1, not from 3.2's own text. Confirm with Ramika.
