# Existing workflow integration seams

Reviewed against the current factory implementation, without the external workflow branch or its API. No integration adapter is implemented here.

| Concern | Existing interface and concrete boundary |
| --- | --- |
| Identity | `FactoryLoop.select/execute` binds task, cycle, child task, attempt, decision revision and optional branch node/revision. `taskgraph.plan_get/plan_patch` is a revisioned dependency graph, not a scheduler. Keep external workflow IDs separate from these identities. |
| Child ownership | `loop.owned_attempts` uses the parent's durable cycle ledger, not `factory_loop_parent` labels alone. It covers direct children only. Arbitrary nested workflow descendants are not automatically supervised or cancelled; their ownership must be mapped explicitly when the external API is available. |
| Evidence | `Store.scoped` requires explicit readable tasks. `FactoryLoop.collect` creates parent evidence with child task/attempt provenance; authored diagnostics additionally retain source artifact IDs and digests. Evidence IDs are task-scoped: preserve task plus ID across workflows, not bare IDs or status strings. |
| Budgets | `Jobs.submit` charges durable attempts (including failures) to the explicit `campaign_budget_owner`, falling back to the direct loop parent. Controller turns/deadlines share the explicit owner. This is a flat owner attribution, not recursive budget inheritance. Construction comparisons reserve 4/4/8 phase containers; queue attempts and GPU processes are different units. |
| Submission/recovery | Jobs binds `(task_id, idem_key)` to a fingerprint; conflicting inputs fail. FactoryLoop persists dispatch intent and recovers the same attempt after lost acknowledgement, including after expiry. A retry/new key spends a new attempt. External retries must preserve this identity. |
| Stop/cancel | `FactoryLoop.stop` and graph pruning prevent fresh dispatch but do not cancel submitted work. `Controller.cancel`/supervisor cancellation address owned attempts; `cancel_requested` and `unknown` remain pending. Cancellation is not evidence of container cleanup. |
| Terminal/result propagation | `Controller._terminal_ready` blocks on active/unknown child attempts and uncollected cycles. A failed or incomplete child must still be collected. A branch's `done` means its investigation was collected, not scientific acceptance; inspect result/evidence completeness and the host decision. |
| Parent shutdown | Supervisor deadline/error handling attempts control recovery and cancellation of every owned job, preserving individual failures, the original stop reason and pending IDs in `supervisor-result.json`. `cancellation_complete=false` requires reconciliation; a partial parent receipt never upgrades child evidence. |

Focused CPU tests cover pending/unknown/cancel-requested child termination, failed-child collection and provenance, cancellation continuing after a child error, and durable partial results after control/queue cleanup failures. Existing tests cover lost acknowledgements, budget expiry, forged ownership labels and nonpromoting incomplete evidence. These tests do not establish live hardware acceptance.

Before integrating the external branch, inspect how it represents nesting, cancellation propagation, terminal versus collected results, scoped evidence references and retry keys. Reuse these interfaces; do not assume its graph states or budget units have factory semantics.
