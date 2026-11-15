---
name: gpu-kernel-lab
description: Evaluate route-preserving expert GEMV batching and CUDA shape choices.
---

Use the finite inline JSON tools in cc.yaml. Full inputs for every capability are in EXAMPLES.json. Read METHOD.md before applying results. Run `python3 verification.py` for reference checks; native experiments require the documented local build. Native tools execute only the fixed bundled binary, accept no paths, commands or network endpoints, and never compile on invocation. GPU benchmarking requires an idle measurement slot.

Results describe component experiments. They do not establish Strata integration, model throughput, whole-system RSS reduction or task quality.

Portable bundles contain source and retained JSON evidence, not executable native binaries. Build is a separate explicit operator action; a CC invocation never compiles. CPU-only verification does not grant GPU access.
