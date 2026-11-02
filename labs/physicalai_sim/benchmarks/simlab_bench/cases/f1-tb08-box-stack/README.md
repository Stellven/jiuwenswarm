# f1-tb08-box-stack: Box stack at rest (TB-08)

Box stack at rest: stays still, contact forces balance gravity, penetration bounded

**Family:** F1. **Procedure:** single_run. **Engine:** MuJoCo 3.17.0 (pinned; a version change forces a rerun, the release manifest records it).

**Known answer and model assumptions:** three 10 cm boxes stacked on a plane with MuJoCo's default soft contact; force = summed normal force between the floor and the bottom box at the end; stillness measured after a 1 s settle.

**Adopted references (test plan, Official external benchmarks, phase 1):**
- MuJoCo engine tests (resting contact)
- ContactBench contact criteria (non-penetration, force balance)

**Variants** (all development split; held-out material is never in this repository):

- `equal-masses`: Three 1 kg boxes.
- `heavy-bottom`: Boxes of 2, 1 and 0.5 kg from the bottom.
- `heavy-top`: Boxes of 0.5, 1 and 2 kg from the bottom.
- `gravity-off`: Negative control: gravity off (contact forces vanish). Negative control: the oracle must report a failure.

**Frozen tolerances** (referee/criteria.json; `[confirm]` = proposed by the coding agent with this reason, owner confirmation pending, spec Clarifications 2026-10-30):

| Variant | Tolerance | Reason | [confirm] |
|---|---|---|---|
| equal-masses | tolerance_force_rel = 0.01, tolerance_still_m = 0.0001, tolerance_penetration_m = 0.001, tolerance_reason = Proposed [confirm]: force within 1% of the total weight (exploratory: exact to rounding), top box height range at most 0.1 mm after the 1 s settle, penetration at most 1 mm (exploratory 0.37 mm with MuJoCo's default soft contact). The source gives no numbers. | Proposed [confirm]: force within 1% of the total weight (exploratory: exact to rounding), top box height range at most 0.1 mm after the 1 s settle, penetration at most 1 mm (exploratory 0.37 mm with MuJoCo's default soft contact). The source gives no numbers. | True |
| heavy-bottom | tolerance_force_rel = 0.01, tolerance_still_m = 0.0001, tolerance_penetration_m = 0.001, tolerance_reason = Proposed [confirm]: force within 1% of the total weight (exploratory: exact to rounding), top box height range at most 0.1 mm after the 1 s settle, penetration at most 1 mm (exploratory 0.37 mm with MuJoCo's default soft contact). The source gives no numbers. | Proposed [confirm]: force within 1% of the total weight (exploratory: exact to rounding), top box height range at most 0.1 mm after the 1 s settle, penetration at most 1 mm (exploratory 0.37 mm with MuJoCo's default soft contact). The source gives no numbers. | True |
| heavy-top | tolerance_force_rel = 0.01, tolerance_still_m = 0.0001, tolerance_penetration_m = 0.001, tolerance_reason = Proposed [confirm]: force within 1% of the total weight (exploratory: exact to rounding), top box height range at most 0.1 mm after the 1 s settle, penetration at most 1 mm (exploratory 0.37 mm with MuJoCo's default soft contact). The source gives no numbers. | Proposed [confirm]: force within 1% of the total weight (exploratory: exact to rounding), top box height range at most 0.1 mm after the 1 s settle, penetration at most 1 mm (exploratory 0.37 mm with MuJoCo's default soft contact). The source gives no numbers. | True |
| gravity-off | tolerance_force_rel = 0.01, tolerance_still_m = 0.0001, tolerance_penetration_m = 0.001, tolerance_reason = Negative control (test plan TB-08: a stack with gravity off fails). | Negative control (test plan TB-08: a stack with gravity off fails). | True |


The oracle grades SIMLAB's own records: the measurement it reports and the raw trace, which the oracle recomputes independently. Missing evidence never passes.
