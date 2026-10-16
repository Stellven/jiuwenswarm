# Model catalog and qualification inventory

`Tier 2 · Part of: [Side systems](README.md)`

The model-routing owner maintains deployment qualification and catalog evidence. The [router](router-design.md) consumes this metadata under a protected [selection profile](../reference/model-routing-contract.md#model-selection-profile).

## Qualification inventory

The qualification inventory contains 24 entries: 12 executor deployments or families (`E`) and 12 typed learned-tool methods (`T`). They are arranged by eight CS/ML task categories, with shared candidates counted once. This is a design shortlist, not enabled services, verified present availability or measured quality. The pilot prioritizes five executor routes plus document and retrieval tools required by admitted cases; reserves remain conditional. Exact endpoint, revision, licence, access, resources and task evidence must be qualified before activation. Deterministic tools and reference checkers are not model entries.

### C01: ML Methods and Inference

`task_category=ml_methods_and_inference`. Compare bounded ML/inference methods, representation quality and resource trade-offs. Image/segmentation tools apply only to an admitted ML method study.

| Kind | Internal ID / status | API/checkpoint/artifact identity to qualify | Task contract and qualification boundary |
|---|---|---|---|
| `E` | `qwen.multimodal4b` | `Qwen/Qwen3.5-4B` | Compact text/image technical node work and bounded code, Apache-2.0. Requires qualified locally served API/parser; 4B does not prove a full pipeline fits available host memory |
| `T` | `vision.dinov2small` / conditional | `facebook/dinov2-small`, Apache-2.0 | Bounded ML representation/inference experiments; outputs features, not automatically classification/detection labels. Any fitted head and evaluation split are separate pins |
| `T` | `vision.sam21tiny` / conditional | `facebook/sam2.1-hiera-tiny`, Apache-2.0 | Prompted image/video segmentation as an ML method study; qualify resolution/frame/batch/CPU versus GPU paths separately |

Shared executors: `openai.economy` and `openai.general` for bounded/general node work, `gemini.research` for technical multimodal inputs, and code routes from C04 for experimental kernels. The telemetry methods in C08 may support a declared inference-system study.

### C02: Retrieval and Knowledge Systems

`task_category=retrieval_and_knowledge_systems`. Technical evidence extraction, retrieval/RAG, corpus/index updates, relevance ranking and grounded synthesis.

| Kind | Internal ID / status | API/checkpoint/artifact identity to qualify | Task contract and qualification boundary |
|---|---|---|---|
| `E` | `openai.economy` | `gpt-6-luna` | Low-cost API comparison for bounded technical extraction, structured node work and local reasoning/code. Published lower tariffs do not establish lower complete-task cost or sufficient quality |
| `E` | `glm.general` | `glm-5` | Chinese/English CS/ML evidence and tool-assisted implementation comparator; region, endpoint, revision and tool/schema capability require verification; not a compact tier merely by label |
| `T` | `evidence.docling258m` | `ibm-granite/granite-docling-258M`, Apache-2.0 | Technical document structure/DocTags, formulas/tables/code; page/bbox/source provenance and independent numeric checks; qualify full CPU pipeline |
| `T` | `evidence.paddleocr09b` | `PaddlePaddle/PaddleOCR-VL-1.6`, Apache-2.0 | Multilingual technical-document parsing; separately pin layout/element/full-page pipeline. Named parameter scale is not a measured memory guarantee |
| `T` | `evidence.bgem3` | `BAAI/bge-m3`, MIT | Dense/sparse/multivector retrieval; pin corpus, chunks, tokenizer/index and scoring settings. Relevance never certifies a claim's truth |
| `T` | `evidence.qwenrerank06b` | `Qwen/Qwen3-Reranker-0.6B`, Apache-2.0 | Typed query/passage relevance scores; exact prompt and score extraction; not a general executor or factual oracle |
| `T` | `evidence.qwenembed06b` | `Qwen/Qwen3-Embedding-0.6B`, Apache-2.0 | Technical literature/code retrieval comparison; freeze instruction/pooling/dimension. Compare against BGE on held-out IR cases before choosing a pilot default |

Shared executors: `qwen.multimodal4b` and `openai.general` for matching extraction/synthesis contracts; C04 code routes for retrieval/index implementation. Embedding/reranking scores do not replace independent factual/citation checks.

### C03: Algorithms, Optimization and Formal Methods

`task_category=algorithms_optimization_and_formal`. Algorithm/optimization reasoning and controlled formal proof obligations in CS/ML research.

| Kind | Internal ID / status | API/checkpoint/artifact identity to qualify | Task contract and qualification boundary |
|---|---|---|---|
| `E` | `deepseek.reasoning` | `deepseek-v4-pro` | Algorithms/optimization and difficult CS/ML interpretation; qualify the documented adapter and exact served version, not an assumed old Responses contract or retired alias |
| `E` | `math.kimina17b` / conditional | `AI-MO/Kimina-Prover-RL-1.7B` | Fixed CS/ML Lean theorem obligations, Apache-2.0; exact statement equivalence, Lean/Mathlib pins, kernel acceptance and no admitted obligations. Only activate if an admitted case needs this method |
| `E` | `math.goedel8b` / reserve | `Goedel-LM/Goedel-Prover-V2-8B` | Harder CS/ML formal obligations, Apache-2.0; same controlled proof contract as the compact formal route, with version-compatible Lean/reference environment |

Shared executors: `qwen.code30b`, `code.opencodereasoning7b` and `openai.general` for algorithm implementations/reasoning. Formal rows require an actually admitted proof method and pinned independent Lean/kernel checks.

### C04: Software Systems and Performance

`task_category=software_systems_and_performance`. Research POC, multi-file experimental software, systems/runtime/compiler kernels and reproducible performance comparisons.

| Kind | Internal ID / status | API/checkpoint/artifact identity to qualify | Task contract and qualification boundary |
|---|---|---|---|
| `E` | `qwen.code30b` | `Qwen/Qwen3-Coder-30B-A3B-Instruct` | Research POC, repositories and multi-file experiments, Apache-2.0. About 30.5B total/3.3B active is not a 3.3B weight-memory footprint; qualify GB10/local API or an approved exact hosted deployment |
| `E` | `code.devstral24b` / local reserve | `mistralai/Devstral-Small-2-24B-Instruct-2512` | Multi-file research software, Apache-2.0. The managed Small 2 API ID is deprecated; only the open checkpoint is a conditional local-service candidate, with runtime/precision/architecture checked |
| `E` | `code.opencodereasoning7b` / reserve | `nvidia/OpenCodeReasoning-Nemotron-1.1-7B` | Algorithm kernels for scheduling/indexing/ML experiments; NVIDIA Open Model License must be approved for the intended use. Competition results do not qualify agentic repository work or native tools |

Shared executors: `openai.general` and `anthropic.fable5` for demanding research implementation/synthesis; `openai.economy` and `qwen.multimodal4b` for bounded subtasks when qualified. These models also support implementation obligations in C01/C02/C05/C06/C07/C08.

### C05: Databases and Data Processing

`task_category=databases_and_data_processing`. Query/index strategy, transactional/streaming behavior and data-pipeline experiments reuse the catalog definitions already listed above; no extra database-specialist model is introduced.

This category has no additional unique catalog entry. The shared candidates below are part of the same 24-entry pool.

Shared executors: `qwen.code30b`, `code.opencodereasoning7b` and qualified `code.devstral24b` for experimental code; `openai.economy` and `qwen.multimodal4b` for bounded technical extraction; `openai.general` for reasoning/evaluation. Use pinned reference DB/query results, controlled workloads, integrity/arithmetic and budget checks.

### C06: Networking and Distributed Algorithms

`task_category=networking_and_distributed_algorithms`. Research network protocols/workloads and typed performance-prediction surrogates under bounded single-host simulation or captured measurements.

| Kind | Internal ID / status | API/checkpoint/artifact identity to qualify | Task contract and qualification boundary |
|---|---|---|---|
| `T` | `network.routenet_fermi` / conditional | RouteNet-Fermi released experiment checkpoints, Apache-2.0 | Topology/routing/traffic/scheduling to delay/jitter/loss; pin metric-specific checkpoint/data conventions. Legacy dependency stack must pass actual-host readiness |
| `T` | `network.routenet_gauss` / conditional | RouteNet-Gauss, Apache-2.0 | Network-performance GNN surrogate; pin released weights plus normalization and graph limits; validate against independent simulation/measurements |

Shared executors: C04 code routes, `deepseek.reasoning` and `openai.general` for protocol/algorithm implementation and analysis. C08 forecasting methods may apply to technical-network telemetry only. Learned surrogates remain distinct from independent reference simulation/measurements.

### C07: Security and Reliability

`task_category=security_and_reliability`. Research program analysis, robustness/fuzzing, isolation/integrity and safe failure behavior through qualified shared code/general models.

This category has no additional unique catalog entry. The shared candidates below are part of the same 24-entry pool.

Shared executors: `qwen.code30b`, `code.opencodereasoning7b`, qualified `code.devstral24b` and `openai.general`. Their independently owned producer/verifier scopes and planted-defect/boundary tests determine qualification; no unmeasured dedicated security model is added to fill the category.

### C08: Experimental Evaluation and Technical Data

`task_category=experimental_evaluation_and_technical_data`. Research synthesis/evaluation, technical figures/tables, uncertainty and technical-system telemetry. Cross-category general executors are defined here once; the fixed baseline remains available across categories only when compatible.

| Kind | Internal ID / status | API/checkpoint/artifact identity to qualify | Task contract and qualification boundary |
|---|---|---|---|
| `E` | `openai.general` | `gpt-6.1-sol` | Exact requested fixed benchmark baseline, complex technical reasoning/code/synthesis and compatible baseline fallback. Qualify Responses tool contract; preserve native Codex CLI boundary separately |
| `E` | `anthropic.fable5` | `claude-fable-5` | Long technical synthesis and demanding research implementation; exact legacy identity/settings, tool/thinking rules and access are pinned; no silent upgrade to another Fable version |
| `E` | `gemini.research` | `gemini-3.8-flash` | Technical figures/documents/multimodal evidence and synthesis; qualify actual modalities, serialization and tools on bounded CS/ML inputs |
| `T` | `statistics.chronos2` | `amazon/chronos-2`, Apache-2.0 | Technical-system/network/inference telemetry forecasting; CPU/GPU paths need actual qualification; chronological split and covariate/target availability enforced |
| `T` | `statistics.timesfm` | `google/timesfm-2.5-200m-pytorch`, Apache-2.0 | Technical telemetry forecasting comparator; use this exact 2.5 checkpoint, not an unapproved later noncommercial variant; normalization/horizons/quantiles pinned |
| `T` | `statistics.moment` / reserve; repin small | `AutonLab/MOMENT-1-small`, MIT | Telemetry reconstruction/imputation/embeddings; task heads may need fitting and separate qualification. No blanket zero-shot anomaly-detection claim |

Shared candidates: `openai.economy` and `qwen.multimodal4b` for qualified bounded evaluation/extraction; C02 evidence tools for technical documents; C01 vision methods for bounded ML studies; C04 code routes for experimental aggregation. Telemetry methods retain their technical-system, network and inference scope.
## Qualification states

Each entry moves through `source_reviewed`, `access_verified`, `contract_qualified`, `development_profiled` and `benchmark_profile_frozen`. Disabled, blocked and retired states also exist. Enabling needs the exact account or service, adapter, settings, licence, resources and verification evidence. A changed model, precision, parser, head, tool or schema invalidates the affected evidence. Unknown, stale or out-of-scope evidence stays visible.

## Catalog entries and refresh

The routing owner pins the catalog, capability-verification and pricing revisions used by each decision, and maintains the exact deployment identity, verified capabilities, access state, data policy and pricing basis in protected catalog records. Registration does not activate an endpoint. A typed tool method is never an executor candidate and never the router alternate model. Approved updates apply to new executions, and revocation is rechecked before each call. M1 trains no online router and activates no new model automatically.

## API provider entry

`Standard`. M1 needs the Codex route only, and that route is not a provider entry (it uses the local IPC in the app container). The API router needs one entry per API provider. The routing owner fills these entries in protected router configuration. The package defines their shape and one rule: **a credential value never appears in a declaration, a catalog record, a route record, an export or a log**. Only the name of the environment variable appears. The value comes from the protected env file that Compose mounts into the app container ([platform](../platform/README.md#container-startup-ipc-and-storage-obligations)).

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `provider_id` | `string` | yes | pattern `^[a-z][a-z0-9_.-]{0,63}$`, unique | Identity of the provider entry |
| `base_url` | `string` | yes | `https` URL, no credential inside it | Endpoint the adapter calls |
| `models` | `object[]` | yes | 1 or more, each `{model_id, provider_model_name}` | The deployments this provider serves. `model_id` is the catalog ID. `provider_model_name` is the name sent to the provider. |
| `credential_env_var` | `string` | yes | pattern `^[A-Z][A-Z0-9_]{0,63}$` | Name of the environment variable that holds the key. Unset or empty means the credential does not resolve (`auth_failed`). |
| `timeout_s` | `number` | yes | 1 to 600 | Time limit of one call to this provider. The call's own time limit still applies when it is shorter. |
| `enabled` | `boolean` | yes | default false | Registration does not activate an endpoint. The routing owner sets it after the capability checks. |

Until the routing owner supplies real entries, the router runs against mocked endpoints and every real provider stays disabled. Adding real entries is the routing owner's decision and never blocks M1.

## Registry and development evidence

A registry entry identifies an exact deployment configuration: `model_id + provider + provider_model_name/checkpoint + endpoint_ref + adapter_id + revision`. Local and hosted copies, quantizations, tool parsers, reasoning settings and different served versions are distinct configurations when they change behavior/cost; avoid duplicate entries with no measured purpose. Keys remain in the credential system.

| Record / fields | Required meaning |
|---|---|
| Identity and access | Stable `model_id`, exact API/checkpoint, provider, endpoint/adapter/configuration revision, credential reference, license status, `access_mode` and enabled/current availability |
| Declared versus verified capability | Modalities, context/output limits, tool/action grammar, structured-output mode, tokenizer and supported parameter settings; endpoint-specific dated verification and effective limits |
| CS/ML scope | Nonexclusive `task_categories`, method/contract compatibility, permitted producer/verifier profile scopes; category labels do not certify performance |
| Runtime state | Actual enable/disable/access outcome, credential-scoped limits when available, sourced provider observations with endpoint/time scope; unknown quota/status is not invented |
| `DevelopmentQualityCostProfile` | Task category, exact Capsule/method contract, deployment/settings, language/input/context/tool stratum, development split/version, oracle eligibility, sample/repeat counts, pass/quality estimate and uncertainty, complete expected call/latency/cost basis |
| Profile validity | Pin measured scope, quality floor, uncertainty rule, freshness/version and supported resource envelope; requalify changed model/adapter/contract/prompt/tool configuration |
| Audit provenance | Requested/effective identity and its basis; provider/local/unavailable usage; actual tariff/pricing revision versus explicitly modeled estimates |

`resource_tier` (model/deployment size), monetary class, and measured task quality remain distinct. A small model may qualify for a difficult bounded contract; a frontier brand cannot automatically qualify. Public model-card/paper results are `advisory_evidence`, confined to the actual checkpoint, dataset and attempt budget. They are not this benchmark's pass rates, item difficulty or cost tiers.

Three readiness levels prevent confusion:
1. **Source-qualified**: official identity/artifact/license/method has been inspected; actual account/service access and capability fit may still be unknown.
2. **Runtime-qualified**: the exact endpoint/adapter passes required callability/capability, permissions and host checks; provisional compatibility/fault tests may use it.
3. **Benchmark-ready**: fixtures/oracles and selector are frozen, real repeated RT06 calibration is complete for the scored items, and quality/cost measurements have adequate provenance. Unresolved items remain in outcomes; their difficulty/regret are unavailable.

Unknown internal quality does not require invented scores or block a basic integration probe. It **does** prevent claiming measured cheap-tier qualification, routing savings, difficulty or regret without the required real calibration. The runtime receives frozen **development aggregate** profiles only; a held-out per-item tier/cost ledger is protected referee data.

For the API branch, a metadata listing/HTTP 200 is not inference verification. Verify tools, native structured output when required, modality and context limits independently. For the native Codex branch, qualify its adapter/configuration and telemetry separately. Account subscription/credit observations are not per-model remaining quota or per-call price.
