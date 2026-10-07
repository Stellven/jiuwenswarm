> **Historical AI4R-001 record:** identities, decisions and observations below retain their original scope. Current M1 design and registration use the repository design-package and M1 TASKS; old review/approval cards do not govern new v2 work.

# AI4R-001 Validation Guide

Version: 0.1 | Draft, not executed subscription acceptance.
Read [plan](plan.md), [runtime contract](contracts/runtime.md), [data model](data-model.md) and [ENVIRONMENT](../../docs/governance/ENVIRONMENT.md) first.

## Prerequisites and current availability

Use the pinned project environment and packaged Codex 0.144.4, a personal eligible subscription, and a dedicated empty application profile. Existing baseline tests are runnable now. New codex test files, subscription routes and their behavior below are **proposed and not implemented**; do not run these instructions as if current HEAD had the feature.

Runtime schema generation already succeeded without signing in or sending a model turn. It does not demonstrate account eligibility or model/tool behavior.

## Preparation after implementation

From the repository root, choose a new absolute path owned by the test run and set it before starting/importing the application:

```powershell
$env:JIUWENSWARM_DATA_DIR = Join-Path $env:LOCALAPPDATA ('ai4r-validation-' + [guid]::NewGuid().ToString('N'))
$nodeToolDir = Join-Path $env:LOCALAPPDATA 'ai4r-tools\node-v22.23.3-win-x64'
$env:Path = $nodeToolDir + [IO.Path]::PathSeparator + $env:Path
.\.venv\Scripts\python.exe --version
```

Retain the exact profile path for restart checks. Never use jiuwenswarm-init --force or delete another profile. Proposed runtime implementation sets its own isolated CODEX_HOME; do not copy existing auth.json. Remove model-provider keys from the test launch environment without printing values. Separately run a contaminated-environment negative fixture to prove policy enforcement.

The standard project entry point `.\.venv\Scripts\jiuwenswarm-start.exe` exists through pyproject.toml; launching the new behavior through it is a **future integration check**, not an action performed during this design task. Confirm its effective profile and service binding before interactive validation.

## Automated checks

Existing baseline command and outcomes: TEST_REPORT Section 3. After adding the proposed files, from repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit_tests/common/test_codex_profile.py tests/unit_tests/gateway/test_codex_subscription_handlers.py tests/unit_tests/runtime/test_codex_subscription_policy.py tests/unit_tests/runtime/test_codex_session_adapter.py tests/unit_tests/runtime/test_codex_tool_bridge.py tests/unit_tests/runtime/test_codex_auxiliary.py tests/unit_tests/runtime/test_codex_lifecycle.py --no-cov -q
```

From jiuwenswarm/channels/web/frontend, with selected Node:

```powershell
npm.cmd run test:chat-model-selection
npm.cmd run test:chat-store-streaming
npm.cmd run test:session-input
npm.cmd run test:web-client-runtime-ack
npm.cmd run build
```

Add proposed `test:codex-subscription` script for the new onboarding/auth/session cases as an implementation task; do not claim that script exists now. Also run impacted existing settings/history/permission suites using their actual package.json entries after inspecting them.

## Q1 — First use and account lifecycle (AC-01, AC-06)

Q1a (US1 milestone): open the fresh profile, complete managed ChatGPT login, verify catalog/readiness, restart with the same profile, then sign out. Expected: no model-key input, no legacy import, no credentials in browser storage/ordinary logs, and signed-out admission blocked. This establishes account setup, not successful model execution.

Q1b (after T018/T019 and required runtime integration): sign in and start a harmless text request: “Reply with the word ready; do not use tools.” Record selected model/runtime and actual result, not token values. Sign out and verify a new request is blocked. T023 owns this execution proof; AC-06 remains incomplete until it and the other policy checks pass.

## Q2 — Chat and team routing (AC-02, AC-08; C02–C06)

Run a main-agent read-only task, a code-mode workspace inspection and a two-member team task with distinct expected outputs. Confirm the leader and every worker use App Server, not merely an external teammate. Inspect provider-construction/outbound-call traps. Match final history to session/agent identity; final output alone is insufficient without path evidence.

## Q3 — Tools and interaction (AC-03)

In a disposable workspace, request a controlled file edit. Deny once and verify no write; approve a separate run and verify one write. Exercise user question, steering, pause/resume, and cancel while a tool is pending. Re-send a stale decision and a duplicate tool receipt; they must not affect another run or repeat the side effect. Include native leader permission/plan/budget rails in G1 fixtures.

## Q4 — Failure and policy (AC-04, AC-06)

Use fake runtime fixtures for auth expiry, quota refusal, missing/incompatible CLI, network loss and crash. Never exhaust real account limits deliberately. Verify explicit recovery state, no API fallback, no empty-success result and no blind replay after ambiguous tool effects. Confirm sanitized logs include enough IDs to diagnose without auth payloads.

## Q5 — Persistence and isolation (AC-07)

Create two new sessions with distinct fixture text, run concurrently, cancel one, restart the runtime/application, and restore history. Verify identities and canceled/unknown states remain distinct. Test logout during execution and a late login/turn callback. Account switching must not attach old-account threads. First-run initialization must not repeat.

## Q6 — Whole-project coverage (AC-08)

Execute every research C01–C20 row with its own fixture and record evidence. Refine rows into concrete callable paths where currently grouped; include vector memory, image/audio/video, search, RSI/evaluation, plugins, background helpers and shipped launchers/platforms. A disabled capability, random embedding mock or untested free-search substitution does not pass. Any unresolved row prevents completion unless an explicit requirements change changes scope.

## Evidence and cleanup

Record implementation C, fetched integration baseline B, fixture versions/digests, commands, model/runtime, counts, logs, failure states and limitations in TEST_REPORT. Keep unit mocks distinct from live account proof. Screenshots of settings/onboarding must cover wide/narrow layouts, relevant themes, Chinese/English strings and Chrome107-compatible behavior. Log out and stop test processes; profile deletion is a separate explicit action, not automatic cleanup.

This guide specifies expected outcomes; no acceptance pass, approval or deployment is implied.

## M1 preview entry point (implementation v0.3)

From the repository root, with the pinned dependencies in ENVIRONMENT installed:

```powershell
.\.venv\Scripts\python.exe -m jiuwenswarm.codex_start
```

This new launcher uses `~/.jiuwenswarm-ai4r`, preserves the old installation and starts the subscription adapter. The original chat page contains the subscription panel. Select **Sign in with ChatGPT**, open the returned secure link, complete sign-in personally, refresh readiness, and send a short ordinary text message. No API key is entered into this flow. Do not run this as a shared-account server.

Status: launcher profile logic, transport, facade/history fixtures, React controls and build have checks in TEST_REPORT. Full application startup, real Gateway/AgentServer fixture journey and actual sign-in-link creation/cancellation now pass. Browser visual QA and actual account/model execution remain unverified. This is not a release-ready procedure yet. After restart or logout, start a new conversation; saved history remains accessible. Teams, tools, media, background/auxiliary coverage and legacy settings replacement are pending; current preview text explicitly identifies this boundary.

Signed-out production-service smoke (no login or model call):

```powershell
.\.venv\Scripts\python.exe specs/AI4R-001-codex-subscription/verification/probe_product.py
```

### Personal acceptance journey

Open the running preview at http://localhost:5173, or double-click Start-Codex.cmd in the repository and use the Web UI address printed in its window. Do not launch a second copy while the preview is already running.

1. Select Sign in with ChatGPT, then Open secure sign-in. Complete the official sign-in personally and return to the app. Wait for Signed in or refresh status.
2. Start an ordinary text conversation without tools, attachments, teams or plan mode. Send: "Reply with exactly: Subscription chat works."
3. Ask: "Write 200 short numbered sentences about gardening." While output is arriving, select Stop. This is a bounded acceptance request using the user's subscription.
4. Refresh the page and open the same conversation. Confirm the first exchange and the stopped partial reply remain. Send a short follow-up to check continued use.
5. Record actual outcomes against AC-01/02/03/06/07 without declaring whole-project acceptance. If a failure occurs, record the visible error; do not send credentials or the sign-in URL in chat.

Reproducible socket fixture (synthetic provider/account, isolated profile):

```powershell
.\.venv\Scripts\python.exe specs/AI4R-001-codex-subscription/verification/probe_journey.py
```

## Accepted browser demo

Xiaoyang accepted the running demo on 2026-09-28 and requested publication. Follow [CODEX_DEMO](../../docs/code/CODEX_DEMO.md) for the tested-machine launch command, fresh Windows setup, browser walkthrough, and restart limitation. Detailed live case records were not supplied with the user acceptance; do not relabel unrun automated checks as passed.
