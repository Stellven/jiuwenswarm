"""ifbench v0: reference benchmark package + profiling/telemetry adapter + token-probability script.

Design source: Inference Engine Layered Architecture, Benchmark and Profiling Plan, revision 3.
Scope: T1 collectors, engine /metrics scraping (T2 without code changes), the four core
benchmarks driven as external CLIs, a speed probe, a token budget estimate, the baseline engine's
token probabilities, a separate Nsight Systems profile pass (T2), and a coverage check of all 47
telemetry IDs. Engine-internal counters (T3) and Nsight Compute (admin only on the Spark) are not
collected.
"""
__version__ = "0.4.1"
