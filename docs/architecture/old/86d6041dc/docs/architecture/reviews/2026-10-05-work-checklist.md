# Architecture cleanup and depth pass: work checklist

This is the progress and evidence record for the October 5 request. It does not introduce product requirements. [Policies](../policies.md) own review rules; [coder requirements](../system/coder-requirements.md) own handoff completeness. Checked boxes record completed work at the stated extent, not runtime acceptance.

| Area | Intended extent | Status / evidence |
|---|---|---|
| Authority cleanup | Canonical ownership index; remove contradictory policy copies; link consumers and distinguish source/history/example/presentation | Written and linked; see completion evidence below |
| Frozen scope coverage | Account for research 3.1–3.9, shared 4.x, workstation 5.x, production/RSI/isolated experiments and blacklist boundaries | Written and linked; see completion evidence below |
| Every active capsule | Twelve capability design packets linking canonical interfaces, internal decisions, bounds, optimization and verification/RSI hooks | Written and linked; see completion evidence below |
| Benchmark material | Primary-source catalogue, applicability, provenance/license/leakage cautions and fixture import boundary; no downloaded hidden corpus | Written and linked; see completion evidence below |
| Planner and Codex abstraction | Explicit decision authority, pre-freeze call authorization, complete proposal validation, budget enforcement and immutable dispatch | Written and linked; see completion evidence below |
| Existing software | Inspect pinned OpenJiuwen agent-core and JiuwenSwarm symbols; distinguish reused mechanisms and new adapters | Written and linked; see completion evidence below |
| Central diagrams | Shallow context and deeper module/process/data/control diagrams; temporal paths and failure authority | Written and linked; see completion evidence below |
| Adversarial review | Attempt boundary bypasses; resolve source-backed findings and record limits | Written and linked; see completion evidence below |
| Presentation variant | Organized lines with precise precedent, local benefit, owner link and honest evidence status | Written and linked; see completion evidence below |
| Mechanical verification | Architecture/schema/link/coverage/story checks, diagram parse/render where available, diff whitespace | Passed; exact commands/results below |
| Provenance | Inspect relevant diff; commit coherent docs only; fetch and push without unrelated changes | Relevant batch checked; publication is recorded in Git history |

## Completion report

This pass completed the documentation work at the extent below. No implementation, real account inference, sandbox probe, dataset score or system benchmark result is claimed by this checklist.

### Completed extent

- [x] Published authority/change-impact routing; distinguished authored wire schemas, semantic API owners, generated views, received inputs and historical evidence. Replaced the duplicated 400-line guard catalogue with an owner-link index and preserved its history. Fixed 33 broken active section links; frozen received bytes are unchanged.
- [x] Mapped all three tracks, research 3.1–3.9, shared/workstation areas and construction stages 0–9. This is complete navigation coverage; the source/reviewer audits were bounded, not a new line-by-line proof of every requirement.
- [x] Added design/defect/optimization packets for all twelve current capability identities, linked to canonical stage/operator/verifier owners. Corrected Search RSI/restart, nested Verification, dependency access and helper classification. Added provisional POC two-call and Report one-call authoring sequences, enforced through pinned direct-call profile limits. Prompts/code and measured optimization remain downstream.
- [x] Researched primary-source benchmark material and asset-level license/custody rules. Supplied project-owned mechanical, semantic and boundary fixture families. No external corpus was imported, hidden fixture set installed or benchmark score measured.
- [x] Closed planner bootstrap, complete-envelope validation, objective identity, pre-freeze bridge authorization and aggregate/direct-call durability. Production validates its fixed intake-based envelope; isolated planning uses a Brief and Codex through the replaceable protected provider. Private RSI/oracle accounting remains private.
- [x] Reinspected pinned agent-core, JiuwenSwarm and CodeSearch sources. Six reuse groups distinguish existing symbols from CC overrides, including native retry/cache behavior, incomplete WAL durability, shared Codex custody and unconstrained native Leader construction.
- [x] Added a central diagram atlas with context, authority, inference, generated research spine, track separation and durable ordering. Split crossed-edge views after rendering. Preserved the complete deep wiring canary as a zoom/reference view, rather than making its large canvas the explanation entry point.
- [x] Recorded seven author-audit findings, 25 adversarial fixture scenarios and three further fresh-review findings. The independent reviewer reread all three integrated corrections and found them closed at design-contract level. Attack executions remain unrun.
- [x] Began the presentable variant: reusable claim/reason/owner lines with primary precedents and explicit evidence status. It makes no unsupported company-equivalence, performance, endorsement or unbreakable-system claim.
- [x] Generated projection examples and the production data-spine diagram from canonical examples/plan so later changes do not require hand-editing duplicate views.

### Observed documentation checks

Executed from the repository root on Windows with Python 3.12.10 and jsonschema:

| Command | Observed result |
|---|---|
| python docs/architecture/_tools/arch_lint.py | ok; refreshed generated exports/graph/example views |
| python docs/architecture/_tools/arch_lint.py --check | ok |
| python docs/architecture/_tools/validate_services.py | 464 schema cases; includes planning/public-call reservation variants, direct-call limits and production versus isolated objective bindings |
| python docs/architecture/_tools/validate_handoff.py | 20 frozen hashes; eight independent module input pairs; 18 production joins; RSI/admission seam; 131 generated payload checks |
| python docs/architecture/_tools/validate_stories.py | 136 story/schema/plan/numeric structure checks |
| python docs/architecture/_tools/validate_library.py | 1769 active file/anchor links; twelve capability packets; three tracks and ten construction-stage navigation rows |
| git diff --check | passed |

Mermaid 11.12 CLI dependency package and its browser Mermaid bundle were installed only in the outside-repository scratch directory C:/Users/m50066326/huawei/architecture-checks-2026-10-05. Its check-diagrams.mjs used Puppeteer with cached Chromium 131 to parse 50 active Mermaid blocks and render twelve central/planner/temporal blocks, with zero parser/render failures. Historical/received/archive diagrams were excluded. SVG/PNG results and diagram-results.json remain derived scratch artifacts. Context, authority, inference, research-spine and failure views were visually inspected; the detailed all-edge map remains large and requires zoom. Parse/render success does not prove the diagram's behavioral claims.

### Remaining extent and evidence limits

Actual capsule prompts, program code, datasets/label adjudication, supported account/version checks, container isolation probes, measurement fixtures, provider cancellation and end-to-end acceptance executions belong to implementation. Optimization items are hypotheses with comparison procedures, not demonstrated speed/cost/quality improvements. Full requirement acceptance needs those observations and exhaustive downstream clause-to-evidence allocation. Reviewed drafts remain drafts; no lock or refreshed historical checkpoint is implied.

The checked documentation batch excludes the user's unrelated video deletions and Obsidian state. Its commit/push identity is available in Git history and the completion reply. No implementation or Spec Kit artifacts were authored.
