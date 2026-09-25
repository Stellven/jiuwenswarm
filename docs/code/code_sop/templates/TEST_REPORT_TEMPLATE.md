# Test and Acceptance Report: [TASK-ID]

> Usage: copy to `docs/tasks/<TASK-ID>/TEST_REPORT.md`. Record verification proportional to the risk of behavior, interface, configuration, dependency, or performance changes. Small changes may use a compact table in the task or PR. Versions, environment, commands, actual results, and missing checks are required. If no test applies, explain why and record alternative verification; do not write All passed. Performance, migration, and similar sections are required only when applicable; otherwise explain N/A.

## 1. Verification target and acceptance basis (required)

- Task / test executor / execution time and time zone: [Fill in].
- Risk level and verification scope: [Fill in and explain why coverage is sufficient].
- Approved design and `write_code.md`: [Paths, versions, and approval records].
- Merge target: `huawei_waterloo_main_branch`.
- Target baseline B: [Full SHA, synchronization source, and time].
- Tested implementation commit C: [Full SHA].
- Tested working tree state: [Clean / list uncommitted changes and their impact; do not cite C while omitting working tree differences].
- Actual execution target: [C itself / integration commit or tree combining C and B; record SHA or reproducible construction steps].
- Relationship to final merge contents: [Identical / integration verification still required / differences and revalidation conclusion].

| Acceptance ID | Approved requirement and threshold | Related case / check | Actual observation | Status |
| --- | --- | --- | --- | --- |
| AC-01 | [Behavior or numerical threshold agreed in advance] | [Command ID / case] | [Measured result] | [Passed / Failed / Not run / Blocked / N/A] |

Do not silently lower thresholds after seeing results. Threshold changes require renewed approval and a record of the reason and original value.

## 2. Reproducible environment (required)

| Item | Actual configuration |
| --- | --- |
| Working directory | [Absolute repository-root path or explicit repository-relative directory] |
| Operating system / architecture | [Fill in] |
| Runtime / package manager / key dependencies | [Actual versions and lockfiles] |
| Installation and preparation commands | [Complete commands; identify missing setup steps] |
| Services / configuration / environment variables | [Names and non-sensitive settings; no credential values] |
| Data / model / prompt versions | [Paths, versions, or checksums; explain N/A] |
| Random seeds / sampling settings | [Fill in or explain N/A] |
| Hardware / concurrency / network conditions | [Required for performance; otherwise include as relevant to impact] |

## 3. Commands and original evidence (required)

Each command must be reproducible from its stated working directory. Redact tokens, personal information, and restricted research data from logs, while preserving the location of original evidence for authorized access.

| ID | Working directory | Actual complete command | Time / duration | Exit code | Case counts and observations | Log / artifact location | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T-01 | [Fill in] | [Command actually executed] | [Fill in] | [Actual value; N/A if not executed] | [Passed/failed/skipped counts and key output] | [Path or access-controlled link] | [Passed / Failed / Not run / Blocked] |

Zero collected cases, all skipped cases, missing commands, or a successful build alone do not establish expected behavior. For pre-existing failures, attach a baseline B comparison in the same environment and analyze the task's impact. Do not hide them from the report.

## 4. Coverage selected by risk (record status or explain N/A for each row)

| Scope | Related commands / cases | Status and reasoning |
| --- | --- | --- |
| Normal path for changed behavior | [Fill in] | [Fill in] |
| Original defect reproduction and post-fix regression | [Fill in] | [Fill in] |
| Boundaries, exceptions, and state after failure | [Fill in] | [Fill in] |
| Callers and module integration | [Fill in] | [Fill in] |
| Types, static checks, and build | [Fill in] | [Fill in] |
| Relevant regression scope | [Fill in] | [Explain selected scope] |
| Data compatibility, migration, and rollback | [Fill in] | [Fill in] |
| Permissions, data handling, or external service constraints | [Fill in] | [Fill in] |

## 5. Performance and research evaluation (required when applicable)

- Performance relevance: [Why measurements are needed, or basis for N/A].
- Fair comparison: [Baseline commit; same data/model/configuration/hardware; warm-up, repetitions, and measurement method].
- Variability handling: [Repeated-run statistics, error ranges, and treatment of anomalous runs; disclose insufficient samples].

| Metric | Approved threshold / maximum allowed regression | Baseline measurement | Current measurement | Unit / sample size | Meets requirement? | Original records |
| --- | --- | --- | --- | --- | --- | --- |
| [Relevant latency, throughput, memory, cost, quality, or other metric] | [Fill in] | [Actual value or Not measured] | [Actual value or Not measured] | [Fill in] | [Yes / No / Unable to determine] | [Fill in] |

Without a baseline or sufficient samples, state which conclusions the evidence can and cannot support. Do not claim performance improvement based on estimates, AI speculation, or a single observation.

## 6. Missing checks, failures, and risks (required)

| Unmet item | Cause and impact | Interim measure | Owner / deadline | Human decision and evidence |
| --- | --- | --- | --- | --- |
| [Fill in, or explicitly state None] | [Fill in] | [Fill in] | [Fill in] | [Pending / authorized human decision; AI cannot approve] |

## 7. Version changes and conclusion (required)

This report references C and does not need to contain the SHA of its own eventual commit. If subsequent commits only add explanatory documentation that does not affect execution, testing, or acceptance, retain C's evidence and list the follow-up scope and diff verification commands in the PR. Changes to code, tests, configuration, dependencies, generation inputs, or acceptance conditions require re-execution for the affected scope and an updated report. If baseline B advances, assess integration impact as well; Code Lead confirms whether approval remains valid.

- Changes after C and verification: [Commit range, files, working directory, actual diff commands, and results].
- Baseline changes after B: [Evidence of no change / changes and impact].
- Revalidation record: [New C/B, command IDs, and results; or scope-based reason re-execution is unnecessary and human confirmation].
- Verification conclusion: [Passed / Partially passed / Failed / Blocked; state the applicable scope].
- Behavior established by evidence: [Fill in].
- Behavior not yet established: [Fill in].
- Follow-up actions: [Fill in].

Passing tests is not approval to merge. The final merge decision belongs in the human approval record described by [REVIEW_TEMPLATE.md](REVIEW_TEMPLATE.md).
