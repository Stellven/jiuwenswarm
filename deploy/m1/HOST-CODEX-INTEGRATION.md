# Existing host Codex login for AI4Research benchmarks

Maintained deployment guide. Updated October 26, 2026 (America/Toronto).

The `host-codex-app-server` backend lets the protected AI4R model bridge use an
operator's existing native Codex ChatGPT login. It launches a bounded native
App Server for each model call. The application and benchmark runner remain in
their existing Linux containers, and Harbor retains trial and grading control.
The application UI remains at **http://127.0.0.1:5175**.

Latest October 26 account diagnosis: supported native `login status`,
`account/read` and `account/rateLimits/read` confirmed the same ChatGPT account
as this desktop app, matching the benchmark account pin. Ordinary usage is
allowed, with 4% consumed in the reported weekly window. No-inference helper
transport checks passed for small and 100,000-byte inputs. A fresh login was not
needed. Subsequent operator recovery preserved the historical unknowns and
authorized distinct new work after local-containment observations. Live
qualification and two CC development variants then completed on GPT-6.1-Sol.
Account evidence is under
`D:/Codex Development Runs/harbor-deployment-20261025/account-diagnostics-20261026/`.
The persistent WSL runtime
`/mnt/d/Codex Development Runs/.harbor-pilot-runtime/linux-venv/bin/python`
is available; its earlier `/tmp/ai4r-harbor-pilot-20261025` copy is absent.
See [LOCAL-MODEL-RECOVERY.md](LOCAL-MODEL-RECOVERY.md) for the supported
acknowledgement, exclusive runtime lock and protected no-inference probe.
Latest original results and remaining case blockers are recorded in
[serial validation status](../../benchmarks/harbor_suite/SERIAL-VALIDATION-STATUS.md).

This route uses the host CLI's existing authenticated account in place. It does
not turn a desktop chat into an inference API, import desktop session tokens,
or reuse an unrelated application's account volume. The operator must explicitly
authorize use of that account and verify its model access and workspace policy.

## Runtime and authentication boundaries

On Windows with WSL Docker, run the private relay with Linux Python in the
selected WSL distribution. Its catalog points to the Windows Python executable
through `/mnt/c/.../python.exe`. The relay sends the packaged stdlib helper
source to that interpreter with `-B -c` and sends the request on stdin. The
helper starts the native Windows `codex.exe`; no inference service is exposed
on TCP, and no source or credential file is copied into the app container.

The helper obtains the native Windows profile through
`SHGetFolderPathW(CSIDL_PROFILE)`. It restores the child process's Windows
`USERPROFILE`, `HOME`, `APPDATA` and `LOCALAPPDATA`, removes inherited Linux
`HOME` and `CODEX_HOME`, and supplies an environment allowlist. API keys,
provider endpoint overrides and proxy environment variables are excluded.
It does not read `auth.json`, set a new `CODEX_HOME`, or alter host login/config
files. Codex can perform its normal managed token renewal during authorized use.

Before inference, the helper verifies the native binary's SHA-256 and reads
the active account through App Server `account/read` with `refreshToken:false`.
It compares the SHA-256 of the returned email with the operator's account pin.
The email and account/login packets are excluded from model evidence. A changed
account fails admission before inference; an unobserved identity stays absent.

The existing [local-model interface](LOCAL-MODEL-INTERFACE.md) supplies the
authenticated Unix socket, peer UID/custody checks, durable request ledger and
app-only mounts. Keep its deployment requirements: a local rootful Linux Docker
daemon, private relay runtime/session, and dedicated socket export. Only the
app receives the read-only catalog/session and socket mount. The benchmark
runner, scientific execution sandboxes and public exports receive no relay
capability, host authentication cache or Windows profile mount.

## Catalog and exact model selection

The catalog retains schema `ai4r-local-model-catalog:1`. A host Codex catalog
uses the following backend fields, replacing the SSH/loopback backend fields:

| Field | Required value |
| --- | --- |
| `kind` | `host-codex-app-server` |
| `host_python` | Canonical absolute Linux-visible executable path; for Windows interop use `/mnt/c/.../python.exe` |
| `codex_executable` | Canonical native absolute path, for example `C:/.../codex.exe` |
| `codex_sha256` | SHA-256 of the exact qualified native executable |
| `account_fingerprint` | SHA-256 of the account email observed through the authorized native account API |
| `working_directory` | Existing native absolute operator directory, for example `D:/.../codex-work` |

Windows paths in the catalog use forward slashes and an uppercase drive letter.
Do not put a WSL `/mnt/c/...` path in `codex_executable` or
`working_directory`: those fields are consumed by Windows Python. The account
fingerprint is an identity pin, not a bearer credential. Obtain it through the
supported account API without printing or saving raw account/login responses;
never derive it by opening or exporting an authentication cache.

Example structure, **disabled until all paths and pins are verified**:

```json
{
  "schema": "ai4r-local-model-catalog:1",
  "gateway_id": "host-codex-sol",
  "backend": {
    "kind": "host-codex-app-server",
    "host_python": "/mnt/c/Operator/Python313/python.exe",
    "codex_executable": "C:/Operator/Codex/codex.exe",
    "codex_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
    "account_fingerprint": "0000000000000000000000000000000000000000000000000000000000000000",
    "working_directory": "D:/Operator/codex-work"
  },
  "transport": {
    "socket_path": "/run/ai4r-local-model/model.sock",
    "session_file": "/run/ai4r-local-model-config/session.json",
    "peer_uid": 1000,
    "socket_mode": 432
  },
  "models": [
    {
      "id": "local-host-codex-sol",
      "name": "Host Codex GPT-6.1-Sol",
      "model_name": "gpt-6.1-sol",
      "revision": "codex-cli-0.161.0-operator-qualified",
      "enabled": false,
      "context_window": 131072,
      "max_prompt_bytes": 262144,
      "timeout_s": 120,
      "reasoning_effort": "medium"
    }
  ]
}
```

Replace the example paths, zero digests, relay UID and declared context window
with verified deployment values. The current qualified combination is
**native Codex CLI 0.161.0, `gpt-6.1-sol`, reasoning effort `medium`**. Medium is
the supported effort in this backend. A binary update requires a new reviewed
hash/revision, qualification and idle reconfiguration.

Host Codex model entries have exactly `id`, `name`, `model_name`, `revision`,
`enabled`, `context_window`, `max_prompt_bytes`, `timeout_s` and
`reasoning_effort`. They do not accept `max_output_tokens`, `temperature` or
`enable_thinking`: this backend does not claim to enforce those OpenAI-compatible
HTTP generation parameters. `max_prompt_bytes` is enforced before submission;
the context window is declared policy metadata, not a newly imposed token cap.
Prompt bytes and context tokens are different units. The later paper pilot
needed a 52,582-byte intent prompt and a 68,204-byte requirements prompt, so its
original 32,768-byte operator cap was insufficient. Its corrected policy used
`max_prompt_bytes:131072` and `context_window:475000`; the latter was observed
in the qualified native `tokenUsage.modelContextWindow`. Protected call/case
deadlines stayed unchanged. Verify actual capacity and input requirements when
deploying elsewhere rather than copying the earlier small-prompt policy.

The helper supplies `model_reasoning_effort=medium` and requires App Server's
original `thread/start` result to report the exact requested model and
`reasoningEffort=medium` before sending `turn/start`. A missing/mismatched result
fails without inference. Model rerouting is rejected; there is no substitution
with Luna or another model. `model/list` is metadata, not proof of entitlement.

## Activate through the existing deployment interface

Provision the catalog, private runtime and socket export with the custody and
permissions documented in [LOCAL-MODEL-INTERFACE.md](LOCAL-MODEL-INTERFACE.md).
Keep the host CLI's normal login where it already resides. If that login is
unavailable, stop and use a separately authorized supported native login flow;
do not copy credentials from the desktop application or another container.

Run the relay from the matching checkout/runtime on the application host:

```sh
python -m jiuwenswarm.research.local_model_relay \
  --catalog /operator/host-codex-models.json \
  --runtime /operator/private/host-codex-relay \
  --socket-directory /operator/host-codex-export \
  --allowed-uid 10001
```

Starting the relay creates transport state, not an inference call. Preserve its
session and ledger across restarts. Configure the normal operator profile:

```sh
python deploy/m1/ai4r.py --profile /operator/app.json local-model configure \
  --catalog /operator/host-codex-models.json \
  --session-file /operator/private/host-codex-relay/session.json \
  --socket-directory /operator/host-codex-export
```

Use the existing build/start/stage workflow in
[HARBOR-INTEGRATION.md](HARBOR-INTEGRATION.md). A changed application build or
frozen source/bundle requires a new control workspace. Select the installed
`local-host-codex-sol` choice under **Settings → Models**, then create a fresh
run. Existing runs and continuations retain their frozen selection. Setting
Harbor's `--expected-model gpt-6.1-sol` only sets the attribution expectation;
it does not select the application model.

## Budgets, original evidence and uncertain outcomes

Every call uses a new empty operator working directory, an ephemeral thread,
read-only sandbox, disabled tools/apps/web/MCP and no project instructions.
Server tool/approval requests are refused. No shell, browser or file tool work
is authorized by this inference route. Configuration overrides replace the
entire MCP table with `{}` because inherited desktop transports may not be
valid in native CLI execution.

The catalog call timeout is between 1 and 600 seconds. The protected bridge
passes the remaining call budget; the relay reserves observer overhead, and
the helper reserves bounded interrupt/join time within its received budget.
Use **120 seconds** for the current benchmark policy. HTTP and stream retries
are disabled, and neither the helper nor the relay retries a generation.

The current helper emits native `ai4r-host-codex-response:2` receipts. Original
UTF-8 frame bytes are base64-encoded once; integer references identify the
original `thread/start`, `turn/start` and `turn/completed` frames. This avoids
duplicating large original outputs and repeated JSON escaping. The validator
also reads version 1 receipts for retained history. No OpenAI chat-completion
JSON or HTTP 200 result is fabricated. Original prompt/output, resolved
identity, turn ID and reported usage remain attributable. Account/login/catalog
packets are excluded from both public and private capture, including messages
with misleading thread tags. Missing observations remain unavailable.

The exact serialized public helper response stays within **1 MiB**; IPC retains
its **4 MiB** frame bound. Requested upstream opt-outs suppress redundant
agent-message and reasoning deltas; unsupported opt-outs may be ignored, so
capture and cancellation remain safe when deltas are still emitted. A separate
4096-frame rejection is no longer applied to otherwise byte-bounded evidence.

If full original evidence cannot fit, the receipt explicitly records
`full_original_trace:false` and `unavailable_reason:"wire_budget"`. Original
correlated start, prompt, interruption and terminal proof are retained when
representable. An observed, valid terminal allows a known **failed** result;
partial evidence never authorizes completed scientific success. If the actual
terminal itself cannot fit, the outcome remains unknown. Neither frames nor
output are truncated and presented as complete. A bounded stdout-only private
evidence carrier preserves additional original frames for relay diagnostics;
it is stripped before public RPC and the total stdout bound remains **4 MiB**.

On timeout/cancellation after submission, the helper requests `turn/interrupt`
and waits within its cleanup allowance for the actual terminal notification.
An interrupt acknowledgement alone is not containment proof. It kills and joins
only its own App Server child. Lost turn acknowledgement, missing terminal
proof or unresolved observer failure remains `outcome_unknown` with retained
bounded partial evidence. The relay's durable unknown claim blocks further
effects, including after restart; investigate the original native turn/host and
preserve the ledger before explicit operator reconciliation. Restarting the
relay or changing a request ID is not recovery authorization.

Evidence exhaustion cannot block the containment control write. Generation
requests still require capture admission before any bytes are sent. Known
failure requires an actual correlated terminal with status `completed`,
`interrupted` or `failed`; a status such as `inProgress` is not terminal proof.
Server tool/approval requests receive only a closed, matching refusal. Original
refusal evidence is validated as a failed outcome with terminal proof, or as
unknown if the terminal is missing; it never authorizes tool execution.

## Qualification and benchmark checkpoint

October 25, 2026: one public `2+2` JSON qualification succeeded through the
native Windows host CLI, and the Windows-Python route invoked through WSL also
succeeded. Both observed exact **`gpt-6.1-sol`**, **medium** reasoning and a
completed native turn using the existing host login. These checks establish
the inference transport and identity gate; they are not Harbor benchmark scores.
Helper boundary tests use offline process fixtures and perform no model calls.

The subsequent live checkpoint also qualified the actual app image through its
app-only Unix relay: a container request returned the original JSON answer,
observed `gpt-6.1-sol` and native usage. Harbor readiness then passed for the
fresh `ai4r-codex-20261025` deployment on port 5175. No new app sign-in or
credential copy was required; its protected model choice was
`local-host-codex61`, and the account locale was English.

Harbor job `ai4r-deployment-live-71cf70779ee7` completed **three trials, zero
Harbor exceptions, zero baseline successes**. Sparse-positive, dense-negative
and conflicting-units all received assessment `unavailable` with
`case_correctness:null`, `baseline_model_verified:false`,
`evidence_integrity:true` and `execution_available:true`. The last flag is a
transport/readiness assessment; no scientific experiment completed.

The first intention-compiler model call had an original remaining allowance of
119.7883 seconds and its invocation lasted 110.8339 seconds. Its original relay
receipt was `outcome_unknown`, with no native response, effective model, usage
or provider turn ID available. The original canonical ModelCall also retains
that uncertainty. The relay's durable guard blocked the following two model
requests. All app runs halted with `compiler_did_not_release`; the required
original run plan was unavailable. These observations do **not** establish
whether the initial failure was a timeout, transport failure, evidence limit or
native validation rejection. Do not report it as a measured model latency
failure or fabricate the missing observation from the earlier smoke calls.

Original controller data remains under
`/home/s50066325/ai4r-codex-harbor-20261025/live`, and raw campaigns remain under
`/home/s50066325/ai4r-codex-results-20261025`. A hash-verified review copy of 159
original assessments and fetched evidence files is retained in the workstation
`harbor-deployment-20261025/codex-activation/retained-harbor-results` directory.
The private original relay ledger remains in the deployment's
`model-control/private/requests.sqlite3`: one completed transport qualification
and one unknown inference claim. Preserve it; no replay or reclassification
was performed. There is no passing end-to-end AI4Research result at this checkpoint.

After collection, the app and runner were confirmed idle: zero active runs,
unfinished claims or unreleased leases. The owned Windows helper and inference
child had exited. The relay was stopped and its original ledger hash was
verified unchanged. This local process observation does not establish the
unobserved provider terminal status. Your existing host login stays in place.

The source now retains bounded original backend stdout privately **before**
native validation, in the relay runtime's `backend-receipts/` directory. Each
exclusive, mode-0600 `.receipt` has a sibling diagnostic JSON containing its
SHA-256/size, request/payload/binding hashes, elapsed time, bounded native-frame
counters and a fixed validation/transport decision reason. The directory stays
mode 0700; receipts are not app-visible or public grading evidence. Malformed
JSON and nonzero helper exits remain unknown while their bounded stdout is
retained. Five new offline audit tests passed; the combined audit/route/relay
checks passed 27 tests on Windows and Linux, including actual Unix custody.

This diagnostic follow-up is a **source change awaiting the next controlled
relay activation**. It was not active during the failed benchmark, does not
reconstruct the missing native response, and does not change its assessment.
Evidence caps, inference budgets and the durable unknown guard remain intact.
Bytes already discarded inside the helper cannot be recovered by this capture.
Preserve and reconcile the original uncertain request before authorizing any
fresh inference; restarting the observer does not clear that requirement.

### Subsequent read-only investigation

Call-owned native host log metadata later corroborated HTTP **200**, model
`gpt-6.1-sol`, medium reasoning and streamed answer notifications for the actual
failed compiler request. Its native thread was
`01a175a1-91bd-7a32-ac09-688c6b9a0618`, with turn
`01a175a1-92d1-7921-b8dc-3063edcb72b7`. Safe row metadata and body hashes are
retained in `codex-activation/host-log-diagnosis.json`; credential-bearing raw
log bodies were not exported. These post-hoc diagnostics do not replace the
original missing native receipt or change the original Harbor assessment.

Offline reproductions exposed two helper defects relevant to the uncertain
receipt: filling the raw capture buffer also prevents the recorded
`turn/interrupt` message from being sent, because capture runs before the
control write; and a completed answer can fit the raw wire limit yet exceed
the duplicated/escaped JSON envelope limit, losing its completion evidence.
A separate validator mismatch rejected the helper's original tool-refusal RPC
error replies. The failed run's exact trigger is still unproven. These defects
motivated the source fix below; the earlier short JSON smoke was insufficient.

### Wrapper fix on `ai4r_M1`

The current source fixes evidence-limit cancellation, duplicated receipt
serialization and tool-refusal validation. Offline regressions reproduce the
original failure modes with injected native processes. They cover a 600 KB
completed original answer, escape-heavy Unicode, more than 4096 small emitted
frames, capture overflow with and without an interrupted terminal, malformed
terminal proof, pre-dispatch admission, and invalid/incomplete receipts.

Independent Linux checks passed **84 tests**, including the actual Unix socket
and peer-credential path from helper output through relay custody/ledger to the
app client. These verify large completion, refused tools followed by a new
authorized fixture, and an unknown terminal that blocks later effects.
The broader Windows regression passed **151 tests**, with six platform-dependent
skips. All **349** pre-existing RSI file hashes and the original stopped relay's
ledger hash were verified unchanged after testing.

This is a **source fix, not a new live benchmark qualification**. The deployed
image and the original failed assessments above are unchanged. Build the
updated app and activate the matching relay source through the normal workflow
before testing a new deployment. Preserve the original stopped relay and its
unknown claim; no reconciliation, model inference or benchmark replay was
performed while implementing this fix. RSI files remain unchanged.

### Subsequent single paper-case live checkpoint

The fixed wrapper was deployed locally in WSL/Docker with the original
`case3-paper` sample and its unchanged PDF and protected criteria. Inference
used the existing host subscription, exact `gpt-6.1-sol` and medium reasoning;
Spark and Qwen were not used. The initial launch stopped before inference
because the operator prompt-byte cap was too low: its relay ledger remained
empty. That launch, profile, controller and assessment are retained separately.

After the operator-only policy correction above, a fresh controller launched
one actual paper trial with no automatic case/provider retries. Four distinct
governed compiler subnodes completed: `intent`, `intent.verifier`,
`requirements` and `requirements.verifier`. Each retained a valid version-2
receipt, exact observed model/effort, an actual completed native turn and
`full_original_trace:true`. Aggregate observed usage was **98,535 input tokens
and 8,084 output tokens**; monetary cost was unavailable. The wrapper therefore
has live evidence beyond the earlier arithmetic smoke.

The product still halted with **`plan_infeasible`** after compiler completion.
Its static plan failed `dependency_closure` for unknown accepted input keys in
hypothesis, builder and benchmark, and `resource_feasibility` for unavailable
`poc_workspace` and `baseline_resource`. Harbor recorded zero exceptions,
valid live evidence, **execution not completed** and scientific **not scored**.
This is not a passing paper task or full research-pipeline result. No further
model run or output repair followed that attempt.

App image:
`sha256:93946cd24fc30ac4adfa6a81c953202aee5854df1e8663dad359a34a0cb9c242`;
build:
`815d1a2f51fe8d93c3d175d3ad9e5572074e3d8e6e52bbdfea4d68bdd5947ec9`.
Campaign: `harbor-68d5e1ffe7e5b9b8b8b9d0c5`;
app run: `run:7db064a51b1347a4941140ea7e4788ba`.
The maintained workstation execution report and exact evidence paths are in
`harbor-deployment-20261025/codex-text-run/EXECUTION.md` and `RESULT.json`.
The corrected assessment/archive review copy contains 117 hash-verified files;
the original app ZIP contains 161 members. The earlier blocked launch remains
separate and visible.

Reconfiguration also exposed a general stopped-volume inspection issue:
SQLite databases with WAL-mode headers could not be queried on read-only
mounts. The host operator now copies bounded database/WAL/SHM snapshots to a
private helper tmpfs, checks source hashes and topology for consistency, and
queries the complete copied WAL view. It never ignores WAL with `immutable=1`,
modifies original database bytes or bypasses active-run/claim/lease checks.
All 48 Linux operator/deployment checks passed, including committed active
work in WAL, unreleased leases and missing/symlinked database refusal.

Final drainage confirmed zero active runs, unfinished claims or unreleased
leases. The new relay was stopped with four completed requests retained; the
earlier uncertain scientific ledger was hash-verified unchanged. All 349 RSI
file hashes matched. The app and runner remain installed in English on 5175;
later model use requires explicitly starting the corresponding private relay.

The deployed app image is
`sha256:f78c5d62ec0ce83657e736ead7279e48cbf78ceee2c6707ec0e9bceea4a7e15e`,
with build ID
`b9ebd8d338c0e3355a131e720ac38b74b8967d65656b805dae05b2af3ea2381a`.
The existing archive-capable runner image is
`sha256:6d6d938832594e5a2d9ff68e4e0243de3114d2890948feed9f76f4d04f5c21e6`.
Regression before this activation passed 131 tests, with three optional
environment skips; separate Linux boundary checks passed 50 tests. All 349 RSI
file hashes matched the pre-activation snapshot, and no RSI case was launched.

If WSL process startup reports service error `0x8007274c`, first reconcile
whether the original operation ran. A Linux working directory and a root entry
point immediately dropping to the original deployment UID through `runuser`
allowed this controller to continue without restarting WSL. A startup retry
does not authorize replay of an already submitted model or benchmark request.

The current ordinary live binding covers **`pipeline01-experiment` only**.
Other CC, verifier, routing, recovery and RSI tests still require their protected
launcher/projection bindings; selecting a case does not create that binding.
This integration changes the inference transport and its deployment wiring.
**RSI files and RSI behavior remain unchanged.**

### Isolated CC model choice and original trace custody

E3 execution owns a private run identity, separate from its canonical source
capture. Account model settings must therefore be frozen on the actual source
capture before its evaluation runtime is approved. Use the existing protected
`freeze_model_selection` operation with the authenticated account/source run and
`parent_run_id: null`; pass its original `selection_ref` to
`prepare_single_cc(..., account_model_selection_ref=...)`. The source must already
exist, and its exact public inputs and qualified intake must pass the complete
parent resource disposition before an executable slot is frozen.

The optional `evaluation-runtime.account_model_selection_ref` pins the original
account choice, deployment and endpoint metadata. The live protected model
context carries both that Ref and its exact runtime Ref. ModelSettingsOwner
checks runtime, request, private child, original subject, source run and account
ownership before choosing the immutable endpoint. It does not consult a changed
account preference or manufacture an ordinary product row for the private run.
An older runtime without this field retains its original default-route behavior;
selecting a local model in the UI alone is insufficient for such a runtime.

Native local trace packets now use the existing exact model-start/claim custody
writer for both ordinary and private execution. E3 observations retain their
request-owned captures; they do not append optional ordinary-run prompt-file
aliases that were never published into the private journal. The export contains
the original finite nonsecret selection/deployment/endpoint closure, and the
receiver independently validates it against the actual route. Build the app and
benchmark runner together when adopting these runtime/export fields.

The original qualified-input CC attempt reached a known failed, contained
framework model call on `codex-cli-default`, with `auth_failed` and no observed
effective model. Its original archive remains invalid because it references an
uncaptured ordinary-run file alias. Neither failure was rewritten or relabeled
as GPT-6.1-Sol inference. A fresh runtime now carries the frozen host selection;
the paired public input bytes remain identical to the completed corrected-input
plain Codex baseline. Actual run results belong in the separate retained pilot
report, not in claims inferred from configuration or offline tests.
