# Authoring and publishing a capability capsule

**Reading level: human potential.** Question answered: What must a CC author provide and which decisions belong to infrastructure?

## Lifecycle

1. **Declare.** State purpose, kind, typed ports, preconditions, dependencies, effects, guarantees, candidate checks, and applicable limits. Keep objectives, node IDs, permissions, verifier assignment, and run policy outside. Declared checks do not define the mandatory bundle.
2. **Choose form.** A leaf points to implementation by locator and hash. Composite creation/execution and merging remain later work; do not author them for M1.
3. **Build.** Keep code separate and pin covered files. Preserve the declaration's meaning. An M1 subnode binds one admitted CC under its Subnode Execution Contract. Additional work CCs use separate gated subnodes within their declared node; verifier invocations remain separate checking assignments. A CC assesses; the gate decides and releases.
4. **Verify.** Run applicable tests and characterization checks; retain outputs, check results, and evidence references against exact declaration/implementation hashes. A passing self-test is not admission or approval of mandatory checks.
5. **Prepare mandatory checks.** An independent check maintainer authors and versions the deterministic bundle and records its exact CC compatibility. The CC author cannot approve or alter it. Contract/policy checks are added separately at protected binding.
6. **Admit.** M1 initial use is limited to the explicitly recorded bootstrap set with its pinned shared bundle; this does not constitute capsule-specific admission evidence. New or changed versions require the governed protected admission gate once available. Under D21, M2 protected automatic admission may admit a passing RSI-produced version only when a pre-approved compatibility association uniquely covers that exact candidate version; the candidate cannot choose or alter its bundle, and missing or ambiguous coverage blocks admission. Unsupported checks block admission or binding. Eligibility applies to future plans only and never changes frozen pins.
7. **Publish and select.** Store immutable CC/bundle versions, association and admission record. M1 uses human activation; M2 automatic eligibility never changes frozen pins. Reversion affects future selection only.

## Authoring rules

Prefer wrapping a working JiuwenSwarm/OpenJiuwen capability. Keep the summary task-independent. Declare effects and repeat safety; prose grants no permission. Type and check outputs. A composite pins members by hash and exposes only a boundary it can guarantee.

The preserved sources disagree on shapes and requiredness. Use the reconciled [declaration reference](declaration.md) and [current schema](../reference/schemas/capsule-declaration.schema.json); import historical declarations through an explicit mapping. Do not independently invent keys. Model/service calls use governed context and admitted injected services; a verifier returns an assessment and never performs workflow halt/continue itself.

Protected configuration or the frozen graph assigns runtime criteria. Keep verifiers, gates, check runners, hidden fixtures, and their behavioral dependency closure outside RSI mutation. Declared checks do not grant release authority.

## Change rules

Preserve each version's meaning. Changes to ports, guarantees, effects, or compatibility require a new version and admission. Record lineage where supported. Library changes apply to future freezes; active runs keep pinned versions and checks.


For an allowed RSI implementation change, protected candidate packaging derives new declaration/body pins for the new immutable version. Semantic ports, guarantees, permissions and frozen interface remain unchanged. The proposer edits only authorized implementation paths; it cannot rewrite declaration policy. Admission checks both unchanged semantics and the exact changed body closure.
