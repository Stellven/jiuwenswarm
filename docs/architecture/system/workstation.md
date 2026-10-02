---
type: design
status: draft
version: 1
owner: muk
sources: [../../product/prd-m1-full-2026-10-01.txt, integration.md, observability.md]
provides: [system.workstation_api, system.installer, system.local_session]
consumes: [system.run_lifecycle, system.config, system.events]
depends_on: [integration.md, observability.md, lifecycle.md, environment.md]
tags: [system, m1, cli, ui]
---

# M1 local workstation interfaces

PRD 5.1–5.6 uses the native CLI, Web UI, TUI and tmux. Their domain-neutral adapters consume the same run API and immutable records. They cannot change blueprint thresholds, Gate decisions or active configuration. [Module map](modules.md) owns code placement; [environment](environment.md) owns installation/config and identity prerequisites.

## Installation and services

Wrap `pip install jiuwenswarm` and `jiuwenswarm-start` rather than introduce another product launcher. Startup scaffolds input/docs, input/repo, input/datasets, poc, outputs, records/runs, records/bundles, records/exports and offline RSI task directories. It deploys admitted capsule/prompt/check packages through author kit and admission, then publishes the M1 policy/vocabulary/plan. It never declares a capsule admitted just because a folder was copied. Fixture owners seed hidden split manifests and at least 20 loop/20 final cases outside Git; installer refuses missing/overlapping splits before enabling RSI.

Service order is effective config, store/recovery, model bridge, security/oracle pre-check, runner supervisor, native API server and local UI. Readiness is gated on doctor. Shutdown first stops new submissions, cancels or completes the current authorized request, seals evidence, stops runner children, then closes bridges/store. Process restart during an active run marks interruption; it never auto-resumes autonomous research. Native instance commands are reused at `jiuwenswarm/start_services.py:385`, `:886`, `:904`, `:929` and readiness `:687` (`6cc05c36b`). Port fallback is disabled for the PRD-pinned Web UI port; occupied 5173 yields a specific doctor error.

## CLI and public run API

Native command namespace: `jiuwenswarm cc run --topic <text> --workspace <dir>`, `cc status <run_id> [--json]`, `cc inspect <run_id> --step <step_id>`, `cc doctor [--json]`, `cc resume <run_id>`, `cc abort <run_id>`, `cc artifacts <run_id>`. These are proposed adapters into the native CLI, not implemented commands. `resume` requires recorded human review through the native terminal session. Exit codes are 0 successful command/completed research (including a scientific FAIL), 2 invalid intake/config/arguments, 3 halted research, 4 unavailable environment/security/storage and 130 user cancellation. JSON output is closed `{version: 1, run_id?, state, data?, reason?}`; text output renders the same record-based state.

The local API exposes `POST /cc/runs` with `{prompt, workspace}`; `GET /cc/runs/{id}`; `GET /cc/runs/{id}/steps/{step}`; `GET /cc/runs/{id}/artifacts`; `GET /cc/content/{sha256}`; `POST /cc/runs/{id}/abort`. Run replies use `RunView {run_id, state: pending|running|evaluating|halted|completed|aborted, current_step?, gate_verdict?, reason?, output_refs}`. Submission accepts only authorized configured workspaces. Abort requests stop execution but do not erase evidence. Resume is terminal-only at M1. Content endpoints require membership in that run's accessible manifests and never serve arbitrary filesystem paths, hidden fixtures, auth data or another session's content. Bytes are verified against the hash before delivery; missing/corrupt content gives typed storage failure.

New submissions create new runs; local submission `request_id` may be supplied by CLI/Web for lost-response recovery. The supervisor durably maps one request id to a run; identical prompt/workspace under the same id returns that run, differing content yields REQUEST_CONFLICT. This local request identity is distinct from a dispatch identity and does not enable arbitrary cross-run deduplication.

## Local session and authentication

Bind native Web API/UI to 127.0.0.1:5173 as the PRD states. The trusted launcher mints an unpredictable ephemeral bearer token and presents a one-time loopback URL. On the first exchange, remove the token from browser location/history and use native session storage for authenticated local requests. Do not print tokens into persistent research logs, traces or evidence bundles. Tokens expire after configured TTL or service shutdown; restart mints a new one. Verify token on HTTP/WebSocket connections, restrict allowed browser origins to the local UI, and refuse unauthenticated content/run APIs. OS identity remains the user profile; no login portal or external bot is created.

The native Web prompt routes through the CC entry adapter, not the text-only Codex chat adapter. Reuse the `workflow.updated` shape and native run tree, with record-backed Gate status and markdown output. An optional progress event can be dropped; reconnect fetches authoritative RunView. Rendering cannot release a node. Native views must demonstrate non-team CC runs (issue 25), and the exact `chat.send` branch is still source-verification work (26).

Native TUI/tmux provides monitor, attach/detach, log inspection and authenticated terminal triage. Name sessions `cc-<run_id>`; keep pid/start-time metadata under the run directory, verify ownership before attach or termination, and do not construct shell commands from user prompts. Do not treat a tmux detach as cancellation. If no controlling terminal is available for human_session, preserve halted state and tell the user to attach; the Web UI displays the requirement without editing the workflow.

## Visibility and retrieval

Use native views for node state, Gate status, time budget, artifact paths and inspection. Capture static OS/CPU/GPU facts once at run start; no live utilization dashboard is required. Time and model-call counts are known; absent token/cost counts remain null, not zero. The final report preserves all scientific labels, including FAIL, and all recorded non-blocking limitations. Published paths identify immutable stored bytes; partial delivery cannot show completed. Inspection reads complete stage evidence and Gate records. Privacy is local folder inspection/deletion; users are warned by the native operation when deleting active-run data, and subsequent missing refs cannot authorize execution.

## Acceptance contracts

Installer/CLI/Web/TUI each demonstrate readiness and the same run state, halt status and artifact bytes. Invalid tokens/workspace paths are denied. A dropped view event repairs on reload. A tmux session owned by another identity is denied. Scientific-negative runs display their report and exit successfully. Installer/security provisioning conflicts remain explicit in [open issues](../open-issues.md) 40 and 57; no unrun runtime/UI scenario is claimed as passed.

## Token-file contract

The launcher stores its ephemeral token at `~/.jiuwenswarm/runtime/local-session.json` in a user-owned mode-0700 directory, using exclusive creation/atomic replace at mode 0600 and no symlink following. Closed file fields are token, created_at, expires_at, instance_id and loopback_origin. CLI reads this file, verifies owner/mode/expiry/instance and adds `Authorization: Bearer <token>` to requests. Web uses the one-time exchange then the same header; WebSockets authenticate before subscription. Tokens never enter CC snapshots, stdout research logs or artifacts. Shutdown revokes and removes the file; stale instance/expired token is rejected. Restart invalidates previous tokens even if a stale file survived a crash. Existing single local service ownership is verified before replacing the file.

## Proposed: programmatic run entry (development only, 2026-10-02)

For the benchmark harness: an entry taking `{task, config, seed}` that returns the result and a stable `run_dir`, with `headless` ([lifecycle](lifecycle.md)). The `seed` is pinned in the run's configuration snapshot ([storage](storage.md)) and is the root of the blueprint's seed policy. Not adopted. Detail: [proposal](../m1/capsule-inventory-proposal.md#benchmark-harness-requests-headless-entry-and-config-assembled-components).
