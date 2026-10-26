# M1 Docker development and test preparation

**October 26 reliability update:** the interrupted-attempt custody gap is fixed;
all 31 status/recovery checks and the combined 215 selected development checks
pass. The previously recorded legacy failures below are historical. Use the
[reproduction guide](reliability-reproduction.md) for exact commands, source/image
identities, negative controls and current limits. The rebuilt app passed
authenticated readiness and status retrieval; live Pi/scientific acceptance
remains pending.

The October 25 user decision selects ordinary generated processes **inside the
app container**. M2 lab sandboxing is deferred. This replaces the nested
bubblewrap/cgroup prerequisite for newly captured M1 runs; retained sandboxed
runs keep their original semantics.

Source implementation: `2663ed82095e6bce4cdd875a510fc8e3a818e1f1`, after merging
remote M1 `809351f8` with the Builder branch and earlier Planner, utilities and
deployment histories. Subsequent deployment commits fix Compose verification
and retain private benchmark references. Exact final source/image refs are in
the verification receipt beside this page.

## Model and agent boundary

OpenJiuwen ReAct owns Builder history, actions and the edit/test/repair loop.
Its native client requests one fresh text completion through the governed Codex
subscription bridge. Builder tool descriptions are text in that request; only
the OpenJiuwen provider dispatches authorized tools. Identity, budgets,
cancellation and independent verifier calls remain.

The pinned Codex profile disables shell, multi-agent, browser/computer use,
code-mode host, plugins, image generation, skills, sleep, goals, hooks and
unbounded connection retries. Unexpected tool events/items or server requests
fail the turn. An actual packaged app-server test verifies effective settings.
Existing ChatGPT sign-in stays; no API key or desktop credential import is added.
This is a completion-like app-server interface, not a raw API-key connection.

## M1 execution and custody

Root-authored runtime schema 5 explicitly pins `execution_mode=m1_app_process`.
An environment flag cannot override an existing capture. New local captures use
`local-research-unified-v5`. Immutable releases are Builder `m1-17`, classification
Benchmark `m1-10-agent-pi`, and separate Pi Benchmark `pi-m1-4`.

Typed jobs run serially as UID/GID10002 with a stripped environment,
no-new-privileges, address-space/UID process limits, wall timeout, bounded logs
and process-group cleanup. The app envelope is 4 GiB/256 PIDs. Existing captured
resources are verified, temporarily aliased under root-owned `/resources`, and
removed afterward. Private references persist in a root-only Docker volume.

Receipts report actual identity/affinity and **inherited networking/shared app
namespaces**. They claim neither a nested isolation probe nor per-job cgroup
limits. Root job attestations bind receipts to the original runtime and
configuration/declaration/admission mapping. Uncertain cessation stays blocked.
M1 does not prove confinement against arbitrary hostile code or network denial;
its POC protocols require no external network, without enforcing that denial.

Edits still invalidate tests. Exact-byte compile, nonempty unittest and public
smoke checks precede submission. Independent replay checks, separate verifiers
and gates remain. Benchmark scores the immutable accepted artifact independently;
candidate timing claims and automatic post-submission repair remain excluded.

## Operation and verification

Use [OPERATIONS.md](../../deploy/m1/OPERATIONS.md). The normal local path requires
**Docker and a browser**, using existing app/runner images at localhost5175.
Host Python/Node/SDK/WSL package setup is unnecessary; the Python launcher is
optional. The human starts Docker, signs in/MFA and makes required production
activation decisions. Builds, finite runner grants, commands and result capture
are automated. Credentials remain in private volumes. The runner writes results
as UID11001; `docker cp` retrieves them.

Recorded checks: **219 focused Docker tests plus 4 subtests**, **64 Docker boundary
tests**, and **31 host/operator tests**. Boundary tests include actual ordinary
processes, the packaged Codex configuration, and controlled-response native
OpenJiuwen tests. No cases were deselected. Tests use a read-only source mount,
ephemeral SDK logs and a filter for an upstream dependency's Python SyntaxWarning.
Older interrupted suites/legacy CLI failures remain historical, not passes.

Both production images built; the app served HTTP200 on localhost5175. An actual
runner process wrote to its named results volume as UID11001. The user completed
sign-in; authenticated runner readiness passed. The first live run recorded four
completed governed Codex calls with observed model `gpt-6.1-sol`, including two
independent verifier calls. It halted at static-plan feasibility because the
bundled summary example omitted scientific resources. The example now explicitly
selects the planned workflow with a synthetic PDF, preserving the failed run.
Local development builtins remain visibly NOT_RUN for model-based catalog
qualification. Accepted Pi build/timings and the complete scientific campaign
remain separate live outcomes, not established by these tests.

After sign-in, start with the included planned PDF summary smoke campaign. Scientific runs
also need frozen public resources, root scorer profile and matching runtime
binding. The prepared Pi task helper supplies task material; it does not create
an accepted run or activate Pi Benchmark. The smoke does not substitute for the
Builder/Pi and full-system demonstrations.

The runner drives the authenticated typed HTTP API from outside the app process.
It uploads selected inputs, prepares intake, submits/polls/cancels/reconciles runs
and retrieves verified evidence. Compose starts the app container. Neither the
runner nor its invoking agent needs direct store access or a Docker socket inside
the runner. See the operation/interface table in the operations guide.

### October 26 live summary and status correction

Run `run:67c206c472b74ed39a7548607dbffa09` completed Compiler, Planner,
Summary and Delivery: 11 completed governed model calls (5 worker, 6 verifier).
The report preserves that its PDF source is fictional and has no measurements.
Status retrieval exposed a scope comparison bug: the Planner's inputs include
its capsule catalog, whereas Binder independently checks four proposal resources.
The reader now joins those four exact proposal refs to their original parent
ports. Original custody, gate, chronology and check-result validation remain.

The old runner campaign paused on HTTP503 and remains pinned to its original
build. After deploying the reader fix, an authenticated client recovered the
completed run without repeating model calls. Collection verified 19,769 archive
members / 23,085,765 uncompressed bytes. Archive SHA256:
`ddc425ec2435c99db9ad8b67e209e4e295f03f926319bf089f7bca84554474fa`.
This is read-only workflow acceptance, not Builder/Pi or scientific acceptance.

Isolated follow-up: 45 capability/Planner checks passed before stale replay
fixtures failed setup. Their protected read ceiling now includes the actual
qualified request, and all 8 replay checks pass. A new controlled-verifier FAIL
case proves Tier1 can pass while Tier2 rejects, records the independent call and
recording-only halt, preserves prior activation, and creates no product gate or
acceptance. It does not establish live semantic rejection quality. Legacy finite
status-fixture failures and interrupted broader follow-ups remain visible in the
evidence; they are not counted as passes. The local product has no E2/E3 profile
and lacks production authoring tooling to freeze one from an existing run.
