---
id: coder-prompt-benchmark-runner
status: ready-to-send
source: Sources/Prompts/2026-10-22-sequential-control-data-runner.txt; Sources/Prompts/2026-10-22-two-image-runner-layout.txt; Sources/Prompts/2026-10-22-runner-code-observability.txt
last_reviewed: 2026-10-22
next_action: Deliver one sequential app-testing path with runner control, observability and persistent data collection
---
# benchmark-runner

## For human and AI

- **Purpose:** Get a useful tool working quickly so we can test AI4Research with supplied tasks and files.
- **Deployment:** AI4R builds two images: `ai4r` for the app and `benchmark-runner` for the separate CLI runner. Run one container of each.
- **Control plane:** The runner prepares inputs, submits tasks one at a time, tracks progress, handles deadlines/cancellation and resumes observation after interruption.
- **Data plane:** The runner transfers input files, executes declared preparation/collection code, captures observability and saves actual outputs/artifacts to the user's mounted output directory.
- **Your paths:** Cases, inputs and output directory are user-selected. Held-out tests are supplied elsewhere. Saved files survive container removal; humans judge results.
- **First version:** Sequential, CLI only. Worker pools, app replicas, distributed scheduling and new framework infrastructure are not required.

## Implementation instructions

Build this in AI4R, our AI4Research branch of JiuwenSwarm. The runner is the control and data plane for a testing campaign; these are responsibilities of one package/process, not two new services. It uses the app's supported interface; the app owns research execution and its policies. Spark deployment is optional.

### 1. Reuse the existing path

Read branch instructions, current M1 task/spec records and the relevant deployment/client contracts. The previously inspected branch was `ai4r_M1`; verify the actual checkout. Locate design files named `benchmark-runner.md` (Platform benchmark runner), `automation.md` and the sidecar/test-runner `README.md` pages. Record this sequential, human-reviewed scope through the native process; earlier parallel requirements are superseded.

Reuse `research_sidecar` client, ledger, reconciliation, evidence and cleanup code plus `deploy/m1` assets. Preserve scoped access, file/hash checks and ownership enforcement. Use existing dependencies and telemetry. Do not build a new SDK, plugin framework, monitoring platform or scheduler. Keep brief progress/decisions/next steps for context recovery.

### 2. Build and connect the two containers

Build `ai4r` with app code/dependencies and `benchmark-runner` with runner code/dependencies. Small neutral contracts may be shared; exclude runner modules from the app wheel/image. Exclude external cases, answers, datasets, credentials, caches and results from both build contexts. Expose the Compose service roles with those exact names, namespace resources by project, and remove required score/referee mounts for this mode without breaking other modes.

Use Compose, private networking and non-root processes. Neither container gets the Docker socket. A small host helper may manage Compose lifecycle, but the runner CLI executes inside `benchmark-runner`. Ordinary app startup must work without the runner.

Use one documented versioned authenticated interface for **readiness/build identity, input upload, submit with client request ID, reconcile, status/events, cancel, and artifact list/download with collection confirmation/retention**. Reuse existing routes. **Modify the app where required to complete this connected path**, preserving research verification, permissions and effect controls. Fix implementation gaps; report actual external prerequisites separately. Pin the build before a campaign and never patch its running target.

Accept endpoint, credential reference and expected identity through configuration. Another hypothetical system implementing this interface must work without private app imports or system-name branches; no second integration is needed now. Optional internal stages/metrics remain unavailable when unsupported. Do not redesign the research workflow or add app concurrency.

### 3. Run the sequential queue

Provide CLI operations for `doctor`, `run`, `status`, `resume`, `cancel`, `export` and owned `cleanup` (equivalent existing commands are fine). Include helpful errors/progress and `--json`; logs go to stderr. Noninteractive runs report required human action instead of hanging. Exit codes describe execution/prerequisite failures, not research correctness.

Load versioned YAML/JSON cases with task text, input references, setup/steps, repeats, limits and deadlines. Persist case/request/run IDs and queue state on the output mount using the existing ledger or SQLite. One task executes at a time: submit → observe terminal state → collect → next task. There is no worker leasing or replica management to build.

After interruption, reconcile the recorded request before any submission; never blindly rerun uncertain work. A disconnected or cancellation-pending run is not stopped: pause dispatch until its state is reconciled so tasks cannot overlap. Preserve failed/blocked/cancelled/timed-out results. Continue after ordinary task failure according to policy; pause new work on shared access/storage failure or unresolved execution. Use fresh run workspaces without changing normal user sessions.

Support case-declared trusted preparation/collection scripts in owned runner workspaces. Execute generated/untrusted task code through the app's existing isolated execution path, not automatically in the runner. Apply explicit commands, working directories, allowed environment, time/resource limits; capture stdout, stderr, exit codes and files. Never execute in user source folders or treat a script exit code as a correctness assessment.

### 4. Persist files and observations

Require explicit user-selected case/input/output host paths resolved on the Docker host, including remote deployment. Bind cases/inputs read-only and output read-write into the runner, for example `/cases`, `/inputs`, `/results`. Validate paths, types, ownership/UID access, conflicting roots and actual mount writability. No fallback to ephemeral container-local output. Create only explicitly requested new directories and owned campaign subfolders; never overwrite existing user files.

Send only permitted task inputs to the app, never private criteria/answers or the whole case store. Collect **actual artifact bytes**, not app-internal paths or links, through the interface into campaign/case/repeat folders. Keep the ledger and collection manifest there. No shared app-private database/state mount. Container writable layers consume disk and disappear on removal; they are not automatically memory-only.

Stream files, validate safe relative paths/archives and sizes/hashes, write temporary files, durably flush and publish atomically. Refuse traversal/symlinks/conflicting names. Retry interrupted collection without rerunning the task or replacing verified evidence. Collect partial artifacts for failed/cancelled runs. Execution and collection have separate states; missing files, disk full and permission/network failure are explicit. Retain app-side pending state/artifacts until collection confirmation or documented expiry; cleanup cannot silently delete uncollected data.

Capture live and saved logs/events, stage/command/tool activity and exposed results, errors, timings, app decisions, identities/configuration and available CPU/memory/disk/GPU/model usage. Correlate by campaign/case/repeat/run/step; record sampling scope, contention and missing metrics. Reuse existing telemetry and add missing essential app observations; advanced optional instrumentation must not delay the first working path. Redact secrets and respect export audiences. Bound disk/cache/log growth and do not infer missing usage as zero.

Automatically save JSON records, a CSV matrix and a readable Markdown report with **Inputs and Setup**, **Actual Output and Observations**, artifact links and blank **Assessment**, **Evidence references**, **Review notes**. Reports rebuild from saved data without reruns or lost annotations. Humans assess quality: no automatic task score, judge, task PASS/FAIL or winner. Distinguish scientific negatives from infrastructure failures.

### 5. Finish a small working version

First deliver **one supplied task → actual app execution → artifact saved on the host**. Then demonstrate a short sequential queue, interruption recovery and reports. Use generic smoke fixtures; do not invent held-out tests. Keep this delivery small: no UI, VM/factory work, parallelism or extensive framework construction.

Run focused connected checks: two images/containers with correct contents; real input/output mounts and authenticated calls; two cases executing in sequence with separated results; cancellation/resume without duplicate submission; failed/interrupted artifact collection; and removal of both containers while host files/hashes survive. Existing sentinel files remain unchanged; cleanup refuses foreign resources and retains results. Use a small interface fixture for configuration-only portability rather than another product integration.

Provide a short build/start/doctor/run/status/export runbook, plus resume/cancel/cleanup examples. Secrets stay out of images/logs/exports. Cleanup is limited to owned disposable resources with no global prune. Report exact commands, evidence and limitations; finish independent work if host access/login is pending and never claim unrun checks passed.
