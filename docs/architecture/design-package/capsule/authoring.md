# Authoring and publishing a capability capsule

**Reading level: human potential.** Question answered: What must a CC author provide and which decisions belong to infrastructure?

## Lifecycle

1. **Declare.** State purpose, kind, typed ports, preconditions, dependencies, effects, guarantees, candidate checks, and applicable limits. Keep objectives, node IDs, permissions, verifier assignment, and run policy outside. Declared checks document claims and candidate coverage; they are not the mandatory bundle.
2. **Choose form.** A leaf points to implementation by locator and hash. Composite creation/execution and merging remain later work; do not author them for M1.
3. **Build.** Keep code separate and pin covered files. Preserve the declaration's meaning. An M1 subnode binds one admitted CC under its Subnode Execution Contract. Additional work CCs use separate gated subnodes within their declared node; verifier invocations remain separate checking assignments. A CC assesses; the gate decides and releases.
4. **Verify.** Run applicable tests and characterization checks; retain outputs, check results, and evidence references against the exact declaration and implementation hashes. A passing self-test alone is not admission or approval of mandatory checks.
5. **Prepare mandatory checks.** An independent check maintainer authors and versions a deterministic bundle, records the exact CC version(s) it supports, and supplies compatibility evidence. The capsule author cannot approve or alter this bundle. Runtime contract and policy checks are added separately by protected binding.
6. **Admit.** M1 starts from the explicitly designated existing bootstrap set, with exact CC and shared-bundle identities recorded. This is initial availability, not a capsule-specific correctness verdict. Once the governed gate is implemented, new or changed versions require protected admission that reviews identity, dependency closure, permissions, independent evidence and compatible bundle. Under D21, protected M2 admission may automatically admit a passing RSI-produced version only when a pre-approved compatibility association uniquely covers that exact candidate version; the candidate cannot choose or alter its bundle, and missing or ambiguous coverage blocks admission. Eligibility for future plans is separate from any M1 human activation and never alters frozen runs. Unsupported required checks block admission or binding.
7. **Publish and select.** Store immutable CC and bundle versions, their association and admission record. M1 uses human activation. D21's M2 path may make a passing version eligible for future plans through protected admission. Existing runs retain their exact pins; reversion changes future selection only.

## Authoring rules

Prefer wrapping a working JiuwenSwarm/OpenJiuwen capability. Keep the summary task-independent. Declare effects and repeat safety; prose grants no permission. Type and check outputs. A composite pins members by hash and exposes only a boundary it can guarantee.

The preserved sources disagree on shapes and requiredness. Use the reconciled [declaration reference](declaration.md) and [current schema](../reference/schemas/capsule-declaration.schema.json); import historical declarations through an explicit mapping. Do not independently invent keys. Model/service calls use governed context and admitted injected services; a verifier returns an assessment and never performs workflow halt/continue itself.

Protected configuration or the frozen `run_plan` ([contract](../reference/run-plan.md)) assigns runtime criteria. The binder pins the mandatory check bundle of each CC version. The Planner can only suggest extra checks. Per-CC pages: [capsule build references](../reference/capsules/README.md). Keep verifiers, gates, check bundles/runners, hidden fixtures, and their behavioral dependency closure outside RSI mutation. Capsule-associated checks do not grant release authority; the protected gate alone releases work.

## Change rules

Preserve each version's meaning. Changes to implementation, ports, guarantees, effects or check compatibility require a new immutable version/association and the applicable admission path. A bundle change creates a new bundle version and association; it cannot silently update a CC version or active run. Record lineage where supported. Library changes apply to future freezes; active runs keep pinned versions and checks.


For an allowed RSI implementation change, protected candidate packaging derives new declaration/body pins for the new immutable version. Semantic ports, guarantees, permissions and frozen interface remain unchanged. The proposer edits only authorized implementation paths; it cannot rewrite declaration policy. Admission checks both unchanged semantics and the exact changed body closure.
