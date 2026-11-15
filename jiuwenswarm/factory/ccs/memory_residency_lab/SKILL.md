---
name: memory-residency-lab
description: Plan and independently replay scratch arena liveness reuse.
---

Use the finite inline JSON tools in cc.yaml. Full inputs for every capability are in EXAMPLES.json. Read METHOD.md before applying results. Run `python3 verification.py` for reference checks; native experiments require the documented local build. Native tools execute only the fixed bundled binary, accept no paths, commands or network endpoints, and never compile on invocation. GPU benchmarking requires an idle measurement slot.

Results describe component experiments. They do not establish Strata integration, model throughput, whole-system RSS reduction or task quality.

Portable bundles contain source and retained JSON evidence, not executable native binaries. Build is a separate explicit operator action; a CC invocation never compiles. CPU-only verification does not grant GPU access.

For portable RSI and CPU missions, prefer `plan`/`verify`. Record
`native_experiment` as an explicit unbuilt prerequisite when the native binary
is absent; do not fabricate a native run or compile during an active engine
measurement. Historical ROUND1.json remains separate evidence.
