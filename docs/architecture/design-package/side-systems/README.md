# Side systems

`Tier 2 · Part of: [README](../README.md) · Serves: Knowledge and Standard`

A side system is built in M1 but stays off the hot path. A research run works the same with every side system absent, switched off or broken. [1. System](../1-system.md#hot-path-and-side-systems) shows the connections. [3. Build plan](../3-build-plan.md#side-systems-built-in-m1-never-blocking) holds the non-blocking test.

| Side system | Connects through | Owner page |
|---|---|---|
| Model router | `RouterPort` in the model bridge | [Model routing](model-routing.md) |
| RSI workbench | Record export (reads), admission inbox (writes) | [RSI workbench](rsi-workbench.md) |
| Platform benchmark runner | Control API (submits runs), record export (reads) | [Benchmark runner](benchmark-runner.md) |

[Integration rulings](owner-rulings.md) record the package-owned routing, RSI and derived-record responsibilities.
