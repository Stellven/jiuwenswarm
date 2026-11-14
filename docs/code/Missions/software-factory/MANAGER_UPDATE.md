we have built up a dynamical workflow and use it to produce a Ascend Native STRATA source project.

The factory reads the real STRATA repository, discovers executable capabilities, and composes reusable stages into task-specific workflows. It generates C++ source, builds it, validates each selected operation, and packages a reproducible code project.

We have demonstrated distinct execution paths for core computation and normalization, cross-workflow stage reuse, and verified artifact hand-offs. The integrated interface presents the execution graph, source-code diff, command logs, and recorded-run replay. The backend has passed 81 tests, with the source-production chain examined across three rounds of independent review.
