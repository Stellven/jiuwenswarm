# 20261117 CC Workflow RSI Reconciliation prepresentation

The two downloads have different roles: capability-pool.schema.json defines the catalog shape, while pool.json is a 150-entry catalog instance. The existing runtime binding profile is the third piece being reconciled.

The smallest useful common contract connects components without replacing the native CCv2 runtime. Keep one execution authority, derive the shared catalog from selected releases, and adapt the authoring vocabulary at the boundary.

| Difference | Reconciled choice | Reason and current limit |
| --- | --- | --- |
| CC package versus executable operation | A CC is a collection of related capabilities and materials; each capability exports an operation. | A package is cohesive, while individual operations remain connectable and testable. |
| Subworkflow versus workflow | Both use the composite form; reusable procedures nest inside task-specific workflows. | Avoids a duplicate execution mechanism. Expanded leaves retain exact instance IDs. |
| Historical inventory versus live authority | Preserve the downloaded inventory as historical data; export the executable pool from selected sealed releases. | An old Python entrypoint is information, not admission to execute code. |
| Transport kind versus meaning | Preserve transport, value kind, semantic type and known JSON payload schemas separately. | A JSON value alone does not establish that it is an admitted build identity. Host ownership and provenance checks still apply. |
| Submission versus completed result | Separate outputs from collected result ports. | A submission acknowledgment cannot satisfy a dependency on completed work. |
| Reference spelling | Author with node; accept existing source at the boundary and reject conflicts. | Compatible with existing graphs without keeping two competing reference models. |
| Small transformations | JSON Pointer projection and bounded template insertion. | Covers build-to-benchmark assembly without an arbitrary expression language. |
| Unknown historical schemas | Mark unknown explicitly and retain original descriptors. | Do not invent precision for the 343 unknown historical port definitions. |
| Adaptation at several levels | Capability implementations can change under their contract; reusable procedures compose leaves; workflow revisions cite evidence. | Current scopes summarize leaves. Independent scope budgets and arbitrary replacement of running scopes are not implemented. |
| RSI and runtime | RSI chooses improvements from retained evidence; workflows execute them; the host admits effects and the evaluator decides eligibility. | Reasoning cannot substitute for independent measurement or grant new authority. |

The offline reconciliation retained all 150 historical entries and all 55 composition references through round trips. Duplicate identities, missing references, cycles and invalid embedded schemas were checked separately from structural JSON Schema validation. This verifies migration fidelity; it does not make those historical entries executable.

The live catalog currently exposes 17 selected CC capabilities and 19 workflow definitions through 61 normalized entries. Catalog contents depend on the selected task configuration. The common schema is version 0.2.0 and the existing executable binding profile is factory.interconnect/1. These versions describe different layers and are intentionally explicit.

## Comparison with AI-only wiring

An agent can propose the connection and select a procedure, but the host must validate the exact values crossing it. Relying on prose alone would leave completion, ownership, payload shape, artifact identity and replay semantics implicit. The small contract gives the agent a reliable surface while letting the system reject an invalid connection before executing its consumer.

Avoid a broad universal type system for now. Add a schema field or transformation only when a real engineering procedure needs it, with compatibility tests and a versioned migration. Semantic labels aid discovery; they do not prove scientific validity. The first useful extension is driven by the actual collected build-to-screen and unchanged-candidate confirmation edges.

## Review decisions

1. Retain the evolved M1 foundation and the removed POC paths as removed.
2. Treat CCs as functional packages and reusable subworkflows as engineering procedures.
3. Keep the compact interconnect and a single admitted execution host.
4. Require exact provenance, collected completion and evidence-backed revisions.
5. Separate a completed engineering run from a qualified performance improvement.
6. Introduce a representative quality gate before evaluating a changed-quantization candidate. Exact token equivalence on three unchanged-quantization prompts does not establish that gate.

## Observed implementation limits

The generated one-capability workflow wrappers currently expose required inputs only. Optional capability controls remain visible in the CC catalog but need an explicitly authored procedure to be used through a wrapper. The live source inspection attempted optional pagination through the default wrapper and was rejected without changing its graph revision. Add optional composite-input semantics when that procedure is needed; do not silently make optional capability ports required or mutate a running task definition to accommodate them.

This run also exposed two general integration faults that were repaired: saved report artifacts were absent from historical search, and an old terminal decision cancelled a legitimately resumed agent turn. History now indexes bounded, digest-verified text artifacts; the resumed-turn watcher considers only decisions newer than its starting revision. Regression tests cover both paths. These repairs preserve the original terminal records, counters and deadline.

The methodology helper now recognizes recorded native throughput gates without claiming a fresh raw-evidence verification. A target miss remains a target miss; it no longer automatically becomes missing repeatability. Native process limits are kept separate from the older completed-cell budget unit. Proposal outputs remain non-executable and grant no effects.

A sealed CC release identifies its bundle; a wrapper delegating into the host API also depends on that host implementation. The package therefore records the platform base, final working-tree file hashes, Python/runtime provenance and measurement-worker hashes separately. The scored worker request pins its critical implementation bytes. Pinning a host build identity on every delegated dispatch would improve complete call-level provenance; the current shared release identifier alone should not be presented as freezing the entire environment.
