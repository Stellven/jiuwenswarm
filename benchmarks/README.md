# AI4Research benchmarks

Start with the [benchmark README](harbor_suite/README.md) for the included
10-case ZIP, setup, execution, results and plain-Codex comparison instructions.
All 69 variants are development material, not held-out evaluation data.

The older [two-case pilot](harbor_pilot/README.md) documents the original runner
bridge; use the ten-case suite for current benchmarking.

For native Pipeline02 cache-study and protected fault execution, see
[isolated deployment instructions](../deploy/m1/PIPELINE02-ISOLATED.md).
The cache protocol retains per-trace request counts and independently scores
miss ratio; fault evidence comes from the native app and root controller.
