# IT request: x86 software factory and build server

Decision recorded 2026-11-16: run the software factory, orchestration and ARM64 image builds on the x86 server. Reserve the single DGX Spark for one exclusive GPU test at a time. The expectation that builds can stay ahead of tests is a planning assumption to measure, not a completed throughput result.

## Requested provisioning

| IT field | Recommendation |
| --- | --- |
| Required OS | **Ubuntu 24.04 LTS, amd64/x86-64**, minimal/server installation with supported updates. Keep Spark on its NVIDIA-supported ARM64 OS. |
| RAID | Default **two disks in RAID1** is acceptable. Use SSD/NVMe where available; state usable capacity after mirroring. RAID does not replace backups. |
| Partitions | Standard UEFI/boot layout; approximately **100-150 GB for OS** if capacity allows, with most remaining space on a persistent **/data** filesystem for Docker/BuildKit, repositories, compiler caches, images and experiment records. Make Docker data placement explicit to avoid filling root. Exact sizes depend on installed disks; do not repartition blindly. |
| User creation | One **named non-root administrator with sudo** is sufficient initially. Enable SSH keys and approved Docker access. Permit persistent systemd services; use user linger if deploying user services. A separate service account is useful but not a prerequisite. |
| Additional tools | Default OS tools are insufficient. Permit installation of the packages below, either by IT or through approved post-handover administrator access. |
| HProxy | Copying the tools is insufficient: provide the approved proxy configuration, corporate CA chain and instructions for the user account, APT, Docker/BuildKit, Git and agent services. Keep credentials out of repositories and images. |
| Others | Private connectivity to Spark, persistent services, reliable time synchronization, backups for source/configuration/evidence, and monitoring for disk, RAM, queue depth and failed jobs. Factory console uses loopback port **5175**, accessed through an approved tunnel/proxy. |

## Software to install or allow

1. **Host services:** OpenSSH client/server, Git, curl, CA certificates, archive tools, systemd, time synchronization, Python 3.12 with venv/pip; an isolated x86 factory environment using the project's dependency lock/closure. Do not copy the Spark ARM64 Python environment.
2. **Containers:** Docker Engine, Buildx/BuildKit and persistent cache storage. Container images and caches stay outside Git. Set explicit memory/CPU limits and cache retention.
3. **ARM64 cross compiler, preferably in a pinned build image:** GCC/G++ 13 targeting aarch64-linux-gnu, ARM64 binutils/sysroot, CMake, Ninja, pkg-config, and native x86 CUDA 13.0 NVCC with **cross-SBSA** headers/libraries. Use the SBSA target for Spark, not Jetson/Tegra packages. Keep target CUDA runtime libraries pinned separately from compiler link stubs.
4. **Console build tools:** Node.js/npm at the version required by the repository lockfile. These are not required on Spark if the console is built on x86.
5. **Build acceleration:** persistent BuildKit and compiler caches; ccache or sccache after validation of the CUDA recipe. Stable source/dependency locations and incremental builds are required to get useful reuse.
6. **Optional local GPU support:** install a driver and NVIDIA Container Toolkit supported by the actual RTX cards only if using those GPUs. Local GPUs are not required to compile Spark images; RTX tests do not qualify GB10 behavior.

## Capacity and connectivity

- Work within the fixed hardware. If RAM is selectable, **64 GB is preferred**, with 32 GB a practical initial planning target for bounded build concurrency; these are recommendations, not measured minimums. Adjust compiler workers to actual memory and monitor swap/OOM.
- Prefer at least **1 TB usable SSD capacity after RAID**, with more space if retaining many images. This is a capacity planning target, not an installation minimum. Keep the approximately 240 GiB model store on Spark rather than copying it to the builder.
- Use a stable wired connection to Spark. Gigabit is usable; faster Ethernet helps when transferring large uncached layers. Reuse stable image layers and transfer by digest.
- Allow approved access or mirrors for Ubuntu packages, NVIDIA CUDA packages, GitHub, the selected container registry, Python/Node packages and the agent provider. Configure proxy/CA trust in both host and container build contexts.
- Allow authenticated SSH and image/artifact delivery between x86 and Spark. Do not expose Docker's unauthenticated TCP socket. An internal authenticated registry is useful; verified archive transfer is acceptable initially.

## Application deployment requirements

- Run factory/controller and build workers on x86; preserve experiment history and provenance in durable storage.
- Keep one authoritative exclusive GPU queue and Lab Manager on Spark. Build-ahead uses a bounded queue; cancel stale candidates and prioritize informative tests.
- Deliver images by immutable digest with source/toolchain/build records. Verify imported image identity before lab admission; do not treat an external build as a native same-host receipt.
- Make the queue worker, controller and console restart reliably after reboot. The existing Spark queue worker's reboot persistence still needs explicit deployment work.
- Back up authoritative source, configuration, contracts, experiment metadata and reports. Compiler caches and disposable images can be recreated; apply retention separately.

The local low-memory x86-to-ARM64 experiment is still running at the time of this request. This document does not claim it has passed GPU qualification or that the production remote-build/admission path is already implemented.

References: [NVIDIA CUDA 13.0 cross-platform installation](https://docs.nvidia.com/cuda/archive/13.0.2/cuda-installation-guide-linux/index.html#cuda-cross-platform-environment), [NVCC cross compilation](https://docs.nvidia.com/cuda/archive/13.0.2/cuda-compiler-driver-nvcc/index.html#cross-compilation), [Docker multi-platform builds](https://docs.docker.com/build/building/multi-platform/). Existing-machine inventory and application changes: [SPARK-IT-PROVISIONING.md](SPARK-IT-PROVISIONING.md).