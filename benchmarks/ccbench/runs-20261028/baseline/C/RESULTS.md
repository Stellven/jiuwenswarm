# Deterministic admission results

Means per repetition; brackets are percentile bootstrap 95% CIs over 10 paired repetitions (2,000 resamples). Fixed 14 defective and 2 correct candidates.

| Route | Defects admitted /14 | Defects rejected /14 | False rejections /2 | Consumer failures through detection | Restricted lag, uses |
|---|---:|---:|---:|---:|---:|
| CC | 0.00 [0.00, 0.00] | 14.00 [14.00, 14.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] |
| CC_THIN | 14.00 [14.00, 14.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 7.00 [6.60, 7.40] | 12.90 [12.50, 13.30] |
| SKILL | 7.00 [6.60, 7.40] | 7.00 [6.60, 7.40] | 0.00 [0.00, 0.00] | 7.00 [6.60, 7.40] | 12.90 [12.50, 13.30] |

Restricted lag = min(first failure use, 20); undetected is censored at 20; pre-admission rejection has zero consumer exposure. CC lag zero is containment/exposure accounting, not an observed failure time. Conditional observed skill lag = 5.80 uses; it excludes censored candidates and is selection-biased. All routes have zero failures strictly before detection under the immediate oracle assumption. The triggering wrong response counts as one delivered failure.

| Candidate | CC failing tests / run | Thin failing tests / run | Skill detected /10 | Mean first failure (detected only) | Mean capped lag |
|---|---:|---:|---:|---:|---:|
| calculate_reference | 0/220 | 0/20 | 0 | censored | 20.00 |
| calculate_absolute | 17/220 | 0/20 | 10 | 3.60 | 3.60 |
| calculate_float | 20/220 | 0/20 | 9 | 8.44 | 9.60 |
| calculate_boolean | 10/220 | 0/20 | 1 | 11.00 | 19.10 |
| calculate_unicode | 10/220 | 0/20 | 0 | censored | 20.00 |
| calculate_comma | 5/220 | 0/20 | 0 | censored | 20.00 |
| calculate_empty | 4/220 | 0/20 | 2 | 15.50 | 19.10 |
| calculate_truncate | 7/220 | 0/20 | 10 | 5.10 | 5.10 |
| table_normalize_reference | 0/50 | 0/2 | 0 | censored | 20.00 |
| table_normalize_numeric | 10/50 | 0/2 | 10 | 1.30 | 1.30 |
| table_normalize_sorted | 2/50 | 0/2 | 10 | 1.20 | 1.20 |
| table_normalize_boolean | 2/50 | 0/2 | 5 | 14.80 | 17.40 |
| table_normalize_float | 2/50 | 0/2 | 0 | censored | 20.00 |
| table_normalize_pad | 2/50 | 0/2 | 0 | censored | 20.00 |
| table_normalize_empty | 2/50 | 0/2 | 5 | 11.00 | 15.50 |
| table_normalize_strip | 2/50 | 0/2 | 8 | 5.88 | 8.70 |

CC and thin decisions occur before consumer use. Skill admission means no observed failure during its probation. Thin post-admission observation uses the same streams and has the same failure exposure as the skill route, but does not retroactively change its pre-admission decision.
