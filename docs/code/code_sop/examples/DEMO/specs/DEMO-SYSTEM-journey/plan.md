# Implementation Plan: DEMO-SYSTEM
**TASK**: [DEMO-SYSTEM](../../DEMO-SYSTEM/TASK.md) | **Spec**: [r1](spec.md)
**Revision / date**: r1 / 2026-09-29 | **Branch**: NOT_STARTED
**Input sources**: DEMO SOURCE-03 and architecture r1

## Summary
Wire an actual consumer to the provider, establish a candidate and verify complete request-to-display behavior.

## Technical Context
Runtime and executable paths are PENDING_DESIGN. All connections are local real implementations; no stub can establish final system acceptance.

## Constitution Check
Owns only system ACs. References provider agreement/evidence and maintains its own native work matrix. No separate review or closure card.

## Project Structure
Consumer entry point, display and system checks are hypothetical and not created. Bind paths before T001 execution.

## Blocks and Dependencies
| Block ID | Responsibility / AC references | Inputs, outputs, state invariants | Dependency block/TASK/IF references | Affected implementation paths |
| --- | --- | --- | --- | --- |
| B01 | Consumer/display / AC-001, AC-002 | Request -> visible result; no stale success | DEMO-001/B01,B02 and IF-001@r1 | PENDING_DESIGN consumer |
| B02 | Complete journey verification / AC-001, AC-002 | Exact candidate and request -> observed journey evidence | B01, provider block evidence and DEMO-001/V03 | PENDING_DESIGN system checks |

## Interfaces and Technical Decisions
Consume [IF-001@r1](../../DEMO-001/TASK.md#4-embedded-cross-module-agreements). Display state is reset on errors. No independent copy of the interface schema.

## Verification Design
| V ID | Level | Block / IF / AC references | Fixture and dependency mode | Expected assertion / criterion source | Command + working directory or manual procedure | Required prerequisites / artifacts |
| --- | --- | --- | --- | --- | --- | --- |
| V01 | SYSTEM | B01,B02 / AC-001 / DEMO-001 blocks / IF-001 | "  ALPHA  "; all local real components | Display exactly "alpha" per AC-001 | Launch candidate entry; submit fixture; capture request, provider result and display | Candidate hashes, valid block/boundary evidence, trace |
| V02 | SYSTEM | B01,B02 / AC-002 / IF-001 | Same session after V01, then " " | Display INVALID_LABEL with no stale "alpha" per AC-002 | Submit invalid fixture and capture error plus resulting display state | Same candidate and session; trace |

## System Candidate and Journeys
The run record must contain actual provider, consumer, check and configuration hashes, runtime and starting state. Candidate is currently NOT_BUILT. Final runs require DEMO-001/V01,V02,V03 valid for that candidate. Earlier exploratory runs cannot establish final completion.

## Unresolved Decisions and Impact
No actual runtime/paths exist. Provider, consumer or interface changes require impact assessment and affected system re-execution.
