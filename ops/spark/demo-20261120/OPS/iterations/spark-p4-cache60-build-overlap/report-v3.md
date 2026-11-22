# Spark P4 matched benchmark

Across ten pairs per size, C3 returned the first token 27.08 seconds sooner at 512 tokens and 92.07 seconds sooner at 2048 tokens than same-budget stock A+ by the paired medians.

All admitted scopes passed the strict quiet preflight and every retained request boundary. The boundary process checks cannot observe activity that begins and ends between snapshots.

Intervals resample matched request repeats within the two fixed launch windows. They describe those launches and exclude between-launch variation.

The initial reverse C3 launch completed all requests, but its cap monitor lost the final process-exit receipt during cgroup teardown. Its entire window was excluded. A prospectively recorded amendment repeated that C3 position from identical cold conditioning before the final A+ control. The ten pairs use four launches with complete cap receipts. The original window, memory trace and shutdown journals are retained as excluded evidence.

A+ and C3 used the same 61,440 MiB budget, 61,401.18 MiB logged allocation and effective runtime settings.

## 512-token prompts

| Arm | Requests | TTFT median and range (s) | Decode median (tokens/s) | Engine prefill median (ms) | Source expert pages resident at request (median) |
| --- | ---: | ---: | ---: | ---: | ---: |
| A+ | 10 | 49.936 [44.229, 55.721] | 20.357 | 49774.481 | 18.5% |
| C3 | 10 | 23.317 [22.363, 25.957] | 21.134 | 23159.028 | 18.2% |

| Arm | Comparison | Estimate | Observed pair range | Pass medians | Conditional 95% interval |
| --- | --- | ---: | ---: | ---: | ---: |
| A+ | inverse ttft vs Aplus | 1.000 | unavailable | unavailable | 1.000, 1.000 |
| A+ | paired decode tps gained vs Aplus | 0.000 | 0.000, 0.000 | 0.000, 0.000 | 0.000, 0.000 |
| A+ | paired ttft seconds saved vs Aplus | -0.000 | -0.000, -0.000 | -0.000, -0.000 | -0.000, -0.000 |
| C3 | inverse ttft vs Aplus | 2.142 | unavailable | unavailable | 1.975, 2.288 |
| C3 | paired decode tps gained vs Aplus | -0.183 | -2.407, 1.701 | -0.427, 1.464 | -0.347, 0.796 |
| C3 | paired ttft seconds saved vs Aplus | 27.082 | 19.974, 32.316 | 27.652, 26.511 | 23.890, 29.305 |

## 2048-token prompts

| Arm | Requests | TTFT median and range (s) | Decode median (tokens/s) | Engine prefill median (ms) | Source expert pages resident at request (median) |
| --- | ---: | ---: | ---: | ---: | ---: |
| A+ | 10 | 156.641 [141.100, 178.406] | 19.994 | 156467.285 | 18.2% |
| C3 | 10 | 65.004 [52.486, 75.287] | 21.072 | 64874.492 | 18.3% |

| Arm | Comparison | Estimate | Observed pair range | Pass medians | Conditional 95% interval |
| --- | --- | ---: | ---: | ---: | ---: |
| A+ | inverse ttft vs Aplus | 1.000 | unavailable | unavailable | 1.000, 1.000 |
| A+ | paired decode tps gained vs Aplus | 0.000 | 0.000, 0.000 | 0.000, 0.000 | 0.000, 0.000 |
| A+ | paired ttft seconds saved vs Aplus | -0.000 | -0.000, -0.000 | -0.000, -0.000 | -0.000, -0.000 |
| C3 | inverse ttft vs Aplus | 2.410 | unavailable | unavailable | 2.248, 2.684 |
| C3 | paired decode tps gained vs Aplus | -0.149 | -1.270, 1.937 | -0.167, 1.664 | -0.589, 1.135 |
| C3 | paired ttft seconds saved vs Aplus | 92.074 | 73.967, 125.921 | 101.498, 90.838 | 84.239, 100.558 |

## Startup requests by position

Each pass began with the common file-specific source conditioning. Read and fault counts cover the engine process through the first token.

| Arm | Pass | Request position | Prompt tokens | Load to ready (s) | TTFT (s) | Decode (tokens/s) | Reads (GB) | Major faults |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A+ | 1 | 1 | 512 | 81.17 | 50.175 | 1.42 | 59.858 | 13,762 |
| A+ | 1 | 2 | 2048 | 81.17 | 124.916 | 3.73 | 73.010 | 50,582 |
| A+ | 1 | 3 | 512 | 81.17 | 33.903 | 20.55 | 27.862 | 19,653 |
| A+ | 1 | 4 | 2048 | 81.17 | 134.634 | 20.75 | 43.571 | 50,079 |
| A+ | 1 | 5 | 2048 | 81.17 | 155.090 | 21.50 | 42.987 | 45,657 |
| A+ | 1 | 6 | 512 | 81.17 | 48.411 | 20.46 | 18.083 | 15,552 |
| C3 | 1 | 1 | 512 | 170.28 | 27.844 | 3.74 | 22.423 | 10,752 |
| C3 | 1 | 2 | 2048 | 170.28 | 65.130 | 6.70 | 17.897 | 23,365 |
| C3 | 1 | 3 | 512 | 170.28 | 28.754 | 20.70 | 9.024 | 11,590 |
| C3 | 1 | 4 | 2048 | 170.28 | 62.754 | 20.44 | 10.461 | 20,095 |
| C3 | 1 | 5 | 2048 | 170.28 | 62.453 | 21.48 | 12.517 | 27,642 |
| C3 | 1 | 6 | 512 | 170.28 | 21.105 | 21.35 | 5.705 | 7,795 |
| C3 | 2 | 1 | 512 | 176.30 | 29.159 | 3.63 | 22.267 | 10,650 |
| C3 | 2 | 2 | 2048 | 176.30 | 74.783 | 7.59 | 19.599 | 27,250 |
| C3 | 2 | 3 | 512 | 176.30 | 24.055 | 21.19 | 10.899 | 12,465 |
| C3 | 2 | 4 | 2048 | 176.30 | 76.383 | 17.79 | 11.449 | 26,800 |
| C3 | 2 | 5 | 2048 | 176.30 | 55.405 | 18.38 | 7.565 | 18,132 |
| C3 | 2 | 6 | 512 | 176.30 | 20.421 | 21.25 | 6.268 | 9,879 |
| A+ | 2 | 1 | 512 | 89.62 | 50.345 | 1.38 | 59.516 | 13,526 |
| A+ | 2 | 2 | 2048 | 89.62 | 124.297 | 4.20 | 74.492 | 50,959 |
| A+ | 2 | 3 | 512 | 89.62 | 37.819 | 19.49 | 23.595 | 16,656 |
| A+ | 2 | 4 | 2048 | 89.62 | 121.649 | 18.83 | 49.460 | 54,156 |
| A+ | 2 | 5 | 2048 | 89.62 | 147.005 | 19.38 | 37.932 | 43,462 |
| A+ | 2 | 6 | 512 | 89.62 | 43.730 | 18.88 | 19.148 | 15,031 |

## Change within each measured launch

Last minus first measured position shows residual movement inside each launch. Exact request samples are retained.

| Arm | Pass | Prompt tokens | TTFT change (s) | Decode change (tokens/s) |
| --- | ---: | ---: | ---: | ---: |
| A+ | 1 | 512 | -2.621 | +0.578 |
| A+ | 1 | 2048 | -11.895 | -0.883 |
| C3 | 1 | 512 | -0.683 | +0.024 |
| C3 | 1 | 2048 | +12.528 | -0.148 |
| C3 | 2 | 512 | +0.284 | +2.148 |
| C3 | 2 | 2048 | +4.505 | -0.637 |
| A+ | 2 | 512 | +1.829 | +0.412 |
| A+ | 2 | 2048 | -4.275 | -0.363 |

## Load and memory by launch

| Arm | Pass | Load to ready (s) | Scope peak (GiB) | Host minimum available (GiB) |
| --- | ---: | ---: | ---: | ---: |
| A+ | 1 | 81.174 | 100.000 | 22.463 |
| C3 | 1 | 170.284 | 100.000 | 22.436 |
| C3 | 2 | 176.302 | 100.000 | 22.513 |
| A+ | 2 | 89.616 | 100.000 | 22.343 |

Source-page residency describes the external inode cache. Scope memory and GPU residency are separate quantities.

Native analysis `factory.spark_gap_analysis` version `1.8.2`, release `e274e0871c0186c9ab8b8bcb2c3f4ba95405d0f8130d556c6cfcdd732df6ecc8`.

## Prospective final-control replacement

The closing stock pass in report-v2 overlapped builds. The owner declared its whole-scope replacement before the fresh control started. The three earlier admitted launches are reused. The orchestrator disclosed a concurrent idle-priority file pull. Its storage impact was not isolated.

At 512 tokens the paired median stock-minus-C3 difference before the first token was 9.89 GB read and 7,450 major faults.

At 2048 tokens the paired median stock-minus-C3 difference before the first token was 28.17 GB read and 18,910 major faults.
