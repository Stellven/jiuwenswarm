# Native M1 deployment and verification

**Current integrated workflow:** [OPERATIONS.md](OPERATIONS.md) covers clean-checkout
setup, two image builds, local/SSH staging, commands, verified result return and
temporary expiry. Docker Compose is the default local entry point; the optional
`python deploy/m1/ai4r.py --help` launcher supports managed staging and SSH.
The local launch scripts now forward to that operator; they no longer use private
workstation scripts. Sections below retain native/advanced profile context and
historical command examples; use OPERATIONS for the current quick start.

For the sequential two-image testing path (`ai4r` + `benchmark-runner`) and the
existing final app on localhost5175, use [BENCHMARK_RUNNER.md](BENCHMARK_RUNNER.md).
It covers explicit host mounts, scoped credentials, CLI commands and guarded
recreation while retaining account/state volumes and collected files.
For the shortest Docker-only build and app launch, see the first section of
[OPERATIONS.md](OPERATIONS.md); it uses the same Compose file, app image and
runner image and keeps the app bound to `127.0.0.1:5175`. Local research mode
captures the authored local operator configuration in the existing app state
volume; no host config file is required. This capture is not science-resource
admission or qualification.

## Local web app: clone to launch

On Windows, open PowerShell and enter WSL:

```powershell
wsl -d Ubuntu -u root
```

With Git installed and Docker running and accessible from Ubuntu:

```bash
git clone --branch ai4r_M1 https://github.com/Stellven/jiuwenswarm.git
cd jiuwenswarm
docker info
bash deploy/m1/start-local.sh --build
```

Open the newest complete **Open JiuwenSwarm:** URL printed in the terminal in
Chrome or Edge. Include the `#research_bootstrap=...` fragment; keep the link
private and bookmark it for reuse. Open **Settings → Models**, click **Sign in with ChatGPT**, and enter
the displayed device code on the provider page. Use **Open secure sign-in** if
the browser blocks a popup.

When the account shows **Signed in**, type in the existing chat composer and send.
Ask follow-up questions in the same conversation. The local launcher enables
ordinary subscription chat without requiring research operator bindings or an
API key. Local chat requests GPT-6.1 Sol and checks the runtime-reported model
identity. If6.1 is unavailable, it reports an error and never substitutes an
older model. The packaged CLI is pinned to0.163.0 for this integration.

To discuss a document, select **Reference document**, upload it, check its row,
then type a question and send. Up to eight documents /100,000 extracted characters
can accompany a message. Repository ZIPs and datasets remain stored resources;
they cannot be selected as text-chat documents. Recent conversation context is
stored privately in the existing account volume. Responses appear when complete.

In **Settings → Agent**, choose a **Conversation Capsule**: General conversation,
Document Analyst (summary, evidence and limitations), or Research Brief (questions,
approach and next steps). The choice applies to the next message and is remembered
in this browser. These two text Capsules structure replies; they do not run tools
or represent a gate-accepted research pipeline. Account and Capsule controls live
in Settings; the chat page uses the existing composer and message timeline.

The launcher explicitly enables an automatically initialized **local input
workspace**. In the composer, choose the input type, upload a file, refresh the
saved list, and select or delete files. Text documents are UTF-8 `.txt`/`.md` or
PDFs with selectable text (`.markdown` is also accepted); repositories are ZIPs. Local uploads are limited to
20 MiB each. The upload control automatically converts filenames containing spaces
or non-Latin characters to safe storage names and shows the saved name. File bytes
are preserved. Saved files and account
state survive app restarts and image rebuilds in the existing Docker volumes.

Local input initialization creates storage only. It does not supply operator
policy, catalog admissions or model/deployment/runtime bindings, and does not
make governed research runs ready. Those execution requirements remain explicit.
The Docker launch opts into local input and chat with
`AI4R_LOCAL_WORKSPACE=1` and `AI4R_LOCAL_CHAT=1` on loopback only. Local
research config capture is an explicit Compose default for the M1 benchmark path.

For updates and restarts, from the same Ubuntu checkout:

```bash
git pull --ff-only
bash deploy/m1/start-local.sh --build
# Later starts without source changes:
bash deploy/m1/start-local.sh
# Stop the app (Ctrl+C only stops following logs):
docker stop ai4r-web-play-app-1
```

Preserve the Docker volumes to keep your files and account. On native Linux,
skip the PowerShell/WSL step. First-time builds require network access and may
take several minutes.

These commands run on the identified Linux Docker host from the repository root.
On this Windows workstation the observed development entry is `wsl -d Ubuntu -u root --exec docker`.
Docker Desktop installation alone does not qualify a daemon, ARM64 or DGX Spark.
Use a distinct `ai4r-…` project and job ID for each disposable target. Do not run
global Docker cleanup commands or remove saved account/state volumes.

The implementation extends the existing `jiuwenswarm-start`, `jiuwenswarm-init`,
web, CLI and TUI entry points. `workswarm` remains the native distribution;
the installed `jiuwenswarm[codex,tui]` compatibility wheel contains metadata only.

## Build and inspect

```sh
docker build --platform linux/amd64 -f deploy/m1/Dockerfile.app \
  --target production -t ai4r-m1-app:<candidate> .
docker image inspect ai4r-m1-app:<candidate>
```

The build uses pinned Python3.12, Node22, uv and the frozen dependency lock.
It builds fresh native and TUI wheels offline from the supplied code, compares
installed source bytes, and records both installed package closures in
`/usr/local/share/ai4r-build-identity.json` (internal schema2). A current source
tree and an older image are different candidates even if their tags match.

Use Buildx with an explicitly qualified builder to build a multiarchitecture
index for `linux/amd64,linux/arm64`. Select and record each actual platform
manifest. An ARM64 build or emulated run does not establish native GB10 results.
No registry push is part of these local commands.

## Start the native application

Set `AI4R_APP_IMAGE` to the exact selected image and `AI4R_OPERATOR_CONFIG` to
the approved, existing Linux file. Set `JIUWENSWARM_M1_ORIGIN` to the actual
private published origin, including its port; the default is
`http://127.0.0.1:5173`. The published bind defaults to loopback. The single
operator YAML must satisfy `research/operator_config.py`; policy, template,
profile and catalog references must identify their actual captured bytes.
The source documents and QA fixtures are not image inputs or runtime mounts.

```sh
export AI4R_JOB_ID=<unique-job-id>
docker compose -p ai4r-<unique-job-id> -f deploy/m1/compose.yaml up -d --no-build app
docker compose -p ai4r-<unique-job-id> -f deploy/m1/compose.yaml exec app jiuwenswarm-start --status
```

The root supervisor starts a fixed root executor broker and an application-owned
tmux session with AgentServer, Gateway and frontend panes. App state/accounts
use UID10001; generated work uses UID10002. The one-use browser bootstrap URL
is printed to launcher stdout. Treat that URL and native session tokens as
credentials; do not copy them into evidence, reports or source. Authenticate
through the native account flow in its dedicated application home.

An HTTP200 page and running panes establish liveness only. The authenticated
`GET /api/v1/readiness` must report the real missing prerequisites. Startup does
not admit arbitrary Capsules, manufacture policy/defaults, copy IDE credentials
or silently run a model. Without protected runtime inputs, readiness remains
blocked and attempted governed work is refused.

For operational execution, add `-f deploy/m1/compose.runtime.yaml` after the base
file. Supply its required existing protected locators and dedicated Builder
credential directory, and prepare the bounded cgroup branch described below.
Each locator contains exactly `{"binding_ref":{"id":"…","sha256":"…"}}`;
it references already captured source records in this target's own store.
`bootstrap_gateway.py`, `executor_bootstrap.py` and `builder_launcher.py` define
the closed internal bindings. No credential bytes belong in a captured binding.
The science binding must match the independently verified installed build,
approved environment/approval records and explicit resource limits. The Builder
binding additionally requires actual pinned CLI tool-sandbox qualification and
current dedicated budget/revocation evidence. Missing evidence is unavailable.

After the actual approved source bindings exist, explicitly install the fixed
catalog as the configured OS operator:

```sh
docker compose -p ai4r-<unique-job-id> -f deploy/m1/compose.yaml \
  -f deploy/m1/compose.runtime.yaml exec --user 10001:10001 app jiuwenswarm-init --json
```

The receipt can record initialization while runtime readiness remains false.
Ordinary startup only resolves existing admissions; it does not repeat this
administrative action. Native workspace/authentication state stays in the
target's dedicated volumes.

## Optional processes and custody

The base file contains only the app. Optional configuration never prevents a
base-only launch merely because an optional environment variable is absent.

| File | Scope and custody |
| --- | --- |
| `compose.routing.yaml` | Explicit app overlay. A separate UID10011 selector runs **inside the app container** over `/run/ai4r-router/router.sock`; the hot path imports only the core port. Router failure leaves fixed Codex available. It gets a scrubbed environment and exact public export, with no provider client/account/main store/hidden fixtures. |
| `compose.sidecar.yaml` | Optional benchmark/referee job profiles. Runner UID11001 receives a job grant and job-scoped token. Offline referee UID11002 receives protected labels and no product token/job grant. Referee scores/reports have separate job-owned writable roots, mounted read-only for the runner. Neither receives a Docker socket or direct writable product store. |
| `compose.rsi.yaml` | Independently launched workbench/custodian/worker-broker topology, with no app service or app dependency. Controller UID12001 has its own native account/state. Custodian UID12002 owns hidden fixtures, exposure ledger and signing key. Fixed root worker broker launches UID12003 with its own bounded cgroup branch and receives only approved function bodies/profiles and role-specific per-call inputs. |

Routing uses a root-owned read-only selector config and a captured authority
locator. The fixed export is `/run/ai4r-routing/public`, owned10001:13100 mode2750;
the separate audit root is `/var/lib/ai4r-router`, owned10011:13100 mode2750.
Shared immutable files are0640. The authority binding must name these same roots
and the protected current status path `/etc/ai4r/deployment-status.json`.
Only actual qualified/current enabled deployments may reach the core provider.
The API credential environment is mounted into the app's protected environment;
the selector launcher removes it before creating the selector process.

RSI requires pre-created Linux directories with exact role ownership. Public
exports and custody-request roots are12001:13000 mode2750 with files0640;
custodian mounts them read-only. Controller private state/account/work roots
are UID12001 mode0700; custody/fixtures/key are UID12002 mode0700/0600.
Worker output root is root-owned0711. Worker socket parents are root-owned0710
with the corresponding controller/custodian group; only peer UID12001 or12002
can use its finite port. No signing key, full fixture store or account is mounted
in the broker. Role-specific input roots contain only the approved helper inputs.
Service configs must exactly match the fixed mount paths in the Compose file.
An operator must supply actual session grants, calibrated fixtures and native
account resources; directory presence alone cannot establish qualification.

The public signed-result inbox is separately owned12002:13000 mode2750 with
immutable files0640. Only the custodian mounts it writable. Add
`compose.rsi-inbox.yaml` to the app for read-only capture of that public closure;
the app receives group13000 only with that explicit overlay. The inbox contains
no private fixture/key/account records. Capturing a signed candidate does not
admit or activate it: canonical library admission, exact protected key and
dependency checks remain required. Empty/corrupt/unavailable inboxes cannot
become product startup dependencies.

The sidecar defaults to `--help`. Use a job-scoped run command after freezing
the actual campaign/schedule/variants and inventories, for example:

```sh
docker compose -p ai4r-<job-id> -f deploy/m1/compose.yaml \
  -f deploy/m1/compose.sidecar.yaml --profile benchmark run --rm --no-deps \
  sidecar run --campaign <frozen-id> --case <capsule|verifier|routing|rsi> --variant <frozen-id>
```

The frozen job must name an actually reachable private target and exact token
path `/run/ai4r-qa/token`. Do not substitute an unqualified endpoint or weaken the
native Origin/Host checks. RSI jobs additionally need the separately authorized
job socket mounted read-only and the exact workbench peer UID/job grant.
Add `compose.qa-rsi.yaml` after the sidecar overlay for that explicit grant.
It adds only the job socket and its traversal group; the controller's exact peer
allowlist must separately authorize runner UID11001. Custody and worker ports
remain absent from the benchmark runner.

`compose.sidecar.verify.yaml` and `compose.rsi.verify.yaml` are explicit test
observer overlays. They select the independently prepared verification image
and mount visible code/tests read-only, preserving each role's identity and
existing custody/network limits. Supply an existing role-owned evidence
directory. Production benchmark and RSI images contain no pytest suite;
observer execution never replaces the separately identified live service or
supplies missing calibration, credentials or hidden fixtures.

## Bounded executor delegation and focused checks

Prepare a **new** branch on the approved Linux host, with explicit limits:

```sh
python deploy/m1/host_cgroup.py prepare --job-id <job-id> \
  --memory-mb <approved-parent-limit> --pids-max <approved-parent-limit> \
  --manifest <owned-evidence-dir>/delegation.json --hold
```

Keep that host owner alive until its jobs have stopped. Never mount this helper,
the host-root cgroup filesystem or a Docker socket into generated work. Set
`AI4R_EXECUTOR_CGROUP_HOST` to the exact recorded branch and record its inode.
`compose.executor-verify.yaml` mounts only that branch, uses `cgroup: host` for
live PID migration, the narrow listed capabilities and the checked seccomp
profile. It grants no SYS_ADMIN or privileged container. The generated child
still enters separate user/mount/PID/network namespaces and UID10002.

```sh
export AI4R_EVIDENCE_DIR=<existing-owned-evidence-dir>
docker compose -p ai4r-verify-<job-id> -f deploy/m1/compose.yaml \
  -f deploy/m1/compose.verify.yaml run --rm --no-deps app \
  -m pytest tests/unit_tests/research -q --junitxml=/evidence/junit.xml
docker compose -p ai4r-verify-<kernel-job-id> -f deploy/m1/compose.yaml \
  -f deploy/m1/compose.verify.yaml -f deploy/m1/compose.executor-verify.yaml \
  run --rm --no-deps app -m pytest tests/integration/research/test_executor.py \
  tests/integration/research/test_environment_provisioning.py -q \
  --junitxml=/evidence/kernel-junit.xml
```

The verify target has visible tests, not private oracle assets. Its default
network is none; tests of an actual external/private target need an explicitly
owned controller network override and protected controller-only inputs.
Focused checks disable incidental repository-wide coverage writes. A required
coverage check must explicitly choose its owned output paths.

Raw JUnit/logs and exact code/test/image/fixture/environment pins must be retained.
Zero collected cases, skipped mandatory work, mocks, missing resources and stale
evidence do not establish acceptance. The native TASK plans own the complete V
procedures and assertion populations; these convenient focused commands are
not replacements. Use `scripts/research_candidate.py` for exact uncommitted
inputs and `scripts/research_reports.py` for the five derived lowercase reports.

## Conditional Screening text trials

Add `-f deploy/m1/compose.rsi.text.yaml` after the independent RSI file only
when the approved conditional Target2 resources exist. The overlay requires
three existing Linux host paths: `AI4R_RSI_TRIAL_BINDING_FILE` (root-owned
read-only locator containing exactly `{"binding_ref": Ref}`),
`AI4R_RSI_TRIAL_IPC` (UID12001:GID12002 mode2750, trial.sock0660), and
`AI4R_RSI_TRIAL_INPUT_ROOT` (UID12002:GID13000 mode2750). The controller reads
only published legitimate per-call inputs; the custodian writes those inputs
and alone retains private captures/labels. The distinct trial socket accepts
only the custodian UID12002. App, sidecar and worker have neither mount.

The exact captured runtime/profile must supply original admitted-parent
contract/check-plan Refs and the separate child trial owner. Current private
IF011r3/IF012r3 pair external Brief/candidate inputs while deriving each
subject's authorized work rubric from its own body. Historical v1 records keep
their original interpretation. Explicit reservation version3 adds only the
finite signed score/warmup/paired/batch slots; it retains the same charged
action, source5/7 schedule and cross-version score replay protection. An absent approved profile, parent/check
qualification, separate model account, custody, fixture registration or measured
headroom blocks this conditional path; adding the overlay grants no quality or
admission/activation result. No operational resource is created by these docs.

## Human Library operations and admission tests

The finite Library command starts as the container OS operator and permanently
drops to the existing app identity before state writes. It consumes an exact
captured action Ref; it cannot accept a replacement declaration, execution
command or policy from command-line flags. Inspect, associate-checks, admit,
admit-rsi and standing are separate actions. Admission does not activate an RSI
candidate, and sandbox activation does not promote it to live plans.

The authored Planner release is `m1-2`. It preserves malformed returned proposal
text as original candidate evidence for protected rejection and the bounded
linked-attempt flow. Upgrading the image does not admit this release: its exact
new declaration/body/checking pins still require the existing protected checking,
admission and standing operations. Existing admissions and frozen pins are not
overwritten.

```sh
docker compose -p <RUN_PROJECT> -f deploy/m1/compose.yaml exec --user 0 app \
  python -m jiuwenswarm.research.library_operator admit \
  --request-ref "$CAPTURED_ADMISSION_ACTION_REF_JSON"
```

For declarations that actually supply self-tests, the protected bootstrap
binding must name an existing `admission_execution_profile_ref`. IF013 binds
the original authenticated action, exact candidate/test bytes, configuration
and actual admission memory before the root broker can launch work. Its
supported pure Python fixture/command adapters run a separate candidate and
driver under the common confined kernel; printed pass text is insufficient.
Missing profiles block the affected test. Model and other carrier adapters
remain unavailable unless implemented and independently qualified; no recorded
model transcript or normal admitted invocation is substituted. Shipped
canonical declarations currently supply no self-tests; that fact proves no
model quality or checking calibration.

Independent checking assets use the separate, explicit calibration operation.
Protected startup must already name the exact captured `calibration_runtime_ref`,
approved challenge profile and case contexts. This is independent of Capsule
eligibility; it creates no product run, Capsule admission or standing.

```sh
docker compose -p <RUN_PROJECT> -f deploy/m1/compose.yaml exec --user 0 app \
  python -m jiuwenswarm.research.library_operator calibrate-checks \
  --request-ref "$CAPTURED_CALIBRATION_ACTION_REF_JSON"
```

The request's original deadline includes preparation, calls and final capture.
Each semantic case gets one payload-bound governed call. Unknown or interrupted
attempts retain their claims and evidence; repeating an action never resends
them. Missing profiles, native account or host contexts produce an explicit
blocked result. Only independent validation can publish the separate checking
asset admissions; raw calibration material cannot become product/RSI inputs.

Operational RSI also requires current independent qualification of all thirteen
security cases, including durable security halts and actual containment of any
started effects. Its exact producer scope must be observed independently.
That positive scope-observer composition and complete security suite remain
unbuilt in this checkpoint. Defaults therefore block new operational RSI,
RSI-child admission and activation. Inspection, containment and revocation stay
available. A job grant, package signature or successful component test does not
supply this qualification.

Clean offline installation remains incomplete. The current image's three
candidate/TUI/alias wheels lack the complete dependency/build closure; the
original metadata also names pinned Git dependencies. The app build now puts
compiled TUI assets and the locked production npm tree into the native wheel
and audits its exact metadata, RECORD and generated bytes. The resulting
`/usr/local/share/ai4r-wheel-assets.json` covers those delivered wheels only.
The full runtime/build-tool/VCS input producer and complete clean-install
population remain unfinished. Installed-image closure and successful startup
are separate observations and do not establish that install.

## Inspection, stopping and resuming

`jiuwenswarm-start --attach gateway` attaches only the owned pane; `--detach`
detaches from that instance. `--stop` requests bounded shutdown of the owned
native session and broker. Preserve stdout bootstrap credentials privately;
native raw service logs live under the state volume's `native/logs/`.

Before shutdown, save candidate/source/IF/native revisions, expanded commands,
image/platform identities, raw failures and exact next commands in the owning
`tasks.md`. Stop only the named project's test containers, then send `stop` to
the held delegation helper. Cleanup refuses populated/unrecorded/changed groups.
Inspect those findings; never broaden deletion to make cleanup pass. Preserve
account/state/artifact/evidence volumes for restart. An interrupted governed
attempt remains interrupted/paused and must not be automatically replayed.


## Submit and read research through the native clients

After the operator initializes the application and its required runtime, connect
the CLI from a supported Linux/POSIX environment. Use a fresh one-use bootstrap
URL from the private launcher console when prompted; the prompt does not echo it.
The session file stores the scoped credential and initialized server defaults
with owner-only permissions.

```sh
jiuwenswarm research connect --origin http://<private-host>:5173 \
  --session-file ./research-session.json
jiuwenswarm research --session-file ./research-session.json doctor
jiuwenswarm research --session-file ./research-session.json submit \
  --prompt-file question.md --document paper.pdf --repository baseline.zip \
  --dataset validation.csv --wait
```

Each attachment option may be repeated. Documents support TXT, Markdown and
text-layer PDF; repositories use ZIP archives. The server performs canonical
document extraction and input qualification. A saved initialized session supplies
workspace, configuration, plan selection and profile defaults; explicit supported
options remain available. Inspection and standalone uploads remain useful while
execution prerequisites are unavailable.

```sh
jiuwenswarm research --session-file ./research-session.json uploads
jiuwenswarm research --session-file ./research-session.json status <run-id>
jiuwenswarm research --session-file ./research-session.json export <run-id> \
  --output ./run_export.zip
```

An interrupted attachment submission retains confirmed upload IDs and, when
available, the qualified intake Ref in its structured error output. Inspect the
upload list before repeating an uncertain upload. Resume with the original
client request ID and the returned intake Ref, or reuse the returned upload IDs;
an existing intake cannot be modified with new attachments. Ctrl-C stops local
waiting and does not cancel server work.

In the browser research panel, **Inspect evidence** opens the original authorized
files. Research Brief and interpreted-request files have readable sections.
Recorded experiment measurements and scientific evaluations have comparison
tables, including explicit unavailable measurements and their recorded reasons.
The run controls show the original current or last stage and execution reasons.
**View source** and expandable provenance retain the underlying content. Accepted,
candidate and captured-evidence labels reflect the run's recorded standing.
**Download original files** retrieves the authorized ZIP.

Each fresh ordinary submission captures its own immutable request and extracted
document list. Local-document Search uses that run's captured papers. Scientific
execution resolves those same inputs against the operator's installed resource
mapping; uploads do not grant new compute, network or model permissions. Existing
finite evaluation and RSI snapshots retain their original inputs.

For an approved RSI job, the existing `ai4r-rsi session inspect --job-ref
'<original-job-ref-json>'` and `ai4r-rsi session export --job-ref
'<original-job-ref-json>'` operations retain interrupted history after the
protected service restarts. When the original signed result was already captured,
recovery returns those exact bytes without rerunning proposals or evaluations.
Otherwise, closing a counted started attempt requires the original inputs and
actual custody halt/query evidence. Missing evidence remains unresolved.
Terminal history does not establish that native work stopped: uncertain
containment keeps the lease blocked and stop reports `outcome_unknown`.

## Reusable local login and ChatGPT sign-in (C011/C012)

Set `AI4R_REUSABLE_LOGIN=1` before Compose startup for a reusable, bookmarkable login link on a literal loopback origin only. Default remains one-use. The private saved challenge survives restarts for the exact same origin and principal; logout/revocation or identity changes retire it. Keep the complete fragment URL private. Browser sessions are independently scoped; research readiness remains separate.

In protected M1, Use ChatGPT login opens the native provider device-authorization page and displays the code to enter there. This avoids container-local OAuth callback ports. A popup-blocked browser can use Open secure sign-in. The user completes authorization in their browser; provider credentials remain in the app-owned account volume. Account sign-in is available while research operator configuration is unavailable, and does not authorize research execution.

Local Linux/WSL convenience entry: `bash deploy/m1/start-local.sh`. It builds a missing image, preserves configured files and data, enables the reusable local login and follows startup output without opening VS Code's browser. After a source update, use `bash deploy/m1/start-local.sh --build`. The initial empty config is inspection-only, not a configured research runtime.
