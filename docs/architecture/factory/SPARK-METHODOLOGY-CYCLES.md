# Methodology CCs and report-driven cycles on Spark

The factory now has four methodology CCs in addition to the engine expert-streaming capsule. They let an agent interpret an experiment, consider several mechanisms, design a bounded next investigation, and propose another input. They do not form a fixed pipeline that blindly installs every available component.

This document records implemented tools and the retained-report replay that tested them. It does not claim that a live agent executed the replay's historical model runs or that a newly proposed experiment was subsequently run. Live-agent mission results are recorded separately.

## Implemented capabilities

All four capsules expose the material names `methodology`, `ontology`, and `component_candidates`. Each uses the existing native CC runner and factory API, with the declared `process.exec` effect needed to start the bounded analysis subprocess. The analysis itself reads task-scoped evidence and makes no source, contract, task or authority changes.

| Capsule ID | Capability | Purpose |
| --- | --- | --- |
| `factory.methodology_diagnosis` | `diagnose` | Describe recorded rates, output repeatability, failed episodes, engagement and unresolved inspection candidates |
| `factory.methodology_out_of_core` | `cache_protocol` | Propose explicit first-after-initialization and fixed-repeat phases, cache controls and measurement boundaries |
| `factory.methodology_ablation` | `ablation` | Prepare a one-variable diagnostic or ABBA design, prerequisites, bounds and stop conditions |
| `factory.methodology_followup` | `followup` | Turn report-backed uncertainty into a proposed next objective/input and a candidate methodology/component description |

The corresponding factory API operations are `methodology.diagnose`, `methodology.cache_protocol`, `methodology.ablation`, and `methodology.followup`. These are capability operations behind the existing CC tools, not additional agent transport tools.

Every operation takes `evidence_ids`, a list of 1–20 current-task report artifact or observation IDs. JSON artifacts are bounded to 4 MiB each. `ablation` and `followup` also accept an optional `hypothesis_id` identifying a candidate returned by diagnosis. An unknown candidate is rejected. JSON artifacts are read through the evidence store's integrity checks; observations use their `values` object. Reports are descriptions of what was recorded, not an independent verification of every claim in their content. Retained engine results should also pass the independent recorded-result verifier.

Each capability returns one CC output named `analysis`. The agent should read that result, record an evidence-citing decision through the existing evidence CC, and only then invoke an authorized build or lab capability. The analysis does not submit jobs or publish a decision on the agent's behalf.

## Input and output examples

Suppose the current task contains a JSON report artifact aliased as `retained-forced-draft`. The alias identifies imported historical evidence; it does not claim that the current task produced that engine run.

The input to the diagnosis capability is:

```json
{
  "evidence_ids": ["retained-forced-draft"]
}
```

The successful native receipt's `outputs.analysis` includes these fields:

```json
{
  "schema_version": 1,
  "evidence_ids": ["retained-forced-draft"],
  "repeatability": {
    "status": "different",
    "matched_prompt_groups": 1,
    "different_groups": 1
  },
  "recommended_inspection": "establish_repeatability",
  "semantic_accuracy": "not_established"
}
```

The full result also retains descriptive rates, failed episodes, draft engagement, the ontology vocabulary, candidate hypotheses and their prerequisites. Within-cell matching prompt outputs are only a diagnostic observation. They do not establish an independent A/A campaign, freeze a reference or evaluate task accuracy.

To inspect the corresponding next input, call `factory.methodology_followup.followup` with:

```json
{
  "evidence_ids": ["retained-forced-draft"],
  "hypothesis_id": "establish_repeatability"
}
```

Its `outputs.analysis` includes:

```json
{
  "status": "proposal_only",
  "requires_operator_admission": true,
  "source_task_id": "methodology-report-replay",
  "source_contract_id": "retained-exploration-not-a-scored-contract",
  "evidence_ids": ["retained-forced-draft"],
  "proposed_input": {
    "engine_slice": "quality",
    "hypothesis_id": "establish_repeatability",
    "budget": {
      "max_turns": 24,
      "wall_clock_s": 14400,
      "max_build_attempts": 2,
      "max_completed_gpu_cells": 6
    }
  }
}
```

This is a partial example of the actual structure: `proposed_input` also contains the objective, target, uncertainty, expected evidence and experiment design. The output explicitly says that a changed contract needs a new revision and operator freeze. No grants are inherited automatically. The included `discovered_cc_candidate` is marked `not_implemented`, with performance benefit `unknown` and separate promotion requirements.

Use the existing evidence CC to preserve the proposal as an ordinary observation or artifact if it is useful. That publication does not turn it into a host-authoritative lab result, admitted task or frozen contract. A later task may import explicitly authorized prior evidence; these methodology operations do not reach across task scopes themselves.

## From a broad objective to a bounded action

For an input such as “make the decoder faster,” the agent starts by reading the task contract, constraints and evidence. It can then use diagnosis to ask what is missing before choosing an implementation.

The ontology covers nine domains:

| Domain | Question and example evidence |
| --- | --- |
| Decode | Which work or wait lies on the per-token critical path? Native decode time and generated-token counts |
| Prefill | Does prompt processing dominate request latency? Prompt time, prompt length and TTFT |
| Placement | Can residency reduce demand stalls without consuming needed host headroom? Effective resident bytes and hit counters |
| IO | Do physical reads delay demand? Phase reads, demand waits and readiness at use |
| CPU | Does scheduling or oversubscription delay GPU progress? CPU quota, queue waits and CPU time |
| Cache | What differs between engine initialization and repeat workloads? Fixed cache protocol, physical reads and output identity |
| Draft | Does verified drafting repay its own cost? Effective state, offered/accepted drafts and target timing |
| Quality | Are full-model and output obligations preserved? Effective experts, token identity, finish reason and task evaluation |
| Telemetry | Can the result be trusted and recovered? Exit/cleanup facts, integrity, completeness and observer overhead |

This vocabulary is not a measured bottleneck model. Missing signals stay unknown. The diagnosis tool currently uses explicit, authored prerequisite rules: recovery gaps and failures precede optimization, output differences or absent repeatability prompt A/A investigation, and otherwise IO/CPU/placement observations are candidates. The agent still chooses the next bounded action from evidence and remaining budget. A recommended inspection is not host authorization or a predicted speedup.

For example, the retained forced-draft report contains working inference and actual draft engagement but differing token outputs for the repeated prompt. A faster second request is insufficient to claim an optimization gain. The useful next question is repeatability and correctness under a controlled configuration. When a static report instead contains equal repeated outputs, the next proposed inspection becomes IO readiness; even then the output does not mark scoring ready or freeze A/A validity.

## Component candidates beyond expert-streaming patches

Each capsule's `component_candidates` material contains seven candidates mapped to pinned Strata revision `ffa80d73133ea5c548aefe57889a16e8085a938f`:

- Resident expert budget: vary one reserve setting while holding the other placement controls fixed and preserving admitted headroom.
- Adaptive expert cache: inspect promotion costs and readiness before a single cache toggle; output repeatability remains a prerequisite.
- CPU thread budget: compare 4 versus 8 workers under the same eight-CPU quota after measuring scheduling effects.
- Prefill chunk size: investigate one chunk change from the tested 256-token setting while measuring TTFT and memory.
- Verified drafting: distinguish `none`, `on` and effectively unloaded `auto`; require acceptance counters and a frozen correctness policy.
- Ahead-readiness observer: instrument queued/in-flight/resident demand states and wasted/duplicate bytes before altering speculation.
- Phase telemetry: expose versioned phase/resource evidence with independent observer-overhead checks.

These materials identify existing native mechanisms or proposed observations. They are **not executable engine patches**, are not replacements for source applicability inspection, and are not automatically registered as accepted engine components. Source symbols and flags must be checked against the pinned revision before implementation. The existing llama.cpp expert-streaming patches remain tied to their own source revision; this catalogue does not make them Strata-compatible.

## A/A, ablations and combined changes

A capsule's existence does not justify applying it. Choose one supported hypothesis, state a single changed variable, freeze the other controls, and collect evidence that distinguishes competing explanations.

Establish independent A/A validity under the approved correctness and cache protocol before scoring B. Preserve raw stream hashes separately from canonical output checks; timing-bearing stdout is not an appropriate semantic equality rule. Missing engagement, failed correctness, incomplete telemetry or resource violations block scoring.

The ablation tool bounds a design to one changed variable and at most three trials. Diagnostic designs are explicitly non-scoring. A possible ABBA design still reports `scoring_ready: false` because within-cell equality cannot replace operator-frozen contract admission and independent A/A checks. Host capabilities enforce admission and execution; methodology prose cannot bypass them.

Use fresh-container counterbalanced ABBA blocks for admitted treatments. Separate first-after-initialization and fixed-repeat phases. Do not call either cold SSD, evict shared host caches, treat hardlinks as independent page cache, or count traced runs as scoring evidence. Measure prefill/decode/end-to-end latency, physical reads, memory and observer overhead separately.

Retain null and failed experiments. An observability component needs useful signals and bounded overhead rather than a speedup. After individual changes pass, compare the final combined stack directly with the original baseline; individual gains cannot simply be multiplied.

## Native report-to-next-input proof

The proof uses the existing native CC host and factory API, not direct-only calls to the Python helper. It ran four methodology tools against three report sets, for **12 successful native calls**:

| Report set | Retained source | Proposed next input |
| --- | --- | --- |
| `cycle1` | Actual long forced-draft engine report | `establish_repeatability` |
| `cycle2_historical_replay` | Actual static resident engine report with equal within-cell repeated outputs | `measure_io_readiness` |
| `failure_history` | Actual crash probes plus the two engine reports | `recover_before_scoring` |

The source artifacts are aliased `retained-forced-draft`, `retained-static-resident`, and `retained-crash-probes` in the separate review task. The task's contract inputs remained unchanged. All four capsules' three materials were prepared/materialized, so the receipts also retain their release identities.

Evidence root:

`/home/user2/software-factory-spark-20261113`

Relevant artifacts:

- `results/methodology-native-proof.py`: executed proof script.
- `results/methodology-native-proof.json`: native receipts, materials, proposal changes and limitations.
- `results/methodology-native-proof.log`: compact success result.
- `methodology-review-store/` and `methodology-review-ccstore/`: task evidence and native CC ledger.
- `results/methodology-tests-catalogue.log`: **15 passed** tests covering missing/nonfinite measurements, output differences, treatment separation, failure retention, read scope, one-variable limits, proposal-only behavior and unchanged contract inputs.

The second report predates the proposal. This tests whether a changed evidence input changes the next proposed question, not whether a new experiment was automatically executed from the proposal. A separate synthetic two-cycle test verifies that retaining both reports preserves the first failed episode rather than forgetting it. Neither test is a new performance claim.

The first test run failed because its assertion compared the task's evidence cursor before and after the test itself explicitly published new evidence. The assertion was corrected to compare immutable task inputs; evidence cursor advancement remains expected and was not suppressed. Earlier logs remain retained.

## Learning over many cycles: what is still open

The implemented methods are authored heuristics and report transformations. They are not an automatically learned optimizer, a causal model of engine behavior, or a system that can safely promote its own generated components.

Future cycles should retain an episode containing original input/contract, evidence considered, hypothesis, applicability, exact change, tool failures, resource costs, measured outcomes, limitations and rejection reasons. Candidate generation can consume those episodes, but a candidate still needs source mapping, explicit effects, positive and negative replay cases, quality/overhead gates and rollback before promotion.

Important unresolved questions include:

- How to distinguish a historical, resolved failure from an active prerequisite gap without erasing failed evidence.
- How to rank information-gathering experiments by expected value and budget rather than a fixed authored prerequisite order.
- How to reuse knowledge across engine versions, quantizations and hardware without treating an old applicability result as current truth.
- How to evaluate stochastic or numerically varying outputs without weakening correctness after seeing results.
- How to determine whether a generated method improves decisions across multiple episodes, rather than merely writing plausible follow-up prose.
- How to prevent redundant candidates and interacting changes from consuming the experiment budget.

A practical next evaluation is to admit a follow-up proposal explicitly, run its bounded action, and compare the agent's next decision against the original uncertainty and evidence obligations. Keep proposal generation, task admission, execution, acceptance and CC promotion as distinct recorded steps. This gives the factory a testable path from reports to better experiments without pretending that the general learning problem is already solved.
