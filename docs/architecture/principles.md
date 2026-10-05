# Principles and decisions

## Design priorities

First make the research pipeline run. Then make its results trustworthy and the deployment reproducible. Reuse existing systems and keep the design reviewable. Extend it when a demonstrated need justifies the cost.

Principles are intended to guide judgment. The design explains the objective and boundaries; coding agents choose implementation details within them.

## Product principles

- **Preserve intent.** Compilers clarify and constrain the request rather than quietly changing its objective.
- **The planner owns tasks.** Tasks may use as many nodes as needed within run limits. Each node invokes one CC; internal CC calls keep the parent's scope.
- **Process in the container.** Keep the control plane and substantive workflow processing inside; outside code handles user interaction and finished transfers.
- **Verify meaningful boundaries.** Assign checks to the risk and decision. Do not require a separate verifier after every capability or allow unchecked dependencies to pass a required gate.
- **Freeze before planned execution.** Record the chosen graph and checking responsibilities. Make material changes visible.
- **Keep evidence distinct from claims.** A producer's success message does not prove correctness; a model judgment does not replace measurement.
- **A negative research result is useful.** Valid evidence can reject a hypothesis and still produce a successful delivery.
- **Bound autonomy.** Model/tool loops and correction are limited by the assigned task and run policy. Do not hide retries or repeat consequential effects silently.
- **Keep state durable and understandable.** Preserve accepted outputs, attempts, and failure reasons; pause interrupted execution after restart.
- **Reuse before building.** Wrap a native feature when it fits. Build only the missing behavior and explain why.
- **Protect authored interfaces.** CC meanings should remain stable; avoid multiplying shared schemas for private intermediates.

## Architecture and Spec Kit

Architecture owns the system intent, major components, placement, dependencies, and shared CC authoring concepts. The PRD supplies product behavior and domain requirements. Exact source clauses must accompany relevant architecture slices when given to a coding agent.

Spec Kit owns task-level specifications, detailed interfaces, algorithms, fixtures, tests, acceptance conditions, and evidence under the [existing constitution](../../.specify/memory/constitution.md). Keep those authorities; do not duplicate them here. Runtime experiment criteria belong to the research protocol and must be established before measurement, even though development acceptance procedures are delegated to Spec Kit.

The system must be testable across capabilities, connected boundaries, and the integrated pipeline. Spec Kit owns concrete procedures and must respect the PRD's phase order or explain departures. Development tests alone do not establish scientific benchmark or verifier quality; those need owner-defined criteria and evidence.

## Changes from the previous design

| Previous default | Current direction and reason |
|---|---|
| Fixed, model-free research planner | Model-assisted composition of available CCs, with ordinary plan checking |
| Gate/verifier after every dispatch | Applicable verification with fixed-pipeline profiles and planned DAG assignments |
| Zero automatic correction | Bounded correction followed by rechecking; continue on acceptance, otherwise pause when unresolved; consequential effects still require care |
| Extensive schemas and acceptance seeds | Shared CC contract explanations; detailed payloads and acceptance work owned by coding tasks |
| RSI and model-routing design mixed into the baseline | Deferred so the first pipeline can be implemented promptly |
| Separate host control plane and Docker worker considered | One application container, including served web UI, control plane, and background execution |

These October 5 directions supersede conflicting archived defaults. Keep PRD sources verbatim and record remaining product conflicts in owning tasks. Do not claim full M1 delivery.

## Freedom and later work

Agents choose internal APIs, algorithms, concurrency, private formats, and adapters. Reconcile changes to product behavior, capability meanings, verification, trust boundaries, or scope with the design and PRD.

Domain owners supply rubrics and thresholds; naming settles with the PRD. Missing input constrains only affected work. Do not fabricate requirements.

Defer RSI, routing, remote access, multiple workers, and expanded DevOps. Retain configuration, versions, inputs, outputs, and evidence to diagnose and reproduce runs; identical stochastic model output is not promised.
