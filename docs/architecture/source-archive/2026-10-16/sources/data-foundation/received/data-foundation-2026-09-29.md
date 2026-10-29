# Data Foundation for Capability Capsules (M1)

From: Suraj · Date: 2026-09-29 · Status: draft, open to change

## Summary

Whenever a capability capsule runs at a workflow node, the system captures everything that touched that run and keeps it. The goal is completeness: whoever later analyzes or improves capsules should find that the information they need was already recorded, without having to rerun anything.

Raw material is saved while a run happens, by small hooks in our own workflow code. Structured records are built from that material after the run. Because the raw material is kept, records can be rebuilt in a new format later without losing anything.

Three things are kept for every capsule execution:

1. **Raw evidence**: the inputs, outputs, prompt, full trace, the worker's workspace, and the gate's and verifier's raw outputs.
2. **A structured record** with named fields, so executions can be searched, counted, and compared.
3. **Declared versus observed**: each capsule's own Declaration is used as a checklist, and the record shows what was declared beside what actually happened.

This work only observes. It does not change how the workflow, capsules, gate, or verifier behave, and it does not decide how the information is used.

**Implementation order.** Build in this sequence, each passing before the next starts: Run Evidence Capture, Capsule Run Record, Run Bundle, Contract Conformance, Capsule Scorecard, Sample Run Export. Capsule Library Snapshot is a stretch goal.

**M1 defaults.** Where another owner's decision is still open, M1 uses these defaults so implementation is not blocked:

*   Each workflow stage uses a fixed capsule. The record marks `selected_by: static` unless a `RouteDecision` from the Model Router is supplied.
*   When the Model Router supplies no execution id, the Swarmflow `agent_id` of the stage's worker is the record key.
*   A capsule's files are its `.md` file, its Declaration, and every file either references by path. The capsule hash is SHA-256 over the sorted list of each file's path and SHA-256.
*   When the Evaluator Gate returns only a verdict, per-check fields are recorded as `not_available`.
*   All output is written under `records/` in the project workspace.

---

### Run Evidence Capture

*   **Definition & Expectation:** Small hooks in our workflow code that save raw material during a run, so nothing is lost to trace truncation, trace retention, or workspace cleanup.
*   **Whitelist (M1 Scope):**
    *   A wrapper around each capsule call that saves which capsule ran, a hash over its files, the input files and their hashes, and start and end times.
    *   A hook at the Evaluator Gate that saves the exact evidence the gate judged, each check's result and raw output, the verifier's full output, and the human's question and answer when a person is asked.
    *   At run start: platform and library versions, a hash of the active configuration, the workflow script hash, the state of the shared workspace, and host facts (operating system, CPU model and core count, memory, and GPU model and driver when present).
    *   At run end: copies of each worker's workspace, the workflow's own run log, and the run's trace data, made before team cleanup and trace retention remove them.
    *   Every hook appends to files and never blocks or changes the run. A hook failure is logged and ignored.
*   **Blacklist (Excluded from M1):**
    *   Any change to openJiuwen platform code.
    *   Assembling records while the run is in progress.
    *   Continuous sampling of CPU, GPU, or memory utilization during a run.
*   **Dependencies:**
    *   *Requires Input from:* each stage node from 3.1 to 3.9 invoking its capsule (for example `search_capsule.md`, `poc_capsule.md`, `verifier_capsule.md`) through the shared capsule wrapper; the 4.2 Evaluator Gate verdict payload (`PASS`, `FAIL`, `BLOCKED`) and the Stage Evidence Bundle it judged; Swarmflow progress events (workflow started, agent started, agent completed, workflow failed) and the run's journal log; 3.0 Codex CLI adapter log entries for timeouts and authentication drops; jiuwenswarm trace output with the trajectory store enabled.
    *   *Provides Output to:* the raw evidence folder `records/runs/<run_id>/`, read by Capsule Run Record and Run Bundle.

### Capsule Run Record

*   **Definition & Expectation:** One structured record per capsule execution, including executions that never reached the gate, built after each run from the saved evidence.
*   **Whitelist (M1 Scope):**
    *   **Where and when:** workflow run id, stage, node, attempt number and why it was retried (automatic retry, gate rerun, or human rerun), start time, end time, duration.
    *   **Which capsule:** name, kind, owner, a hash over every file that makes up the capsule, a separate hash of its Declaration, and whether the capsule was fixed for the stage or selected by the router.
    *   **Which model and why:** the model that executed the capsule and its settings; the routing decision, meaning which models were considered, why others were excluded, why this one was chosen, and whether a fallback was used.
    *   **Environment:** versions of the platform, the workflow script, and the tools available; a hash of the active configuration; the sandbox policy in force.
    *   **State at start:** budget remaining, the state of the shared workspace, and how much of the model's context was already used.
    *   **What it was given:** the prompt as sent; each declared input as a file reference with hash and size; where each message the model saw came from; any memory items it retrieved.
    *   **What it produced:** each declared output as a file reference with hash and size, and the result returned to the workflow.
    *   **What it cost:** input, output, and cached tokens; number of model calls; latency; budget spent against budget allowed.
    *   **What it did:** every tool call in order, with name, status, duration, and error; files written.
    *   **How it behaved:** repeated identical calls, tool errors, and whether the model's context was compacted during the run.
    *   **How it stopped:** completed, hit an iteration limit, ran out of budget, errored, was stopped, or was halted by a person.
    *   **What the gate saw and said:** a reference to the exact evidence the gate judged; every check by its declared id with pass or fail, message, raw output, and the evidence it looked at; the verifier's verdict, written reasoning, a result per criterion where the verifier provides one, and the verifier's own version and model.
    *   **What went wrong:** the declared failure reason code when one applies; the error text; an error fingerprint with volatile details removed so the same error groups together across runs; a failure class of `capsule`, `input`, `infrastructure`, or `scientific`.
    *   **What the human said:** the question shown, the answer given, and any edit the person made to the output.
    *   **Where its inputs came from and what happened next:** which earlier execution produced each input and which later execution used each output, matched by file hash, and whether the next node accepted it.
    *   **How each judgement was produced:** every check result, verifier result, and failure class is labelled as produced by a deterministic check, a model, or a person.
    *   Fields whose source is unavailable are marked as not available, never left out.
    *   Successful executions are recorded as completely as failed ones.
    *   Stored as an append-only file, one line per execution.
*   **Blacklist (Excluded from M1):**
    *   Any database, vector store, or graph store.
    *   Large content inside the record itself. Content lives in the run bundle and the record points to it.
    *   Using an LLM to decide whose fault a failure was. In M1 the failure class comes from which check failed, how the run stopped, and the human's answer.
    *   Any interpretation, ranking, or recommendation.
    *   Multi-user separation.
*   **Dependencies:**
    *   *Requires Input from:* `records/runs/<run_id>/` from Run Evidence Capture; each capsule's files and Declaration (`cc.declaration.v1`); per-check results from the 4.2 Evaluator Gate and the Tier 2 verifier's output; the `RouteDecision` from the 4.3 Model Router when available; stage payloads, identified by content hash for lineage (`Research_Brief.json`, `Candidate_Set.json`, `Opportunity_Card.json`, `Hypothesis_Blueprint.json`, `POC_Artifact_Bundle.zip`, `Benchmark_Payload.json`, `Evaluation_Verdict.json`); and the verdict classification in `Evaluation_Verdict.json` from Stage 3.8.5, which assigns the `scientific` failure class.
    *   *Provides Output to:* `records/records.jsonl`, read by Capsule Scorecard and Sample Run Export.

### Contract Conformance

*   **Definition & Expectation:** For every clause a capsule declares, the record holds what was declared beside what was observed, so differences are visible without anyone reading a trace. This sits on top of the Capsule Run Record, which is complete whether or not a capsule declares anything useful.
*   **Whitelist (M1 Scope):**
    *   Ports: declared type and schema beside the actual file and whether it validated.
    *   Needs: declared tools and network access beside the tools actually called and network actually used.
    *   Effects: declared writable resources beside the files actually written.
    *   Guarantees: each declared check beside its result.
    *   Failure modes: declared reason codes beside the failure that occurred.
    *   **Undeclared behavior** recorded explicitly: a tool used but not declared, a file written outside declared effects, a failure with no matching reason code.
    *   **Unused declarations** recorded explicitly: something declared that the capsule never used.
    *   **Declaration coverage:** the share of what the capsule did that its Declaration accounted for.
*   **Blacklist (Excluded from M1):**
    *   Blocking or stopping a run because of a mismatch. This is observation only.
    *   Changing a capsule's Declaration automatically.
*   **Dependencies:**
    *   *Requires Input from:* the Declaration clauses `ports`, `needs`, `changes.effects`, `guarantees.checks`, and `guarantees.failure_modes`; tool-call spans for the stage's worker; the copied worker workspace in `records/runs/<run_id>/`.
    *   *Provides Output to:* the `conformance` block of each record in `records/records.jsonl`, and the Capsule Scorecard.

### Run Bundle

*   **Definition & Expectation:** A folder per capsule execution that preserves the raw material behind the record, so nothing is lost if a need arises that the record's fields did not anticipate.
*   **Whitelist (M1 Scope):**
    *   The capsule's files as they were at run time.
    *   The prompt as sent, and the input and output files.
    *   The worker's workspace at the end of the execution.
    *   The full trace for the execution.
    *   The raw output of each check and of the verifier, and the exact evidence the gate judged.
    *   Everything needed to run the capsule again on its own: prompt, inputs, capsule files, model and settings, and tool results with their timestamps.
    *   A manifest listing every file with its hash.
*   **Blacklist (Excluded from M1):**
    *   A tool that performs the rerun.
    *   Deduplication or compression across bundles.
    *   Automatic deletion. Bundles are kept until a retention rule is agreed.
    *   Redaction. Bundles may contain sensitive text and are treated as internal.
*   **Dependencies:**
    *   *Requires Input from:* `records/runs/<run_id>/` from Run Evidence Capture.
    *   *Provides Output to:* `records/bundles/<run_id>/<agent_id>/` with `manifest.json`, referenced by each record's `bundle_path`.

### Capsule Scorecard

*   **Definition & Expectation:** A summary per capsule version, computed from the records, so the team can see how each capsule is performing and at what cost.
*   **Whitelist (M1 Scope):**
    *   Per capsule version: number of executions, gate pass rate, pass rate per check, verdict counts, most common failure reasons and error fingerprints, undeclared-behavior counts, declaration coverage, how often the next node accepted the output, typical token use, duration, and number of attempts.
    *   Side-by-side view of two versions of the same capsule, restricted to executions whose inputs match. The scorecard reports how many matched pairs it found, because later stages rarely receive identical inputs in ordinary runs.
    *   The comparison of each stage's capsule run with and without the `make_capsule.md` contract wrapper, on matched inputs.
    *   Failures classed as `infrastructure` or `scientific` are reported but do not lower a capsule's pass rate.
    *   Output as one markdown table and one JSON file.
*   **Blacklist (Excluded from M1):**
    *   Dashboards or a web UI.
    *   Ranking capsules or recommending one over another.
    *   Statistical significance testing.
*   **Dependencies:**
    *   *Requires Input from:* `records/records.jsonl`.
    *   *Provides Output to:* `records/scorecard.md` and `records/scorecard.json`, for 4.1 Capability Capsule owners and 4.4 RSI Integration.

### Sample Run Export

*   **Definition & Expectation:** Frozen copies of real runs, packaged so that other tracks can work against realistic data without touching the live workflow.
*   **Whitelist (M1 Scope):**
    *   Per exported execution: its record and its run bundle.
    *   Each export set has an id and a content hash so everyone can confirm they are using the same data.
    *   Includes failed executions as well as successful ones.
    *   Each execution carries a label fixed at export time, so consumers can set some aside.
*   **Blacklist (Excluded from M1):**
    *   Generating synthetic runs.
    *   Any path that writes back into the live workflow.
*   **Dependencies:**
    *   *Requires Input from:* `records/records.jsonl` and `records/bundles/` from runs of the default DAG.
    *   *Provides Output to:* `records/exports/<export_id>/`, the sample DAG fixtures for 4.4 RSI Integration and offline development of the 4.2 Tier 2 verifier.

### Capsule Library Snapshot (stretch goal)

*   **Definition & Expectation:** One file describing the capsule library as a whole, computed from the capsule files alone without running anything.
*   **Whitelist (M1 Scope):**
    *   Capsules that declare no checks, and capsules that declare no failure modes.
    *   Pairs of capsules where one's output type fits the other's input type.
    *   Pairs of capsules with identical interfaces, and capsules with identical content.
*   **Blacklist (Excluded from M1):**
    *   Recommending which capsules to merge, remove, or change.
*   **Dependencies:**
    *   *Requires Input from:* every capsule's files and Declaration.
    *   *Provides Output to:* `records/library_snapshot.json`, for 4.1 Capability Capsule owners.

### Existing Memory and Telemetry Modules

*   **Definition & Expectation:** States how the modules named in the earlier test report for Data Foundations and Visibility relate to this work in M1.
*   **Whitelist (M1 Scope):**
    *   JiuwenSwarm Task Memory and Coding Memory remain the agents' durable working context, unchanged.
    *   The native `/swarmflows` run tree, team token budgeting, and tool security logs are read as sources for Run Evidence Capture.
    *   Records carry the ids, content hashes, and upstream and downstream links that a later trace graph would be built from.
*   **Blacklist (Excluded from M1):**
    *   Using Task Memory or Coding Memory to store run evidence, benchmark output, or telemetry. They hold notes written by a model, not raw records.
    *   Concept, code, or trace graph stores.
    *   Distributed or multi-host storage.
    *   Persistent telemetry dashboards and multi-run reporting interfaces. The scorecard is a file.
    *   Host-level CPU and GPU utilization tracking.
*   **Dependencies:**
    *   *Requires Input from:* JiuwenSwarm Task Memory, Coding Memory, and `/swarmflows` run state, read-only.
    *   *Provides Output to:* nothing new. This entry records M1 boundaries.

---

## What I need from other owners

| From | What | Why |
|---|---|---|
| Capsule | Agreement on which files make up a capsule, and stable check ids | So a record names the exact capsule version and check |
| Evaluator Gate | Each check's result and raw output, and the exact evidence it judged | A verdict alone does not say what happened or what was seen |
| Verifier | Written reasoning, a result per criterion if it judges more than one, and what it relied on | Same reason |
| Model routing | An execution id, the model and settings, and the decision record: candidates, exclusions, rationale, fallback | To tell a capsule problem from a model problem, and to keep the only record of what else could have run |
| Workflow | Capsules run through one shared wrapper; team cleanup happens after the run-end copy | The hooks live in the workflow code, and worker workspaces are deleted with the team |
| Operators | Permission decisions in a readable form | A denied tool call can look like a capsule fault |
| Platform configuration | For M1 runs: the lossless trajectory store switched on, the trace length limit raised, and the sandbox activity log switched on | By default traces cut long text at 10,240 characters, and the sandbox log is off |

## Known limits

- Stage 3.7.3 currently says benchmark `stdout`, `stderr`, and runtime telemetry are captured in Task Memory and Coding Memory. This section proposes saving them as raw evidence instead. The two need to agree before implementation.

- Some fields depend on another component emitting the information. Where it is not available in M1, the field is marked as not available.
- Traces are kept for seven days and worker workspaces are deleted with the team, so the run-end copy must happen promptly.
- The workflow engine cannot replay a finished run. Reruns start from the inputs saved in the bundle.
- Capturing everything means bundles contain sensitive text. Access and retention need a decision before bundles leave a developer machine.

## Open for change

Field names, file locations, and output formats are all open. The parts I would keep are one record per capsule execution tied to the exact capsule version, results at the level of individual checks, and raw material kept so records can always be rebuilt.
