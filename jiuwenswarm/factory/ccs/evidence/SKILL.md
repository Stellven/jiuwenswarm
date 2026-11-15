---
name: factory-evidence
description: Find and publish task-scoped evidence, immutable reports and decisions without needless context duplication.
---

Use query to find summaries, then read only records needed for the current decision. Query limit is1..50; continue with the returned cursor rather than requesting an unbounded page. IDs name evidence records, not filesystem paths. Reuse operator-imported artifact IDs instead of republishing the same input as a new artifact.

For a large JSON artifact, the optional evidence-digest package can index and project exact source-linked fields inside the factory. Preserve workload/scope, limitations, correctness and exact-output differences when judging speed. A projected subset is not a complete scientific report. Small records can be read directly here.

Publish a decision with actual evidence IDs and current revision; use observation publication for findings or a structured report. Publishing an artifact from a path requires a file that already exists in the admitted workspace. If a local file tool cannot write, retain report text as an immutable observation and return its evidence ID; do not invent a filesystem artifact. The parent exporter can later copy that exact text into a portable report.

The branch workbench handles branching as its own job. Its mutations already return state; reuse those responses before asking for another full graph. These methods reduce avoidable calls, but the November15 trace is the baseline rather than proof of a future token reduction.
