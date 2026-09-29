# Capsule module context guide
This is a preparation guide, not an installed subtree AGENTS file or a claim that a corresponding code directory exists. Use the [local template](../../AGENTS_local.md) after confirming actual paths.

## Domain focus
Confirm what the product calls a capsule before choosing code paths. Define creation, read/update, version identity, persistence and reconstruction boundaries from the PRD. Identify state integrity and applicable migration/recovery requirements.

## Entry and boundaries
- Parent TASKS / current TASK / executor: resolve from the actual program register.
- PRD clauses and architecture nodes: bind when the master inputs arrive.
- Actual implementation, callers and existing subtree AGENTS: inspect before implementation.
- Owned/consumed interfaces: embed definitions in the owning TASK; reference IF IDs and revisions.
- Unknown requirements, commands and thresholds: record with resolution conditions; do not fabricate them.

## Work and verification
Use one Spec Kit directory per TASK. spec.md owns measurable ACs; plan.md owns blocks and checks; tasks.md owns work and the evidence matrix.

Verify each relevant block's normal, boundary and failure behavior, then the real connected boundaries and the contribution to the system TASK. Store actual runs in feature evidence/. Missing services and unrun checks remain visible.

Keep progress out of this guide. No separate authorization, implementation checklist, test-report, review or handoff file is required. Follow the [SOP](../../Code_SOP.md) and [verification method](../VERIFICATION.md).
