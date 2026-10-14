# Capsules, verification, and library

**Reading level: human potential.** Question answered: How do reusable CCs execute, get checked and enter the library; what composition remains future work?

## Invocation and authority

`V ⊆ C`: runtime verifier capsules are a subset of capability capsules. `G ∩ C = ∅`: protected gates are separate infrastructure roles. The [composition notation](glossary.md#composition-notation) distinguishes subtype, dependency, binding and permission intersection. A gate uses a verifier assessment; it does not inherit capsule identity or delegate release authority to the capsule author.

Every admitted/usable CC version is explicitly associated with an immutable, independently owned deterministic check bundle. The bundle is a separately versioned library record, not capsule-author-controlled content; reuse across CC versions requires an explicit compatibility association. M1 protected admission pins the exact CC and bundle versions. Execution and freeze pin both; a new CC version or bundle association follows the applicable admission path. Existing frozen runs retain their pins. Capsule-pinned checks supplement contract/policy checks and do not replace the semantic verifier or protected gate.

## Exact verification boundary

**Core path:** fixed Compiler Intent + Requirement work and gates produce the accepted Research Brief; the planner proposes the downstream DAG, while the protected binder assigns mandatory profiles/checks, validates coverage and graph feasibility, and freezes before dispatch. A planner failure halts unless the run explicitly selected the retained static SwarmFlow fallback mode at run entry. See [core build](core-build.md) and D19.

**Required now.** Every work invocation, including planning and delivery, has a pinned verification assignment. Protected configuration combines each participating CC version's pinned deterministic bundle with mandatory checks from the node/subnode contracts, CC/dependency pins, accepted obligations, artifact type and policy. The planner may add checks but cannot remove the CC bundle or contract/policy obligations. Missing bundle association or unsupported mandatory checks block readiness, binding and freeze. Invocation checks protect intermediate boundaries; aggregate node verification controls successor release. Fixed preparation uses protected templates and the qualified original request; planned research uses the accepted Brief.

## Evaluator Gate internals and referee protection

**Required now.** The Evaluator Gate boundary composes host deterministic checking, a restricted semantic verifier CC assessment and protected decision/release infrastructure. The model receives exactly the subject CC declaration and exact output plus fixed instructions. It does not receive hidden inputs/criteria/evidence or fetch capability. It cannot establish fidelity, source support or scientific validity ([D24](decision-review.md#d24)). Those are producer obligations backed by host checks. See the [Verifier page](reference/capsules/verifier.md) and [capsule build references](reference/capsules/README.md). The host keeps a host-only, audit-only review manifest. The host assembles the unchanged persisted Assessment and gate applies mandatory host checks and policy. The capsule author, producer and verifier have no successor-dispatch or acceptance-policy authority. [Human callbacks](failure-and-human.md) define non-advancing outcomes.

## Library lifecycle

**Required now.** Publish declarations and referenced implementation closure together as immutable versions. The M1 bootstrap catalog is an explicit, bounded set of existing versions designated for the initial build; file presence alone never grants use. Bind each bootstrap version to an immutable independently maintained shared checking bundle and record its exact identity. This bootstrap record enables the first main path but is not evidence of capsule-specific correctness or a completed governed admission gate. Keep activation and suspension under human standing control. Once the governed admission gate is implemented, disable bootstrap defaults for every new or changed version; those candidates require a protected eligibility decision with independent evidence and an exact compatible bundle. Existing bootstrap records remain usable unless suspended or revoked. Retain versions, bundle associations and decisions.

## RSI boundary

RSI is an optional, separately buildable target. It has no import, startup, test, or core acceptance dependency; the core parent handoff remains independent of RSI availability. RSI cannot change live workflow or mandatory verifier/referee boundaries.

M1 retains human activation. Under D21, M2 (November 2026) protected automatic admission for a passing RSI-produced version validates the exact compatible check-bundle pin. Admission may resolve the bundle only from a pre-approved compatibility association that uniquely covers the candidate version; the candidate cannot choose or alter it, and missing or ambiguous coverage blocks admission. A passing version may become eligible for future plans without human activation. It cannot self-admit or change M1 or frozen runs. M3 composition/fusion is targeted for December 2026; spatiotemporal lifecycle work is targeted for 2027.

## Composition and optimization

**M1 distinction.** A node may contain predefined work/verifier subnodes and protected gates, each governed by its own assignment. Composite/merged CC creation and arbitrary intra-capsule dispatch remain later work; fixed node cooperation does not create a reusable composite capability.

## Connected behavior summary

CC is a reusable declaration plus exact admitted implementation, not a node or run contract. M1 includes bounded code tools/prompts/skills/adapters, with one work CC per subnode. Composite creation/execution and merging remain later work. [CC fields](capsule/declaration.md) and [schema](reference/schemas/capsule-declaration.schema.json) standardize identity/version, ports, entrypoints, dependencies, conditions, effects/resources, limits, evidence/checking and mutation scope.

Human-readable `make_capsule.md` derives from `capsule.json`. Hand-written and RSI versions undergo declaration/integrity/provenance/compatibility/self-test admission and pin an independently maintained check bundle; provisional is M1 trust level. Changed implementation or bundle association follows admission as a new immutable version/association. Self-tests support admission, not runtime release authority. Human activates/suspends/deprecates/rolls back in M1; retained CC and bundle history supports reproduction.

Binder selects admitted CC versions and their exact bundle associations from captured inventory; node contract narrows permission. Runner intersects admission, contract and policy per CC, combines capsule-bundle and run-specific checks, captures every invocation and aggregates node evidence/checking. Additional work CCs use separate gated subnodes within their declared node. Private helpers remain the owning CC's responsibility; no internal CC dispatch, member graph, composite execution or merging in M1. Unsupported forms or missing bundles block admission/binding.

CC authors produce payload/assessment; trusted capture owns envelope/hash/provenance, protected gate owns release. No model self-selection, capability installation, mutation of gate/referee, automatic promotion or permission widening. Suspension blocks eligible start/release without silently rewriting history. [Workflow](workflow.md), [guard](guard-design.md) and [RSI](offline-rsi.md) connect these boundaries.

## Per-CC build coverage

Use the [CC ports and checking map](cc-build-coverage.md) for all ten work capabilities, the Planner semantic-verifier context and the shared implementation-completion rule.
