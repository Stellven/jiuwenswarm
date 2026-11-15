---
name: factory-branch-workbench
description: Record agent-chosen alternative hypotheses, bounded reservations, evidence, pruning and continuations in a factory task graph; compare reported speed, memory and quality without execution or acceptance authority.
---

Use this capsule when a factory investigation has several plausible causes or treatments. Read the task, contract, available releases and operator constraints first. Choose hypotheses from evidence; the host does not choose branches.

Call `create` for the initial hypothesis and `fork` for alternatives. A branch can list several CC capability references; these are work references, not grants. Invoke each admitted CC through the normal agent tools, save its receipts and evidence, and keep execution inside existing task authority. The workbench performs no nested calls.

For a reported measurement call `record` with the current-task observation ID described in METHOD.md. Use `attach` for qualitative findings, missing prerequisites or failed experiments. Keep missing metrics unknown. Use `refine` to create a changed hypothesis after a completed parent; it preserves the original hypothesis, result and lineage. Use `prune` with a reason when evidence rejects an idea. Allocation remains charged after pruning.

Read `ready` before choosing another action. Read `compare` only as a descriptive Pareto view; its output cannot authorize acceptance, changed contracts or promotion. Stop when no bounded action can reduce the uncertainty, the operator budget is exhausted, or the task stop condition holds.

## Avoid redundant context and calls

Every mutation returns the updated graph revision, branches, readiness and reservations. Reuse that returned status for the next dependent operation. Call status/ready again when another actor could have changed the graph or when you need a fresh snapshot, not mechanically after every mutation. This advice follows the November15 live run's repeated status reads; its impact on model cost has not yet been measured. Keep hypotheses concise and cite existing evidence IDs instead of republishing the same report.
