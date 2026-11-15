# Engine capability-capsule review

Reviewed 2026-11-14; 13 packages. This is a source/evidence review, not a new test or GPU run. Paths below are relative to this repository unless explicitly called workspace paths. `C` means `jiuwenswarm/factory/ccs`; `S` means `C/expert_streaming/components`. Each section identifies a real manifest ID, not a proposed domain name.

The engine library has three different jobs: inspect evidence, supply source patches, and generate bounded runtime configurations/experiments. The factory executes the latter through its admitted builder/lab paths. Only integrated patches or selected native flags change a delivered inference engine. Reading materials, sealing packages, passing Python tests or qualifying profile transformation does not prove engine correctness or benefit. The feature-scoped controller exception preserves that division of responsibility ([AGENTS.md:7](../../../../AGENTS.md), [AMENDMENT.md:7](../AMENDMENT.md)).

## Shared boundaries and evidence

All eight nested llama.cpp packages are **passive**: their manifests contain materials but no bindings, capabilities, needs or changes. Materials include `component.yaml` plus actual patch files with SHA256 declarations. They require an external admitted source-integration/build/lab workflow; none installs or launches itself. `components.py:9` validates names and material declarations, `components.py:25` resolves source dependents and `components.py:49` validates environment keys. Source presence and runtime enablement are deliberately separate. The graph is mmap_advice → router_prefetch → expert_fill → expert_pregate; thread_names and expert_readiness require fill/pregate; inflight_join requires readiness; phase_stats requires join source. The latter source dependencies can remain switched off at runtime where documented.

All eight target the pinned llama.cpp base `cf34d311332e362198f0a410c466d1e940287d02`. Their patches assume Linux file mappings/host expert consumption; the demonstrated path is Qwen35MoE on Jetson Orin UMA, not Strata/GB10. They do not move experts between GPU and CPU. GGUF/CPU-MoE/mmap applicability is guidance, not a portable performance guarantee ([STREAMING.md:3](../../../../jiuwenswarm/factory/ccs/expert_streaming/STREAMING.md), [SOURCE-MAP.md:15](../../../../jiuwenswarm/factory/ccs/expert_streaming/SOURCE-MAP.md)).

For every nested component, engagement regexes, correctness obligations and acceptance policies in `component.yaml` are **declarations**, not verification-unit certificates. None supplies `VERIFICATION-UNITS.json`. `tests/factory/test_expert_streaming.py:20` checks material existence/schema/acceptance classification; `:55` parses a recorded stderr fixture; `:87`, `:119` and `:128` exercise synthetic acceptance/keep/overhead behavior. These protect the factory evidence path, not patch numerical semantics or C++ concurrency. `EVIDENCE.md:25` requires accepted ABBA performance plus byte-identical greedy stdout for performance components, versus engagement, correctness and bounded overhead for observability. The declared 3% overhead bound is not measured merely by including it.

Historical evidence is mixed: `STATUS-2026-11-12.md:29` reports Run 4 fill 1.11× and pregate 1.13× accepted individually, but ratios must not be multiplied. `:30` says mmap/router source stayed dormant and thread_names was reverted under older acceptance rules. `:33` records real Qwen readiness counters from a cache-confounded smoke whose A/B report was INVALID. `:35` and `:67` record null/rejected Run 5 fill trials and dormant regressing prerequisites. These historical summaries are not newly reproduced measurements or proof that the same packages benefit Spark. The source map itself says it was read from an older `/home/muk` checkout and not run-verified (`SOURCE-MAP.md:3–13`).

## 1. `engine.expert_streaming` — `C/expert_streaming`

**Role/materials/capabilities.** Factory domain inspection and agent guidance: `applicability` reads GGUF headers/host memory or an approved Strata asset inventory; `engagement` interprets retained attempt/evaluation artifacts. Materials are STREAMING.md, EVIDENCE.md, SOURCE-MAP.md, ONTOLOGY.yaml and all eight component descriptors (`cc.yaml:4–40`). Both tools declare Python and `process.exec`; the wrapper delegates to the task-scoped API with a 49-second timeout (`run.py:10–24`). Actual implementation also appends task observations (`expert_streaming.py:379`); its “read-only” wording means no engine execution, not zero persistent effects.

**Implementation/dependencies.** `expert_streaming.py:41` parses GGUF metadata/tensor layout; `:108` applies CPU-side/mmap/memory heuristics; `:152` parses llama config/fill/pregate/readiness/phase evidence. `:217` validates complete Strata inventory without borrowing llama CPU-placement assumptions; `:256` uses native T/DONE evidence, retaining unavailable fill/readiness/inflight metrics as unknown. `:334` selects backend from the saved contract and pairs scoped artifacts. Dependencies include ontology, contract/store, engine_adapters and the normal lab evidence path. It never patches the delivered engine.

**Verification/readiness.** Unit evidence: `test_expert_streaming.py:43–80` uses a synthetic GGUF and stored fixture; `test_expert_streaming_strata.py:61–173` checks inventory identity, native units, unknown readiness, missing stderr, reduced/partial output and cross-arm evidence isolation. No declared domain verification unit. Ready for bounded inspection, not optimization certification. A measured native phase does not imply streaming-readiness engagement.

**Improvements.** Explicitly document observation writes in capability wording/effects; expose backend/contract compatibility before dispatch so benchmark-v2/scoped workbench records are not mistaken for supported `strata-v1` records (`expert_streaming.py:301`). Add backend-specific verification units for asset applicability and artifact/phase interpretation, with unknown-value obligations. Refresh the historical source map with relocatable revision/symbol anchors. No new Strata prefetch claim is justified by llama counters.

## 2. `factory.components.mmap_advice` — `S/mmap_advice`

**Purpose/materials/delivered effect.** Descriptor plus `01-mmap-advice-random.patch`; suppresses sequential/readahead hints and applies random advice to the mapping (`01…patch:9`, `component.yaml:8–16`). No source prerequisites. `LLAMA_MMAP_ADVICE=random` is an I/O/page-cache treatment, not expert placement.

**Verification/applicability/readiness.** Declares the `llama_mmap` random-advice line, byte-identical greedy stdout and performance acceptance (`component.yaml:10–23`). Shared Python tests verify descriptor/parser/policy only. Historical dormant/regressing evidence above gives no accepted portable win. Linux mmap behavior depends on cache pressure and kernel; usable as an experimental pinned patch, not enabled by default.

**Gap/improvement.** Router-prefetch changes/suppresses this global advice path (`SOURCE-MAP.md:74–85`), so independent “advice on” labels can misdescribe the effective treatment. Record effective per-range advice and cache protocol; qualify exact arm behavior and compare actual bytes/latency before retention.

## 3. `factory.components.router_prefetch` — `S/router_prefetch`

**Purpose/materials/delivered effect.** Descriptor plus `02-router-prefetch.patch`; depends on mmap_advice source. Adds a CPU-consumer scheduler callback, loader mapping metadata and page-aligned `MADV_WILLNEED` advice on selected expert ranges; optional next-layer same-ID prediction (`02…patch:109–151`, `:170–230`). Device-only/noncontiguous/unsupported tensors are skipped. Its source hook is reused by fill; enabling it is separate.

**Verification/applicability/readiness.** Declares CPU-hook log plus nonzero advise calls, greedy identity and performance acceptance (`component.yaml:13–30`). Shared tests do not execute the C++ hook. Historical work kept it dormant as a source prerequisite. Useful integration infrastructure on supported host-mapped llama experts; performance remains experimental. Advice calls/bytes are requests, not bytes physically ready.

**Gap/improvement.** Separate hook installation evidence from successful, timely prefetch evidence; retain unsupported-tensor/failed-advice counts and readiness at consumer arrival. Make the fill-on/prefetch-off interaction explicit in machine-readable compatibility metadata. It is not a Strata routing port.

## 4. `factory.components.expert_fill` — `S/expert_fill`

**Purpose/materials/delivered effect.** Descriptor plus patches03/04/05: mincore-based residency scanning, bounded parallel buffered `pread` of selected missing expert ranges before demand compute, phase-specific controls and diagnostics. Depends on mmap_advice/router_prefetch source; `LLAMA_EXPERT_FILL=1` enables it. Thread/chunk/random/decode token limits are explicit (`component.yaml:11–25`, `:39–49`). This changes the engine demand I/O path; it does not alter target routing.

**Verification/applicability/readiness.** Declares active/random-at-decode/nonzero-call signals, greedy identity and performance acceptance (`component.yaml:26–36`, `:51`). Run 4 acceptance and later null trials show conditional evidence, not universal readiness. Shared parser tests cannot establish pread error handling, cancellation or concurrent worker safety. Applicable to CPU host-mapped experts larger than memory; not directly applicable to native Strata CUDA paths.

**Gap/improvement.** Preserve bytes and critical-path wait per actual decode token, and compare cache-start states. Add a bounded patch verification unit covering exact integration base, I/O failure handling and output equivalence; verify effective range semantics by source revision (03 permissive versus08 strict). Retain null settings instead of selecting an unreported best trial.

## 5. `factory.components.expert_pregate` — `S/expert_pregate`

**Purpose/materials/delivered effect.** Descriptor plus patches06/07/08; depends on fill. Predicts future expert routes, schedules bounded async reads, then adds scheduling controls and strict effective config observation (`component.yaml:4–18`, `:32–38`). Changes engine pre-demand scheduling; factory agent supplies the hypothesis and admitted settings.

**Verification/applicability/readiness.** Requires active/effective pregate plus nonzero predictions, greedy identity and performance acceptance (`component.yaml:19–41`). Historical Run 4 accepted its own comparison; no multiplication with fill gains. Real readiness smoke shows why high recall is insufficient: late/duplicate/wasted reads can coexist. Shared fixture/policy tests are not predictor or worker correctness tests. Experimental supported llama path only.

**Gap/improvement.** Qualify predicted-range identity, readiness-at-arrival, queue delay and wasted bytes together. Couple runtime evidence to the exact k/order/lookahead/concurrency values, and exercise bounded shutdown/read-error behavior. Add per-configuration negative results and source prerequisite closure to the reusable material.

## 6. `factory.components.thread_names` — `S/thread_names`

**Purpose/materials/delivered effect.** Descriptor plus patch09; depends on fill and pregate source even if pregate is dormant. Linux `pthread_setname_np` labels workers `xfill-N` (`09…patch:19`, `component.yaml:7–21`); no enable variable. This is delivered observability, not a speed optimization.

**Verification/applicability/readiness.** Declares owned-thread capture, greedy identity and observability acceptance with3% overhead (`component.yaml:11–26`). Shared tests model capture/overhead gates, not live thread naming. Historically reverted under obsolete performance-only criteria; that rejection is not a current overhead measurement. Ready as a small pinned diagnostic patch, awaiting owned-process signal/overhead qualification for any new engine build.

**Gap/improvement.** The patch ignores the pthread naming return value; capture failures/platform absence must remain unknown/invalid rather than “no overhead.” Retire duplicate legacy `factory.engine_component` from new-task discovery and maintain one authoritative patch/hash descriptor.

## 7. `factory.components.expert_readiness` — `S/expert_readiness`

**Purpose/materials/delivered effect.** Descriptor plus patch10; depends on fill/pregate. At layer arrival before demand fill, splits selected bytes into resident/missing and predicted/unpredicted, and records wasted async/duplicate demand bytes (`component.yaml:19–25`, `10…patch:88`). This observes page residency, not counterfactual causality or critical-path savings.

**Verification/applicability/readiness.** Active/effective/readiness decode-token signals, greedy identity and3% overhead are declared (`component.yaml:10–29`). Historical Qwen smoke reports actual counters but invalid A/B timing; no accepted speed result follows. Shared tests exercise parsing and unknown fields, not C++ counter conservation or probe overhead. Useful experimental diagnosis on the pinned llama path, not yet an engine-independent readiness sensor.

**Gap/improvement.** Add verification units for byte partition/conservation and denominator/phase attribution, plus matched instrumentation-off overhead. Expose sampling time explicitly and distinguish preexisting residency from prediction-created residency; maintain “not measured” on absent counters.

## 8. `factory.components.inflight_join` — `S/inflight_join`

**Purpose/materials/delivered effect.** Descriptor plus patch11; requires readiness source, while readiness may be disabled. Requires active pregate at runtime. Tracks queued/active chunks, claims queued work or waits on a condition variable for overlapping in-flight reads instead of duplicate demand pread (`11…patch:138–177`, `component.yaml:16–22`). It changes synchronization and critical-path I/O.

**Verification/applicability/readiness.** Declares effective join=1, nonzero join_waits, greedy identity and performance acceptance (`component.yaml:11–24`). Nonzero waits prove an exercised join path, not lower latency. No current Spark/Strata or independent accepted join trial was found in the inspected evidence; shared parser/schema tests are insufficient for race/deadlock qualification. Experimental pinned llama implementation.

**Gap/improvement.** Before a new runtime claim, verify overlapping ranges, queued claims, partial read/errors, worker teardown and wait completion under bounded fault injection; directly compare duplicate bytes and demand wait. An async job marked done does not itself prove residency remained available at demand.

## 9. `factory.components.phase_stats` — `S/phase_stats`

**Purpose/materials/delivered effect.** Descriptor plus patch16; requires01–11 integration through join because shared config/validator lines are edited. Runtime fill/pregate/join can be off. Uses `getrusage(RUSAGE_SELF)` decode deltas plus token latency distribution/first-eight versus later-token summaries (`16…patch:49–77`, `component.yaml:16–22`). Delivered process-wide phase observability only.

**Verification/applicability/readiness.** Effective phase_stats and positive decode_tokens plus greedy identity/3% overhead are declared (`component.yaml:11–26`). Shared tests parse synthetic/fixture fields; no independently accepted live phase_stats overhead result is established here. Linux rusage counters can aid diagnosis, but are not per-thread attribution, blocked duration, fault cost or SSD bytes. Experimental diagnostic patch.

**Gap/improvement.** Add phase-boundary/counter-unit and percentile verification; measure disabled/enabled overhead in the identical source stack. Source-heavy dependency closure for a small observer is an integration cost: rebase a truly independent observer if useful, then qualify that separate release.

## 10. `factory.engine_component` — `C/engine_component`

**Role/materials/effects.** Legacy recorded-demo package; no executable capability. Contains the same patch09, a combined01–08 provenance/reverse-check patch, component.yaml and README (`cc.yaml:4–16`). The descriptor explicitly targets Jetson Orin aarch64/sm87 and qwen35moe, with pre-integration commit e14b87603 plus pinned upstream base (`component.yaml:1–19`). Applying combined01–08 again to that integrated checkout would be wrong (`README.md:12–15`).

**Verification/readiness.** Declares xfill threads/effective config and immutable qwen36-greedy-v1 stdout identity (`component.yaml:39–46`). README explicitly says packaging performed no live verification; CPU Granite proves config parsing only (`README.md:17–24`). No verification-unit material. Ready solely for replaying that recorded demo/provenance; not the general component evolution entry point.

**Overlap/improvement.** Exact patch hash duplicates nested thread_names. Mark legacy/deprecated status in discoverable metadata and route new tasks to `factory.components.thread_names`; retain historical source/image identities rather than silently replacing the package with new semantics. No Spark or Strata readiness is inherited.

## 11. `engine.strata_prefill_chunk` — `C/strata_prefill_chunk`

**Role/materials/capability.** COMPONENT.json and METHOD.md plus pure `apply(base_profile, chunk_tokens)`; Python/process.exec is the wrapper effect, not GPU use (`cc.yaml:4–31`, `run.py:1–12`). `strata_prefill.py:9–40` checks integer256/512/1024, reuses fixed full-six/static/no-reuse profile validation, deep-copies and changes only one `--prefill-chunk` value, returning before/after hashes and unmeasured candidate status. No source build, job, contract mutation or promotion occurs. Delivered effect is the already-existing native engine setting when an admitted profile later executes.

**Dependencies/applicability.** Pinned Strata DSV41 revision ffa80d…, Spark/GB10 full-six profile. Fixed environment excludes DS4_CHUNK/DS4_WINDOWS overrides via an allowlist (`strata_components.py:14–68`). The source mechanism is native layer-major prompt chunking, which changes scratch memory and possibly expert placement. Source inspected in sibling `../strata-deepseek/src/dsv41/ds4_model.cu:2719–2725,2789–2803`; those current lines differ from the historical COMPONENT.json map, so revision plus symbol anchors matter. Actual startup chunk must be checked: requested values may be clamped/fall back.

**Verification/live evidence/readiness.** No standalone verification-unit material. `test_strata_prefill.py:34–115` tests reversible single-change sealing, forbidden overrides, effective chunk/draft rejection and v2 scoring separation. Historical operator-host benchmark reports accepted combined native rate9.20→10.70tokens/s (+16.27% paired ratio), ARC60/64 both, but decode14.43→14.02 and incomplete baseline warmup (`SPARK-FACTORY-EXPERIMENTS-2026-11-14.md:70–101`). This is scoped evidence, not a stable end-to-end/general correctness claim. Latest stricter workbench screen fails cross-arm single-token equality; neither historical contract should be rescored to erase the other. Ready as a candidate generator; no default promotion.

**Gaps/improvements.** Profile transform currently preserves dspark on as well as none (`strata_prefill.py:19–22`), although METHOD.md instructs none for the single-mechanism campaign. Encode the narrower experiment eligibility separately and disclose this difference. Share an explicit transformation unit with workbench, refresh source anchors, and resolve cross-chunk numerical repeatability before broad deployment.

## 12. `engine.strata_verified_drafting` — `C/strata_verified_drafting`

**Role/materials/capability.** COMPONENT.json, METHOD.md and bounded API wrapper; `apply` changes only `--dspark none/on`, not source or a frozen contract (`cc.yaml:15–30`, `run.py:8–19`). `strata_components.py:35–86` validates boolean enabled, exactly one required flag, full six experts, static cache, fixed confidence0.65, no prefix reuse and restricted environment; emits hashes and candidate-only obligations. It orchestrates native MTP draft/target verification already in Strata. Sibling engine `ds4_main.cpp:296–313` calls draft/verify; this is not a llama patch port.

**Verification/applicability/readiness.** Python/process.exec; actual GPU work belongs to benchmark/lab. `test_strata_components.py:19–95` covers no mutation, idempotence/reversal, boolean schema, unsafe/confounding profiles and sealing; no package verification-unit declaration. Live comparison is stronger than unit evidence: eight quality plus eight speed phases, raw independent analysis, offered840/accepted696 drafts, fixed six experts and cleanup (`SPARK-BENCHMARK-RESULTS.md:40–108`). Warm decode accepted +16.95%, but native prefill+decode was6.43% slower; ARC sample60/64 both and arbitrary continuation tokens differ (`:3–28`). Therefore configuration-ready and conditionally measured, not universally beneficial or byte-equivalent. Applies only to the pinned native DSV41/Spark setup with compatible assets and sufficient memory, not arbitrary engines/models.

**Gaps/improvements.** Add a profile-transform verification unit and separate runtime draft-cost unit (offered/accepted, memory/placement and prefill/decode). Select metrics from intended workload before admission; do not promote drafting on warm decode alone when short-output total latency is the objective. Full-six target verification does not prove bit-identical greedy output or broad task accuracy.

## 13. `engine.strata_prefill_workbench` — `C/strata_prefill_workbench`

**Role/materials/capabilities.** METHOD.md and VERIFICATION-UNITS.json; seven operations inspect/design/apply/verify_profile/submit/status/result (`cc.yaml:15–72`). All need Python/process.exec; only submit additionally declares gpu.use. This is a factory domain workbench covering the experiment lifecycle, not a new inference kernel. Design creates a separate scoped contract; submit requires exact operator-admitted identity; result imports independent raw evidence. The delivered engine still receives the native chunk flag.

**Implementation/dependencies.** `prefill_workbench.py:31–87` freezes Spark image, same512-token input, chunks256/512, AB screen or ABBA confirm, full-six static profile, drafting off, four warmups plus three measured requests, one output token and limits. `:139–228` independently checks native framing, startup chunk, exact argv/environment/mount/GPU, pipe coverage, cleanup and sealed file/source identities. `:234–250` uses Jobs and host admission; `prefill_worker.py:29–90` rechecks pins, waits for quiet control, owns recorder/lease/guarded containers, preserves partial evidence and seals recovery. `:174–205` returns scoped correctness failure before any performance signal when cross-arm tokens disagree. Uses benchmark helpers, strata_prefill/components, recorder/lifecycle/targets and host bridge; source closure is explicitly hashed.

**Verification/live readiness.** Sole declared unit is `profile-single-change`, checker `strata.prefill_profile.v1`, covering **apply/verify_profile only**, not inspect/design/submit/status/result (`VERIFICATION-UNITS.json:3–15`). The host re-evaluates profile evidence and ties package/material/checker/module identities; eligible assessments explicitly set runtime_qualified=false and scientific_benefit=not_evaluated (`cc_qualification.py:200–240`). `test_prefill_workbench.py:64–196` checks frozen contracts, zero decode time, draft/chunk evidence, cross-arm mismatch, screen-versus-confirm, forged/incomplete boundaries, worker partial failure and occupied observations. Tests are synthetic; they are not the live screen.

The retained real Jiuwen proof (`/home/user2/software-factory-spark-20261113/results/agent-improvement-proof.json`, task spark-agent-improvement-001) shows inspect/design/apply/verify_profile calls and configuration qualification, then host loop submission/collection of the scoped child. It does not show that the workbench's own submit/status/result capabilities were all directly invoked. Actual two fresh-process cells completed and cleaned up; medians4368.7ms versus3211.6ms were descriptive only because tokens9544 versus5 disagreed throughout seven repeats per arm. The agent stopped report_inconclusive, without confirmation or promotion (`SPARK-AGENT-IMPROVEMENT-2026-11-14.md:93–126`). This is useful live factory-loop evidence and a rejected candidate, not a qualified speedup.

**Gaps/improvements.** Extend qualification with separate units for contract design, lifecycle/cleanup and independent raw-result import rather than extending the profile certificate's claim. Make `apply/verify_profile` schema bounds explicit in this manifest as in standalone chunk. Consolidate duplicate profile operations into one authoritative implementation while retaining distinct benchmark/scoped contracts. Highest-value next capability is separately admitted A/A repeatability plus numerical-parity/logit diagnostics; the first-token mismatch is unexplained and does not itself prove which token is correct or an engine defect. Broader prompt sets, fresh process replicates, convergence and full-generation quality require separate frozen integration work.

## Priority actions

1. Preserve the latest negative prefill screen and qualify A/A/numerical parity before any chunk default change; historical ARC acceptance cannot waive this scoped mismatch.
2. Keep configuration eligibility, runtime engagement, correctness, performance and promotion as separate claims. Add domain verification units incrementally; twelve of these13 packages have none, and workbench covers only2 of7 operations.
3. Keep historical llama patch materials available with engine/revision/platform and passive/legacy status; do not surface them as Strata-ready integrations. Replace old absolute source-map locations with pinned, relocatable references.
4. Consolidate exact duplicate patch09 and chunk-transform packaging; preserve independent experiment contracts and historical provenance. Expose source dependencies separately from runtime enablement to prevent dormant prerequisites from being counted as retained performance wins.
