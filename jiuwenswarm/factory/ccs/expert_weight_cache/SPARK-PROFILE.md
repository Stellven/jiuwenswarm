# Spark activation profile

These settings are a source-derived Spark validation profile. Hold the stock, candidate gate-unset and candidate gate-enabled flags matched for each comparison, and retain the effective settings, logs, output parity and counters. Run under the approved capped wrapper. The strict stock reference keeps its documented four-slot configuration.

| Capsule | Matched stock control and candidate flags | Gate-on evidence |
| --- | --- | --- |
| Cache | Strict A for all three, with native MoE cache disabled. A separate A+ triplet exercises the documented bypass. | `LLAMA_EXPERT_CACHE=1 LLAMA_EXPERT_CACHE_MIB=64`. Confirm effective mmap and CUDA selected-copy traffic, one active line and one stats line, positive leases, reuses and `bytes_copied_saved`, and peak within the admitted budget. Saved upload bytes are a counter, not total memory traffic or elapsed-time evidence. |
