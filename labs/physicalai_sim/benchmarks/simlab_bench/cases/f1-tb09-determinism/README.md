# f1-tb09-determinism: Determinism and checkpoint restore (TB-09)

Two executions are identical, replay is identical, and restore-and-continue equals the uninterrupted run

**Family:** F1. **Procedure:** determinism. **Engine:** MuJoCo 3.17.0 (pinned; a version change forces a rerun, the release manifest records it).

**Known answer and model assumptions:** same machine and same build only (test plan Rules); seeds, recorded actions and checkpoints come from SIMLAB's own records.

**Adopted references (test plan, Official external benchmarks, phase 1):**
- MuJoCo state API (mj_getState with mjSTATE_INTEGRATION; 3.17 batch runs bit-identical to a plain loop)
- SIMLAB test plan TB-09

**Variants** (all development split; held-out material is never in this repository):

- `controlled-noisy`: Controlled pendulum with a seeded noisy controller and a random start angle.
- `contact-rich`: A box dropped onto a box from a random height (contact-rich).
- `factor-random`: Two controller gains (a factor) with a normally distributed start angle.

**Frozen tolerances** (referee/criteria.json; `[confirm]` = proposed by the coding agent with this reason, owner confirmation pending, spec Clarifications 2026-10-30):

| Variant | Tolerance | Reason | [confirm] |
|---|---|---|---|
| controlled-noisy | tolerance_reason = Identity rule, not a tolerance. | Identity rule, not a tolerance. | False |
| contact-rich | tolerance_reason = Identity rule, not a tolerance. | Identity rule, not a tolerance. | False |
| factor-random | tolerance_reason = Identity rule, not a tolerance. | Identity rule, not a tolerance. | False |


The oracle grades SIMLAB's own records: the measurement it reports and the raw trace, which the oracle recomputes independently. Missing evidence never passes.
