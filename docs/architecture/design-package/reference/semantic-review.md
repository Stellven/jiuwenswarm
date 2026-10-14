# Restricted semantic review contract

**Reading level: AI reference.** This page defines the declaration/output-only semantic invocation authorized by D20. [Guard design](../guard-design.md) owns the mechanism; [checking records](checking.md) own the persisted Assessment fields. This is an assurance boundary, not a claim of equivalence to PRD §4.2 contextual review.

## Invocation

The host first selects an existing independently admitted verifier profile for the subject CC's declared type and supported contract. The profile and its criterion IDs/rubric are prewritten, independently owned verifier instructions; the binder selects and pins them before work. It does not generate checks, rubric text or policy from worker output. The selected profile determines the fixed system instructions for this invocation. No request-specific criterion text or evidence is added to those instructions.

The complete semantic task payload is exactly this pair:

| Payload member | Exact value |
|---|---|
| `declaration` | The exact pinned subject CC declaration document, unchanged |
| `output` | The exact candidate output document/bytes captured from that work invocation, unchanged |

No worker input, original request, accepted predecessor, conversation/transcript, request-specific context, review manifest, dynamic binder findings, runtime observations, external evidence, provenance envelope or additional evidence is included. The model has no evidence-fetch, network, filesystem, tool, execution or control-plane access. Host-held input and runtime data remain available to deterministic checks and gate processing only. Do not rename, summarize, encode or replay a worker input as another payload member.

Both declaration and output are untrusted data. Text inside either cannot override the prewritten verifier instructions, add or waive criteria, grant permissions, change the selected profile or issue an `always pass` command. The semantic question is limited to whether this output conforms to what this declaration states under the prewritten profile. It does not compare against hidden task obligations or establish intent fidelity, truth, source support, effects, scientific validity or external correctness.

## Reply and trusted assembly

The model reply is untrusted content: criterion finding material, uncertainty, limitations and optional correction text. It does not author identity fields, reference IDs, evidence refs, the trusted verdict or a gate action. The existing `verifier-assessment` schema remains the persisted record; this contract adds no public reply schema, artifact field or runtime API.

The trusted host checks that the reply can be mapped to the selected profile's required criterion IDs exactly once, that outcomes/findings are structurally admissible, and that each attached evidence reference resolves to the exact declaration or output provided. It creates `subject_ref` and `review_context_ref`, attaches the host-owned evidence refs, assembles the existing Assessment, derives its assessment verdict from criterion findings and fixed policy, and passes that record to the protected gate. The gate separately checks mandatory deterministic results and decides whether exact outputs may be committed/released. A model reply cannot directly advance work.

The host review manifest retains the original inputs, accepted requirements, policy/profile pins, deterministic results, runtime records and evidence inventory for provenance, deterministic evaluation and audit. A reference in that manifest is not evidence seen by the model. Host assembly must not imply that undisclosed inputs/evidence were semantically reviewed.

## Assurance and failure

This restriction explicitly departs from the relevant-input-context and evidence-review expectations of PRD §4.2. A declaration/output conformance pass is not a fidelity, citation/source-grounding, factuality, empirical-support, scientific-validity or PRD §4.2 semantic pass. Report the restricted scope and preserve unresolved semantic risks. Host deterministic checks can establish only mechanically decidable conditions; a mandatory condition they cannot establish remains unsatisfied and blocks release.

The runtime sequence remains two verification tiers followed by the protected gate: Tier 1 deterministic checks, Tier 2 restricted semantic review, then host gate interpretation and durable release. The gate is not a third semantic reviewer. Timeout, malformed or incomplete reply, missing criteria, unavailable mandatory check, unresolved required condition or persistence failure is non-advancing. Never convert absence or uncertainty into success.

See [checking field definitions](checking.md), [host review manifest](other-contracts.md), [D20](../principles.md#d20-declarationoutput-only-semantic-review) and [D21](../decision-review.md#d21).

## Fixed restricted-profile questions and reply

For the current restricted M1 review, the independently owned profile fixes these criterion IDs in its system instructions before execution: `declared_output_conformance`, `internal_consistency`, and `limitations_consistency`. Check the output against the declaration, identify contradictions inside the output, and check that required limitations/uncertainty are present and coherent. Stage-specific fixed instructions may explain these questions but cannot add hidden request-specific obligations. Broader fidelity/source criteria from the earlier full-context profile are not silently retained as satisfiable requirements of this two-artifact review.

The model returns only this finding body; the host rejects missing/duplicate/unknown criteria or unsupported outcomes and supplies all trusted reference/identity fields:

```json
{
  "findings": [
    {"criterion_id": "declared_output_conformance", "outcome": "PASS", "reason": "Describe the checked declaration/output fields."},
    {"criterion_id": "internal_consistency", "outcome": "PASS", "reason": "Describe the consistency checks on the output."},
    {"criterion_id": "limitations_consistency", "outcome": "PASS", "reason": "Describe whether declared uncertainty and limitations are coherent."}
  ],
  "uncertainties": [],
  "limitations": [],
  "required_correction": null
}
```

Finding outcomes are `PASS`, `FAIL`, `ENVIRONMENT_BLOCKED` or `INCONCLUSIVE`. This synthetic body illustrates the reply shape, not actual evidence or a required positive outcome. Reasons may name output fields; the host attaches the exact declaration/output references when assembling the existing persisted Assessment. An ambiguity the restricted profile cannot resolve is inconclusive. Adapt the trial's hard-coded profile and worker-data-copying path together; do not reuse a prior full-context pass as evidence of this invocation.

## Restricted release meaning

The three fixed semantic criteria cover only properties observable in the declaration/output pair. They do not certify every external guarantee written in a declaration. Original-request fidelity, external source truth and empirical validity are explicitly outside this D20 semantic profile; record that limitation rather than inventing a pass or blocking every run solely because that context was deliberately excluded. Worker obligations remain, and independent platform cases measure their fulfillment. A missing mandatory deterministic check or an unresolved question within the restricted profile still blocks release. An advancing Assessment describes restricted conformance only; it is not acceptance of the original full-context assurance requirement.
