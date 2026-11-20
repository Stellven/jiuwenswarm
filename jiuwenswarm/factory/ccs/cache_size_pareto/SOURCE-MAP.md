# Source map

The upstream files below were inspected at JiuwenSwarm commit
`1ebd3ee448264d51cbf03913c8875f82741d677d`. The digests pin the upstream
launch and native report contract used by the normalization adapter. The
capsule's own transport, analysis, verifier and tests are pinned in SHA256SUMS.

| Source | Role | SHA-256 |
| --- | --- | --- |
| `ops/spark/steady_requests.py` | Six discarded positions and ten measured positions, exact order, fixed prompts, and request boundaries | `dd9f622c2d43d9b6793355e670a3a5dae392ee8fd2e23612a90582c2f35b0628` |
| `ops/spark/report_residency_speed.py` | Match launch inputs, retain original raw receipts, run and verify native lab analysis | `ba73e8f611a2a87d70f0a8fad2e61b0a7e1a8b4eba587b3a016ccc13a19b94f0` |
| `jiuwenswarm/factory/ccs/spark_gap_analysis/residency_speed.py` | Assert matched configuration and capture actual bank, startup and request metrics | `af751a1c5570fd3ac58188749eb872c23710dcfce21edc7413d2add87e5160af` |
| `jiuwenswarm/factory/ccs/spark_gap_analysis/early_bracket.py` | Validate caps, launch identity, source conditioning and raw request evidence | `599c19d16a28ee26fdbe5345a4c69a606722aff9f4772742de5c21255a1c810b` |

The companion `ops/spark/report_cache_pareto.py` checks the original
analyze/verify packet and Store references and normalizes admitted receipts.
This capsule calculates only from the retained normalized rows. Partial runs,
warm-up pilots, analytical estimates, generated model names and the separate
stock A+ tuning sequence provide no timing rows for this analysis.
