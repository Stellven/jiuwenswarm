# AI4R local model pool on one DGX Spark

## Current pool generation 3 — 27 October 2026

The active selection is `spark-pool-v3.json`: gpt-oss-20b MXFP4 (12.11 GB),
Nemotron 3.5 Lightning 30B-A3B Q4_0 (18.90 GB), and gpt-oss-120b MXFP4
(63.39 GB). Each service has one slot and a 16K context. Container memory
ceilings are 20/24/67 GiB; these are limits, not measured peaks. All three
completed the eight public MR01 development assignments correctly once.
Qwen scored 4/8 in the same qualification and was replaced; this small,
development-set observation does not establish general model superiority.

Automatic policy `ai4r-hybrid-bounded-routing:8` uses gpt-oss-20b as assessor
and as a separate declaration/output-only verifier. It may also execute work.
Critical task risks require subscription GPT-6.1-Sol before dispatch. Other
work is selected among compatible candidates under protected budgets. The
fixed-worker reference `ai4r-chatgpt-fixed-reference:3` uses ChatGPT inside
AI4R, with the same verifier, structural check and gate. Historical manual
ChatGPT and direct-transport benchmark results retain their original meanings.

The selector has an actual frozen ceiling of 1,024 output tokens and 30 seconds,
inside the node's worker time envelope. Its request asks for no reasoning;
the current llama.cpp model may still generate reasoning, which is included
in recorded usage. Worker reasoning remains enabled. Verifier budget is
separate and cannot be borrowed. Selector failures are recorded; a compatible
ChatGPT fallback before worker dispatch is not counted as a successful local
selection. No model-call replay or forced gate acceptance is allowed.

Services are shared without API keys at `http://100.105.127.48:8012/v1`
(20b), `:8011/v1` (Lightning) and `:8013/v1` (120b), subject to tailnet access.
They also bind host loopback. They do not bind the public interface. The app
remains the single existing UI on 5175; Windows caches stay on D and weights
stay on Spark. Old pool weights and the v5 checkpoint remain recoverable.

## Historical replacement generation 2 — 27 October 2026

The current approved replacement is pinned in `spark-pool-v2.json`: Qwen3.8-27B
Q4_K_M (18.97 GB), Nemotron 3.5 Lightning 30B-A3B Q4_0 (18.90 GB), and
gpt-oss-120b MXFP4 (63.39 GB). These are roughly 94.3 GiB of weights total,
not measured runtime peaks. Each has one slot and a 16K context; memory limits
are 25/24/67 GiB. The model files are downloaded and verified on Spark only.
The v2 services use the existing pinned ARM64 llama.cpp CUDA image, with bounded
reasoning and batch sizes. Share addresses remain loopback and Tailscale only.

Automatic v6 routing includes all three and subscription GPT-6.1-Sol. Settings
also exposes **ChatGPT 6.1 Sol · fixed worker in AI4R**, using the same Qwen
verifier/check/gate as automatic routing. The older manual ChatGPT model choice
is retained separately. The original direct-ChatGPT benchmark is historical,
not the new matched reference. Critical or uncertain work must not downgrade
to a weaker model when the required tier or budget is unavailable.

For an idle existing v1 deployment, the operator supports explicit migration:

```bash
python3 deploy/m1/ai4r.py --profile /home/user2/ai4r-data/operator.json \
  local-pool migrate --data-root /home/user2/ai4r-data/inference-v2 \
  --share-address 100.105.127.48
python3 deploy/m1/ai4r.py --profile /home/user2/ai4r-data/operator.json local-pool prepare
```

Migration retains old pool pins and weights. Replacing a running app image
still requires the existing idle-upgrade procedure; these commands do not
bypass it. Do not prune checkpoint image tags or stop other users' services.
The models must be observed healthy and complete actual tasks before calling
the replacement qualified. The historical v1 setup below is retained as a
deployment reference, not a claim that the new models are already qualified.

## Historical pool v1

This configures the existing AI4R app and operator, with its single web endpoint
on **5175**. It does not create a second chat app. No commercial API key is used.
ChatGPT sign-in remains a separate, manually selected comparison mode.

| Service | Role | Runtime | Initial limits |
| --- | --- | --- | --- |
| Nemotron 3.5 Bolt E4B Q4_K_M | Router and executor | llama.cpp CUDA 13 | 12 GiB container, 64K context, concurrency 1 |
| Qwen3.8-27B FP8 | Executor and fixed independent verifier | NVIDIA vLLM 26.09 | 48 GiB container, 0.36 GPU memory utilization, 64K context, concurrency 1 |
| Nemotron 3.5 Bolt 74B-A9B official 24GB GGUF | Larger executor | llama.cpp CUDA 13 | 36 GiB container, 64K context, concurrency 1 |

These are starting resource budgets, not measured peak-memory guarantees. CUDA
allocations on unified memory need confirmation on the actual host. The three
services receive a startup headroom check based on unloaded weight file sizes
and Qwen's configured vLLM reservation. It refuses clearly insufficient memory
without stopping other workloads; it does not certify peak runtime usage. The
services share the app's private Docker network; scientific jobs and the runner
receive no model config mount. Shared inference also binds host loopback and the
explicit Tailscale address, never the public network. E4B and
Qwen must be ready before an automatic run can start. An unavailable Bolt is
excluded before the run pool is frozen. Context filtering can explicitly block
inputs that exceed these bounded services; inputs are never silently truncated.

## Connect the workstation

Install Tailscale on Windows and sign in to the same tailnet as Spark. On the
Spark itself, enable Tailscale SSH with `tailscale set --ssh`; the tailnet policy
must permit the connection and the chosen Linux user. This command does not
install Tailscale on Windows. Use the Spark's actual Linux username when it
differs from the workstation username.

Keep Windows operator profiles, temporary files and downloads on D:

```powershell
New-Item -ItemType Directory -Force D:\ai4r-cache\tmp | Out-Null
$env:TEMP = 'D:\ai4r-cache\tmp'
$env:TMP = $env:TEMP
$env:PYTHONDONTWRITEBYTECODE = '1'
& 'D:\Apps\Tailscale\tailscale.exe' status
ssh YOUR_SPARK_USER@100.105.127.48
```

Windows Installer keeps its own system metadata/cache even when the Tailscale
program and downloaded installer are placed on D. No model weights belong on
the Windows workstation.

## Configure and prepare on Spark

Prerequisites: the current checkout containing this feature, Docker/Compose/
Buildx, NVIDIA Container Toolkit and a compatible NVIDIA driver. The Spark
operator must have Docker access and a writable dedicated data directory. Use
the actual designated data mount in place of `/data/ai4r`. Do not run another
deployment on the same host's 5175; stop the old idle deployment through its
existing operator first, retaining its state volumes.

For a new deployment, from the checkout on Spark:

```bash
export TMPDIR=/data/ai4r/tmp
mkdir -p "$TMPDIR"
export PYTHONDONTWRITEBYTECODE=1
PROFILE=/data/ai4r/operator.json
python3 deploy/m1/ai4r.py --profile "$PROFILE" setup \
  --project ai4r-spark --platform linux/arm64 \
  --root /data/ai4r/deployment --output /data/ai4r/results
python3 deploy/m1/ai4r.py --profile "$PROFILE" local-pool configure \
  --data-root /data/ai4r/inference --share-address 100.105.127.48
python3 deploy/m1/ai4r.py --profile "$PROFILE" local-pool weights
mkdir -p /data/ai4r/builds
python3 deploy/m1/ai4r.py --profile "$PROFILE" build \
  --output "/data/ai4r/builds/$(date +%Y%m%dT%H%M%S)"
python3 deploy/m1/ai4r.py --profile "$PROFILE" local-pool prepare
python3 deploy/m1/ai4r.py --profile "$PROFILE" start
python3 deploy/m1/ai4r.py --profile "$PROFILE" logs --service ai4r
```

`configure` checks ARM64/128GB/GB10 and pins official Hugging Face revisions.
`weights` downloads the pinned public files directly on Spark without Docker or
GPU allocation. It verifies upstream SHA-256/Git blob hashes and resumes partial
downloads; final files are published only after validation. Download storage
preserves 20% filesystem headroom and at least 20 GiB. `prepare` also performs
this step if it has not been run separately. It requires 20 GiB runtime space at
the data root and 80 GiB free at Docker's image store, pulls the pinned runtime
tags and resolves their immutable image IDs. Existing valid weight files are
retained; it never prunes unrelated Docker resources or caches. First startup
may take time for downloads and kernel compilation. Weight files live under
`inference/models`; Hugging Face, vLLM, Triton, FlashInfer and temporary caches
live under `inference/cache`. `inference/pool.json` records the prepared pins.
No weights are downloaded by `configure`, by the Windows client or by chat.
For a fresh deployment without Docker permission yet, `setup`, `local-pool
configure` and `local-pool weights` can be run first on Spark. All models still
run on that single Spark; downloading first does not split the deployment.

The operator generates the services in its existing `compose.json`, mounts a
root-owned read-only endpoint configuration into AI4R and preserves these
services on subsequent starts. Model image/layer storage remains Docker-managed.
When using an already initialized app, use the existing app upgrade procedure;
the operator does not bypass its image-change guard or discard account data.

## Use the same chat over Tailscale

### Shared model access for other users

The model services are shared with all Spark OS users through loopback and with
users permitted by the existing Tailscale network policy through the explicitly
configured Tailscale address. No commercial API key or AI4R app account is needed
for these inference APIs. Do not publish them on a public interface.

| Model | Spark-local base URL | Tailscale base URL |
| --- | --- | --- |
| Nemotron Lightning | `http://127.0.0.1:8011/v1` | `http://100.105.127.48:8011/v1` |
| gpt-oss-20b | `http://127.0.0.1:8012/v1` | `http://100.105.127.48:8012/v1` |
| gpt-oss-120b | `http://127.0.0.1:8013/v1` | `http://100.105.127.48:8013/v1` |

Call `GET /models` on the chosen base URL to discover its exact pinned model ID,
then use that ID with `POST /chat/completions`. The models retain their bounded
context and concurrency when shared; other users' requests can increase queue
time. An AI4R `stop` stops only the app and optional runner and leaves these shared
model services running. App initialization recreates only the app container.
The operator does not change tailnet permissions; remote users must already have
network access to the Spark and these ports under the administrator's policy.

### AI4R chat

From Windows, keep this forwarding terminal open:

```powershell
ssh -N -o ExitOnForwardFailure=yes -L 5175:127.0.0.1:5175 YOUR_SPARK_USER@100.105.127.48
```

Open the complete private bootstrap URL from the app log yourself at
`http://127.0.0.1:5175`. In Settings → Model, save **AI4R · automatic model routing**
and refresh until the local services are connected. Sign in with ChatGPT for
the protected critical-task tier. The fixed-worker AI4R reference also requires
this sign-in; it does not require a commercial API key.
Upload a document and send a request in the existing composer. The existing
Compiler, Planner CC, task CCs, deterministic checks, verifiers, gates and
Delivery retain their roles. A selector never replaces that workflow.
Each Capsule invocation selects at most once. Builder's internal turns keep the
same executor; the next Capsule makes an independent choice. Local readiness
does not require ChatGPT authentication or subscription-model discovery.

The model menu shows connection status, not proof of inference quality. A real
completed task and its captured route decisions are still necessary to establish
end-to-end deployment. Component benchmark results are not full-DAG acceptance.

Sources: [Tailscale SSH](https://tailscale.com/docs/features/tailscale-ssh),
[llama.cpp ARM64 CUDA images](https://github.com/ggml-org/llama.cpp/blob/master/docs/docker.md),
[NVIDIA vLLM 26.09](https://docs.nvidia.com/deeplearning/frameworks/vllm-release-notes/rel-26-09.html),
[E4B weights](https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Bolt-E4B-4GB),
[Qwen FP8 weights](https://huggingface.co/Qwen/Qwen3.8-27B-FP8),
[Bolt GGUF weights](https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Bolt-74B-A9B-24GB-GGUF).
