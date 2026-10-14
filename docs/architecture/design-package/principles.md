# Architecture principles

**Reading level: human immediate.** These rules explain why the connections in the [system architecture](m1-design.md) exist. The separately supplied PRD defines product obligations. Its [receipt](sources/product/README.md) identifies the reviewed source. Exact fields live in the reference layer.

## Research integrity and early stopping

AI4Research supports reproducible, evidence-backed investigation. Long agent runs are costly, so block material misunderstanding, unsupported assumptions and missing mandatory resources before downstream spending. A plausible result cannot substitute for measured evidence. Keep artifacts traceable and readable. Allow harmless omissions and deliver correctly obtained scientific negatives.

## Capabilities perform work; infrastructure controls it

A capability capsule is a reusable capability declaration plus a pinned implementation. M1 supports executable code, bounded agents and prompts, and supported service adapters. A workflow node encapsulates a product responsibility and its bounded subnodes, checks and gates. Each subnode binds one CC under both node and subnode contracts. The Intention Compiler node holds Intention and Requirements work plus separate verifier subnodes. Composite or merged CCs and arbitrary composition remain later work. Private helpers remain the owning capability's responsibility.

A verifier is a CC that assesses a submitted artifact. A gate is protected non-CC infrastructure that uses checking results to decide whether work may advance. A verifier issues a verdict with reasons and evidence. It cannot stop the scheduler, accept artifacts, waive checks, change policy or write replacement work. A producer's claim of readiness is data, not release authority.

## Check before continuing

Every work invocation follows **capture → deterministic checks → semantic verifier → protected decision → durable acceptance or halt**. Deterministic failure prevents semantic review. Guard-purpose CC outputs end with mechanical validation, so there is no recursive verifier chain.

Fixed mandatory work has its output contracts and independently owned checking profiles assigned beforehand. Bound checks use the actual objective, input identities, CC and dependency pins, policy and limits. They are never derived from a favorable producer claim after execution. Check the exact output on every attempt. An earlier pass cannot authorize a changed subject.

Structure and meaning are separate obligations. Each producer CC self-reviews the fidelity or preservation of its own output, and deterministic host checks on spans, references and coverage back that review. The verifier checks the exact output against its declaration and against itself. It never reads the request, the Intent or any worker input, and it does not answer the user's request a second time.

Only committed protected decisions publish accepted references to successors. Failed evidence persistence blocks release. A valid scientific negative can pass infrastructure verification and be delivered. A research conclusion and a workflow decision are different records.

## PRD and implementation authority

The PRD owns overall requirements and required outcomes. Design interprets the PRD and owns architecture and implementation-facing details. If implementation guidance conflicts, follow the current design. Product obligations stay binding. A conflict that changes an obligation needs an explicitly recorded authorized decision.

## Intermediates are architectural contracts

Intent IR captures what the user means without choosing a solution. Requirements IR is the Research Brief: what the research program must fulfil. The Hypothesis Blueprint later fixes experiment-specific measurements and outcome boundaries before results exist.

Define required information, field meaning, types, attribution, uncertainty and consumers for major artifacts. Use exact schemas at critical shared boundaries and avoid specifying every private datatype. Humans inspect descriptive JSON files and readable views of the same records. Manifests connect identities, versions and evidence and do not replace readable content. [Reference principles](reference/README.md) define representation and version rules.

## Freeze authority and preserve evidence

Effective authority is the intersection of each CC's admission, node and subnode contracts and run policy. Additional work CCs use separate subnodes within their declared node. Permissions do not pool. Freeze topology, versions, checking profiles and limits. Instantiate future input references only from accepted predecessors. Observe and enforce effects before they occur, because retrospective verification cannot undo disclosure.

Default to zero automatic repair or replay. Blocking failures halt new dispatch, preserve the attempt and show actionable reasons. Phase 1 requests a clearer submission when intent is unusable and runs no clarification conversation. Headless execution never waits. Human corrections create linked new work, not a rewritten pass or a changed failed attempt.

## Route models and improve offline

CC model calls go through governed execution and the protected routing and bridge boundary. Record requested and effective model and configuration identities and unavailable telemetry. No CC selects a stronger endpoint or silently switches a started invocation.

RSI runs separately from live research. It changes only allowed implementation parts of an eligible target, with frozen contracts and referees and protected fixture custody. Paired evidence is independent of proposer assertions. M1 candidates stay inactive until admission and explicit human activation. D21 permits protected automatic selectability for admitted M2 candidates in future plans only. Changed versions affect future runs. Better scores grant neither broader permissions nor release authority.

## Decisions and source amendments

[Decision history and review reasoning](decision-review.md) hold every decision, D1 onward, with its source status and rationale.

## Required now and later

M1 preserves bounded research, local supplied resources, permitted academic retrieval, one opportunity and hypothesis, immutable experimental criteria, isolated execution, matched measurements, negative-result delivery, inspectable evidence, workstation security and independently buildable RSI. D19 promotes bounded pre-dispatch planning into the assigned core and keeps the static baseline. Broader integration remains separately scoped. Composite or merged CCs, new planning epochs, remote workers and recursive improver deployment remain future directions.

### D19: assigned core scope and non-blocking improvement

A bounded Planner joins the current core, the static baseline stays, and RSI stays independently buildable ([D19](decision-review.md#d19), [Core build](core-build.md)).

## D20: declaration/output-only semantic review

The semantic reviewer receives the declaration and exact output only ([D20](decision-review.md#d20), [review contract](reference/semantic-review.md)).

## D21: iterative generation and automatic admission

November adds Generalist, generation and automatic admission, and composition moves to December ([D21](decision-review.md#d21)).
