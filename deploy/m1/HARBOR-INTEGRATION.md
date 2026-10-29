# Harbor integration with AI4Research deployment

Maintained deployment guide. Updated October 26, 2026 (America/Toronto).
Standard application runs use Docker Compose as described in
[OPERATIONS.md](OPERATIONS.md); Harbor is optional benchmark infrastructure.
This integration retains upstream M1 Builder/runtime changes. The workstation
results below predate the merge candidate: build new images and qualify exact
runtime/asset bindings before claiming results on the integrated code. The
opt-in evidence-aware verifier mode is not supported by E2 replay yet.
For the installed browse-only local results UI, see
[HARBOR-VIEWER.md](HARBOR-VIEWER.md).
For the latest serial launch-readiness checks of CC, verifier and pipeline cases,
excluding RSI and MR, see
[serial validation status](../../benchmarks/harbor_suite/SERIAL-VALIDATION-STATUS.md).
The latest checkpoint restored Docker and host inference and passed one variant
from each CC case. Verifier and pipeline qualification gaps remain explicit.
Harbor controls benchmark trials and offline grading. The existing deployment
operator controls application images, Docker/SSH transport, authentication,
persistent state and verified campaign retrieval. The existing research runner
retains dispatch, reconciliation, cancellation and collection authority.

## Latest workstation execution checkpoint

Two individual development variants passed on GPT-6.1-Sol/medium:
`cc01-transfer / evaluate-boundary` and `cc02-binding / valid-pinned`.
The latter was collected from the original completed request after a proxy
failure; its failed first observer is retained. No model invocation was repeated
to recover that result. The matched plain-Codex evaluation arm passed its format
checks but marked complete supplied measurements incomplete. This single pair
does not establish general improvement. Other cases retain their documented
interface/resource blockers, and formal M1 acceptance is not established.

The final workstation app is `sha256:f31901c0b25c0856399b17c56bc50f9971d6bc86a7e07e00d57418cd0d7ab9ba`;
the matching receiver is `sha256:5bbdf34eda2beedaf0e8e9c05b70536cb6af78171b105cd6eb08b7c92c0c7a48`.
Build identity, frozen sources and operator profile snapshots are retained under
`D:/Codex Development Runs/harbor-deployment-20261025/final-app-update-20261026/`.
Rebuild for another platform and pin its actual image IDs. The current ordinary
runner credential is deliberately marked for native refresh before a new campaign.

Keep Windows preparation and native Codex execution under the same operator
identity. Windows Python can create owner-only directories whose sandbox identity
differs from the WSL/native operator; those preparations may be unreadable across
runtimes. Preserve an unlaunched failed preparation and create a fresh one under
the proper identity. Use the persistent WSL environment, not the removed
`/tmp/ai4r-harbor-pilot-20261025` environment. Its verified current interpreter is
`/mnt/d/Codex Development Runs/.harbor-pilot-runtime/linux-venv/bin/python`.

For uncertain model outcomes, use the privileged, append-only procedure in
[LOCAL-MODEL-RECOVERY.md](LOCAL-MODEL-RECOVERY.md). Historical unknowns stay
unknown; acknowledgement authorizes distinct new work after local containment
observations and explicit acceptance of unknown provider status. The same ID
is never replayed. Run the protected no-inference transport probe before a new
bounded qualification call, then verify actual model/effort and native terminal.

Evaluation requests have a finite 660-second proxy window for the versioned
authenticated POST paths; native worker budgets are unchanged. Original E2/E3
ZIPs now stream in bounded chunks. Server errors are ambiguous delivery and
trigger same-request reconciliation, never another POST. For a completed E3
whose observer already wrote an immutable failed record, collect a fresh
read-only generation with the matching receiver:

```sh
python -m jiuwenswarm.research_sidecar.evaluation_collection \
  --config /control/collection.json --credential-file /run/ai4r-cc/token
```

Its protected configuration pins the original request, scheduled row, run record
and durable ledger/WAL bytes. It permits only GET, validates the complete original
export and response, and preserves the old files. Publish its new observation
separately; collection timestamps do not replace missing execution timings.
Do not count two observations of one request as independent scientific trials.
The original failed Harbor job and guard remain preserved.

When the export contract changes, rebuild app and receiver together. Finite E3
exports now include original typed library snapshot/profile records and validate
their exact source pin. Earlier exports remain readable; CC02 cannot acquire a
missing snapshot by synthesizing one. The suite reward called `baseline_success`
checks requested-model attribution plus correctness; a plain-Codex comparison
requires its separate matched job.

## Separate the three hosts

| Role | Required runtime | Responsibility |
| --- | --- | --- |
| Harbor controller | Linux/WSL Python with Harbor 0.24.0 and working Linux Docker | Task containers, isolated graders, private labels and reports |
| Application host | Existing AI4R Docker deployment and authenticated runner | Governed research execution and authoritative artifacts |
| Inference host | An already running, qualified model endpoint | Model inference; Docker is optional here |

These roles can share a machine or use different machines. An ARM64 inference
host does not require an ARM64 Harbor controller image. Application images must
match the application host's architecture.

For the current Spark arrangement, use workstation Docker for Harbor and the
application, and Spark's existing native Qwen server for inference. Spark does
not need Docker in that arrangement. Its loopback-only endpoint needs an
authorized private transport reachable from the application model adapter.
Connecting a catalog endpoint alone does not configure the product's model
selection, qualify its output, or complete missing module bindings.

The application UI uses **127.0.0.1:5175** and the browse-only AI4R Bench Hub
uses **127.0.0.2:5175**. Both stay on loopback and the same permitted port.
Existing model
service ports belong to their inference host. Do not automatically expose them
on the workstation or change remote service binds.

## Repository entry points

```sh
python deploy/m1/ai4r.py --profile /work/operator.json harbor prepare --help
python deploy/m1/ai4r.py --profile /work/operator.json harbor doctor --workspace /work/control
python deploy/m1/ai4r.py --profile /work/operator.json harbor stage --workspace /work/control
python deploy/m1/ai4r.py --profile /work/operator.json harbor run --workspace /work/control
```

`prepare` creates an immutable local control workspace without contacting the
target. `stage` transfers only public research input files and exact per-trial
runner cases through the existing operator. `doctor` checks the Harbor runtime,
local Docker, target access, architecture and, for live mode, authenticated
runner readiness. `run` launches one serial Harbor job with automatic retries
disabled. Each explicit launch gets a separate result directory.

Run Harbor commands from one consistent path namespace. On Windows, use the
selected WSL distribution for the Harbor/Docker runtime and `/mnt/...` paths.
The workstation setup/image-transfer commands can also run from Windows Python,
but paths in a prepared Harbor workspace belong to its Harbor controller.
Prefer native Linux storage (for example `/home/USER/harbor-control`) for bundles,
jobs and verified snapshots. Full bundles contain thousands of pinned files;
repeated custody checks across `/mnt/c` or `/mnt/d` are substantially slower.

The controller Python must contain Harbor 0.24.0, httpx and jsonschema, and run
from this checkout. Install runtime dependencies deliberately in a dedicated
environment; the operator does not install host services or dependencies.

## Prepare a hardware-specific deployment

Follow [OPERATIONS.md](OPERATIONS.md) for the normal setup/build/up/authentication
workflow. Select the actual application platform explicitly. For example:

```sh
python deploy/m1/ai4r.py --profile /work/spark.json setup \
  --ssh user2@100.105.127.48 --platform linux/arm64 \
  --project ai4r-harbor-suite --output /home/user2/ai4r-harbor-results
python deploy/m1/ai4r.py --profile /work/spark.json doctor
```

Use `linux/amd64` for an AMD64 application host. For local application Docker,
omit `--ssh`; select the existing Docker context or explicit WSL target using
the operator options. Use separate profiles/projects for different deployments.
Do not copy another operator's deployment ID, image IDs or credential metadata.

These Spark commands describe deploying the application to Spark. That path
requires Docker access there. It is optional when Spark serves only inference.
The current `user2` account has no Docker socket access, so application-container
deployment on Spark is blocked; no sudo or Docker permission changes were made.

## Freeze the benchmark bundle and check wiring

Use the suite generator on the Harbor controller:

```sh
python -m benchmarks.harbor_suite.prepare \
  --destination /work/bundle --profile smoke --case pipeline01-experiment \
  --python-image python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258
python deploy/m1/ai4r.py --profile /work/operator.json harbor prepare \
  --bundle /work/bundle --workspace /work/control-preflight \
  --mode preflight --case pipeline01-experiment
python deploy/m1/ai4r.py --profile /work/operator.json harbor doctor \
  --workspace /work/control-preflight
python deploy/m1/ai4r.py --profile /work/operator.json harbor run \
  --workspace /work/control-preflight
```

Preflight runs task/verification containers locally and dispatches no product
requests. A target deployment can still be unavailable: `doctor` separates the
preflight controller's `ready` status from `deployment_ready` and lists blockers.
Expected assessments are `unavailable`, with null correctness and zero rewards.

`--case` may be repeated; omission selects all frozen tasks. A smoke bundle has
one task per variant. A campaign bundle has three per variant. Full campaigns
also retain stricter case-specific calibration and qualification requirements.
The generator also accepts repeatable `--case` to freeze only selected authored
cases; omitting it retains the complete ten-case suite.

Reference JSON documents use the app's strict UTF-8 document extractor, retaining
their original bytes. Non-ZIP repository inputs are transported as deterministic
single-file ZIPs because the product's repository intake accepts ZIPs only.
The archive member retains the authored logical path and exact source bytes;
the task's `input_transform` binds source and archive hashes/sizes. Runner input
pins identify the actual uploaded ZIP. Source files remain separately frozen
in the public manifest. Existing ZIPs, authored prompts, data and private grading
checks are unchanged; packaging does not execute source code or relax upload
validation. Preserve failed preparation attempts before changing a bundle.

For an operator using Windows SSH credentials from WSL, preparation accepts an
explicit executable, for example:

```sh
python deploy/m1/ai4r.py --profile /mnt/d/work/operator.json harbor prepare \
  --bundle /work/bundle --workspace /work/control-preflight \
  --ssh-executable /mnt/c/Windows/System32/OpenSSH/ssh.exe
```

This uses the existing verified Windows SSH identity. Transfers use the bounded
SSH-stdin fallback because Windows SCP may not understand WSL source paths.
No private key is copied, and host-key checking remains enabled. Native Linux
normally uses its existing `ssh` executable and authorized identity.

## Stage and run a qualified application deployment

First build/select matching app and runner images, start the app, complete model
authentication and refresh its scoped runner credential through the existing
operator. `build_id` and actual image IDs must exist in the operator profile
before preparing a live workspace.

For bootstrapping `up`, the preflight workspace's `public/selected.json` and
`public/inputs/` are public-only staging roots. Use the existing `up --cases`
and `--inputs` options with those paths and the qualified image pair. Never pass
the protected benchmark bundle itself as an input root.

```sh
python deploy/m1/ai4r.py --profile /work/operator.json harbor prepare \
  --bundle /work/bundle --workspace /work/control-live \
  --mode live --case pipeline01-experiment
python deploy/m1/ai4r.py --profile /work/operator.json harbor stage \
  --workspace /work/control-live
python deploy/m1/ai4r.py --profile /work/operator.json start --refresh-credential
python deploy/m1/ai4r.py --profile /work/operator.json harbor doctor \
  --workspace /work/control-live
python deploy/m1/ai4r.py --profile /work/operator.json harbor run \
  --workspace /work/control-live
```

Starting after staging adopts the selected input mount. Images/build, target,
source code, public inputs and runner case hashes are frozen. A changed target,
image/build, source implementation or input selection requires a new workspace.
The old workspace and results are preserved.

The ordinary bridge supports `pipeline01-experiment`, subject to scientific
executor qualification. Finite prepared E3 bindings now also support selected
CC variants. Verifier, routing, RSI and recovery faults still require their
supported protected launcher/projection bindings. Selecting them does not turn
an ordinary prompt into an isolated module test.

Finite `single_cc` preparation is now implemented separately for tool-free,
network-free admitted subjects. The `cc01-transfer / screen-missing` pilot has
been attempted against the installed `research.screening` `m1-4` implementation.
Its final host-relay request has an unknown outcome and is not scientifically
scored. This does not activate the other
module or fault cases. See the finite preparation and paired comparison notes
below.

## Model configuration and Dockerless inference

Changing `--expected-model` in bundle preparation changes the expected identity
used for attribution. It does not select or configure the application's model.
Use the product's supported account/operator model configuration and frozen
deployment/profile records, then verify the actual effective model in exports.
Keep local-model experiments separate from the GPT-6.1-Sol baseline.

The account model-settings interface now supports operator-approved local
endpoints through a private authenticated SSH relay. An installed `local-*`
choice needs no API key. The operator catalog pins the backend, exact model,
revision and limits; the account selection and catalog hash are frozen into the
run. The existing cloud provider retains its HTTPS and credential requirements.
See [LOCAL-MODEL-INTERFACE.md](LOCAL-MODEL-INTERFACE.md) for the portable catalog,
app-only mounts, explicit activation commands, evidence and recovery contract.
The interface was built offline; live model qualification remains pending.

For the temporary route using an existing native host Codex ChatGPT login, see
[HOST-CODEX-INTEGRATION.md](HOST-CODEX-INTEGRATION.md). It documents the separate
`host-codex-app-server` catalog, exact GPT-6.1-Sol/medium identity gate, Windows
through WSL execution, credential custody, original native evidence and current
qualification checkpoint. That route preserves the ordinary live binding's
`pipeline01-experiment` scope; it does not activate RSI module tests.

Keep the target hardware's verified model inventory in a private operator
handoff outside the product repository.
The existing vLLM `Qwen3.8-27B-NVFP4` endpoint is host-local on port 8000; the
Ollama/gateway route is a different model. Host `127.0.0.1` is not a Docker
container's loopback address. Private SSH connectivity, endpoint authorization,
context/output limits and output validity need separate checks before an AI4R
local-model benchmark can be claimed. A direct endpoint smoke test is not an
end-to-end AI4R case result.

The stdlib [inference probe](../../benchmarks/harbor_suite/inference_probe.py)
can run natively on an authorized inference host over SSH. Its default mode
only reads the catalog. `--generate` explicitly enables two sequential,
256-output-token JSON smoke requests, without retries, redirects or environment
proxies. It stops after an uncertain generation outcome. Private credentials,
if required, are referenced by a local protected token file and never recorded.

On October 25, the existing Spark vLLM server answered both the plain-prompt JSON
and strict native JSON-schema probes with HTTP 200 and the expected small JSON
object. Responses identified `Qwen3.8-27B-NVFP4` and ended with `stop`. No Docker,
service changes or model downloads were used on Spark. This establishes bounded
native inference and those two format checks; it does not establish app model
selection, scientific execution, isolated module coverage or per-call GPU usage.

## Artifact custody and recovery

Private oracles, criteria, host profiles and SSH configuration stay on the Harbor
controller. Only `control/public/` is staged. The app credential stays in the
existing deployment runner's private Docker volume; no credential is exported
to Harbor task/verification containers or sent in command arguments.

Each trial uses the existing runner CLI inside that container. Raw campaigns
remain in the deployment's output root. The existing hash/size-verified fetch
path saves immutable generations under `control/snapshots/`; their original
runner views populate `control/evidence/`. Harbor retains assessments under
`control/jobs/<job>/.../verifier/`. Source artifacts are never executed by graders.

If SSH observation is interrupted, the remote operation may still be active.
The durable single-active pointer blocks later dispatch. Recovery reconciles
the same remote campaign, including when no first snapshot was fetched. It
does not resubmit a request whose delivery is uncertain. Cancellation uses the
existing runner's cancel operation; terminating an SSH observer is not proof of
remote containment. Never delete active pointers to force a new run.

Use `ai4r.py ... runner status/resume/cancel --campaign-dir /results/CAMPAIGN`
for explicit diagnosis, and the existing `fetch` command for independent
verified retrieval. Keep one immutable Harbor job per report; do not combine
repeat IDs from different launches. Archive retained data before deliberate
cleanup. The operator's TTL does not automatically delete Harbor workspaces.

## Current validation and remaining deployment work

The integration is checked with focused operator/runner/Harbor custody and
recovery tests. Model-free Docker preflight exercises actual Harbor lifecycle;
neither unit tests nor preflight establish research or GPU acceptance.

The October 25 integration checkpoint passed **94 focused tests**, with two
optional environment-dependent checks skipped. The new `ai4r.py harbor`
prepare/doctor/run path completed three workstation Docker preflight trials
with zero Harbor exceptions, three expected unavailable assessments and no
product dispatch. The Windows-OpenSSH-from-WSL transport was exercised against
Spark's owned operator configuration. Native Qwen generation was separately
verified by the two bounded probes described above. Live remote application
dispatch, cancellation and snapshot recovery have unit coverage but were not
demonstrated on Spark because its Docker application runtime is unavailable.

An isolated operator profile was initialized for Spark's ARM64 host at
`/home/user2/.local/share/ai4r/ai4r-harbor-suite`, with output
`/home/user2/ai4r-harbor-results`. No app/model service was started or changed.
Readiness confirmed Docker access denial for `user2`, only the default Docker
context, and no `/run/user/1002/docker.sock`. Use the Dockerless inference
arrangement for this hardware until an authorized application runtime is ready.
The local-endpoint product binding is implemented with offline fixture and
Linux RPC checks; it awaits live qualification after Qwen is reserved. Protected
module/fault interfaces remain separate work; no passing full-suite claim is made.

### Later local-Qwen activation

The subsequently authorized workstation-app/Spark-inference checkpoint is
recorded in [LOCAL-MODEL-INTERFACE.md](LOCAL-MODEL-INTERFACE.md#subsequent-authorized-live-checkpoint).
Transport and eight real public uploads qualified. The three pipeline variants
launched but did not pass: the first compiler inference exceeded its protected
120-second subnode/binding allowance, and the relay blocked further inference
after the uncertain outcome. The existing node's 600-second total allowance is
not permission to exceed that subnode limit. Benchmark budgets and oracles
remain unchanged.

Generated runner cases now set `collection_mode: "archive"` so even small
collections retain the original authorized export ZIP and its Ref inventory.
Default `auto` preserves the older runner behavior for other case files. This
transport change uses existing hash/member/size and collection-confirmation
checks; no original Refs are reconstructed from filenames or payloads. The
actual interrupted export qualified the archive join separately, without a new
model call or rewriting an old assessment. The new runner is deployed; its
model-free Harbor checkpoint completed three expected unavailable assessments
and zero exceptions. Final software regression passed 217 tests and 20 subtests
(five environment-dependent skips).

The user requested RSI files stay unchanged. All 349 matching source/artifact
files in this checkout retained their original hashes; no RSI case was launched.
The local relay is stopped after confirmed drainage, with its unknown ledger
preserved. Spark services, model weights and remote RSI work were not changed.
The compiler-time limit and late interrupted native-trace publication remain
explicit qualification limitations; a passing ten-case suite is not claimed.

## Finite CC preparation and paired comparisons

Use `jiuwenswarm.research.evaluation_preparation` from the protected operator,
not a public request. `publish_frozen_inputs` resolves a finite dependency DAG
of public Ref aliases, verifies authored byte digests and retains original and
adapted Ref receipts. Explicit schema migrations and installed capsule pins must
be frozen before either comparison arm. The current Screening fixture needs
Brief v3 and explicit qualitative comparison status for its nonnumeric target;
the original bytes remain retained. No worker output is repaired.

`prepare_single_cc` takes actual `AdmittedResourceContext` handles, the approved
evaluation profile, snapshot, exact input Refs and an operator-owned terminal
source capture. It reuses ContractFactory and admitted-measurement validation
to freeze the canonical subject, checking plan, assets, exact E3 request and
single-use runtime slot. A source-only halted capture is not an executed product
run or the identity of the later private evaluation.

Capture a new protected configuration with `allowed_entry_points: [E3]`,
`invalid_for_product: true`, and `integrated_workflows: false`; bind its original
assets/runtime/snapshot Refs in bootstrap options. Preserve the exact model,
policy, checks and existing admission standing. Select that immutable bootstrap
generation through the normal supervisor environment. Issue a separate scoped
evaluation credential with `research.evaluation_grants` into a private app/runner
volume; keep it out of Harbor tasks, grader containers and exported results.

Readiness advertises `single_cc` independently of full experiment readiness
only after observing the actual current E3 owner, exact startup Refs, shared
auth/build/model/trajectory gates, tool-free subject and the executor's read-only
qualification. Ordinary `ready` and `submit` semantics remain unchanged. A
missing scientific Builder is not permission to bypass other E3 requirements.

Freeze one selected variant using `prepare(..., variant_ids=(...),
evaluation_overlay=...)`. The overlay records the exact request, run scope,
actual published public bytes, preregistered criteria and transformation receipts.
The host-only `evaluation_config` pins a bounded command invoking the existing
sidecar `Runner.execute_evaluation`, plus its input files and exact results root.
Only script/request/inventory controls enter the runner; private criteria stay
with the controller and grader. Its active pointer prevents automatic duplicate
dispatch and supports read-only reconciliation of the same attempt. Grading
requires complete original `EvaluationRecords` joined to that frozen request.

The earlier October 26 Screening checkpoint ran a plain GPT-6.1-Sol/medium arm and
attempted the implemented Screening CC, each limited to one tool-free call of
120 seconds against the same corrected public inputs and output contracts.
Initial host capacity was insufficient; later observations passed after the
user freed memory and completed-build caches were released. Plain Codex passed
mechanical content and format checks. The final CC request reached the selected
host relay, which retained an unknown outcome after a backend exception without
native terminal evidence. No further inference or unknown reclassification
followed. The idle relay is stopped and its guard is preserved. No paired
quality improvement is claimed. See the retained
[pilot result](../../benchmarks/harbor_suite/CC-PILOT-RESULT.md). The current local
catalog is a development built-in authorization; independent pre-admission
calibration remains NOT_RUN and this pilot does not establish M1 acceptance.

See [COMPARISONS.md](../../benchmarks/harbor_suite/COMPARISONS.md) for baseline
receipt custody, common content/format scoring, and verifier false-accept and
false-reject comparisons. Framework binding checks are reported separately from
plain Codex task quality. A single pair cannot establish a general improvement.
