---
type: capsule
status: draft
tags: [capsule, guards, navigation]
---

# Guards: find the owning check

A guard checks record shape, integrity, permission or a boundary contract. Its product rule belongs to the owner below; this page neither maintains a parallel guard specification nor invents reason codes. The [historical catalogue](../archive/guards-2026-10-05.md) records earlier design ideas and is outside the coding authority path.

| What needs checking | Canonical rule and callable boundary |
|---|---|
| Closed envelope, field shape, hash and reference | [Common](../schemas/common.md), owning [schema/type](../types/types.md), [store](../system/storage.md) |
| Declaration and supported M1 fields | [Declaration](fields.md), [field enforcement](tools.md#field-validation-and-enforcement-map), [admission](admission.md) |
| Dependency and port closure | [Freeze](toolchain.md#m03-freeze-the-binding-writer), [planner validation](../system/planner.md), [Binding](../schemas/binding.md) |
| Call input, code, effect, permission and host frame | [Runner](runner.md), [permissions](permissions.md), [process boundary](process-boundary.md) |
| Gate criteria, verdict fold and release | [Gate host](gate-host.md), [check ABI](../schemas/checks.md), [Verification](../schemas/verification-record.md), [lifecycle](../system/lifecycle.md) |
| Scientific thresholds and trustworthy measurements | [Measurement protocol](../m1/measurement-protocol.md), [research checks](../m1/research-gates.md) |
| Model authorization, quota and cancellation | [Environment](../system/environment.md), [reservations](../system/records.md), [profiles](../schemas/profiles.md) |
| Private fixture access and allowed RSI changes | [Oracle](fixture-oracle.md), [RSI engine](rsi-engine.md) |
| Installation, config, image and child confinement | [Environment](../system/environment.md), [deployment](../system/deployment.md), [doctor probes](../system/verification.md) |

The [standard policy registry](../schemas/policy.md) owns reason codes. Capsule-specific diagnostics remain safe detail under an existing runner reason unless a reviewed policy revision adds a standard code. [Boundary cases](../system/boundary-cases.md), [adversarial cases](../reviews/2026-10-05-adversarial-design.md) and [stories](../stories/README.md) supply scenario views, not extra guard rules. An unimplemented check remains a named validation obligation, not a pass.
