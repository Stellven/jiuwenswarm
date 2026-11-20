# C1 recorder functional iteration

The recorder product was produced by a JiuwenSwarm source session using the selected Satay round-2 evidence. The native build pilot produced the stock-matched Spark server under build attempt `3d4a835381364f5c9d2b62380ae3ecab`.

The capped DeepSeek 512-token probe produced the same greedy output hash with the recorder gate unset and set. The recorder wrote exactly 1,360 of 1,360 expected records, with zero lost, zero incomplete transfer records and zero failed dispatches. The retained analysis CC found 120 prefill events and 1,240 decode events. All 52,689,716,736 recorded selected-expert copy bytes were submitted during prefill. The run establishes functional capture under these settings. The capped single-pair probe ran alongside development activity, and no time comparison is eligible for the quiet benchmark. The historical Granite score reported a single missing prefill event. The Spark DeepSeek receipt does not resolve that separate fixture issue.

The measured prefill copies motivate the next cache and placement plans. In the transfer analysis, the frozen Strata top 32 per layer covered 45.50% of observed prefill picks and 16.90% of distinct per-dispatch expert unions. Route coverage does not predict savings. Require actual copies and bytes by memory path plus matched TTFT. Maintain a separate stock equivalent-placement control. Strict-A decode recorded no selected-expert transfers through this path, so this prefill copy hook provides no supported decode savings.

## Expert-copy replay and the next planner decision

Reconstructing copy geometry from the original mapped GGUF offsets matched the recorder's 52,689,716,736 submitted bytes. The replay issued 10,674 host-to-device calls across 40 groups on the NVIDIA GB10, driver 580.178.04. All positive groups were for one 507-row prefill microbatch across 40 layers. The other two prefill microbatches (1 and 4 rows) and all decode events submitted zero bytes at the observed hook.

The capped replay used the original pageable file mappings, one CUDA stream, a reused destination buffer and synchronization after each nonempty group. No model kernels ran alongside the replay.

| Replay pass | Elapsed time | Effective submitted bytes/s |
|---|---:|---:|
| 0 | 21.347 s | 2.468 GB/s |
| 1 | 42.993 s | 1.226 GB/s |
| 2 | 1.001 s | 52.621 GB/s |
| 3 | 1.000 s | 52.712 GB/s |

The analysis capsule used the measured later-pass median of 52.621 GB/s. Dividing 52.690 GB by that rate gives **1.001 s** of serialized replay-equivalent copy time, or **1.84%** of the single C1 gate-on request's 54.367 s TTFT. For scale only, 1.001 s is **10.3%** of the historical warm A median of 9.679 s. The same-prompt historical A repeat used for output parity took 5.188 s. C1 gate-off and gate-on were separate first requests, at 49.815 s and 54.367 s. Those times cannot isolate recorder overhead or a treatment effect.

The earlier replay passes had uncontrolled file residency and were much slower. Page faults, residency and synchronization are hypotheses for the spread. The replay does not measure the duration of C1's actual copies, their overlap with model kernels, critical-path stalls, or speedup from removing them. The recorder can change synchronization to capture routes, which adds uncertainty when applying these observations to stock. The relative 512-token replay numbers should not be transferred to 2048-token prompts without measurement.

1. Prioritize the expert weight cache and placement planner. Measure actual gate-on and gate-off bytes by path, unique expert demand, wait at first demand, cap headroom, parity and warm TTFT under the matched stock control. For CPU-expert placement conflicts, use an explicitly matched placement control. Check whether an effect remains against A+ once native calibration is complete. The replay motivates a residency and copy experiment without assuming raw transfer speed explains the entire TTFT gap.
2. Then test the batch layout mapper. At 512, the two small groups contained no expert copy bytes and there were no repeated large-copy dispatches per layer to deduplicate. At 2048, demonstrate changed cuts under an eligible matched profile and measure repeated expert copies across microbatches. Keep that activation profile distinguishable from strict A.
3. Use quiet mirrored launches for timing attribution. Compare two warmed launch windows per arm. The original C1 probe establishes functional parity and trace activity, with the independent authoritative Granite scorer still pending.

### Added evidence

- Exact copy replay `spark-c1-functional/copy-replay/bandwidth.json`, SHA256 `b86230e2c85e7bb4775e0c830b38d89bbcb2ca175fb37a529b9c3304ad45007e`.
- Verified copy timing analysis `routing-copy-timing-analysis-report.json`, SHA256 `a39424ca7b57e6e7f2ea6fc68b22b2b74d8359f685fe819c219647d670c4f209`, from `analysis.expert_routing_profile` v1.2.0, release `b7fa53d5c91345807b1372df359850a4c49d5f3c4b2d7bbdfaf0bfa3c1a454fa`.
- Replay plan `spark-c1-functional/copy-replay/c1-copy-replay-plan.json`, SHA256 `b4f9f69a8b121129d9fdb7e787ab2cf508df96a8954ff9e0c7eb34325c0e8456`; capped stop `spark-c1-functional/copy-replay/result.json`, SHA256 `569c8c08fcc42445c0819bd8e306d9c1b06b16d23fb882fb97f42128a9ef50d0`.
- Functional lab `spark-recorder-deepseek-01/lab.json`, SHA256 `bf2f9db6f3f187ff53072baa7b9b07f35a2c11530f7accf6202169c5a5a7c376`; its source references include both C1 requests, the historical parity request and the original trace.
- Historical A measurements and sources in the [P1 reference report](../spark-p1-reference-reconnaissance/report.md), SHA256 `71c3a2f25cfb217efaf4614101163a5c52aa5bab14a3add8ff8e8a6ba15ea115`.

## Independent Granite fixture checks

The frozen v4 scorer evaluated Work Order 1 against the same-host stock reference. Fixture SHA-256 is `a52205df70ad71f268af0690c07ce3e7bb4f148a8945e51115b9090558684bba`. The Spark amendment maps build and fixture provenance. Frozen stage predicates are preserved.

The capped scorer command exited with code 0. Applicable stage outcome is **pass**. The status below is the frozen scorer result from this Granite fixture.

| Stage | Status | Recorded reason |
| --- | --- | --- |
| S1 | pass | Checked and applied against pinned pristine source |
| S2 | pass | All 8 touched paths are allowed |
| S3 | pass | Built llama-server using the stock CUDA build recipe |
| S4 | pass | Both stock hashes matched and both logs were marker-free |
| S5 | pass | Both stock hashes matched and both logs had the required markers |
| S5L | pass | Both configs matched stock with the gate off and on and met the log checks |
| S6 | pass | Replay or placement comparison passed |
| S7 | skipped | Stage does not apply to this work order |

### S6 fixture event replay

| Fixture configuration | Retained records | Expected records | Reported loss |
| --- | ---: | ---: | ---: |
| C1 | 1151 | 1152 | 1 |
| C2 | 1151 | 1152 | 1 |

The fixture replay has accounted event loss. The capsule’s normal-run zero-loss condition remains open.

The DeepSeek trace outcome above came from a different capped functional request. The 1,360 retained DeepSeek events and its recorder summary are separate from the Granite scorer’s S6 replay and fixture counts.

Scope evidence records the 100 GiB memory limit and eight-CPU affinity. The retained wrapper termination reason is `normal exit`.
