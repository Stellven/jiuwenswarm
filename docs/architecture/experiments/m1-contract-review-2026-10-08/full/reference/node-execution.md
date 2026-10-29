# Node Execution Contract

**AI reference.** Protected binder → governed runner, check-plan builder and gate. This is the finalized dispatch record, not a reusable CC declaration, planning template or invocation observation. [Exact schema](schemas/node-execution-contract.schema.json) is authoritative.

| Required fields | Meaning / consumer obligation |
|---|---|
| `schema_version`, `id`, `run_id`, `node_id`, `attempt_id`, `revision` | Versioned immutable contract within one run/node/attempt; changes require a new identity/revision and invalidated decisions |
| `objective`, `requirement_ids` | Assigned work and accepted Brief obligations; fixed preparation uses predefined profile obligation IDs |
| `bindings` | Each binding: `id`, `role`, exact `declaration_ref`, `implementation_refs`, `dependency_refs`, protected `admission_ref`, `effective_authority`, `limits` |
| `inputs`, `outputs` | Named ports: `name`, catalog `contract_id`, `version`, `required`; inputs additionally have exact `artifact_refs`. Finalized contracts contain concrete accepted refs, never future placeholders |
| `input_refs`, `required_outputs` | Compatibility inventories derived from port entries, not independently authored alternate bindings |
| `evidence_obligations` | Named required observation/check/evidence obligations; absence blocks release |
| `node_limits` | Aggregate `time_s`, `model_calls`, `memory_mb`, including reserved checking spend; binding limits constrain each work invocation and the pinned guard profile reserves verifier spend as well |
| `guard_profile_ref`, `policy_ref`, `configuration_ref`, `template_ref` | Exact independently owned frozen guard/profile, effective policy/configuration and originating template |

Effective authority names `network`, `network_allowlist`, `resource_reads`, `write_roots`, `tools`. It is an enforced intersection of admission, contract and run policy. Empty lists grant no access. `network: none` requires an empty allowlist. Scope/resource IDs resolve through protected manifests; no union across bindings. Verifier authority is read-only for its subject/evidence and cannot write gate state.

Optional `ext` is namespaced diagnostic data, not permission or release policy. Deterministic checks additionally establish unique binding/port IDs, catalog resolution, exact input inventory, output inventory, limit containment, admission eligibility, input scope and referenced artifact type. Schema validity alone cannot establish trusted authorship or allowed effects.

Contracts pin reusable guard profiles. Bound check plans reference the finalized contract and exact inputs; observations/context/decisions reference both. There is no contract↔bound-plan hashing cycle. Failure to bind accepted inputs, policy or evidence obligations blocks dispatch. A stale or mismatched subject/scope blocks release even if a verifier says PASS. [Complete examples](examples/README.md) illustrate this boundary without claiming runtime admission.

## M1 execution scope

M1 binds exactly one work CC per execution node. Additional work CCs occupy separate gated nodes with named typed dependencies. Verifier CCs are separate protected checking assignments; private helpers remain the owning CC's implementation. The declaration and node port names/types must match; no implicit aliases or internal CC calls are supported. Composite creation/execution, internal member graphs, fusion and merging remain later work. The PRD permits broader admitted capability sets, but does not require this bounded realization to use them. Unsupported forms block admission/binding; schema recognition of future metadata does not grant execution support.
