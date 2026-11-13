# Reproducing a CC win on another machine

There are two different "wins". They travel very differently.

## 1. The `factory.builder` reuse win: reproduces on any host the factory runs on

It depends only on the factory repeating builds, not on the hardware.

**On a second Jetson Orin:**
1. Restore the sources from the v3 package.
2. Run the live check in `README.md`, steps a–d.

That takes about 15 min and no GPU, and it is the cheapest "same win, second machine" result.

**On a non-Jetson host:** `Builder._request` accepts only `target == "jetson-orin"`. A new target (recipe, base image, CUDA arch) has to be added to the builder capsule first. That is engineering work, not RSI.

## 2. The `engine.expert_streaming` speed win: reproduces only in the same memory regime

### Why it's specific to that regime

The 15.5% (J-OM13) exists because:
- the MoE model's expert weights (18.3 GiB) are larger than RAM (7.4 GiB) and are read from NVMe through mmap;
- experts run on the CPU (`-cmoe`), so decode waits on page faults;
- demand fill and predictive reads change how and when those reads happen.

On a machine where the model fits in RAM, there is nothing to fix, and the expected result is null.

### Options, cheapest first

**a. Another Jetson Orin Nano 8 GB (same code, same regime).**
- Restore the v3 package's source bundles.
- Use the same model (sha256 `707a55a8…4450`) and base image `nvcr.io/nvidia/l4t-cuda:12.6.11-runtime@sha256:49853e9f…`.
- Rebuild the plain and factory images (or `docker load` them).
- Rerun the J-OM13 spec (`siminfeng experiments/jetson/OM/J-OM13/spec.json`, 4 rounds, 64 tokens, about 40 min of lab time).

This is the most faithful reproduction.

**b. A bigger unified-memory box (DGX Spark, Strix Halo) with the same code.** Force the same regime instead of changing the model.
- Run the engine container with a memory cap below the model size, for example `docker run --memory=7g --memory-swap=7g …`. Under cgroup v2, page cache from the mmap'd model counts against the cap, so expert pages get evicted the way they do on Satay.
- Check that it worked: major faults per token and NVMe GiB per token should be similar to Satay's `nvme_gib_per_token_decode`.
- The alternative is a larger MoE model that really exceeds RAM.

The main branch of siminfeng is meant for exactly these unified-memory hosts (Jetson, Spark, Strix).

**c. An x86 host with a discrete GPU (siminfeng branch `origin/x86/c2-resume`).**
- The memory regime differs: weights cross PCIe, and the CPU-side experts use host DRAM.
- The patches may apply, but the builder target, contracts and tuning are all new work.

Treat it as a new experiment, not a reproduction.

### Rules that keep a second-host result honest

- **New host, new reference.** Greedy output bytes can differ across GPU architectures and CPUs. Freeze a fresh bare reference under a **new contract ID**, as AB.md requires. Don't reuse `7a154179…` or `cad62aa9…` unless the bytes actually match.
- **Measure noise first.** Run A/A rounds before any claim. Satay's noise doubled between 11 and 13 Nov, and the frozen gate's threshold depends on it. Pick rounds with the fallback evaluator's power numbers.
- **Report cache state.** Record start residency, and use a cold or warm protocol. J-OM13 was warm, with residency not recorded.
- **Never multiply ratios across hosts, and don't pool them with Satay's.**
