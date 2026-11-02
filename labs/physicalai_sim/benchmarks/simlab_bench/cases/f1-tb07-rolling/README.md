# f1-tb07-rolling: Rolling without slipping (TB-07)

Rolling without slipping: a = g sin theta / (1 + I/mr^2)

**Family:** F1. **Procedure:** single_run. **Engine:** MuJoCo 3.17.0 (pinned; a version change forces a rerun, the release manifest records it).

**Known answer and model assumptions:** sphere, shell or cylinder (1 kg, radius 0.1 m) on a plane, friction 1, condim 3 (no rolling resistance); incline by tilted gravity (20 degrees); acceleration from a quadratic fit of the centre of mass along the slope.

**Adopted references (test plan, Official external benchmarks, phase 1):**
- arXiv 2603.14634, analytic rolling test
- ContactBench contact criteria (rolling, no slip inside the friction cone)

**Variants** (all development split; held-out material is never in this repository):

- `solid-sphere`: Solid sphere, radius 0.1 m, 20 degree incline.
- `hollow-sphere`: Thin spherical shell (shell inertia), radius 0.1 m.
- `solid-cylinder`: Solid cylinder, radius 0.1 m, rolling about its axis.

**Frozen tolerances** (referee/criteria.json; `[confirm]` = proposed by the coding agent with this reason, owner confirmation pending, spec Clarifications 2026-10-30):

| Variant | Tolerance | Reason | [confirm] |
|---|---|---|---|
| solid-sphere | tolerance_rel = 0.005, tolerance_reason = Proposed 0.5% [confirm]: the source gives none. MuJoCo's soft contact lets the roller slip slightly (exploratory error at most 0.14%); 0.5% still separates the three inertias (their accelerations differ by 6% or more). | Proposed 0.5% [confirm]: the source gives none. MuJoCo's soft contact lets the roller slip slightly (exploratory error at most 0.14%); 0.5% still separates the three inertias (their accelerations differ by 6% or more). | True |
| hollow-sphere | tolerance_rel = 0.005, tolerance_reason = Proposed 0.5% [confirm]: the source gives none. MuJoCo's soft contact lets the roller slip slightly (exploratory error at most 0.14%); 0.5% still separates the three inertias (their accelerations differ by 6% or more). | Proposed 0.5% [confirm]: the source gives none. MuJoCo's soft contact lets the roller slip slightly (exploratory error at most 0.14%); 0.5% still separates the three inertias (their accelerations differ by 6% or more). | True |
| solid-cylinder | tolerance_rel = 0.005, tolerance_reason = Proposed 0.5% [confirm]: the source gives none. MuJoCo's soft contact lets the roller slip slightly (exploratory error at most 0.14%); 0.5% still separates the three inertias (their accelerations differ by 6% or more). | Proposed 0.5% [confirm]: the source gives none. MuJoCo's soft contact lets the roller slip slightly (exploratory error at most 0.14%); 0.5% still separates the three inertias (their accelerations differ by 6% or more). | True |


The oracle grades SIMLAB's own records: the measurement it reports and the raw trace, which the oracle recomputes independently. Missing evidence never passes.
