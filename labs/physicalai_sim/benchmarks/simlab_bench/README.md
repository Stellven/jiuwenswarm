# SIMLAB-Bench (phase 1: families F1 and F5)

SIMLAB's own benchmark cases, in the team's Harbor case format (`benchmarks/harbor_suite/AUTHORING.md` at the repository root). Source: SIMLAB test plan, "SIMLAB-Bench families" and "Test benches" (`missions/PAS-M1/source/Verification/benchmark-and-test-plan.md`).

| Family | Cases | Oracle |
|---|---|---|
| F1 Known-answer physics | `f1-tb01-pendulum` to `f1-tb09-determinism` (TB-01 to TB-09) | Analytic formulas, an independent RK4 reference (TB-06), identity (TB-09) |
| F5 Agreement | `f5-replay` (replay on the same machine and build) | Identity |

Each case directory holds `case.json` (objective, inputs, grading, primary metric, variants, references, engine version), `public/` (the scene and the experiment template the harness builds through SIMLAB's tools), `referee/criteria.json` (expected values and frozen tolerances, each with its reason; `confirm: true` marks a tolerance the source does not give, proposed by the coding agent and awaiting the owner), a stdlib-only `oracle.py`, `test_oracle.py` and `README.md`. Expected values live only in `referee/` (B12). Held-out cases are never in this repository (`.gitignore`).

## Running

```sh
simlab bench freeze --release <id>                         # SHA-256 manifest of every case file; refuses to overwrite
simlab bench run --family F1 --profile campaign --release <id> --output benchmarks/reports/<YYYYMMDD>/
simlab bench run --profile smoke --output /tmp/smoke         # wiring check only: first variant, one repeat
simlab bench speed --output benchmarks/reports/<YYYYMMDD>/speed.json
simlab bench admit --report <report dir>                     # registry: MuJoCo admitted only from a passing F1 campaign
```

The harness builds every variant through the Python client (the same operations as the MCP server and the CLI), takes a hardware inventory before each run (B17), keeps failed runs and never retries (B08), exports SIMLAB's own records as evidence, and grades each cell with the case's oracle in a separate isolated interpreter (B05). A negative-control variant counts as PASS only when its oracle reports a failure. Reports are per case and family; there is no aggregate score.

Profiles: `smoke` (one variant, one repeat; wiring only), `development` (every variant once; before freezing, never evidence), `campaign` (every variant, three repeats).
