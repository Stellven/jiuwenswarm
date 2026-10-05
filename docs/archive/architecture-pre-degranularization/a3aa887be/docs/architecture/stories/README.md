---
type: home
status: draft
tags: [stories, walkthrough, quality]
---

# M1 stories

These stories let a coder follow concrete items through the architecture: which proposed code receives them, which interface connects the next module, who writes evidence, and what happens on failure. They are design walkthroughs, not logs of implemented software running.

All `cc/` and `capsules/` paths are proposed repository destinations from the [module map](../system/modules.md). Existing upstream symbols are identified through [integration](../system/integration.md); the stories do not claim those symbols already implement CC behavior. Labels such as R1, O1 and V1 illustrate correlation. Example hashes are structural placeholders and authorize no execution. Owning contracts linked in each story remain authoritative.

## Read the stories

| Story | Item followed | Main connections checked |
|---|---|---|
| [Research from question to report](01-research-workflow.md) | Question, repository, validation data and resulting payloads | All eight work capabilities, model bridge, nested search, Gates and publication |
| [Screening selects or stops](02-screening.md) | Three candidate ideas | Consolidation, dependency policy, ranking, evidence and Hypothesis |
| [A passing Gate cannot be saved](03-durable-recovery.md) | Output, Verification and release identities | Store, supervisor, journal, explicit recovery and duplicate requests |
| [Scientific measurements become a verdict](04-scientific-execution.md) | Baseline and treatment measurements | POC process, trusted measurement, arithmetic, scientific classification and report |
| [Container login and a model turn](05-auth-and-model.md) | Persistent auth profile and scoped model request | Startup, AuthProvider, ModelProvider, capture, timeout and private custody |
| [Offline RSI produces an inactive candidate](06-offline-rsi.md) | Parent, trial, query reservation and Candidate | Hidden oracle, closure, budgets, admission and manual activation |
| [An experimental plan is accepted or rejected](07-experimental-planner.md) | Model-proposed run plan | Leader adapter, validator, freeze, track checks and experimental advancement |
| [The external harness starts and retrieves a run](08-benchmark-and-workstation.md) | HTTP request, run handle and export | Benchmark endpoints, local UI/terminal, reconnect, retrieval and authorization |

[Quality findings and check results](quality-checks.md) records the corrections these walkthroughs exposed. [Fixtures](fixtures/science.json) contain complete schema-shaped scientific examples used by [the story checker](../_tools/validate_stories.py).

## Coverage and limits

The stories cover startup/configuration, fixed production, required offline RSI and isolated whitelist experiments. Successful, scientifically negative, halted, interrupted and denied paths are represented. They complement the broader [boundary-case index](../system/boundary-cases.md): that index assigns all specified case families to their owning invocation points, while these narratives show how several connected cases unfold over time.

The checker validates example structure, independent numerical expectations and agreement with the current plan/module contracts. It does not execute the proposed runner, model, Docker image, store, oracle or HTTP server, or prove that referenced records exist. Actual observations belong to downstream implementation tasks.
