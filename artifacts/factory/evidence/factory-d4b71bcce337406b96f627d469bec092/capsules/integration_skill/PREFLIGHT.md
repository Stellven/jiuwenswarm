# Before a bounded engine run

Adapted from siminfeng/cc/abrun/preflight.py, test_effective_config.py,
c2/METHODS.md and c2/MEASUREMENT-GAPS.md. Tag-keyed help caching in the old
preflight is superseded: resolve docker image inspect Id on every call, then
cache help by that immutable Id and tool under FACTORY_HOME/preflight/.
Retagging must never reuse help from the old image. Query /app/<tool> --help
using --runtime nvidia; reject every unsupported flag before a workload.

Call inspector.verify_effective_config with the exact image and LLAMA_EXPERT_*
string environment. It runs one CPU-only Granite token (-ngl 0, context 256),
with a 45-second subprocess deadline. This checks model-independent parsing,
not Qwen worker activation or performance. Unknown names and invalid values
must emit `expert_config: invalid NAME=VALUE (range R)` and abort: retain that
exact line, exit status and artifact. One effective line per context must match
all supplied values, even when fill/pregate are disabled. Never accept an OR
of activation regexes or a run label as configuration evidence. Read the
observation/artifact on CONFIG_REJECTED, CONFIG_MISMATCH or CONFIG_MISSING.

CUDA PATH lesson: nvcc installed on disk is insufficient. Check nvcc on the
actual build worker PATH and publish toolchain/version/flags. Pass required
PATH/CUDA settings before submission so the durable worker inherits them.
Build identity includes toolchain and digest-pinned base, not just source.
Older shells may need DOCKER_CMD_PREFIX='sg docker -c'; the complete Docker
argv must be one shell-quoted argument. Do not change group/root configuration.

llama-server memory lesson: inspect exact-image help and pin --cache-ram and
context/checkpoint behavior explicitly when supported. Defaults can reserve
large prompt/context-checkpoint caches and exhaust shared Jetson DRAM. Treat
unsupported --cache-ram as a preflight failure, never an ignored option. Record
actual allocation/headroom and checkpoint/cache settings; CPU/GPU RSS and
shared-DRAM counters overlap. Do not use Docker --memory as a Tegra CUDA cap.
The inspector config probe uses llama-completion and does not run a server.

Controller environment: set PYTHONPATH to the repository root so the host-sealed
Python interpreter can import the factory API (or install the package in that
interpreter). Set FACTORY_HOME, FACTORY_TASK_ID (existing task), and
FACTORY_WORKSPACE; use a host-bound workspace handle for inspect. Optional
FACTORY_READ_TASKS controls evidence reads, DOCKER_CMD_PREFIX wraps Docker,
and FACTORY_DOCKER is an offline fake executable argv only for tests. Native
capsules inherit environment. Supply process.exec, plus workspace.read for
inspect or gpu.use for NVIDIA-runtime probes, via operator grants.
