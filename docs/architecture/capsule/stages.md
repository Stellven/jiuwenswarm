---
type: capsule
tags: [capsule]
---

# Checked and unchecked at M1

> **Every field M1 knows about is in the schema now. M1 requires and tests only the checked ones.**

M1 is the PRD's first milestone. Every field row on the [schema pages](../schemas/schemas.md) is marked in its **M1** column (defined in [common](../schemas/common.md)):

- **checked:** required for M1 and tested for M1 completion.
- **unchecked:** part of the shared schema. When a value is present, admission validates its type and hashes it, but M1 neither requires nor tests it. The **Unlocks** column names what reads it.

Authors write a capsule once, in full. A tool that arrives after M1 reads the unchecked values already there. **Nobody rewrites a capsule.**

RSI is developed on a separate branch that shares this schema.

## What admission requires at M1

The [policy](../schemas/policy.md)'s `required` section sets this, not the schema. The first epoch requires of a Declaration:

- `identity.name`, `kind`, `summary`;
- exactly one of `carrier` or `body`;
- `ports.outputs` (at least 1), each with `check_id`;
- `changes.effect_class`;
- `guarantees.checks` (at least 1);
- every capability it calls listed in `needs.external`.

The policy `rules` then apply, each with its reason code. A new epoch may require more; the schema does not change (INV-17).

**For authors:** fill in every field you can answer. Leave out only what you do not know; [fields](fields.md) gives each field's default where it has one.

## What the unchecked fields unlock

Grouped by the **Unlocks** column. A field that unlocks several things appears in each group.

| Unlocks | Unchecked fields |
|---|---|
| RSI | Declaration `identity.lineage` (`parent_hash`, `relation`, `co_parent_hashes`), `guarantees.failure_modes`; Candidate `builder_evidence`, `test_aids`; test suite `inherited_from_hash`; Artifact `issues`; Binding `overlays`; Observation `trajectory_ref`; every Finding field |
| tracking | `identity.lineage`, `lineage.parent_hash`, `lineage.relation` |
| merge | `identity.lineage.co_parent_hashes` |
| budgets | Observation `cost.tokens`, `cost.money`; Binding `budget.tokens`, `budget.money` |
| planner | `Predicate.evaluable_at` |
| selection | `identity.tags`, `Predicate.state_source` |
| librarian | `guarantees.quality` (`criterion_check_id`, `target_rate`); every Finding field; Observation `effects_observed`; Standing `evidence` |
| importer | Candidate `source` (`system`, `uri`, `name`, `version`, `publisher`); `identity.namespace`, `identity.license`; `needs.dependencies`, `needs.config` |
| isolated verification | `needs.dependencies` (`runtime`, `platforms`, `packages`, `lockfile`), `needs.config` (`args`, `env`), `needs.secrets`, `needs.resources`; Verdict `environment` (`runtime`, `image_sha256`) |
| store | Candidate `source`, including `source.attestation`; `identity.namespace`, `identity.owner`, `identity.tags`, `identity.license` |
| remote capsules | `identity.remote` (`endpoint`, `version`, `interface_version_range`); `capsule_kind` values `mcp`, `a2a` |
| agents | `capsule_kind` values `subagent`, `agent_template` |
| composer | `members` (`id`, `decl_hash`), `structure`, `wiring` |
| retries | `idempotency_key`; `guarantees.failure_modes` |
| fallbacks | `guarantees.failure_modes` (`reason_code`, `when`, `retriable`) |
| certification | Candidate `requested_level`, `tests[].negative_control`; test case `negative_control`, test suite `access`; `visibility`; Verdict `evidence_requests`, `level: certified` |
| tracing | `trace` (`trace_id`, `span_id`) |
| quality labels | Artifact `issues` |
| exempt agents | Observation `trajectory_ref`; Verdict `level: exempt` |

The [tools page](tools.md) says which tool reads each group.

## What this means in practice

- A capsule admitted at M1 keeps its `decl_hash` when a new tool starts reading its unchecked fields. Its Verdict and Standing stay valid.
- **A new tool may need a new field.** It is added as an optional field in a v1.x schema. Readers apply its default when it is absent, but the hash does not: only defaults defined in v1.0 are filled in before hashing, and a field added later hashes as absent when it is absent. So existing `decl_hash` values never change. The schema never makes the field required; a later policy epoch can require it for new submissions only. The rules are on [invariants](../schemas/invariants.md).
