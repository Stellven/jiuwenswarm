---
id: capsule.why
type: capsule
level: detail
status: proposed
provides: [capsule.why]
depends_on: [capsule.md]
tags: [capsule, context]
prd: [4.1.1]
---

# Why Capability Capsule

PRD: 4.1.1

> Answers: Why do we use Capability Capsules at all?

> **We cannot check something that claims nothing.** An AI4Research run is a chain: ingest, extract, verify, design, report. One wrong capability early makes everything after it wrong while the run can still finish green. So a capability must be shown to be right before it [runs](../system/lifecycle.md#term-run), not discovered wrong afterwards.

- **Importing is solved, promising is not.** MCP declares a tool's name and arguments; A2A delegates to agents. Neither declares effects, preconditions or guarantees, so neither says whether a capability should be allowed in.
- **Value needs a stated goal.** "Better" and "correct" are relations to a declaration. With none, there is nothing to verify against, and no safe self-improvement.
- **Declared, then observed.** CC declares first, because a declaration can be verified and found wrong, then records every call against it. An observation with no stated target measures nothing.
- **The evidence.** Self-built tools mostly fail held-out tests of their own job while running cleanly (215 of 222, arXiv 2604.00392); unverified self-generated skills barely beat none; an agent removed the logging its checker read, so the referee must be protected; look-alike skills degrade selection. Verify primary figures before reusing them in a presentation ([references](references.md)).
- **What openJiuwen lacks.** It has the engine (workflow runtime, tool cards, permission engine) but no effects, preconditions, guarantees, version or hash on any tool or skill spec, no installed-capability record, and a permission check keyed only on tool name and arguments. The [Declaration](fields.md#term-declaration) is that missing column ([permissions](permissions.md)).

## What CC is not

- Not a runtime or framework: CC runs nothing; [tools](tools.md) read the Declaration and write records.
- Not a model router: selection picks [capsules](capsule.md#term-capability-capsule), never models.
- Not a guarantee of correctness in every case or of undoing emissions: it makes each promise checkable and each failure attributable.

Future directions are listed in [future state](future-state.md).
