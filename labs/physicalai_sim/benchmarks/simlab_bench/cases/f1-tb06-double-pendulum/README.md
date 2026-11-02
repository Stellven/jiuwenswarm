# f1-tb06-double-pendulum: Passive double pendulum (TB-06)

Passive double pendulum: bounded energy error and agreement with a high-accuracy reference over a short horizon

**Family:** F1. **Procedure:** single_run. **Engine:** MuJoCo 3.17.0 (pinned; a version change forces a rerun, the release manifest records it).

**Known answer and model assumptions:** two point masses on massless rods; MuJoCo's second hinge angle is relative to the first, so phi1 = q1 and phi2 = q1 + q2; the reference is an independent pure-Python RK4 at 0.01 ms frozen in referee/ with its own convergence test.

**Adopted references (test plan, Official external benchmarks, phase 1):**
- arXiv 2603.14634, analytic double-pendulum test
- MuJoCo engine tests (multi-joint chains)
- Textbook double-pendulum equations (point masses, massless rods)

**Variants** (all development split; held-out material is never in this repository):

- `swing-a`: Equal masses and lengths, released at 0.8 and 1.2 rad. MuJoCo's second angle is relative (q2 = phi2 - phi1).
- `swing-b`: Masses 1 and 2 kg, lengths 1.0 and 0.6 m, released at 1.5 and 0.5 rad. MuJoCo's second angle is relative (q2 = phi2 - phi1).
- `swing-c`: Masses 2 and 1 kg, lengths 0.7 and 1.0 m, released at -0.5 and 2.0 rad. MuJoCo's second angle is relative (q2 = phi2 - phi1).
- `frozen-gravity-off`: Negative control: gravity off, so the pendulum stays frozen. Negative control: the oracle must report a failure.
- `over-damped`: Negative control: heavy joint damping. Negative control: the oracle must report a failure.

**Frozen tolerances** (referee/criteria.json; `[confirm]` = proposed by the coding agent with this reason, owner confirmation pending, spec Clarifications 2026-10-30):

| Variant | Tolerance | Reason | [confirm] |
|---|---|---|---|
| swing-a | tolerance_angle_rad = 0.001, tolerance_energy_rel = 1e-06, tolerance_reason = Proposed 1e-3 rad [confirm]: the source asks for agreement 'over a short horizon' without a number; RK4 at 0.1 ms agrees with the 0.01 ms reference to about 1e-7 rad over 2 s before chaotic growth, so 1e-3 rad fails a frozen, damped or wrongly coupled model by orders of magnitude. Proposed 1e-6 relative [confirm]: RK4 at 0.1 ms conserves energy far better on this passive system; an over-damped simulation loses most of it. | Proposed 1e-3 rad [confirm]: the source asks for agreement 'over a short horizon' without a number; RK4 at 0.1 ms agrees with the 0.01 ms reference to about 1e-7 rad over 2 s before chaotic growth, so 1e-3 rad fails a frozen, damped or wrongly coupled model by orders of magnitude. Proposed 1e-6 relative [confirm]: RK4 at 0.1 ms conserves energy far better on this passive system; an over-damped simulation loses most of it. | True |
| swing-b | tolerance_angle_rad = 0.001, tolerance_energy_rel = 1e-06, tolerance_reason = Proposed 1e-3 rad [confirm]: the source asks for agreement 'over a short horizon' without a number; RK4 at 0.1 ms agrees with the 0.01 ms reference to about 1e-7 rad over 2 s before chaotic growth, so 1e-3 rad fails a frozen, damped or wrongly coupled model by orders of magnitude. Proposed 1e-6 relative [confirm]: RK4 at 0.1 ms conserves energy far better on this passive system; an over-damped simulation loses most of it. | Proposed 1e-3 rad [confirm]: the source asks for agreement 'over a short horizon' without a number; RK4 at 0.1 ms agrees with the 0.01 ms reference to about 1e-7 rad over 2 s before chaotic growth, so 1e-3 rad fails a frozen, damped or wrongly coupled model by orders of magnitude. Proposed 1e-6 relative [confirm]: RK4 at 0.1 ms conserves energy far better on this passive system; an over-damped simulation loses most of it. | True |
| swing-c | tolerance_angle_rad = 0.001, tolerance_energy_rel = 1e-06, tolerance_reason = Proposed 1e-3 rad [confirm]: the source asks for agreement 'over a short horizon' without a number; RK4 at 0.1 ms agrees with the 0.01 ms reference to about 1e-7 rad over 2 s before chaotic growth, so 1e-3 rad fails a frozen, damped or wrongly coupled model by orders of magnitude. Proposed 1e-6 relative [confirm]: RK4 at 0.1 ms conserves energy far better on this passive system; an over-damped simulation loses most of it. | Proposed 1e-3 rad [confirm]: the source asks for agreement 'over a short horizon' without a number; RK4 at 0.1 ms agrees with the 0.01 ms reference to about 1e-7 rad over 2 s before chaotic growth, so 1e-3 rad fails a frozen, damped or wrongly coupled model by orders of magnitude. Proposed 1e-6 relative [confirm]: RK4 at 0.1 ms conserves energy far better on this passive system; an over-damped simulation loses most of it. | True |
| frozen-gravity-off | tolerance_angle_rad = 0.001, tolerance_energy_rel = 1e-06, tolerance_reason = Negative control (test plan TB-06: a frozen or over-damped simulation fails). | Negative control (test plan TB-06: a frozen or over-damped simulation fails). | True |
| over-damped | tolerance_angle_rad = 0.001, tolerance_energy_rel = 1e-06, tolerance_reason = Negative control (test plan TB-06: a frozen or over-damped simulation fails). | Negative control (test plan TB-06: a frozen or over-damped simulation fails). | True |


The oracle grades SIMLAB's own records: the measurement it reports and the raw trace, which the oracle recomputes independently. Missing evidence never passes.
