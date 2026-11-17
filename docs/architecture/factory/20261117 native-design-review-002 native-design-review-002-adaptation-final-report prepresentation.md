# native-design-review-002: final bounded adaptation — target not met

Final outcome: report_inconclusive. The one distinct operator-justified follow-up combined retained ARM64 1 ms worker idle policy with a hardware YIELD relaxation hint in the existing cpu_relax helper. It built successfully and screened successfully as an execution, but its independent frozen verdict is target_not_met: 9.2798536971% aggregate decode gain, below the unchanged 10% criterion. No independent confirmation was admitted, appended or executed. No runtime promotion, push, merge or deployment occurred. The first 8.2955546134% screen remains target_not_met. Earlier terminal reports and decisions remain immutable; this report updates the final assessment after the explicitly authorized bounded follow-up.

## Final measurements and exactness

Frozen contract native-design-review-suite-001 version 2, DGX Spark / spark-gb10, unchanged model assets and numerical operations. Each process executes three matching unscored warmups followed by three measured requests: retained-discovery (1471 input tokens), code (32), reasoning (52), each max_new_tokens=64. Only final three requests score. Exact canonical tokens and finish must match each request's own baseline. Baseline spread <=5%, no measured case more than5% slower, >=10% conservative unchanged-candidate ABBA improvement remain required. The original deadline1794876521.7678294 and budgets were never reset. No baseline qualification rerun or evaluator/protocol change occurred in the adaptation.

| Comparison | A decode tokens/s | B decode tokens/s | Relative gain | Independent verdict |
| --- | ---: | ---: | ---: | --- |
| Fresh matched-warmup AA13cdad115f0244e1a6a020ae6e9897f4 |14.496802398012731 /14.382776624991573|—|—|baseline_valid|
| First1ms source screen7d89a882f13c407eab9cef9f9d67874f |14.455871945067688|15.655066697107072|8.295554613352452%|target_not_met|
| Combined1ms+YIELD screen0b7f6d0e3ea64ba88614dc3965d8888d |14.473416404712905|15.816528272044287|9.279853697113505%|target_not_met|

| Measured case | Combined screen A tokens/s | Combined screen B tokens/s | Paired gain |
| --- | ---: | ---: | ---: |
| retained-discovery |14.023401551338797|15.446251870444565|10.1462566974%|
| code |14.465892138691741|15.807543162002618|9.2745819646%|
| reasoning |14.96131098487505|16.214435914975553|8.3757695523%|

All combined screen gates passed: exact_tokens_and_finish, fixed_placement, baseline_timing_stable, suite_case_regression_bound. execution_complete=true, measured_cases=3, warmup_requests=3. Independent parser verified raw hashes and exact boundaries; manifest SHA256 ace2680013c3356bd5bee57fd8dd1421891f49b23bc1515149ca2802223a549d. Primary evidence0b7f6d0e3ea64ba88614dc3965d8888d:throughput and its :request.json, :manifest.json and :worker.json remain retained.

The screen has one A and one B. Its conservative_relative_gain equals relative_gain by that sample shape; this is not ABBA confirmation or a population confidence bound. Use the paired A baseline for each screen; comparing successive B rates or gains does not isolate a YIELD effect. The combined screen is direct original-vs-combined evidence, not a causal ablation separating caller and worker contributions.

## Why this experiment was chosen

The operator supplied the observation that src/dsv41/ds4_pool.hpp cpu_relax was empty on Linux ARM64 while x86 emitted pause, and supplied the official ACLE reference https://arm-software.github.io/acle/main/acle.html describing YIELD as a hardware hint for spin loops. This was recorded as externally supplied evidence in review002-external-arm64-yield-lead, not autonomous discovery or an independently fetched citation. A hint neither yields to the OS scheduler nor guarantees a speedup. Current admitted source review independently confirmed the empty helper and its use in caller completion and worker idle loops.

The historical native-throughput-goal-002 original final report was searched and read completely through provenance snapshot b034089426245d0130fdbd5fac18ea59ca86791744f298287699237044617c5d (source report SHA1b8ec791ff4c53431a9914ed7e81d24cfd59538058241cc30a01c62f9eb2f333). It supported reproducing1ms first, and discouraged repeating failed caller-CV/immediate-park ideas. Its narrow10.0175% conservative confirmation on one discovery prompt does not establish expanded-suite success. Current first1ms screen missed target; the distinct helper mechanism justified exactly one bounded follow-up, not an unchanged retry or threshold sweep. review002-hint-screen-rejection retains the new falsification of the >=10% screen hypothesis. No further candidate is proposed for execution in this envelope.

## Exact source and native build

Owned source lineage:
ORIGINAL89ae0ee6123597636ef162dec826230186c00f3b
-> retained1ms f5075a168adcdcf4289d45165bfbad00584e9eba
-> combined candidate84864456256b0e8fb4d933b7dcb67550daafaf85.
Combined tree dc0e18ca7d6d80889ac25a183487914c8d035c24; clean localcommit result status empty, pushed=false. Exactly src/dsv41/ds4_pool.hpp was committed in this adaptation. Header SHA before127d06acc0bf0020cf59df12bbe7408d6e3e988cb7736c8a705bf65a0fa5759c; after0e799c510cb61a457fe395ddc3509ad6615bb5e25aebada377613c84da0a487b.

The added branch after existing x86 handling is:
```cpp
#elif defined(__aarch64__) && (defined(__GNUC__) || defined(__clang__))
    // Hardware spin-loop hint; synchronization remains in the surrounding atomics.
    __asm__ __volatile__("yield");
```
It avoids relying on a recent ACLE intrinsic in GCC13. Existing MSVC/x86 paths and other architecture fallback remain as before. Existing ARM64 idle_spin_us=1000 remains. All atomics, memory orders, generation/ticket claims, fences, CV predicates and notifications, worker counts, numerical jobs and IoQueue stay preserved. No OS scheduler yield or new synchronization primitive was introduced. No model weights, quantization, expert count/placement, evaluator, timing or logs changed.

Native build e39288b3260d425a9818de59046b4484 succeeded for spark-gb10 and exact chosen commit/tree. Image sha256:cdc4ec5544b0c4bcc4a24023734d9b57e9026330f3f680707280993478889502, tag factory/strata:native-design-review-001, retained artifact tag. Executable SHA df7e11caed6b6afb4cdf69971fd3504fe13dcd4462fe626ae50a0bb93015237f. Build record SHA496e5964cf648ca9707c611a88c0bdb677820003f48882c7bc9a696d52f90a79. Frozen source archive SHAabe6d5757d9ccbe05cec85c24d0f860e6be36c99e971c69ac3b5d18f1a2c1f60. Dependency3cf03257f219afbe7334045ff7c6a06ac68c627d. Pinned builder sha256:d893d61a6f641fdeb6d20ce33870868d3ffd497746531a233d988427deff7f87.

Native aarch64 host and compiler, GCC13.3.0, CUDA compiler13.0.88, CMake4.4.3; Release, portable ARMv8.2 dotprod/fp16/i8mm, SM121 real/virtual, GGML_NATIVE and OpenMP off. Wall166.919236286s; configure2.564875370s, compile142.357234308s, native-compile phase146.344016982s, package18.281941543s. build_cache_present=false; cache_hit unknown. STRATA_BUILD_TESTS=OFF; no unit suite, HIP, SYCL, Windows or other-backend validation claimed. Native compilation plus frozen exact-output GPU screen are performed validation.

Baseline image remains sha256:a431b930d26d0abb6eacbd56a970f56216367d901f514a898a2197dc9d1d3b24, factory/strata:fixed-placement-89ae0ee6.

## Actual architecture and adaptation

CCs are functional packages: source_workbench supplies admitted source reads/optimistic write/localcommit; builder constructs the native image; throughput_campaign independently evaluates the frozen contract; evidence retains decisions and artifacts. Reusable nested procedures connect those capabilities. Workflow composition adapts from collected evidence; RSI here is persistent evidence-based software improvement, not model weight training. No second scheduler or restored M1/POC path was used.

Stopped earlier graphs remained stopped: design-review revision4 and design-review-continuation revision9. New operator-authorized graph design-review-adaptation revisions:
1 inspect clean retained1ms source;
2 read current Pool;
3 optimistic helper write;
4 explicit localcommit;
5 append strata-candidate-cycle instance hint-cycle, collect native build, then connected screen; stop and reconciliation.

Actual reusable nesting: strata-candidate-cycle -> construct-and-evaluate -> candidate-construction + candidate-screen.
Builder node: hint-cycle/strata-candidate-cycle/experiment/construction/build
Screen node: hint-cycle/strata-candidate-cycle/experiment/evaluation/screen

Screen request uses a real typed binding {node:builder node above,port:attempt_id,channel:result}, assembled at /build_attempt_id into {stage:screen}. It resolved only from collected successful builder result to e39288b3260d425a9818de59046b4484. No manually copied build_attempt_id, direct builder/screen leaves, unbound image or alternate scheduler was used.

If screen had been positive, strata-independent-confirmation would require an explicit input binding to that exact builder node, port attempt_id, channel result, kind text, across a new revision. Since verdict is target_not_met it was not appended; confirmation wiring is not falsely claimed as demonstrated. Both actual candidate construction-to-screen edges are demonstrated; independent acceptance is not.

Decision10 recorded externally supplied mechanism and bounded source review. Decision11 selected clean committed hint candidate. Decision12 verified native build and advanced screen. Decision13 collected screen before final assessment. Final decision will cite this report and independent target_not_met evidence. Every agent turn published a decision revision. Appends used expected_revision and decision reason/evidence referencing collected current-task nodes.

## Budget, closure and limits

Used2/3 source builds,3/5 comparisons (AA plus two distinct screens),6/14 phase GPU processes. Predecessor2 remain charged:8/16 aggregate GPU processes. Four-process/one-comparison confirmation reserve remains unused because no screen qualified. No changed threshold, protocol, numerical/model setting, deadline or budget reset; no favorable-noise retry or parameter sweep.

All submitted builds/GPU comparisons terminal succeeded operationally and collected. Combined screen cleanup_state=reaped. Build cleanup_state=process_groups_reaped;containers_unverified; graph closure does not upgrade this to verified containers. design-review-adaptation stopped and reconciled to cancelled revision5, cleanup_pending=[]. All six nodes completed; build and screen collected=true. No CC service was started. Earlier graphs and all terminal failures, reports, attempts and cleanup records remain retained. This adaptation added no failed build/GPU attempts.

Acceptance remains unproven. Exactness covers only the three frozen generated outputs. No claim of general task accuracy, quantization validation, prefill/total-request speedup, long-generation quality, cold-cache performance, causal scheduling gain or sustained/generalized improvement is supported. One case exceeding10% does not override the suite aggregate rule. No independent confirmation exists, and neither9.2799% nor the prior8.2956% becomes an accepted gain.

Proposed future input, not authorized or executed here: a separately frozen non-scoring scheduling diagnostic could distinguish spin cost from wake latency and inspect hint engagement, followed only if justified by a separately admitted untouched evaluation. Preserve this null-target result as evidence; do not tune this frozen suite further.

## Retained prior complete report

The following unchanged earlier report supplies full original protocol, predecessor failed-AA lineage, initial source reproduction, historical provenance, earlier per-case rates, failure records and exact fixed settings. Its earlier completion assessment was accurate when written; the final adaptation assessment above governs the later explicitly authorized follow-up.

---

# native-design-review-002: source reproduction completed; target not met

Outcome: report_inconclusive for the requested >=10% conservative independently confirmed decode improvement. The general ARM64 1 ms worker idle policy was reproduced fresh over ORIGINAL89ae0ee, locally committed, built natively and independently screened through the required nested workflow. Screen gain was8.295554613352452%, below10%; confirmation was therefore not admitted or executed. No candidate was promoted or pushed.

## Frozen protocol and methodological lineage

DGX Spark, target spark-gb10; contract native-design-review-suite-001 version2. DeepSeek v4.1 Flash IST DAS2.00bpw; unchanged model/tokenizer/assets, full six experts, fixed placement and76,000,000,000-byte expert budget. Eight CPU limit, memory111669149696 bytes, guard8GiB, no extra swap, timeout600s per process. Asset identity9701567ad45d018cdebb8bf322bbe74cad2d89b8108bd7d0a0a654d58f164214.

Six requests per process: first three matching unscored warmups, then the same three measured cases in order: retained-discovery1471 input tokens, code32, reasoning52; each max_new_tokens64. Exact canonical tokens and finish must match each case's own baseline. Gates remain <=5% baseline spread, no measured case more than5% slower, and >=10% conservative unchanged-candidate ABBA improvement. Timing/logging/evaluator were preserved; no prompt, threshold or measurement-policy tuning occurred.

Fixed argv: --max-context8192 --eos1 --vision off --dspark none --prefill-chunk256 --cpu-threads8 --vram-experts1.0 --reserve-mib16384 --ssd-cache0 --mmap-experts on --experts6 --verbose --dspark-conf0.65 --no-expert-cache, with the operator-pinned pack. Fixed environment: DS4_AHEAD0, DS4_ASYNC_T4, DS4_COPY_ALL0, DS4_ENGRAM_CACHE_MB64, DS4_ENGRAM_THREADS2, DS4_EXPERT_BUDGET_BYTES76000000000, DS4_STORE_GB0, DS4_UMA_HEADROOM_GIB16, STRATA_DS4_REUSE0. No candidate argument/environment overrides.

Predecessor native-design-review-001 AA1920ec8fded74d6fa1cb9372afbe9cf2 was inconclusive: exact tokens/finish and placement passed, but aggregate spread5.27043956% exceeded5%. Rates10.968294772922022 and11.546371913450322; mean11.257333343186172. Case rates were [14.172461136454228,8.938048153734428,10.979961570134504] and [14.101264707178425,9.878525012734036,11.405556644627804]. Read original observation snapshot72270531ba71dba7f26ae0613da8ab1e4d3172b363774632530fcc0cd56868fc, SHA1941fe3a435d608a0803e72a67a0ad4dc268d0f9432f243511fc43c3f46282b7. Present revision prospectively added each case's matching warmup; scored prompts and gates stayed unchanged. This is a methodological revision, not candidate evidence or an unchanged favorable-noise retry. The predecessor's2 GPU processes remain charged.

## Historical evidence and changed decision

Searched native-throughput-goal-002 and read its ORIGINAL complete throughput-round2-final-report via snapshotb034089426245d0130fdbd5fac18ea59ca86791744f298287699237044617c5d. Source database native-throughput-round2-20261116/factory/factory.sqlite; artifact SHA1b8ec791ff4c53431a9914ed7e81d24cfd59538058241cc30a01c62f9eb2f333; snapshot SHA7c1417b82437287c1dfb912fb08fa5b0fef950378c3f2a2d7ade75c0e3e3d28e. Entire20974-character provenance snapshot was read with limit24000; original report text_complete=true. Operator prose was not substituted.

Historical caller-CV screen gained8.8704%, immediate worker parking4.0385%; both missed target. General ARM64 1ms screen gained12.0194%, then unchanged ABBA6f085d494c254300af31c32edb9df959 gained11.2507% mean and10.0175148390% conservative on ONE1471-token discovery prompt. Historical A rates14.151151992216866/13.920306246737427; B15.568745742921084/15.660940635246904. Narrow conservative margin0.0175 percentage points above target, small sample and no end-to-end/generalization evidence. Historical candidate231b10b9780c8fb678d130a5d23676660e798add/image343355fc was not reused as owned source or current measurement.

review002-report-recovered-transfer records why the decision changed: mandatory report access was repaired, permitting requested general1ms reproduction from original source after valid AA. Historical failures avoided caller-CV/immediate-park repetition. No new tuning was selected after this screen: retained evidence does not identify a justified next threshold or establish CPU-quota/wake causality. review002-screen-rejection retains that revised hypothesis.

Earlier report native-design-review-002-final-report and decision3 remain immutable historical prerequisite-stop evidence. They correctly describe the earlier incomplete phase; this continuation report supersedes their task-completion assessment after repaired report access, without erasing failures.

## Fresh AA and current source screen

AA13cdad115f0244e1a6a020ae6e9897f4 returned baseline_valid. Aggregate rates14.496802398012731 and14.382776624991573; mean14.439789511502152; spread about0.7928%. All gates passed. Three matching warmups were unscored. Manifest SHA b7c641d5af0be31f4eb2948167e08527342ebc9b8bdc632fc0075698dbf2b578; independent_parse/raw_hashes/exact_boundary=true. It was reused, not rerun.

| Measured case | AA A1 tokens/s | AA A2 tokens/s | Screen A tokens/s | Screen B tokens/s | Screen gain |
| --- | ---: | ---: | ---: | ---: | ---: |
| retained-discovery |14.001312623058412|13.796968978377564|13.986013986013987|15.028413093504906|7.453153619%|
| code |14.527954963339614|14.42936375524192|14.513788098693757|15.849430411094602|9.202575532%|
| reasoning |14.99531396438613|14.970059880239521|14.896885619850101|16.12984525429709|8.276626846%|

Screen7d89a882f13c407eab9cef9f9d67874f succeeded operationally; independent verdict target_not_met. Aggregate A14.455871945067688 vs B15.655066697107072 decode tokens/s; relative_gain0.08295554613352452. The screen's conservative_relative_gain field is identical because there is one A and one B; it is NOT independent confirmation. Paired screen baseline, not AA mean, is authoritative for screen gain.

All screen gates true: exact_tokens_and_finish, fixed_placement, baseline_timing_stable, suite_case_regression_bound. All three cases improved in this pair; exactness covers only these frozen generated outputs. Independent parse, raw hashes and exact measured boundaries true; manifest SHAdc4147daea325b88d69a917afc502dab9123099f7bb55a9efd29af6810dfa4ca. Warmup_requests3, measured_cases3. Evidence IDs are both attempt IDs suffixed :throughput, :request.json, :manifest.json, :worker.json. No ABBA, population bound or target acceptance is claimed.

## Source and build identities

Original source89ae0ee6123597636ef162dec826230186c00f3b, tree55eb1b479a648d5211b2846302a60b6c79f2528e. Baseline image factory/strata:fixed-placement-89ae0ee6, IDsha256:a431b930d26d0abb6eacbd56a970f56216367d901f514a898a2197dc9d1d3b24.

Owned clean local candidate commitf5075a168adcdcf4289d45165bfbad00584e9eba has direct parent89ae0ee6123597636ef162dec826230186c00f3b, tree870d0b80694940544ffb89882b467ad781416ac8. Exactly one file committed: src/dsv41/ds4_pool.hpp. Complete original SHA8fbf2cee40e5c951ef485a267c2bd9a3a15e5935b78e9ea577e27cafb462fb6b; candidate SHA127d06acc0bf0020cf59df12bbe7408d6e3e988cb7736c8a705bf65a0fa5759c.

Change: within Pool::loop, __aarch64__/_M_ARM64 selects constexpr idle_spin_us=1000; other architectures use existing spin_us_. Existing elapsed idle check uses that value. Original caller busy-loop, ticket/generation/fence/CV predicate/wake protocol, job numerical operations and worker count preserved. IoQueue, model lane constructors, model assets, routing/experts/placement and measurement code unchanged. Unlike historical editable tree, no inherited200us lane-constructor patch was imported; general override governs all ARM64 Pool instances. Read AGENTS.md and docs/AI_REFERENCE.md. Writes used expected complete SHA; localcommit used expected original HEAD and explicit path; returned clean status and pushed=false.

Native build457dc1d08ff44572b303ce821cf65140 succeeded. Candidate image sha256:f9bab49828fb291827a12faa2dfb1386058ab8aa6602213e657145b7877fce47, tag factory/strata:native-design-review-001, retained under artifact tag. Executable SHAe00db06ca8abe0237c784a16468fa4397a6d4526d88750091f32c5236f30019c. Build record SHAdba41507ebc333468bfe53534d6d01c17354dafd635fdaf818c473f27bbb3bcd; frozen source archive SHA3069ff7a1c639035a99f1ad91bdb03abbc5019e29ca0e755bedbe0d4095b0830.

Pinned builder sha256:d893d61a6f641fdeb6d20ce33870868d3ffd497746531a233d988427deff7f87; dependency3cf03257f219afbe7334045ff7c6a06ac68c627d; host/compile architecture aarch64. GCC13.3, CUDA compiler13.0.88, CMake4.4.3, SM121 real/virtual, Release, portable ARMv8.2 dotprod/fp16/i8mm; GGML_NATIVE/OpenMP off. STRATA_BUILD_TESTS=OFF: no unit suite or other-backend validation claimed. Native compilation plus exact-output GPU screen are the performed validation. Build wall168.216684517s; configure2.404078479s, compile143.038081355s, native-compile phase146.704260151s, package19.135047139s. build_cache_present=false; cache_hit unknown, not zero. Build/result/record/request/log artifacts retained.

## Actual architecture, typed edges and graph revisions

CCs are functional packages: source_workbench owns bounded source inspection/read/optimistic write/localcommit; builder owns native image construction; throughput_campaign owns frozen admission and independent evaluation; evidence owns retained observations/decisions/artifacts. Passive materials were read before action. No second scheduler, engine_factory_loop or model-weight training was used.

Original graph design-review remains stopped at revision4, status cancelled, cleanup_pending=[]. Its AA and source-inspection nodes remain collected. Operator repair authorized NEW graph design-review-continuation instead of reviving a stopped graph.

Continuation revisions:
1 clean original source inspect.
2 read AGENTS.md.
3 read docs/AI_REFERENCE.md.
4 failed wrong-path Pool read retained.
5 replacement read of actual src/dsv41/ds4_pool.hpp.
6 clean original state recheck.
7 optimistic source write.
8 authorized explicit-path local commit.
9 append strata-candidate-cycle instance one-ms-cycle; native build/result and screen collected; stop reconciled, status cancelled, cleanup_pending=[].

Appends used expected_revision and decision reason/evidence with current task_id and exact collected prior node_id. Decision4 resumed after original report recovery;5 selected committed candidate build;6 collected build and advanced connected screen;7 collected independent screen;8 rejected target and stopped; final decision cites this report.

The actual reusable nesting was strata-candidate-cycle -> construct-and-evaluate -> candidate-construction and candidate-screen. Builder node:
one-ms-cycle/strata-candidate-cycle/experiment/construction/build
Screen node:
one-ms-cycle/strata-candidate-cycle/experiment/evaluation/screen

The screen request input is a typed result-channel binding from that builder node's attempt_id, assembled at /build_attempt_id into {stage:screen}. It resolved only after collected successful build, yielding request {stage:screen,build_attempt_id:457dc1d08ff44572b303ce821cf65140}. No manual build ID copy or independent builder/screen leaves were submitted. Same-task host admission resolved exact immutable image.

strata-independent-confirmation would bind build_attempt_id to that exact prior builder node, port attempt_id, channel result, kind text across a new graph revision. It was NOT appended or executed because screen was target_not_met. This cross-revision confirmation edge is available but not demonstrated in this rejected experiment; do not claim otherwise. Actual nested construction-to-screen data edge and evidence-backed graph adaptation were demonstrated. Full source implementation/build/screen cycle completed; successful target/confirmation cycle did not.

## Failures, budgets, cleanup and limitations

Retained prerequisite failures from earlier phase: missing/unadmitted original report reads, cross-task SCOPE_DENIED query, invalid search limit and append input, sandbox shell/report-file write failures. Earlier failure report and decision3 retained. Report-access repair did not renew budget or reset deadline.

Continuation failed read node read-original-pool/factory-source_workbench-read/operation/call returned PERSISTENCE_FAILED. Agent used stale src/ds4 path from header comment; replacement tracked src/dsv41 path succeeded with original hash. No source mutation in failed read. Optional prefix/limit inspect append failed before mutation, graph revision stayed5; corrected path-only/default admitted workflows were used. Script serialization/JSON parsing errors during inspection did not launch work or become successes. An early direct evidence read of un-ingested screen :throughput failed; subsequent native graph result ingestion succeeded. No failed build/GPU attempts or hidden retries.

Used1/3 source builds,2/5 comparison jobs (AA+screen),4/14 phase GPU processes. Including predecessor2:6/16 aggregate GPU processes. Four-process/one-comparison confirmation reserve unspent; no unchanged rerun to chase noise. Original deadline1794876521.7678294 unchanged.

AA cleanup_state=reaped; screen cleanup_state=reaped. Build cleanup_state=process_groups_reaped;containers_unverified. Both graphs report cleanup_pending=[]; this does not upgrade the builder's container verification field to verified. All durable submitted jobs terminal succeeded operationally and collected; every attempt/result/failure retained. No CC services were started.

Accuracy is exact output agreement for frozen cases only. No general task accuracy, quantization validation, prefill or total-request speedup, cold-cache result, long-generation quality, other-backend result or sustained-use generalization is established. Only one A/B screen exists. Historical conservative confirmation was on one prompt and does not rescue this suite's missed target. No causal CPU quota/wake counters were collected. Remaining budget is not evidence or reason to tune blindly.

Proposed followup, not executed or authorized as a new contract: separately freeze a non-scoring scheduling/quota/wake diagnostic to distinguish busy-spin cost from wake latency, then choose one evidence-backed candidate and a fresh independently frozen validation protocol. Keep present failed/null evidence and exact gates intact. No runtime promotion, push, merge or deployment.

## Report retention and post-report followup assessment

The local workspace report-file write failed before a file was created. The complete report was successfully published inline as immutable text/markdown factory artifact native-design-review-002-continuation-report, SHA d62c09432dd67fc7884a6cf2929cf97231624464704bb753940192a4e0981d73,14490 bytes, complete=true, and read back by evidence.read. This final v2 artifact appends these retention/followup outcomes; the first artifact is retained unchanged. No filesystem link is fabricated.

After report publication, methodology_followup was read and called. First mixed markdown/task input failed INVALID_INPUT ("Evidence must be a JSON report artifact or observation"); this is retained as a failed call. A revised input citing the structured screen :throughput and review002-screen-rejection observations succeeded operationally and returned proposal_only for contract native-design-review-suite-001. Its generic establish_repeatability fallback does not recognize the native gate shape: it suggests missing repeatability despite the valid fresh AA. Its generic zero GPU fields are not the native campaign's remaining allowance. It neither invalidates AA nor supports a new run.

review002-followup-assessment retains that limitation, the helper failure, and the agent's scoped proposal for separately admitted non-scoring CPU quota/wake diagnosis. No helper advice was executed, no threshold/grant/workload changed, and no new GPU/build process was launched after stopping.
