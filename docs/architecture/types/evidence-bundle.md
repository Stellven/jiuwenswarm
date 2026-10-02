---
type: payload-type
id: cc.type.evidence_bundle
version: 1
status: checked
tags: [types, m1, verifier]
---

> **Checked, not yet approved.** Compiles, its example validates, and it has been through review.

# `evidence_bundle`: what the judge is shown · version 1

The bounded semantic projection a judge needs against judged checks: criteria/rubrics, promises and admitted input/output values. The complete PRD Stage Evidence Bundle also includes immutable runtime/process/security evidence and is owned by [storage](../system/storage.md#required-evidence-and-derived-views). This model-facing projection never replaces that manifest.

**Made by** the gate host (M10), once per gated call, after Tier 1 passed, and stored with `record_input(..., origin="control")`. **Read by** the step's gate capsule, which the Binding names in `verifier`, called through the runner with `caller: gate` on input port `evidence_bundle` ([seams](../seams.md#evaluator-gate-and-verifier)). Its answer is a [`verifier_assessment`](verifier-assessment.md).

The bundle holds values, not references, because the judge is a model and reads text. Which Artifacts they came from is in the judged call's Observation, which the gate's Verification already names (INV-5).

## Fields

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `subject` | `object` | req | checked |  | The capsule whose output is judged |
| `subject.capsule_name` | `string` | req | checked |  | Its `identity.name`. Example: `research.compile_brief` |
| `subject.decl_hash` | `sha256` | req | checked |  | The version judged. The judge never has this `decl_hash` itself (rule `no_self_judging`) |
| `subject.summary` | `text` | req | checked |  | Its `identity.summary` |
| `criteria` | `list<object>` | req | checked |  | At least one. One entry per `judged` check in the Binding's `checks`, in that order |
| `criteria[].check_id` | `id` | req | checked |  | The check, as the Binding names it. The judge answers by this id |
| `criteria[].description` | `text` | req | checked |  | The check's `description`: what passes, in one line |
| `criteria[].rubric` | `text` | req | checked |  | The full text of the check's runner file (its rubric), fetched by the runner's `sha256` |
| `criteria[].over` | `enum(outputs, inputs_and_outputs)` | req | checked |  | What the criterion looks at. When `outputs`, the judge must not use `inputs` for it |
| `inputs` | `map<string, json>` | req | checked |  | Input port name to value, as the call received them. Empty when no criterion is `inputs_and_outputs` |
| `outputs` | `map<string, json>` | req | checked |  | Output port name to value |
| `issues` | `map<string, list<Reason>>` | req | checked |  | Output port name to the Artifact's `issues`. The judge reads the capsule's own caveats before judging |
| `ext` | `map<string, json>` | opt | checked |  | Extensions keyed by producer |

A `file` value appears as its text, by the runner's inline rule ([runner values](../capsule/runner.md#values-how-each-port-type-travels)). A value too large to inline makes the criterion `unknown`, never `pass` (INV-8).

## Type checks

| Check | Anchor | Over | Applies at | Runner | Author | What passes |
|---|---|---|---|---|---|---|
| `check.value_matches_type.v1` | deterministic | `outputs` | `both` | `cc/checks/registry/common.py:value_matches_type` | muk | the value matches the generated schema |
| `check.evidence_bundle_criteria_unique.v1` | deterministic | `outputs` | `both` | `cc/checks/registry/evidence_bundle.py:evidence_bundle_criteria_unique` | muk | no `check_id` appears twice in `criteria` |

## Example

For the `intent` step's judged check:

```json
{
  "subject": {"capsule_name": "research.compile_intent", "decl_hash": "5d41402abc4b2a76b9719d911017c592ae0a7b5e6d3b8e0c5e8f2f9a1b2c3d4e", "summary": "Extract goals, outcomes, constraints, ambiguities, conflicts and unknowns from a request's prompt into an IntentIR, each item citing an exact source span, using fixed rules and no model call."},
  "criteria": [{"check_id": "intent_fidelity", "description": "Every goal, outcome and constraint is stated in the prompt, and nothing central to the prompt is missing.", "rubric": "Read the prompt, then each item...", "over": "inputs_and_outputs"}],
  "inputs": {"intake": {"prompt": "Compare 4-bit and 8-bit quantisation; the report must cover both.", "channel": "cli", "documents": [], "skipped": []}},
  "outputs": {"intent_ir": {"generation": 0, "goals": [], "outcomes": [], "constraints": [], "ambiguities": [], "conflicts": [], "unknowns": []}},
  "issues": {"intent_ir": []}
}
```
