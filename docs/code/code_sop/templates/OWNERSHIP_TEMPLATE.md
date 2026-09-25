# Team and Module Ownership

> Usage: copy to `docs/governance/OWNERSHIP.md`; Code Team Lead maintains it. Update at adoption and when personnel, module boundaries, or review authority change. Names/identities, code scope, primary and backup owners, and review relationships are required. Keep unknown assignments as Pending confirmation; do not infer module ownership from branch names. Explain the reason and impact if there is no backup or interface.

- Document version / update date: [Fill in].
- Code Team Lead / maintainer: [Actual name and team identity].
- Applicable code and architecture versions: [Commit SHA and architecture document version].
- Human confirmation record: [Person, time, and evidence; initially Pending confirmation].

## 1. People and persistent branches (required)

The team integration branch is `huawei_waterloo_main_branch`. Retain the following four personal branches. They do not imply a one-to-one assignment of people to the four modules. Record remote branch status from actual Git queries; this ownership table does not establish real-time status.

| Branch label | Persistent working branch | Confirmed name / GitHub identity | Modules and roles | Backup / effective period |
| --- | --- | --- | --- | --- |
| Xiaoyang | `huawei_waterloo_xiaoyang` | [Pending confirmation] | [Pending confirmation] | [Fill in] |
| Saurav | `huawei_waterloo_saurav` | [Pending confirmation] | [Pending confirmation] | [Fill in] |
| Ramika | `huawei_waterloo_ramika` | [Pending confirmation] | [Pending confirmation] | [Fill in] |
| Muk | `huawei_waterloo_muk` | [Pending confirmation] | [Pending confirmation] | [Fill in] |

## 2. Module boundaries and ownership (required)

Verify actual code paths in the repository. A module name does not establish that a directory with that name exists. Split rows into smaller scopes if needed, but do not leave critical interfaces without owners.

| Module | Actual code / test / local AGENTS paths | Owned behavior and boundaries | Primary owner | Backup | Human reviewer |
| --- | --- | --- | --- | --- | --- |
| RSI | [Pending verification] | [Fill in] | [Pending confirmation] | [Fill in] | [Fill in] |
| Router | [Pending verification] | [Fill in] | [Pending confirmation] | [Fill in] | [Fill in] |
| Capsule | [Pending verification] | [Fill in] | [Pending confirmation] | [Fill in] | [Fill in] |
| Verifier | [Pending verification] | [Fill in] | [Pending confirmation] | [Fill in] | [Fill in] |
| Shared code / tools / CI | [Actual scope] | [Fill in] | [Pending confirmation] | [Fill in] | [Fill in] |

## 3. Interfaces and cross-module decisions (required when applicable)

| Interface / shared resource | Provider owner | Consumer owner | Contract and version | Joint test owner | Change confirmation record |
| --- | --- | --- | --- | --- | --- |
| [Fill in] | [Fill in] | [Fill in] | [Actual path under `docs/contracts/`] | [Fill in] | [Pending confirmation / actual evidence] |

## 4. Review, approval, and execution boundaries (required)

| Activity | Execution responsibility | Required human decision | Assigned people and authority evidence |
| --- | --- | --- | --- |
| Design and implementation scope | Author drafts; relevant owners confirm impact | Code Lead approves design and issues `write_code.md` | [Fill in] |
| Implementation and file understanding | Task author | Author explains and takes responsibility for every changed file | [Per-task record] |
| AI review | AI reviewer reports findings and limits | AI is not an approver | [Tool / workflow entry] |
| Final function-level review | Code Lead or authorized delegate | Human decision for a specific implementation and baseline | [Fill in] |
| Merge execution | Designated executor | Confirm current approval and verification are valid | [Fill in] |
| Release / incident response | Designated executor | Explicit authority for the actual task and environment | [Fill in] |

When Code Lead is the author, designate an independent human reviewer with an overall understanding of the code and record the scope and duration of that authority. The author cannot substitute for independent review. Keep the task pending if no suitable reviewer is available. A backup assumes explicitly defined responsibilities during an absence. Code Lead resolves cross-module disputes; AI does not change contracts on its own.

## 5. Updates and handoff (required)

- Current change and reason: [Fill in].
- Effective scope and date: [Fill in].
- Unassigned responsibilities and resolution plan: [Item, impact, owner, and deadline].
- Handoff evidence: [Tasks, document access, and receipt confirmation; explain N/A].
- Repository permissions or CODEOWNERS changes needed: [Pending decision / actual status; this document does not establish that permissions are configured].

Use [HANDOFF_TEMPLATE.md](HANDOFF_TEMPLATE.md) for handoff. Update this table when temporary authority ends; retain approval records in historical tasks.
