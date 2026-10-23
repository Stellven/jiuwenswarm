# Sequential benchmark runner

The final installation has exactly two Compose service roles: `ai4r` and
`benchmark-runner`. Only AI4R publishes a host port, `127.0.0.1:5175`. The runner
uses `http://ai4r:5173` on the project network and executes one task at a time.
It mounts cases/inputs read-only and results read-write. Neither service mounts
the Docker socket, and the runner has no app database or account-volume mount.

The runner is UID11001 with no capabilities, a 128-process ceiling, 2 GiB memory
ceiling and 128 MiB temporary filesystem. Native app workers run as UID10001
and generated work as UID10002. The existing fixed app supervisor/executor broker
still requires root and its bounded capabilities to enforce that separation;
this deployment does not claim that every app-container process is non-root.

## Build

Full source builds use the existing frozen dependency lock:

```bash
docker build -f deploy/m1/Dockerfile.app --target production -t ai4r:local .
docker build -f deploy/m1/Dockerfile.sidecar --target benchmark-runner -t benchmark-runner:local .
```

For a bounded offline rebuild, pin an already complete local M1 dependency
runtime. `build_two_images.py` verifies its exact image ID, freezes a public TAR,
builds fresh app wheels and installs the current built web assets. It reuses the
complete cached TUI assets and requires an unchanged dependency lock. The final
app copies a sanitized filesystem into a scratch image: old runner code/wheels
and obsolete lower image layers are absent. Its installed identity hashes all
packaged code/assets and dependencies. A frontend-source change requires running
the normal frontend build first; the cached mode consumes its explicit `dist`.

```powershell
python deploy/m1/build_two_images.py ai4r --output <new-receipt-dir> --tag ai4r:<new-tag> --dependency-image <cached-runtime> --expected-dependency-id sha256:<exact-id>
python deploy/m1/build_two_images.py benchmark-runner --output <other-new-receipt-dir> --tag benchmark-runner:<new-tag> --dependency-image <cached-runtime> --expected-dependency-id sha256:<exact-id>
```

Do not rebuild or patch a campaign's running target. Receipts contain the frozen
context hash and final immutable image ID; use a new output directory/tag.

## Start and mounts

For a new installation, use `compose.benchmark-runner.yaml` with an explicit
Compose project and the approved operator configuration. `up -d ai4r` works
without runner configuration. Set `AI4R_BENCH_CASES`, `AI4R_BENCH_INPUTS`,
`AI4R_BENCH_OUTPUT`, `AI4R_BENCH_CREDENTIAL`, `AI4R_EXPECTED_BUILD`, and immutable
image selections before starting the `benchmark` profile. No referee, answers,
score or report mount is required. Existing research runtime bindings remain
necessary for the chosen app operations.

Host paths are absolute paths on the selected Docker daemon, including a remote
context. They must already exist and be canonical; a Windows client path is not
silently translated for a remote host. On this workstation the selected paths
resolve under `/mnt/d/research/ai_for_research/runs/jiuwenswarm/docs/code/Missions/docs/source/QA/Benchmark/`:
`cases`, `inputs`, and `results`. The cases file is `/cases/smoke.json` inside the
runner. Credentials are kept separately under the protected operator runtime.

Run the mount check from Linux/WSL with the built runner image and explicit
paths. It checks actual mounted types, UID11001 access, read-only kernel mount
flags, disjoint roots and an exclusive, flushed output probe. It never creates
the requested directories or overwrites a user file.

```bash
python3 deploy/m1/benchmark_runner_host.py --image <runner-image-id> \
  --cases <host-cases> --inputs <host-inputs> --output <host-output> \
  --credential <protected-host-token> --json
# For a remote daemon, add --docker-context <context> and use canonical remote paths.
```

The existing 5175 installation uses `migrate_benchmark_runner.py prepare` then
`activate` with its prepared manifest. This reuses the same project and six
volumes, requires zero active runs/leases before and after stopping, removes
source/identity override binds, and captures fresh runtime metadata against the
installed build. Existing imported resource/scoring references are preserved
without reading datasets or private answers. It issues a finite scoped runner
grant after native startup. It removes only the old stopped app container.

## CLI

The workstation wrapper reads the active immutable Compose profile and executes
the CLI inside its existing runner container. Configuration supplies endpoint,
credential-file reference and expected build through `AI4R_ENDPOINT`,
`AI4R_TOKEN_FILE`, and `AI4R_EXPECTED_BUILD`. `AI4R_HTTP_AUTHORITY` pins the
authenticated virtual host when its authority differs from the private network
endpoint; here it is `127.0.0.1:5175`. Token bytes are never printed.

```powershell
python deploy/m1/runner.py doctor --json
python deploy/m1/runner.py run --campaign-id smoke-001 --json
python deploy/m1/runner.py run --cases /cases/other.json --campaign-id other-001 --json
python deploy/m1/runner.py status --campaign-dir /results/smoke-001 --json
python deploy/m1/runner.py resume --campaign-dir /results/smoke-001 --json
python deploy/m1/runner.py cancel --campaign-dir /results/smoke-001 --json
python deploy/m1/runner.py export --campaign-dir /results/smoke-001 --json
python deploy/m1/runner.py cleanup --campaign-dir /results/smoke-001 --json
```

Use a fresh campaign ID; existing folders are never adopted or overwritten.
`resume` reconciles recorded requests before dispatch. `cancel` pauses dispatch
until terminal state is observed, and collection can resume independently.
Large native event/record collections remain packed in the original verified
export ZIP with a per-member SHA-256 inventory. The runner downloads one bounded
archive instead of expanding thousands of trace files or making one request per
event. Defaults distinguish 4,096 physical output files from 100,000 archive
members; transport/uncompressed totals are limited to 512 MiB and individual
members to 128 MiB. Every member's path, size and hash is verified. Readable
Markdown/text extraction is limited to 32 files and 4 MiB within the physical
budget. Deep optional readable-copy paths use a bounded filename containing the
full content hash; original member paths remain in the ZIP/inventory for
provenance and Windows compatibility. Case `limits` can explicitly tighten these bounds. Interrupted transfers
retain verified evidence and resume collection without rerunning the task.
`export` rebuilds JSON/CSV/Markdown from saved records and preserves human review
annotations. Cleanup is restricted to owned disposable campaign workspaces and
retains evidence/results. Never use `down -v` or global Docker prune.

Grants expire and are revoked when the app's native session family changes.
After app restart or grant expiry, refresh the idle runner's credential with:

```powershell
python deploy/m1/configure_benchmark_runner.py --refresh-credential
python deploy/m1/runner.py doctor --json
```

This uses the existing root operator CLI and protected account/workspace binding
to issue a finite grant into a fresh exclusive token file, updates an immutable
Compose profile, and recreates only the idle runner. It never prints token bytes
or copies a broad browser credential. An active `run`/`resume` process refuses
configuration changes.

Normal PowerShell app resume/open uses the retained role-aware helper. Opening
the fresh bootstrap URL does not print the credential:

```powershell
$helper = "$env:LOCALAPPDATA/AI4Research/runtime/poc-clean-isolation.py"
python $helper resume
python $helper open
```

Reports leave Assessment, Evidence references and Review notes for humans.
Exit codes describe execution or prerequisites, never scientific correctness.

Every app run export now contains `contracts/index.json` plus the exact available
Research Brief, frozen run plan, node/subnode execution contracts and bound check
plans under `contracts/`. The index carries original references, hashes and Brief
acceptance status. Artifacts not created before a halt are explicitly missing;
no plan or accepted Brief is fabricated. In sequential results these files remain
inside `artifacts/originals.zip`, indexed by its verified inventory. Brief 3.0.0
supports factor-plus-offset targets and explicit quantitative, qualitative and
unsupported status; historical 2.0.0 contracts keep their original bytes.

Repeated cases reuse an authenticated existing upload only when scope, kind,
filename, size and content hash match. Different bytes at an occupied filename
block preparation; the runner never overwrites or deletes retained inputs.

## Local connected evidence

`smoke-20261022-02` completed two supplied synthetic PDF tasks in sequence on the
pinned app build `789e4745...`. Interrupting the observer and resuming kept the
same first request/run IDs; the second task started after collection confirmation.
Both archives and actual summary bytes were collected on the host. All 122 host
files and the pre-existing sentinel retained their hashes after both containers
were removed and recreated. These checks assess execution and persistence;
humans assess the summaries.

The final running app build is `db45a807...` (stable export filenames) with runner
image `193c0ae0...` (bounded archives and portable readable-copy paths). The old
execution image remains pinned for traceability. Final readiness, repeated stable
artifact manifests, and a matching summary download were verified after recreation.
The fixed privileged supervisor exception above remains; optional telemetry is
reported only when exposed, and no GPU or unavailable usage is inferred as zero.
