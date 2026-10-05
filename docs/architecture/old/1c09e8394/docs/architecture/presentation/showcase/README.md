# M1 architecture - start here

**Audience:** teammates, reviewers and leads. **Snapshot:** 5 October 2026; current draft, not implemented acceptance.

## The short route

1. [Quick presentation PDF](../../../../output/pdf/m1-architecture-presentation-2026-10-05.pdf): six pages integrating decisions, capsule/system diagrams, failure handling, testing and one wiring appendix. [Editable presentation points](presentation.md).

   [Detailed report](../../../../output/pdf/m1-architecture-current-state-2026-10-05.pdf) has the longer explanation and all four appendix views.
2. [Whole-system overview](../../system/overall-draft.md): all twelve CC identities, placement, dynamic/conditional tracks, simplified authority and I/O.
3. [Actual information flow](../../system/information-flow.md): all 23 required production input bindings; full, observability-hidden, RSI-hidden and core variants; failure/recovery.
4. [Diagram atlas](../../system/diagram-atlas.md): shallow-to-deep map and temporal expansion.

## If someone asks...

| Question | Go here |
|---|---|
| What have we decided and why? | [Report](../architecture-report-2026-10-05.md), [decision ledger](../../decisions.md) |
| What does each capsule do and exchange? | [Capability guides](../../m1/capability-designs.md), [production ports](../../m1/pipeline.md) |
| How do failures stop work and recovery reuse evidence? | [Flow/recovery graph](../../system/information-flow.md), [lifecycle](../../system/lifecycle.md), [stories](../../stories/README.md) |
| Who owns authority, code placement and shared definitions? | [Authority](../../authority.md), [module map](../../system/modules.md) |
| How do we test and review it? | [Invocation/failure hooks](../../system/verification.md), [bounded agent policy](../../review-workflow.md) |
| How does this help coders build it? | [Coder requirements](../../system/coder-requirements.md), [full handoff](../../system/handoff.md), [construction order](../../system/build-order.md) |
| What remains unproved? | [Validation obligations](../../open-issues.md), [latest diagram review](../../reviews/2026-10-05-overall-diagrams-review.md) |
| What source establishes scope? | [Frozen master source set](../../../product/SOURCE_FREEZE.md) |

## Sharing and maintenance

This folder is the presentation entry point, not another architecture authority. Its links open the canonical pages; edits are made there once. The PDF is a dated derived reading view. Show the short route first, then follow the question links. Sharing this index alone requires access to the repository; send the PDF when the audience needs a self-contained artifact. Historical review results and unrun product/security scenarios are not current acceptance claims.
