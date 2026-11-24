# Quantized kernel profile

## Build a source and weight inventory

Pin the checkout and compiled engine independently. Verify that the files in SOURCES.json match the named Git commits and record their digests. Use the retained matched-weight pack metadata to identify where IQ2_XXS and IQ4_NL occur. The report distinguishes expert matrices from Engram tensors and includes other routed expert formats in the denominator.

Read the actual device scheduler selection for routed matrix products, vector products and fallback. In llama.cpp, distinguish MMQ, MMVQ, eligible few-row MMQ, standalone format conversion, and quantized row gather. The ARM row-dot and compatible IQ4_NL packed routes have different eligibility. Record effective backend assignment, shape, flags and placement before claiming dispatch. In Strata, inspect native IQ kernels, the conditional linked ggml-cpu fallback and the Engram dequant path. The TQ source is adjacent code for different formats.

Invoke inventory and verify_inventory on the pinned pack index. The inventory has no measured time denominator.

## Attribute retained wall-clock operations

Acquire an explicitly approved CPU/GPU trace in a separate profiling window. Pair the exact model receipt and engine ELF identity with the trace, compiler/backend feature flags, engine configuration, request, instrumentation overhead control, and software/device clock synchronization receipt. Capture client request start, first emitted token and decode finish on the established common timeline. Keep actual prompt length, residency and warm-up aligned across engines. Keep instrumented requests separate from uninstrumented headline measurements.

Normalize a single capture as quant-kernel-spans/1 with engine, capture_id, engine_sha256, model_receipt_sha256, raw_trace_sha256, clock_receipt_sha256 and aligned_clock. The input carries windows with phase (ttft or decode) and start_ns/end_ns. Spans carry integer nanosecond endpoints, device (CPU, GPU, unknown), quant_type (IQ2_XXS, IQ4_NL, other, unknown), and operation (quant_matmul, dequant, fused_quant, activation_quant, transfer, other, unknown). Use completed GPU intervals on the shared timeline. Keep CPU activity per-thread for conversion, then take wall unions. Preserve unclassified spans and discarded requests in source evidence.

Attribute the complete fused launch as fused_quant. Do not split embedded unpack, weight dequant, dot product or fused epilogues using symbol names. Assign separate activation quantization and standalone dequant only where explicit labels and trace events establish the operation. Verify shape, format and backend against graph or engine instrumentation. Cache, copy, file-page stalls and launch/synchronization are separate scope.

Invoke profile and verify_profile. Clip spans to the request windows, union each category, report CPU/GPU overlap separately and retain unknown or absent spans. Cross-category shares can overlap. An uncovered interval can include other work or missing trace coverage. The normalized report is arithmetic verification against the pinned trace artifact. Review raw trace-to-span correlation independently before attaching measured attribution. Compare per-engine distributions only after matched collection. A builder decision requires evidence that the observed kernel fraction is material for that workload.
