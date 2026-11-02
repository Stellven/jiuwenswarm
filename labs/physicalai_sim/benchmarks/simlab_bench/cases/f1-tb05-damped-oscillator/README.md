# f1-tb05-damped-oscillator: Damped oscillator (TB-05)

Damped oscillator decay rate and frequency

**Family:** F1. **Procedure:** single_run. **Engine:** MuJoCo 3.17.0 (pinned; a version change forces a rerun, the release manifest records it).

**Known answer and model assumptions:** a mass on a slide joint with linear stiffness and viscous damping, no gravity, no contact; period from upward zero crossings, decay rate from a log-linear fit of the peaks.

**Adopted references (test plan, Official external benchmarks, phase 1):**
- arXiv 2603.14634, analytic damped-oscillator test
- MuJoCo engine tests (passive joint stiffness and damping)

**Variants** (all development split; held-out material is never in this repository):

- `light-damping`: m 1 kg, k 100 N/m, c 1 N s/m.
- `medium-damping`: m 2 kg, k 50 N/m, c 4 N s/m.
- `stiff-light`: m 0.5 kg, k 200 N/m, c 0.5 N s/m.

**Frozen tolerances** (referee/criteria.json; `[confirm]` = proposed by the coding agent with this reason, owner confirmation pending, spec Clarifications 2026-10-30):

| Variant | Tolerance | Reason | [confirm] |
|---|---|---|---|
| light-damping | tolerance_rel = 0.005, tolerance_reason = Proposed 0.5% [confirm], the same as the source's pendulum tolerance; the source gives none for TB-05. RK4 at 0.1 ms integrates this linear system far more accurately; peak and crossing interpolation at 5 kHz bound the measurement error. | Proposed 0.5% [confirm], the same as the source's pendulum tolerance; the source gives none for TB-05. RK4 at 0.1 ms integrates this linear system far more accurately; peak and crossing interpolation at 5 kHz bound the measurement error. | True |
| medium-damping | tolerance_rel = 0.005, tolerance_reason = Proposed 0.5% [confirm], the same as the source's pendulum tolerance; the source gives none for TB-05. RK4 at 0.1 ms integrates this linear system far more accurately; peak and crossing interpolation at 5 kHz bound the measurement error. | Proposed 0.5% [confirm], the same as the source's pendulum tolerance; the source gives none for TB-05. RK4 at 0.1 ms integrates this linear system far more accurately; peak and crossing interpolation at 5 kHz bound the measurement error. | True |
| stiff-light | tolerance_rel = 0.005, tolerance_reason = Proposed 0.5% [confirm], the same as the source's pendulum tolerance; the source gives none for TB-05. RK4 at 0.1 ms integrates this linear system far more accurately; peak and crossing interpolation at 5 kHz bound the measurement error. | Proposed 0.5% [confirm], the same as the source's pendulum tolerance; the source gives none for TB-05. RK4 at 0.1 ms integrates this linear system far more accurately; peak and crossing interpolation at 5 kHz bound the measurement error. | True |


The oracle grades SIMLAB's own records: the measurement it reports and the raw trace, which the oracle recomputes independently. Missing evidence never passes.
