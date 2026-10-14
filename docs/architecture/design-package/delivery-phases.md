# Delivery phases and build direction

**Reading level: human potential.** Delivery phases, implementation stages and runtime research steps are different concepts. This page lists each phase once and points to the page that defines it. The [PRD](sources/product/README.md) owns acceptance requirements.

## Current assignment and independent product coverage

| Phase | What it is | Defined in |
|---|---|---|
| Current core (D19) | The bounded journey from accepted Brief through planner proposal, binder check and freeze to one Search-to-Delivery scientific path. A static template runs first ([D26](decision-review.md#d26)) and cannot stand in for the planned-mode record. Design scope, not runtime completion | [Core build](core-build.md), [run plan](reference/run-plan.md) |
| October 30 gate scope | The bounded D19 journey on the fixed Codex route. RSI and new Model Router work are excluded from its acceptance. It is narrower than the full PRD M1 gate and must not be reported as full M1 completion ([D22](decision-review.md#d22)) | [Core build](core-build.md#connected-acceptance) |
| Separate optional RSI target | Improves a sandbox copy of `rank_opportunities`. Built and accepted on its own evidence. Never a startup, import, test, benchmark or release dependency of the core | [Core build](core-build.md#future-work-this-build-must-not-block) |
| Full M1 coverage | The whole PRD, mapped clause by clause. Not equivalent to the current core | [Coverage allocation](coverage-allocation.md), [phase details](phase-details.md) |
| November | Generalist, automatic capsule generation, automatic library admission, better planning and MCTS ([D21](decision-review.md#d21)) | [Core build](core-build.md#future-work-this-build-must-not-block) |
| December | Composition and fusion ([D21](decision-review.md#d21)) | [Core build](core-build.md#future-work-this-build-must-not-block) |
| 2027 | Spatiotemporal lifecycle | [Core build](core-build.md#future-work-this-build-must-not-block) |

[Immediate plan](immediate-plan.md) routes builders to the current core. The existing [Intention Compiler build](builds/intention-compiler/README.md) is a reusable first component, not the complete journey.

## Boundaries that remain fixed

- The static template has a separate acceptance record and cannot satisfy the D19 core assignment.
- A new route, compiler or candidate version affects only new attributable runs. It never changes a started invocation, accepted Brief, `run_plan` or historical decision.
- Advanced clarification is bounded pre-acceptance work in declared interactive mode. Headless paths never wait.
- One active research run follows one opportunity and hypothesis, with sequential baseline then treatment measurement.
- M1 adds no distributed workers, model training, external publication, live self-installation or recursive improver deployment.
- Composite creation and execution, merging, arbitrary capsule member graphs, multiple planning epochs and broader optimizers remain later work. M1 uses separate gated work CC nodes.
- Stage and phase completion need reproducible evidence, not implementation existence or a diagram. Required summaries reference underlying verification and do not replace it.
- Semantic review input is limited to the declaration and output ([D20](principles.md#d20-declarationoutput-only-semantic-review)). Host checks retain runtime evidence.
