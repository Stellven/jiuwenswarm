# Software Factory Build Server Requirements

- **Purpose:** Run the software factory and build ARM64 images on x86. Use DGX Spark for GPU testing.
- **OS:** Ubuntu 24.04 LTS, latest maintenance release, x86-64 (amd64).
- **Storage:** SSD/NVMe; default RAID1 acceptable. Space for Docker images, source code, build caches and experiment records.
- **Account:** Named administrator with sudo, SSH-key access and Docker access.
- **Container tools:** Docker Engine and Buildx/BuildKit — latest stable.
- **Development tools:** Git, OpenSSH, curl, CA certificates and archive utilities — latest stable supported by the OS.
- **Factory runtime:** Python 3.12 (latest patch), pip/venv and pinned project dependencies; Node.js latest LTS with bundled npm for the web interface build.
- **ARM64 build tools:** GCC/G++ 13 ARM64 cross compiler (latest patch), matching ARM64 binutils/sysroot; CMake, Ninja and pkg-config — latest stable.
- **CUDA build tools:** CUDA 13.0 NVCC and ARM64 cross-SBSA development libraries, plus matching ARM64 runtime libraries.
- **Build cache:** Persistent compiler/container caches; ccache or sccache — latest stable.
- **Services:** systemd, time synchronization, automatic service startup and backups for configuration/experiment records.
- **Network:** Configured HProxy/corporate CA access to package repositories, GitHub, container registries and the agent provider; private SSH/image transfer to DGX Spark.
- **Optional local GPUs:** Latest stable NVIDIA driver and NVIDIA Container Toolkit compatible with the installed RTX GPUs, if used. GPUs are not required for compilation.

Default OS tools alone are insufficient; the software above must be installable after handover.
Specific OS, Python, GCC and CUDA versions above are retained for compatibility with the current factory/build recipe.
