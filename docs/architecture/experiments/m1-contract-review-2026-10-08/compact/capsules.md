# Capsules, verification, and library

**Reading level: human potential.** Question answered: How do reusable CCs execute, get checked and enter the library; what composition remains future work?

## Invocation and authority

`V ⊆ C`: runtime verifier capsules are a subset of capability capsules. `G ∩ C = ∅`: protected gates are separate infrastructure roles. The [composition notation](glossary.md#composition-notation) distinguishes subtype, dependency, binding and permission intersection. A gate uses a verifier assessment; it does not inherit capsule identity or delegate release authority to the capsule author.

## Exact verification boundary

**Required now.** Every work invocation, including planning and delivery, has a pinned verification assignment. Protected configuration establishes mandatory checks from the Node Execution Contract, every participating CC declaration, applicable accepted obligations, artifact type and run policy. Fixed preparation uses the qualified original request and protected template obligations before an accepted Research Brief exists; planned research uses the Brief. Invocation checks protect intermediate boundaries; the node aggregate gate also checks the objective and all required outputs/evidence before successor release. The planner may add checks but cannot remove obligations. Missing supported verification blocks readiness.

## Evaluator Gate internals and referee protection

**Required now.** The Evaluator Gate boundary composes deterministic checking, a runtime verifier CC assessment and protected decision/release infrastructure. The verifier returns an **assessment verdict**: for example, “the submitted result violates this obligation,” with evidence and uncertainty. It reports conformance of the exact subject against accepted inputs and obligations, not an instruction to stop or advance. The protected gate interprets that assessment with mandatory check results and bound policy, then issues the **authoritative gate verdict**. Run-state must durably commit that decision before the scheduler advances. The capsule author, producer and verifier have no successor-dispatch or acceptance-policy authority; a supplied boolean or free-text command never changes outer control flow directly. [Human callbacks](failure-and-human.md) define every non-advancing outcome and mode-specific routing.

## Library lifecycle

**Required now.** Publish declarations and referenced implementation closure together as immutable versions. Admission validates the supported contract, pinned dependencies, permissions, and supplied verification evidence. Provisional admission means limited evidence, not guaranteed correctness. Retain historical admitted versions and decisions.

## Composition and optimization

**Later work.** A multi-CC node would be a run-specific objective binding; a composite CC would be a reusable capability with an internal graph. M1 supports neither and leaves their implementation design open.

## Connected behavior summary

CC is a reusable declaration plus exact admitted implementation, not a node or run contract. M1 includes bounded code tools/prompts/skills/adapters, with one work CC per node. Composite creation/execution and merging remain later work. [CC fields](capsule/declaration.md) and [schema](reference/schemas/capsule-declaration.schema.json) standardize identity/version, ports, entrypoints, dependencies, conditions, effects/resources, limits, evidence/checking and mutation scope.

Human-readable `make_capsule.md` derives from `capsule.json`. Hand-written and RSI versions undergo declaration/integrity/provenance/compatibility/self-test admission; provisional is M1 trust level. Changed implementation gets a new identity. Self-tests support admission, not runtime release authority. Human activates/suspends/deprecates/rolls back; retained version history supports reproduction.

Binder selects admitted pins from captured inventory; node contract narrows permission. Runner intersects admission, contract and policy per CC, captures every invocation and aggregates node evidence/checking. Additional work CCs use separate gated nodes. Private helpers remain the owning CC's responsibility; no internal CC dispatch, member graph, composite execution or merging in M1. Unsupported forms block admission/binding.

CC authors produce payload/assessment; trusted capture owns envelope/hash/provenance, protected gate owns release. No model self-selection, capability installation, mutation of gate/referee, automatic promotion or permission widening. Suspension blocks eligible start/release without silently rewriting history. [Workflow](workflow.md), [guard](guard-design.md) and [RSI](offline-rsi.md) connect these boundaries.
