# A-matched and fair Strata cold and post-warmup reference

After three warmups per size, fair Strata decoded the 512-token workload at a median 17.20 tokens per second and A-matched at 3.00.

## Launch and cap accounting

| Arm | Launch to ready | Peak cgroup memory | Reclaim max events |
|---|---:|---:|---:|
| A-matched-speed-30720MiB | 75.132 s | 100.00 GiB | 1039 |
| S-fair-steady | 42.055 s | 22.25 GiB | 0 |

## Request positions after conditioning

| Arm | Position | Prompt tokens | TTFT | Decode tok/s | Process reads / major faults to first token | Process reads / major faults afterward |
|---|---:|---:|---:|---:|---:|---:|
| A-matched-speed-30720MiB | 1 | 512 | 49.649 s | 2.71 | 30,794.727 MiB / 90,175 | 4,889.555 MiB / 25,287 |
| A-matched-speed-30720MiB | 2 | 2048 | 75.476 s | 2.75 | 4,118.836 MiB / 5,899 | 3,292.707 MiB / 39,973 |
| A-matched-speed-30720MiB | 3 | 512 | 31.853 s | 2.85 | 1,012.613 MiB / 3,000 | 1,341.738 MiB / 8,379 |
| A-matched-speed-30720MiB | 4 | 2048 | 18.976 s | 2.95 | 2.035 MiB / 3 | 3.949 MiB / 38 |
| A-matched-speed-30720MiB | 5 | 2048 | 12.092 s | 3.02 | 0.062 MiB / 1 | 0.000 MiB / 0 |
| A-matched-speed-30720MiB | 6 | 512 | 4.706 s | 3.00 | 0.000 MiB / 0 | 0.125 MiB / 1 |
| S-fair-steady | 1 | 512 | 5.299 s | 9.80 | 7,152.832 MiB / 48 | 1,377.832 MiB / 10,956 |
| S-fair-steady | 2 | 2048 | 18.330 s | 14.80 | 7,955.207 MiB / 0 | 224.742 MiB / 1,833 |
| S-fair-steady | 3 | 512 | 7.302 s | 17.10 | 6,111.539 MiB / 0 | 1.449 MiB / 14 |
| S-fair-steady | 4 | 2048 | 22.584 s | 16.90 | 8,183.410 MiB / 0 | 1.781 MiB / 5 |
| S-fair-steady | 5 | 2048 | 25.069 s | 17.00 | 8,293.738 MiB / 0 | 0.270 MiB / 0 |
| S-fair-steady | 6 | 512 | 9.785 s | 17.00 | 6,343.242 MiB / 0 | 0.145 MiB / 2 |

No sampled expert, Engram or dense pages were resident in either pack view immediately before each launch. Launch initialization can change residency before the first request.
Process counters come from one unchanged engine PID per launch. Resource snapshots span client request start to first token and first token to stream completion. The raw analysis retains cgroup file refaults and separate host NVMe counters. Host disk activity includes any other activity on the device.

## Cold positions matched by ordinal

| Candidate and control | Position | Tokens | TTFT saved | Decode gain | Reads / major faults avoided to first token | Greedy parity |
|---|---:|---:|---:|---:|---:|---|
| fair Strata engine and pack versus A-matched | 1 | 512 | +44.350 s | +7.09 tok/s | +24.790 GB / +90,127 | diverged |
| fair Strata engine and pack versus A-matched | 2 | 2048 | +57.146 s | +12.05 tok/s | -4.023 GB / +5,899 | diverged |
| fair Strata engine and pack versus A-matched | 3 | 512 | +24.551 s | +14.25 tok/s | -5.347 GB / +3,000 | diverged |
| fair Strata engine and pack versus A-matched | 4 | 2048 | -3.608 s | +13.95 tok/s | -8.579 GB / +3 | diverged |
| fair Strata engine and pack versus A-matched | 5 | 2048 | -12.977 s | +13.98 tok/s | -8.697 GB / +1 | diverged |
| fair Strata engine and pack versus A-matched | 6 | 512 | -5.079 s | +14.00 tok/s | -6.651 GB / +0 | diverged |

## Five post-warmup pairs

| Arm | Tokens | TTFT median [min, max] s | Decode median [min, max] tok/s | Last minus first TTFT / decode |
|---|---:|---:|---:|---:|
| A-matched-speed-30720MiB | 2048 | 12.051 [12.010, 12.548] | 3.011 [2.998, 3.030] | +0.497 s / +0.008 tok/s |
| A-matched-speed-30720MiB | 512 | 4.557 [4.550, 4.607] | 3.002 [2.997, 3.031] | -0.056 s / -0.033 tok/s |
| S-fair-steady | 2048 | 26.807 [21.864, 30.614] | 17.100 [17.000, 17.200] | +8.750 s / +0.100 tok/s |
| S-fair-steady | 512 | 12.313 [10.175, 13.041] | 17.200 [13.400, 17.300] | +2.138 s / +3.800 tok/s |

| Arm | Tokens | Process reads to first token (MiB) | Major faults to first token | Process reads afterward (MiB) | Major faults afterward |
|---|---:|---:|---:|---:|---:|
| A-matched-speed-30720MiB | 2048 | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] |
| A-matched-speed-30720MiB | 512 | 0.000 [0.000, 0.188] | 0.000 [0.000, 2.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] |
| S-fair-steady | 2048 | 8560.609 [8555.277, 8560.766] | 0.000 [0.000, 0.000] | 0.199 [0.000, 3.355] | 0.000 [0.000, 0.000] |
| S-fair-steady | 512 | 6360.496 [6360.059, 6360.660] | 0.000 [0.000, 0.000] | 0.027 [0.000, 0.180] | 0.000 [0.000, 1.000] |

| Candidate and control | Tokens | TTFT saved s | Decode gain tok/s | Greedy parity |
|---|---:|---:|---:|---|
| fair Strata engine and pack versus A-matched | 512 | -7.761 [-8.492, -5.568] | 14.202 [10.369, 14.303] | diverged |
| fair Strata engine and pack versus A-matched | 2048 | -14.753 [-18.066, -9.813] | 14.089 [14.002, 14.188] | diverged |

Ranges summarize the five observed paired positions within one launch per arm. Persistent movement across positions indicates residual warming or drift. Comparisons across cache budgets or Strata packs describe the named settings and engine differences. Greedy parity is reported separately. Retain mirrored launch replication for a causal performance decision.

## Greedy output checks

| Arm | Prompt tokens | Within-arm content and reasoning stability | Content SHA256 prefix |
|---|---:|---|---|
| A-matched-speed-30720MiB | 2048 | stable | `fbcc592f6770` |
| A-matched-speed-30720MiB | 512 | stable | `e7d866c0639c` |
| S-fair-steady | 2048 | stable | `ad42523685cf` |
| S-fair-steady | 512 | stable | `1dc4cb2ce81c` |

Cross-arm equality is shown in the paired tables. Timing comparisons use the actual generated sequences. Accuracy remains unmeasured.

## Strata engine prefill counters

Native engine log `spark-a-s-cold-steady/reference/scopes/strata-steady-fair-01/engine.log` and parsed prefill counters `spark-a-s-cold-steady/reference/scopes/strata-steady-fair-01/prefill-streaming.json` are retained separately from request process and NVMe snapshots.

The final logged 2048-token CUDA0 prefill streamed 1,530 experts from files and 4,547 from the layer cache. The engine reported 8.9 GB unbuffered and 4.4 GB through page cache, with 20365 ms of compute wait for reads.
I/O workers accumulated 119645 ms of activity across threads.

Worker times can overlap one another and other prefill work. The engine counters have their own boundaries and remain separate from client TTFT, process reads and GPU copies.

The paired measurements compare the two complete engine and pack configurations. The experiment used the same request order and host caps, and sampled both source packs after each file-specific reset. The startup and load paths differ between engines.

Source, cap, prompt, raw request phases, residency, model identities and build receipts are linked in the iteration record.
Native analysis and exact recomputation used release `4c486958fd4f149f194eebd642ef2a464adc7332a933ecc3d8179e532eb67309`.
