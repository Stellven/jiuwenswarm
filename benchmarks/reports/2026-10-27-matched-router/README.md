# Matched AI4R routing comparison — 27 October 2026

The fixed reference now runs ChatGPT GPT-6.1-Sol **through AI4R's production
model bridge**, with the same independent local verifier and component gate
as the automatic arm. The historical direct-ChatGPT reference is unchanged.
These are isolated MR01 routing-component observations, not a complete
Compiler/Planner/research-DAG or frontend acceptance campaign.

| Observed result | Fixed ChatGPT in AI4R | Automatic routing v8 |
| --- | ---: | ---: |
| Exact-correct worker answers | 24/24 | 24/24 |
| Correct answers allowed through gate | 20/24 | 20/24 |
| Correct answers blocked by verifier | 4 | 4 |
| Worker calls to ChatGPT | 24 | 18 |
| Worker calls to Lightning | 0 | 6 |
| Successful selector calls | 0 | 6 |
| Failed calls / selector fallbacks | 0 / 0 | 0 / 0 |
| Total reported tokens, all roles | 244,732 | 200,227 |
| Sum of observed request durations | 271.16 s | 313.69 s |

Automatic routing used **18.19% fewer reported tokens**, including selector and
verifier usage. It was slower in this observation. Latency was not measured on
an otherwise idle, controlled host; application image builds overlapped part of
the campaign. No monetary saving is calculated: subscription marginal prices
and local compute prices were not observed. Providers use different tokenizers.

| Role | Fixed reference tokens | Automatic tokens |
| --- | ---: | ---: |
| Worker | 227,039 | 176,166 |
| Independent verifier | 17,693 | 14,471 |
| Router assessor | 0 | 9,590 |

c01 used actual subscription GPT-6.1-Sol on all three automatic attempts;
all three answers were correct and their gates advanced. Critical task risks
are handled by general task rules, not case IDs or answer lookup. No failed
answer was repaired or replayed. Verifiers saw only declaration and output.

The verifier false-block problem is **not resolved**. In the fixed arm it
blocked c05 repeats 1/2 and c08 repeats 0/1; in the automatic arm it blocked
c02 repeat 2, c05 repeats 0/1 and c06 repeat 2. The verifier is stochastic;
matching aggregate counts do not mean matching per-request decisions or a
statistical equivalence result. Gates were never overridden.

## Deployed pool and access

The current local pool is gpt-oss-20b MXFP4, Nemotron 3.5 Lightning 30B-A3B
Q4_0, and gpt-oss-120b MXFP4. Each scored 8/8 in one direct qualification on
the same public development fixtures; Qwen Q4_K_M scored 4/8 and was replaced.
This is development-set selection, not evidence that these are universally
the best models. ChatGPT subscription model and medium effort are unchanged.

gpt-oss-20b supplies the assessor and a separate verifier invocation. All three
local models remain eligible executors; this campaign's six local workers
actually selected Lightning. The assessor has a frozen 1,024-token / 30-second
ceiling, with its time inside the worker envelope. Worker time is 90 seconds,
and verifier time is separately 60 seconds. A request for no assessor reasoning
does not guarantee the server disabled it; actual reasoning usage is included.

The single existing UI remains on **5175**. In Settings → Model, select
**AI4R · automatic model routing**, or **ChatGPT 6.1 Sol · fixed worker in AI4R**
for the reference, save, and start new research. Existing runs retain frozen
selections. ChatGPT sign-in is required for the protected critical-task tier.

Shared local APIs require tailnet access but no API key:

| Model | Base URL |
| --- | --- |
| Lightning | `http://100.105.127.48:8011/v1` |
| gpt-oss-20b | `http://100.105.127.48:8012/v1` |
| gpt-oss-120b | `http://100.105.127.48:8013/v1` |

Use `/models` to discover the exact pinned served ID. Services bind loopback
and the Tailscale address, not the public interface. The final check observed
all three healthy, no OOM kills, ChatGPT signed in and about 20 GiB available.

## Evidence

- [Assessment and per-request receipt hashes](assessment.json): deterministic
  offline scoring against the original pinned reviewer criteria; no model judge.
- [Candidate qualification](local-qualification.json).
- [Successful real selector/local-worker/verifier/gate probe](probe-summary.json).
- [Measured source provenance](source-provenance.json).
- [Released image provenance](release-provenance.json): final changes were UI,
  documentation and a model-readiness explanatory string. Routing and the
  benchmark call path were unchanged. Exact source inventories remain on Spark.

All record hashes and 42 subscription native traces were checked, including
actual prompt hashes, resolved GPT-6.1-Sol identity, medium effort and terminal
completion. Eight fixtures were repeated three times; they are not 24
independent tasks or a held-out evaluation. Reviewer answers and credentials
were not exported. Full original receipts remain on `gx10-004d` under
`/home/user2/ai4r-data/benchmarks/router-v8-20261027/`.

The v5 checkpoint, original reports and stopped old pool weights are retained.
