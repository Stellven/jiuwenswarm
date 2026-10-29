# Capability capsules and library

CC is a reusable declaration plus exact admitted implementation, not a node or run contract. M1 includes bounded code tools/prompts/skills/adapters and supported composites. [CC fields](capsule/declaration.md) and [schema](reference/schemas/capsule-declaration.schema.json) standardize identity/version, ports, entrypoints, dependencies, conditions, effects/resources, limits, evidence/checking and mutation scope.

Human-readable `make_capsule.md` derives from `capsule.json`. Hand-written and RSI versions undergo declaration/integrity/provenance/compatibility/self-test admission; provisional is M1 trust level. Changed implementation gets a new identity. Self-tests support admission, not runtime release authority. Human activates/suspends/deprecates/rolls back; retained version history supports reproduction.

Binder selects admitted pins from captured inventory; node contract narrows permission. Runner intersects admission, contract and policy per CC, captures every invocation and aggregates node evidence/checking. Composite members require compatible typed ports, pinned closure, per-member limits/checks and aggregate output; no pooled privilege or hidden internal work. Unsupported composition blocks. Fuse only through separate admission against unfused reference, not live mutation.

CC authors produce payload/assessment; trusted capture owns envelope/hash/provenance, protected gate owns release. No model self-selection, capability installation, mutation of gate/referee, automatic promotion or permission widening. Suspension blocks eligible start/release without silently rewriting history. [Workflow](workflow.md), [guard](guard-design.md) and [RSI](offline-rsi.md) connect these boundaries.

<a id="capsules-verification-and-library"></a>
<a id="invocation-and-authority"></a>
<a id="exact-verification-boundary"></a>
<a id="evaluator-gate-internals-and-referee-protection"></a>
<a id="library-lifecycle"></a>
<a id="composition-and-optimization"></a>
