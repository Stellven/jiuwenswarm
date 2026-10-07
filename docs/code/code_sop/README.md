# Complete documentation catalog - SOP v2
The package entry guide is in Chinese; all other active v2 documents are in English. Start with [Code SOP](../Code_SOP.md). This catalog is the complete process package; optional generated research/schema files are not additional mandatory cards.

## Reading order
1. [Package entry](../README.md)
2. [Code SOP](../Code_SOP.md)
3. [Spec Kit workflow](SPEC_KIT_WORKFLOW.md)
4. [Block-to-system verification](VERIFICATION.md)
5. [Worked example](WORKED_EXAMPLE.md)
6. [Future M1 register](../../tasks/M1/TASKS.md)

## Guides and instructions
| Document | Purpose |
| --- | --- |
| [Git workflow](GIT_WORKFLOW.md) | Branch/candidate handling without automatic commits |
| [Migration and preparation](MIGRATION.md) | Replacement map and treatment of unfinished historical work |
| [Root AGENTS template](../AGENTS_global.md) | Reusable durable repository instructions |
| [Local AGENTS template](../AGENTS_local.md) | Reusable subtree context |
| [Active repository AGENTS](../../../AGENTS.md) | Deployed v2 repository entry and rules |
| [Active constitution](../../../.specify/memory/constitution.md) | Spec Kit's v2 principles |
| [RSI guide](modules/RSI_AGENTS.md) | Research-workflow boundary questions |
| [Router guide](modules/Router_AGENTS.md) | Executor-only routing and PRD-derived model list |
| [Capsule guide](modules/Capsule_AGENTS.md) | Product capsule scope and state |
| [Verifier guide](modules/Verifier_AGENTS.md) | Product verification behavior |

## Required record templates
| Template | Destination / authority |
| --- | --- |
| [TASKS](templates/TASKS_TEMPLATE.md) | docs/tasks/PROGRAM-ID/TASKS.md; whole-program source/coverage/dependencies |
| [TASK](templates/TASK_TEMPLATE.md) | docs/tasks/PROGRAM-ID/TASK-ID/TASK.md; identity and embedded agreements |
| [Evidence](templates/EVIDENCE_TEMPLATE.md) | Selected feature evidence/RUN-ID.md; actual run observations |

These are the only record templates in the active package. Evidence is an output attachment, not an extra task card.

## Native Spec Kit templates
| Native template | Destination / authority |
| --- | --- |
| [Spec override](../../../.specify/templates/overrides/spec-template.md) | Feature spec.md; requirements and ACs |
| [Plan override](../../../.specify/templates/overrides/plan-template.md) | Feature plan.md; design, blocks and checks |
| [Tasks override](../../../.specify/templates/overrides/tasks-template.md) | Feature tasks.md; work and AC-to-evidence matrix |

Overrides are canonical. Do not maintain duplicate copies under this catalog's templates directory.

## Complete fictional example
| Document | Link |
| --- | --- |
| Program register and inline source | [DEMO TASKS](examples/DEMO/TASKS.md) |
| Provider TASK | [DEMO-001](examples/DEMO/DEMO-001/TASK.md) |
| Provider native artifacts | [spec](examples/DEMO/specs/DEMO-001-label/spec.md), [plan](examples/DEMO/specs/DEMO-001-label/plan.md), [tasks](examples/DEMO/specs/DEMO-001-label/tasks.md) |
| System TASK | [DEMO-SYSTEM](examples/DEMO/DEMO-SYSTEM/TASK.md) |
| System native artifacts | [spec](examples/DEMO/specs/DEMO-SYSTEM-journey/spec.md), [plan](examples/DEMO/specs/DEMO-SYSTEM-journey/plan.md), [tasks](examples/DEMO/specs/DEMO-SYSTEM-journey/tasks.md) |

No example runtime result is reported as passed. Actual future runs use the evidence template.

## Source delivery and historical snapshots

Use the live guides, templates and repository authorities above. The obsolete combined handbook, ZIP and manifest have been removed; their exact original versions are retained through the [pinned history index](../../architecture/build-package/history.md#final-branch-cleanup--october-7-2026). [Documentation checks](../DOCUMENTATION_CHECKS.md) record the earlier delivery, not current M1 readiness.
