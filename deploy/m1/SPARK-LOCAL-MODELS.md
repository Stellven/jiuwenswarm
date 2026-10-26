# AI4R local model pool on one DGX Spark

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
| E4B | `http://127.0.0.1:8011/v1` | `http://100.105.127.48:8011/v1` |
| Qwen | `http://127.0.0.1:8012/v1` | `http://100.105.127.48:8012/v1` |
| Bolt | `http://127.0.0.1:8013/v1` | `http://100.105.127.48:8013/v1` |

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
`http://127.0.0.1:5175`. In Settings → Model, save **AI4R local automatic** and
refresh until E4B and Qwen are ready. No ChatGPT login is required in this mode.
Upload a document and send a request in the existing composer. The existing
Compiler, Planner CC, task CCs, deterministic checks, verifiers, gates and
Delivery retain their roles. A selector never replaces that workflow.
Each Capsule invocation selects at most once. Builder's internal turns keep the
same executor; the next Capsule makes an independent choice. Local readiness
does not require ChatGPT authentication or subscription-model discovery.

The model menu shows connection status, not proof of inference quality. A real
completed task and its captured route decisions are still necessary to establish
end-to-end deployment. No successful Spark run is claimed by this guide.

Sources: [Tailscale SSH](https://tailscale.com/docs/features/tailscale-ssh),
[llama.cpp ARM64 CUDA images](https://github.com/ggml-org/llama.cpp/blob/master/docs/docker.md),
[NVIDIA vLLM 26.09](https://docs.nvidia.com/deeplearning/frameworks/vllm-release-notes/rel-26-09.html),
[E4B weights](https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Bolt-E4B-4GB),
[Qwen FP8 weights](https://huggingface.co/Qwen/Qwen3.8-27B-FP8),
[Bolt GGUF weights](https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Bolt-74B-A9B-24GB-GGUF).
