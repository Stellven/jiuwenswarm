# Alignment with the software-factory and CC intent

Reviewed local factory commit `e6099f4210442ef81ec9a54c4d7f11acbe98896e` against freshly fetched `Muxite/tools` commit `b74121c712ee5378b70ad54c4997cd81563685e7`. Two gpt-6.1-sol reviewers independently inspected package/protocol and factory/lab responsibilities; the primary agent checked the cited code and repeated the schema comparison. This is a source review and structural probe, not a new GPU campaign or live-agent result.

## Source authority and what we are building

The current [Muxite reading route](https://github.com/Muxite/tools/blob/b74121c712ee5378b70ad54c4997cd81563685e7/DGX-SPARK/README.md) is useful, but its new DGX-SPARK material includes our own source/evidence snapshot. Its agreement with our reports is not independent confirmation. The earlier [CC protocol](https://github.com/Muxite/tools/blob/b74121c712ee5378b70ad54c4997cd81563685e7/AI4Research-Notebook/Designs/CC%20Protocols/README.md), original workshop directions and Nov12 RSI assignment supply additional intent. Historical compiler chains, hardware assignments, Incus proposals and expired run budgets do not supersede this session or the authorized [revisable-loop decision](DESIGN-CHANGE-2026-11-12.md).

The software factory turns a product objective, model/hardware facts and constraints into a runnable engine and evidence about it. CCs supply reusable capabilities for doing that work: tools, integration components, methods, skills and checks. A component may enter the engine; a profiling tool or build skill may help produce it without shipping in it. The engine, its contract and the CC library are different things. Several CCs may support a task node; a cohesive CC may contain several kinds of material and action. Neither one CC per node nor a mandatory invocation chain follows from the design.

The same agent/workflow infrastructure should also be able to produce a new CC when an investigation exposes a capability gap. RSI then improves a versioned CC at its job against comparable cases. Neither a larger library nor a faster manually tuned engine alone demonstrates that capability-production loop.

This largely matches our direction. The important divergences are interchange, identity and the breadth of executable work, rather than a need to replace JiuwenSwarm or restore M1.

## Concrete findings and proposed changes

| Priority | Source-confirmed finding | Change and acceptance condition |
|---|---|---|
| P0: CC interchange | All 40 top-level plus eight nested factory declarations fail the current upstream schema because of local `kind` fields. The protocol-change document incorrectly said schemas were unchanged. | Documentation corrected in this review. Preserve role information, but define canonical export/import or explicitly agree an upstream extension. Prove a representative mixed tool/component/skill CC can be prepared and used by both runners. Never mutate old sealed releases. |
| P0: consumed implementation identity | Several CCs seal wrappers/materials while invoking the installed factory backend. Some component consumers resolve current source materials instead of the selected release's material. | Declare the factory runtime dependency, bind its actual build/tree identity, and resolve selected component artifacts by digest. Test that changing host source cannot silently change a release-bound integration. Keep existing request snapshots and image pins. |
| P1: bounded exploration versus construction | The connected factory loop selects exact admitted templates; selection cannot create a new source/image/configuration. Source/build capabilities exist elsewhere, so construction is not absent, but it is not yet integrated into this connected search path. | Complete the connected recovery acceptance case, then add one bounded candidate-build route through existing Jobs/Builder/Manager. The agent may choose implementation changes within preauthorized roots/resources; it may not change the comparison's fundamental requirements or judge. |
| P1: economical completion | The live CPU investigation published a report but timed out. Generic followup proposes 24 turns, four hours, two builds and six GPU cells regardless of that task's small CPU-only budget. | Make suggested next work state its budget basis and distinguish current permitted work from a future request. Exercise the existing terminal-decision/turn-return handshake. A report observation alone must not be treated as successful completion. Compare matched old/new task cost and conclusion quality. |
| P1: capability production | Method-transfer and hypothesis tools support supplied evidence and proposals; our new CC implementations were authored by coding agents in this development session. That is not an established JiuwenSwarm paper/repository-to-tested-CC loop. | Use one discovered gap to produce a candidate package with provenance, applicability, implementation, integration guidance and independent checks, then import and use it on a second case. Reuse the factory; do not build a separate registry/orchestrator stack. |
| P2: causal profiling and portability | Common-history logits now exist, but expert demand/readiness timelines, observer overhead, clean-root restoration and endurance remain unqualified. | Choose the cheapest mechanism-specific diagnostic, verify its coverage and overhead, then integrate one supported intervention. Restore under a fresh root before expanding to sustained unattended campaigns. |

### 1. The local role taxonomy is useful, but it is a protocol extension

Current upstream FORMAT permits material `path`, `description` and `media_type`; its closed schema has no capability/material `kind` property. Our schema adds it and `ccv2.py` validates it. Local history attributes the addition to `608656eb1` on Nov12. This is an existing deliberate branch extension, not something introduced by the latest numerical CC.

The [audit receipt](context-review-20261116/schema-compatibility.json) pins both source commits, the upstream schema and every checked declaration. Results: 0/48 valid unchanged; 48/48 valid after removing only the local role fields **in memory**. No runtime invocation, semantic guarantee or portable dependency claim follows from this probe. No actual package was rewritten.

The correction is to separate role description from interchange compatibility. A compatible export could preserve role descriptions in passive material/catalog metadata; alternatively, the extension could be adopted explicitly by the protocol owner. This choice needs a small conformance fixture before migrating the whole library. The factory's current `components.load` requires `materials.component.kind`, so deleting fields is not a complete migration. New declarations also change release identity and qualification references.

### 2. A package and its runtime dependency need distinct identities

Representative execution path: `ccs/expert_streaming/run.py` imports `job_packages`; `job_packages.main` starts the installed `jiuwenswarm.factory.api`. `controller.configure_agent` supplies the current source root in `PYTHONPATH`. Core receipts record the interpreter hash and installed package names/versions, while `job_packages.telemetry_identity` names the sealed wrapper release. These facts do not uniquely identify changed editable backend source.

A concrete material path compounds this: `components.py:ROOT/load` resolves `component.yaml` from the host factory tree. `ab.submit` consumes those engagement rules, even though an expert-streaming release also contains component materials. The request snapshots and hashes the material it actually loaded, which preserves the submitted experiment. The missing link is proof that those bytes correspond to the component release the agent selected.

This is not a demand to copy the entire factory into every CC. Upstream allows external runtimes. An immutable runtime image/build identity plus selected material digests is suitable. Current pinned-image experiments and frozen campaign runtime manifests already provide stronger whole-run provenance; this finding does not invalidate them or imply that all standalone numerical tools have this dependency. It concerns the general mutable-checkout invocation path and accurate reusable-package claims.

### 3. Keep product requirements fixed while allowing implementation search

`FactoryLoop.select` validates an exact template hash and a list of allowed hypotheses, then rejects arbitrary treatment/source/image parameters. This is an appropriate bounded experiment interface. It becomes a limitation if every useful newly discovered implementation requires an operator to construct another whole campaign manually.

The next integration should let an admitted task choose source edits, components and build iterations within its existing authority. A candidate record should reference its parent source, actual patch/tree, component/material identities, build recipe/image and the unchanged evaluation obligations. The existing Builder, Jobs, Manager, Store and taskgraph remain the owners. Schema validation or request construction must not become a new host planner choosing the intervention.

`methodology.ONTOLOGY` is currently a useful set of analysis categories and signal names. It is not a complete, owner-approved inference-system ontology or realization space. Start with explicit, versioned domain references linking model/hardware constraints, layers/modules, interventions, evidence obligations and applicable CCs. Accept the owning ontology's definition rather than silently standardizing our Python dictionary as the project's ontology. Original compiler diagrams explain a need for structured requirements; they do not require restoring the removed compiler pipeline.

### 4. Give RSI a job with measurable improvement

The independent [Nov12 RSI assignment](https://github.com/Muxite/tools/blob/b74121c712ee5378b70ad54c4997cd81563685e7/DGX-SPARK/planning/satay-assignments/20261112%20RSI%20Expert%20Streaming%20Factory%20Starter%20prepresentation/20261112%20RSI%20Agent%20Assignment%20prepresentation.md) distinguishes improving the reusable capability from merely adding a report/verifier or fixing the scheduler. It asks for comparable inputs, unchanged criteria and actual evidence that an agent's task improves.

Good immediate cases are budget-aware followup, applicability/engagement diagnosis and efficient evidence intake. Baseline and candidate should receive the same task/evidence, with a separate case for generalization. Measure correct/incorrect next decisions, invalid trials avoided, useful outputs, wall time, native calls/errors and cached/uncached usage. Keep host lifecycle fixes in a separate result category. Improved tool replay is not yet improved agent decisions; improved agent decisions are not yet engine speed.

For the latest timeout, `scripts/factory_branch_mission.py` wraps `Controller.run` in a deadline. The controller checks terminal decisions between awaited agent turns. This identifies a completion boundary to test; it does not establish that the timeout's sole cause was controller polling. The agent's published final report was an observation, and should not be silently promoted into a terminal decision. Exercise explicit completion with no active work and preserve partial evidence on genuine timeout.

## Revised work order

1. **Correct compatibility claims now.** Done here: protocol/provenance documentation, source-pinned schema audit and this plan addendum. Historical handoffs remain unchanged.
2. **Make one package transfer and one component consumption trustworthy.** Canonical/local-role interoperability plus explicit backend/material identity. Acceptance is cross-runner use and rejection or explicit requalification after dependency drift, not just schema success.
3. **Finish one connected investigation under current execution boundaries.** Real agent chooses an experiment, yields for quiet lab work, recovers from lost acknowledgement without duplicate submission and records a supported next action. No forced fork count or positive speed requirement.
4. **Close the construction loop with one source-changing case.** Use a bounded editable candidate, existing builder and frozen judge; prove the new component was actually used. Distinguish factory tool improvement from engine-product improvement.
5. **Exercise one capability-production/RSI task on comparable cases.** Produce or revise a cohesive CC and use it beyond its authoring example. Package integration skill and independent checks with tools/components; do not add a wrapper solely to increase catalog size.
6. **Broaden after mechanism and recovery evidence.** Targeted profiling, independent quality/speed confirmation, fresh-root restoration and bounded endurance remain necessary for weeks-long operation.

The earlier review and connected-development notes retain their dated evidence. This addendum changes priority and clarifies remaining gaps; it neither retracts the measured prefill result nor claims a new result. No runtime/schema migration, image rebuild, GPU run or remote push was performed for this review.
