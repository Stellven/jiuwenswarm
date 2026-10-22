# Source Alignment Checklist: M1-QA

**Purpose**: Review completeness,clarity,consistency,measurability and source coverage before Plan
**Created**: 2026-10-16
**Feature**: [spec.md](../spec.md)
**Status**: Direct requirements-quality review complete after formal Clarify

**Note**: Uses the installed speckit-checklist instructions and active resolved template. The native prerequisite helper requires plan.md; direct template resolution preserves the user's required pre-plan order without fabricating a plan.
**Review Ownership**: The user explicitly requested direct source review. Codex performs that review under Code SOP v2,which introduces no separate reviewer assignment or human approval gate.
**Marker Semantics**: Generation leaves all new items unchecked. A later checked marker means requirements quality was assessed and satisfied,never implementation acceptance.

## Requirements quality and source alignment

- [x] CHK001 Are exactly four top-level integration cases and their frozen expected outcomes scoped separately from full campaigns? [Scope; AC-001]
- [x] CHK002 Do Capsule gate assertions require actual governed execution rather than invocation-only E3? [Completeness; AC-003; M1-I009]
- [x] CHK003 Do valid/invalid verifier counterparts require actual semantic/commit/advance/locking observations with C001 explicit? [Measurability; AC-004]
- [x] CHK004 Does routing require an actual supported decision and real call while permitting fixed Codex null API decision refs? [Consistency; AC-005]
- [x] CHK005 Does RSI permit truthful no-improvement/inconclusive integration while preserving accounting and admission/activation restrictions? [Coverage; AC-006]
- [x] CHK006 Are independent oracles protected from evaluated contexts and model-judge eligibility conditional on using model score authority? [Completeness; AC-008]
- [x] CHK007 Are proposed BIF versions/privileges reconciled to current canonical product contracts? [Compatibility; Scope; M1-I009]
- [x] CHK008 Are actual images/configuration and fresh host/container inventory/readiness required for every attempt/repeat? [Measurability; AC-002]
- [x] CHK009 Are all scheduled/failed/ambiguous attempts,denominators and missing-data rows retained without silent retry? [Coverage; AC-007/008]
- [x] CHK010 Are reusable extensions,actually exercised commands,evidence export and scoped cleanup required without startup dependence? [Completeness; AC-009]

## Review notes for this invocation

Focus: source completeness and protected execution/evidence boundaries; standard depth; direct author review after Clarify and before Plan. Every item has a traceability reference. Resolve findings in owning TASK/spec; generation was unchecked; this separate direct review found all items satisfied after correcting the owning requirements. No runtime success is claimed.

Review completed 2026-10-16: source alignment, completeness, consistency and measurability checked directly. Corrected M1-001/AC-007 to distinguish external-router profile from protected fixed-baseline call authorization, and M1-004/AC-006 to specify prohibited ZIP members precisely. Other reviewed requirements had no blocking findings. All markers describe requirements quality only; implementation and execution evidence remain pending.
