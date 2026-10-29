# Requirements Quality Checklist: M1-001 foundation

**Purpose**: Review completeness, clarity and consistency before planning
**Created**: 2026-10-16
**Feature**: [spec.md](../spec.md)
**Status**: Direct requirements-quality review complete after Specify and Clarify; original draft retained and reviewed with the ordered invocation.

**Note**: Generated through the installed speckit-checklist instructions using the active resolved template.
**Review Ownership**: The user's requested direct requirements review is performed within Code SOP v2; no separate reviewer assignment or approval stage is introduced.
**Marker Semantics**: A checked item means requirements quality was reviewed and satisfied, never that implementation passed. Generation leaves markers unchecked; review is a separate action.

## Requirement Completeness and Clarity

- [x] CHK001 Are native reuse and distribution constraints sourced and separated from a replacement application? [Completeness, FR-001, AC-001]
- [x] CHK002 Are both image architectures and the distinct native-GB10 evidence claim specified? [Clarity, FR-002, AC-002]
- [x] CHK003 Are origin, authentication, private binding and prohibited service exposure requirements explicit? [Completeness, FR-003, AC-003]
- [x] CHK004 Are valid and invalid operator-configuration outcomes specified without embedding credentials? [Coverage, FR-004, AC-004]
- [x] CHK005 Are protected model entry, authorization failure and runtime identity requirements defined? [Completeness, FR-005, AC-005]
- [x] CHK006 Are pre-dispatch evidence requirements and persistence-failure behavior unambiguous? [Clarity, FR-006, AC-006]

## Consistency and Acceptance Quality

- [x] CHK007 Are fixed Codex, verifier routing and enabled experimental router boundaries consistent? [Consistency, FR-007, AC-007]
- [x] CHK008 Are pre-start fallback and post-start failure distinguished, with the sourced 30-second limit? [Consistency, FR-008, AC-008/009]
- [x] CHK009 Do isolation requirements identify actual denied resources and effective authority? [Measurability, FR-009, AC-010]
- [x] CHK010 Are the Builder call shape, tool cap and enforced terminal failure specified independently of model claims? [Clarity, FR-010, AC-011]
- [x] CHK011 Are the dedicated credential, temporary lifetime, missing-resource outcome and accepted exposure risk explicit? [Coverage, FR-011, AC-012]
- [x] CHK012 Are requested/effective model identities and missing usage distinguished without invented values? [Measurability, FR-006, AC-013]

## Edge Cases, Dependencies and Scope

- [x] CHK013 Are liveness, functional readiness and host/container facts distinguished? [Clarity, FR-012, AC-014]
- [x] CHK014 Are side-system absence and no-replay lifecycle requirements covered? [Coverage, FR-013, AC-015/016]
- [x] CHK015 Are reproducible operations and evidence-preserving cleanup requirements specified? [Completeness, FR-014, AC-017]
- [x] CHK016 Are dependent product interfaces, real-resource prerequisites and incomplete execution claims explicit? [Dependencies, Scope and Assumptions]

## Notes

Focus: deployment/security and model/executor authority, standard depth, direct author review before planning as requested by the user. All 16 items are traceable. The native prerequisite helper refused checklist-before-plan; the active template was resolved directly, preserving the requested phase order. This diagnostic does not create a human gate. Findings must be corrected in the owning spec/TASK/plan.

## Ordered Checklist phase - post-Clarify source alignment

- [x] CHK017 Are the single UI/API origin, session authentication, private binding and prohibited service exposures explicit? [Completeness; AC-003]
- [x] CHK018 Do requirements distinguish both image architectures, emulated execution and native GB10 qualification without implying unavailable evidence? [Clarity; AC-002; Scope]
- [x] CHK019 Are fixed Codex, pre-start fallback, platform-integrity halt and post-start failure/no-replay outcomes consistent? [Consistency; AC-007/008/009; M1-IF-001]
- [x] CHK020 Are dedicated Builder credential lifetime, one synchronous call and the sourced tool cap measurable? [Measurability; AC-011/012]
- [x] CHK021 Are automatic fixture-custody boot checks and native evidence/logging initialization required? [Coverage; AC-010/014]
- [x] CHK022 Are Linux Unix-domain IPC, mode0600 and ephemeral session credentials required without an alternate TCP route? [Clarity; AC-005]
- [x] CHK023 Are requested/effective identity, per-call usage and informational subscription observations distinguished? [Consistency; AC-013]
- [x] CHK024 Are consumed agreement owners and revisions canonical, with the fixed-call authorization/profile distinction resolved? [Traceability; Scope; M1-I001]
- [x] CHK025 Do unavailable credentials/hardware constrain only operations that need them rather than becoming invented global prerequisites? [Dependencies; Scope; AC-014]
- [x] CHK026 Are cancellation, restart, side-system independence and reproducible evidence-preserving operations covered? [Coverage; AC-015/016/017]

## Review notes for this invocation

Focus: source completeness and protected execution/evidence boundaries; standard depth; direct author review after Clarify and before Plan. Every item has a traceability reference. Resolve findings in owning TASK/spec; generation was unchecked; this separate direct review found all items satisfied after correcting the owning requirements. No runtime success is claimed.

Review completed 2026-10-16: source alignment, completeness, consistency and measurability checked directly. Corrected M1-001/AC-007 to distinguish external-router profile from protected fixed-baseline call authorization, and M1-004/AC-006 to specify prohibited ZIP members precisely. Other reviewed requirements had no blocking findings. All markers describe requirements quality only; implementation and execution evidence remain pending.
