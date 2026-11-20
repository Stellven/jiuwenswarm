# C3 native cache cold and post-warmup lab

In exploratory screening, the 30-GiB stock A+ bank reached the first token sooner and decoded faster than fair Strata at both prompt sizes based on the five-request medians.

| Prompt | A+ 30 TTFT s | S TTFT s | A+ 30 decode tok/s | S decode tok/s | Paired A+ minus S TTFT s | Paired A+ minus S decode tok/s |
|---|---:|---:|---:|---:|---:|---:|
| 512 | 6.600 [5.316, 16.902] | 12.313 [10.175, 13.041] | 19.295 [9.797, 22.437] | 17.200 [13.400, 17.300] | -6.085 [-6.441, 6.727] | 4.818 [-7.503, 5.895] |
| 2048 | 14.111 [11.853, 34.145] | 26.807 [21.864, 30.614] | 17.263 [7.331, 21.691] | 17.100 [17.000, 17.200] | -12.929 [-18.182, 7.338] | 0.063 [-9.769, 4.591] |

The absolute and paired columns are medians and observed ranges. The 2048-token decode medians were 0.163 tok/s apart, with overlapping observed ranges. These two prompt lengths, generated outputs and launch settings define the scope of the comparison. The best documented settings across workloads remain unmeasured.

## C3 contribution against the same-budget A+ bank

| Budget | Tokens | C3 minus A+ TTFT s | C3 minus A+ decode tok/s | Paired TTFT deltas by position | Paired decode deltas by position |
|---|---:|---:|---:|---|---|
| 30 GiB | 512 | -2.794 [-8.128, 0.967] | -0.592 [-0.842, 1.931] | 7: -8.128, 10: -3.800, 11: +0.967, 14: -2.794, 15: -2.618 | 7: +1.584, 10: -0.842, 11: -0.630, 14: +1.931, 15: -0.592 |
| 30 GiB | 2048 | -1.018 [-12.188, 0.201] | 0.453 [-0.339, 3.243] | 8: -6.745, 9: -12.188, 12: -0.771, 13: +0.201, 16: -1.018 | 8: +0.198, 9: -0.339, 12: +3.243, 13: +0.453, 16: +1.506 |
| 60 GiB | 512 | -22.994 [-33.216, -19.131] | 1.039 [-0.980, 4.474] | 7: -22.994, 10: -20.002, 11: -24.418, 14: -19.131, 15: -33.216 | 7: +2.347, 10: -0.980, 11: +0.132, 14: +1.039, 15: +4.474 |
| 60 GiB | 2048 | -94.989 [-98.053, -85.460] | 1.765 [1.042, 2.607] | 8: -96.740, 9: -85.460, 12: -87.298, 13: -94.989, 16: -98.053 | 8: +2.268, 9: +2.607, 12: +1.042, 13: +1.765, 16: +1.149 |

Use these same-allocated-bank rows to assess the profile contribution. A-matched and S comparisons give engine and configuration context. A quiet mirrored ABBA protocol with ten measured repeats per prompt is planned without a co-running planner or build.


## Concurrent CPU lane exposure

The affected scope measurements are exploratory. Boundary receipts identify the owner-authorized JiuwenSwarm service on CPUs 12–19 while the capped model used CPUs 0–7. Shared storage and memory can still affect timing.

| Scope | Source conditioning | Launch | Request positions and observed boundaries | Recorded service units |
|---|---|---|---|---|
| C3-profile-on-speed-30720MiB | — | — | 4 (after), 5 (after+before), 6 (after+before), 7 (after+before), 8 (after+before), 9 (before) | spark-c3-iteration2-planner.service |
| Aplus-speed-30720MiB | observed | observed | 1 (after+before), 2 (after+before), 3 (after+before), 4 (after+before), 5 (after+before), 6 (after+before), 7 (after+before), 8 (after+before), 9 (after+before), 10 (after+before), 11 (after+before), 12 (before) | spark-c3-iteration2-do.service |
| Aplus-speed-61440MiB | observed | observed | 1 (after+before), 2 (after+before), 3 (after+before), 4 (after+before), 5 (after+before), 6 (after+before), 7 (after+before), 8 (after+before), 9 (before), 11 (after), 12 (after+before), 13 (after+before), 14 (after+before), 15 (after+before), 16 (after+before) | spark-c3-iteration2-direct-seed.service, spark-predictor-iteration2-decode.service, spark-predictor-iteration2-do.service |

Each observation names the PID, service cgroup and CPU affinity. Positions with an empty boundary observation can still overlap activity between snapshots. Repeat under the quiet mirrored protocol to confirm timing.
Authorization `spark-c3-native-cache/full/concurrent-screening.json` SHA256 `7444e8a61a54556e2ccf267385e3752d7603ca35ee89b500da9a55aede64ea60`.

## Launch and cache admission

| Arm | Launch to ready | Peak cgroup memory | Reclaim max events | Profile seeds | Initial upload |
|---|---:|---:|---:|---:|---:|
| A-matched-speed-30720MiB | 75.132 s | 100.00 GiB | 1039 | — | — |
| C3-profile-on-speed-61440MiB | 167.276 s | 100.00 GiB | 1241 | 7432 | 63.875 GB |
| S-fair-steady | 42.055 s | 22.25 GiB | 0 | — | — |
| C3-profile-on-speed-30720MiB | 113.189 s | 100.00 GiB | 1044 | 3686 | 31.664 GB |
| Aplus-speed-30720MiB | 81.145 s | 100.00 GiB | 1300 | — | — |
| Aplus-speed-61440MiB | 88.241 s | 100.00 GiB | 1228 | — | — |

The profile seeds the existing stock bank during startup. Initial seed upload is separate from demand refill traffic.

| Arm | Actual bank | Seed time | Demand upload | Native lookup hits / misses | Large-prefill D2D experts | Evictions |
|---|---:|---:|---:|---:|---:|---:|
| C3-profile-on-speed-61440MiB | 61401.18 MiB | 86.294 s | 12784.57 MiB | 133,944 / 1,559 | 396,975 | 1511 |
| C3-profile-on-speed-30720MiB | 30682.35 MiB | 26.167 s | 62075.57 MiB | 127,961 / 7,542 | 251,913 | 7494 |
| Aplus-speed-30720MiB | 30682.35 MiB | — | 70983.63 MiB | 126,880 / 8,623 | 242,229 | — |
| Aplus-speed-61440MiB | 61401.18 MiB | — | 33451.44 MiB | 131,427 / 4,076 | 261,903 | — |

## Request positions after conditioning

| Arm | Position | Prompt tokens | TTFT | Decode tok/s | Process reads / major faults to first token | Process reads / major faults afterward |
|---|---:|---:|---:|---:|---:|---:|
| A-matched-speed-30720MiB | 1 | 512 | 49.649 s | 2.71 | 30,794.727 MiB / 90,175 | 4,889.555 MiB / 25,287 |
| A-matched-speed-30720MiB | 2 | 2048 | 75.476 s | 2.75 | 4,118.836 MiB / 5,899 | 3,292.707 MiB / 39,973 |
| A-matched-speed-30720MiB | 3 | 512 | 31.853 s | 2.85 | 1,012.613 MiB / 3,000 | 1,341.738 MiB / 8,379 |
| A-matched-speed-30720MiB | 4 | 2048 | 18.976 s | 2.95 | 2.035 MiB / 3 | 3.949 MiB / 38 |
| A-matched-speed-30720MiB | 5 | 2048 | 12.092 s | 3.02 | 0.062 MiB / 1 | 0.000 MiB / 0 |
| A-matched-speed-30720MiB | 6 | 512 | 4.706 s | 3.00 | 0.000 MiB / 0 | 0.125 MiB / 1 |
| C3-profile-on-speed-61440MiB | 1 | 512 | 28.751 s | 3.50 | 21,339.000 MiB / 10,730 | 2,870.012 MiB / 1,591 |
| C3-profile-on-speed-61440MiB | 2 | 2048 | 75.111 s | 6.88 | 22,679.711 MiB / 33,590 | 1,345.848 MiB / 703 |
| C3-profile-on-speed-61440MiB | 3 | 512 | 22.972 s | 18.32 | 9,659.121 MiB / 11,847 | 11.762 MiB / 30 |
| C3-profile-on-speed-61440MiB | 4 | 2048 | 69.359 s | 21.27 | 11,262.422 MiB / 27,420 | 11.879 MiB / 28 |
| C3-profile-on-speed-61440MiB | 5 | 2048 | 60.909 s | 20.03 | 9,686.949 MiB / 26,585 | 11.879 MiB / 28 |
| C3-profile-on-speed-61440MiB | 6 | 512 | 23.667 s | 18.01 | 5,258.109 MiB / 9,942 | 11.617 MiB / 28 |
| S-fair-steady | 1 | 512 | 5.299 s | 9.80 | 7,152.832 MiB / 48 | 1,377.832 MiB / 10,956 |
| S-fair-steady | 2 | 2048 | 18.330 s | 14.80 | 7,955.207 MiB / 0 | 224.742 MiB / 1,833 |
| S-fair-steady | 3 | 512 | 7.302 s | 17.10 | 6,111.539 MiB / 0 | 1.449 MiB / 14 |
| S-fair-steady | 4 | 2048 | 22.584 s | 16.90 | 8,183.410 MiB / 0 | 1.781 MiB / 5 |
| S-fair-steady | 5 | 2048 | 25.069 s | 17.00 | 8,293.738 MiB / 0 | 0.270 MiB / 0 |
| S-fair-steady | 6 | 512 | 9.785 s | 17.00 | 6,343.242 MiB / 0 | 0.145 MiB / 2 |
| C3-profile-on-speed-30720MiB | 1 | 512 | 54.422 s | 1.50 | 26,094.375 MiB / 15,106 | 4,252.133 MiB / 2,459 |
| C3-profile-on-speed-30720MiB | 2 | 2048 | 79.823 s | 3.87 | 12,572.781 MiB / 12,523 | 1,411.312 MiB / 647 |
| C3-profile-on-speed-30720MiB | 3 | 512 | 32.434 s | 4.24 | 4,400.703 MiB / 4,069 | 1,470.891 MiB / 1,209 |
| C3-profile-on-speed-30720MiB | 4 | 2048 | 48.277 s | 5.70 | 1,903.855 MiB / 3,251 | 650.727 MiB / 840 |
| C3-profile-on-speed-30720MiB | 5 | 2048 | 29.724 s | 21.07 | 103.492 MiB / 231 | 6.137 MiB / 1 |
| C3-profile-on-speed-30720MiB | 6 | 512 | 9.194 s | 5.91 | 76.352 MiB / 116 | 48.441 MiB / 72 |
| Aplus-speed-30720MiB | 1 | 512 | 72.449 s | 1.13 | 44,476.043 MiB / 20,650 | 6,619.344 MiB / 4,644 |
| Aplus-speed-30720MiB | 2 | 2048 | 100.230 s | 3.67 | 21,833.602 MiB / 21,670 | 1,500.262 MiB / 871 |
| Aplus-speed-30720MiB | 3 | 512 | 30.295 s | 4.04 | 4,297.188 MiB / 5,788 | 1,628.512 MiB / 1,545 |
| Aplus-speed-30720MiB | 4 | 2048 | 52.374 s | 4.47 | 2,223.988 MiB / 3,919 | 609.598 MiB / 872 |
| Aplus-speed-30720MiB | 5 | 2048 | 31.342 s | 21.73 | 248.234 MiB / 600 | 5.973 MiB / 0 |
| Aplus-speed-30720MiB | 6 | 512 | 7.349 s | 6.80 | 186.973 MiB / 337 | 135.535 MiB / 251 |
| Aplus-speed-61440MiB | 1 | 512 | 49.801 s | 1.37 | 56,922.965 MiB / 13,730 | 14,959.621 MiB / 7,063 |
| Aplus-speed-61440MiB | 2 | 2048 | 125.146 s | 4.01 | 68,884.480 MiB / 48,837 | 3,605.141 MiB / 1,526 |
| Aplus-speed-61440MiB | 3 | 512 | 33.722 s | 19.65 | 25,752.219 MiB / 16,603 | 11.742 MiB / 30 |
| Aplus-speed-61440MiB | 4 | 2048 | 132.129 s | 19.65 | 43,146.418 MiB / 48,838 | 11.488 MiB / 29 |
| Aplus-speed-61440MiB | 5 | 2048 | 139.006 s | 19.12 | 39,749.211 MiB / 44,563 | 11.426 MiB / 28 |
| Aplus-speed-61440MiB | 6 | 512 | 41.671 s | 19.63 | 19,186.785 MiB / 16,026 | 11.680 MiB / 29 |

No sampled expert, Engram or dense pages were resident in either pack view immediately before each launch. Launch initialization can change residency before the first request.
Process counters come from one unchanged engine PID per launch. Resource snapshots span client request start to first token and first token to stream completion. The raw analysis retains cgroup file refaults and separate host NVMe counters. Host disk activity includes any other activity on the device.

## Cold positions matched by ordinal

| Candidate and control | Position | Tokens | TTFT saved | Decode gain | Reads / major faults avoided to first token | Greedy parity |
|---|---:|---:|---:|---:|---:|---|
| 30-GiB A+ stock bank versus fair Strata engine and pack | 1 | 512 | -67.150 s | -8.67 tok/s | -39.136 GB / -20,602 | diverged |
| 30-GiB A+ stock bank versus fair Strata engine and pack | 2 | 2048 | -81.900 s | -11.13 tok/s | -14.553 GB / -21,670 | diverged |
| 30-GiB A+ stock bank versus fair Strata engine and pack | 3 | 512 | -22.994 s | -13.06 tok/s | +1.902 GB / -5,788 | diverged |
| 30-GiB A+ stock bank versus fair Strata engine and pack | 4 | 2048 | -29.790 s | -12.43 tok/s | +6.249 GB / -3,919 | diverged |
| 30-GiB A+ stock bank versus fair Strata engine and pack | 5 | 2048 | -6.274 s | +4.73 tok/s | +8.436 GB / -600 | diverged |
| 30-GiB A+ stock bank versus fair Strata engine and pack | 6 | 512 | +2.436 s | -10.20 tok/s | +6.455 GB / -337 | diverged |
| 30-GiB profile versus the same-budget stock bank | 1 | 512 | +18.028 s | +0.37 tok/s | +19.275 GB / +5,544 | matched |
| 30-GiB profile versus the same-budget stock bank | 2 | 2048 | +20.407 s | +0.20 tok/s | +9.711 GB / +9,147 | matched |
| 30-GiB profile versus the same-budget stock bank | 3 | 512 | -2.139 s | +0.20 tok/s | -0.109 GB / +1,719 | matched |
| 30-GiB profile versus the same-budget stock bank | 4 | 2048 | +4.098 s | +1.24 tok/s | +0.336 GB / +668 | matched |
| 30-GiB profile versus the same-budget stock bank | 5 | 2048 | +1.618 s | -0.66 tok/s | +0.152 GB / +369 | matched |
| 30-GiB profile versus the same-budget stock bank | 6 | 512 | -1.845 s | -0.88 tok/s | +0.116 GB / +221 | matched |
| 60-GiB profile versus the same-budget stock bank | 1 | 512 | +21.050 s | +2.13 tok/s | +37.312 GB / +3,000 | matched |
| 60-GiB profile versus the same-budget stock bank | 2 | 2048 | +50.036 s | +2.87 tok/s | +48.449 GB / +15,247 | matched |
| 60-GiB profile versus the same-budget stock bank | 3 | 512 | +10.750 s | -1.33 tok/s | +16.875 GB / +4,756 | matched |
| 60-GiB profile versus the same-budget stock bank | 4 | 2048 | +62.769 s | +1.63 tok/s | +33.433 GB / +21,418 | matched |
| 60-GiB profile versus the same-budget stock bank | 5 | 2048 | +78.097 s | +0.91 tok/s | +31.523 GB / +17,978 | matched |
| 60-GiB profile versus the same-budget stock bank | 6 | 512 | +18.004 s | -1.61 tok/s | +14.605 GB / +6,084 | matched |
| 30-GiB profile and bank versus stock without a native bank | 1 | 512 | -4.772 s | -1.21 tok/s | +4.929 GB / +75,069 | diverged |
| 30-GiB profile and bank versus stock without a native bank | 2 | 2048 | -4.347 s | +1.12 tok/s | -8.865 GB / -6,624 | diverged |
| 30-GiB profile and bank versus stock without a native bank | 3 | 512 | -0.581 s | +1.39 tok/s | -3.553 GB / -1,069 | diverged |
| 30-GiB profile and bank versus stock without a native bank | 4 | 2048 | -29.301 s | +2.75 tok/s | -1.994 GB / -3,248 | diverged |
| 30-GiB profile and bank versus stock without a native bank | 5 | 2048 | -17.632 s | +18.06 tok/s | -0.108 GB / -230 | diverged |
| 30-GiB profile and bank versus stock without a native bank | 6 | 512 | -4.488 s | +2.91 tok/s | -0.080 GB / -116 | diverged |
| 60-GiB profile and bank versus stock without a native bank | 1 | 512 | +20.899 s | +0.79 tok/s | +9.915 GB / +79,445 | diverged |
| 60-GiB profile and bank versus stock without a native bank | 2 | 2048 | +0.365 s | +4.12 tok/s | -19.462 GB / -27,691 | diverged |
| 60-GiB profile and bank versus stock without a native bank | 3 | 512 | +8.881 s | +15.47 tok/s | -9.067 GB / -8,847 | diverged |
| 60-GiB profile and bank versus stock without a native bank | 4 | 2048 | -50.383 s | +18.33 tok/s | -11.807 GB / -27,417 | diverged |
| 60-GiB profile and bank versus stock without a native bank | 5 | 2048 | -48.817 s | +17.01 tok/s | -10.157 GB / -26,584 | diverged |
| 60-GiB profile and bank versus stock without a native bank | 6 | 512 | -18.961 s | +15.01 tok/s | -5.514 GB / -9,942 | diverged |
| 30-GiB profile versus fair Strata engine and pack | 1 | 512 | -49.123 s | -8.30 tok/s | -19.862 GB / -15,058 | diverged |
| 30-GiB profile versus fair Strata engine and pack | 2 | 2048 | -61.493 s | -10.93 tok/s | -4.842 GB / -12,523 | diverged |
| 30-GiB profile versus fair Strata engine and pack | 3 | 512 | -25.132 s | -12.86 tok/s | +1.794 GB / -4,069 | diverged |
| 30-GiB profile versus fair Strata engine and pack | 4 | 2048 | -25.692 s | -11.20 tok/s | +6.585 GB / -3,251 | diverged |
| 30-GiB profile versus fair Strata engine and pack | 5 | 2048 | -4.655 s | +4.07 tok/s | +8.588 GB / -231 | diverged |
| 30-GiB profile versus fair Strata engine and pack | 6 | 512 | +0.590 s | -11.09 tok/s | +6.571 GB / -116 | diverged |
| 60-GiB profile versus fair Strata engine and pack | 1 | 512 | -23.452 s | -6.30 tok/s | -14.875 GB / -10,682 | diverged |
| 60-GiB profile versus fair Strata engine and pack | 2 | 2048 | -56.781 s | -7.92 tok/s | -15.440 GB / -33,590 | diverged |
| 60-GiB profile versus fair Strata engine and pack | 3 | 512 | -15.670 s | +1.22 tok/s | -3.720 GB / -11,847 | diverged |
| 60-GiB profile versus fair Strata engine and pack | 4 | 2048 | -46.775 s | +4.37 tok/s | -3.229 GB / -27,420 | diverged |
| 60-GiB profile versus fair Strata engine and pack | 5 | 2048 | -35.841 s | +3.03 tok/s | -1.461 GB / -26,585 | diverged |
| 60-GiB profile versus fair Strata engine and pack | 6 | 512 | -13.882 s | +1.01 tok/s | +1.138 GB / -9,942 | diverged |

## Five post-warmup pairs

| Arm | Tokens | TTFT median [min, max] s | Decode median [min, max] tok/s | Last minus first TTFT / decode |
|---|---:|---:|---:|---:|
| A-matched-speed-30720MiB | 2048 | 12.051 [12.010, 12.548] | 3.011 [2.998, 3.030] | +0.497 s / +0.008 tok/s |
| A-matched-speed-30720MiB | 512 | 4.557 [4.550, 4.607] | 3.002 [2.997, 3.031] | -0.056 s / -0.033 tok/s |
| C3-profile-on-speed-61440MiB | 2048 | 63.520 [49.839, 69.472] | 21.262 [20.520, 21.479] | +19.633 s / -0.674 tok/s |
| C3-profile-on-speed-61440MiB | 512 | 23.886 [21.480, 27.926] | 20.364 [16.303, 21.356] | +6.446 s / -0.037 tok/s |
| S-fair-steady | 2048 | 26.807 [21.864, 30.614] | 17.100 [17.000, 17.200] | +8.750 s / +0.100 tok/s |
| S-fair-steady | 512 | 12.313 [10.175, 13.041] | 17.200 [13.400, 17.300] | +2.138 s / +3.800 tok/s |
| C3-profile-on-speed-30720MiB | 2048 | 13.341 [11.413, 21.958] | 18.769 [7.529, 21.827] | -6.900 s / +11.239 tok/s |
| C3-profile-on-speed-30720MiB | 512 | 5.892 [3.596, 8.774] | 20.879 [8.955, 21.845] | -5.178 s / +0.966 tok/s |
| Aplus-speed-30720MiB | 2048 | 14.111 [11.853, 34.145] | 17.263 [7.331, 21.691] | -12.626 s / +9.932 tok/s |
| Aplus-speed-30720MiB | 512 | 6.600 [5.316, 16.902] | 19.295 [9.797, 22.437] | -10.688 s / +3.142 tok/s |
| Aplus-speed-61440MiB | 2048 | 153.649 [146.578, 167.525] | 19.478 [18.818, 19.655] | +20.947 s / +0.445 tok/s |
| Aplus-speed-61440MiB | 512 | 44.747 [41.536, 61.142] | 19.009 [16.844, 19.325] | +16.668 s / -2.165 tok/s |

| Arm | Tokens | Process reads to first token (MiB) | Major faults to first token | Process reads afterward (MiB) | Major faults afterward |
|---|---:|---:|---:|---:|---:|
| A-matched-speed-30720MiB | 2048 | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] |
| A-matched-speed-30720MiB | 512 | 0.000 [0.000, 0.188] | 0.000 [0.000, 2.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] |
| C3-profile-on-speed-61440MiB | 2048 | 9077.891 [6260.219, 11529.289] | 24703.000 [8310.000, 27309.000] | 11.371 [10.980, 11.941] | 27.000 [27.000, 29.000] |
| C3-profile-on-speed-61440MiB | 512 | 2682.957 [2354.750, 5524.754] | 8044.000 [7938.000, 9116.000] | 11.234 [11.172, 12.484] | 27.000 [27.000, 34.000] |
| S-fair-steady | 2048 | 8560.609 [8555.277, 8560.766] | 0.000 [0.000, 0.000] | 0.199 [0.000, 3.355] | 0.000 [0.000, 0.000] |
| S-fair-steady | 512 | 6360.496 [6360.059, 6360.660] | 0.000 [0.000, 0.000] | 0.027 [0.000, 0.180] | 0.000 [0.000, 1.000] |
| C3-profile-on-speed-30720MiB | 2048 | 0.000 [0.000, 141.934] | 0.000 [0.000, 199.000] | 5.973 [0.000, 15.695] | 0.000 [0.000, 20.000] |
| C3-profile-on-speed-30720MiB | 512 | 0.000 [0.000, 28.758] | 0.000 [0.000, 45.000] | 0.000 [0.000, 33.203] | 0.000 [0.000, 58.000] |
| Aplus-speed-30720MiB | 2048 | 0.000 [0.000, 40.434] | 0.000 [0.000, 55.000] | 6.211 [0.000, 35.207] | 1.000 [0.000, 107.000] |
| Aplus-speed-30720MiB | 512 | 0.266 [0.000, 26.027] | 6.000 [0.000, 46.000] | 0.000 [0.000, 22.844] | 0.000 [0.000, 14.000] |
| Aplus-speed-61440MiB | 2048 | 38857.301 [33650.176, 43792.453] | 49072.000 [40441.000, 51109.000] | 11.879 [11.426, 11.941] | 29.000 [28.000, 30.000] |
| Aplus-speed-61440MiB | 512 | 13699.320 [8982.078, 18825.844] | 16570.000 [12255.000, 19112.000] | 11.742 [11.680, 11.742] | 30.000 [29.000, 30.000] |

| Candidate and control | Tokens | TTFT saved s | Decode gain tok/s | Greedy parity | Request positions with observed CPU-lane overlap |
|---|---:|---:|---:|---|---|
| 30-GiB A+ stock bank versus fair Strata engine and pack | 512 | 6.085 [-6.727, 6.441] | 4.818 [-7.503, 5.895] | diverged | 7, 10, 11 |
| 30-GiB A+ stock bank versus fair Strata engine and pack | 2048 | 12.929 [-7.338, 18.182] | 0.063 [-9.769, 4.591] | diverged | 8, 9, 12 |
| 30-GiB profile versus the same-budget stock bank | 512 | 2.794 [-0.967, 8.128] | -0.592 [-0.842, 1.931] | matched | 7, 10, 11 |
| 30-GiB profile versus the same-budget stock bank | 2048 | 1.018 [-0.201, 12.188] | 0.453 [-0.339, 3.243] | matched | 8, 9, 12 |
| 60-GiB profile versus the same-budget stock bank | 512 | 22.994 [19.131, 33.216] | 1.039 [-0.980, 4.474] | matched | 7, 11, 14, 15 |
| 60-GiB profile versus the same-budget stock bank | 2048 | 94.989 [85.460, 98.053] | 1.765 [1.042, 2.607] | matched | 8, 9, 12, 13, 16 |
| 30-GiB profile and bank versus stock without a native bank | 512 | -1.333 [-4.166, 0.956] | 17.848 [5.952, 18.847] | diverged | 7 |
| 30-GiB profile and bank versus stock without a native bank | 2048 | -1.309 [-9.903, 1.135] | 15.756 [4.525, 18.796] | diverged | 8, 9 |
| 60-GiB profile and bank versus stock without a native bank | 512 | -19.329 [-23.374, -16.873] | 17.362 [13.300, 18.325] | diverged | — |
| 60-GiB profile and bank versus stock without a native bank | 2048 | -51.488 [-56.924, -37.788] | 18.232 [17.521, 18.474] | diverged | — |
| 30-GiB profile versus fair Strata engine and pack | 512 | 6.636 [1.401, 9.235] | 4.188 [-8.345, 7.479] | diverged | 7 |
| 30-GiB profile versus fair Strata engine and pack | 2048 | 12.728 [3.551, 19.201] | 1.569 [-9.571, 4.727] | diverged | 8, 9 |
| 60-GiB profile versus fair Strata engine and pack | 512 | -12.219 [-15.613, -9.363] | 3.264 [-0.997, 7.956] | diverged | — |
| 60-GiB profile versus fair Strata engine and pack | 2048 | -36.422 [-41.381, -27.975] | 4.162 [3.520, 4.379] | diverged | — |

Ranges summarize the five observed paired positions within one launch per arm. Persistent movement across positions indicates residual warming or drift. Comparisons across cache budgets or Strata packs describe the named settings and engine differences. Greedy parity is reported separately. Retain mirrored launch replication for a causal performance decision.

## Source residency immediately before post-warmup requests

| Arm | Source view | Tokens | Sampled expert inode residence, median [min, max] % | Cgroup file memory, median [min, max] GiB |
|---|---|---:|---:|---:|
| A-matched-speed-30720MiB | llama | 2048 | 64.875 [64.837, 64.875] | 76.829 [76.749, 76.829] |
| A-matched-speed-30720MiB | llama | 512 | 64.875 [64.875, 64.875] | 76.829 [76.829, 76.829] |
| C3-profile-on-speed-61440MiB | llama | 2048 | 18.019 [17.956, 18.121] | 16.033 [15.168, 17.441] |
| C3-profile-on-speed-61440MiB | llama | 512 | 17.994 [17.727, 18.045] | 16.760 [14.648, 17.203] |
| S-fair-steady | strata | 2048 | 8.854 [7.469, 10.963] | 13.531 [11.703, 15.790] |
| S-fair-steady | strata | 512 | 9.146 [7.787, 11.280] | 13.911 [12.073, 16.337] |
| C3-profile-on-speed-30720MiB | llama | 2048 | 42.676 [42.434, 42.828] | 35.873 [35.848, 36.150] |
| C3-profile-on-speed-30720MiB | llama | 512 | 42.676 [42.460, 42.841] | 35.848 [35.817, 36.254] |
| Aplus-speed-30720MiB | llama | 2048 | 42.218 [41.672, 42.688] | 36.980 [36.795, 37.394] |
| Aplus-speed-30720MiB | llama | 512 | 42.218 [41.609, 42.676] | 36.945 [36.797, 37.562] |
| Aplus-speed-61440MiB | llama | 2048 | 17.880 [17.537, 18.248] | 19.005 [16.171, 19.483] |
| Aplus-speed-61440MiB | llama | 512 | 18.057 [17.862, 18.235] | 19.134 [15.112, 21.154] |

Expert residence estimates come from sampled pages of the named source inodes in the host page cache. Cgroup file memory comes from that scope’s memory.stat file field. Strata samples its own pack. Residency differences are observed at these boundaries, and a link to specific expert hits remains a hypothesis.
Planner input `spark-c3-native-cache/full/steady-source-residency.json` SHA256 `85c1dc0574b4ee61c44a159b674b24899e9f469987c3d455473568225f83af66` retains all sample values and exact artifact references.

## Greedy output checks

| Arm | Prompt tokens | Within-arm content and reasoning stability | Content SHA256 prefix |
|---|---:|---|---|
| A-matched-speed-30720MiB | 2048 | stable | `fbcc592f6770` |
| A-matched-speed-30720MiB | 512 | stable | `e7d866c0639c` |
| C3-profile-on-speed-61440MiB | 2048 | stable | `b2881b1b899a` |
| C3-profile-on-speed-61440MiB | 512 | stable | `ca9f89c46a40` |
| S-fair-steady | 2048 | stable | `ad42523685cf` |
| S-fair-steady | 512 | stable | `1dc4cb2ce81c` |
| C3-profile-on-speed-30720MiB | 2048 | stable | `b2881b1b899a` |
| C3-profile-on-speed-30720MiB | 512 | stable | `ca9f89c46a40` |
| Aplus-speed-30720MiB | 2048 | stable | `b2881b1b899a` |
| Aplus-speed-30720MiB | 512 | stable | `ca9f89c46a40` |
| Aplus-speed-61440MiB | 2048 | stable | `b2881b1b899a` |
| Aplus-speed-61440MiB | 512 | stable | `ca9f89c46a40` |

Cross-arm equality is shown in the paired tables. Timing comparisons use the actual generated sequences. Accuracy remains unmeasured.

## Strata engine prefill counters

Native engine log `spark-c3-native-cache/full/scopes/strata-steady-fair-01/engine.log` and parsed prefill counters `spark-c3-native-cache/full/scopes/strata-steady-fair-01/prefill-streaming.json` are retained separately from request process and NVMe snapshots.

The final logged 2048-token CUDA0 prefill streamed 1,530 experts from files and 4,547 from the layer cache. The engine reported 8.9 GB unbuffered and 4.4 GB through page cache, with 20365 ms of compute wait for reads.
I/O workers accumulated 119645 ms of activity across threads.

Worker times can overlap one another and other prefill work. The engine counters have their own boundaries and remain separate from client TTFT, process reads and GPU copies.

Source, cap, prompt, raw request phases, residency, model identities and build receipts are linked in the iteration record.
Native analysis and exact recomputation used release `acbed314bbdea04633841848fa2fdfca22459725e12b281a24f2f790337f9ea9`.
