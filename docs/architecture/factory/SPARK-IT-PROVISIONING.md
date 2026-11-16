# IT provisioning for the inference software factory

Observed on the running Spark on 2026-11-16. This is an evidence-based handoff,
not a claim that a clean-machine installation has been reproduced. It separates
the working configuration from requirements and gaps. No host settings were
changed for this inventory, and no new GPU/build jobs were launched.

## Values for the IT request form

| Form field | Requested value / clarification |
| --- | --- |
| Operating system | **Ubuntu**, NVIDIA-supported DGX Spark ARM64 image if the replacement is another GB10/Spark. Observed image is Ubuntu 24.04.5 LTS with NVIDIA kernel 7.0.0-1019. Do not substitute generic x86 Ubuntu, EulerOS or CentOS without a separate port/qualification. Hardware model remains to be confirmed. |
| RAID, default two disks RAID1 | **Confirm disk count and hardware first.** Current Spark exposes one root filesystem on `/dev/nvme0n1p2`, approximately 4 TB decimal; no evidence of a two-disk RAID1 arrangement. Do not assume the form's default is applicable. Mirroring must still leave sufficient usable model/build/evidence space. |
| Partitions | Vendor-recommended boot/system layout is acceptable if the persistent data filesystem has sufficient capacity and supports ordinary Linux ownership, locking and atomic rename. Current `/home` and Docker data share the root NVMe filesystem. Reserve capacity for roughly 240 GiB of model files plus images, build caches and growing experiment history. Do not size the system disk for OS files alone. |
| Users, default root/admin only | A **named non-root admin account** with sudo, writable workspace, SSH access, approved Docker access and user linger can satisfy this policy. A separate service account is preferable but not required by the observed setup. Current account is `user2`, UID/GID 1002; exact identity may change if ownership/mounts are remapped. Root-only operation is not the qualified setup. |
| Additional tools, default OS only | **A generic default OS is insufficient.** Verify NVIDIA driver and Container Toolkit/CDI, Docker Engine, Python 3.12 with venv, Git, SSH, systemd user services, the approved ARM64 Python dependency bundle, pinned build/runtime images, factory and queue source, and model assets. The vendor Spark image may already supply much of the GPU/container stack; verify before reinstalling. Node/npm are needed only on a frontend build machine if the built console is transferred. See exact versions and provenance below. |
| HProxy tools copied | Copying tools does not configure connectivity. IT must provide the approved invocation/configuration, upstream access and certificate requirements, and whether proxy settings apply to the service account, package manager, Docker daemon and agent. No HProxy endpoint, port or credential is inferred here. |
| Others | Enable persistent user services (linger); keep the console loopback-only on port 5175 and access by SSH tunnel; supply sufficient unified memory and NVMe storage; import approved offline dependencies/models; provision agent authentication privately; install exactly one shared queue worker; qualify GPU access, cleanup and correctness before live cutover. |

If IT only hands over the default OS, arrange approved post-handover installation
privileges and network/mirror access for the listed dependencies. The form can
remain concise; the remainder of this document is the installation handoff.
NVIDIA's [Spark software requirements](https://docs.nvidia.com/dgx/dgx-spark-porting-guide/porting/software-requirements.html)
and [platform overview](https://docs.nvidia.com/dgx/dgx-spark-porting-guide/latest/overview.html)
identify the Ubuntu 24.04-based DGX OS and NVIDIA stack underlying this choice.

If the machine is not another Spark/GB10, this is an application requirements
list, not a compatible image recipe. The current target validates ARM64,
CUDA 13 and SM121; a different GPU/architecture needs an explicit target profile,
new builder/runtime images, memory limits and hardware qualification.

## Observed host and what is actually required

| Layer | Observed current machine | Interpretation |
| --- | --- | --- |
| OS/kernel | Ubuntu 24.04.5 LTS; `7.0.0-1019-nvidia`; `aarch64` | Supported NVIDIA platform installation required. Exact observed patch versions are a reference, not a tested compatibility range. |
| CPU/GPU | 20 ARM CPUs, Cortex-X925/Cortex-A725; NVIDIA GB10 | ARM64 native binaries; model/placement contracts are Spark-specific. |
| Memory | OS reports 130,661,142,528 bytes; 16 GiB swap | Approximately 128 GB unified-memory hardware. Current inference admission requires at least 108 GiB host-available memory and no other GPU compute. Container cap is not a complete unified-memory guard. |
| Storage | Root NVMe filesystem 4,030,802,149,376 bytes; about 2.12 TB available at inspection | Observed model directory is 240 GiB, pack directory 8.5 MiB, agent dependency bundle 944 MiB. Additional images/cache/artifact space is required. These are observed usage, not a minimum capacity proof. |
| GPU driver | `580.178.04` | Working host driver; preserve a supported driver/toolkit pairing. `nvidia-smi` reports memory total as N/A on this unified-memory device. |
| Docker | CE `29.6.2`, containerd `2.2.5`, runc `1.3.6`; overlayfs; cgroup v2 with systemd driver | Docker CLI/socket plus cgroup telemetry are used directly. Rootless Docker has not been qualified. |
| GPU container access | NVIDIA Container Toolkit `1.20.1`; CDI `nvidia.com/gpu=0`; refresh path/service enabled | Code uses `--device nvidia.com/gpu=0`, not `--gpus all`. Default runtime is `runc`; no `/etc/docker/daemon.json` exists. A custom default NVIDIA runtime is not required by this deployment. |
| Host Python | `3.12.3`, venv and pip installed | Host controller/service/recorder and queue use Python. SQLite FTS5, Linux process groups, `/proc`, file locks and cgroup reads must work. |
| Host Git/SSH | Git `2.43.0`; OpenSSH server package `9.6p1-3ubuntu13.19` | Source identity/local commits, transfers and remote operation. Git LFS is not installed on current Spark and is not needed for the small source-only deployment. |
| Access network | SSH and Tailscale services active; Tailscale `1.104.5` | Tailscale is the current route, not an intrinsic factory dependency. An IT-approved reachable SSH route can replace it. |

CPU boost is reported disabled by `lscpu`; no evidence was found that the
factory changed this setting. Do not automatically change it for provisioning.

The [sanitized package inventory](qualifications/20261116-spark-it-package-inventory.json)
contains 274 selected installed host packages, the complete 182-distribution
agent closure's names/versions, its source manifest hash, and 13 retained APT
install/upgrade records filtered to relevant packages. Package lists are not a
minimal install recipe. Command lines, direct download URLs and credentials were
excluded. Retained logs show much of the NVIDIA/Docker/CUDA stack installed or
upgraded on October 5, before the current November factory integration; it would
be incorrect to attribute all of those packages to this work. Log rotation and
image provisioning prevent a complete original-default versus current diff.

## OS defaults versus deliberate application configuration

Observed sysctls: `vm.swappiness=60`, `vm.max_map_count=1048576`,
`kernel.unprivileged_userns_clone=1`, `kernel.perf_event_paranoid=4`.
`/etc/sysctl.d/10-map-count.conf` supplies max_map_count and belongs to the
`procps` package. We have not established a before/after OS baseline; the partial
APT inventory above does not establish who changed sysctls. These are **observed settings**, not claimed factory
tuning changes. No blanket sysctl change, privileged container, disabled
AppArmor/seccomp, or relaxed profiler policy is required by the exercised path.

Known application-specific setup includes: service-account Docker access,
user linger, the `native-cc-factory.service` unit, isolated workspace/source
checkouts, Python environments/dependency closure, pinned role images, queue
configuration, fresh task/workflow contracts, and a locally built static console.
The earlier `deploy/spark/README.md` describes a historical container/bridge port;
the current native host service supersedes that operational entry point.

Current Docker socket is `root:docker`, mode `0660`. Docker membership conveys
powerful host control; IT must authorize this service-account permission. After
changing group membership, start a fresh login/user-manager session and verify
the actual service process sees it. Do not solve stale group membership by
making the socket world-writable. Current user also belongs to `sudo` and
`users`; ordinary factory execution does not require sudo membership.

Inference containers are non-root, read-only, network-disabled, private IPC and
cgroup namespaces, no added capabilities, no-new-privileges, 256-PID limit,
8-CPU quota, 104 GiB memory cap, no additional swap, read-only model mounts and
a 64 MiB `/tmp`. A separate host guard stops at less than 8 GiB available memory.
Native compilation uses no GPU/network/socket, read-only source, eight CPUs,
16 GiB memory and a writable owned build area. Do not replace these boundaries
with privileged execution to make provisioning pass.

## Python and build dependencies

The permanent service environment is
`/home/user2/software-factory-spark-20261113/native-workflow-service-env`.
It was created with `python3 -m venv --system-site-packages`; this fact matters:
`pip list` alone includes unrelated OS packages and does not describe the
effective agent environment. `PYTHONPATH` prepends the factory source followed
by `native-agent-dependencies-20261116`, an ARM64 dependency closure copied from
the existing approved agent image. Representative **effective** versions are:

| Package | Effective version |
| --- | --- |
| openai-codex-cli-bin | 0.163.0 |
| openjiuwen | 0.1.18 |
| fastapi / uvicorn | 0.136.1 / 0.46.0 |
| pydantic | 2.13.3 |
| mcp / fastmcp | 1.29.0 / 2.14.7 |
| jsonschema / rfc8785 | 4.26.0 / 0.1.4 |
| psutil / PyYAML | 7.2.2 / 6.0.3 |
| httpx / anyio | 0.28.1 / 4.13.0 |

The complete captured closure has 182 distributions and 26,480 files.
`agent-build-context-001/closure.json` has SHA256
`76a5885683516a6111ed99a68f302b1bd46be99b44a5865266ed63ea7396f842`.
Use `deploy/spark/package-agent.py`, `Agent.Dockerfile` and
`requirements-agent.lock` as the existing packaging references. The packager
copies an already installed, exercised environment; it is **not** a clean
internet bootstrap script. The version-only lock is not a hash-locked wheelhouse.
IT needs the approved ARM64 closure/image or a separately verified wheelhouse.
Do not install all packages from the host `pip list` or assume unpinned
`pip install -e .` reproduces the working environment.

The working native builder is pinned to image
`sha256:d893d61a6f641fdeb6d20ce33870868d3ffd497746531a233d988427deff7f87`.
Its toolchain is GCC/G++ 13.3.0, CUDA nvcc 13.0.88, private CMake 4.4.3 and Ninja
1.13.2.git.kitware.jobserver-pipe-1. Host CMake is only 3.28.3 and host Ninja is
not installed: these are **container toolchain dependencies**, not instructions
to replace the host compiler globally. Host CUDA toolkit package 13.0.3-1 is
present because packaging can copy it; an imported complete builder avoids
requiring that toolkit on every runtime-only host.

`deploy/spark/package-builder.py` snapshots GCC13, binutils, libc/libstdc++
development packages, CUDA and private CMake/Ninja into a Docker context.
`builder-build-context-001/toolchain.json` SHA256 is
`4e9807adeab0924014d098eeda71c60334058a7998f6fd67180ca00152e26a65`.
The Dockerfiles use ARM64 base
`ghcr.io/ggml-org/llama.cpp@sha256:695214dcb4d4062014335702caee98836bbf92c5974b78331c70e152176cbf08`.
Import approved images by digest or transfer them out-of-band; the factory uses
`--pull never`/offline builds. Image IDs in task contracts must match the
actually imported/rebuilt images; tags alone do not establish identity.

The engine build additionally needs clean STRATA and GGML source. Current
original fixed-placement baseline is STRATA
`89ae0ee6123597636ef162dec826230186c00f3b`, GGML
`3cf03257f219afbe7334045ff7c6a06ac68c627d`. Candidate commits are separate and
must not silently replace that baseline. Native compilation targets ARM64,
CUDA13 and SM121; relevant recipe is `jiuwenswarm/factory/spark_engine.py`.

No Node binary exists on current Spark. The static console was built elsewhere
using the frontend lockfile and `scripts/build-factory.mjs`, then transferred.
Node/npm and frontend dependencies are needed only if IT chooses to build the
console on the destination. Use the repository's frontend lockfile and an
approved build host; serving the built assets requires Python, not Node.

## External queue and persistence dependencies

The factory repository alone is insufficient. It calls the shared `siminfeng`
`bin/jobq` and `bin/run_op`, currently outside the factory root:

```text
SIMINFENG_ROOT=/home/user2/rsi-expert-streaming-spark-002/paired-retry-001/lab-source
JOBQ_DIR=/home/user2/rsi-expert-streaming-spark-002/paired-retry-001/jobq
CAMPAIGN_ROOT=/home/user2/rsi-expert-streaming-spark-002/paired-retry-001/lab-evidence
```

These copied source trees do not expose a Git revision to `git rev-parse`.
Observed `bin/jobq` SHA256:
`da67e7972a17c8073c6d28af93b767abe991bca7cb63d4ac1972fdc182ba3a91`.
Observed `bin/run_op` SHA256:
`41f954bda92aa84e23d9512bb99c9f1b497d85510e47bd4c7978fb3d9630079c`.
Supply the approved complete queue source/evidence configuration, not guessed
files from an unrelated branch. Both scripts use standard-library Python, but
the existing worker runs from a separate historical venv at
`/home/user2/rsi-expert-streaming-001/factory-env/bin/python`.

Exactly one shared worker is currently running. It is an orphaned process in a
login-session scope, not a proven reboot-persistent queue systemd service.
Linger and the web unit do **not** establish queue restart persistence. A new
machine needs an explicitly managed queue worker and restart/reconciliation
qualification; do not start a duplicate worker against the existing live queue.
Use `JOBQ_DIR` and `CAMPAIGN_ROOT` consistently for both submitters and worker.

Local writable persistent storage is needed for task SQLite databases, sealed
CC releases, queue records, process/container ownership records, append-only
evidence, source workspaces, build outputs and the experiment-library SQLite
index. Back up originals as well as the search index; the index contains bounded
projections and is not a substitute for raw experiment evidence. Do not put
mutable stores, model files, archives or credentials in Git. Do not copy live
SQLite databases without a consistent backup/checkpoint procedure.

## Model assets and access

Current pack is
`/home/user2/strata-baseline/Strata-data/packs/deepseek-v4.1-flash-ist-das-2.00bpw`;
model root is `/home/user2/strata-baseline/Strata-data/models`, containing the
quantized DeepSeek model and shared assets. Supply these separately with the
approved inventory and small metadata/tokenizer/profile hashes. Existing
large-file size/mtime checks are not full model content hashes. Mount paths and
asset identities are frozen in each contract; changing host paths requires a
new prepared contract, not an ad-hoc symlink assumption.

The agent requires outbound access to its configured model/auth provider,
including TLS and any persistent streaming connections. Package/image/source
downloads additionally require approved repositories during provisioning;
qualified build and inference containers themselves run without network.
IT should provide DNS, CA trust, proxy policy and approved source/image mirrors.
No direct outbound bypass is assumed when HProxy is required.

Provision agent authentication through the approved login/secret mechanism.
Current auth files are owner-only mode0600; their contents were not inspected.
Per-task Codex homes are private runtime state. Do not copy another employee's
credentials into the provisioning package, environment file, image or Git.
The operator's SSH key and optional repository credentials are separate from
the model-provider authentication. Only local source commits are needed by the
experiment agent; GitHub push credentials are not required in GPU containers.

## Application setup and service template

The following application changes were needed for the exercised native factory.
They are source requirements, not reasons to weaken OS/container permissions:

| Change | Source evidence / purpose |
| --- | --- |
| Native workflow/CC integration | `cb0ec15`: reusable native CC leaves, durable graph revisions, scoped Lab Manager jobs and independent evidence. Preserve the workflow team's composition layer and the CC team's authority/lifecycle boundary. |
| Standalone native console/server | `e0746e939`: `cc_server` entry point and static factory frontend build; serves the host workflow API without the retired application entry point. |
| GPU terminal cleanup | `ab23ddc67`: reconcile the exact owned inference container even when the queue job is already terminal. This fixed a real cancellation qualification failure. |
| Native build cleanup | `5d30d9a00`: apply shared owned-container cleanup to native builds as well. Do not replace this with global Docker cleanup. |
| Real agent workflow/history front door | `abcc4af85`: native workflow MCP tools, scoped persistent experiment search, frozen throughput campaign, independent acceptance and budget admission. Also forwards the queue source path to agent tool processes. |
| Fixed-placement engine baseline | STRATA `89ae0ee612`: original A image records fixed expert placement to avoid comparing different residency layouts. This is separate from factory source and from later unpromoted scheduling experiments. |

The service integration branch contains these fixes. Deploy an approved complete
revision rather than trying to reproduce them with host configuration. Round 1
and round 2 experimental STRATA patches are **not** IT provisioning requirements
and must not be silently promoted as part of setting up the machine.

Choose destination paths and replace placeholders consistently. Check out the
approved `integration/native-cc-workflows` source revision, import dependencies,
build/copy the static console, provision the queue and model assets, then create
a **fresh** operator-admitted task and workflow configuration. Historical
deadlines and GPU allowances must not be reused. Task preparation must create
the owned workspace, sealed selected CCs, allowed effects and exact build/lab
contracts before service start. Current campaign preparation scripts are
machine-specific and are not yet a portable bootstrap installer.

The environment file must contain only the required non-secret settings:

```text
FACTORY_HOME=<campaign>/factory
FACTORY_TASK_ID=<fresh-task-id>
FACTORY_WORKSPACE=<campaign>/factory/agent-workspace
FACTORY_PYTHON=<venv>/bin/python
FACTORY_HOST_PYTHON=<venv>/bin/python
PYTHONPATH=<factory-source>:<approved-arm64-agent-dependency-directory>
SIMINFENG_ROOT=<approved-queue-source>
JOBQ_DIR=<shared-queue-state>
DOCKER_PREFIX=
DOCKER_CMD_PREFIX=
JIUWENSWARM_SKIP_DOTENV=1
JIUWENSWARM_DATA_DIR=<campaign>/factory/agent-data
```

Install a user unit like the exercised one (substitute paths; no secrets):

```ini
[Unit]
Description=Native CC Software Factory operator console
After=network-online.target

[Service]
Type=simple
WorkingDirectory=<factory-source>
EnvironmentFile=<campaign>/service.env
ExecStart=<venv>/bin/python -m jiuwenswarm.software_factory.cc_server --config <campaign>/workflow-config.json --static <console-directory>
Restart=on-failure
RestartSec=5
TimeoutStopSec=75

[Install]
WantedBy=default.target
```

IT enables linger for the service account (`loginctl enable-linger <account>`),
then that account reloads/enables the user unit. This console unit does not
launch the decision-making controller or queue worker. Each campaign must
launch its bounded controller separately with the same task/environment and
retain its outcome/logs. Do not infer an active optimization from a healthy UI.

The server listens only on `127.0.0.1:5175` and rejects remote operator calls.
Access it through `ssh -N -L 5175:127.0.0.1:5175 <account>@<host>`; do not expose
5175 publicly or change it to another host port. Preserve rollback configuration
and reconcile owned jobs before switching services. Stopping the web service
alone does not cancel queue work.

## IT acceptance checks

Perform read-only checks first: `uname -m`, `nvidia-smi`, `docker version`,
`docker info`, `nvidia-ctk cdi list`, `id`,
`loginctl show-user <account> -p Linger`, and
`systemctl --user status native-cc-factory.service`. Confirm the effective
Python imports with the actual service `PYTHONPATH`; verify SQLite FTS5 and
the real MCP tool listing, not just `pip list`. Verify asset/source/image hashes
and readable cgroup/process telemetry without printing credentials.

Then use a fresh bounded qualification task: native build, real inference on
the intended model, exact outputs, admitted image lineage, wrong-image
rejection, cancellation/timeout and exact-container cleanup, queue restart
reconciliation, service restart and read-only browser replay. Reserve the GPU
and host memory for these tests; never run them alongside an existing campaign.
Boot persistence of both queue and web service must be tested on the new host.
A healthy service or successful compile does not establish model correctness
or a speedup. Keep experimental candidate promotion separate from IT acceptance.

## Remaining replication gaps

1. Confirm replacement hardware and usable disk layout before accepting the
   form's RAID/partition defaults.
2. Deliver the approved ARM64 dependency closure/wheelhouse, pinned images,
   queue source and model inventory out-of-band; Git alone is insufficient.
3. Convert the historical mixed venv/copied closure into a clean reproducible
   environment if desired, and requalify it instead of silently upgrading.
4. Make the queue worker explicitly persistent and validate crash/reboot
   reconciliation; current web linger does not cover it.
5. Supply IT's HProxy/network/CA configuration and authorized agent login.
6. Parameterize machine-specific task/model/queue paths and create fresh
   authority; do not replay expired setup JSON blindly.

Evidence sources: read-only host commands, the current systemd unit and safe
configuration fields, package ownership queries, builder/agent manifests,
`deploy/spark/{package-agent.py,package-builder.py,Agent.Dockerfile,Builder.Dockerfile}`,
`jiuwenswarm/factory/{spark_engine.py,lab_recorder.py,throughput_campaign.py}`,
and the [service runbook](SPARK-NATIVE-SERVICE.md). No exact install chronology
or unobserved change to vendor defaults is claimed.
