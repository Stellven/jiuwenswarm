# Development review and next milestones

Reviewed 2026-11-16 UTC against local commits `2e06e4b50` and `1ada3481c`, current implementation, retained run reports and the latest agent's next-input proposal. This is a development assessment and proposed milestone sequence, not a new GPU result, qualification certificate or experiment admission. Historical exports remain immutable.

## Product objective

Build a hardware/model-specific software factory that turns an operator objective into justified experiments, reusable CCs and a reproducible engine configuration. Its agent should explore alternatives, perform the cheapest discriminating tests, retain negative results, integrate promising changes and resume after failure. RSI improves the packages at their jobs; the factory supplies trustworthy tasks, feedback and cost measurements.

The success measure is useful, verified decisions per unit of time and resources. Neither the number of CCs, number of branches, number of tests nor maximum reported tokens/s alone measures that. A correct rejection or a trace that rules out an optimization can be valuable. A fast experiment without reliable numerical or scope checks is not.

## Achieved, with limits

| Area | Evidence achieved | Limit |
|---|---|---|
| Oversized model execution | Qualified local Strata build runs the pinned DeepSeek pack on Spark using storage streaming; model assets exceed physical memory | Applies to this source/image/model binding, not arbitrary models or current upstream |
| Actual engine performance | Chunk256→1024: pg4096/tg16 native total latency28.221→17.717s;1.593× combined rate; decode about14.8tokens/s in both arms | One distinct speed prompt repeated, small fresh-process sample; primarily a prefill gain |
| Correctness checks | Adapted eight-shot ARC16:16/16 each arm, exact tokens and finish match; long-prefill speed output also matches | pg512/tg128 still diverges. Sample quality agreement does not prove numerical parity or broad quality noninferiority |
| Memory tradeoff | 76→68billion-byte resident budget produced roughly8GB more observed host-available headroom | Cgroup and host accounting differ; no consistent speed benefit or exact total GPU-memory saving established |
| GPU/memory components | GPU batching passed an oracle; synthetic lifetime arena reduced allocation30→14MiB | Neither is integrated into Strata. Large microbenchmark ratios are not engine gains |
| CC library |39 top-level packages,47 including nested components; tools, components, methods, skills and verification materials | Package sealing and verification declarations are not universal certification |
| Agent-led lab loop | Earlier real agent submitted a bounded prefill screen, resumed after quiet lab execution and rejected an incorrect candidate | Exact operator-admitted templates; no general source-changing search |
| Agent branching | Latest real mission created five branches, refined/pruned and proposed a numerical investigation | CPU evidence investigation only; no new GPU experiment executed by those branches |
| Factory efficiency | Measured batch/provenance improvements; exact bounded evidence projection demonstrated | Optional metadata patch is not integrated; digest has no second live-agent cost comparison |
| Reliability and portability |1114 tests passed,1 skipped; stopped-container cleanup; hashed evidence and standalone ARM64 image exported | No clean-host restoration/endurance/reboot qualification; some host paths and lab dependencies remain external |

Detailed numbers and raw evidence locations: [night results](NIGHT-BRANCH-RESULTS.md), [earlier agent cycle](SPARK-AGENT-IMPROVEMENT-2026-11-14.md), [methodologies](NIGHT-BRANCH-METHODOLOGIES.md), [handoff audit](SPARK-DEPENDENCY-CLEANUP-AUDIT.md). Counts above describe the reviewed snapshot, not future additions.

## What needs to change in our approach

Breadth was useful for discovering mechanisms and package roles. The next round should concentrate on connecting and qualifying that breadth. Avoid adding several more wrappers whose core implementations, evidence formats or runtime integrations remain missing. Keep packages cohesive around an agent job; several CCs may serve a node without requiring their internal operations to alternate constantly.

Do not demand bitwise agreement for every future numerical optimization by default. Preserve each frozen contract's existing exactness requirement, including the present failures. For a new experiment, distinguish placement/scheduling changes, floating-point arithmetic changes and intentional approximation. Specify an appropriate numerical and quality policy before examining results. A failed exactness check is evidence to diagnose; it cannot be relabeled acceptable after observing a speed gain.

Keep the qualified local Strata baseline as the immediate comparison. An upstream Strata or llama.cpp comparison would be a separate engine/format/quantization study. It may be useful later, but switching baselines now would obscure attribution. Maintain llama.cpp as a recovery option rather than making a new engine migration the critical path.

## Source-confirmed gaps

1. **Branch reasoning and execution are separate.** `branch_workbench.py` manages graph lineage/reservations and reported observations. `loop.py` reserves admitted template cycles and delegates to Benchmark/Jobs. A branch capability list does not bind it to an executed cycle or independently verified result. Build on the existing taskgraph/store/supervisor, with explicit branch→decision→cycle→attempt→artifact linkage and idempotence. Do not add a second scheduler or planner.
2. **The live branch launcher is a historical recipe.** `scripts/factory_branch_mission.py` hardcodes task ID, inputs, package allowlist, objective and2026-11-15 deadline. Its prompt requires certain actions, so completing the demo obligations is weaker evidence than economical exploration under an outcome contract. Freeze fresh validated campaign inputs rather than editing an old run or merely extending its deadline.
3. **Qualification is narrow.** `cc_qualification.py` supports `strata.prefill_profile.v1` with explicit256→512 values and a fixed implementation-module set. That does not certify1024, the GPU package, the memory package or every declared verification unit. Add explicit independent checker support by claim, including backend/environment identity, without accepting arbitrary checker code from an imported package.
4. **Numerical evidence is missing at the decisive point.** The latest agent proposed shared-history inspection at output token50, after49 common tokens. Retained output IDs confirm the location, not its cause. There is no demonstrated common-history logit/margin trace or first-divergent-layer diagnosis.
5. **Profiling lacks an end-to-end expert timeline.** Ordinary counters exist; the earlier native profiler failure remains. Prediction evaluation has no successful real demand/readiness trace-to-intervention path. More predictors before tracing would optimize an ungrounded proxy.
6. **Factory costs are not integrated outcomes.** The latest mission took1029s with37 evidence reads and13 useful analysis calls. Branch allocations are bookkeeping, not measured process CPU consumption. Its Pareto schema is engine-oriented; build latency, analysis cost, evidence completeness and invocation overhead need role-specific views. Cached provider input counts must remain distinct from uncached input and output.
7. **Portability is export-proven, not restore-proven.** Image sealing and archive checks succeeded. External paths, host services, model mounts, deadline policy and credentials still require setup. A fresh-root restoration must demonstrate both correct dependency resolution and preserved artifact identities.

The older whole-library review remains useful historical evidence, but some findings were subsequently fixed: current `methodology.py` recognizes scoped prefill correctness failures, and the library has expanded since its23-top-level inventory. Do not reuse that review as a current open-issue list without checking source.

## Recommended milestone sequence

### M1: One connected, restartable investigation

Use existing branch, evidence, qualification, builder, loop and supervisor responsibilities. First development slice: a reusable immutable campaign specification with fresh identity, deadline, allowed packages/capabilities, evidence inputs, experiment/build limits and resource bounds. Validation must reject expired policy, missing source identity and widened effects on resume. Discover only the job-relevant packages, including optional evidence digest.

Then link an agent-selected branch to an existing admitted experiment cycle. Resume must recover the same attempt after loss of acknowledgement, retain its failure/result exactly once and leave the original decision/contract unchanged. Branch execution consumes the existing execution budget; branch reservations must not become a second route to extra experiments.

Exit evidence: one actual agent chooses between materially different hypotheses, executes one bounded experiment, resumes and updates the branch from verified artifacts, then creates a justified continuation or rejection. A controlled interruption proves no duplicate submission. A no-benefit outcome is acceptable. Report which parts are actual runs versus injected tests. Do not require a fixed number of forks or calls merely to pass the demonstration.

### M2: Numerical diagnosis and a meaningful profile

Develop a cohesive numerical-investigation CC: input/common-history replay components, exactness and logit/margin analysis tools, integration skill, bounded trace schema and independent verification units. Reuse current source/build/lab paths. Start with the retained divergent case. Freeze the teacher-forced sequence, tokenization, checkpoint/precision, routing and treatment identities. Compare logits at the same input history; later free-running outputs cannot isolate the first cause.

Exit evidence: first divergence reproduced or explicitly not reproduced; common-history top candidates, margins and numerical differences retained; observer-on/off behavior checked before performance interpretation. A suspected reduction-order effect, routing difference or implementation bug must remain a hypothesis until supported. No arbitrary tolerance selected after looking at the answer.

For performance attribution, extend the existing profiling CC with a bounded, opt-in timeline at a small number of layers/requests. Capture demand, read/ready events, bytes and waits on a common clock with event-drop reporting. First test trace invariants and failure recovery, then measure observer overhead separately. This should distinguish launch overhead, compute, memory bandwidth and storage wait before another broad kernel search.

### M3: One integrated optimization and an honest frontier

Select the next intervention from M2 evidence. Plausible alternatives are prefill chunk policy, grouped dispatch for actual quantized shapes, expert read scheduling or scratch reuse. Apply one primary change. Prefer replay or a subsystem oracle before a full-model run. Use an explicit cost/memory constraint alongside the chosen speed objective.

Exit evidence: source/profile change in a reproducible engine image; matched baseline/candidate workload; engagement check; predeclared correctness policy; fresh-process confirmation with order effects reported; reserved independent quality/workload holdout. Confirm any combined stack directly. Report prefill-heavy, decode-heavy and memory-constrained cases separately. Do not require a positive speed result to complete a sound experiment.

### M4: Factory cost and endurance

Measure the digest/batching methodology on a fresh real agent task with comparable inputs and outcome obligations. Retain wall time, tool calls, errors/retries, uncached/cached provider usage, useful analysis outputs and conclusion/evidence integrity. Smaller JSON is an input reduction, not proof of better reasoning. Cheap deterministic replay can screen tools before spending live-agent time.

Restore from committed source and the exported runtime into a fresh owned root without hidden imports from the old project directories. Exercise build→quiet→lab→recovery→review, then expand from a few cycles to a bounded endurance campaign with disk limits, crash thresholds and deduplication. A clean restart is the next step toward weeks-long work; weeks-long work is not the next unqualified launch.

## Priorities for CC development and RSI

| Job | Preferred action | Evaluation |
|---|---|---|
| Branch/experiment lifecycle | Extend branch and factory-loop packages together at their explicit interface; keep each responsibility contained | Correct lineage, exactly-once submission/recovery, enforced budget, useful next decision |
| Numerical investigation | New cohesive CC justified by missing replay/instrumentation/analysis capability | Same-history comparisons, known-error detection, identity checks and observer scope |
| Profiling/prediction | Extend deep-profile and prediction packages after a real trace exists | Timely coverage, waste, stalls, dropped events and observer overhead; eventual engine effect |
| Scoped qualification | Extend existing package with independent claim-specific checkers | Reject stale/mismatched/unsupported evidence; admit only the checked capability and deployment |
| Agent evidence intake | Use and measure digest plus revised evidence/branch skills | Correct decisions and evidence coverage per latency/token/tool-call cost |
| Native builder | Preserve native ARM64/cache work; improve only if new receipts identify a bottleneck | Correct artifact identity, clean/incremental build latency, cache validity and disk cost |
| Research intake | Consolidate pinned source/license/applicability receipts and verification paths | Reproducible transfer with explicit missing prerequisites, not number of imported papers |

RSI receives a job contract, fixed fixtures/holdouts where suitable, raw baseline receipts, failure cases and a cost vector for each selected CC. It must not be able to improve a score by dropping verification, hiding failed runs, weakening tolerances or omitting provenance. Record all verification scope changes as new claims, not silent upgrades.

## Next-round allocation proposal

Start with M1 and M2; keep M3 contingent on their evidence. A reasonable small campaign would reserve separate cells for numerical reproduction/observer checks, one selected optimization screen and independent confirmation, with a failure margin. Choose actual cell counts and absolute deadline in a fresh campaign contract before admission. The previous overnight allocation/deadline is historical and is not reused.

Immediate engineering work is CPU/source work on campaign inputs and lifecycle linkage plus the numerical replay interface. Do not start another broad GPU sweep, enable speculative approximate execution or change the baseline while these interfaces are unresolved. The objective for the next round is a trustworthy connected investigation that can yield a measured improvement—not another large catalog or a predetermined winning result.
