---
type: capsule
tags: [capsule]
---

# Checked and unchecked at M1

> **Every field M1 knows about is in the schema now. M1 requires and tests only the checked ones.**

This page is the one definition of the **M1** and **Unlocks** columns in every field table. M1 is the PRD's first milestone.

- **checked:** required for M1 and tested for M1 completion.
- **unchecked:** part of the shared schema. When a value is present, admission validates its type and hashes it, but M1 neither requires nor tests it. The **Unlocks** column names the tool or feature that reads it.

Authors write a capsule once, in full. A tool that arrives after M1 reads the unchecked values already there. **Nobody rewrites a capsule.** A capsule admitted at M1 keeps its `decl_hash`, Verdict and Standing when a new tool starts reading its unchecked fields. A field added later is optional and never changes existing hashes (INV-16, [invariants](../schemas/invariants.md)).

What admission actually requires is set by the [policy](../schemas/policy.md)'s `required` section, not by the schema (INV-17). **Authors:** fill in every field you can answer; the [Declaration](fields.md) gives each field's default where it has one.

## What the unchecked fields unlock

Generated from the Unlocks column of every field table; do not edit by hand. A field that unlocks several things appears in each group. [CC tooling and field enforcement](tools.md) says which tools read each group and distinguishes the M1 checked status from actual runtime enforcement.

<!-- sync:unlocks -->
| Unlocks | Unchecked fields |
|---|---|
| RSI | Declaration `identity.lineage.co_parent_hashes`, `needs.external[].purpose`, `guarantees.failure_modes`, `evolution.notes`; Candidate `builder_evidence`, `test_aids`; Check, test case and test suite `inherited_from_hash`; Binding `overlays`; Observation `trajectory_ref`; Finding `kind`, `subjects`, `step_id`, `text`, `evidence`, `measure`, `detail` |
| budgets | Observation `cost.tokens`, `cost.money` |
| certification | Candidate `tests[].negative_control`, `requested_level`; Check, test case and test suite `negative_control`, `access`; Verdict `evidence_requests`; Common `visibility` |
| composer | Declaration `identity.lineage.co_parent_hashes`, `members`, `wiring` |
| exempt agents | Observation `trajectory_ref` |
| fallbacks | Declaration `guarantees.failure_modes` |
| importer | Declaration `identity.namespace`, `identity.license`, `needs.dependencies`, `needs.config`; Candidate `source` |
| isolated verification | Declaration `needs.dependencies`, `needs.config`, `needs.secrets`; Verdict `environment` |
| librarian | Declaration `guarantees.quality`; Standing `evidence`; Observation `effects_observed`; Finding `kind`, `subjects`, `step_id`, `text`, `evidence`, `measure`, `detail` |
| merge | Declaration `identity.lineage.co_parent_hashes` |
| planner | Declaration `Predicate.evaluable_at`; Binding `role` |
| remote capsules | Declaration `identity.remote` |
| retries | Declaration `guarantees.failure_modes`; Common `idempotency_key` |
| selection | Declaration `identity.tags`, `Predicate.state_source` |
| store | Declaration `identity.namespace`, `identity.owner`, `identity.tags`, `identity.license`; Candidate `source` |
| tracing | Common `trace` |
<!-- /sync:unlocks -->

Also unchecked, but values rather than field rows: Binding `budget.tokens` and `budget.money` (budgets); Verdict `level` values `certified` (certification) and `exempt` (exempt agents); `capsule_kind` values `mcp`, `a2a` (remote capsules), `subagent`, `agent_template` (agents) and `composite` (composer), in the [policy](../schemas/policy.md).
