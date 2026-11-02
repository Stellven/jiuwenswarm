# f1-tb04-collision: 1D collisions (TB-04)

1D collision: momentum is conserved and restitution sets the ratio of relative normal velocities

**Family:** F1. **Procedure:** single_run. **Engine:** MuJoCo 3.17.0 (pinned; a version change forces a rerun, the release manifest records it).

**Known answer and model assumptions:** two spheres on frictionless slide joints with gravity off; contact stiffness k and damping b given directly (MuJoCo negative solref, per unit effective mass), impedance 0.9999; restitution measured as -(va - vb)after / (va - vb)before around the contact.

**Adopted references (test plan, Official external benchmarks, phase 1):**
- ContactBench contact criteria (impulse balance, restitution)
- Acosta et al. impact data (phase 5 real-data follow-up)
- Schwager T., Poeschel T., Coefficient of restitution and linear-dashpot model revisited, Granular Matter 9 (2007)

**Variants** (all development split; held-out material is never in this repository):

- `elastic-1to1`: Equal masses, undamped contact.
- `damped-1to3`: Masses 1:3, damped contact.
- `damped-2to1`: Masses 2:1, lightly damped contact.

**Frozen tolerances** (referee/criteria.json; `[confirm]` = proposed by the coding agent with this reason, owner confirmation pending, spec Clarifications 2026-10-30):

| Variant | Tolerance | Reason | [confirm] |
|---|---|---|---|
| elastic-1to1 | tolerance_e = 0.005, tolerance_momentum = 1e-09, tolerance_reason = Proposed 0.005 absolute [confirm]. The source gives none. The expected restitution comes from the contact law itself (linear spring-dashpot with force-based separation, Schwager and Poeschel 2007); MuJoCo's impedance 0.9999 and the step size leave a small residual (exploratory: up to 3e-4). Proposed 1e-9 relative [confirm]: equal and opposite contact forces conserve momentum to rounding (exploratory 1e-15). | Proposed 0.005 absolute [confirm]. The source gives none. The expected restitution comes from the contact law itself (linear spring-dashpot with force-based separation, Schwager and Poeschel 2007); MuJoCo's impedance 0.9999 and the step size leave a small residual (exploratory: up to 3e-4). Proposed 1e-9 relative [confirm]: equal and opposite contact forces conserve momentum to rounding (exploratory 1e-15). | True |
| damped-1to3 | tolerance_e = 0.005, tolerance_momentum = 1e-09, tolerance_reason = Proposed 0.005 absolute [confirm]. The source gives none. The expected restitution comes from the contact law itself (linear spring-dashpot with force-based separation, Schwager and Poeschel 2007); MuJoCo's impedance 0.9999 and the step size leave a small residual (exploratory: up to 3e-4). Proposed 1e-9 relative [confirm]: equal and opposite contact forces conserve momentum to rounding (exploratory 1e-15). | Proposed 0.005 absolute [confirm]. The source gives none. The expected restitution comes from the contact law itself (linear spring-dashpot with force-based separation, Schwager and Poeschel 2007); MuJoCo's impedance 0.9999 and the step size leave a small residual (exploratory: up to 3e-4). Proposed 1e-9 relative [confirm]: equal and opposite contact forces conserve momentum to rounding (exploratory 1e-15). | True |
| damped-2to1 | tolerance_e = 0.005, tolerance_momentum = 1e-09, tolerance_reason = Proposed 0.005 absolute [confirm]. The source gives none. The expected restitution comes from the contact law itself (linear spring-dashpot with force-based separation, Schwager and Poeschel 2007); MuJoCo's impedance 0.9999 and the step size leave a small residual (exploratory: up to 3e-4). Proposed 1e-9 relative [confirm]: equal and opposite contact forces conserve momentum to rounding (exploratory 1e-15). | Proposed 0.005 absolute [confirm]. The source gives none. The expected restitution comes from the contact law itself (linear spring-dashpot with force-based separation, Schwager and Poeschel 2007); MuJoCo's impedance 0.9999 and the step size leave a small residual (exploratory: up to 3e-4). Proposed 1e-9 relative [confirm]: equal and opposite contact forces conserve momentum to rounding (exploratory 1e-15). | True |


The oracle grades SIMLAB's own records: the measurement it reports and the raw trace, which the oracle recomputes independently. Missing evidence never passes.
