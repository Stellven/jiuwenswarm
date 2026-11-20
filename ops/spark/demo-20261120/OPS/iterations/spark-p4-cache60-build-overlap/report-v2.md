# Spark P4 matched benchmark

Partially build-overlapped screening. Across ten pairs per size, C3 returned the first token 24.92 seconds sooner at 512 tokens and 90.80 seconds sooner at 2048 tokens than same-budget stock A+ by the paired medians.

Every launch passed quiet preflight. Two authorized builds overlapped the final A+ scope. The ten-pair result is descriptive screening. The boundary process checks cannot observe activity that begins and ends between snapshots.

Intervals resample matched request repeats within the two fixed launch windows. They describe those launches and exclude between-launch variation.

The initial reverse C3 launch completed all requests, but its cap monitor lost the final process-exit receipt during cgroup teardown. Its entire window was excluded. A prospectively recorded amendment repeated that C3 position from identical cold conditioning before the final A+ control. The ten pairs use four launches with complete cap receipts. The original window, memory trace and shutdown journals are retained as excluded evidence.

A+ and C3 used the same 61,440 MiB budget, 61,401.18 MiB logged allocation and effective runtime settings.

## 512-token prompts

| Arm | Requests | TTFT median and range (s) | Decode median (tokens/s) | Engine prefill median (ms) | Source expert pages resident at request (median) |
| --- | ---: | ---: | ---: | ---: | ---: |
| A+ | 10 | 47.966 [40.709, 55.721] | 21.444 | 47819.089 | 18.2% |
| C3 | 10 | 23.317 [22.363, 25.957] | 21.134 | 23159.028 | 18.2% |

| Arm | Comparison | Estimate | Observed pair range | Pass medians | Conditional 95% interval |
| --- | --- | ---: | ---: | ---: | ---: |
| A+ | inverse ttft vs Aplus | 1.000 | unavailable | unavailable | 1.000, 1.000 |
| A+ | paired decode tps gained vs Aplus | 0.000 | 0.000, 0.000 | 0.000, 0.000 | 0.000, 0.000 |
| A+ | paired ttft seconds saved vs Aplus | -0.000 | -0.000, -0.000 | -0.000, -0.000 | -0.000, -0.000 |
| C3 | inverse ttft vs Aplus | 2.057 | unavailable | unavailable | 1.943, 2.269 |
| C3 | paired decode tps gained vs Aplus | -0.411 | -2.487, 1.545 | -0.427, 0.818 | -2.141, 0.473 |
| C3 | paired ttft seconds saved vs Aplus | 24.915 | 18.062, 32.316 | 27.652, 22.348 | 23.119, 28.668 |

## 2048-token prompts

| Arm | Requests | TTFT median and range (s) | Decode median (tokens/s) | Engine prefill median (ms) | Source expert pages resident at request (median) |
| --- | ---: | ---: | ---: | ---: | ---: |
| A+ | 10 | 156.689 [134.757, 178.406] | 21.224 | 156545.048 | 18.0% |
| C3 | 10 | 65.004 [52.486, 75.287] | 21.072 | 64874.492 | 18.3% |

| Arm | Comparison | Estimate | Observed pair range | Pass medians | Conditional 95% interval |
| --- | --- | ---: | ---: | ---: | ---: |
| A+ | inverse ttft vs Aplus | 1.000 | unavailable | unavailable | 1.000, 1.000 |
| A+ | paired decode tps gained vs Aplus | 0.000 | 0.000, 0.000 | 0.000, 0.000 | 0.000, 0.000 |
| A+ | paired ttft seconds saved vs Aplus | -0.000 | -0.000, -0.000 | -0.000, -0.000 | -0.000, -0.000 |
| C3 | inverse ttft vs Aplus | 2.410 | unavailable | unavailable | 2.127, 2.697 |
| C3 | paired decode tps gained vs Aplus | -0.149 | -2.270, 1.919 | -0.167, 0.049 | -1.270, 0.334 |
| C3 | paired ttft seconds saved vs Aplus | 90.801 | 71.079, 125.921 | 101.498, 86.386 | 73.967, 100.235 |

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
| A+ | 2 | 1 | 512 | 83.16 | 48.392 | 1.38 | 59.660 | 13,939 |
| A+ | 2 | 2 | 2048 | 83.16 | 130.035 | 3.66 | 72.585 | 49,750 |
| A+ | 2 | 3 | 512 | 83.16 | 45.286 | 21.50 | 23.402 | 16,051 |
| A+ | 2 | 4 | 2048 | 83.16 | 148.241 | 21.25 | 40.276 | 45,955 |
| A+ | 2 | 5 | 2048 | 83.16 | 154.440 | 20.81 | 45.035 | 47,934 |
| A+ | 2 | 6 | 512 | 83.16 | 48.275 | 21.43 | 15.863 | 15,295 |

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
| A+ | 2 | 512 | -4.815 | -1.884 |
| A+ | 2 | 2048 | -23.387 | -2.506 |

## Load and memory by launch

| Arm | Pass | Load to ready (s) | Scope peak (GiB) | Host minimum available (GiB) |
| --- | ---: | ---: | ---: | ---: |
| A+ | 1 | 81.174 | 100.000 | 22.463 |
| C3 | 1 | 170.284 | 100.000 | 22.436 |
| C3 | 2 | 176.302 | 100.000 | 22.513 |
| A+ | 2 | 83.164 | 100.000 | 19.322 |

Source-page residency describes the external inode cache. Scope memory and GPU residency are separate quantities.

Native analysis `factory.spark_gap_analysis` version `1.8.0`, release `70ec6d82fffde1a81ab5a50ca0e2479f42d77678bb3b8c32e844fa8839dd833d`.

## Build exposure and quiet-only pairs

- `spark-owner-d-cpu.service` retained CPUs 12–19, nice 19 and idle I/O in its systemd properties.
- `spark-owner-c2-cpu.service` retained CPUs 12–19, nice 19 and idle I/O in its systemd properties.

| Build service invocation | Start UTC | Stop UTC in this run | Attempt |
|---|---|---|---|
| spark-owner-d-cpu.service | 2026-11-20T13:45:31.550698+00:00 | 2026-11-20T13:45:31.640578+00:00 | Preflight only |
| spark-owner-d-cpu.service | 2026-11-20T13:46:26.681790+00:00 | 2026-11-20T13:46:30.621806+00:00 | 51b98e442f1b4ba69cc7e879eb5b95c6 |
| spark-owner-d-cpu.service | 2026-11-20T13:48:29.851831+00:00 | Still active at GPU close | 87ecc8bf665f43729dd3a375a88699e3 |
| spark-owner-c2-cpu.service | 2026-11-20T13:46:07.028118+00:00 | 2026-11-20T13:46:11.413119+00:00 | 6e73a022cdac4b2ebd505b40c4a1acfb |
| spark-owner-c2-cpu.service | 2026-11-20T13:48:08.957594+00:00 | Still active at GPU close | ce1eef65da2341f59846b0c6bb7711a7 |
| spark-c2-placement-tier-build.service | 2026-11-20T13:45:29.860678+00:00 | 2026-11-20T13:45:34.025936+00:00 | 9f533251884a4a2eb9088d235398af91 |

The quiet-only subset ends at the first authorized preflight or build activity at 2026-11-20T13:45:29.860678+00:00. A request whose after-boundary crosses that cutoff stays in the screening set, including later gaps. The journal identifies active-service intervals. Boundary snapshots separately record visible compiler processes.

| Final A+ prompt | Repeat | Before UTC | After UTC | Intersecting service intervals | Compiler observed at boundary |
|---:|---:|---|---|---|---|
| 2048 | 7 | 2026-11-20T13:43:53.725005+00:00 | 2026-11-20T13:46:41.906715+00:00 | spark-c2-placement-tier-build.service, spark-owner-c2-cpu.service, spark-owner-d-cpu.service | None observed |
| 512 | 7 | 2026-11-20T13:46:41.982223+00:00 | 2026-11-20T13:47:30.394762+00:00 | None | None observed |
| 512 | 8 | 2026-11-20T13:47:30.467916+00:00 | 2026-11-20T13:48:25.424377+00:00 | spark-owner-c2-cpu.service | spark-owner-c2-cpu.service |
| 2048 | 8 | 2026-11-20T13:48:25.517402+00:00 | 2026-11-20T13:50:49.988538+00:00 | spark-owner-c2-cpu.service, spark-owner-d-cpu.service | spark-owner-c2-cpu.service, spark-owner-d-cpu.service |
| 2048 | 9 | 2026-11-20T13:50:50.060157+00:00 | 2026-11-20T13:53:15.776989+00:00 | spark-owner-c2-cpu.service, spark-owner-d-cpu.service | spark-owner-c2-cpu.service, spark-owner-d-cpu.service |
| 512 | 9 | 2026-11-20T13:53:15.858694+00:00 | 2026-11-20T13:54:01.788679+00:00 | spark-owner-c2-cpu.service, spark-owner-d-cpu.service | spark-owner-c2-cpu.service, spark-owner-d-cpu.service |
| 512 | 10 | 2026-11-20T13:54:01.864982+00:00 | 2026-11-20T13:54:44.890771+00:00 | spark-owner-c2-cpu.service, spark-owner-d-cpu.service | spark-owner-c2-cpu.service, spark-owner-d-cpu.service |
| 2048 | 10 | 2026-11-20T13:54:44.968216+00:00 | 2026-11-20T13:57:02.086020+00:00 | spark-owner-c2-cpu.service, spark-owner-d-cpu.service | spark-owner-c2-cpu.service, spark-owner-d-cpu.service |

| Prompt | Quiet-only repeat labels | Paired C3 TTFT saved s (range) | Paired C3 decode gained tok/s (range) |
|---:|---|---:|---:|
| 512 | 1, 2, 3, 4, 5, 6 | +26.796 [+23.160, +32.316] | -0.448 [-2.487, +0.127] |
| 2048 | 1, 2, 3, 4, 5, 6 | +100.235 [+73.967, +125.921] | -0.149 [-1.270, +0.605] |

Quiet-only rows give observed ranges. The ten-pair conditional bootstrap includes the build-overlapped reverse control and describes these run windows.

A separate agent reported a read-only text search lasting about 10 seconds within 13:48:23–13:51:25 UTC. That period is already in the screened portion. Its shared-I/O effect was not measured.

# 60 GiB C3 versus A+ request I/O and scope review

The ten measured pairs include the final A+ control with authorized build exposure. The timing and I/O comparisons are screening.

| Prompt | Pairs | A+ / C3 TTFT (s) | Paired C3 TTFT added (s) | A+ / C3 decode (tok/s) | Paired C3 decode gain (tok/s) |
|---:|---:|---:|---:|---:|---:|
| 512 | 10 | 47.966 / 23.317 | -24.915 [-28.668, -23.119] | 21.444 / 21.134 | -0.411 [-2.141, +0.473] |
| 2048 | 10 | 156.689 / 65.004 | -90.801 [-100.235, -73.967] | 21.224 / 21.072 | -0.149 [-1.270, +0.334] |

Timing brackets are conditional 95% intervals within the two mirrored launch windows.

## Scope safety

| Arm | Pass | Launch to ready (s) | Peak cap usage (GiB) | Minimum host available (GiB) | memory.events max | OOM events |
|---|---:|---:|---:|---:|---:|---:|
| A+ | 1 | 81.174 | 100.000 | 22.463 | 1,187 | 0 |
| C3 | 1 | 170.284 | 100.000 | 22.436 | 1,022 | 0 |
| C3 | 2 | 176.302 | 100.000 | 22.513 | 1,197 | 0 |
| A+ | 2 | 83.164 | 100.000 | 19.322 | 1,269 | 0 |

All scopes exited normally under the 100 GiB cap with swap disabled and CPU affinity 0–7.

## Ten measured pairs per prompt

| Prompt | Phase | Counter | A+ median [min, max] | C3 median [min, max] | Paired A+ minus C3 median [min, max] |
|---:|---|---|---:|---:|---:|
| 512 | Start to first token | Engine reads (GB) | 14.674 [11.074, 18.433] | 2.768 [2.099, 5.435] | 11.616 [8.451, 15.654] |
| 512 | Start to first token | Engine major faults | 14,649.0 [12,714.0, 18,308.0] | 8,399.5 [6,868.0, 9,910.0] | 7,054.0 [2,804.0, 10,270.0] |
| 512 | First token to stream end | Engine reads (GB) | 0.012 [0.011, 0.012] | 0.012 [0.011, 0.012] | 0.000 [-0.000, 0.001] |
| 512 | First token to stream end | Engine major faults | 29.0 [27.0, 31.0] | 27.0 [26.0, 30.0] | 2.0 [-1.0, 4.0] |
| 2048 | Start to first token | Engine reads (GB) | 40.581 [29.810, 49.055] | 10.091 [6.883, 11.139] | 29.904 [22.927, 41.588] |
| 2048 | Start to first token | Engine major faults | 45,247.0 [37,632.0, 55,163.0] | 26,119.0 [8,498.0, 30,234.0] | 18,510.0 [13,150.0, 29,551.0] |
| 2048 | First token to stream end | Engine reads (GB) | 0.012 [0.011, 0.013] | 0.012 [0.012, 0.013] | -0.000 [-0.001, 0.001] |
| 2048 | First token to stream end | Engine major faults | 29.0 [26.0, 31.0] | 28.0 [27.0, 32.0] | 1.5 [-5.0, 3.0] |

Positive paired values mean fewer reads or faults in C3. Ranges here are observed pair ranges. Process read_bytes counts I/O charged to the engine by Linux. GPU copies and host-wide disk counters have separate accounting.

## Startup after identical source conditioning

| Arm | Pass | Position | Tokens | TTFT (s) | Decode (tok/s) | Reads before / after first token (GB) | Major faults before / after |
|---|---:|---:|---:|---:|---:|---:|---:|
| A+ | 1 | 1 | 512 | 50.175 | 1.421 | 59.858 / 15.222 | 13,762 / 6,054 |
| A+ | 1 | 2 | 2048 | 124.916 | 3.731 | 73.010 / 3.610 | 50,582 / 1,559 |
| A+ | 1 | 3 | 512 | 33.903 | 20.550 | 27.862 / 0.012 | 19,653 / 29 |
| A+ | 1 | 4 | 2048 | 134.634 | 20.752 | 43.571 / 0.013 | 50,079 / 29 |
| A+ | 1 | 5 | 2048 | 155.090 | 21.500 | 42.987 / 0.012 | 45,657 / 29 |
| A+ | 1 | 6 | 512 | 48.411 | 20.460 | 18.083 / 0.012 | 15,552 / 30 |
| C3 | 1 | 1 | 512 | 27.844 | 3.739 | 22.423 / 2.762 | 10,752 / 1,133 |
| C3 | 1 | 2 | 2048 | 65.130 | 6.700 | 17.897 / 1.376 | 23,365 / 689 |
| C3 | 1 | 3 | 512 | 28.754 | 20.703 | 9.024 / 0.012 | 11,590 / 30 |
| C3 | 1 | 4 | 2048 | 62.754 | 20.444 | 10.461 / 0.012 | 20,095 / 27 |
| C3 | 1 | 5 | 2048 | 62.453 | 21.483 | 12.517 / 0.012 | 27,642 / 29 |
| C3 | 1 | 6 | 512 | 21.105 | 21.349 | 5.705 / 0.011 | 7,795 / 26 |
| C3 | 2 | 1 | 512 | 29.159 | 3.627 | 22.267 / 2.882 | 10,650 / 1,214 |
| C3 | 2 | 2 | 2048 | 74.783 | 7.585 | 19.599 / 1.482 | 27,250 / 719 |
| C3 | 2 | 3 | 512 | 24.055 | 21.192 | 10.899 / 0.012 | 12,465 / 27 |
| C3 | 2 | 4 | 2048 | 76.383 | 17.789 | 11.449 / 0.012 | 26,800 / 27 |
| C3 | 2 | 5 | 2048 | 55.405 | 18.379 | 7.565 / 0.011 | 18,132 / 25 |
| C3 | 2 | 6 | 512 | 20.421 | 21.251 | 6.268 / 0.011 | 9,879 / 24 |
| A+ | 2 | 1 | 512 | 48.392 | 1.375 | 59.660 / 15.589 | 13,939 / 6,248 |
| A+ | 2 | 2 | 2048 | 130.035 | 3.656 | 72.585 / 3.737 | 49,750 / 1,489 |
| A+ | 2 | 3 | 512 | 45.286 | 21.497 | 23.402 / 0.012 | 16,051 / 28 |
| A+ | 2 | 4 | 2048 | 148.241 | 21.255 | 40.276 / 0.012 | 45,955 / 28 |
| A+ | 2 | 5 | 2048 | 154.440 | 20.814 | 45.035 / 0.012 | 47,934 / 29 |
| A+ | 2 | 6 | 512 | 48.275 | 21.435 | 15.863 / 0.012 | 15,295 / 30 |

## Process I/O in the quiet-only paired subset

| Prompt | Pairs | Phase | Paired C3 reads avoided in GB [min, max] | Paired C3 major faults avoided [min, max] |
|---:|---:|---|---:|---:|
| 512 | 6 | Start to first token | 10.547 [9.454, 12.853] | 6,033.0 [2,804.0, 10,270.0] |
| 512 | 6 | First token to stream end | 0.000 [-0.000, 0.001] | 0.5 [-1.0, 3.0] |
| 2048 | 6 | Start to first token | 27.531 [22.927, 35.797] | 18,030.5 [13,150.0, 29,134.0] |
| 2048 | 6 | First token to stream end | -0.001 [-0.001, 0.001] | -1.5 [-5.0, 3.0] |

## Verified native-bank shutdown counters

| Arm | Pass | Small ubatch ≤8 hits | Small ubatch misses | CPU misses | Demand upload MiB | Large batch cache copies | Large batch device-to-device MiB |
|---|---:|---:|---:|---:|---:|---:|---:|
| A+ | 1 | 131,427 | 4,076 | 0 | 33,451.44 | 261,903 | 723,372.54 |
| C3 | 1 | 133,944 | 1,559 | 0 | 12,784.57 | 396,975 | 1,096,775.24 |
| C3 | 2 | 133,944 | 1,559 | 0 | 12,784.57 | 396,975 | 1,096,775.24 |
| A+ | 2 | 131,427 | 4,076 | 0 | 33,451.44 | 261,903 | 723,372.54 |

Counters cover the whole launch, including warmups. The small-ubatch category can include prefill and decode. Large-batch cache copies are device-local. Process read and fault counters use separate boundaries.

## Host file pages associated with actual C3 startup seeds


Both C3 passes admitted the same 7,432 experts and uploaded 63.875 GB at startup. The A+ comparison applies the same layer and expert IDs to its source pages.

| Arm | Pass | Post-ready seeded pages | Post-ready other expert pages | Excluded boundary draws |
|---|---:|---:|---:|---:|
| A+ | 1 | 16.54% (3,715 draws) | 18.13% (4,149 draws) | 11 |
| C3 | 1 | 34.06% (3,715 draws) | 5.11% (4,149 draws) | 11 |
| C3 | 2 | 33.83% (3,715 draws) | 4.87% (4,149 draws) | 11 |
| A+ | 2 | 16.66% (3,715 draws) | 18.32% (4,149 draws) | 11 |

| Arm | Prompt | Seeded before-request median [min, max] | Other before-request median [min, max] |
|---|---:|---:|---:|
| A+ | 512 | 18.35% [15.39%, 19.19%] (3,715 draws) | 17.82% [15.75%, 18.59%] (4,149 draws) |
| A+ | 2048 | 18.40% [15.95%, 18.81%] (3,715 draws) | 17.69% [15.67%, 18.54%] (4,149 draws) |
| C3 | 512 | 8.86% [8.31%, 9.30%] (3,715 draws) | 26.56% [25.92%, 26.93%] (4,149 draws) |
| C3 | 2048 | 9.05% [8.38%, 9.44%] (3,715 draws) | 26.55% [25.63%, 27.34%] (4,149 draws) |

The same deterministic page draws are weighted by their original stratum size and exclude slice-boundary pages. The JSON supplement retains all three post-warmup-pair observations per launch and separate cgroup/host evidence references. These estimates describe host file pages by startup admission class. Later evictions can change device-bank membership. Per-expert cache-hit causation remains unmeasured.


## Prospective scope replacement

The operator excluded `OPS/runs/p4-cache60-c3-pass-2-01` and named `OPS/runs/p4-cache60-c3-pass-2-retry-01` before its fresh launch.
Cap monitor read ENODEV as the cgroup vanished at shutdown. The process return code was not retained. Exclude the whole scope. The paired results use the fresh verified scope.
Amendment `spark-p4-cache60-build-overlap/raw/OPS/p4/cache-abba-60g-amendment.json@cb072674e5927e56b9a503a96ff4cef7b76b0f17ebe1002ed8297e09af6ed248` SHA256 `cb072674e5927e56b9a503a96ff4cef7b76b0f17ebe1002ed8297e09af6ed248`.


## Original native DO and build

Factory source task `spark-cache-residency-do-01` used original commit `ad2130b0126ad0c8f7ac33d966f828fc17f4528c`, source verifier call `c7981f3a-1d5b-4bbc-acb5-97326aeaec2a` and build attempt `32b595d1a67b489eb2fc8bc12ed985d5`.
The revision links the exact source decision, diff, verifier receipt, ELF manifest, and build receipts.


Native report `spark-p4-cache60-build-overlap/report.md` SHA256 `90341d85316b2df43f1edac3a76d3133ebc9d99d8ceb585c2dc7e2d7a780486a`.
Native verifier `spark-p4-cache60-build-overlap/verify-receipt.json` SHA256 `fdb49f102ad5b38ec320300329fac0268731944d5cae0118d4c75e6534fc989e`.
