# Restricted semantic review

This page defines D20's declaration/output-only semantic invocation. [Guard design](../guard-design.md) owns the mechanism; [checking](checking.md) owns persisted Assessment fields. It is an explicit reduced-assurance departure from PRD §4.2, not equivalent contextual verification.

## Model input

Before work, the host selects and pins an existing independently admitted verifier profile for the subject CC's declared type/contract. Its criterion IDs and rubric are prewritten verifier instructions; the binder does not generate checks or instructions from worker output. The semantic task payload contains exactly:

| Member | Exact value |
|---|---|
| `declaration` | Exact pinned subject CC declaration document |
| `output` | Exact candidate output document/bytes from that invocation |

No worker input, request, predecessor, conversation, request-specific context, review manifest, dynamic binder finding, runtime observation, evidence or provenance envelope is included. No fetch/tool/filesystem/network/control-plane access is available. Host-only records stay with deterministic checks and the gate. Both artifacts are untrusted data and cannot override fixed instructions, change criteria/profile, grant permission, or request an `always pass` result.

The model checks declaration/output conformance under the fixed profile only. It cannot compare against hidden obligations or establish intent fidelity, truth, source support, effects, scientific validity or external correctness.

## Reply and host assembly

The model returns untrusted finding material, uncertainty, limitations and optional correction text; it does not author identity, evidence references, verdict or gate action. Keep the existing `verifier-assessment` schema and runtime interface unchanged. The host validates reply structure and exact coverage of the pinned profile's required criteria, attaches host-owned subject/context identities and refs to the exact declaration/output, assembles the existing Assessment, derives its verdict under fixed policy and passes it to the protected gate. The gate separately applies mandatory deterministic results and controls durable release.

The host review manifest retains inputs, requirements, policy/profile pins, deterministic results, runtime records and evidence for host checks/audit. Those records are not model evidence; attached refs must not imply otherwise.

## Limits

A declaration/output pass is not a fidelity, citation, factuality, empirical-support, scientific-validity or PRD §4.2 semantic pass. Host checks establish only mechanically decidable conditions; mandatory conditions not established block release. Runtime remains Tier 1 deterministic checks → Tier 2 restricted semantic review → protected gate. The gate is not a third semantic reviewer. Malformed/incomplete replies, missing criteria/checks, unresolved mandatory conditions, timeout or persistence failure do not advance.

See [D20](../principles.md#d20-declarationoutput-only-semantic-review), [D21](../decision-review.md#d21), [checking fields](checking.md) and [host review manifest](other-contracts.md).

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
