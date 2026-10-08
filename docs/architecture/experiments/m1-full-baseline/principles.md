# Architecture principles

**Reading level: human immediate.** These rules explain why the connections in the [system architecture](m1-design.md) exist. The [PRD](sources/product/prd-m1-current-2026-10-07.txt) travels with this design; exact fields live in the reference layer.

## Research integrity and early stopping

AI4Research supports reproducible, evidence-backed investigation. Long-running agent work is costly: block material misunderstanding, unsupported assumptions and missing mandatory resources before downstream spending. A plausible result cannot substitute for measured evidence. Preserve traceability and readable artifacts; allow harmless omissions and deliver correctly obtained scientific negatives.

## Capabilities perform work; infrastructure controls it

A capability capsule is a reusable capability declaration plus a pinned implementation. It may be executable code, a bounded agent/prompt, a service adapter or a composite of admitted members. A workflow node has its own objective and Node Execution Contract; it can bind several CCs. Private helpers remain the containing capability's responsibility.

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

Effective authority is the intersection of each CC's admission, node contract and run policy. Multi-CC nodes do not pool permissions. Freeze topology, versions, checking profiles and limits; instantiate future input references only from accepted predecessors. Observe and enforce effects before they occur; retrospective verification cannot undo disclosure.

Default to zero automatic repair/replay. Blocking failures halt new dispatch, preserve the attempt and show actionable reasons. Phase 1 requests a clearer submission when intent is unusable; it does not run a clarification conversation. Headless execution never waits. Human corrections create linked new work, not a rewritten pass or changed failed attempt.

## Route models and improve offline

CC model calls go through governed execution and the protected routing/bridge boundary. Record requested and effective model/configuration identities and unavailable telemetry. No CC independently selects a stronger endpoint or silently switches a started invocation.

RSI operates separately from live research. It changes only allowed implementation parts of an eligible target, with frozen contracts/referees and protected fixture custody. Paired evidence is independent of proposer assertions. Candidates remain inactive until admission and explicit human activation; changed versions affect future runs. Better scores grant neither broader permissions nor release authority.

## Decisions and source amendments

These identifiers retain their history. Local exceptions are explicit; they do not rewrite received PRD bytes.

| ID | Current decision | Source disposition |
|---|---|---|
| D1 | Static Phase 1 baseline; bounded direct admitted CC planning in Phase 3 | §§1.3, 4.8, 6.5, 6.12; no live restructuring |
| D2 | Deterministic checks, independent verifier, protected gate | §§1.4, 4.2; replaces optional semantic checking |
| D3 | Protected host owns release; freeze referee assets | §§4.1.5, 4.2.8, 4.4.5 |
| D4 | No automatic repair/replay; blocking outcomes halt | §§1.4, 4.6.4; human correction is new linked work |
| D5 | Separate bounded generative Intent and Requirements CCs, each checked | **Authorized local exception** to §§3.2/4.7 single-generation Brief fallback. Freeze combined budgets; retain non-interactive baseline |
| D6 | One Docker app, Python/TypeScript, SQLite state and artifact files | **Authorized local realization/exception** to source container/native-only and persistence assumptions in §§4.1.4, 4.5, 5.1, 5.2, 5.4. Generated-code confinement remains separately required |
| D7 | Preserve CC concepts with one reconciled current machine contract | §4.1; historical sources are provenance, not competing serialization authorities |
| D8 | Required offline RSI in Phase 2; interfaces precede planner completion | §§1.3, 4.4, 6.11; immediate slice excludes execution |
| D9 | Mandatory evidence fails closed; optional telemetry can be unavailable | §§1.4, 4.2, 4.5, 6.4 |
| D10 | Verifier assesses; gate decides; control plane shows halt/triage | §§4.2, 4.3.4, 4.6.4, 5.3; headless never waits |
| D11 | Optional benchmarker uses ordinary scoped client boundary | §§5.3.1, 5.6.5; no privileged product control |
| D12 | Durable product identity/profile separate from local execution host | §§1.1, 2.3, 5.4; optional cloud profile storage grants no remote execution |
| D13 | Node objective/contract differs from CC invocation | §§1.4, 4.1, 4.2; per-call checking plus node aggregate acceptance |
| D14 | Account for all stages/phases and applicable Phase 3 efforts | §§1.3, 6.12, 6.14; preliminary Leader checks never replace plan acceptance |
| D15 | Independent guard profiles and output-led evidence review | §§1.4, 4.1, 4.2, 5.4; review is assessment, not replacement authorship |
| D16 | Three reading levels; critical schemas and other major field contracts | §§1.7, 6.13 and October 7 user direction; replaces agent-owned competing wire shapes |
| D17 | Intent acceptance requires fidelity **and** usefulness to Requirements | §§3.2.1, 4.7.3, 4.2; topic-only extraction with material missing purpose/result blocks |
| D18 | Readable IRs, decisions and views; raw evidence separate | §§5.1.2, 5.3.1, US05–US17; no mandatory opaque binary decoding |

## Required now and later

M1 preserves bounded research, local supplied resources, permitted academic retrieval, one opportunity/hypothesis, immutable experimental criteria, isolated execution, matched measurements, negative-result delivery, inspectable evidence, workstation security and required RSI. Phase 3 integrates declared dynamic capabilities while retaining the baseline. Fusion, new planning epochs, remote workers and recursive improver deployment remain future directions.
