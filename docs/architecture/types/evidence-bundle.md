---
type: payload-type
id: cc.type.evidence_bundle
version: 1
status: draft
tags: [types, m1, verifier]
prd: [4.2.1, 4.2.6]
level: detail
---

> **Draft: example refreshed to the current production Requirement capability.** Shape checks are documentation evidence, not semantic acceptance.

# `evidence_bundle`: what the judge is shown Ã‚· version 1

PRD: 4.2.1, 4.2.6

The bounded semantic projection a judge needs against judged [checks](../capsule/fields.md#term-check): criteria/rubrics, promises and admitted input/output values. The complete PRD Stage Evidence Bundle also includes immutable runtime/process/security evidence and is owned by [storage](../system/storage.md#behavior-required-evidence-and-derived-views). This model-facing projection never replaces that manifest.

**Made by** the gate host (M10), once per gated call, after [Tier 1](../verification.md#term-tier-1) passed, and stored with `record_input(..., origin="control")`. **Read by** the step's gate [capsule](../capsule/capsule.md#term-capability-capsule), which the [Binding](../schemas/binding.md#term-binding) names in `verifier`, called through the runner with `caller: gate` on input port `evidence_bundle` ([seams](../system/seams.md)). Its answer is a [`verifier_assessment`](verifier-assessment.md).

The bundle holds values, not references, because the judge is a model and reads text. Which [Artifacts](../schemas/artifact.md#term-artifact) they came from is in the judged call's [Observation](../schemas/observation.md#term-observation), which the gate's [Verification](../schemas/verification-record.md#term-verification) already names (INV-5).

## Key terms

| Term | Meaning |
|---|---|
| <a id="term-evidence-bundle"></a>**evidence_bundle** (also: evidence bundle) | The bounded package a judge is shown: the criteria or rubrics, the producer's promises, and the admitted input and output values as text. The Gate host builds it once per gated call, after Tier 1 passed. |

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

A `file` value appears as its text, by the runner's inline rule ([runner values](../capsule/runner-handlers.md#values-how-each-port-type-travels)). A value too large to inline makes the criterion `unknown`, never `pass` (INV-8).

## Type checks

| Check | Anchor | Over | Applies at | Runner | Author | What passes |
|---|---|---|---|---|---|---|
| `check.value_matches_type.v1` | deterministic | `outputs` | `both` | `cc/checks/registry/common.py:value_matches_type` | cc-team | the value matches the generated schema |
| `check.evidence_bundle_criteria_unique.v1` | deterministic | `outputs` | `both` | `cc/checks/registry/evidence_bundle.py:evidence_bundle_criteria_unique` | cc-team | no `check_id` appears twice in `criteria` |

## Example

For Requirement, the embedded input/output values below are generated from their canonical type examples by architecture lint. The zero hash is illustrative, not admitted authority. This example exercises the projection schema; actual criterion and source-grounding checks still require their own [fixtures](../system/test-surfaces.md#term-fixture).

<!-- generated:example-view -->
```json
{
  "subject": {
    "capsule_name": "research.compile_brief",
    "decl_hash": "0000000000000000000000000000000000000000000000000000000000000000",
    "summary": "Compile source-grounded objectives, constraints and acceptance into a Research Brief."
  },
  "criteria": [
    {
      "check_id": "brief_objective_faithful",
      "description": "The Brief preserves mandatory task requirements without inventing evidence.",
      "rubric": "Check each mandatory requirement against the supplied source evidence; missing or unsupported coverage cannot pass.",
      "over": "inputs_and_outputs"
    }
  ],
  "inputs": {
    "intake": {
      "prompt": "Reduce the VRAM use of my model's attention by at least 30% without losing more than 1% accuracy. Don't retrain from scratch.",
      "channel": "cli",
      "resources": [
        {
          "resource_id": "res-doc-1",
          "kind": "reference_document",
          "source": "supplied",
          "path": "input/flash-attention.pdf",
          "label": "FlashAttention reference"
        },
        {
          "resource_id": "res-repo-1",
          "kind": "project_asset",
          "source": "supplied",
          "path": "input/repo",
          "label": "User baseline code"
        },
        {
          "resource_id": "res-data-1",
          "kind": "validation_data",
          "source": "supplied",
          "path": "input/datasets/validation",
          "label": "Validation split"
        }
      ],
      "documents": [
        {
          "document_id": "doc-1",
          "path": "input/flash-attention.pdf",
          "format": "pdf",
          "size_bytes": 1824311,
          "text": "FlashAttention: Fast and Memory-Efficient Exact Attention ..."
        }
      ],
      "skipped": [
        {
          "path": "input/slides.pptx",
          "reason": "unsupported_format"
        }
      ]
    },
    "source_text": {
      "text": "Reduce peak VRAM by at least 30% without losing more than 1% accuracy.",
      "source_ref": "prompt",
      "source_kind": "prompt",
      "content_sha256": "d52e0efde980d3066305e9f49d37fe2e546f68a096dadf76e70efc542df9a51f",
      "offset_basis": "unicode_codepoint"
    }
  },
  "outputs": {
    "research_brief": {
      "objective": "Reduce attention-layer VRAM use while keeping accuracy close to the baseline.",
      "objective_evidence": "Reduce the VRAM use of my model's attention",
      "in_scope_items": [
        {
          "item": "the model's attention layers",
          "evidence": "my model's attention",
          "evidence_source_id": "prompt"
        }
      ],
      "out_of_scope_items": [
        {
          "item": "retraining from scratch",
          "evidence": "Don't retrain from scratch",
          "evidence_source_id": "prompt"
        }
      ],
      "constraints": {
        "compute": {
          "hardware": "single_gpu",
          "runtime_limit_s": 3600,
          "quotes": []
        },
        "frameworks": [],
        "other_limits": []
      },
      "mandatory_requirements": [
        {
          "requirement_id": "R1",
          "statement": "VRAM reduction of at least 30%",
          "evidence": "by at least 30%",
          "evidence_source_id": "prompt"
        },
        {
          "requirement_id": "R2",
          "statement": "accuracy loss of at most 1%",
          "evidence": "without losing more than 1% accuracy",
          "evidence_source_id": "prompt"
        }
      ],
      "optional_preferences": [],
      "metrics": [
        {
          "metric_id": "M1",
          "requirement_id": "R1",
          "name": "vram_reduction",
          "comparator": "gte",
          "target": 30,
          "unit": "percent",
          "basis": "relative_percent",
          "evidence": "by at least 30%",
          "evidence_source_id": "prompt"
        },
        {
          "metric_id": "M2",
          "requirement_id": "R2",
          "name": "accuracy_loss",
          "comparator": "lte",
          "target": 1,
          "unit": "percent",
          "basis": "unspecified",
          "evidence": "without losing more than 1% accuracy",
          "evidence_source_id": "prompt"
        }
      ],
      "defaults_applied": [
        {
          "field": "constraints.compute.hardware",
          "value": "single_gpu",
          "reason": "no hardware stated"
        },
        {
          "field": "constraints.compute.runtime_limit_s",
          "value": 3600,
          "reason": "no runtime stated"
        }
      ]
    }
  },
  "issues": {
    "research_brief": []
  }
}
```
<!-- /generated:example-view -->
