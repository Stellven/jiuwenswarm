# Spark P4 matched benchmark

Across ten pairs per size, C3-direct returned the first token 0.02 seconds later at 512 tokens and 0.20 seconds sooner at 2048 tokens than same-budget stock A+ by the paired medians.

All admitted scopes passed the strict quiet preflight and every retained request boundary. The boundary process checks cannot observe activity that begins and ends between snapshots.

Intervals resample matched request repeats within the two fixed launch windows. They describe those launches and exclude between-launch variation.

A+ and C3-direct used the same 30,720 MiB budget, 30,682.35 MiB logged allocation and effective runtime settings.

## 512-token prompts

| Arm | Requests | TTFT median and range (s) | Decode median (tokens/s) | Engine prefill median (ms) | Source expert pages resident at request (median) |
| --- | ---: | ---: | ---: | ---: | ---: |
| A+ | 10 | 4.210 [3.514, 17.909] | 18.876 | 4138.769 | 42.9% |
| C3-direct | 10 | 4.155 [3.432, 13.074] | 20.237 | 4085.218 | 42.7% |

| Arm | Comparison | Estimate | Observed pair range | Pass medians | Conditional 95% interval |
| --- | --- | ---: | ---: | ---: | ---: |
| A+ | inverse ttft vs Aplus | 1.000 | unavailable | unavailable | 1.000, 1.000 |
| A+ | paired decode tps gained vs Aplus | 0.000 | 0.000, 0.000 | 0.000, 0.000 | 0.000, 0.000 |
| A+ | paired ttft seconds saved vs Aplus | -0.000 | -0.000, -0.000 | -0.000, -0.000 | -0.000, -0.000 |
| C3-direct | inverse ttft vs Aplus | 1.013 | unavailable | unavailable | 0.595, 2.585 |
| C3-direct | paired decode tps gained vs Aplus | 0.744 | -1.670, 10.067 | -0.032, 1.468 | -0.534, 1.459 |
| C3-direct | paired ttft seconds saved vs Aplus | -0.024 | -4.762, 8.959 | -0.327, 4.835 | -1.348, 2.423 |

## 2048-token prompts

| Arm | Requests | TTFT median and range (s) | Decode median (tokens/s) | Engine prefill median (ms) | Source expert pages resident at request (median) |
| --- | ---: | ---: | ---: | ---: | ---: |
| A+ | 10 | 14.356 [11.197, 22.362] | 17.485 | 14279.865 | 42.9% |
| C3-direct | 10 | 13.004 [10.696, 22.033] | 19.168 | 12931.706 | 42.8% |

| Arm | Comparison | Estimate | Observed pair range | Pass medians | Conditional 95% interval |
| --- | --- | ---: | ---: | ---: | ---: |
| A+ | inverse ttft vs Aplus | 1.000 | unavailable | unavailable | 1.000, 1.000 |
| A+ | paired decode tps gained vs Aplus | 0.000 | 0.000, 0.000 | 0.000, 0.000 | 0.000, 0.000 |
| A+ | paired ttft seconds saved vs Aplus | -0.000 | -0.000, -0.000 | -0.000, -0.000 | -0.000, -0.000 |
| C3-direct | inverse ttft vs Aplus | 1.104 | unavailable | unavailable | 0.875, 1.309 |
| C3-direct | paired decode tps gained vs Aplus | -0.201 | -2.862, 6.114 | -0.211, -0.191 | -1.414, 0.965 |
| C3-direct | paired ttft seconds saved vs Aplus | 0.199 | -6.552, 5.756 | -0.148, 2.160 | -1.719, 3.261 |

## Startup requests by position

Each pass began with the common file-specific source conditioning. Read and fault counts cover the engine process through the first token.

| Arm | Pass | Request position | Prompt tokens | Load to ready (s) | TTFT (s) | Decode (tokens/s) | Reads (GB) | Major faults |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A+ | 1 | 1 | 512 | 82.24 | 55.244 | 1.41 | 48.311 | 14,447 |
| A+ | 1 | 2 | 2048 | 82.24 | 96.676 | 3.83 | 20.671 | 21,167 |
| A+ | 1 | 3 | 512 | 82.24 | 30.363 | 3.70 | 4.862 | 5,796 |
| A+ | 1 | 4 | 2048 | 82.24 | 56.450 | 4.85 | 1.576 | 2,328 |
| A+ | 1 | 5 | 2048 | 82.24 | 32.058 | 21.26 | 0.342 | 807 |
| A+ | 1 | 6 | 512 | 82.24 | 7.089 | 5.96 | 0.128 | 215 |
| C3-direct | 1 | 1 | 512 | 86.14 | 39.419 | 1.52 | 30.344 | 12,957 |
| C3-direct | 1 | 2 | 2048 | 86.14 | 75.667 | 3.62 | 15.368 | 12,635 |
| C3-direct | 1 | 3 | 512 | 86.14 | 34.368 | 4.46 | 4.037 | 3,379 |
| C3-direct | 1 | 4 | 2048 | 86.14 | 51.297 | 6.69 | 2.956 | 5,544 |
| C3-direct | 1 | 5 | 2048 | 86.14 | 28.288 | 20.10 | 0.205 | 420 |
| C3-direct | 1 | 6 | 512 | 86.14 | 6.845 | 6.42 | 0.203 | 331 |
| C3-direct | 2 | 1 | 512 | 87.15 | 39.372 | 1.78 | 29.922 | 12,229 |
| C3-direct | 2 | 2 | 2048 | 87.15 | 75.417 | 4.29 | 17.038 | 13,937 |
| C3-direct | 2 | 3 | 512 | 87.15 | 27.576 | 4.23 | 4.724 | 4,308 |
| C3-direct | 2 | 4 | 2048 | 87.15 | 51.103 | 5.06 | 2.117 | 3,211 |
| C3-direct | 2 | 5 | 2048 | 87.15 | 32.574 | 21.51 | 0.139 | 327 |
| C3-direct | 2 | 6 | 512 | 87.15 | 6.181 | 5.03 | 0.019 | 43 |
| A+ | 2 | 1 | 512 | 76.15 | 51.433 | 1.51 | 43.424 | 12,644 |
| A+ | 2 | 2 | 2048 | 76.15 | 91.936 | 3.97 | 25.728 | 21,438 |
| A+ | 2 | 3 | 512 | 76.15 | 29.118 | 3.56 | 4.750 | 5,522 |
| A+ | 2 | 4 | 2048 | 76.15 | 57.205 | 5.94 | 2.314 | 4,154 |
| A+ | 2 | 5 | 2048 | 76.15 | 32.848 | 21.52 | 0.407 | 599 |
| A+ | 2 | 6 | 512 | 76.15 | 6.212 | 6.34 | 0.161 | 189 |

Direct-seed pass 1 uploaded 31,663,779,840 bytes in 12.416 s, with 0 failures and 0 fallbacks.

Direct-seed pass 2 uploaded 31,663,779,840 bytes in 12.517 s, with 0 failures and 0 fallbacks.

## Change within each measured launch

Last minus first measured position shows residual movement inside each launch. Exact request samples are retained.

| Arm | Pass | Prompt tokens | TTFT change (s) | Decode change (tokens/s) |
| --- | ---: | ---: | ---: | ---: |
| A+ | 1 | 512 | -6.022 | +2.378 |
| A+ | 1 | 2048 | -10.992 | +12.096 |
| C3-direct | 1 | 512 | -7.381 | +0.897 |
| C3-direct | 1 | 2048 | -5.783 | +8.383 |
| C3-direct | 2 | 512 | -9.642 | +2.600 |
| C3-direct | 2 | 2048 | -9.190 | +12.491 |
| A+ | 2 | 512 | -5.518 | +3.836 |
| A+ | 2 | 2048 | -6.414 | +7.533 |

## Load and memory by launch

| Arm | Pass | Load to ready (s) | Scope peak (GiB) | Host minimum available (GiB) |
| --- | ---: | ---: | ---: | ---: |
| A+ | 1 | 82.243 | 100.000 | 52.878 |
| C3-direct | 1 | 86.142 | 100.000 | 52.964 |
| C3-direct | 2 | 87.145 | 100.000 | 52.945 |
| A+ | 2 | 76.147 | 100.000 | 52.952 |

Source-page residency describes the external inode cache. Scope memory and GPU residency are separate quantities.

Native analysis `factory.spark_gap_analysis` version `1.6.0`, release `b05745ab9d48b6003cc0f036013ce0d480073d2a2be69fe3fa9f5db04efda198`.
