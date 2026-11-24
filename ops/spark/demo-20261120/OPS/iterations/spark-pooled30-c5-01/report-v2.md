# C5 and a separate flags-matched stock launch

Paired first-token time saved at 512 / 2048 tokens was +0.06 s / +0.08 s in the separate fixed-flags stock screen. Greedy output or reasoning differed at 2048 tokens.

The follow-up used one pristine A+30 stock launch with the C5 slot, context, checkpoint and batch arguments and the mapper gate unset. Both fixed-flags arms used the same actual bank allocation and request order. The original pooled package comparison remains below.

| Compared arms | Prompt | Paired TTFT saved s [range] | Paired decode gained tok/s [range] | Greedy parity |
| --- | ---: | ---: | ---: | --- |
| Flags-matched stock vs pooled A+30 | 512 | +3.044 [+0.941, +9.171] | +7.968 [+1.641, +15.107] | False |
| Flags-matched stock vs pooled A+30 | 2048 | +7.626 [+2.047, +23.904] | +4.646 [-0.229, +15.456] | True |
| C5 vs flags-matched stock | 512 | +0.061 [-0.057, +0.232] | -1.964 [-2.176, -1.030] | True |
| C5 vs flags-matched stock | 2048 | +0.084 [-0.444, +1.021] | -1.912 [-2.047, -1.413] | False |

Each row uses four measured request positions after two warmups per size. The original pooled controls contribute the same absolute request positions, including their third discarded request. Greedy parity checks both content and reasoning. The structured analysis retains all matched hashes and individual control comparisons.

Each flags-matched arm ran once. Report observed paired ranges and avoid confidence intervals.
The flags-versus-pool comparison describes the settings package and uses historical controls.
C5 versus flags-matched stock keeps settings constant. Any greedy divergence limits output-equivalent attribution.

## Absolute measured results

| Profile | Prompt | TTFT median [range] (s) | Decode median [range] (tok/s) |
| --- | ---: | ---: | ---: |
| C5 | 512 | 2.950 [2.933, 3.419] | 20.266 [20.222, 20.406] |
| A+30 C5 flags | 512 | 3.105 [2.976, 3.362] | 22.319 [21.257, 22.398] |
| Pooled A+30 | 512 | 6.126 [3.964, 12.533] | 14.351 [6.150, 20.758] |
| C5 | 2048 | 10.442 [10.318, 11.119] | 20.194 [20.079, 20.244] |
| A+30 C5 flags | 2048 | 10.585 [10.487, 11.408] | 22.082 [21.613, 22.219] |
| Pooled A+30 | 2048 | 18.208 [12.542, 35.313] | 17.482 [6.669, 21.843] |

## Greedy content and reasoning SHA-256

Each printed pair is content SHA-256 followed by reasoning SHA-256. The structured analysis retains the hashes for each individual measured request.

### 512 tokens

- C5 `c82284bfb8eb1b88ab4b2843a84b1e272f14e98a1f321da8f0ccbc09080f7bf8` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- A+30 with C5 flags `c82284bfb8eb1b88ab4b2843a84b1e272f14e98a1f321da8f0ccbc09080f7bf8` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- spark-p4-cache30-attribution:A+:1 `ca9f89c46a40f9bcbde19b09af6c0c06eea4fa91c84d4563192cf633405b10d5` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- spark-p4-cache30-attribution:A+:2 `ca9f89c46a40f9bcbde19b09af6c0c06eea4fa91c84d4563192cf633405b10d5` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- spark-p4-cache30-direct-seed:A+:1 `ca9f89c46a40f9bcbde19b09af6c0c06eea4fa91c84d4563192cf633405b10d5` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- spark-p4-cache30-direct-seed:A+:2 `ca9f89c46a40f9bcbde19b09af6c0c06eea4fa91c84d4563192cf633405b10d5` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`

### 2048 tokens

- C5 `2ac8494b9ea15ebbee245a1ba833412164a22e249620c3c4e7e2ee5a6721dbcb` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- A+30 with C5 flags `b2881b1b899ae178b31d75a78842b421df5c9773ad7775b04241afc7ba0b26a1` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- spark-p4-cache30-attribution:A+:1 `b2881b1b899ae178b31d75a78842b421df5c9773ad7775b04241afc7ba0b26a1` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- spark-p4-cache30-attribution:A+:2 `b2881b1b899ae178b31d75a78842b421df5c9773ad7775b04241afc7ba0b26a1` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- spark-p4-cache30-direct-seed:A+:1 `b2881b1b899ae178b31d75a78842b421df5c9773ad7775b04241afc7ba0b26a1` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- spark-p4-cache30-direct-seed:A+:2 `b2881b1b899ae178b31d75a78842b421df5c9773ad7775b04241afc7ba0b26a1` / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`

Observed competing CPU boundaries, C5 False, flags-matched stock True.

## Original pooled package screen

# C5 pooled A+30 screening

C5 and its single-slot, 4096-context, batch-2047 profile were screened as one package. C5 screened against four prior quiet A+30 scopes. Median paired differences at 512 tokens (+3.181 s TTFT saved, +6.004 tok/s gained) and 2048 tokens (+7.400 s TTFT saved, +2.734 tok/s gained). Greedy output or reasoning differed.

No competing CPU activity was observed at the sampled boundaries.

One prospective candidate scope was compared with four historical quiet controls. Differences are descriptive screening estimates.
Candidate per-size ordinal 3 aligns with the controls’ third discarded warmup. Ordinals 4–6 align with their first three measured requests.
The across-control range and warmup exclusion show sensitivity. A positive difference favors the candidate.
C5 and its explicit slot, context, checkpoints and batch settings form one package. The pooled stock scopes cannot isolate the mapper effect.

Greedy output or reasoning differs from the controls. Timing is descriptive.

The candidate logged 30,682.35 MiB. The four controls logged 30,682.35 MiB, 30,682.35 MiB, 30,682.35 MiB, 30,682.35 MiB.

Startup to first healthy response took 84.15 s. Host memory available stayed at or above 76.95 GiB. The capped scope recorded zero OOM events and 1,182 memory.max reclaim events.

## Mapper runtime settings and logical cuts

| Arm | Slots | Context | Batch | Ubatch | Requested bank MiB | Actual bank MiB | CPU miss share |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| C5 package | 1 | 4096 | 2047 | 512 | 30,720 | 30,682.35 | 0% |
| Pooled A+ | 4 | 1048576 | 2048 | 512 | 30,720 | 30,682.35 | 0% |

The candidate explicitly disables context checkpoints. The recorded launch artifact retains the full command.

The gate-on log recorded 18 layout decisions, 15,360 mapped rows and 0 bypasses across all requests, including warmups.

All 6 2048-token prompts logged the logical cuts 0–1536 and 1536–2048.

The logical cut markers do not measure physical dispatch counts.

Earlier matched-flags functional control `spark-pooled30-c5-01/history/spark-c5-functional/report.md` used the legacy ELF without a native bank. It reported greedy parity and zero mapper decisions. Its discarded timings do not estimate this repair’s effect.

## 512-token prompts

| Arm | TTFT median, range (s) | Decode median, range (tok/s) |
| --- | ---: | ---: |
| C5 | 2.950 [2.933, 3.419] | 20.266 [20.222, 20.406] |
| Pooled A+ | 6.126 [3.964, 12.533] | 14.351 [6.150, 20.758] |
| spark-p4-cache30-attribution:A+:1 | 6.482 [3.960, 11.565] | 14.917 [6.506, 21.549] |
| spark-p4-cache30-attribution:A+:2 | 7.540 [3.896, 13.502] | 13.413 [4.886, 19.962] |
| spark-p4-cache30-direct-seed:A+:1 | 5.771 [3.968, 9.535] | 15.081 [5.956, 22.218] |
| spark-p4-cache30-direct-seed:A+:2 | 9.067 [3.810, 17.909] | 14.161 [6.345, 19.967] |

| Control or sensitivity | Median TTFT saved (s) | Median decode gained (tok/s) |
| --- | ---: | ---: |
| Pooled by ordinal | +3.181 | +6.004 |
| spark-p4-cache30-attribution:A+:1 | +3.537 | +5.438 |
| spark-p4-cache30-attribution:A+:2 | +4.591 | +6.942 |
| spark-p4-cache30-direct-seed:A+:1 | +2.826 | +5.274 |
| spark-p4-cache30-direct-seed:A+:2 | +6.123 | +6.194 |
| Exclude third control warmup | +1.519 | +2.167 |

Across individual controls, median TTFT saved ranged from +2.826 to +6.123 s and median decode gained ranged from +5.274 to +6.942 tok/s.

## 2048-token prompts

| Arm | TTFT median, range (s) | Decode median, range (tok/s) |
| --- | ---: | ---: |
| C5 | 10.442 [10.318, 11.119] | 20.194 [20.079, 20.244] |
| Pooled A+ | 18.208 [12.542, 35.313] | 17.482 [6.669, 21.843] |
| spark-p4-cache30-attribution:A+:1 | 20.850 [11.069, 38.512] | 19.922 [6.099, 21.835] |
| spark-p4-cache30-attribution:A+:2 | 23.133 [12.139, 37.778] | 15.115 [6.551, 19.691] |
| spark-p4-cache30-direct-seed:A+:1 | 18.551 [12.945, 32.058] | 17.626 [8.552, 22.075] |
| spark-p4-cache30-direct-seed:A+:2 | 17.375 [15.255, 32.848] | 17.351 [6.788, 21.851] |

| Control or sensitivity | Median TTFT saved (s) | Median decode gained (tok/s) |
| --- | ---: | ---: |
| Pooled by ordinal | +7.400 | +2.734 |
| spark-p4-cache30-attribution:A+:1 | +10.042 | +0.293 |
| spark-p4-cache30-attribution:A+:2 | +12.325 | +5.101 |
| spark-p4-cache30-direct-seed:A+:1 | +7.742 | +2.590 |
| spark-p4-cache30-direct-seed:A+:2 | +6.567 | +2.865 |
| Exclude third control warmup | +5.102 | +6.598 |

Across individual controls, median TTFT saved ranged from +6.567 to +12.325 s and median decode gained ranged from +0.293 to +5.101 tok/s.

