# AI4Research architecture

Updated October 15, 2026. The maintained design package is the shared architecture for `ai4r_muk` and `ai4r_main_branch`.

| Package | Use |
|---|---|
| [design-package](design-package/README.md) | Full M1 architecture, responsibilities, rationale and implementation-facing reference |

Start with the package README, then its system architecture and principles. The compact package was retired on October 14, 2026 (decision D27); the maintained design package is the sole current architecture. The PRD is supplied separately and owns product requirements. Its current receipt and clause mappings are in the maintained package.

## Component reading

The [Intention Compiler component](design-package/pipeline/intention-compiler.md) defines the preparation boundary through an accepted Research Brief or attributable halt. Accepted Intent IR is an intermediate result. The current [core build scope](design-package/3-build-plan.md) extends through the bounded Planner, protected freeze and governed research journey. Design scope does not establish implementation completion; use the live coding records and exact runtime evidence for that status.

[Design method](design-package/method/design-method.md) explains design depth, review and change impact. [Decision review](design-package/method/decisions.md) records alternatives and authorized source exceptions. Detailed fields, schemas and examples belong to each package's reference layer.

## Experiments and evidence

The [experiment registry](experiments/README.md) identifies dated inputs, protocols, delivery receipts and prepared benchmark designs. The [routing-integration delivery receipt](experiments/design-package-routing-integration-2026-10-13/README.md) records the October 13 integration snapshot. Frozen comparisons retain their recorded versions; later edits to the maintained package do not update those inputs. Documentation checks establish package consistency, not agent quality or runtime acceptance.

Local notes are outside the shared review package. Promote material decisions into the maintained design. Historical source evidence stays outside the delivery package and is not routine build input.

## Model-routing owner integration

The [routing overview](design-package/side-systems/model-routing.md) connects the separate router design and catalog to one [shared Capsule–routing contract](design-package/reference/model-routing-contract.md). Architecture owns binding, permissions and dispatch; the model-routing owner owns selection, provider integration and routing evidence. Phase 1 remains fixed Codex; APIs belong to Phase 3. The canonical [product receipt](../product/README.md) identifies PRD V10.
