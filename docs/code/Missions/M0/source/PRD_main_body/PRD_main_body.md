### 4.7 Intention Compilers

**Intention Compiler:** Transform unstructured qualified intake into a fixed, validated `Research_Brief.json` for Phase 1. The fallback is bounded and non-interactive, not limited to one LLM call.
- Preserve conservative defaults, source-supported scope, stable contract, and fixed SwarmFlow handoff.
- Architecture Design owns internal model-call sequencing. Phase 3 may integrate the advanced external compiler; the Phase 1 fallback stays available.

#### 4.7.1 Intent Classification & Compilation Variant Selection

Phase 1 fixes the Scientific Research lane and standard acceptance profile. Phase 3 may add dynamic request classification for the Leader Agent.

#### 4.7.2 Goal, Scope and Context Normalization

Extract objective, explicit parameters, and `in_scope`/`out_of_scope` from qualified user intake and bound local material without unsupported assumptions or undeclared external enrichment. No fixed internal LLM-call count.

#### 4.7.3 Ambiguity Resolution & Readiness

Apply conservative recorded defaults and deterministic readiness checks without waiting for interactive clarification. Human multi-turn clarification is Phase 3.

#### 4.7.4 Constraint Compilation

Normalize declared compute, hardware, time, token, and policy constraints into the brief. Enforce reliable time/call limits; token limits block only when trustworthy endpoint telemetry exists.

#### 4.7.5 Task Contract & Acceptance Compilation

Publish stable schema-bound Research Brief objectives, scope, constraints, targets, and acceptance expectations to the fixed DAG. Phase 3 may provide dynamic Planner/Leader-compatible semantics without changing the downstream contract.
