# Evidence limits

- This demo multiplies numbers by two; it performs no inference.
- Synthetic loopback client timings are NOT inference-engine TTFT or token-rate
  evidence. They include transport, scheduling, JSON parsing, and client overhead.
- p50/p95 use nearest-rank percentiles of successful requests only. Empty workloads
  succeed with count zero, an empty series, and null percentile/runtime values.
- Failed requests yield partial results, possibly with zero successful requests.
- A ready endpoint confirms HTTP startup only, not scientific validity or quality.
- The image pins an OS/Python base; build_image.py must bind the built application
  ID. Base-image identity alone does not identify this service implementation.
- Published Docker bridge ports cannot enforce no-egress. The image service
  therefore declares network.request along with process.exec and network.listen.
- Runtime metadata is self-reported; no hardware or remote identity is attested.
- Workspace inventories skip dependency/cache directories and symbolic links.
  Counts cover at most max_files ordinary files (default 2000).
- Structured metadata covers at most 50 eligible files, each at most 1 MiB.
  Parser errors and missing optional YAML support are recorded per file.
- No contents are written into the inspected workspace. Retained artifacts live
  in host-managed output storage. Inventory metadata can still be sensitive.
- Passive methodology materials execute nothing. A request CC is a design input,
  never an implemented executable package.
