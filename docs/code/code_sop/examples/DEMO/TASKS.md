# TASKS: DEMO
Illustrative only. No runtime execution has occurred.

## 1. Identity and source baselines
| Field | Value |
| --- | --- |
| Program ID and objective | DEMO: normalize an executor label and show it to a consumer |
| Register revision/date | r1 / 2026-09-29 |
| Program coordinator | Unassigned example |
| Full PRD path / revision / SHA256 / bytes | The three inline SOURCE clauses below, r1; hash/bytes N/A for an inline fictional source |
| Architecture source and rendered views / revision / SHA256 | Inline r1: request -> validate -> normalize -> consumer display; hash N/A |
| Scope inclusions and exclusions | Three SOURCE clauses; external services, storage, model routing and performance claims excluded |
| System-verification TASK | [DEMO-SYSTEM](DEMO-SYSTEM/TASK.md) |
| Integrated candidate | NOT_BUILT |

Fictional source:
- SOURCE-01: a label is a string containing at least one non-whitespace character; other values produce INVALID_LABEL.
- SOURCE-02: return the label trimmed and lowercased.
- SOURCE-03: the full request displays the normalized label on success and INVALID_LABEL on invalid input, with no stale success value.

## 2. Task register and dependency graph
| TASK ID / entry link | Bounded outcome | Executor | Required for program? | Prerequisite TASK/block/IF IDs | Native feature directory | Progress/evidence source |
| --- | --- | --- | --- | --- | --- | --- |
| [DEMO-001](DEMO-001/TASK.md) | Validate and normalize labels | Unassigned example | Yes | None for block work; consumer needed for boundary V03 | specs/DEMO-001-label/ within this example | [tasks](specs/DEMO-001-label/tasks.md) |
| [DEMO-SYSTEM](DEMO-SYSTEM/TASK.md) | Consumer wiring and system verification | Unassigned example | Yes | DEMO-001 blocks and IF-001@r1 | specs/DEMO-SYSTEM-journey/ within this example | [tasks](specs/DEMO-SYSTEM-journey/tasks.md) |

Order: define IF -> provider blocks -> consumer wiring -> boundary check -> final system check. The provider boundary check depends on consumer wiring, not on the system TASK being fully complete; this avoids a circular completion dependency.

## 3. Source coverage allocation
| Source clause ID / exact locator | Architecture node/edge IDs | Owning TASK / AC references | Allocation decision and completeness |
| --- | --- | --- | --- |
| SOURCE-01 | Validate | DEMO-001/AC-001 | Allocated: validity and error result |
| SOURCE-02 | Normalize | DEMO-001/AC-002 | Allocated: output transformation |
| SOURCE-03 | Provider -> consumer display | DEMO-SYSTEM/AC-001, AC-002 | Allocated: success and invalid-input journeys |

## 4. Interface index
| IF ID / revision | Canonical owning TASK section | Provider TASK | Consumer TASKs | Boundary verification location |
| --- | --- | --- | --- | --- |
| IF-001@r1 | [Owning TASK](DEMO-001/TASK.md#4-embedded-cross-module-agreements) | DEMO-001 | DEMO-SYSTEM | DEMO-001/V03 |

## 5. System verification entry
- Native spec/plan/tasks: [System TASK registry](DEMO-SYSTEM/TASK.md#2-spec-kit-registry).
- Complete journeys: DEMO-SYSTEM/AC-001 and AC-002.
- Candidate manifest: NOT_BUILT; eventual run records provider and consumer source hashes.
- Final run evidence: NOT_RUN.
- Required child evidence: DEMO-001/V01, V02 and V03 valid for that candidate.
- Program conclusion: NOT_READY.
- Unverified scope: all runtime behavior.

## 6. Source changes and unresolved inputs
| Change/question ID | Source or IF revision / question | Affected TASK/AC/block/check IDs | Action and evidence invalidation | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| EXAMPLE-01 | No implementation exists | All | Keep checks NOT_RUN; bind actual paths if instantiated | Unassigned; only if this toy example is explicitly selected for implementation |
