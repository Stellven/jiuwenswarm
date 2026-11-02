# f1-tb02-free-fall: Free fall (TB-02)

Measure free-fall distance against g t^2 / 2

**Family:** F1. **Procedure:** single_run. **Engine:** MuJoCo 3.17.0 (pinned; a version change forces a rerun, the release manifest records it).

**Known answer and model assumptions:** a free sphere with no contact (contype 0) under uniform gravity; displacement of the body origin from t = 0 to the declared time.

**Adopted references (test plan, Official external benchmarks, phase 1):**
- arXiv 2603.14634, analytic free-fall test
- MuJoCo engine tests (free joint integration)

**Variants** (all development split; held-out material is never in this repository):

- `earth-1s`: Drop for 1.0 s at g = 9.81 m/s^2 (RK4, 1 ms).
- `moon-0p5s`: Drop for 0.5 s at g = 1.62 m/s^2 (RK4, 1 ms).
- `earth-2s-euler`: Drop for 2.0 s at g = 9.81 m/s^2 with semi-implicit Euler, 0.1 ms.

**Frozen tolerances** (referee/criteria.json; `[confirm]` = proposed by the coding agent with this reason, owner confirmation pending, spec Clarifications 2026-10-30):

| Variant | Tolerance | Reason | [confirm] |
|---|---|---|---|
| earth-1s | tolerance_rel = 0.001, tolerance_reason = Test plan TB-02 gives 0.1%. | Test plan TB-02 gives 0.1%. | False |
| moon-0p5s | tolerance_rel = 0.001, tolerance_reason = Test plan TB-02 gives 0.1%. | Test plan TB-02 gives 0.1%. | False |
| earth-2s-euler | tolerance_rel = 0.001, tolerance_reason = Test plan TB-02 gives 0.1%. Semi-implicit Euler's error here is dt/t = 5e-5. | Test plan TB-02 gives 0.1%. Semi-implicit Euler's error here is dt/t = 5e-5. | False |

Each variant sets its own fall time through the procedure.
The oracle grades SIMLAB's own records: the measurement it reports and the raw trace, which the oracle recomputes independently. Missing evidence never passes.
