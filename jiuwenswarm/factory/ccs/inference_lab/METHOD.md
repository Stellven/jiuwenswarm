# Inference lab analysis and intervention job

This CC packages related methods and tools for an agent working across an inference
engine. It is not one optimization, a fixed workflow, or a host planner. Read SKILL.md for the job procedure and choose capabilities for the question.
Analysis and pure transforms do not launch an engine. Explicit execute/lab_submit
use existing admitted host lifecycle and declared GPU authority; no call grants
new authority. Existing narrower CCs remain compatible but are not prerequisites.

## Improvement cycle

1. Read the contract and retained evidence. Separate execution success, correctness,
   engagement, performance, and unresolved observability. Choose the engine layer.
2. Use test_scope to match the claim to the smallest useful test. Configuration
   checks and offline replay can precede subsystem measurements. Full correctness
   and end-to-end speed tests are escalation, not a prerequisite for every tool call.
3. Diagnose or propose an evidence-linked hypothesis: applicability to this model
   and hardware, one variable, prediction, counters, falsification and stop condition.
   Use ablation to hold other variables fixed. Reserve independent confirmation;
   do not tune thresholds or workload after seeing a result.
4. Inspect the chosen CC release and its materials, run the relevant verification
   units, and assess the task-specific admission policy. A package can expose many
   tools, services, methods and components; admitting one capability under one scope
   does not certify all of it or the delivered engine. External implementation
   modules and environment bindings need identities as well as package hashes.
5. Select and execute an admitted test through the factory loop. End the agent turn;
   let the supervisor stop control before measurement. Preserve crashes and raw data.
6. Resume from durable evidence, assess the claim at its declared scope, and choose
   confirmation, a new hypothesis, a prerequisite investigation, or a justified stop.
   Publish the next-input proposal and unresolved gaps. No automatic default promotion.

## Methods learned from other systems

- MoE-Infinity (https://arxiv.org/abs/2401.14361): use routing/access history to ask
  which experts are useful to retain or prefetch. Our evaluate_prediction capability
  uses causal last-token and frozen-frequency controls with request-separated temporal
  holdout. It does not implement the paper's full system or inherit its results.
- Fiddler (https://arxiv.org/abs/2402.07033): compare costs of moving weights versus
  executing experts on CPU. On shared-memory GB10 this is an applicability question,
  not a copied PCIe bandwidth model. Need measured storage, CPU, GPU and synchronization
  costs before admitting a placement intervention. No automatic placement tool yet.
- Strata native phases: separate prefill, decode, drafting and memory movement.
  profile_plan and analyze_profile retain observer evidence separately from untraced
  performance. Native DS4_PROF crashed in a retained experiment; inspect that failure
  before using this observer again. Missing counters mean a tool gap, not zero cost.
- Warmup and ablation: retain first/steady positions, change one variable, counterbalance
  process order, and confirm with fresh processes. File cache, initialization and
  prompt-prefix reuse are different mechanisms. Identical-token prompts can diagnose
  one subsystem but cannot establish broad language-model quality.

## Verification and limits

Domain tests cover scope boundaries, authorization refusal and delegated evidence
scoping. These are development verification units, not blanket certification.
Use qualify_prefill only for supported prefill domain verification/admission policies;
there is no universal package qualification.
Paper references are methodology provenance; pin revisions/source bytes before a
reproducible implementation admission. The current factory is a bounded first draft:
new source-derived implementations still require review and admitted test templates.

## Inspect collected benchmark resources

Use `inspect_evidence(cycle_id)` after collecting a benchmark cycle. It resolves
only the current parent's ledger child, verifies retained manifests/contracts,
and publishes bounded raw-log artifacts into this parent scope. Use `read` with
the returned artifact IDs; no child-task read grant is required or implied.
The report includes effective expert slot/CPU counts, native request timings,
draft counters and lifecycle CPU/I/O/memory observations. Startup and idle work
are included in lifecycle counters; missing request TTFT, GPU utilization and
true memory peaks remain unknown. Failed/cancelled collected cycles expose
verified partial diagnostic evidence when available, without complete execution,
quality or speed claims. Reinspection fails if source/copy integrity changes.
