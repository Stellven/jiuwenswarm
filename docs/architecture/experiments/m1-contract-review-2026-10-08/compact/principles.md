# Architecture principles

**Reading level: human immediate.** These rules explain why the connections in the [system architecture](m1-design.md) exist. The [PRD](sources/product/prd-m1-current-2026-10-07.txt) travels with this design; exact fields live in the reference layer.

## Research integrity and early stopping

AI4Research supports reproducible, evidence-backed investigation. Long-running agent work is costly: block material misunderstanding, unsupported assumptions and missing mandatory resources before downstream spending. A plausible result cannot substitute for measured evidence. Preserve traceability and readable artifacts; allow harmless omissions and deliver correctly obtained scientific negatives.

## Capabilities perform work; infrastructure controls it

A capability capsule is a reusable capability declaration plus a pinned implementation. M1 supports executable code, bounded agents/prompts and supported service adapters. A workflow node has its own objective and Node Execution Contract with one work CC. Additional work CCs use separate gated nodes; composite/merged CCs and internal member graphs remain later work. Private helpers remain the containing capability's responsibility.

A verifier is a CC whose work is to assess a submitted artifact. A gate is protected non-CC infrastructure that uses checking results to decide whether work may advance. A verifier issues a verdict with reasons and evidence; it cannot stop the scheduler, accept artifacts, waive checks, change policy or write replacement work. A producer's assertion of readiness is likewise data, never release authority.

## Check before continuing

Every work invocation follows **capture → deterministic checks → semantic verifier → protected decision → durable acceptance or halt**. Deterministic failure prevents semantic review. Guard-purpose CC outputs terminate with mechanical validation; there is no recursive verifier chain.

Fixed mandatory work has its output contracts and independently owned checking profiles assigned beforehand. Bound checks incorporate the actual objective, input identities, CC/dependency pins, policy and limits. They are not derived from a favorable producer claim after execution. Check the exact output on every attempt; an earlier pass cannot authorize a changed subject.

Structure and meaning are separate obligations. Well-formed Intent that merely lists unknown purpose and result may be faithfully extracted yet unusable. The verifier checks whether the submitted interpretation is coherent and usable by Requirements, using the original request as evidence. It does not give a second independent answer to the user's request.

Only committed protected decisions publish accepted references to successors. Failed evidence persistence blocks release. A valid scientific negative can pass infrastructure verification and be delivered; a research conclusion and a workflow decision are different records.

## Intermediates are architectural contracts

Intent IR captures what the user means without choosing a solution. Requirements IR is the Research Brief: what the research program must fulfil. The Hypothesis Blueprint later fixes experiment-specific measurements and outcome boundaries before results exist.

Define required information, field meaning, types, attribution, uncertainty and consumers for major artifacts. Use exact schemas at critical shared boundaries; avoid specifying every private datatype. Humans inspect descriptive JSON files and readable views of the same records. Manifests connect identities, versions and evidence; they do not replace readable substantive content. [Reference principles](reference/README.md) define representation and version rules.

## Freeze authority and preserve evidence

Effective authority is the intersection of each CC's admission, node contract and run policy. Additional work CCs use separate M1 nodes; no permission pooling. Freeze topology, versions, checking profiles and limits; instantiate future input references only from accepted predecessors. Observe and enforce effects before they occur; retrospective verification cannot undo disclosure.

Default to zero automatic repair/replay. Blocking failures halt new dispatch, preserve the attempt and show actionable reasons. Phase 1 requests a clearer submission when intent is unusable; it does not run a clarification conversation. Headless execution never waits. Human corrections create linked new work, not a rewritten pass or changed failed attempt.

## Route models and improve offline

CC model calls go through governed execution and the protected routing/bridge boundary. Record requested and effective model/configuration identities and unavailable telemetry. No CC independently selects a stronger endpoint or silently switches a started invocation.

RSI operates separately from live research. It changes only allowed implementation parts of an eligible target, with frozen contracts/referees and protected fixture custody. Paired evidence is independent of proposer assertions. Candidates remain inactive until admission and explicit human activation; changed versions affect future runs. Better scores grant neither broader permissions nor release authority.

## Decisions and source amendments

[Decision history and review reasoning](decision-review.md) retain D1–D18 and the new contract/reading choices. D5 authorizes two bounded compiler generations; D6 authorizes the bundled Docker/SQLite realization. Both differ from literal received PRD clauses. They are visible exceptions, not silently claimed compliance.

## Required now and later

M1 preserves bounded research, local supplied resources, permitted academic retrieval, one opportunity/hypothesis, immutable experimental criteria, isolated execution, matched measurements, negative-result delivery, inspectable evidence, workstation security and required RSI. Phase 3 integrates declared dynamic capabilities while retaining the baseline. Composite/merged CCs, new planning epochs, remote workers and recursive improver deployment remain future directions.
