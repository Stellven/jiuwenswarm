# C4 pooled A+30 screening

C4 screened against four prior quiet A+30 scopes. Median paired differences at 512 tokens (-1.908 s TTFT saved, -0.688 tok/s gained) and 2048 tokens (-2.779 s TTFT saved, -0.867 tok/s gained). Greedy output and reasoning matched.

Competing CPU activity was observed.

One prospective candidate scope was compared with four historical quiet controls. Differences are descriptive screening estimates.
Candidate per-size ordinal 3 aligns with the controls’ third discarded warmup. Ordinals 4–6 align with their first three measured requests.
The across-control range and warmup exclusion show sensitivity. A positive difference favors the candidate.

The candidate logged 30,682.35 MiB. The four controls logged 30,682.35 MiB, 30,682.35 MiB, 30,682.35 MiB, 30,682.35 MiB.

Startup to first healthy response took 94.13 s. Host memory available stayed at or above 50.64 GiB. The capped scope recorded zero OOM events and 1,041 memory.max reclaim events.

## 512-token prompts

| Arm | TTFT median, range (s) | Decode median, range (tok/s) |
| --- | ---: | ---: |
| C4 | 7.493 [4.810, 18.735] | 13.663 [5.083, 21.366] |
| Pooled A+ | 6.126 [3.964, 12.533] | 14.351 [6.150, 20.758] |
| spark-p4-cache30-attribution:A+:1 | 6.482 [3.960, 11.565] | 14.917 [6.506, 21.549] |
| spark-p4-cache30-attribution:A+:2 | 7.540 [3.896, 13.502] | 13.413 [4.886, 19.962] |
| spark-p4-cache30-direct-seed:A+:1 | 5.771 [3.968, 9.535] | 15.081 [5.956, 22.218] |
| spark-p4-cache30-direct-seed:A+:2 | 9.067 [3.810, 17.909] | 14.161 [6.345, 19.967] |

| Control or sensitivity | Median TTFT saved (s) | Median decode gained (tok/s) |
| --- | ---: | ---: |
| Pooled by ordinal | -1.908 | -0.688 |
| spark-p4-cache30-attribution:A+:1 | -1.910 | -1.248 |
| spark-p4-cache30-attribution:A+:2 | -2.071 | +0.801 |
| spark-p4-cache30-direct-seed:A+:1 | -1.964 | -0.862 |
| spark-p4-cache30-direct-seed:A+:2 | -1.089 | -0.498 |
| Exclude third control warmup | -3.458 | -0.331 |

Across individual controls, median TTFT saved ranged from -2.071 to -1.089 s and median decode gained ranged from -1.248 to +0.801 tok/s.

## 2048-token prompts

| Arm | TTFT median, range (s) | Decode median, range (tok/s) |
| --- | ---: | ---: |
| C4 | 24.545 [13.470, 38.122] | 15.236 [6.310, 21.033] |
| Pooled A+ | 18.208 [12.542, 35.313] | 17.482 [6.669, 21.843] |
| spark-p4-cache30-attribution:A+:1 | 20.850 [11.069, 38.512] | 19.922 [6.099, 21.835] |
| spark-p4-cache30-attribution:A+:2 | 23.133 [12.139, 37.778] | 15.115 [6.551, 19.691] |
| spark-p4-cache30-direct-seed:A+:1 | 18.551 [12.945, 32.058] | 17.626 [8.552, 22.075] |
| spark-p4-cache30-direct-seed:A+:2 | 17.375 [15.255, 32.848] | 17.351 [6.788, 21.851] |

| Control or sensitivity | Median TTFT saved (s) | Median decode gained (tok/s) |
| --- | ---: | ---: |
| Pooled by ordinal | -2.779 | -0.867 |
| spark-p4-cache30-attribution:A+:1 | -1.005 | -0.922 |
| spark-p4-cache30-attribution:A+:2 | -0.838 | +0.299 |
| spark-p4-cache30-direct-seed:A+:1 | -3.633 | -1.642 |
| spark-p4-cache30-direct-seed:A+:2 | -4.785 | -0.942 |
| Exclude third control warmup | -2.749 | -0.810 |

Across individual controls, median TTFT saved ranged from -4.785 to -0.838 s and median decode gained ranged from -1.642 to +0.299 tok/s.

## Decode readiness

Coverage `observed-issue` across 372 observed graph rows and 12 request IDs. 0 request IDs showed a completed prefetch consumed by demand.

| Counter | Value |
| --- | ---: |
| already resident | 15,879 |
| completed bytes | 759,767,040 |
| completed transfers | 96 |
| denied | 12,778 |
| duplicate | 0 |
| issued | 96 |
| issued bytes | 759,767,040 |
| late | 0 |
| miss | 5,145 |
| opportunities | 14,880 |
| pending | 0 |
| requested | 19,081 |
| reused | 47 |
| unknown | 0 |
| unused | 96 |
| useful bytes | 0 |
| useful ready | 0 |
| wasted bytes | 759,767,040 |
| demand hits | 84,135 |
| demand issued bytes | 44,265,922,560 |
| demand selected | 89,280 |

