# Source Alignment Checklist: M1-004

**Purpose**: Review completeness,clarity,consistency,measurability and source coverage before Plan
**Created**: 2026-10-16
**Feature**: [spec.md](../spec.md)
**Status**: Direct requirements-quality review complete after formal Clarify

**Note**: Uses the installed speckit-checklist instructions and active resolved template. The native prerequisite helper requires plan.md; direct template resolution preserves the user's required pre-plan order without fabricating a plan.
**Review Ownership**: The user explicitly requested direct source review. Codex performs that review under Code SOP v2,which introduces no separate reviewer assignment or human approval gate.
**Marker Semantics**: Generation leaves all new items unchecked. A later checked marker means requirements quality was assessed and satisfied,never implementation acceptance.

## Requirements quality and source alignment

- [x] CHK001 Are strategy generation, query-grouped evidence and single-turn synthesis bounded and attributable? [Completeness; AC-002]
- [x] CHK002 Do per-ID scoring, fixed rubric anchors, dependency filtering and stable tie order remain consistent with consolidation? [Consistency; AC-003; M1-I004]
- [x] CHK003 Are immutable hypotheses, disjoint rules, source repeat/seed limits and one-file intervention explicit? [Measurability; AC-004]
- [x] CHK004 Are prepared package closure, read-only baseline and Builder no-install/no-trial responsibilities defined? [Completeness; AC-005/006]
- [x] CHK005 Are exact zip contents, mechanical readiness and analytical ownership boundaries specified? [Clarity; AC-006]
- [x] CHK006 Does C002 require one row per actual run, explicit status/reasons and no invented values under IF-005@r1? [Consistency; AC-008; M1-IF-005 empirical2]
- [x] CHK007 Are executed protocol parity, receipts, failed baseline halt and unmeasured treatment outcomes distinct? [Coverage; AC-007]
- [x] CHK008 Are scientific verdict precedence, pre-registered comparisons and infrastructure acceptance separated? [Measurability; AC-009]
- [x] CHK009 Is the exact numbered report template, metric-row coverage and section6 classification/completeness/plausibility conformance required? [Completeness; AC-010]
- [x] CHK010 Are all source budgets and conditional isolated Code Mode work retained without broadening Phase1? [Consistency; AC-011/012]

## Review notes for this invocation

Focus: source completeness and protected execution/evidence boundaries; standard depth; direct author review after Clarify and before Plan. Every item has a traceability reference. Resolve findings in owning TASK/spec; generation was unchecked; this separate direct review found all items satisfied after correcting the owning requirements. No runtime success is claimed.

Review completed 2026-10-16: source alignment, completeness, consistency and measurability checked directly. Corrected M1-001/AC-007 to distinguish external-router profile from protected fixed-baseline call authorization, and M1-004/AC-006 to specify prohibited ZIP members precisely. Other reviewed requirements had no blocking findings. All markers describe requirements quality only; implementation and execution evidence remain pending.
