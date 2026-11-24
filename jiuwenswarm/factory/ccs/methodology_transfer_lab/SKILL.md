---
name: inference-methodology-transfer
description: Turn a pinned inference-system technique into a target-specific, one-variable experiment and interpret matched phase-separated measurements. Use for research intake and ablation design, not engine execution or automatic admission.
---

Use this whole package when an agent must decide whether a method from another
runtime deserves an implementation experiment. Read SOURCES.json for provenance
and EXAMPLES.json for native tool inputs; tools operate only on supplied JSON.

1. Inspect the primary repository or paper yourself. Record its revision, license,
   actual execution path, demonstrated model and hardware. A README claim is not
   a reproduced measurement. `assess_transfer` checks declarations, not truth.
2. Map assumptions to the target: Spark CPU/GPU allocations share physical RAM;
   PCIe-copy savings cannot be imported as measured Spark savings. Check model
   routing, packed formats, architecture-specific kernels and attention state.
3. Keep full-routing placement/scheduling in one lane. Expert skipping and new
   quantization require a separately declared approximation/quality lane.
4. Use `design_trial` for a single change and the cheapest discriminating test.
   Failure in a reference component is reason to repair it before a full model
   run. A trace-model gain is a hypothesis, not measured tokens/s.
5. Use `analyze_abba` only after retaining raw inputs, native timings, placement,
   outputs and cleanup evidence. Input hashes must bind complete token IDs;
   output hashes must bind token IDs and finish status. Compare prefill/decode
   separately. Preserve negative results and missing identity information.

The tools do not run models or admit jobs. Hand an agent-authored candidate to
the existing builder/lab path only within that task's frozen authority. Never
interpret this package's CPU checks as engine correctness certification.
