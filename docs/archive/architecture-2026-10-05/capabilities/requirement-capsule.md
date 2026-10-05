---
id: cap.requirement-capsule
type: capability
status: draft
tags: [design, draft, m1, capsule]
level: detail
provides: []
depends_on: []
prd: [3.2.3, 3.2.4, 3.2.5, 3.2.6, 3.2.7, 4.7.5]
---

# `requirement_capsule`: design

PRD: 3.2.3, 3.2.4, 3.2.5, 3.2.6, 3.2.7, 4.7.5

> Answers: How does the requirement capsule turn the intake and accepted intent into the Research Brief?

The requirement [capsule](../capsule/capsule.md#term-capability-capsule) sits at flow node `N_req`, designed from PRD 3.2 Requirement Compilation ([full PRD](../../product/prd-m1-full-2026-10-02.txt)). It follows the [Declaration](../capsule/fields.md) and the [`make_capsule.md`](../capsule/make-capsule.md) format. Hashes are shown as `<author kit>`: the author kit computes them once the files exist.

## What it does

It turns the [Qualified Intake Package](../types/intake.md#term-intake) from Ingestion (3.1.5) and the **accepted intent** (`intent_ir`, from [`research.compile_intent`](intent-compile.md)) into the **[Research Brief](../types/research-brief.md#term-research-brief)**: the contract every later stage reads. It makes one model call, with no clarification dialogue, and does not wait for approval (3.2.3, 3.2.7).

| PRD step | What the capsule does |
|---|---|
| 3.2.1 Intent Interpretation | states the core research objective, without choosing a solution |
| 3.2.2 Context Scoping | lists `in_scope_items` and `out_of_scope_items` (the PRD's `in_scope` and `out_of_scope`), taken only from the intake text |
| 3.2.3 Ambiguity Resolution | fills missing parameters from a fixed table of conservative defaults, such as `single_gpu`, and records each default it applied |
| 3.2.4 Constraint Resolution | extracts stated compute limits: hardware, runtime, token budget |
| 3.2.5 Requirement Prioritization | splits requirements into `mandatory_requirements` and `optional_preferences` |
| 3.2.6 Acceptance Definition | defines concrete target metrics, each with a comparator and a threshold |
| 3.2.7 Contract Confirmation | returns everything as one Research Brief JSON, which goes to the Evaluator [Gate](../verification.md#term-gate) (4.2) |

**The design choice that matters:** every item the Brief says the user *stated* carries a short quote from the intake text. A deterministic check then confirms the quote is really there. So the model cannot invent a requirement and present it as the user's. Anything not stated is either a recorded default or absent. `compile_intent` grounds its output the same way, with source spans.

## The Research Brief

The Brief is the shared [payload type](../types/types.md#term-payload-type) [`research_brief`](../types/research-brief.md). That page is its only definition: fields, type [checks](../capsule/fields.md#term-check) and an example. This capsule's input types are [`intake`](../types/intake.md) and [`source_text`](../types/source-text.md), and the required, Gate-accepted [`intent_ir`](../types/intent-ir.md). The exact port change (adding `intent_ir` to the node inputs) is `PENDING_SOURCE`, see [decisions](../decisions.md#pending-source-do-not-invent); types are expected unchanged.

## Where it sits

Fixed flow node `N_req` in [flow](../flow.md), run once after the intent Gate accepts. Work capsule `research.compile_brief`; Gate is the profile `research.accept_brief.v1` of the shared `research.verifier`. Inputs: `intake`, `source_text` and accepted `intent_ir`.

## Gate

- **Gate:** shared `research.verifier`, profile [`research.accept_brief.v1`](brief-gate.md), following [the gate capsule pattern](../capsule/gate-capsules.md).
- **[Tier 1](../verification.md#term-tier-1):** this capsule's deterministic checks below, and the `research_brief` type's checks.
- **[Tier 2](../verification.md#term-tier-2):** the step check `brief_objective_faithful`, defined in the profile [`research.accept_brief.v1`](brief-gate.md). A fail [halts](../system/lifecycle.md#term-halt) the run before the planner.

## Existing code it touches

Its [model turns](../system/model-bridge.md#term-model-turn) go through M05 and `cc.adapters.codex` ([integration](../system/integration.md#codex-the-model-for-m05)). Nothing else.

## Declaration (`capsule.json`)

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
      {"name": "source_text", "type": "source_text", "required": true,
       "description": "Canonical prompt projection; all source spans use this text."},
      {"name": "intent_ir", "type": "intent_ir", "required": true,
       "description": "The accepted IntentIR of the same prompt. Never a source of quotes."}
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
       "description": "Every evidence quote appears verbatim in its evidence_source_id: the intake prompt, or the text of the named document. The objective, every requirement and every metric cite the prompt.", "author": "cc-team"},
      {"id": "defaults_only_when_silent", "anchor": "deterministic", "target": "ports.outputs.research_brief",
       "over": "outputs", "applies_at": "both",
       "runner": {"ref": "checks/brief_checks.py:defaults_only_when_silent", "sha256": "<author kit>"},
       "description": "A structural check on the Brief alone, not a judgment about the intake: a field listed in defaults_applied has no evidence quote anywhere and its value equals the defaults table's value; a field with an evidence quote is never also in defaults_applied.", "author": "cc-team"},
      {"id": "requirements_and_metrics_present", "anchor": "deterministic", "target": "ports.outputs.research_brief",
       "over": "outputs", "applies_at": "both",
       "runner": {"ref": "checks/brief_checks.py:requirements_and_metrics_present", "sha256": "<author kit>"},
       "description": "At least one metric, unless every mandatory requirement is qualitative and `issues` records an `INPUT_INCOMPLETE` explaining why no metric was written. The shape, the id rules and at least one mandatory requirement are the type's checks.", "author": "cc-team"},
      {"id": "metric_target_grounded", "anchor": "deterministic", "target": "ports.outputs.research_brief",
       "over": "outputs", "applies_at": "both",
       "runner": {"ref": "checks/brief_checks.py:metric_target_grounded", "sha256": "<author kit>"},
       "description": "Each metric's target number appears in its own evidence quote (after normalizing things like '30%' and '30 percent'), so a metric's threshold cannot silently diverge from the requirement it operationalizes.", "author": "cc-team"},
      {"id": "brief_matches_reference", "anchor": "reference", "target": "ports.outputs.research_brief",
       "over": "inputs_and_outputs", "applies_at": "admission",
       "runner": {"ref": "checks/brief_checks.py:matches_reference", "sha256": "<author kit>"},
       "description": "On a test case, the Brief's metrics match the expected ones by requirement_id, comparator and target, not by name (a name mismatch such as vram_reduction vs vram_reduction_pct must not fail the fixture).", "author": "cc-team"}
    ]
  },
  "evolution": {"rsi": "none"}
}
```

**Why these choices:**

- **`kind: skill`,** because PRD 3.2.1 calls for one LLM generation. The protected broker selects the [frozen](../system/lifecycle.md#term-freeze) Phase 1 Codex route; author front matter cannot override the route. The call is recorded and replayable in [fixtures](../system/test-surfaces.md#term-fixture).
- **`effect_class: pure`:** it writes nothing outside its output.
- **`intent_ir` is a required accepted input:** the intent call and its Gate run first ([flow](../flow.md)). The [Declaration](../capsule/fields.md#term-declaration) below lists the port, and `prep.plan.json` wires the accepted `intent_ir` to it. This deviates from the PRD ([deviation 2](../decisions.md#prd-deviations)).
- **M1 [RSI](../rsi.md#term-rsi) does not target this capsule.** Manual prompt/example/default revisions create an admitted new version; the defaults_only_when_silent check validates the frozen table.
- **The checks' code (`checks/`) is not in `may_change`.** The referee stays fixed.
- **No judged check of its own.** The judgement "the objective says what the user asked" is the step's, so it is a Gate criterion judged through the brief profile ([brief gate](brief-gate.md)). The capsule is then admitted with deterministic checks only, and needs no admission judge.

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

## Prompt brief

The rows of the [prompt brief](../capsule/prompt-brief.md) for `SKILL.md`. The wording is the prompt layer's; everything here is fixed.

| Row | Brief |
|---|---|
| Job | Turn the intake into one Research Brief in one model call. Do not ask the user anything, wait for approval, or pick a solution |
| Inputs | `intake`: resources and prompt. `source_text`: canonical span basis. `intent_ir`: the accepted intent from `research.compile_intent` (required), never a source of quotes |
| Output | `research_brief`, field by field as the [type page](../types/research-brief.md) defines it |
| Rules | The Declaration's checks: every stated item is quoted (`brief_evidence_grounded`), defaults match the table (`defaults_only_when_silent`), requirements and metrics are present (`requirements_and_metrics_present`), every metric target is grounded (`metric_target_grounded`). The type's own checks: a compute field is quoted or defaulted and never both, and requirement ids are unique ([`research_brief`](../types/research-brief.md#type-checks)). At least one mandatory requirement exists |
| Grounding | Every item the user stated carries a verbatim quote and its `evidence_source_id`. The objective, requirements and metrics quote the prompt. Scope comes from the intake only. Nothing is invented and presented as stated |
| Gaps | A missing compute field takes its value from `references/defaults.json` and is listed in `defaults_applied`. A missing metric is never defaulted: raise `INPUT_INCOMPLETE`. A vague request raises `INPUT_AMBIGUOUS` and still returns a valid Brief. A request that contradicts itself raises `INPUT_CONTRADICTORY` |
| Issue codes | `INPUT_AMBIGUOUS`, `INPUT_INCOMPLETE`, `INPUT_CONTRADICTORY` |
| Tools | none |
| Must not | Invent a requirement or a threshold. Choose a method, model or library the prompt did not name. Restate the schema |
| Examples wanted | A clear request. A request with no hardware stated, which exercises the default. A vague request, which raises `INPUT_AMBIGUOUS`. One case with a metric missing, which raises `INPUT_INCOMPLETE` |
| RSI surface | None in the frozen M1 whitelist; manual candidate revisions use normal admission |
| Done when | Each fixture's recorded reply reproduces its expected Brief (metrics matched by `requirement_id`, comparator and target, not by name), all checks pass, and the [brief gate](brief-gate.md)'s `brief_objective_faithful` passes |

## Checks

The checks are the `checks` array in the Declaration above (admission and Gate Tier 1 kinds). The Tier 2 step check is in the [brief gate](brief-gate.md).

## Tests

- **Fixtures.** At least three intake cases, each with a recorded model reply and its expected Brief:
  - a clear request;
  - a request with no hardware stated, which exercises the default;
  - a vague request, which should give an `INPUT_AMBIGUOUS` issue and still a valid Brief.
- **Test cases:** one per admission check. `brief_matches_reference` compares each fixture's output with its expected Brief.
- **Replay.** Tests run on the recorded replies, so they are exact and need no live model.

## RSI boundary

M1 RSI cannot mutate this capability. The frozen whitelist targets Screening's rank helper and conditionally its text prompt. Manual capsule revisions use normal admission/versioning.

## What Model Routing gets

A real skill call with a known input and output schema. The protected model broker supplies the frozen Phase 1 Codex route; capsule authors cannot choose an alternate endpoint. Isolated experimental routes use explicit experimental policy.

## Adopted defaults and failure behavior

The canonical Brief type is authoritative. Token budgets are recorded and bounded by the model/run policy; hardware and frameworks remain user-request values until a supported trusted method/package adapter validates them. Contradictory requests retain INPUT_CONTRADICTORY evidence; vague requests retain INPUT_AMBIGUOUS, and missing required quantitative targets retain INPUT_INCOMPLETE. These halt readiness when no valid experimental contract can be derived, without clarification or repair loops. Defaults are applied only when the source is silent, never to overwrite contradictory evidence.

Metric units and comparison basis are preserved explicitly; unspecified percentage interpretation [blocks](../system/modules.md#term-block) Hypothesis rather than weakening a target. Structural quote validation requires nonempty verbatim quotes and valid source identity; semantic fidelity is independently assessed by the Brief profile.

## Acceptance seeds

These rows seed the spec AC table. Each is derived from the behavior on this page; the coding spec sets final thresholds and fixtures. Level is BLOCK, [BOUNDARY](../v-model.md#term-boundary) or [SYSTEM](../v-model.md#term-system).

| AC ID | Source | Observable criterion | Level |
|---|---|---|---|
| cap.requirement-capsule.AC-01 | PRD 3.2.1, N_req | On a clear-request fixture with a recorded reply, the output equals the expected research_brief exactly (brief_matches_reference). | BLOCK |
| cap.requirement-capsule.AC-02 | PRD 3.2.3, N_req | When the request states no hardware, the Brief carries the table default (single_gpu, runtime_limit_s 3600) and lists exactly those defaults in defaults_applied; no default overwrites a stated value. | BLOCK |
| cap.requirement-capsule.AC-03 | PRD 3.2.3, US-04 | A vague request records an INPUT_AMBIGUOUS issue and still returns a valid Brief; no clarification dialogue happens. | BLOCK |
| cap.requirement-capsule.AC-04 | PRD 3.2.6 | A missing target metric is recorded as INPUT_INCOMPLETE and is never defaulted; a contradictory request retains INPUT_CONTRADICTORY evidence. | BLOCK |
| cap.requirement-capsule.AC-05 | US-04 | A requirement not grounded in a nonempty verbatim quote of the source fails the quote-grounding check at Tier 1. | BLOCK |
| cap.requirement-capsule.AC-06 | N_req, G_req | Brief profile test: a Brief whose objective names a solution the request did not name fails brief_objective_faithful at Gate G_req. | BOUNDARY |
| cap.requirement-capsule.AC-07 | N_req, N_plan | The planner is not called until research_brief is committed and G_req has [released](../system/lifecycle.md#term-release). | SYSTEM |
| cap.requirement-capsule.AC-08 | N_req | The call makes at most 1 model turn and no nested capsule call. | BLOCK |
