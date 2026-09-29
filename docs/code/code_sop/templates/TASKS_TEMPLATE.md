# TASKS: [PROGRAM-ID]
Copy to docs/tasks/[PROGRAM-ID]/TASKS.md. This is the program register, not a second implementation checklist.

## 1. Identity and source baselines
| Field | Value |
| --- | --- |
| Program ID and objective | [Fill] |
| Register revision/date | [Fill] |
| Program coordinator | [Name or UNASSIGNED; bookkeeping responsibility, not an approval gate] |
| Full PRD path / revision / SHA256 / bytes | [Fill or PENDING_SOURCE] |
| Architecture source and rendered views / revision / SHA256 | [Fill or PENDING_SOURCE] |
| Scope inclusions and exclusions | [Source references and reasons] |
| System-verification TASK | [Exact TASK link or PENDING_SOURCE] |
| Integrated candidate | [Commit plus dirty-tree identity if needed, or NOT_BUILT] |

## 2. Task register and dependency graph
| TASK ID / entry link | Bounded outcome | Executor | Required for program? | Prerequisite TASK/block/IF IDs | Native feature directory | Progress/evidence source |
| --- | --- | --- | --- | --- | --- | --- |
| [Fill] | [Fill] | [Fill] | [Yes/No with source basis] | [Fill or None] | [Exact path] | [Link to native tasks.md] |

Describe dependency order or add a diagram. Explain and resolve cycles. Progress is read from linked native records; do not duplicate their checkboxes or keep a second task status table.

## 3. Source coverage allocation
| Source clause ID / exact locator | Architecture node/edge IDs | Owning TASK / AC references | Allocation decision and completeness |
| --- | --- | --- | --- |
| [Fill] | [Fill or N/A with reason] | [One or more qualified AC IDs] | [Allocated / PENDING_SOURCE / Unallocated / Excluded with reason] |

Include functional, nonfunctional and system-wide clauses. If a clause spans several ACs, explain coverage of its parts. Each AC has exactly one owning spec. Every in-scope clause must be allocated before claiming program completeness.

## 4. Interface index
| IF ID / revision | Canonical owning TASK section | Provider TASK | Consumer TASKs | Boundary verification location |
| --- | --- | --- | --- | --- |
| [Fill] | [Exact link] | [Fill] | [Fill] | [Qualified V IDs / native evidence matrix] |

This is an index only. The owning TASK defines semantics. Do not repeat schemas here.

## 5. System verification entry
- System TASK and native spec/plan/tasks: [Links].
- Complete journeys and cross-cutting requirements: [References to system ACs, not copies].
- Candidate component/version manifest: [Location].
- Final system run evidence: [Link or NOT_RUN].
- Required child-task evidence for the candidate: [Native links and reuse basis where applicable].
- Program conclusion: [NOT_READY / VERIFYING / VERIFIED; derive from coverage and native evidence].
- Unverified scope and reason: [Fill or None].

VERIFIED requires full source allocation, all required task/block/boundary evidence valid for the candidate, and the system TASK passing on that candidate.

## 6. Source changes and unresolved inputs
| Change/question ID | Source or IF revision / question | Affected TASK/AC/block/check IDs | Action and evidence invalidation | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| [Fill] | [Fill] | [Fill] | [Fill] | [Fill] |

Record material scope decisions here with their source. Unknown future inputs are normal preparation states. Do not create a separate change-request card.
