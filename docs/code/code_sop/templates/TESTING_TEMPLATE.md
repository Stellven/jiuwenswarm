# Testing and research evaluation standard

> Suggested location: `docs/governance/TESTING.md`. Maintain long-lived verification methods and entry points here. TASK is the authoritative source for each task's approved acceptance criteria and thresholds; `write_code.md` references AC identifiers and sets the required checks. Actual results belong only in the task's TEST_REPORT or, for a simplified task, its TASK/PR verification section. This document is not evidence that tests passed. Select checks proportionate to impact rather than running every check for every task.

- Maintainer / effective version / human confirmation: [Fill in].
- Environment baseline: `docs/governance/ENVIRONMENT.md`, version [fill in].
- Module test entry points and owners: [Verified paths and owners; mark unknown items pending verification].
- Long-lived requirement sources: [Architecture, contracts, and versions; task-specific acceptance remains in TASK].

## 1. Select methods by impact — maintain at project level

Maintain real entry points and module owners. Each task references applicable rows and selection reasons in its directive or plan. Explain task-specific N/A decisions in that task's records, not by changing this shared matrix.

| Trigger | Fact to verify | Suggested method | Maintenance owner / actual entry point / missing setup |
| --- | --- | --- | --- |
| Explanatory documentation only | Links, references, versions, and workflow agree | Static inspection and human reading | [Fill in; do not invent program test results] |
| Local behavior change | Normal path matches approved behavior | Unit tests with observable assertions | [Fill in] |
| Bug fix | Original trigger is fixed without related regression | Regression case; before/after comparison where feasible | [Fill in] |
| Boundaries or state transitions | Empty/extreme values, repeated calls, state constraints | Boundary and invariant checks | [Fill in] |
| External calls or failures | Timeout, failure, cancellation, retry, partial success | Controlled failure injection and state checks | [Fill in] |
| Interfaces across modules | Request/response contracts, call chains, compatibility | Joint provider/consumer contract and integration tests | [Fill in] |
| Data or persistent state | Schema compatibility, migration, recovery boundaries | Representative data checks and recovery rehearsal when needed | [Fill in] |
| Routing, models, prompts, or evaluation changes | Task quality, behavior constraints, cost, latency | Versioned evaluation set and reproducible experiments | [Fill in] |
| Critical performance path | Latency, throughput, resources, or cost meet requirements | Same-environment baseline comparison and repeated measurement | [Fill in] |
| Configuration, dependencies, or shared code | Runtime and affected consumers avoid regressions | Installation/build, static checks, related regression tests | [Fill in] |

Tests should detect incorrect behavior, not mirror implementation logic or merely assert that no exception occurred. Affected owners confirm cross-module scope. Mock-only verification does not prove real-service integration. Do not resolve required-test failures by removing assertions, lowering thresholds, or widening ignores.

## 2. Existing repository entry points — statically inspected, not run

On 2026-09-25, static inspection of commit `52abe68db2dd167485f6bd79d6e36e193d608e64` covered `tests/README.md`, `pytest.ini`, and `Makefile`. Candidate commands from the repository root are `python -m pytest tests/unit_tests/` and `python -m pytest tests/`; select actual files by change scope. Interpreter, dependencies, and platform adaptation are described in [ENVIRONMENT_TEMPLATE.md](ENVIRONMENT_TEMPLATE.md).

- Declared unit/integration/system/slow/async markers do not prove relevant cases are marked or collected; record actual case counts.
- The configured coverage plugin and outputs do not establish behavioral correctness; no universal coverage threshold is assumed.
- `make lint` in the Makefile suppresses nonzero exits from pylint, mypy, and codespell. Execute and record these checks separately.
- The clone recorded a server 404 for a video LFS object. Recheck affected resources; missing-resource failures or skips are not passes.

## 3. Reproducibility requirements — required in applicable task reports

The table defines what a report must contain. Fill actual values in the task's single verification record, not in this long-lived standard.

| Item | Required report information |
| --- | --- |
| Code and environment | Implementation C, main-branch baseline B, actual integration version, dependencies/configuration, working directory |
| Data version and split | Identifier/digest, sample counts, train/dev/test split, deduplication and contamination checks, sampling method |
| Evaluation-set boundaries | Frozen version, use in tuning, comparability with formal reports, reasons for changes |
| Models and prompts | Model/service version, prompt version, tool permissions, context handling, sampling settings |
| Randomness | Split/model/tool seeds where controllable, repetition count, uncontrollable sources and impact |
| Runtime conditions | Hardware/GPU, concurrency, caching/warm-up, timeout/retry, network and external-service state |
| Quality judgment | Appropriate metrics, scoring rules, evaluator/annotation version, disagreement handling, failure cases |
| Cost and latency | Billing basis/unit/date, token or call counts, end-to-end measurement boundary, quantiles, sample size |
| Statistics and artifacts | Aggregation, variation/intervals, raw-result locations, run IDs, reproduction commands, access requirements |

There is no universal quality, cost, or latency threshold for RSI, Router, Capsule, and Verifier. Select metrics before implementation based on users and the baseline. Never claim improvement without measurements. If no stable baseline exists, first conduct explicitly authorized measurement and report its limits.

## 4. Where acceptance and verification records belong

| Information | Authoritative location | How other documents reference it |
| --- | --- | --- |
| AC, metrics, thresholds, allowed regression | Acceptance section in `docs/tasks/<TASK-ID>/TASK.md` | TASK version and AC identifier |
| Design coverage and measurement protocol | Actual design and directive/plan sections | Link to the protocol without redefining thresholds |
| Baseline/current measurements, commands, environment, results | Task TEST_REPORT; simplified tasks may use a TASK/PR verification section | Actual path/section and C/B; do not duplicate results |
| Deferral reasons, permitted stage, follow-up responsibility | Relevant CHANGE_REQUEST | Keep the actual incomplete result in the report and reference the approval |
| AI review, human review, merge decision | Task `review.md` and explicit human decision source | Covered version and decision evidence |

Use real task paths or section links. Simplified tasks need not create empty reports to satisfy references. Threshold or evaluation-protocol changes require a TASK/design revision and approval before reevaluation; never change the basis after seeing results to make a check pass. Report important subsets and failures because averages may conceal regressions.

## 5. Results and evidence validity — report rules

Each execution records working directory, exact command, environment, C/B, time, exit code, pass/fail/skip counts, and raw evidence. Use Passed, Failed, Skipped, Not run, Blocked, or N/A with a reason. Zero tests, all skipped tests, missing services, and suppressed errors cannot be reported as verified behavior.

Compare baseline and changed code in the same environment to identify pre-existing failures. Explain unverified scope. Facts support test conclusions; humans decide merges. Code, contracts, configuration, dependencies, tests, or baseline changes require appropriate revalidation. Review conflict resolutions as new code. Later result-only documentation may reference the tested implementation after a diff check; reports need not contain their own commit SHA.

- Preserve required-check completion, failures, missing evidence, impact, and temporary measures in the task verification record.
- A deferral references the Code Lead's explicit decision, permitted stage, follow-up owner/deadline, and failure response. A task cannot be Done while required follow-up verification remains incomplete.
- Update this document when methods, entry points, or lasting rules change. Maintain task state in CURRENT_STATUS and execution results in the task record.

Use [TEST_REPORT_TEMPLATE.md](TEST_REPORT_TEMPLATE.md) for execution evidence and [REVIEW_TEMPLATE.md](REVIEW_TEMPLATE.md) for review.

