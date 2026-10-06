# Architecture inputs and coding authorities

Start at [the overview](README.md), then [TRIAL-1](immediate-plan.md), [contract shapes](contracts-and-native-reuse.md), [guard design](guard-design.md), [stage exits](delivery-phases.md) and [failure routing](failure-and-human.md). This folder contains current architecture, its CC contract references, and the latest PRD. Existing coding-process and task records are linked in their repository locations.

| Information | Read |
|---|---|
| Product behavior and amendments | [Latest PRD](sources/product/prd-m1-current-2026-10-06.txt), [source index](sources/product/README.md), [decisions](principles.md#decisions-and-source-amendments) |
| Design-to-owner mapping | [Clause allocation](coverage-allocation.md), [phase/stage exits](delivery-phases.md) |
| Future coding registration | Existing [M1 register](../../code/Missions/M1/TASKS.md); register a distinct TRIAL-1 TASK before native generation, using [the trial design](immediate-plan.md) |
| Existing task, AC and IF ownership | [M1 register](../../code/Missions/M1/TASKS.md); preserve existing IDs and reconcile affected native artifacts before implementation |
| Coding process | [Code SOP](../../code/Code_SOP.md), [Spec Kit workflow](../../code/SPEC_KIT_WORKFLOW.md), [verification](../../code/VERIFICATION.md) |
| Constitution | [Live constitution](../../../.specify/memory/constitution.md) |
| CC contract | [Declaration inventory](capsule/declaration.md), [machine schema](sources/capsule.schema.json), [semantic description](sources/capsule-semantic-v2.10b.md), [M1 policy source](sources/policy-m1.json) |
| Reuse evidence | [Native interface observations](contracts-and-native-reuse.md), [pinned source evidence](sources/native-reuse-evidence.json); source inspection does not prove runtime compatibility |

Architecture owns workflow responsibilities, approximate inputs/outputs, authority, trust boundaries and failure outcomes. Spec Kit owns exact serialization, APIs, algorithms, prompts, limits, measured thresholds and implementation evidence. Required reading depends on the assigned responsibility; historical task descriptions do not override the current PRD and explicit amendments.

```mermaid
flowchart LR
    Product[Current PRD and recorded amendments] --> Design[Architecture and semantic handoffs]
    Design --> Live[Live TASKS and owning TASK or IF]
    Live --> Native[Native spec, plan, tasks and evidence]
```

Use this reading set inside the repository; existing live authorities are intentionally not copied into this folder. Optional external bibliography is reference material, not an extra required offline input. Documentation checks do not establish runtime or scientific acceptance.
