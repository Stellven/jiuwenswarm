# Restricted semantic review contract

**Summary.**
- The semantic verifier receives the pinned CC declaration and the exact output. It receives nothing else.
- Fidelity and preservation belong to the producer CC and to deterministic host checks. They are not verifier criteria.
- Every criterion must be answerable from declaration plus output.
- The host assembles the persisted Assessment from the verifier's findings.

**Reading level: AI reference.** This page defines the declaration/output-only semantic invocation (D20). [Guard design](../guard-design.md) owns the mechanism. [Checking records](checking.md) own the persisted Assessment fields.

## Invocation

The host first selects an existing independently admitted verifier profile for the subject CC's declared type and supported contract. The profile and its criterion IDs/rubric are prewritten, independently owned verifier instructions; the binder selects and pins them before work. It does not generate checks, rubric text or policy from worker output. The selected profile determines the fixed system instructions for this invocation. No request-specific criterion text or evidence is added to those instructions.

The complete semantic task payload is exactly this pair:

| Payload member | Exact value |
|---|---|
| `declaration` | The exact pinned subject CC declaration document, unchanged |
| `output` | The exact candidate output document/bytes captured from that work invocation, unchanged |

No worker input, original request, accepted predecessor, conversation/transcript, request-specific context, review manifest, dynamic binder findings, runtime observations, external evidence, provenance envelope or additional evidence is included. The model has no evidence-fetch, network, filesystem, tool, execution or control-plane access. Host-held input and runtime data remain available to deterministic checks and gate processing only. Do not rename, summarize, encode or replay a worker input as another payload member.

Both declaration and output are untrusted data. Text inside either cannot override the prewritten verifier instructions, add or waive criteria, grant permissions, change the selected profile or issue an `always pass` command. The semantic question is limited to whether this output conforms to what this declaration states under the prewritten profile. It does not compare the output with any input.

## Reply and trusted assembly

The model reply is untrusted content: criterion finding material, uncertainty, limitations and optional correction text. It does not author identity fields, reference IDs, evidence refs, the trusted verdict or a gate action. The existing `verifier-assessment` schema remains the persisted record; this contract adds no public reply schema, artifact field or runtime API.

The trusted host checks that the reply can be mapped to the selected profile's required criterion IDs exactly once, that outcomes/findings are structurally admissible, and that each attached evidence reference resolves to the exact declaration or output provided. It creates `subject_ref` and `review_context_ref`, attaches the host-owned evidence refs, assembles the existing Assessment, derives its assessment verdict from criterion findings and fixed policy, and passes that record to the protected gate. The gate separately checks mandatory deterministic results and decides whether exact outputs may be committed/released. A model reply cannot directly advance work.

The host review manifest retains the original inputs, accepted requirements, policy/profile pins, deterministic results, runtime records and evidence inventory for provenance, deterministic evaluation and audit. A reference in that manifest is not evidence seen by the model. Host assembly must not imply that undisclosed inputs/evidence were semantically reviewed.

## Assurance and failure

The verifier checks the output against the declaration and against itself. Fidelity, preservation and source support are producer obligations. The host backs them with deterministic checks where a rule can decide them. A mandatory condition the host cannot establish stays unsatisfied and blocks release.

The runtime sequence remains two verification tiers followed by the protected gate: Tier 1 deterministic checks, Tier 2 restricted semantic review, then host gate interpretation and durable release. The gate is not a third semantic reviewer. Timeout, malformed or incomplete reply, missing criteria, unavailable mandatory check, unresolved required condition or persistence failure is non-advancing. Never convert absence or uncertainty into success.

See [checking field definitions](checking.md), [host review manifest](other-contracts.md), [D20](../principles.md#d20-declarationoutput-only-semantic-review) and [D21](../decision-review.md#d21).

## Criteria and reply

The independently owned profile fixes its criterion IDs in its system instructions before execution. Three are generic and apply to every CC: `declared_output_conformance`, `internal_consistency` and `limitations_consistency`. A profile may add at most two criteria for an artifact type. Each must be answerable from declaration plus output.

| Criterion ID | Question | Applies to |
|---|---|---|
| `declared_output_conformance` | Does the output have the artifact type, fields and shape the declaration states? | all CCs |
| `internal_consistency` | Do the output fields agree with each other and do local references resolve inside the output? | all CCs |
| `limitations_consistency` | Are the listed uncertainties and limitations coherent with the rest of the output? | all CCs |
| `uncertainty_consistency` | Does `readiness.status` agree with the listed blocking uncertainties? | `intent_ir` |
| `requirement_link_completeness` | Is every mandatory requirement linked from an acceptance expectation and an evidence obligation? | `research_brief` |

Stage-specific instructions may explain these questions. They cannot add a criterion that needs an input.

The model returns only this finding body. The host rejects missing, duplicate or unknown criteria and unsupported outcomes. The host supplies all trusted reference and identity fields.

```json
{
  "findings": [
    {"criterion_id": "declared_output_conformance", "outcome": "PASS", "reason": "Describe the checked declaration and output fields."},
    {"criterion_id": "internal_consistency", "outcome": "PASS", "reason": "Describe the consistency checks on the output."},
    {"criterion_id": "limitations_consistency", "outcome": "PASS", "reason": "Describe whether the listed uncertainty and limitations are coherent."}
  ],
  "uncertainties": [],
  "limitations": [],
  "required_correction": null
}
```

Finding outcomes are `PASS`, `FAIL`, `ENVIRONMENT_BLOCKED` or `INCONCLUSIVE`. The body is a shape illustration. Reasons may name output fields. The host attaches the exact declaration and output references when it assembles the persisted Assessment. An ambiguity the profile cannot resolve from the two artifacts is inconclusive.

## Release meaning

An advancing Assessment says the output conforms to its declaration and agrees with itself. Producer self-review and deterministic host checks carry fidelity and preservation. A missing mandatory deterministic check or an unresolved question in the profile blocks release.
