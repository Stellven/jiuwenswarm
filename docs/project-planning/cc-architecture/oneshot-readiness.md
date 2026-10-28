# One-shot build readiness: design package work for October 16

**Planning date:** October 14, 2026. **Owner:** Architect and CC owner. **Done means:** a coding agent given the full design package and the PRD can plan and build the core without inventing a shared field, port, check or file name.

The core to build: the existing Intention Compiler node (intake to `research_brief.json`), a static fixed DAG over the research path, then the Planner that proposes a fixed DAG, protected binding and freeze, dispatch of capsules, deterministic checks, verifiers, gates, Delivery, and a benchmark run over the result.

M1 is the first and weakest working version. The goal is a site that runs a request end to end and produces correct, checked artifacts. It does not need to score well. The benchmark must run on M1 and stay usable for later milestones so we can show improvement over time.

## What the built code already does (October 14 inspection)

| Area | State | Source |
|---|---|---|
| Intention Compiler | Standalone FastAPI service in Docker, `codex exec --output-schema`, Intent then verifier then Requirements then verifier then node gate. 207 of 209 local tests pass. Container path not yet run | `origin/ai4r_test_with_spec_kit` 73ed9e8, `standalone/intent_compiler/` |
| Compiler verifier payload | Copies the worker input into the verifier payload (`runtime.py:443`). This conflicts with D20 and must change in code | same |
| Compiler checks | Schema, span and reference checks are real. `binding_integrity` is always PASS. The node gate verdict is hard-coded | same, `runtime.py:416-431,504` |
| Planner, binder, freeze, DAG runner | Not implemented anywhere. Only the generic agent-core Leader team plan and `SwarmflowTool` exist | `openjiuwen/agent-core` `agent_teams/` |
| Benchmark runner and sidecar | Design only | `development-tools/` |

## Blockers to a one-shot build and how each is closed

| # | Blocker | Fix in the design package | Done when |
|---|---|---|---|
| B1 | Five work CCs have no declaration (Planner, Hypothesis, Builder, Research Benchmark, Delivery). The other declarations are teaching stubs | One tier 3 page per CC with a declaration example that validates against the declaration schema | `validate.py` loads ten work CC declarations and one verifier declaration |
| B2 | Research artifact field tables have no enums, ranges or cross-field rules | Each field row gives type, required, constraint or enum, meaning and consumer use | Every enum and range used by a check is written in the field table |
| B3 | No invalid examples after the Research Brief | One valid and at least one invalid example per CC output, each tied to the check that rejects it | Validator rejects every invalid example for the named reason |
| B4 | No contract for the plan proposal, frozen run plan, static template, check bundle, checking profile, screening rubric, execution and provisioning receipts, or report sections | Add field contracts for each | Contract index resolves each one |
| B5 | Verifier criteria contradict each other. Examples still use `fidelity`, `intent_preservation` and `requirements_usability`. Some pages say the verifier reads original evidence or a review context with input refs | Verifier input is the declaration plus the exact output. Criteria are output-only and listed per CC. Fidelity and preservation become producer obligations inside the Intent and Requirement CCs | No page, example or schema gives the verifier worker input |
| B6 | Planner versus binder authority for checks is stated two ways | The Planner suggests. The binder assigns from the pinned check bundle of each chosen CC | One statement, in the workflow and guard pages |
| B7 | Port names and file names mix case and style (`intent-ir`, `intent_ir`, URN as type, `Research_Brief.json`) | Lowercase only. Ports, artifact types, check and criterion IDs and internal file names use lowercase snake_case. Docker runs on Linux, where case matters | No uppercase internal file name or port name remains in either package |
| B8 | No build order between static and planned DAGs | Static fixed DAG first, then the Planner produces the same run plan type through the same binder and freeze (PRD section 2, default over dynamic) | Core build page gives the order and the shared run plan contract |
| B9 | How prewritten gates attach to a planned CC is spread over several pages | One explanation: each admitted CC version pins a check bundle and a checking profile. The binder attaches them. The Planner cannot add, drop or weaken checks | Guard and workflow pages state it once and link the contract |
| B10 | Benchmark requirements (October 14) need interfaces the design lacks | Add hardware inventory, node replay entry, evaluation-profile fault hook, outcome mapping, label custody and external-configuration adapter to the benchmark runner design. The runner targets every milestone, not only M1 | Benchmark runner design names each interface with fields |
| B11 | Contradictions between prose and field tables (Opportunity Card, Evaluation Verdict, Builder evidence) | Per-CC page owns the field table. Other pages link to it | Contradiction list C3 to C8 closed |
| B12 | Validator fails on the orientation word count | Trim the three-document route | `validate.py` passes |
| B13 | Style drift: semicolons, em dashes, repeated hedging, mixed role names | Plain technical English. Owner roles: CC owner, Architect, Verifier owner, Benchmark owner, RSI owner, Router owner, PRD owner | Sweep finds none |
| B14 | Compact package drifts from full | Sync compact after the full package passes | Shared contracts byte-identical |

## Future work the design must not block

These are written as seams only. No human build effort goes into them before the core gate.

| Later capability | Seam to keep now |
|---|---|
| Model Router (Phase 3) | Capsules declare model needs, not models. Dispatch keeps a route field fixed to Codex in M1 |
| Offline RSI | CC versions are immutable and pinned. Check bundles and labels are held outside the capsule. RSI only creates new candidate versions |
| Generalist and automatic capsule generation (November) | A generated capsule uses the same declaration, check bundle and admission path as a hand-written one |
| Automatic library admission (November) | Admission writes an eligibility record. Plans read eligibility from a library snapshot pinned at plan time |
| Better planning and MCTS (November) | The Planner output type and the binder do not change. Search changes only how the proposal is produced |
| Composition and fusion (December) | A run plan node points to one CC version. Node contracts already allow an enclosing node with subnodes |

## Work order for October 14 to 16

1. Record decisions D23 to D26 (naming, verifier criteria, field-table standard with constraints, static-then-planned build order) in the decision pages.
2. Rename internal files to lowercase and refresh example hashes and diagrams.
3. Write one tier 3 page per CC and the run plan, check bundle and checking profile contracts. Agents work on separate files in parallel.
4. Merge field contracts into the machine mirror and extend the validator.
5. Fix the remaining contradictions, the D20 leftovers and the tier 1 word count.
6. Fold the October 14 benchmark requirements into the benchmark runner design.
7. Style sweep, sync compact, run the validator, then one adversarial review.

## Code follow-ups (not design work)

- Remove worker input from the compiler verifier payload.
- Make `binding_integrity` a real check and compute the node gate verdict.
- Rename compiler output files to lowercase.
- Run the compiler container path end to end.
