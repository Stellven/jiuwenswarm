---
type: reference
tags: [reference, index]
---

# Terms

Where each term is defined. Each definition lives on one page only; this is an index.

| Term | Defined in |
|---|---|
| Capability capsule (CC, 能力胶囊), kind, control code, gate | [Capability Capsule](../capsule/capsule.md) |
| Declaration, carrier, body, remote, members, wiring, predicate (`needs.when`), effect class, failure mode, lineage, `decl_hash`, `interface_hash`, `code_sha256` | [Declaration](../capsule/fields.md) |
| M1, checked, unchecked, Unlocks | [Checked and unchecked at M1](../capsule/stages.md) |
| Singleton, composite, fusion, spatiotemporal composability | [Composition](../capsule/composition.md) |
| Author kit, admission, runner, check runner, library store, lineage index, librarian, RSI submitter, selection index, cost meter, importer, isolated verification sandbox, store, composer, remover | [Tools](../capsule/tools.md) |
| RSI (recursive self-improvement), RSI permissions | [RSI](../capsule/rsi.md) |
| Level, trust | [Trust](../capsule/trust.md) |
| Library, admission, test storage, librarian, three clocks, sprint | [Library](../capsule/library.md) |
| Generalist | [Generalist](../capsule/generalist.md) |
| Observation, quality, fingerprint | [Observability and quality](../capsule/observability.md) |
| Port, port type | [Port type vocabulary](../schemas/port-types.md) |
| Check, test case, test suite, sealed suite | [Checks](../schemas/checks.md) |
| Candidate, Verdict, Standing, Binding, Observation, Artifact, Verification, Finding | the [records table](../schemas/schemas.md#the-records) and each record's page |
| Policy, epoch, registry, reason code | [Policy](../schemas/policy.md) |
| Invariants (INV-n), type grammar, hash, `schema_version`, page status (`draft`/`proposed`/`v1`/`v1.x`) | [Invariants](../schemas/invariants.md) |

## openJiuwen pieces named in these pages

Defined nowhere else in this folder.

| Term | What it is |
|---|---|
| **openJiuwen, agent-core** | the open-source agent framework; agent-core is its runtime library |
| **jiuwenswarm** | the multi-agent application built on agent-core |
| **Swarmflow** | agent-core's workflow engine; a workflow is a Python script calling `agent()` |
| **Symphony** | agent-core's capability index, retrieval and planner |
| **jiuwenbox** | a Linux sandbox service for running tools and code in isolation |
| **Agentic Hub** | openJiuwen's self-hosted skill store (the `skillhub` repository) |
