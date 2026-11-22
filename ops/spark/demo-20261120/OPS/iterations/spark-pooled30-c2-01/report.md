# C2 pooled A+30 screening

C2 placed three layer-27 projections on CUDA0. C2 screened against four prior quiet A+30 scopes. Median paired differences at 512 tokens (-0.144 s TTFT saved, +1.905 tok/s gained) and 2048 tokens (+1.193 s TTFT saved, +1.289 tok/s gained). Greedy output and reasoning matched.

No competing CPU activity was observed at the sampled boundaries.

One prospective candidate scope was compared with four historical quiet controls. Differences are descriptive screening estimates.
Candidate per-size ordinal 3 aligns with the controls’ third discarded warmup. Ordinals 4–6 align with their first three measured requests.
The across-control range and warmup exclusion show sensitivity. A positive difference favors the candidate.

The candidate logged 30,691.85 MiB. The four controls logged 30,682.35 MiB, 30,682.35 MiB, 30,682.35 MiB, 30,682.35 MiB.

Startup to first healthy response took 79.12 s. Host memory available stayed at or above 49.41 GiB. The capped scope recorded zero OOM events and 954 memory.max reclaim events.

Placement and its allocation/readback differences are part of the treatment. These timings describe the package.

## Placement readback

The v1 manual policy reports 117 other expert weights on CPU_Mapped. The tier-v2 path requires the native bank to be disabled.

| Tensor | Actual buffer | Payload bytes |
| --- | --- | ---: |
| blk.27.ffn_down_exps.weight | CUDA0 | 990,904,320 |
| blk.27.ffn_gate_exps.weight | CUDA0 | 1,309,409,280 |
| blk.27.ffn_up_exps.weight | CUDA0 | 1,309,409,280 |

## 512-token prompts

| Arm | TTFT median, range (s) | Decode median, range (tok/s) |
| --- | ---: | ---: |
| C2 | 6.921 [3.803, 9.324] | 16.787 [8.337, 22.136] |
| Pooled A+ | 6.126 [3.964, 12.533] | 14.351 [6.150, 20.758] |
| spark-p4-cache30-attribution:A+:1 | 6.482 [3.960, 11.565] | 14.917 [6.506, 21.549] |
| spark-p4-cache30-attribution:A+:2 | 7.540 [3.896, 13.502] | 13.413 [4.886, 19.962] |
| spark-p4-cache30-direct-seed:A+:1 | 5.771 [3.968, 9.535] | 15.081 [5.956, 22.218] |
| spark-p4-cache30-direct-seed:A+:2 | 9.067 [3.810, 17.909] | 14.161 [6.345, 19.967] |

| Control or sensitivity | Median TTFT saved (s) | Median decode gained (tok/s) |
| --- | ---: | ---: |
| Pooled by ordinal | -0.144 | +1.905 |
| spark-p4-cache30-attribution:A+:1 | -0.146 | +1.713 |
| spark-p4-cache30-attribution:A+:2 | +0.977 | +2.812 |
| spark-p4-cache30-direct-seed:A+:1 | -0.142 | +1.356 |
| spark-p4-cache30-direct-seed:A+:2 | +3.514 | +2.081 |
| Exclude third control warmup | +0.161 | +1.624 |

Across individual controls, median TTFT saved ranged from -0.146 to +3.514 s and median decode gained ranged from +1.356 to +2.812 tok/s.

## 2048-token prompts

| Arm | TTFT median, range (s) | Decode median, range (tok/s) |
| --- | ---: | ---: |
| C2 | 18.167 [11.994, 29.822] | 20.012 [8.981, 21.935] |
| Pooled A+ | 18.208 [12.542, 35.313] | 17.482 [6.669, 21.843] |
| spark-p4-cache30-attribution:A+:1 | 20.850 [11.069, 38.512] | 19.922 [6.099, 21.835] |
| spark-p4-cache30-attribution:A+:2 | 23.133 [12.139, 37.778] | 15.115 [6.551, 19.691] |
| spark-p4-cache30-direct-seed:A+:1 | 18.551 [12.945, 32.058] | 17.626 [8.552, 22.075] |
| spark-p4-cache30-direct-seed:A+:2 | 17.375 [15.255, 32.848] | 17.351 [6.788, 21.851] |

| Control or sensitivity | Median TTFT saved (s) | Median decode gained (tok/s) |
| --- | ---: | ---: |
| Pooled by ordinal | +1.193 | +1.289 |
| spark-p4-cache30-attribution:A+:1 | +2.683 | +0.125 |
| spark-p4-cache30-attribution:A+:2 | +4.050 | +2.337 |
| spark-p4-cache30-direct-seed:A+:1 | +0.964 | +0.406 |
| spark-p4-cache30-direct-seed:A+:2 | +2.372 | +1.159 |
| Exclude third control warmup | +0.548 | +2.311 |

Across individual controls, median TTFT saved ranged from +0.964 to +4.050 s and median decode gained ranged from +0.125 to +2.337 tok/s.

