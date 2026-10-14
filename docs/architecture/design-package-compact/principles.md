# Architecture principles

**Reading level: human immediate.** These rules explain why the connections in the [system architecture](m1-design.md) exist. The separately supplied PRD defines product obligations. Its [receipt](sources/product/README.md) identifies the reviewed source. Exact fields live in the reference layer.

## Research integrity and early stopping

AI4Research supports reproducible, evidence-backed investigation. Long-running agent work is costly, so block material misunderstanding, unsupported assumptions and missing mandatory resources before downstream spending. A plausible result cannot substitute for measured evidence. Preserve traceability and readable artifacts. Allow harmless omissions and deliver correctly obtained scientific negatives.

## Capabilities perform work; infrastructure controls it

A capability capsule is a reusable capability declaration plus a pinned implementation. M1 supports executable code, bounded agents/prompts and supported service adapters. A workflow node encapsulates a product responsibility and its bounded internal subnodes/checks/gates. Each subnode binds one CC under both node and subnode contracts. The Intention Compiler node contains Intention and Requirements work plus separate verifier subnodes. Composite/merged CC creation and arbitrary composition remain later work. Private helpers remain the owning capability's responsibility.

A verifier is a CC whose work is to assess a submitted artifact. A gate is protected non-CC infrastructure that uses checking results to decide whether work may advance. A verifier issues a verdict with reasons and evidence. It cannot stop the scheduler, accept artifacts, waive checks, change policy or write replacement work. A producer's assertion of readiness is data, not release authority.

## Check before continuing

Every work invocation follows **capture → deterministic checks → semantic verifier → protected decision → durable acceptance or halt**. Deterministic failure prevents semantic review. Guard-purpose CC outputs terminate with mechanical validation; there is no recursive verifier chain.

Fixed mandatory work has its output contracts and independently owned checking profiles assigned beforehand. Bound checks incorporate the actual objective, input identities, CC/dependency pins, policy and limits. They are not derived from a favorable producer claim after execution. Check the exact output on every attempt; an earlier pass cannot authorize a changed subject.

Structure and meaning are separate obligations. Each producer CC self-reviews the fidelity or preservation of its own output, and deterministic host checks on spans, references and coverage back that review. The verifier checks the exact output against its declaration and against itself. It never reads the request, the Intent or any worker input, and it does not give a second answer to the user's request.

Only committed protected decisions publish accepted references to successors. Failed evidence persistence blocks release. A valid scientific negative can pass infrastructure verification and be delivered. A research conclusion and a workflow decision are different records.

## PRD and implementation authority

The PRD owns overall requirements and required outcomes. Design interprets the PRD and owns architecture and implementation-facing details that achieve those outcomes. If implementation guidance conflicts, follow the current design. Product obligations remain binding; a conflict that changes an obligation needs an explicitly recorded authorized decision.

## Intermediates are architectural contracts

Intent IR captures what the user means without choosing a solution. Requirements IR is the Research Brief: what the research program must fulfil. The Hypothesis Blueprint later fixes experiment-specific measurements and outcome boundaries before results exist.

Define required information, field meaning, types, attribution, uncertainty and consumers for major artifacts. Use exact schemas at critical shared boundaries. Avoid specifying every private datatype. Humans inspect descriptive JSON files and readable views of the same records. Manifests connect identities, versions and evidence. They do not replace readable substantive content. [Reference principles](reference/README.md) define representation and version rules.

## Freeze authority and preserve evidence

Effective authority is the intersection of each CC's admission, node/subnode contracts and run policy. Additional work CCs use separate subnodes within their declared node. Permissions do not pool. Freeze topology, versions, checking profiles and limits. Instantiate future input references only from accepted predecessors. Observe and enforce effects before they occur. Retrospective verification cannot undo disclosure.

Default to zero automatic repair or replay. Blocking failures halt new dispatch, preserve the attempt and show actionable reasons. Phase 1 requests a clearer submission when intent is unusable. It does not run a clarification conversation. Headless execution never waits. Human corrections create linked new work, not a rewritten pass or changed failed attempt.

## Route models and improve offline

CC model calls go through governed execution and the protected routing/bridge boundary. Record requested and effective model/configuration identities and unavailable telemetry. No CC independently selects a stronger endpoint or silently switches a started invocation.

RSI operates separately from live research. It changes only allowed implementation parts of an eligible target, with frozen contracts/referees and protected fixture custody. Paired evidence is independent of proposer assertions. M1 candidates remain inactive until admission and explicit human activation. D21 permits protected automatic selectability for admitted M2 candidates in future plans only. Changed versions affect future runs. Better scores grant neither broader permissions nor release authority.

## Decisions and source amendments

[Decision history and review reasoning](decision-review.md) retain D1–D18 and D19, the current core-scope amendment. D5 retains the fixed, bounded multi-pass compiler sequence, now aligned with the confirmed PRD (4). D6 retains the authorized bundled Docker/SQLite realization and its recorded source departure. Their source status and rationale remain visible.

## Required now and later

M1 preserves bounded research, local supplied resources, permitted academic retrieval, one opportunity/hypothesis, immutable experimental criteria, isolated execution, matched measurements, negative-result delivery, inspectable evidence, workstation security and independently buildable RSI. D19 promotes bounded pre-dispatch planning into the assigned core while retaining the static baseline; broader integration remains separately scoped. Composite/merged CCs, new planning epochs, remote workers and recursive improver deployment remain future directions.


### D19: assigned core scope and non-blocking improvement

The user-authorized assignment promotes a bounded Planner into the current core, retains a separately selected static baseline and keeps RSI independently buildable without making it a prerequisite. This modifies the delivery allocation in PRD §§1.3, 4.8 and 6.12/6.14 and the core dependency treatment of §§4.4/6.11. It does not waive §4.2 checking, declared authority, resource feasibility or durable release. Full source obligations remain traceable; current core acceptance is not a claim that every full-M1/Phase 3 obligation is complete. [Core build](core-build.md) states the selected behavior.

## D20: declaration/output-only semantic review

The LLM reviewer receives the declaration and exact output only. Worker inputs, conversation and external evidence stay outside its context. Protected deterministic checks retain runtime records. No semantic check establishes fidelity ([D24](decision-review.md#d24)). [Review contract](reference/semantic-review.md).

## D21: iterative generation and automatic admission

November adds Generalist, generation, protected automatic admission and improved planning/MCTS. Admitted M2 versions become selectable for future plans; M1 retains human activation. Frozen runs keep their pins. Composition/fusion moves to December. [Decision details](decision-review.md#d21).
