# f1-tb01-pendulum: Pendulum, small and large swing (TB-01)

Measure the pendulum period for small and large swings

**Family:** F1. **Procedure:** single_run. **Engine:** MuJoCo 3.17.0 (pinned; a version change forces a rerun, the release manifest records it).

**Known answer and model assumptions:** point mass (inertia 1e-9) on a massless rigid rod, no damping, no contact, g = 9.81 m/s^2, RK4 with 0.2 ms steps, period = mean interval between upward zero crossings over 13 s.

**Adopted references (test plan, Official external benchmarks, phase 1):**
- arXiv 2603.14634, analytic pendulum test (the seven analytic tests)
- MuJoCo engine tests (hinge dynamics)
- Elliptic integral K by the arithmetic-geometric mean (Abramowitz and Stegun 17.6)

**Variants** (all development split; held-out material is never in this repository):

- `small-swing`: Point-mass pendulum, length 1.0 m, released from 0.05 rad.
- `large-swing-1p2`: Length 0.8 m, released from 1.2 rad.
- `large-swing-2p6`: Length 1.2 m, released from 2.6 rad.

**Frozen tolerances** (referee/criteria.json; `[confirm]` = proposed by the coding agent with this reason, owner confirmation pending, spec Clarifications 2026-10-30):

| Variant | Tolerance | Reason | [confirm] |
|---|---|---|---|
| small-swing | tolerance_rel = 0.005, tolerance_reason = Test plan TB-01 gives 0.5% ([confirm] value in the source, TASKS §6 Q-01). The small-angle formula itself differs from the exact period by theta0^2/16 = 0.016% here. | Test plan TB-01 gives 0.5% ([confirm] value in the source, TASKS §6 Q-01). The small-angle formula itself differs from the exact period by theta0^2/16 = 0.016% here. | True |
| large-swing-1p2 | tolerance_rel = 0.005, tolerance_reason = Test plan TB-01 gives 0.5% ([confirm] value in the source, TASKS §6 Q-01). | Test plan TB-01 gives 0.5% ([confirm] value in the source, TASKS §6 Q-01). | True |
| large-swing-2p6 | tolerance_rel = 0.005, tolerance_reason = Test plan TB-01 gives 0.5% ([confirm] value in the source, TASKS §6 Q-01). | Test plan TB-01 gives 0.5% ([confirm] value in the source, TASKS §6 Q-01). | True |


The oracle grades SIMLAB's own records: the measurement it reports and the raw trace, which the oracle recomputes independently. Missing evidence never passes.
