# Local routing development protocol, version 1

This retained protocol describes the historical E4B-selection / fixed-Qwen
development comparison. It is **not the current app policy or the requested
ChatGPT baseline**. The prior protected Qwen-only policy is
`ai4r-local-bounded-routing:2`. New app runs use
`ai4r-hybrid-bounded-routing:5`: trusted Capsule scopes use direct cost-free
routing rules; otherwise Qwen identifies task operations and the host maps them
to Qwen or the signed-in GPT-6.1-Sol subscription for each compatible task Capsule;
verification remains a separate Qwen call with declaration and output only.
At most four subscription Capsule invocations are reserved per research run.
E4B and Bolt do not execute in this pool. Original frozen runs and scores remain
unchanged. This policy aims to reduce observed tokens relative to all-ChatGPT
execution; it does not assert an achieved quality or monetary saving.
The requested external comparison uses ChatGPT subscription authentication in
the Spark-backed app's Settings > Model > ChatGPT comparison mode. That sign-in
does not automatically grant this isolated v1 controller access to the account;
do not report any v1 fixed-Qwen observation as a ChatGPT result.

The same host controller can run the current hybrid routing component with
`prepare --arm hybrid`. Use a fresh output directory and the same public source
plan/repeats as the ChatGPT comparator. The owner uses the production
`AutomaticRouting`, `GovernedBridge`, local provider and current subscription
connection, with a separate finite component authority/store. Case IDs, referee
answers and reviewer files never reach selection. Selection, worker and review
claims, original inputs/outputs, route versions, actual model identities and
tokens are retained. A component gate is not a product scheduler gate or proof
that the complete AI4R DAG passed acceptance.

## ChatGPT subscription comparison

After signing in at the existing 5175 app (Settings > Model > ChatGPT comparison
mode), the separate host controller below submits only public MR01 tasks and
inputs to the existing native subscription owner. It never changes the selected
app mode or obtains account credentials. The native owner pins GPT-6.1-Sol,
medium reasoning, fresh contexts, tools disabled, one call per request identity
and a 90-second whole-call deadline. Unknown calls stop collection without replay.
This direct ChatGPT component baseline does not run AI4R's Capsule DAG or its
verifier/gates. Compare raw answers using the same independent reviewer criteria;
do not describe it as a verified app research run.

On Spark, use a **new** output directory:

```sh
python3 deploy/m1/chatgpt_baseline.py prepare \
  --source-plan /home/user2/ai4r-data/benchmarks/local-routing-v1/results/campaign-001/plan.json \
  --output /home/user2/ai4r-data/benchmarks/chatgpt-comparison-new --repeats 3
python3 deploy/m1/chatgpt_baseline.py run \
  --output /home/user2/ai4r-data/benchmarks/chatgpt-comparison-new
```

Add `--variant c01-inference --repeats 1` for one public task. The plan contains
no referee files or expected answers. Results retain model identity, usage,
original text, prompt hashes and call-owned native packets; account/login packets
are excluded. Costs stay unknown. These original public development tasks do not
establish held-out performance or completion of the original MR acceptance suite.

This is the owner-approved adaptation of the ZIP's `mr01-quality` and
`mr02-compatibility` to the deployed Spark pool. The original ZIP, cases,
independent answers and original Harbor integration are unchanged.

| Item | Local protocol |
|---|---|
| Selector | E4B, one bounded selection per worker invocation |
| Executors | E4B, Qwen, Bolt; actual operator-pinned revisions/aliases |
| Fixed comparison / selector-failure fallback | Qwen |
| Independent review | Fixed Qwen; declaration and output only |
| Quality assignment | Unchanged public MR01 task/data and independent exact answers |
| Repetition | Campaign: three; smoke: one, wiring only |
| Expense | Every selection, worker and review call, tokens and elapsed time retained; monetary costs, savings and monetary regret unavailable |
| Scope | Isolated routing component, not admitted-CC, Planner/DAG, frontend, full-pipeline or original-MR acceptance |

The local controller calls the production `prepare_local_choice`,
`AutomaticRouting` selection/continuation logic, `GovernedBridge`,
`ModelSettingsOwner`, native Jiuwen provider and SQLite call-claim store.
It supplies its own explicit **component** binding and finite authority. It
does not invent product admissions, product invocation observations, endpoint
qualification, `model-route` records or app gate records. The original MR
oracles cannot score this different policy/record generation, so a separate
offline local scorer checks original bridge records and the unchanged answers.
The reported component gate is not a claim about the app scheduler's gate.
The inference services are shared. Other callers' contention is not measured;
elapsed times include controller work and review, not just GPU generation.
Treat these development timings as exploratory rather than isolated hardware
performance measurements.

MR01 freezes the public assignment, declaration, execution/review budgets and
model roster. For each domain it runs calibration on each of three models,
fixed Qwen, and routed execution. Calibration originals are frozen before the
fixed/routed arms. Gold answers and calibration scores are never given to E4B
or any worker/reviewer. Three exact passes and Wilson lower bound >= 0.4 mark a
locally qualifying tier; this small development sample proves no broad
reliability. Compare per-domain accuracy before aggregation. Report actual
failures without answer repair, reruns or prompt changes to obtain a pass.

MR02 adapts the five currently applicable controls:

- `context-window`: bind min-context 32768 and enforce a smaller 16384 campaign
  ceiling for E4B. Qwen/Bolt retain their actual configured ceilings. This tests
  exclusion, **not** long-context quality or physical maximum-context discovery.
- `endpoint-unavailable`: a private proxy returns real HTTP 503 for E4B catalog
  requests; the other two real services remain available.
- `router-timeout`: the private E4B proxy delays the selection HTTP request past
  a frozen one-second endpoint deadline; the production bridge chooses Qwen.
- `provider-quota`: the chosen worker's proxy returns real HTTP 429 after route
  selection. Retain the failed attempt; no worker resend or switching.
- `provider-timeout`: the chosen worker's proxy delays its HTTP response past a
  frozen one-second endpoint deadline. The original outcome may remain unknown;
  retain it. No task is forwarded upstream, as captured by the scoped proxy.

`unsupported-tool` and `unsupported-schema` remain **unavailable**, with all
three rows retained: current local Capsule adapters advertise neither a tool
loop nor native schema enforcement. Do not manufacture an eligible endpoint.
The proxy runs only inside the benchmark controller and never stops/reconfigures
shared model services. Bounded delays are contained before another independent
observation; any other unknown effect stops the campaign without automatic
replay. HTTP fault simulation demonstrates controlled disposition, not naturally
occurring provider outage reliability.

## Run on Spark

Use the existing deployed app image; no model download, Harbor installation or
application restart is required. Run from the synchronized repository on Spark:

```sh
cd /home/user2/dev/jiuwenswarm
python3 -m zipfile -e benchmarks/harbor_suite/assets/AI4Research-Benchmark-Cases-2026-10-26.zip /home/user2/ai4r-data/benchmark-assets

python3 deploy/m1/local_routing_benchmark.py \
  --profile /home/user2/ai4r-data/operator.json \
  --root /home/user2/ai4r-data/benchmarks/local-routing-v1 \
  prepare --workspace mr-local-001 --mode campaign \
  --cases-root /home/user2/ai4r-data/benchmark-assets/AI4Research-Benchmark-Cases-2026-10-26/cases
```

Add `--case mr01-quality --variant c02-retrieval --mode smoke` for a small
wiring run instead. Never overwrite a prepared workspace or reuse it as a new
attempt. Keep the same controller/production source snapshot for its lifetime.

```sh
python3 deploy/m1/local_routing_benchmark.py --profile /home/user2/ai4r-data/operator.json --root /home/user2/ai4r-data/benchmarks/local-routing-v1 doctor --workspace mr-local-001
python3 deploy/m1/local_routing_benchmark.py --profile /home/user2/ai4r-data/operator.json --root /home/user2/ai4r-data/benchmarks/local-routing-v1 run --workspace mr-local-001
python3 deploy/m1/local_routing_benchmark.py --profile /home/user2/ai4r-data/operator.json --root /home/user2/ai4r-data/benchmarks/local-routing-v1 status --workspace mr-local-001
python3 deploy/m1/local_routing_benchmark.py --profile /home/user2/ai4r-data/operator.json --root /home/user2/ai4r-data/benchmarks/local-routing-v1 score --workspace mr-local-001
```

`run` starts one detached, bounded Docker controller, so closing the SSH terminal
does not stop it. Check `status`; scoring is offline and makes no inference
requests. Repeating `run` cannot replace its container or exclusive launch claim.
An interrupted/unknown campaign requires inspection of its original records,
not deletion of the claim or replay under another name to conceal a failure.

The launcher stages an immutable small controller snapshot. It uses the exact
core files in that snapshot **only inside the benchmark container**; the running
app and its build qualification are untouched. `deployment.json` records app
image, inference images and model revisions. The plan records base commit,
source hashes, public fixture hashes, limits and model aliases. Its commit is
explicitly not a clean-commit claim when source overlays differ.

Reviewer files are in a separate sibling `*-reviewer` directory. The inference
container never mounts it, the source case tree, application state, accounts,
credentials, Docker socket or the original ZIP. The scorer has no network.
It independently checks original byte hashes, call/route joins, effective model
identity, complete claims/calls, and exact answers. Missing observations remain
in the scheduled denominator. Raw evidence stays on Spark under the selected
data root; the launcher creates no Windows/C: caches. Controller logs/tmp are
bounded and separate from the shared models' resources.

For the current hybrid component campaign, use the same public source plan and
a fresh output folder:

```sh
python3 deploy/m1/chatgpt_baseline.py prepare --arm hybrid \
  --source-plan /home/user2/ai4r-data/benchmarks/local-routing-v1/results/campaign-001/plan.json \
  --output /home/user2/ai4r-data/benchmarks/hybrid-comparison-new --repeats 3
python3 deploy/m1/chatgpt_baseline.py run \
  --output /home/user2/ai4r-data/benchmarks/hybrid-comparison-new
```

The controller waits for native subscription readiness before claiming inference,
keeps its exact source beside the plan, and retains unknown deliveries without
replay. Compare worker exact-answer scores separately from verifier/gate acceptance.
A rejected correct answer must not be counted as successfully delivered.
