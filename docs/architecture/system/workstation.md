---
id: system.workstation
type: module-spec
status: draft
version: 1
sources: [../../product/prd-m1-full-2026-10-02.txt, integration.md, observability.md]
provides: [system.workstation_api, system.installer, system.local_session]
consumes: [system.run_lifecycle, system.config, system.events]
depends_on: [integration.md, observability.md, lifecycle.md, environment.md]
tags: [system, m1, cli, ui]
level: detail
prd: [5.1.1, 5.2.1, 5.2.2, 5.3.1]
---

# M1 local workstation interfaces

PRD: 5.1.1, 5.2.1, 5.2.2, 5.3.1

> Answers: Which local CLI, session and API interfaces does M1 expose?

## Purpose

PRD 5.1–5.6 uses the native CLI, Web UI, TUI and tmux. Their domain-neutral [adapters](integration.md#term-adapter) consume the same run API and immutable records. They cannot change blueprint thresholds, [Gate](../verification.md#term-gate) decisions or active configuration. [Module map](modules.md) is the home of code placement; [environment](environment.md) is the home of installation/config and identity prerequisites.

## Installation and services

Install the digest-pinned Docker image using [deployment](deployment.md)'s fixed launch manifest. The existing `jiuwenswarm-start` primitives are wrapped inside the monolith; native host pip installation is not used ([decisions](../decisions.md), A12). Startup scaffolds input/docs, input/repo, input/datasets, poc, outputs, records/runs, records/bundles, records/exports and offline [RSI](../rsi.md#term-rsi) task directories. It deploys admitted capsule/prompt/check packages through author kit and admission, then publishes the M1 [prep plan](../types/run-plan.md#term-prep-plan), vocabulary, policy and [fixtures](test-surfaces.md#term-fixture) inputs. `cc bootstrap` (the installer) admits and activates the seed [capsules](../capsule/capsule.md#term-capability-capsule) with `expected_current_hash` null and actor `installer`: toy capsules at build step 1, research capsules when each is ported. It never declares a capsule admitted just because a folder was copied. Referee authors seed hidden split manifests and at least 20 loop/20 final cases outside Git; installer refuses missing/overlapping splits before enabling RSI.

Service order is effective config, store/recovery, [model bridge](model-bridge.md#term-model-bridge), security/oracle pre-check, runner supervisor, native API server and local UI. Readiness is gated on doctor. Shutdown first stops new submissions, cancels or completes the current authorized request, seals evidence, stops runner children, then closes bridges/store. Process restart during an active run writes a `halt_report` with reason `INTERRUPTED` and waits; it never auto-resumes autonomous research. Native instance commands are reused at `jiuwenswarm/start_services.py:385`, `:886`, `:904`, `:929` and readiness `:687` (`6cc05c36b`). Port fallback is disabled for the PRD-pinned Web UI port; occupied 5173 yields a specific doctor error.

## Interface: CLI and public run API

Messages of this module.

- **Start a run (prompt, channel, workspace, optional seed and headless)** (call, CLI, Web, benchmark client -> supervisor). Schema: [`execution-v1.schema.json#launch_request`](../contracts/execution-v1.schema.json).
- **Run handle or typed rejection** (call, supervisor -> CLI, Web, benchmark client). Schema: [`execution-v1.schema.json#launch_result`](../contracts/execution-v1.schema.json).
- **Stop a run, evidence kept** (record, CLI, Web -> supervisor). Schema: [`execution-v1.schema.json#abort_request_run`](../contracts/execution-v1.schema.json).
- **RunView: state, phase, current step, [gate verdict](../capsule/gate-host.md#term-gate-verdict), outputs** (report, supervisor -> CLI, Web, TUI). Schema: [`execution-v1.schema.json#run_status_view`](../contracts/execution-v1.schema.json).
- **JSON printed by cc status, inspect, doctor** (report, CLI -> user or script). Schema: [`execution-v1.schema.json#cli_json_output`](../contracts/execution-v1.schema.json).
- **Ephemeral local session token file** (record, launcher -> in-container CLI). Schema: [`execution-v1.schema.json#local_session_token`](../contracts/execution-v1.schema.json).
- **DoctorReport: [checks](../capsule/fields.md#term-check), ready flag, probed profile** (report, doctor -> launcher, supervisor, CLI). Schema: [`tools-v1.schema.json#doctor_report`](../contracts/tools-v1.schema.json).

Native command namespace: `jiuwenswarm cc run --topic <text> --workspace <dir>`, `cc status <run_id> [--json]`, `cc inspect <run_id> --step <step_id>`, `cc doctor [--json]`, `cc resume <run_id>`, `cc abort <run_id>`, `cc artifacts <run_id>`, `cc bootstrap`, `cc attempts clean <run> <step>`, `cc library list`, `cc library standing <name>` and `cc verdict show <decl_hash>`. These are proposed adapters into the native CLI, not implemented commands. `cc resume <run_id>` is run by a human: it creates the `human_review_record` (action `resume_after_fix`) and a new attempt of the interrupted step under unchanged pins. A crash, a kill or an auth loss never resumes by itself: the run stays [halted](lifecycle.md#term-halt) (`INTERRUPTED`, or `ENVIRONMENT_BLOCKED` after `AUTH_RELOGIN_REQUIRED`) until that command. `cc attempts clean` inspects and cleans the disposable attempt directory of a crashed step. Test-only seam: the config key `cc.test.review_injection` (a pre-recorded review file) stands in for the human reply and is refused by the production profile. Schema of the run-start, resume and abort requests: `execution-v1.schema.json#launch_request`, `execution-v1.schema.json#resume_request`, `execution-v1.schema.json#abort_request_run`. Schema of the `--json` output: `execution-v1.schema.json#cli_json_output`. CLI exit codes are 0 success (a completed run, including a scientific FAIL), 2 launch or configuration rejected (invalid intake, config or arguments), 3 halted, 4 environment unavailable (environment, security or storage); a user interrupt ends the process with the shell's 130 and is not a research outcome. HTTP status codes of the run API are separate from these exit codes. JSON output is closed `{version: 1, run_id?, state, data?, reason?}`; text output renders the same record-based state.

The local API exposes `POST /cc/runs` with `{version, prompt, channel, workspace, request_id}` (`request_id` required; optional `config_ref`, `seed`, `headless`); `GET /cc/runs/{id}`; `GET /cc/runs/{id}/steps/{step}`; `GET /cc/runs/{id}/artifacts`; `GET /cc/content/{sha256}`; `POST /cc/runs/{id}/abort`. Run replies use `RunView {version, run_id, state: pending|running|evaluating|halted|completed|aborted, current_step?, gate_verdict?, reason?, output_refs, phase?, prep_plan_ref?, planned_plan_ref?}`; schema `execution-v1.schema.json#run_status_view`. A `POST /cc/runs` reply is `execution-v1.schema.json#launch_result`. `POST /cc/runs/{id}/abort` takes `human_review_ref` only for a halted run. Submission accepts only authorized configured workspaces. Abort requests stop execution but do not erase evidence. Resume is terminal-only at M1 (`cc resume`). Content endpoints require membership in that run's accessible manifests and never serve arbitrary filesystem paths, hidden fixtures, auth data or another session's content. Bytes are verified against the hash before delivery; missing/corrupt content gives typed storage failure.

New submissions create new [runs](lifecycle.md#term-run); the launch `request_id` is required (the CLI and Web generate one when the user gives none) so a lost response can be recovered. The supervisor durably maps one request id to a run; identical prompt/workspace under the same id returns that run, differing content yields REQUEST_CONFLICT. This local request identity is distinct from a dispatch identity and does not enable arbitrary cross-run deduplication.

## Behavior: local session and authentication

Publish the container Web API/UI only at host 127.0.0.1:5173; the internal server binds its container interface. The trusted launcher mints an unpredictable ephemeral bearer token and presents a one-time loopback URL. On the first exchange, remove the token from browser location/history and use native session storage for authenticated local requests. Do not print tokens into persistent research logs, traces or evidence bundles. Tokens expire after configured TTL or service shutdown; restart mints a new one. Verify token on HTTP/WebSocket connections, restrict allowed browser origins to the local UI, and refuse unauthenticated content/run APIs. OS identity remains the user profile; no login portal or external bot is created.

The native Web prompt routes through the authenticated CC entry branch before ordinary text-chat dispatch. Reuse the `workflow.updated` shape and native run tree, with record-backed Gate status and markdown output; the CC adapter installs the subscription without requiring team-mode execution. Optional progress events may be dropped; reconnect fetches authoritative RunView. Rendering cannot release a node. Non-team rendering and the new branch require downstream integration fixtures.

Native TUI/tmux provides monitor, attach/detach, log inspection and authenticated terminal triage. Name sessions `cc-<run_id>`; keep pid/start-time metadata under the run directory, verify ownership before attach or termination, and do not construct shell commands from user prompts. Do not treat a tmux detach as cancellation. If no controlling terminal is available for [human_session](lifecycle.md#term-human-session), preserve halted state and tell the user to attach; the Web UI displays the requirement without editing the workflow.

## Failure

| Situation | Outcome | Recovery |
|---|---|---|
| Invalid token or workspace path | denied | obtain a new local session token through the launcher |
| Same submission `request_id` with different prompt or workspace | `REQUEST_CONFLICT` | submit with a new request id |
| tmux session owned by another identity | denied | use the session of the same identity |
| Dropped view event | the view repairs on reload from records | reload |
| Experiment toggle requested in production | refused | use an approved isolated experiment profile |

## Visibility and retrieval

Use native views for node state, Gate status, time budget, artifact paths and inspection. Capture static OS/CPU/GPU facts once at run start; no live utilization dashboard is required. Time and model-call counts are known; absent token/cost counts remain null, not zero. The final report preserves all scientific labels, including FAIL, and all recorded non-blocking limitations. Published paths identify immutable stored bytes; partial delivery cannot show completed. Inspection reads complete stage evidence and Gate records. Privacy is local folder inspection/deletion; users are warned by the native operation when deleting active-run data, and subsequent missing refs cannot authorize execution.

## Tests: acceptance contracts

Rows in [test surfaces](test-surfaces.md#verification-table): [V24](test-surfaces.md#verification-table), [V29](test-surfaces.md#verification-table), [V30](test-surfaces.md#verification-table), [V35](test-surfaces.md#verification-table) (launcher, headless halt exit 3, resume, abort), [V39](test-surfaces.md#verification-table) (read-only view API), [V41](test-surfaces.md#verification-table) (crash then resume), [V42](test-surfaces.md#verification-table) (abort mid-call), [V43](test-surfaces.md#verification-table) (CLI in CI: exit codes 0, 2, 3, 4).

Installer/CLI/Web/TUI each demonstrate readiness and the same run state, halt status and artifact bytes. Invalid tokens/workspace paths are denied. A dropped view event repairs on reload. A tmux session owned by another identity is denied. Scientific-negative runs display their report and exit successfully. Docker/profile/platform validation obligations remain explicit in [deployment](deployment.md); no unrun runtime/UI scenario is claimed as passed.

## Token-file contract

The launcher stores its ephemeral token at the private container runtime path `/run/jiuwenswarm/local-session.json` in a user-owned mode-0700 directory, using exclusive creation/atomic replace at mode 0600 and no symlink following. Closed file fields are token, created_at, expires_at, instance_id, loopback_origin and version (1) (schema `execution-v1.schema.json#local_session_token`). The in-container CLI reads this file; a host CLI receives the token through an explicit local bootstrap exchange and never reads an arbitrary container path. The CLI verifies file user, mode, expiry and instance and adds `Authorization: Bearer <token>` to requests. Web uses the one-time exchange then the same header; WebSockets authenticate before subscription. Tokens never enter CC snapshots, stdout research logs or artifacts. Shutdown revokes and removes the file; stale instance/expired token is rejected. Restart invalidates previous tokens even if a stale file survived a crash. Existing single local service ownership is verified before replacing the file.

## Docker and benchmark transport

All client adapters use the same monolith lifecycle and records. [Deployment](deployment.md) fixes loopback host publication on 8787 for authenticated versioned benchmark HTTP endpoints and 5173 for native workstation views. Benchmark clients use this HTTP API (`benchmark_request`, `export_request`), not `launch_request`. [Benchmark export](benchmark-export.md) is the home of route/envelope meanings, including asynchronous submission, status, abort and committed exports. Bearer tokens are never included in prompts, snapshots or evidence; no endpoint accepts arbitrary container/host filesystem paths. TUI/tmux runs inside the fixed container. A host terminal attaches through its explicit container CLI, without exposing Docker control to capsule code.

## Programmatic headless entry

The launch, resume and abort requests are closed and carry no `ext`. Every CLI command exits with one of four codes: 0 success or completed research, 2 launch, intake or configuration rejected, 3 halted (including a user cancellation, Ctrl-C, of a waiting prompt), 4 environment unavailable; no other code is used. The halt report printed in headless mode (exit code 3) is `execution-v1.schema.json#halt_report`. The adopted [benchmark boundary](benchmark-export.md) supplies `run_task(task, config_ref, seed, request_id) -> RunHandle` and `export_run(run_id, request_id) -> BenchmarkExportRef`. Seed is [frozen](lifecycle.md#term-freeze) as cc.execution.seed requested/effective/unavailable_reason in the effective run configuration. Preserve the requested nonnegative seed; record applied seed per component and null/NOT_SUPPORTED for endpoints without seed support. Model audit records and benchmark export retain both requested and effective seed evidence. A seeded workload does not imply deterministic model output. Headless returns halted state when review is required and never waits for stdin. `POST /cc/runs` accepts the same request identity, optional validated config reference and seed; CLI maps `--headless`, `--config-ref`, `--seed`, and `--request-id` to this API. The response exposes stable run_dir/status/manifest refs. Configuration selects a frozen track; unsupported production experiment toggles are refused. The benchmark harness's eventual export schema is `PENDING_SOURCE` and is adapted at export; US-16 is partial by design until the harness side supplies it.

## Workstation precedent and replacement

The UI is a projection of durable records, following the state/read-model separation documented by [Microsoft CQRS](https://learn.microsoft.com/en-us/azure/architecture/patterns/cqrs). M1 uses one local store rather than separate databases. Reuse native CLI/Web/TUI to reduce front-end work; replace adapters behind the same run API if native views prove unsuitable. Acceptance verifies reconnect and independent client views against the same records.
