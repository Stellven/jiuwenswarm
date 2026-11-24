# Spark P4 matched benchmark

P4 measured 2 arms in two mirrored launches with ten timed requests per arm at each prompt size. First-token latency and decode throughput are reported separately.

All admitted scopes passed the strict quiet preflight and every retained request boundary. The boundary process checks cannot observe activity that begins and ends between snapshots.

Intervals resample matched request repeats within the two fixed launch windows. They describe those launches and exclude between-launch variation.

A+ and C3 used the same 30,720 MiB budget, 30,682.35 MiB logged allocation and effective runtime settings.

## 512-token prompts

| Arm | Requests | TTFT median and range (s) | Decode median (tokens/s) | Engine prefill median (ms) | Source expert pages resident at request (median) |
| --- | ---: | ---: | ---: | ---: | ---: |
| A+ | 10 | 3.928 [3.461, 13.502] | 19.156 | 3856.725 | 42.7% |
| C3 | 10 | 6.804 [3.536, 16.305] | 20.226 | 6734.037 | 42.8% |

| Arm | Comparison | Estimate | Observed pair range | Pass medians | Conditional 95% interval |
| --- | --- | ---: | ---: | ---: | ---: |
| A+ | inverse ttft vs Aplus | 1.000 | unavailable | unavailable | 1.000, 1.000 |
| A+ | paired decode tps gained vs Aplus | 0.000 | 0.000, 0.000 | 0.000, 0.000 | 0.000, 0.000 |
| A+ | paired ttft seconds saved vs Aplus | -0.000 | -0.000, -0.000 | -0.000, -0.000 | -0.000, -0.000 |
| C3 | inverse ttft vs Aplus | 0.577 | unavailable | unavailable | 0.357, 0.934 |
| C3 | paired decode tps gained vs Aplus | 0.192 | -9.693, 2.613 | -0.120, 1.362 | -4.232, 1.729 |
| C3 | paired ttft seconds saved vs Aplus | -1.184 | -11.852, 4.032 | -0.128, -3.111 | -6.843, 1.531 |

## 2048-token prompts

| Arm | Requests | TTFT median and range (s) | Decode median (tokens/s) | Engine prefill median (ms) | Source expert pages resident at request (median) |
| --- | ---: | ---: | ---: | ---: | ---: |
| A+ | 10 | 11.916 [10.692, 28.393] | 19.225 | 11841.281 | 42.7% |
| C3 | 10 | 19.877 [11.142, 30.585] | 16.193 | 19801.588 | 42.8% |

| Arm | Comparison | Estimate | Observed pair range | Pass medians | Conditional 95% interval |
| --- | --- | ---: | ---: | ---: | ---: |
| A+ | inverse ttft vs Aplus | 1.000 | unavailable | unavailable | 1.000, 1.000 |
| A+ | paired decode tps gained vs Aplus | 0.000 | 0.000, 0.000 | 0.000, 0.000 | 0.000, 0.000 |
| A+ | paired ttft seconds saved vs Aplus | -0.000 | -0.000, -0.000 | -0.000, -0.000 | -0.000, -0.000 |
| C3 | inverse ttft vs Aplus | 0.600 | unavailable | unavailable | 0.514, 0.902 |
| C3 | paired decode tps gained vs Aplus | 0.031 | -8.730, 1.811 | -0.032, 0.577 | -3.803, 1.018 |
| C3 | paired ttft seconds saved vs Aplus | -2.844 | -13.626, 2.879 | -0.414, -3.495 | -8.446, -1.077 |

## Change within each measured launch

Last minus first measured position shows residual movement inside each launch. Exact request samples are retained.

| Arm | Pass | Prompt tokens | TTFT change (s) | Decode change (tokens/s) |
| --- | ---: | ---: | ---: | ---: |
| A+ | 1 | 512 | -8.090 | +3.773 |
| A+ | 1 | 2048 | -15.137 | +14.564 |
| C3 | 1 | 512 | -4.840 | +1.039 |
| C3 | 1 | 2048 | -11.962 | +13.581 |
| C3 | 2 | 512 | -2.867 | +2.233 |
| C3 | 2 | 2048 | -5.427 | +4.502 |
| A+ | 2 | 512 | -10.040 | +1.865 |
| A+ | 2 | 2048 | -7.182 | +12.208 |

## Load and memory by launch

| Arm | Pass | Load to ready (s) | Scope peak (GiB) | Host minimum available (GiB) |
| --- | ---: | ---: | ---: | ---: |
| A+ | 1 | 82.201 | 100.000 | 52.967 |
| C3 | 1 | 107.211 | 100.000 | 52.953 |
| C3 | 2 | 105.458 | 100.000 | 52.713 |
| A+ | 2 | 85.197 | 100.000 | 52.957 |

Source-page residency describes the external inode cache. Scope memory and GPU residency are separate quantities.

Native analysis `factory.spark_gap_analysis` version `1.6.0`, release `b05745ab9d48b6003cc0f036013ce0d480073d2a2be69fe3fa9f5db04efda198`.
