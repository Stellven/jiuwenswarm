---
type: design
status: draft
version: 1
owner: muk
sources: [../PROCESS.md, modules.md]
provides: [system.coder_requirements]
consumes: [system.module_map]
depends_on: [handoff.md, modules.md, verification.md]
tags: [system, handoff, quality]
---

# Seven questions the coding handoff must answer

Architecture supplies the agreements; downstream coders author Spec Kit, code, commands and tests.

| Question | Required answer |
|---|---|
| Who does what and where? | responsibility, code location, exact reused source pin/symbol, adapter, process and owner |
| How is work handed over? | canonical types/files/references, caller/callee, validation, missing-input errors, duplicate, timeout and cancellation |
| What runs first and who stops it? | startup prerequisites, step/Gate/release sequence, halt authority, durable success point and explicit restart |
| Where is evidence stored? | sole writer, identities, atomic publication/recovery, retention and immutable input/policy pins |
| How is generated code restricted? | identities, paths, network/credentials, IPC, protected fixture custody and failure-closed pre-checks |
| What environment/settings apply? | platform/Python profiles, dependencies, startup, config keys/precedence/reload and doctor |
| How can boundaries be checked? | independent invocation, injectable adjacent failures, observable records and integration path |

## Completeness matrix

[Handoff module cards](handoff.md#complete-module-cards) cover the full module map. Each API owner answers questions 1–4 and 7; every card inherits [environment](environment.md), [process boundary](../capsule/process-boundary.md), [storage](storage.md), [records](records.md) and [lifecycle](lifecycle.md) explicitly. Shared answers are linked rather than duplicated. A card is incomplete if an applicable answer is an unexplained black box or unspecified owner response. Saurav's external schema has a concrete provisional adapter contract.

`defined` means a contract is published; `checked` requires connected review evidence; `validated` requires actual downstream execution. Draft status and successful schema checks do not imply runtime validation.

## AI review policy

AI performs detailed review. Give fresh reviewers frozen sources, owning pages and a bounded question without the author's favorable conclusion. Review source/scope, independent producer/consumer expectations, control/persistence, security and coder usability. Findings name exact source clauses/pages, conflicting contracts, practical consequences and corrections. Verify findings against sources and record dispositions; an approval sentence is not verification evidence.

Checked status requires resolved findings, matching contracts and mechanical schema/example/link/graph checks. Human review is a short decision brief for scope changes, significant tradeoffs and unresolved disagreement. Runtime/security observations require actual implementation evidence. This borrows [Pact's consumer/provider separation](https://docs.pact.io/) and maintains INV-9/INV-10 independence.

## Release handoff

Pin the source manifest, design revisions, schema hashes and review dispositions. Supply module cards, build order, APIs/types, spatial/temporal diagrams and acceptance scenarios. After release, changed contracts recheck producers, consumers, Gates and diagrams before publishing a new revision.
