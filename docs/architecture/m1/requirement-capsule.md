---
type: design
status: draft
tags: [design, draft, m1, capsule]
---

# `requirement_capsule`: design

> **Draft.** The first M1 capsule, designed from PRD 3.2 Requirement Compilation ([PRD section 3](../../product/prd-m1-section3.md)). It follows the [Declaration](../capsule/fields.md) and the [`make_capsule.md`](../capsule/make-capsule.md) format. Hashes are shown as `<author kit>`: the author kit computes them once the files exist.

## What it does

It turns the Qualified Intake Package from Ingestion (3.1.5) into the **Research Brief**: the contract every later stage reads. It makes one model call, with no clarification dialogue, and does not wait for approval (3.2.3, 3.2.7).

| PRD step | What the capsule does |
|---|---|
| 3.2.1 Intent Interpretation | states the core research objective, without choosing a solution |
| 3.2.2 Context Scoping | lists `in_scope` and `out_of_scope`, taken only from the intake text |
| 3.2.3 Ambiguity Resolution | fills missing parameters from a fixed table of conservative defaults, such as `single_gpu`, and records each default it applied |
| 3.2.4 Constraint Resolution | extracts stated compute limits: hardware, runtime, token budget |
| 3.2.5 Requirement Prioritization | splits requirements into `mandatory_requirements` and `optional_preferences` |
| 3.2.6 Acceptance Definition | defines concrete target metrics, each with a direction and a threshold |
| 3.2.7 Contract Confirmation | returns everything as one Research Brief JSON, which goes to the Evaluator Gate (4.2) |

**The design choice that matters:** every item the Brief says the user *stated* carries a short quote from the intake text. A deterministic check then confirms the quote is really there. So the model cannot invent a requirement and present it as the user's. Anything not stated is either a recorded default or absent. `compile_intent` grounds its output the same way, with source spans.

## The Research Brief (draft payload schema)

The Research Brief schema is open: it fixes the minimum below, and allows extra fields. PRD section 6, "Payload Specs", will own the final schema; this draft is our proposal for it.

| Field | Type | Meaning |
|---|---|---|
| `brief_version` | string | `"1"` |
| `objective` | string | the core research objective, in one or two sentences, with no chosen solution |
| `objective_evidence` | string | a quote from the intake text that supports it |
| `in_scope` | list of `{item, evidence}` | what the research covers; `evidence` is a quote from the intake text |
| `out_of_scope` | list of `{item, evidence}` | what it must not cover |
| `constraints.compute` | object | `hardware` (string, such as `single_gpu`); optional `gpu_memory_gb`, `runtime_limit_s`, `token_budget` |
| `constraints.other` | list of `{item, evidence}` | any other stated limit: data, time, tools, policy |
| `mandatory_requirements` | list of `{id, statement, evidence}` | must be met; at least one |
| `optional_preferences` | list of `{id, statement, evidence}` | nice to have |
| `metrics` | list of `{name, direction, comparator, target, unit, evidence}` | acceptance metrics. `direction` is `increase` or `decrease`; `comparator` is `>=` or `<=`; `target` is a number. Stage 3.7 takes its pass and fail thresholds from these |
| `defaults_applied` | list of `{field, value, reason}` | every value taken from the defaults table instead of the text |

Caveats, such as a vague request or a missing metric, go in the output Artifact's `issues`. Their codes are `INPUT_AMBIGUOUS`, `INPUT_INCOMPLETE` and `INPUT_CONTRADICTORY`. The Brief is still returned.

**Example**, for the request "Reduce the VRAM use of my model's attention by at least 30% without losing more than 1% accuracy. Don't retrain from scratch.":

```json
{
  "brief_version": "1",
  "objective": "Reduce attention-layer VRAM use while keeping accuracy close to the baseline.",
  "objective_evidence": "Reduce the VRAM use of my model's attention",
  "in_scope": [{"item": "the model's attention layers", "evidence": "my model's attention"}],
  "out_of_scope": [{"item": "retraining from scratch", "evidence": "Don't retrain from scratch"}],
  "constraints": {"compute": {"hardware": "single_gpu"}, "other": []},
  "mandatory_requirements": [
    {"id": "R1", "statement": "VRAM reduction of at least 30%", "evidence": "by at least 30%"},
    {"id": "R2", "statement": "accuracy loss of at most 1%", "evidence": "without losing more than 1% accuracy"}
  ],
  "optional_preferences": [],
  "metrics": [
    {"name": "vram_reduction", "direction": "increase", "comparator": ">=", "target": 30, "unit": "percent", "evidence": "by at least 30%"},
    {"name": "accuracy_loss", "direction": "decrease", "comparator": "<=", "target": 1, "unit": "percent", "evidence": "without losing more than 1% accuracy"}
  ],
  "defaults_applied": [{"field": "constraints.compute.hardware", "value": "single_gpu", "reason": "no hardware stated"}]
}
```

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
      {"name": "intake", "type": "json", "required": true,
       "description": "The Qualified Intake Package: the prompt, and the extracted text of each reference document.",
       "value_schema": {"uri": "payloads/intake.schema.json", "sha256": "<author kit>"}},
      {"name": "intent_ir", "type": "json", "required": false,
       "description": "Optional IntentIR from compile_intent, used as hints only.",
       "value_schema": {"uri": "payloads/intent_ir.schema.json", "sha256": "<author kit>"}}
    ],
    "outputs": [
      {"name": "research_brief", "type": "json", "check_id": "brief_evidence_grounded",
       "description": "The Research Brief.",
       "value_schema": {"uri": "payloads/research_brief.schema.json", "sha256": "<author kit>"}}
    ]
  },
  "needs": {
    "when": [{"id": "prompt_nonblank", "path": "inputs.intake.prompt", "op": "matches", "value": "\\S"}],
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
       "description": "Every evidence quote appears verbatim in the intake prompt or a document's text.", "author": "muk"},
      {"id": "defaults_only_when_silent", "anchor": "deterministic", "target": "ports.outputs.research_brief",
       "over": "inputs_and_outputs", "applies_at": "both",
       "runner": {"ref": "checks/brief_checks.py:defaults_only_when_silent", "sha256": "<author kit>"},
       "description": "Every applied default comes from references/defaults.json, and only for a field the intake does not state.", "author": "muk"},
      {"id": "requirements_and_metrics_present", "anchor": "deterministic", "target": "ports.outputs.research_brief",
       "over": "outputs", "applies_at": "both",
       "runner": {"ref": "checks/brief_checks.py:requirements_and_metrics_present", "sha256": "<author kit>"},
       "description": "At least one mandatory requirement and one metric; every metric has a direction, comparator, numeric target and unit; requirement ids are unique.", "author": "muk"},
      {"id": "brief_matches_reference", "anchor": "reference", "target": "ports.outputs.research_brief",
       "over": "inputs_and_outputs", "applies_at": "admission",
       "runner": {"ref": "checks/brief_checks.py:matches_reference", "sha256": "<author kit>"},
       "description": "On a test case, the Brief's requirements and metrics match the expected ones by name, comparator and target.", "author": "muk"},
      {"id": "objective_faithful", "anchor": "judged", "target": "ports.outputs.research_brief",
       "over": "inputs_and_outputs", "applies_at": "node",
       "runner": {"ref": "checks/brief_rubric.md", "sha256": "<author kit>"},
       "description": "The objective states what the user asked for, chooses no solution, and the scope adds nothing the request did not say.", "author": "muk"}
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
- **The judged check is marked `node`.** A `node` check also runs at admission, on the outputs of test calls. So admitting this capsule needs the admission judge, `verifier_capsule`, admitted first. Until then, `objective_faithful` can be left out of the first version and added in the next.

## `make_capsule.md` (generated)

````markdown
---
name: research.compile_brief
kind: skill
decl_hash: <author kit>
interface_hash: <author kit>
rsi: propose
generated_from: capsule.json
---

# research.compile_brief

## What it does

Compile a research request and its reference text into a Research Brief: objective, scope, constraints, prioritised requirements and acceptance metrics, each stated item quoted from the request, gaps filled from a fixed defaults table.

## Inputs

| Port | Type | Required | Meaning |
|---|---|---|---|
| `intake` | json (`payloads/intake.schema.json`) | yes | the prompt, and each reference document's extracted text |
| `intent_ir` | json (`payloads/intent_ir.schema.json`) | no | IntentIR from compile_intent, as hints |

## Outputs

| Port | Type | Checked by |
|---|---|---|
| `research_brief` | json (`payloads/research_brief.schema.json`) | `brief_evidence_grounded` |

## Acceptance rules

**Tier 1: programmatic**

| Check | Passes when | Runs at |
|---|---|---|
| `brief_evidence_grounded` | every evidence quote appears verbatim in the intake | admission and every call |
| `defaults_only_when_silent` | every applied default is from the table, and only where the intake is silent | admission and every call |
| `requirements_and_metrics_present` | at least one mandatory requirement and one well-formed metric | admission and every call |
| `brief_matches_reference` | on a test case, requirements and metrics match the expected ones | admission |

**Tier 2: judged by the verifier**

| Check | Passes when | Runs at |
|---|---|---|
| `objective_faithful` | the objective reflects the request, chooses no solution, and adds no scope | every call |

## Needs

- **Before a call:** the prompt is not blank.
- **Calls:** nothing.
- **Network:** none.
- **Time budget:** 300 s.
- **Human interaction:** none.

## Changes

- **Effect class:** `pure`.

## RSI

- **RSI may:** propose a new version, which waits for a person.
- **RSI may change only:** `files:SKILL.md`, `files:references/brief_example.json`.
- **Notes for a builder:** the prompt is the main lever. The defaults table is policy, not prompt: change it by hand.

## Files

| Path | sha256 |
|---|---|
| `SKILL.md` | <author kit> |
| `references/defaults.json` | <author kit> |
| `references/brief_example.json` | <author kit> |
````

## The defaults table (`references/defaults.json`)

A draft, taken from PRD 3.2.3's example. The rule: choose the most conservative value, so the POC stays small.

| Field | Default | Why |
|---|---|---|
| `constraints.compute.hardware` | `single_gpu` | the PRD's example |
| `constraints.compute.runtime_limit_s` | `3600` | one hour per benchmark run keeps a run bounded |
| `constraints.other` | `[]` | nothing is assumed |

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

1. **The Research Brief schema's owner.** PRD section 6, "Payload Specs", isn't out yet. Send this draft to Ramika as our proposal.
2. **The Intention Compiler sync (PRD 3.2 flag).** It may add dynamic behaviour in Phase 2; Phase 1 stays one-shot.
3. **The Qualified Intake Package's exact shape** belongs to Ingestion (3.1.5). This design assumes `{prompt, documents: [{path, text, size_bytes}]}`.
4. **Token budgets** (3.2.4) are recorded in the Brief as a constraint, but M1 does not gate on tokens.
