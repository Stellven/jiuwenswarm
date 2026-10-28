# Native reuse and contract adapters

**Reading level: AI reference; optional reuse evidence.** [Critical schemas/major fields](reference/README.md) own shared contracts. Framework models are adapter inputs, not competing schemas. Existing Pydantic/dataclass choices do not prescribe private implementation structure.

## What Symphony already offers

Optional implementation reference: the source paths below help the coding agent investigate reuse; they are not required architecture reading or a prescribed module layout.

These observations come from local source inspection, not an AI4Research acceptance run. Paths beginning `jiuwenswarm/` below are relative to this repository; `../openjiuwen/agent-core/` identifies the sibling upstream checkout. Code paths are evidence locations, not document links.

| Existing seam and source evidence | Reuse proposal | Remaining AI4Research responsibility |
|---|---|---|
| `CapabilityIO`, `CapabilityDescriptor`, `SourceSnapshot` in `../openjiuwen/agent-core/openjiuwen/symphony/models/capability.py` | Project admitted declarations into a normalized read-only discovery catalogue | Full artifact schema references, effect/resource authority, admission standing and pinned runtime bindings |
| `CapabilityFingerprint` and `FingerprintArtifact` in upstream `symphony/models/fingerprint.py` | Reuse semantic description, version/hash metadata and reproducible catalogue snapshots for candidate matching | Treat extracted fingerprints as derived metadata; an LLM extraction cannot replace the authored declaration or grant permissions |
| `CapabilityProvider` and `AtomicCapabilityProvider` in upstream `symphony/interfaces/capability.py`; `ScanResultCapabilityProvider` and `FingerprintArtifactCapabilityProvider` in `jiuwenswarm/symphony/adapter.py` | Add an admitted-library provider through the existing provider seam; capture inventory and identity consistently | Filter eligible versions, preserve canonical identities and schema/check references, and prevent stale catalogue data from authorizing execution |
| `SkillFolderScanner`, `FingerprintService` and `SymphonyRuntime` imports in `jiuwenswarm/symphony/build.py` | Reuse existing catalogue build and graph-artifact infrastructure where compatible | Folder presence is not admission; static Delivery Phase 1 bindings must not depend on live semantic search |
| `OrchestrationService.plan` in upstream `symphony/orchestration/service.py`; `SymphonyGraphEngine` in upstream `symphony/graph_engine.py` | Evaluate bounded planning and graph lifecycle support for the dynamic path | Accepted Research Brief adapter, deterministic feasibility checks, node-contract assembly, freeze, gate-controlled dispatch and fallback |
| `SwarmSymphonyService` in `jiuwenswarm/symphony/service.py` and upstream `SymphonyRuntime` in `symphony/runtime.py` | Reuse existing application adapters and capture seams rather than inventing an independent Symphony integration | Prove run/attempt identity, evidence completeness, admission and gate semantics at the connected boundary |

`CapabilityIO.type` is a semantic string, with a description and optional required/default metadata. It is useful for retrieval and composition reasoning, but it is not a complete payload validator. A match between two such ports does not prove that the produced JSON satisfies the consumer's schema or meaning.

Upstream `SymphonyModel` in `symphony/models/_base.py` already uses Pydantic with frozen models and `extra="ignore"`. That compatibility policy is evidence of the framework's style, not permission to ignore unknown governance fields in AI4Research's authoritative contracts. Use adapters and explicit validation at that boundary.

The observed Symphony capability graph is a reusable catalogue/relationship graph; its planned graph is a planning artifact. Neither is automatically the frozen AI4Research execution graph or Node Execution Contract. Likewise, Symphony Flow packaging/review and graph evolution are not evidence that PRD capsule admission, human activation, protected evaluation or offline RSI controls are implemented. Any reuse must preserve those product responsibilities.

## Evidence limits

This repository pins OpenJiuwen agent-core revision `9e3390195a9ea15235b2b5f7412cb2aa440622cc` in both `pyproject.toml` dependency and UV source configuration. The inspected sibling checkout was clean at `e23806c1073275780dced2b71ddd592ffb0a21fd`. The initial review inspected that sibling HEAD. The closing review additionally inspected the actual pinned Git objects: [source hashes and interface observations](sources/native-reuse-evidence.json) establish the cited catalogue/provider/planning/model interfaces at the pin. This is source availability, not installed-runtime or connected gate compatibility.

The inspected shell's Python reported Pydantic `2.13.5`; resolving `openjiuwen` found the sibling namespace directory, not an installed agent-core package. No AI4Research/Symphony runtime compatibility test was performed, and no dependency pin was changed. Actual integration must first establish its actual environment, confirm the installed dependency matches the recorded pin, and then test the admitted-library adapter and one connected governed invocation before claiming native integration.

The accepted architecture responsibilities and unresolved source decisions belong in [workflow](workflow.md), [capsules](capsules.md), [placement](placement.md) and [principles](principles.md). [Critical schemas and major fields](reference/README.md) are architecture-owned; private APIs and executable implementation tests remain implementation work. Source §§1.3, 4.8 and 6.12 place dynamic integration in M1 Delivery Phase 3. The Leader's preliminary proposal checks remain separate from protected plan acceptance under D14.
