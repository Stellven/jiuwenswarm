# D pooled A+30 screening

D screened against four prior quiet A+30 scopes. Median paired differences at 512 tokens (-0.674 s TTFT saved, +0.530 tok/s gained) and 2048 tokens (-2.953 s TTFT saved, -0.648 tok/s gained). Greedy output and reasoning matched.

Competing CPU activity was observed.

One prospective candidate scope was compared with four historical quiet controls. Differences are descriptive screening estimates.
Candidate per-size ordinal 3 aligns with the controls’ third discarded warmup. Ordinals 4–6 align with their first three measured requests.
The across-control range and warmup exclusion show sensitivity. A positive difference favors the candidate.

The candidate logged 30,682.35 MiB. The four controls logged 30,682.35 MiB, 30,682.35 MiB, 30,682.35 MiB, 30,682.35 MiB.

Startup to first healthy response took 79.13 s. Host memory available stayed at or above 52.54 GiB. The capped scope recorded zero OOM events and 1,187 memory.max reclaim events.

Placement and its allocation/readback differences are part of the treatment. These timings describe the package.

## Runtime gate readbacks

The recorder wrote 17,040 of 17,040 events with 0 losses, 0 incomplete transfer records, and 1,373,036,875,776 submitted bytes. Trace status is `route-complete-as-recorded`.

Placement emitted 120 expert tensor readbacks among 1,043 assignments. CPU-equivalent placement verified for all 120 experts is true.

- Legacy expert cache reported 0 activation markers and 1 decline markers. native MoE cache enabled.
- Legacy demand predictor reported 0 activation markers and 1 decline markers. server requires one configured slot.
- Batch layout mapper reported 0 activation markers and 1 decline markers. multiple slots configured.
- The mapper emitted 0 changed cuts.

## 512-token prompts

| Arm | TTFT median, range (s) | Decode median, range (tok/s) |
| --- | ---: | ---: |
| D | 5.997 [4.533, 14.973] | 15.356 [6.552, 19.238] |
| Pooled A+ | 6.126 [3.964, 12.533] | 14.351 [6.150, 20.758] |
| spark-p4-cache30-attribution:A+:1 | 6.482 [3.960, 11.565] | 14.917 [6.506, 21.549] |
| spark-p4-cache30-attribution:A+:2 | 7.540 [3.896, 13.502] | 13.413 [4.886, 19.962] |
| spark-p4-cache30-direct-seed:A+:1 | 5.771 [3.968, 9.535] | 15.081 [5.956, 22.218] |
| spark-p4-cache30-direct-seed:A+:2 | 9.067 [3.810, 17.909] | 14.161 [6.345, 19.967] |

| Control or sensitivity | Median TTFT saved (s) | Median decode gained (tok/s) |
| --- | ---: | ---: |
| Pooled by ordinal | -0.674 | +0.530 |
| spark-p4-cache30-attribution:A+:1 | -0.676 | +0.146 |
| spark-p4-cache30-attribution:A+:2 | -0.837 | +1.176 |
| spark-p4-cache30-direct-seed:A+:1 | -0.672 | -0.020 |
| spark-p4-cache30-direct-seed:A+:2 | +1.193 | +0.539 |
| Exclude third control warmup | -1.268 | +0.658 |

Across individual controls, median TTFT saved ranged from -0.837 to +1.193 s and median decode gained ranged from -0.020 to +1.176 tok/s.

## 2048-token prompts

| Arm | TTFT median, range (s) | Decode median, range (tok/s) |
| --- | ---: | ---: |
| D | 22.976 [15.422, 29.906] | 15.683 [7.981, 21.030] |
| Pooled A+ | 18.208 [12.542, 35.313] | 17.482 [6.669, 21.843] |
| spark-p4-cache30-attribution:A+:1 | 20.850 [11.069, 38.512] | 19.922 [6.099, 21.835] |
| spark-p4-cache30-attribution:A+:2 | 23.133 [12.139, 37.778] | 15.115 [6.551, 19.691] |
| spark-p4-cache30-direct-seed:A+:1 | 18.551 [12.945, 32.058] | 17.626 [8.552, 22.075] |
| spark-p4-cache30-direct-seed:A+:2 | 17.375 [15.255, 32.848] | 17.351 [6.788, 21.851] |

| Control or sensitivity | Median TTFT saved (s) | Median decode gained (tok/s) |
| --- | ---: | ---: |
| Pooled by ordinal | -2.953 | -0.648 |
| spark-p4-cache30-attribution:A+:1 | -2.126 | -0.702 |
| spark-p4-cache30-attribution:A+:2 | +2.294 | +1.310 |
| spark-p4-cache30-direct-seed:A+:1 | -3.182 | -0.877 |
| spark-p4-cache30-direct-seed:A+:2 | -1.656 | -0.722 |
| Exclude third control warmup | -3.026 | -0.950 |

Across individual controls, median TTFT saved ranged from -3.182 to +2.294 s and median decode gained ranged from -0.877 to +1.310 tok/s.

