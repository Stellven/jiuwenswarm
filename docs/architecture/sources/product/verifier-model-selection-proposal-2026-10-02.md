# PRD for M1 — Verifier Model Selection and Integration Readiness

**Status:** Proposed; target interface and milestone scope require agreement with Stellven and the relevant component owners.

## 1. Goal

Select a model suitable for future Verifier fine-tuning, produce a justified technical recommendation, and integrate the selected model without changing its weights into an agreed experimental verification path (possibly a branch of the repository).

This milestone must establish:

- Which verification responsibility the model will perform.
- Why the selected model is a suitable candidate.
- How the framework will invoke it and consume its results.
- What data, resources, and evaluation would be required for future fine-tuning.

It does not establish that the selected model improves verification quality.

“Unmodified model” means an existing model checkpoint [a specific saved version of a model] with no additional training performed by this workstream. It may already have been instruction-tuned by its publisher.

## 2. Component responsibility

This workstream owns model selection, design of the future fine-tuning procedures, and model-specific integration work agreed with the Verifier and Model Routing owners.

The intended target is the model used for Tier 2 semantic verification [judging meaning, reasoning, and evidence beyond fixed code checks].

The Verifier owner retains responsibility for verification criteria, accepted result formats, and how judgments affect gate decisions. The Model Routing owner retains responsibility for model provisioning and selection mechanisms. The RSI owner retains responsibility for proposing and testing capability changes.

This draft targets the workflow’s Tier 2 Verifier. Whether the same model will also judge RSI-generated candidates must be agreed with the Verifier and RSI owners.

## 3. In scope — whitelist

- Map the intended Verifier responsibility to the available architecture and implementation.
- Compare a bounded set of candidate models using documented capabilities, licensing, weight availability, future training feasibility, deployment constraints, and expected resource requirements.
- During model selection, I may go online and search for benchmarks to aid my decision.
- Select one candidate, recording its exact version, rationale, limitations, and unresolved assumptions.
- Produce an architecture and fine-tuning strategy analysis covering the integration boundary, candidate training approaches, data requirements, estimated resources, risks, and a future evaluation plan.
- Integrate the selected unmodified model through the agreed framework interface in an isolated experimental configuration.
- Perform functional integration checks and regression checks [checks that existing behavior still works].
- Document how to disable the experimental integration and restore the baseline configuration.

Exact interfaces, training algorithms, and deployment mechanisms belong in the technical design produced by this work.

## 4. Out of scope — blacklist

- Training or fine-tuning model weights.
- Executing quality benchmarks or claiming performance improvements measured in this project.
- Running an RSI optimization campaign to assess the candidate.
- Replacing the active Phase 1 Codex verifier route without an explicit product decision.
- Changing verification policies, acceptance thresholds, or gate authority.
- Allowing RSI to modify its own referee.
- Training-data production at scale or building a new general-purpose routing system.

Functional checks may establish that requests, responses, error handling, and restoration of the baseline configuration work. They do not establish the model’s verification accuracy.

## 5. Dependencies and handoffs

The named component owners must be confirmed before integration.

| Collaborator | Required input | Handoff from this workstream |
|---|---|---|
| Stellven / product and architecture owners | Confirmed target, milestone scope, deployment constraints, and resolution of conflicting documents | Model recommendation, design proposal, unresolved decisions, and approval request |
| Verifier / Evaluator owner | Input contract, rubric [rules for judging an output], result contract, and failure handling | Compatible model integration and functional evidence |
| Model Routing owner | Supported model interface, endpoint access, configuration rules, and permitted experimental route | Exact model identity, required capabilities, and configuration requirements |
| RSI owner | Confirmation of whether the existing RSI judge is a consumer and which interface applies | Integration guidance; no changes to RSI’s scoring policy |
| Data Foundations / fixture owner | Available evidence formats, labeling responsibilities, and access restrictions | Future training-data requirements and a plan separating training from held-out evaluation data |

Sealed evaluation fixtures [test cases withheld to preserve an independent assessment] must not become training data.

## 6. Invariants

- The existing agreed baseline remains usable with the experimental integration disabled.
- Experimental activation is explicit and reversible.
- The model remains read-only with respect to the artifact being reviewed.
- Model judgments cannot bypass required deterministic checks or independently grant workflow advancement.
- Existing gate policies and decision rules remain under their current owner’s control.
- Model and integration versions are identifiable in execution records.
- Unavailable endpoints, malformed responses, and other integration failures cannot be converted into a successful verification result.
- Model weights remain unchanged throughout this milestone.

## 7. Acceptance criteria

**AC1 — Target and scope agreed:** The intended consumer, integration interface, responsible owners, and permitted experimental environment are documented. Conflicts with the master PRD are explicitly resolved before dependent integration.

**AC2 — Model selection complete:** The recommendation identifies an exact model version, explains the selection against stated constraints, and distinguishes published claims from properties verified in this project.

**AC3 — Future fine-tuning proposal complete:** The proposal explains the target behavior, candidate approach and alternatives, data and labeling needs, resource estimates, risks, and a future evaluation protocol. No training or benchmark execution is required.

**AC4 — Functional integration demonstrated:** A bounded, non-benchmark example reaches the selected model through the agreed interface and returns a result accepted by that interface. The evidence identifies the actual model used. A mocked response alone does not satisfy this criterion.

**AC5 — Failure handling demonstrated:** Applicable checks show that invalid responses and unavailable model access produce explicit errors or non-advancing outcomes.

**AC6 — Baseline preservation demonstrated:** Agreed baseline checks pass before and after the change. Disabling or rolling back the integration restores the original route. Existing failures are recorded separately.

**AC7 — Proposal approved:** Stellven’s approval of the selected model and future fine-tuning plan is recorded against a specific document revision. This approval does not establish model quality or authorize training within this milestone.

## 8. Definition of Done

All acceptance criteria are satisfied, and the following are delivered through the project’s existing task structure:

- Model-selection analysis and technical design.
- Future fine-tuning and evaluation proposal.
- Unmodified-model integration and configuration instructions.
- Functional and regression evidence.
- Instructions for disabling the experimental integration and restoring the baseline configuration.
- Recorded approval and any remaining limitations.

Missing endpoint access or a missing consumer interface leaves integration incomplete; it must not be reported as successfully demonstrated.

## 9. Implementation order

1. Confirm the target Verifier responsibility and reconcile the PRD/architecture scope.
2. Agree on the consumer interface, ownership, access, and resource constraints.
3. Compare candidates and prepare the model-selection and fine-tuning proposal.
4. Record Stellven’s decision on the proposed model and approach.
5. Establish baseline checks and implement the isolated integration.
6. Verify request/response handling, failures, baseline preservation, and restoration of the original configuration.
7. Complete the handoff with evidence and the approved future-work proposal.

Document preparation and candidate analysis may proceed while interface or access decisions remain unresolved.