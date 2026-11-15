# Native Spark role images

The control image runs the actual JiuwenSwarm facade, factory controller, CC
runner and packaged Codex 0.163.0 transport. It is separate from the small
`factory/cli` image. `requirements-agent.lock` records the 182-distribution
closure exercised from the existing approved native environment; the closure
manifest also records installed file hashes and VCS provenance. It is not a
blind install of all project extras. Packaging requires no package downloads,
global installations, or copied authentication files.

The builder image seals the existing CUDA 13/GCC 13 native compiler, CMake 4.4.3
and Ninja 1.13 tools, headers and required libraries. Its toolchain manifest
records 13 source Debian package versions and file hashes. It has no model,
credentials, GPU access or Docker socket. Runtime image packaging remains a
host Docker operation after compilation exits.

Both reuse the existing pinned ARM64 Ubuntu 24.04 CUDA runtime layers. This
keeps the imported native Python wheels on their matching libc ABI. Build
images before starting scored lab work:

```sh
python3 deploy/spark/build-role-images.py \
  --output /home/user2/software-factory-spark-20261113/role-contexts-NEW \
  --agent-python /home/user2/rsi-expert-streaming-001/factory-env/bin/python \
  --cmake-data /home/user2/strata-baseline/Strata/.venv-build/lib/python3.12/site-packages/cmake/data \
  --ninja /home/user2/strata-baseline/Strata/.venv-build/bin/ninja
```

The output directory must be new. It contains package/build logs, manifests
and immutable image IDs. Source manifests and the existing dependency closure
make the current imported build reproducible from retained inputs; rebuilding
those upstream dependencies from scratch remains a separate provenance task.

Set `FACTORY_NATIVE_BUILDER_IMAGE` to the immutable builder ID when submitting
Spark builds. The worker verifies ARM64 identity and compiles in the container
with read-only source/dependency mounts, eight CPUs, 16 GiB/no-extra-swap and
configuration-keyed writable output/cache mounts. The host compiler fallback
remains available for historical tasks without this setting.

Agent/control runs need `HOME=/tmp` and a writable temporary working directory:
OpenJiuwen logging initializes during imports. Its actual agent working
directory is the isolated factory checkout configured by the controller.
`mission_supervisor` supplies these settings and mounts only the operator's
single auth file read-only into the dedicated profile; credentials never enter
an image or evidence artifact. Expired credentials stop the mission rather
than being copied into a new profile or exported.

After preparing and approving the task separately, run or resume it with the
finite launcher from this checkout:

```sh
/home/user2/software-factory-spark-20261113/venv/bin/python \
  deploy/spark/run-mission.py
```

The launcher reads the approved task grants and role-image receipt, reuses the
held mission bridge or starts an owned finite bridge, and invokes the actual
supervisor. It never creates a task, changes a contract, or replaces a bridge
owned by another process. It mounts the operator contract, asset inventory,
models and pack read-only, including paths nested inside the owned workspace.
Use `--help` for alternate task/home/queue paths and an optional grant subset.

Observed qualification: a C++ program compiled and returned `42` in the builder
image; the agent image ran the packaged Codex executable and imported the real
JiuwenSwarm facade in a read-only, network-disabled container. These are startup
checks, distinct from a live agent turn or full Strata build.

`results/mission-role-images.json` in the owned workspace records the executed
image identities. Failed initial packaging/runtime smoke logs are retained:
the first import needed writable cwd/HOME, and merged `/lib` paths had to be
normalized to `/usr/lib` when assembling the Ubuntu image.
