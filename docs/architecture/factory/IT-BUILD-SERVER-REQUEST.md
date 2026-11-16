# Software Factory Build Server Requirements

- **Purpose:** Run the software factory and build ARM64 images on x86. Use DGX Spark for GPU testing.
- **OS:** Ubuntu 24.04 LTS, x86-64 (amd64).
- **Storage:** SSD/NVMe; default RAID1 acceptable. Space for Docker images, source code, build caches and experiment records.
- **Account:** Named administrator with sudo, SSH-key access and Docker access.
- **Container tools:** Docker Engine and Buildx/BuildKit.
- **Development tools:** Git, OpenSSH, curl, CA certificates and archive utilities.
- **Factory runtime:** Python 3.12, pip, venv and project dependencies; Node.js/npm for the web interface build.
- **ARM64 build tools:** GCC/G++ 13 ARM64 cross compiler, ARM64 binutils/sysroot, CMake, Ninja and pkg-config.
- **CUDA build tools:** CUDA 13.0 NVCC and ARM64 cross-SBSA development libraries, plus matching ARM64 runtime libraries.
- **Build cache:** Persistent compiler/container caches; ccache or sccache.
- **Services:** systemd, time synchronization, automatic service startup and backups for configuration/experiment records.
- **Network:** Configured HProxy/corporate CA access to package repositories, GitHub, container registries and the agent provider; private SSH/image transfer to DGX Spark.
- **Optional local GPUs:** Compatible NVIDIA driver and NVIDIA Container Toolkit if the RTX GPUs will be used. GPUs are not required for compilation.

Default OS tools alone are insufficient; the software above must be installable after handover.