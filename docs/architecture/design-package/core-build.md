# Core build: a bounded governed research journey

**Reading level: human potential.** This is the current build assignment (decisions [D19](decision-review.md#d19), [D22](decision-review.md#d22) and [D26](decision-review.md#d26)). The whole product vision is in [system architecture](m1-design.md). This page says what to build now, in what order, and which later work it must not block. It is a design scope, not a schedule. Every acceptance statement stays `DESIGN` until implementation and verification evidence exist.

## What to build, in order

| Step | Build | Done when |
|---|---|---|
| 1 | Reconcile the existing Intention Compiler node to the current contracts: lowercase names, verifier sees declaration and output only, real binding checks, computed node gate | Accepted `research_brief.json` or a visible halt, with all decisions and evidence stored |
| 2 | Shared runtime: declaration loader, binder, freeze, scheduler, dispatch, check runner, verifier call, gate and store | One path runs every CC the same way |
| 3 | Static template over Search, Screening, Hypothesis, Builder, Research Benchmark, Scientific Evaluation and Delivery | One request runs from Brief to Delivery, or halts with a recorded reason |
| 4 | Planner CC producing a `plan_proposal` that the same binder turns into a frozen `run_plan` | The planned path reaches Delivery, and bad proposals are rejected before dispatch |
| 5 | Platform benchmark runs over the result | The M1 pilot cases run end to end and their results are stored as the baseline |

Each step uses the contracts on the [capsule build pages](reference/capsules/README.md) and the [run plan page](reference/run-plan.md). M1 is the first and weakest working version. It must produce correct, checked artifacts, not the best plans, ideas or scores.

## The required journey

**Compiler.** Qualified intake enters the fixed Intention Compiler node. The Intent and Requirement CCs each have deterministic checks, a verifier and a protected gate. The node releases `research_brief.json` only after its decisions and evidence are durable.

**Planning.** In static mode the binder reads a hand-authored static template. In planned mode the Planner proposes a finite JSON DAG from the accepted Brief, the pinned library snapshot, the resource inventory and the plan policy. The binder validates either one the same way: Brief coverage, typed ports, dependencies, permissions, resources, budgets, acyclicity and a pinned check bundle for every CC. It then freezes the `run_plan`. The Planner cannot release its own graph or change checks. An infeasible or rejected proposal halts the planned run and starts a linked Intention Compiler attempt with the reasons (PRD 4.8.3). Select the mode before the run and record it. A failed planned run never falls back to static mode silently. A static run does not count as planned-mode acceptance.

**Research path.** One opportunity, one registered hypothesis and protocol, a bounded POC, sequential baseline then treatment measurement, a scientific verdict and a readable report. Every CC invocation is checked. Each scientific stage has its own contract, evidence and gate. Scientific Evaluation owns the conclusion, and infrastructure gates decide only whether artifacts and process are admissible. A valid scientific negative result is delivered like any other.

**Dispatch.** The scheduler dispatches a node only when its inputs are gate-accepted outputs or run inputs. It writes a `dispatch_record` per attempt. After freeze, nothing changes the topology, CC pins or check pins. No live replan or substitution is allowed.

## Responsibility and reuse

| Boundary | Owner role | Reuse |
|---|---|---|
| Compiler contracts | CC owner (contracts), Verifier owner (checking profiles) | Reconcile the built standalone compiler, its runner, bridge and store before replacing code |
| Planner, binder, freeze, dispatch | Architect (graph and authority), CC owner (Planner ports) | Adapt agent-core Leader and SwarmFlow where they fit. No AI4Research planner exists yet |
| Check bundles, profiles, gates | Verifier owner | Reuse the compiler's deterministic checks and durable gate store. The producer is never its own referee |
| Research CCs | CC owner | Use existing tools and bounded code capsules |
| Platform benchmark | Benchmark owner | Separate development tooling. See [benchmark runner](development-tools/benchmark-runner/README.md) |
| Model access | Router owner (component), Architect (dispatch authority) | Fixed Codex route in M1 |

## Future work this build must not block

RSI and new Model Router work get no human effort before the core gate. No RSI engine, alternate verifier or route, Generalist, MCTS, composition or spatiotemporal capability is a core dependency. The design keeps these seams so later work fits without rework.

| Later capability | Seam kept now |
|---|---|
| Model Router (Phase 3) | Capsules declare model needs, not models. Dispatch keeps a route field fixed to Codex |
| Offline RSI | CC versions are immutable and pinned. Check bundles, profiles and labels sit outside the capsule. RSI only creates candidate versions. The Screening ranking is the first target |
| Generalist and automatic capsule generation (November) | A generated capsule uses the same declaration, check bundle and admission path as a hand-written one |
| Automatic library admission (November) | Admission writes an eligibility record. Plans read eligibility from the library snapshot pinned at plan time. Running plans never change pins |
| Better planning and MCTS (November) | The `plan_proposal` type and the binder stay the same. Only how the proposal is produced changes |
| Composition and fusion (December) | A run plan node references one CC version. Node contracts already allow an enclosing node with subnodes |
| Spatiotemporal lifecycle (2027) | Frozen runs keep their original identities. New versions affect only new runs |

## Scope boundaries

- The optional RSI target is independently buildable once its parent CC export, frozen target and referee, and protected fixtures exist. It stays outside core startup, imports, coding, tests, platform benchmarks and release gates. Core work never waits for it.
- Full M1 PRD coverage stays visible in [coverage allocation](coverage-allocation.md). It is not the same as this assignment.
- The Planner's place in the core is the explicit D19 amendment in [principles](principles.md#decisions-and-source-amendments). It is not an unaltered PRD requirement.
- Reuse the existing compiler and the governed runtime and evidence foundations where they fit. Keep attribution, immutable artifacts, durable decisions, exact version pins, bounded model access, user-visible halt evidence and local secured execution.
- Existing TASK, AC, IF and feature identities, including historical compiler trial names, are not renamed.

## Connected acceptance

The October 30 demonstration covers two representative requests, three successful repeats of one bounded journey, and rejection before dispatch of an incompatible connection, a cycle and a missing check bundle. It also covers a valid scientific negative delivery and a persistence failure that halts. Inspect the accepted artifacts, gate decisions, matched measurements and the readable report. Fixture or schema checks alone do not prove runtime acceptance.

Missing model access, baseline data, a check bundle or durable storage stops the affected run. Record the missing resource and its owner role. Never replace it with an invented result. Human corrections create new linked work.
