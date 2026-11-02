# f1-tb03-incline: Block on an incline (TB-03)

Block on an incline: slides when tan theta > mu with a = g(sin theta - mu cos theta)

**Family:** F1. **Procedure:** single_run. **Engine:** MuJoCo 3.17.0 (pinned; a version change forces a rerun, the release manifest records it).

**Known answer and model assumptions:** flat box (0.2 x 0.2 x 0.04 m, 1 kg) on a plane with Coulomb friction mu on both geoms; the incline is represented by tilting gravity by theta (equivalent physics); acceleration from a quadratic fit of the box's centre of mass along the slope between 0.1 and 1.0 s.

**Adopted references (test plan, Official external benchmarks, phase 1):**
- Drake inclined-plane and friction tests (pattern)
- ContactBench contact criteria (Coulomb law: stick inside the cone, slide on it)
- arXiv 2603.14634, analytic sliding test

**Variants** (all development split; held-out material is never in this repository):

- `slide-30deg-mu0p2`: 30 degree incline (tilted gravity), friction 0.2.
- `slide-40deg-mu0p5`: 40 degree incline, friction 0.5.
- `stick-20deg-mu0p5`: 20 degree incline, friction 0.5 (tan 20 = 0.364 < 0.5).

**Frozen tolerances** (referee/criteria.json; `[confirm]` = proposed by the coding agent with this reason, owner confirmation pending, spec Clarifications 2026-10-30):

| Variant | Tolerance | Reason | [confirm] |
|---|---|---|---|
| slide-30deg-mu0p2 | tolerance_rel = 0.01, tolerance_stick_m = None, tolerance_reason = Proposed 1% [confirm]. The source gives no tolerance (TP 'Test benches'). MuJoCo friction is a soft, regularized constraint (elliptic cone, impratio 10); exploratory runs on this build differed from the formula by at most 0.03%, so 1% leaves margin for solver settings while still failing a wrong friction law (a frictionless block would be off by more than 30%). | Proposed 1% [confirm]. The source gives no tolerance (TP 'Test benches'). MuJoCo friction is a soft, regularized constraint (elliptic cone, impratio 10); exploratory runs on this build differed from the formula by at most 0.03%, so 1% leaves margin for solver settings while still failing a wrong friction law (a frictionless block would be off by more than 30%). | True |
| slide-40deg-mu0p5 | tolerance_rel = 0.01, tolerance_stick_m = None, tolerance_reason = Proposed 1% [confirm]. The source gives no tolerance (TP 'Test benches'). MuJoCo friction is a soft, regularized constraint (elliptic cone, impratio 10); exploratory runs on this build differed from the formula by at most 0.03%, so 1% leaves margin for solver settings while still failing a wrong friction law (a frictionless block would be off by more than 30%). | Proposed 1% [confirm]. The source gives no tolerance (TP 'Test benches'). MuJoCo friction is a soft, regularized constraint (elliptic cone, impratio 10); exploratory runs on this build differed from the formula by at most 0.03%, so 1% leaves margin for solver settings while still failing a wrong friction law (a frictionless block would be off by more than 30%). | True |
| stick-20deg-mu0p5 | tolerance_rel = None, tolerance_stick_m = 0.001, tolerance_reason = Proposed 1 mm over 0.9 s [confirm]. Soft contacts creep slightly while sticking (exploratory: 0.08 mm); a block that slid at these values would travel more than 0.1 m. | Proposed 1 mm over 0.9 s [confirm]. Soft contacts creep slightly while sticking (exploratory: 0.08 mm); a block that slid at these values would travel more than 0.1 m. | True |


The oracle grades SIMLAB's own records: the measurement it reports and the raw trace, which the oracle recomputes independently. Missing evidence never passes.
