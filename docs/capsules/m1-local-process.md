# M1 Docker development and test preparation

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
runner process wrote to its named results volume as UID11001. Local development
builtins remain visibly NOT_RUN for model-based catalog qualification. Sign-in,
authenticated inference, accepted Pi build/timings and the complete research
campaign are separate live outcomes, not established by these tests.

After sign-in, start with the included summary smoke campaign. Scientific runs
also need frozen public resources, root scorer profile and matching runtime
binding. The prepared Pi task helper supplies task material; it does not create
an accepted run or activate Pi Benchmark. The smoke does not substitute for the
Builder/Pi and full-system demonstrations.
