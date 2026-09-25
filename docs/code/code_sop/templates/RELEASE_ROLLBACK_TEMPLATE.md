# Release and Rollback Record: [VERSION]

> Usage: copy to `docs/releases/<VERSION>.md`. Use only when the task involves a release, deployment, runtime environment change, or a documented recovery plan. Ordinary merges may describe rollback in the PR without a separate release record. Preparing this SOP or filling in the template does not execute or authorize a release, remote push, or rollback. Confirm existing explicit authority before operational actions; otherwise keep the status Planned. Versions, scope, environment, authority, acceptance thresholds, actual execution evidence, and recovery boundaries are required. Explain N/A for inapplicable items.

## 1. Release target and authority (required)

- Release version / release owner / Code Lead: [Fill in].
- Related tasks and PRs: [Fill in].
- Target environment / affected parties / operating window and time zone: [Fill in].
- Currently running version: [Code commit, artifact version/checksum, configuration, and data schema version].
- Planned release version: [Full SHA merged into `huawei_waterloo_main_branch`, artifact checksum, configuration, and data schema version].
- Tested implementation C / baseline B / integration version: [Identifiers consistent with the test report].
- Test and AI review evidence: [`TEST_REPORT.md` and `review.md` in the task directory].
- Code Lead's human approval of release contents: [Approver, time, explicit version, and evidence; initially Pending approval].
- Operational authority: [Authorizing person, time, environment, actions, and evidence; code merge approval does not automatically authorize production deployment].
- Risk level and recovery difficulty: [Fill in].
- Current status: [Planned / Pending authorization / Ready / In progress / Released / Rolled back / Blocked].

If release contents differ from the reviewed and tested version, update verification and human approval for the differences first. Reports may reference tested implementation C plus checks of later explanatory documentation changes. Behavior, configuration, or acceptance changes are not exempt merely because a document is involved.

## 2. Contents, dependencies, and compatibility (required)

- Changes observable by users or research workflows: [Fill in].
- Interface / configuration / dependency changes: [Fill in].
- Data migration / model / prompt / evaluation set changes: [Fill in or explain N/A].
- Coexistence and compatibility of old and new versions: [Fill in].
- Affected modules, running services, and owners: [Fill in].
- Known defects and excluded scope: [Fill in].
- Previous artifacts, configuration, backups, and access methods to retain: [Locations and versions; no credentials].

## 3. Pre-release verification and execution (required for actual execution)

| Order | Action and purpose | Working directory / environment | Reproducible command or steps | Expected result | Actual time, result, exit code, and evidence | Executor |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Check authority, target environment, and artifact version | [Fill in] | [Actual command] | [Versions match] | [Not executed] | [Fill in] |
| 2 | Verify recovery prerequisites | [Fill in] | [Backup validation or applicable recovery check] | [Agreed standard met] | [Not executed] | [Fill in] |
| 3 | Execute release | [Fill in] | [Project-specific steps] | [Fill in] | [Not executed] | [Fill in] |
| 4 | Verify release result | [Fill in] | [Smoke, critical behavior, and performance checks] | [Fill in] | [Not executed] | [Fill in] |

This template does not provide generic deployment commands that have not been verified against the repository. Fill in steps that work for this project. For irreversible actions, first document recovery boundaries and authorization conditions. A generic instruction to revert code does not address data risks.

## 4. Observation window and acceptance thresholds (required)

- Observation start/end and owner: [Fill in].
- Data sources and accessible monitoring/logs: [Fill in].
- Performance measurement conditions: [Hardware, concurrency, data size, repetitions, and baseline environment].

| Metric / function | Success threshold approved in advance | Current-version baseline measurement | Post-release measurement | Rollback trigger | Evidence |
| --- | --- | --- | --- | --- | --- |
| [Critical behavior / error rate / latency / quality or other relevant item] | [Fill in] | [Measured value or Not measured] | [Measured value or Not measured] | [Specific condition and duration] | [Fill in] |

If the observation window is incomplete or required measurements are missing, retain Pending acceptance or Unable to determine. Do not claim the release is stable.

## 5. Rollback plan and recovery boundaries (required)

- Triggers: [Consistent with the table above, including functional failures].
- Decision-maker / executor / existing authority: [Fill in].
- Rollback target: [Confirmed code commit, artifacts, configuration, and data versions].
- Recoverable and unrecoverable effects: [Explicit data, external side-effect, schema migration, and other boundaries].
- Recovery time / acceptable data loss targets: [Fill in when applicable; otherwise explain N/A].
- Prior validation evidence: [Rehearsal or feasibility check, environment, and date; explicitly state if unverified].

| Order | Rollback action | Working directory / environment | Actual command or steps | Expected recovery result | Execution evidence |
| --- | --- | --- | --- | --- | --- |
| 1 | [Project-specific containment or restoration of previous artifacts] | [Fill in] | [Fill in] | [Fill in] | [Not executed] |
| 2 | [Configuration or data recovery, if applicable] | [Fill in] | [Fill in] | [Fill in] | [Not executed / explain N/A] |
| 3 | [Functional and performance checks after recovery] | [Fill in] | [Fill in] | [Compare with approved thresholds] | [Not executed] |

Use ordinary commits, review, and merges for code fixes or rollback, preserving history. Do not rewrite persistent branches with force push. Restoring a running artifact and reverting a Git branch are separate actions; record their facts and authority separately.

## 6. Outcome, incidents, and handoff (required)

- Release conclusion: [Not executed / Pending acceptance / Accepted / Failed / Rolled back].
- Actual running version and confirmation command: [Fill in].
- Rollback execution and outcome: [Not executed / Executed; start/end, actual steps, and verification evidence].
- Deviations, missing evidence, and residual risks: [Fill in].
- Incident or anomaly record: [Path / No known anomaly, with observation scope].
- Follow-up tasks, owners, and deadlines: [Fill in].
- Human acceptance owner / time / decision evidence: [Fill in; initially Pending acceptance].
- Handoff record: [`docs/tasks/<TASK-ID>/HANDOFF.md` or actual receipt record].

Related templates: [Test report](TEST_REPORT_TEMPLATE.md), [Review](REVIEW_TEMPLATE.md), [Handoff](HANDOFF_TEMPLATE.md).
