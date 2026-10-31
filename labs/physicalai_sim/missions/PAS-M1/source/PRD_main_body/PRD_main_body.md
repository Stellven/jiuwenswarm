# SIMLAB: simulation lab for AI4Research

**PRD Main Body · r0.4.2 · Milestone PAS-M1 (local workstation only) · October 30, 2026 · Owner: Suraj.** What SIMLAB must do. [PRD Context](../PRD_context/PRD_context.md) holds sources, user stories and scope; the architecture says how.

**Description:** SIMLAB is a general simulation environment for experiments. A request comes in from AI4Research or another agent. SIMLAB constructs the experiment, runs it, returns all the data, and takes the next request, often a follow-up that changes what was built. The scientific requester does the science: it decides what to test, what counts as success and what to ask next. In the integrated journey that is AI4R; in direct use it is the agent or person making the request. SIMLAB builds, runs, records and reports. Any research objective is a valid starting point, including mechanism investigations, design comparisons, robustness studies and hypotheses arising from earlier experiments, even when they no longer test a particular paper claim.

### SL-1 Requests and research objectives
* **Definition & Expectation:** Accept requests from AI4R or any agent: a research objective with sources, or a follow-up that references an earlier run or checkpoint. Record the objective's kind (claim test, assumption test, mechanism, design comparison, robustness, follow-up, exploration) without judging it.
* **Scope (Whitelist):** The builder writes the full protocol from AI4R's outputs, each item with its origin, frozen before the run that counts. It halts on ambiguity or conflicting sources, and AI4R decides.
* **Blacklist:** Refusing work because it does not test a paper claim; inventing predicates, thresholds, arms or trial counts.

### SL-2 Construction
* **Definition & Expectation:** The builder constructs and modifies every part of an experiment through SIMLAB's normal tools: apparatus, scenes, geometry and collision shapes; controllers, policies, models in the loop, sensors and what they observe; procedures and interventions; measurements and diagnostic probes.
* **Scope (Whitelist):** Authoring tools produce the runnable artifacts (geometry and collision assets, model files, procedures, measurements, component code at declared extension points), bound to the experiment by an immutable manifest. A follow-up is a new experiment built with the same tools. A change the tools cannot express is recorded as a capability gap.
* **Blacklist:** Editing the lab's core to make one experiment work.

### SL-3 Execution
* **Definition & Expectation:** Run any number of arms (baseline, treatment, control, reference), factors, conditions, replicates and episodes, with paired trials, declared randomness, pilot runs that never count as evidence, and measurements per trial, pair or set.
* **Scope (Whitelist):** Keep every trial, attempt, failure and interruption. Physical instability is a result. A trial is invalid only for numerical failure, a protocol violation, an incorrect intervention, a missing required observation, a corrupted record, or invalid state or action delivery. An experiment never changes after submission; a changed protocol is a new experiment, and a fresh execution of the same one gets a new run identity.
* **Blacklist:** Verdicts in the runner; silent reruns.

### SL-4 Checks
* **Definition & Expectation:** Every result carries checks: validation before running (all findings at once), physics sanity watchdogs, reruns across engine settings and assumed values, independent recomputation of standard measurements, and known-answer checks or control arms.
* **Scope (Whitelist):** A run with no control or known-answer check is reported as *unanchored*, not refused; a required check that failed marks the affected measurements *invalid*. Counted comparisons declare their unit of inference, pairing, aggregation and required precision.
* **Blacklist:** Hiding or averaging away a failed check.

### SL-5 Simulator and built-in libraries
* **Definition & Expectation:** One simulator with built-in libraries: MuJoCo, a numerical engine, motors and actuators, extra forces (magnets, thrust, tires), flexible parts, solver libraries, frozen policies and learned world models. Each library passes its known-answer case before research use.
* **Scope (Whitelist):** Use the source's simulator when it runs on our machines, otherwise MuJoCo (or the numerical engine), and record why. World models run as a labeled preview or as a test subject measured against physics; their predictions are not physics results unless validated for that domain.
* **Future State (Blacklist now):** Training; fluids, granular media and large FEM; photoreal perception; real hardware.

### SL-6 Models and memory under test
* **Definition & Expectation:** A model deciding during a trial, or a memory module evolving across episodes, can be the thing under test.
* **Scope (Whitelist):** Record every call (model identity, inputs, answer, timing, cost, failure); support waiting, measured-latency and fixed-latency timing; enforce budgets; apply declared fallbacks on failure.
* **Blacklist:** Training or fine-tuning the model under test.

### SL-7 Experiment state
* **Definition & Expectation:** Save, restore and branch the whole experiment state: world, controllers, planners, memory, random state, pending events, and action and model-call history.
* **Scope (Whitelist):** *Replay* (recorded decisions and timing) reproduces the original on the same machine and build; *fresh replication* (new randomness or model calls) is a new run; a *fresh checkout* reproduces results with no hidden files; portability across machines is M2. In M1, checkpoints are taken at quiescent points with no unrecorded model request. Follow-ups can start from a saved state.

### SL-8 Data and honest reporting
* **Definition & Expectation:** Return all the data: time series, events, contacts, model calls, measurements and checks, queryable by run, arm, trial, time and signal.
* **Scope (Whitelist):** A feasibility record for every dependency (inspected, missing, unverified, needs calibration, ran). A missing dependency makes the affected arms BLOCKED with the reason. Every counted result carries minimum provenance (source revision; dependency, asset and model identities; configuration and randomness; package, run, trial and attempt; raw evidence and analysis), kept in a declared durable location, not only temporary logs.
* **Blacklist:** Replacing a missing dependency with a proxy that AI4R did not declare.

### SL-9 Access and AI4R integration
* **Definition & Expectation:** Any agent drives SIMLAB through tools (an MCP server, a Python client and a CLI with the same operations). Inside AI4R, a builder capsule and a run capsule join the research journey, selected by the typed Planner and checked and gated like every capsule. AI4R's next question returns to the builder with references to earlier runs.
* **Blacklist:** A second chat entry point or host port; interpretation of results inside SIMLAB.

### SL-10 Operation and evidence
* **Definition & Expectation:** Run on the local x86-64 workstation, with a capability registry, a doctor command, concurrent runs, crash recovery and resource records. A live view is Conditional on the AI4R UI owner.
* **Scope (Whitelist):** Verification follows the team's `VERIFICATION.md` and SIMLAB's benchmark and test plan, with a completion report per phase and a final test report.
* **Future State (M2 and later):** The DGX Spark and native arm64; vision-language-action models and world models too large for the laptop; full input lineage (finding every run that used a faulty input); use as an RL environment and for training; further engines.
