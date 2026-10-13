# Design method and architectural integrity

**For design authors and human reviewers.** Question answered: what must architecture explain, how deeply, and how do we keep it coherent as it changes? Start product reading at [README](README.md). This document guides design work; it is not an additional coding-agent prerequisite.

## Purpose and authority

Architecture transfers our project knowledge to implementers: what the system is for, why its boundaries exist, what information crosses them, and what future work those boundaries must accommodate. A foundation for a house needs different decisions from an isolated concrete slab. Future context changes present design even when future features are not built now.

AI4Research supports evidence-backed research: reproducing claims, designing bounded experiments and evaluating results. Long-running agent work is costly. Block a materially wrong or unusable request before spending on downstream work; never optimize for a plausible answer at any cost. Preserve reproducibility, traceability, auditability and readable artifacts. Optional omissions are not automatically blockers, and a correctly obtained negative result is valuable research.

| Authority | Owns |
|---|---|
| Verbatim PRD | Product behavior, M1 scope, invariants and product acceptance |
| Maintained architecture | Components, connections, authority, shared representations, deployment and architectural obligations realizing the PRD |
| Native implementation specifications | Concrete realization, interface agreements, executable acceptance cases and evidence under repository governance |
| Runtime evidence | What the implementation actually did; a document or diagram cannot supply this proof |

**Implementation precedence:** The PRD owns overall requirements and required outcomes. Design interprets the PRD and owns architecture and implementation-facing details that achieve those outcomes. If implementation guidance conflicts, follow the current design. Product obligations remain binding; a conflict that changes an obligation needs an explicitly recorded authorized decision.

Architecture can require a module-specific test because the PRD need not name every mechanism. It cannot weaken product acceptance. [Decisions](principles.md#decisions-and-source-amendments) disclose authorized departures, including D5 and D6.

## What we claim and what we leave open

| Statement class | Required treatment |
|---|---|
| Product requirement | Cite the current source; retain its exclusions |
| Authorized architecture decision | State selected behavior, authority and rationale; identify any source departure |
| Standardization choice | Specify one compatible representation; do not claim it is scientifically optimal |
| Assumption | State its consequence and how it is checked; failed mandatory assumptions block affected work |
| Implementation choice | Give purpose, constraints, expected outcome and evidence obligations; let the owning specification select the mechanism |
| Future context | State the boundary to preserve and the feature not yet provided |

Do not present guesses as facts. Do not hide a material product or compatibility decision behind “implementation detail.” Readiness requires resolved behavior at shared boundaries; it does not require a preselected private function or algorithm.

## Required depth

For each major responsibility specify purpose, inputs and producers, outputs and consumers, broad approach, prerequisites, authority, limits, failure/recovery, evidence, phase and reason for the boundary. The [component obligations](research-design.md#architectural-component-obligations) connect this standard to full M1.

Shared fields are architecture. Define their meaning, requiredness, types, identity, attribution, uncertainty and use. Exact schemas belong at consequential compatibility boundaries; other artifacts need field contracts. Manifests identify named content, versions, hashes, relationships, audience and omissions. They cannot substitute for the substantive readable artifact. Agents must not independently invent conflicting representations.

Define **producer obligations → deterministic checks → semantic assessment → protected decision → consumer use**. Verifier CCs assess; protected non-CC code controls progression. Work cannot self-certify. The Intent boundary is one application of this principle, not the complete system.

Future planning, new model routes and wider RSI targets need preserved contracts, lineage, permission boundaries and evidence now. They do not justify speculative infrastructure. Internal algorithms and storage/transport adapters may vary only within the declared behavior and compatibility constraints.

## Three tiers and human review

| Tier | Read to answer | Human review |
|---|---|---|
| Immediate: three-document route | What is the whole system, who connects, who decides, where does it run and what is built? | Review product intent, architecture, authority, deployment and phase coverage without opening schemas |
| Potential: selected topics | How does a responsibility work, why, and what passes or blocks? | Review affected components and both sides of changed connections; retain consequential rationale |
| Reference: contracts/examples | What information must compatible implementations exchange? | Relevant domain and interface reviewers inspect critical fields, identities, assumptions and evidence relationships |

All three tiers require human review at their relevant scope. One reviewer need not read every reference file. Authors select the affected reading set and explain its change impact. Automated checks support human judgment; they do not replace it. This is design review, not a new coding approval workflow or a runtime permission gate.

Use plain technical English and one canonical term per component. Every sentence must explain behavior, constraint, connection, rationale or review evidence. Prefer purposeful tables and point form. Shorten repetition, not information required to make a decision. Diagrams must show actual authority and label omitted repeated checks.

## Change and knock-on effects

1. Identify the source requirement, decision or assumption being changed and its phase.
2. Trace producers, consumers, artifact fields, permissions, model disclosure, deployment, persistence, inspection and failure behavior. Include indirect consumers such as exports, RSI and historical readers.
3. Change authoritative definitions first; update affected tier summaries, examples and diagrams together. Received PRD/source bytes remain immutable.
4. Determine compatibility: field/meaning changes need a version disposition and consumer migration; private changes still need affected evidence rechecking. Frozen runs and historical decisions retain original identities. Update existing repository authorities when implementation allocation/interfaces change.
5. Recheck connected scenarios and obtain human review at affected tiers. Report unresolved conditions and stale implementation evidence; do not manufacture a pass.

| Change | Typical affected boundaries |
|---|---|
| Brief metric or assumption | Intent/default attribution, planning coverage, hypothesis criteria, benchmark measures, verdict rationale, report |
| CC port or permission | Declaration/admission, binder, invocation, checks, routing/effects, library and RSI profile |
| Artifact field/version | Producer, schema/field contract, consumers, readable views, export/import and examples |
| Container or identity | Startup, published/private ports, session authentication, model IPC, volumes, isolation, doctor and clients |
| Gate or evidence policy | Check assignments, review context, release transaction, failure behavior, scheduler and invalidated verification |

Use current canonical behavior rather than requiring readers to reconstruct history. Existing TASKS/TASK/native specifications retain their authority; create no parallel handoff or change-card system.

## Team decisions and implementation handoff

**Architecture connects product intent to implementable work.** The PRD sets outcomes; code tasks are too detailed to own the system picture. Architecture is the level where contributors can see component boundaries, dependencies, shared contracts and why a choice was made. Clear instructions help coding agents and human contributors for the same reason: both need unambiguous inputs, outputs and constraints.

- **Review material changes with affected owners.** Check impacts on components, contracts, authority, phase exits, evidence and schedule. Record the decision, reason, owner and follow-up in the existing design and linked work records. Keep superseded decisions for context; do not create a parallel change log.
- **Maintain high-level design CI.** Architecture owns lightweight scripts and reusable agent skills/workers that review changes to system design and its documentation. Check structure, links, names, versions and references mechanically. For English and Chinese documents, check that required counterparts exist and that shared identifiers, contracts and links agree; use agents to flag possible meaning drift for owner review. Report findings and notify affected owners. Do not let agents silently rewrite, translate or approve consequential changes.
- **Reuse the sidecar where it fits.** Run checks as bounded jobs with attributable inputs and retained results. Keep this review lane separate from product gates; start with useful checks and extend it when experience shows a need.
- **Make rotation safe.** Keep current decisions, rationale, open questions, accepted state and evidence links in Git beside the authoritative design. New owners should be able to understand and modify it without private handoff context. Component responsibility persists even when a person changes roles.
- **Keep plans honest.** Track target dates separately from forecasts and assumptions. When dates move, show affected dependencies and choices; change scope or commitments by team decision. At a phase boundary, carry accepted evidence, unfinished work and open decisions into the next baseline.

**Example — model access is late.** Keep the working static path, mark real model integration blocked, and update dependent tasks and forecast. Do not count mock results as integration evidence or weaken the exit. This preserves progress and makes the schedule decision visible.

Fix a design defect in the authoritative design and refresh affected evidence. Fix code that diverges from correct design in implementation work; logs help diagnose it but are not the decision record.

Use the Git-tracked full-package [glossary](glossary.md) as the naming source. The compact glossary mirrors it. Any team member can propose edits in Git; affected owners check meaning and affected uses. Use the canonical terms in design, tasks, specifications and agent instructions. Keep stable machine identifiers in the contract and task registries. This gives people and agents one shared reference. Definitions and examples still matter; matching names alone do not prove shared understanding.

Keep detail at the level needed to decide boundaries, shared contracts, authority, failure behavior and phase exits; leave private algorithms to implementation plans. Full versus compact remains an open question. Use the project’s matched experiment protocol to compare consequential ambiguity, compatibility defects, clarification and correction effort at equal scope, not document size alone.

Keeping both packages current adds a second edit and review pass and creates drift risk. In the October 8 delivery snapshot, compact has 36% fewer explanatory words (15,961 vs. 25,066) and 10 diagram views (full: 26), with shared contracts preserved. If only one remains, full costs more reading and diagram upkeep; compact costs less, but may need more clarification if its shorter rationale leaves gaps. No paired implementation results yet show that compact performs as well. Use the experiment before choosing one; then make one package authoritative and freeze the other as historical evidence instead of maintaining two live copies.

## Mechanical document checks

Keep deterministic checks beside the design: the portable package validator already checks schemas, examples, local links/anchors, the orientation word target and diagram projections; experiment checkers pin paired inputs, compare shared content and count words. Extend these before adding a parallel tool. Structure/link failures and file/word drift are good script targets. Token counts vary by tokenizer and model, so report them only with the tokenizer/version used and never treat them as design quality. Scripts cannot judge whether rationale is sufficient, decisions are sound or the workflow is understandable; retain owner review and matched implementation evidence.

## Integrity review

| Pass | Required evidence of design integrity |
|---|---|
| Coverage | Actual PRD obligations and exclusions mapped to responsibilities/phases; explicit source exceptions |
| Compatibility | Producer fields meet consumer needs; versions, references, authority and human views agree |
| Feasibility | No circular prerequisites; model access, provisioned resources, isolation and persistence can coexist; mandatory unsupported assumptions block |
| Scenarios | Normal and failing connected paths, including scientific negatives, data loss, restart, unavailable services and RSI isolation |
| Mechanical/visual | Valid contracts/examples, local links, hashes, portable copy; every diagram audited and changed views rendered/inspected |
| Human | Independent immediate-route read, selected deeper review, critical field review and unresolved-question disposition |

Architecture obligations guide implementation tests: prove a real consumer uses released output, invalid output cannot release it, effects are confined before execution, and evidence reconstructs the decision. Concrete fixtures and thresholds belong to native specifications unless already prescribed by the PRD or design.

Ready to specify means no unresolved material behavior or shared-contract question. Ready to connect requires actual compatible producer/consumer evidence. Ready for M1 requires its product exits and evidence. These are different claims.

## Measuring sufficient detail

A cut-down experiment carries the same full M1 scope, separately supplied PRD receipt, decisions and authoritative contracts. Reduce explanatory depth and examples, never silently weaken obligations. Pin both input snapshots, isolate agent contexts and use matched assignments/evaluation. Measure invented interfaces, clarification, omitted responsibilities, compatibility, failure handling and evidence quality alongside input length. An Intent-only trial measures only that boundary; it cannot establish full-M1 sufficiency. Results inform later design depth; no size target proves effectiveness.

## Focused human review questions

1. Does the immediate route explain all M1 responsibilities and Docker/browser/model/isolation placement?
2. Can each consumer use the specified output, including negative and unavailable outcomes?
3. Do permissions, verdicts, decisions and persistence have one clear owner?
4. Are assumptions and future seams honest, feasible and compatible with M1 scope?
5. What changed, which evidence became stale, and what must still be demonstrated?

The [review record](coverage.md) reports performed checks and their limits. Human review completion must be recorded from actual review, not inferred from an author polishing the text.


## Reading ownership and consolidation

The immediate route is README → system architecture → principles. Phase exits and the bounded assignment are selectively required before reviewing that build. Component authors/reviewers use the second tier; implementation agents use the relevant field contracts as well. Human field review focuses on changed meanings, authority and cross-component compatibility, rather than reading every diagnostic type.

| Definition | Authoritative home | Summaries may do |
|---|---|---|
| System connections and placement | System architecture; deployment detail in placement | Identify owners and link details |
| Planning/freeze/dispatch | Workflow | Explain dependency release without restating every check |
| Independent checking and release | Guard design; exact records in reference | State who assesses and who decides |
| Scientific stage obligations | Research design | Summarize journey and valid negative delivery |
| Offline improvement | Offline RSI | Locate profile/referee/admission/activation boundaries |
| Field spelling/type/version | Exact schema or field catalog | Explain meaning without redefining representation |

Consolidate repeated explanation only after its authoritative home answers purpose, connections, approach, pass/block behavior, authority and rationale. Preserve useful examples and deeper causal explanation in the full package. [Decision review](decision-review.md) records selected tradeoffs. New comparison pairs are frozen separately; no revision rewrites an old input identity.
