# AI4Research architecture

Updated October 13, 2026. These packages are the shared architecture for `ai4r_muk` and `ai4r_main_branch`.

| Package | Use |
|---|---|
| [design-package](design-package/README.md) | Full M1 architecture, responsibilities, rationale and implementation-facing reference |
| [design-package-compact](design-package-compact/README.md) | The same M1 scope, shared contracts and source decisions with less explanatory prose |

Start with the package README, then its system architecture and principles. The full package owns architectural changes; synchronize shared contracts, examples and decisions into compact. The PRD is supplied separately and owns product requirements. Its receipt and clause mappings are retained inside each package.

## Component reading

The [Intention Compiler entrypoint](design-package/builds/intention-compiler/README.md) and [Context](design-package/builds/intention-compiler/context.md) define the complete compiler through an accepted Research Brief or attributable halt, including required foundations. Accepted Intent IR is an intermediate result. Design scope does not establish implementation completion; use the live coding records and exact runtime evidence for that status.

[Design method](design-package/design-method.md) explains design depth, review and change impact. [Decision review](design-package/decision-review.md) records alternatives and authorized source exceptions. Detailed fields, schemas and examples belong to each package's reference layer.

## Experiments and evidence

The [experiment registry](experiments/README.md) identifies dated inputs, protocols, delivery receipts and prepared benchmark designs. Use the [routing-integration delivery receipt](experiments/design-package-routing-integration-2026-10-13/README.md) for the latest maintained pair. Frozen comparisons retain their recorded versions; later edits to the maintained packages do not update those inputs. Documentation checks establish package consistency, not agent quality or runtime acceptance.

Local notes are outside the shared review package. Promote material decisions into the maintained design. Optional provenance remains in [pinned history](design-package/history.md).

## Model-routing owner integration

The [routing overview](design-package/model-routing.md) connects the separate router design and catalog to one [shared Capsule–routing contract](design-package/reference/capsule-model-routing.md). Architecture owns binding, permissions and dispatch; the model-routing owner owns selection, provider integration and routing evidence. Phase 1 remains fixed Codex; APIs belong to Phase 3. The current product receipt identifies confirmed PRD (4).
