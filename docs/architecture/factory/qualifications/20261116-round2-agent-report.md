# Native throughput round 2 — scoped target confirmed

Task native-throughput-goal-002. Terminal recommendation: accept the frozen discovery decode target only. No runtime promotion, push, merge, deployment, generalized speedup or total-request improvement is authorized or claimed.

## Result and scope

Independent unchanged-candidate ABBA attempt 6f085d494c254300af31c32edb9df959 returned target_met. Baseline mean 14.035729119477146 tokens/s; candidate mean 15.614843189083995 tokens/s; mean gain 11.2506735928%. Conservative gain (slowest B / fastest A - 1) = 10.0175148390%, meeting the frozen >=10% requirement. Fastest A 14.151151992216866 gives threshold 15.566267191438554 tokens/s; slowest B 15.568745742921084 clears it by 0.002478551482530733 tokens/s. The conservative margin is only 0.017514839 percentage points above target: a narrow measured pass, not a robust population bound.

ABBA process rates in order: A 14.151151992216866, B 15.568745742921084, B 15.660940635246904, A 13.920306246737427 tokens/s. Exact canonical tokens and finish, fixed expert placement and baseline timing stability all passed. Host verification reports independent parsing, raw hashes and exact boundaries. Confirmation manifest SHA256 7c95101ed7b5e63024d8ff78066a1dbd7692fd328a14f9f0ce778860e917deda.

Contract native-throughput-frozen-001 on DGX Spark / spark-gb10: DeepSeek v4.1 Flash IST DAS 2.00bpw, full six experts, fixed placement, 76,000,000,000-byte expert budget, eight CPU limit. The fixed 1471-token input is repeated: first request warms, second measures, up to64 generated tokens. This is one discovery prompt shape, not a representative workload suite. Weights, numerical kernels/semantics, token workload, finish policy, placement, timing/logging implementation, observer and judge were unchanged. Worker idle waits were scheduling code changes, not measurement timer changes.

## All round 2 comparisons

| Attempt / stage | Baseline tokens/s | Candidate tokens/s | Gain | Independent verdict |
| --- | ---: | ---: | ---: | --- |
| c726bee610664936be9456e48f07d090 / AA | 14.1164623223 | — | — | baseline_valid |
| c39634e9ff744af4bfa05284d8950a2a / caller completion CV screen | 13.9387999564 | 15.1752264428 | +8.8703941% | target_not_met |
| 33cef0f3bff64964956e9ef0425d00b4 / immediate worker park screen | 13.9254552971 | 14.4878324844 | +4.0384833% | target_not_met |
| 8c285334c93c4926acc4a42c75e45324 / 1ms worker spin screen | 13.9121361650 | 15.5842890886 | +12.0193830% | screen_positive |
| 6f085d494c254300af31c32edb9df959 / same 1ms candidate ABBA | 14.0357291195 | 15.6148431891 | +11.2506736% mean; +10.0175148% conservative | target_met |

Fresh AA rates were14.0390900915 and14.1938345531. Every comparison passed exact token/finish, fixed placement and stable baseline gates. Screens are single pairs and exploratory. Their paired baseline is authoritative; do not compare against the AA mean to invent a gain. The first two candidates failed the target and were not confirmed or retried unchanged. All submitted GPU/build jobs succeeded operationally; target failure is retained separately from execution failure.

Screen request was exactly {"stage":"screen","build_attempt_id":"7af5ff2406af4b5ba530a7fe74de389c"}. Confirmation changed only stage to confirm. There were no environment or argument overrides.

## Learning transfer: recall, changed decisions, new evidence, untested hypotheses

Recall from independently searched/read round1 measurements, decision8, source-mechanisms, followup-assessment and final report snapshots: AA mean13.98355685 was valid. DS4_AHEAD=1 regressed7.0941%; CPU6 showed -0.3662% in one pair. ARM CPU-lane idle spin200us instead of20ms screened15.32677156 vs13.96983389 (+9.7133%), explicitly target_not_met, and received no ABBA. ASYNC_T2/4/8 all cover a one-token decode row; Engram threads remained untested. The generic followup fallback did not understand the native gate shape and did not invalidate the valid AA. Those records were evidence, not current authority.

Changed decisions: published round2-learning-transfer before decision1 and fresh AA. Avoided rerunning rejected lookahead/CPU6, inert async thresholds and unchanged200us for favorable noise. Inspected remaining caller spin first. After its screen missed target, restored caller behavior and tested immediate worker parking. Its smaller uplift weakened the simple “less spin is faster” idea; tested a distinct1ms worker idle tradeoff. Only a positive1ms screen enabled separate unchanged ABBA. Reserved confirmation budget throughout. This is persistent evidence-based adaptation, not model weight training.

External evidence delivery: after the initial plan, the operator supplied external-round1-cpu-telemetry from a parallel investigation, verified against original manifest23e2ca8a8864c39f7f5a137ea3fd9c7b15dfbf909b96eee9b3e9fd940b9651e6. I did not autonomously discover those counters. Baseline decode interior had43/43 periods throttled,33,842,929usec CPU over4.235925587s; inherited200us candidate0/32 throttled,14,894,774usec over3.206732265s. This corrected the initial statement that counters were unavailable in retained evidence and strengthened the scheduling investigation (round2-telemetry-assessment). Unequal interior windows omit edges; host pipe receipt is not kernel timing; one pair and cache differences do not establish causality. Throttled_usec is not lost wall time and was not converted to a stall percentage.

New evidence generated here: fresh AA, static Pool mechanism inspection, three clean same-task native source builds, three distinct screens and separate ABBA. Pool::wait was an unbounded busy loop, cpu_relax a no-op on ARM64. Caller-CV did not qualify; immediate worker parking did not qualify;1ms idle policy qualified and confirmed on this workload.

Untested: causal CPU quota/wake explanation for final1ms benefit, per-pool contribution, Engram thread counts, other prompts and lengths, cold cache behavior, other machines/backends and sustained runs. No live scheduling/wake counter collector exists among admitted workflow leaves; no new such counters were collected. No synthetic/self-reported observations were substituted for host speed evidence.

## Source and build identities

A remained ORIGINAL source89ae0ee6123597636ef162dec826230186c00f3b and image sha256:a431b930d26d0abb6eacbd56a970f56216367d901f514a898a2197dc9d1d3b24. Editable checkout began at unpromoted round1 c82131559d084d408b3a58b8e7eaaefb02477a8d, which had changed ARM lane construction to200us.

1. a9b7a7ad7560a6b30d4c76b093f8a878066e811d: added ARM caller bounded200us spin then completion CV, last-job notification synchronized through a mutex. Retained inherited worker idle setting. Header SHA2567b213fcd4f405c4f29f752b58aecc0ac4d3ba000b53801fb326392d8dd22bec5. Build9861542e467e46b895a1de2243c18be9 image sha256:4ac861d64591b3954f0f1eebcea4c0d183ba908a6803dbecf6832da30ac1be8b; executable12a648bff04a289bc669ec0a2b60b4f25a2d93be9c4756f5c49db47188970340. Target failed; caller change subsequently undone.
2. f3c793071dfa5b8599fa73abadfefa9835c0e8cd: restored original caller and applied immediate idle CV parking to all ARM64 Pool instances. Header SHA256427e14dc48581e93b366b13bcbd4a1a82807e6ba59ac7bbe85f9a2f477e78fa6. Buildec99d5a626574298a366be460f77f53b image sha256:4dd03f003064fd12378c6a40e9c22d092d70d8d9a3289300271d9dfccef931fc; executableb976f5156c625a705ab2590f194c0ef9f6caa11c150cf132d6ccfe12ac0a94b5. Target failed.
3. Final231b10b9780c8fb678d130a5d23676660e798add, tree60f45b7444382a7f2cca1eb6250119022249705f: original caller and existing generation/ticket/fence/condition-variable wake protocol; ARM64 worker idle threshold1000us across all Pool instances, other architectures retain spin_us_. Header SHA2562ad6c38fb0525252f7784bfeb03a01e9ae8bdac06db96abc638c7b0b2038547f (original inspected header8fbf2cee40e5c951ef485a267c2bd9a3a15e5935b78e9ea577e27cafb462fb6b). Inherited model lane200us constructor source remains, but ARM worker loop uses1000us. Numerical jobs, worker count, routing and placement unchanged. Build7af5ff2406af4b5ba530a7fe74de389c image sha256:343355fc4ff55d899dd4247ebf8b47025bdf44c7f3431b246f36137e69eb5c59; executablea78fdaa9d3ab2eaa1be12d03400f40824514a93dcfcaa1cb383e7e957bd3abf6. Retained locally, unpromoted.

All edits/local commits used admitted source_workbench native workflow leaves inside owned strata checkout. Clean commits only; no push/reset/runtime edit. Final comparison is original versus final policy, not a causal ablation isolating inherited lane change or individual pools.

All three builds used pinned native ARM64 builder sha256:d893d61a6f641fdeb6d20ce33870868d3ffd497746531a233d988427deff7f87, dependency3cf03257f219afbe7334045ff7c6a06ac68c627d, CUDA13.0.88, GCC13.3, SM121 flags. STRATA_BUILD_TESTS=OFF; no unit suite or cross-backend validation claimed. Build_cache_present=false for each. Wall/configure/compile/package seconds respectively:
- build9861542e:159.1298 /2.1526 /134.5906 /18.7547; build-record SHA256a2bc0a095205f2172a759a6d9d626bf4a89720a786687f15eb51f38bea0827b3.
- build ec99d5a (ec99d5a626574298a366be460f77f53b):166.3448 /2.1583 /142.9250 /17.6608; build-record SHA25654520e3ed58ff8179b99d8d418018a30f69271700e091d31a1c3173278c2fe66.
- build7af5ff24:166.8179 /2.2104 /142.7479 /18.3531; build-record SHA256f7701b4aa5a22efa277b2f9e8b1b313cbbf2cdba5ff33ce9043024c17fbd46ed.
Build result/record evidence IDs are the full attempt IDs above suffixed :build-result / :build-record. First compile-log preview was truncated.

## Prefill, total time and generalization limits

External read-only review external-round2-prefill-review of FIRST (rejected caller-CV) screen raw logs found measured A prefill15407.2ms + decode4591.5ms =19998.7ms; B20976.3+4217.4=25193.7ms. Thus higher decode tokens/s coexisted with a slower reported phase sum in that pair. Cache/order confounding and one pair prevent causal regression claims. These are engine phase times, not independently measured client end-to-end latency. They are non-scored diagnostics; judge unchanged. They do not describe the final1ms candidate. Final candidate prefill/end-to-end improvement was not established. Never equate this accepted decode target with faster complete requests.

Only two A and two B confirmation processes, one repeated input, fixed warm protocol and a narrow conservative pass. No population confidence interval, general task accuracy, long-generation quality, generalization, prefill or overall inference improvement claim. Exact output gate covers the frozen generated requests only. operator-generalization-requirement remains unmet for a broader claim.

## Execution, failures and budget

Owned native workflow throughput-round2 was created before AA, then appended from collected nodes after evidence-backed decisions. Reusable admitted leaves performed source operations/builds/comparisons. No engine_factory_loop, second scheduler or legacy followup helper was executed. Final graph revision19 stopped and reconciled to cancelled with cleanup_pending=[], all submitted work collected; graph stop is execution closure, not a performance failure.

Used3/4 source builds,5/8 comparison jobs,12/18 GPU processes (AA2 + screens6 + confirm4). No failed/cancelled build or GPU attempts; no hidden retries. Stopped after independent confirmation rather than spending remaining budget. Passive evidence methodology lookup returned UNKNOWN_MATERIAL; used available skill material. An initial history search limit30 was rejected and repaired to20. Custom read-page workflow definitions were rejected for invalid list/map/schema/missing name or subworkflows/empty workflow; graph revision stayed10, no source mutation or job submitted. Abandoned custom paging and explicitly revised design to complete already-collected Pool header. These failures are retained in round2-endpoint-design and decisions5/6. A local report-file write was rejected by the file tool; the complete text is instead retained as this factory artifact, with no local-file link claimed. They are not reported as successful workflow creation.

## Next justified action — proposed held-out validation, not executed

Before a broader speed or promotion claim, separately admit and freeze a held-out suite and exact candidate image343355fc against original baseline. No tuning or selection on holdout results; a changed candidate requires a new untouched holdout.

Proposed coverage: four unseen content families (code/debugging, mathematical reasoning, factual/instruction dialogue, long-document extraction/summarization), four input lengths (128,1024,4096,7168 tokens), two output budgets (32,256 tokens), two independently chosen items per content/length/output cell =64 unique cases. Freeze exact prompt IDs/tokenizer/assets/requests before running; avoid overlap with discovery prompt. Cross each case with cold and warm conditions =128 case-condition cells. Keep input+output within8192 context and fixed full-six-expert placement. Define cold as fresh process and independently verified cold/reclaimed cache under separately admitted host controls; if unavailable, label cold cache unknown, never pretend fresh process means cold pages. Warm includes a predeclared unscored matching warmup, then measurement. Keep concurrency/resource limits fixed.

Proposed execution: fresh AA qualification per condition, then counterbalanced original-versus-unchanged-final ABBA for each cell, randomized predeclared case order across at least two independent sessions. A host-frozen budget and power/noise assessment must precede execution; this campaign's residual allowance is not admission. Independently record startup separately, prefill milliseconds and input tokens/s, first-token latency, decode output tokens/s and inter-token latency, engine prefill+decode, true client request-to-last-token wall time and output tokens/s. Keep phase sums distinct from client latency. Retain per-case distributions and resource/cgroup counters under separately qualified non-scoring observation; do not score traced runs.

Correctness for each case: canonical tokens and finish against its own frozen baseline, unchanged full six experts/model/tokenizer/placement; failures, OOMs/timeouts and engagement gaps invalidate that case, never dropped from aggregation. Predeclare aggregate weighting (equal case/condition weight), confidence method and regression gates before data. Suggested proposal: report both geometric mean throughput ratios and latency ratios, per-family/length/cache strata, worst-case and count of cases >5% slower; flag every correctness mismatch and every >5% end-to-end or decode regression. A future operator must freeze acceptable aggregate and per-case thresholds; the current10% discovery gate cannot be silently reused as a generalization gate. Publish every case, including regressions, with no post-hoc holdout tuning.

Additionally, a separately admitted non-scoring diagnostic should measure CPU scheduling/quota and wake latency for original vs final and optionally inherited200us to explain mechanism. This is a proposal, not current authority or a new measured result.

## Provenance snapshots

Round2 measurements/diagnostic:
- database=/home/user2/software-factory-spark-20261113/native-throughput-round2-20261116/factory/factory.sqlite; task=native-throughput-goal-002; record=c726bee610664936be9456e48f07d090:throughput; snapshot_sha256=0341601b862d0e840cc73ed0e9cd341db13f545713579b91d556019c46b48b49
- database=/home/user2/software-factory-spark-20261113/native-throughput-round2-20261116/factory/factory.sqlite; task=native-throughput-goal-002; record=c39634e9ff744af4bfa05284d8950a2a:throughput; snapshot_sha256=9066567a968e9f0c997b70bc9e71f742f0fbe04d421b6b1e029e89e8d34ed8fd
- database=/home/user2/software-factory-spark-20261113/native-throughput-round2-20261116/factory/factory.sqlite; task=native-throughput-goal-002; record=33cef0f3bff64964956e9ef0425d00b4:throughput; snapshot_sha256=a717967b2d992a55c77e699bda4895b13544d0fb81e3e77aab245170ad5741c7
- database=/home/user2/software-factory-spark-20261113/native-throughput-round2-20261116/factory/factory.sqlite; task=native-throughput-goal-002; record=8c285334c93c4926acc4a42c75e45324:throughput; snapshot_sha256=801398bd0981939c2960fb7abeed6a924083e263b70b70407144576d2fa5cd6a
- database=/home/user2/software-factory-spark-20261113/native-throughput-round2-20261116/factory/factory.sqlite; task=native-throughput-goal-002; record=6f085d494c254300af31c32edb9df959:throughput; snapshot_sha256=9b56f09711c9eccdee70f631dec1820dc294771266b3721d2c65381a5c06b8a2
- database=/home/user2/software-factory-spark-20261113/native-throughput-round2-20261116/factory/factory.sqlite; task=native-throughput-goal-002; record=external-round2-prefill-review; snapshot_sha256=98a96a60a411e4e901bd0ff8ccd4d245b87debad386347864b5c2e21ad8a1e6a
- database=/home/user2/software-factory-spark-20261113/native-throughput-round2-20261116/factory/factory.sqlite; task=native-throughput-goal-002; record=external-round1-cpu-telemetry; snapshot_sha256=eb292d4e58a2d499dccd4e94fd2449a7ec6eac39af3bd5bf42a3f2b1a6500d99

Round1 history read before intervention selection:
- database=/home/user2/software-factory-spark-20261113/native-throughput-round2-20261116/factory/factory.sqlite; task=native-throughput-goal-002; record=round1-final-report-page-2; snapshot_sha256=3775c161fac342df35f835b838e3af41f004ff7471a26e741351f46f33b72346
- database=/home/user2/software-factory-spark-20261113/native-throughput-goal-20261116/factory/factory.sqlite; task=native-throughput-goal-001; record=followup-assessment; snapshot_sha256=53f923f101e6d9bda42135221f3585b64e4176b7f01db091e084d2ca49ce45c8
- database=/home/user2/software-factory-spark-20261113/native-throughput-goal-20261116/factory/factory.sqlite; task=native-throughput-goal-001; record=native-throughput-goal-001:decision:8; snapshot_sha256=aaaf41953dc19d2372f8bbbf662f402c948684bb8ed0a2ad09917f1702c01b83
- database=/home/user2/software-factory-spark-20261113/native-throughput-goal-20261116/factory/factory.sqlite; task=native-throughput-goal-001; record=15b90731b65244efaeac4b91fb52d8da:throughput; snapshot_sha256=6ae81c2dd4329e1d131f7e58084e3838b73ae9f1a5e6059d66fd3eb7825a0ddc
- database=/home/user2/software-factory-spark-20261113/native-throughput-goal-20261116/factory/factory.sqlite; task=native-throughput-goal-001; record=96d16c5f09ef406689b158fe3e44f8ce:throughput; snapshot_sha256=a3efb6dc2f01ab84bba1b781b849001849f9a5458f90207e3100ed465345e679
- database=/home/user2/software-factory-spark-20261113/native-throughput-goal-20261116/factory/factory.sqlite; task=native-throughput-goal-001; record=ca30536c6b4b4d348b04a17ccde68a48:throughput; snapshot_sha256=1c2cf5a30bd26599870807222b001a9d9cd51a6b2d451a2c89619134126aed6d
- database=/home/user2/software-factory-spark-20261113/native-throughput-goal-20261116/factory/factory.sqlite; task=native-throughput-goal-001; record=1f28df9ed3be4c1087c87c84e48ae7b0:throughput; snapshot_sha256=676df04ac7a9df95be019bdd03b2a7d3e6ffa506738124076dabd21eb10646fc
- database=/home/user2/software-factory-spark-20261113/native-throughput-round2-20261116/factory/factory.sqlite; task=native-throughput-goal-002; record=round1-final-report-page-3; snapshot_sha256=dfb16d4a7bfaf5577c40aa60ff6f094404aa440ee6d2f59e200cc70599258d67
- database=/home/user2/software-factory-spark-20261113/native-throughput-goal-20261116/factory/factory.sqlite; task=native-throughput-goal-001; record=source-mechanisms; snapshot_sha256=1fb17746b74672526d79939ba3a28223137638c8915c22ce4946d1ca0a77b7f8
- database=/home/user2/software-factory-spark-20261113/native-throughput-round2-20261116/factory/factory.sqlite; task=native-throughput-goal-002; record=round1-final-report-page-1; snapshot_sha256=535ba68007ace79334a0bc6a3c83e83f16aefc5a0dfacfd93b5dc357e83057fc.
- Round1 final report original artifact throughput-goal-final-report-v2 SHA256e01e51eb110cdce3dcb3d7a9f9ad66f54d638ff389e287e68151c3dd156fd321, delivered as three cited historical report pages.

Current-task decision trail: round2-learning-transfer, round2-telemetry-assessment, round2-pool-mechanism, round2-endpoint-design and decisions1 through11 retain recall, external-evidence correction, scope revision, rejected hypotheses and candidate requests. Terminal decision will cite this report and independent confirmation.
