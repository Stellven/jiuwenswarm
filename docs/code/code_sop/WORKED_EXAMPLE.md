# Worked example: one small program, two TASKs
This is a fictional, unexecuted documentation example. It is not the M1 PRD, Router design, model list or a report of passing tests.

Open [DEMO TASKS](examples/DEMO/TASKS.md). It allocates a tiny source to:
- [DEMO-001](examples/DEMO/DEMO-001/TASK.md): validate and normalize an executor label.
- [DEMO-SYSTEM](examples/DEMO/DEMO-SYSTEM/TASK.md): wire a consumer and verify the complete request-to-display journey.

Each has its own spec/plan/tasks directory. The provider owns one embedded IF agreement; the consumer references it. DEMO-001's native matrix covers two blocks and the connection check; the system TASK's matrix covers whole-journey results.

Expected values illustrate test design only. Every runtime check remains NOT_RUN. No application files or tests are created by this example.

## Walkthrough
1. TASKS allocates each SOURCE clause to a single owning spec/AC.
2. TASK binds the executor, source and feature paths, and owns or consumes IF-001@r1.
3. spec.md defines behavior, including rejected inputs.
4. plan.md defines B01 validation, B02 normalization, connection checks and exact expected values.
5. tasks.md contains implementation/verification work and its evidence matrix.
6. An eventual execution creates evidence from the shared evidence template and updates the matrix.
7. A passing block result alone cannot complete DEMO: the boundary and system checks must also pass on the candidate.

The example has no write_code, implementation checklist, test report, review or handoff file.
