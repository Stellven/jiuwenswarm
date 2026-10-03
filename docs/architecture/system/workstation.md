---
type: design
status: draft
version: 1
owner: muk
sources: [../../product/prd-m1-full-2026-10-02.txt, integration.md, observability.md]
provides: [system.workstation_api, system.installer, system.local_session]
consumes: [system.run_lifecycle, system.config, system.events]
depends_on: [integration.md, observability.md, lifecycle.md, environment.md]
tags: [system, m1, cli, ui]
---

# M1 local workstation interfaces

PRD 5.1–5.6 uses the native CLI, Web UI, TUI and tmux. Their domain-neutral adapters consume the same run API and immutable records. They cannot change blueprint thresholds, Gate decisions or active configuration. [Module map](modules.md) owns code placement; [environment](environment.md) owns installation/config and identity prerequisites.

## Installation and services

Install the digest-pinned Docker image using [deployment](deployment.md)'s fixed launch manifest. The existing `jiuwenswarm-start` primitives are wrapped inside the monolith; native host pip installation is superseded by the user's Docker agreement. Startup scaffolds input/docs, input/repo, input/datasets, poc, outputs, records/runs, records/bundles, records/exports and offline RSI task directories. It deploys admitted capsule/prompt/check packages through author kit and admission, then publishes the M1 policy/vocabulary/plan. It never declares a capsule admitted just because a folder was copied. Fixture owners seed hidden split manifests and at least 20 loop/20 final cases outside Git; installer refuses missing/overlapping splits before enabling RSI.

Service order is effective config, store/recovery, model bridge, security/oracle pre-check, runner supervisor, native API server and local UI. Readiness is gated on doctor. Shutdown first stops new submissions, cancels or completes the current authorized request, seals evidence, stops runner children, then closes bridges/store. Process restart during an active run marks interruption; it never auto-resumes autonomous research. Native instance commands are reused at `jiuwenswarm/start_services.py:385`, `:886`, `:904`, `:929` and readiness `:687` (`6cc05c36b`). Port fallback is disabled for the PRD-pinned Web UI port; occupied 5173 yields a specific doctor error.

## CLI and public run API

Native command namespace: `jiuwenswarm cc run --topic <text> --workspace <dir>`, `cc status <run_id> [--json]`, `cc inspect <run_id> --step <step_id>`, `cc doctor [--json]`, `cc resume <run_id>`, `cc abort <run_id>`, `cc artifacts <run_id>`. These are proposed adapters into the native CLI, not implemented commands. `resume` requires recorded human review through the native terminal session. Exit codes are 0 successful command/completed research (including a scientific FAIL), 2 invalid intake/config/arguments, 3 halted research, 4 unavailable environment/security/storage and 130 user cancellation. JSON output is closed `{version: 1, run_id?, state, data?, reason?}`; text output renders the same record-based state.

The local API exposes `POST /cc/runs` with `{prompt, workspace}`; `GET /cc/runs/{id}`; `GET /cc/runs/{id}/steps/{step}`; `GET /cc/runs/{id}/artifacts`; `GET /cc/content/{sha256}`; `POST /cc/runs/{id}/abort`. Run replies use `RunView {run_id, state: pending|running|evaluating|halted|completed|aborted, current_step?, gate_verdict?, reason?, output_refs}`. Submission accepts only authorized configured workspaces. Abort requests stop execution but do not erase evidence. Resume is terminal-only at M1. Content endpoints require membership in that run's accessible manifests and never serve arbitrary filesystem paths, hidden fixtures, auth data or another session's content. Bytes are verified against the hash before delivery; missing/corrupt content gives typed storage failure.

New submissions create new runs; local submission `request_id` may be supplied by CLI/Web for lost-response recovery. The supervisor durably maps one request id to a run; identical prompt/workspace under the same id returns that run, differing content yields REQUEST_CONFLICT. This local request identity is distinct from a dispatch identity and does not enable arbitrary cross-run deduplication.

## Local session and authentication

Publish the container Web API/UI only at host 127.0.0.1:5173; the internal server binds its container interface. The trusted launcher mints an unpredictable ephemeral bearer token and presents a one-time loopback URL. On the first exchange, remove the token from browser location/history and use native session storage for authenticated local requests. Do not print tokens into persistent research logs, traces or evidence bundles. Tokens expire after configured TTL or service shutdown; restart mints a new one. Verify token on HTTP/WebSocket connections, restrict allowed browser origins to the local UI, and refuse unauthenticated content/run APIs. OS identity remains the user profile; no login portal or external bot is created.

The native Web prompt routes through the authenticated CC entry branch before ordinary text-chat dispatch. Reuse the `workflow.updated` shape and native run tree, with record-backed Gate status and markdown output; the CC adapter installs the subscription without requiring team-mode execution. Optional progress events may be dropped; reconnect fetches authoritative RunView. Rendering cannot release a node. Non-team rendering and the new branch require downstream integration fixtures.

Native TUI/tmux provides monitor, attach/detach, log inspection and authenticated terminal triage. Name sessions `cc-<run_id>`; keep pid/start-time metadata under the run directory, verify ownership before attach or termination, and do not construct shell commands from user prompts. Do not treat a tmux detach as cancellation. If no controlling terminal is available for human_session, preserve halted state and tell the user to attach; the Web UI displays the requirement without editing the workflow.

## Visibility and retrieval

Use native views for node state, Gate status, time budget, artifact paths and inspection. Capture static OS/CPU/GPU facts once at run start; no live utilization dashboard is required. Time and model-call counts are known; absent token/cost counts remain null, not zero. The final report preserves all scientific labels, including FAIL, and all recorded non-blocking limitations. Published paths identify immutable stored bytes; partial delivery cannot show completed. Inspection reads complete stage evidence and Gate records. Privacy is local folder inspection/deletion; users are warned by the native operation when deleting active-run data, and subsequent missing refs cannot authorize execution.

## Acceptance contracts

Installer/CLI/Web/TUI each demonstrate readiness and the same run state, halt status and artifact bytes. Invalid tokens/workspace paths are denied. A dropped view event repairs on reload. A tmux session owned by another identity is denied. Scientific-negative runs display their report and exit successfully. Docker/profile/platform validation obligations remain explicit in [deployment](deployment.md); no unrun runtime/UI scenario is claimed as passed.

## Token-file contract

The launcher stores its ephemeral token at the private container runtime path `/run/jiuwenswarm/local-session.json` in a user-owned mode-0700 directory, using exclusive creation/atomic replace at mode 0600 and no symlink following. Closed file fields are token, created_at, expires_at, instance_id and loopback_origin. The in-container CLI reads this file; a host CLI receives the token through an explicit local bootstrap exchange and never reads an arbitrary container path. The CLI verifies owner/mode/expiry/instance and adds `Authorization: Bearer <token>` to requests. Web uses the one-time exchange then the same header; WebSockets authenticate before subscription. Tokens never enter CC snapshots, stdout research logs or artifacts. Shutdown revokes and removes the file; stale instance/expired token is rejected. Restart invalidates previous tokens even if a stale file survived a crash. Existing single local service ownership is verified before replacing the file.

## Docker and benchmark transport

All client adapters use the same monolith lifecycle and records. [Deployment](deployment.md) fixes loopback host publication on 8787 for authenticated versioned benchmark HTTP endpoints and 5173 for native workstation views. [Benchmark export](benchmark-export.md) owns route/envelope meanings, including asynchronous submission, status, abort and committed exports. Bearer tokens are never included in prompts, snapshots or evidence; no endpoint accepts arbitrary container/host filesystem paths. TUI/tmux runs inside the fixed container. A host terminal attaches through its explicit container CLI, without exposing Docker control to capsule code.

## Programmatic headless entry

The adopted [benchmark boundary](benchmark-export.md) supplies `run_task(task, config_ref, seed, request_id) -> RunHandle` and `export_run(run_id, request_id) -> BenchmarkExportRef`. Seed is frozen as cc.execution.seed requested/effective/unavailable_reason in the effective run configuration. Preserve the requested nonnegative seed; record applied seed per component and null/NOT_SUPPORTED for endpoints without seed support. Model audit records and benchmark export retain both requested and effective seed evidence. A seeded workload does not imply deterministic model output. Headless returns halted state when review is required and never waits for stdin. `POST /cc/runs` accepts the same request identity, optional validated config reference and seed; CLI maps `--headless`, `--config-ref`, `--seed`, and `--request-id` to this API. The response exposes stable run_dir/status/manifest refs. Configuration selects a frozen track; unsupported production experiment toggles are refused. Saurav's eventual schema is adapted at export.

## Workstation precedent and replacement

The UI is a projection of durable records, following the state/read-model separation documented by [Microsoft CQRS](https://learn.microsoft.com/en-us/azure/architecture/patterns/cqrs). M1 uses one local store rather than separate databases. Reuse native CLI/Web/TUI to reduce front-end work; replace adapters behind the same run API if native views prove unsuitable. Acceptance verifies reconnect and independent client views against the same records.
