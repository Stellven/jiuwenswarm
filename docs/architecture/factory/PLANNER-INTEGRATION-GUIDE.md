# Instructions for the Software Factory Frontend & E2E Integration AI Agent

## 1. Repository & Branch

- **Repository**: `https://github.com/Stellven/jiuwenswarm.git`
- **Target Branch**: `M2planner` — [https://github.com/Stellven/jiuwenswarm/tree/M2planner](https://github.com/Stellven/jiuwenswarm/tree/M2planner)
- **Verified Implementation Commit SHA**: `64fc2f366be125f07544e5f80a03f6f38855ed14`

> **Boundary Contract**: The Planner subsystem strictly stops at producing verified standard JSON deliverables (`graph.json` as the sole user-facing downloadable output, backed by `contract.json`, `plan.json`, `task.json`, `verification.json`, and `derivation.json`). Downstream execution modules (`controller.py`, `planner.py`, `scheduler.py`, `node_check.py`, `schemas/task.schema.json`) remain untouched on the `M2` baseline (`HEAD`), aside from `node_contract.py` / `node_check.py` retaining `evidence` output capsule verifier support required by the CC Work Library.

---

## 2. Where the Planner Sits in the Software Factory

```text
Upstream TaskInput (factory.task-input/1)
  │
  ▼
[1] Host Context & Full CC Library (plan_select.context + plan_catalog.prompt_view)
  │   - Hard filters (H1-H4), soft features (F1-F4), hardware risks, interference, M1/M2/M3
  │   - Full Capability Capsules catalog (56 cc.yaml manifests / 64 atlas-names entries)
  ▼
[2] Governed LLM Turn (ai_planner.codex_invoke -> Plan IR factory.plan-ir/1)
  │   - Autonomously selects capsules + designs TaskGraph `steps` & bound CCs (up to 3 rounds)
  ▼
[3] Deterministic Compiler (plan_compile.compile_plan -> factory.node-contracts/1 + factory.plan/1)
  │
  ▼
[4] Bridged Static Gate (plan_checks.run + m1_verifier_bridge.run_m1_plan_checks)
  │   - M1 binding.plan_checks + M2 8 semantic rules + node_contract.problems + planner.check_plan
  ▼
[5] Internal Formal Proof Gate (tla_graph.render_graph_tla -> tla_check.check_graph_tla)
  │   - 2-pass Java TLC (`tla2tools.jar`) + load-time `ASSUME` invariants (zero `.tla` leaked externally)
  ▼
[6] Init Gate (planner.plan_for_task -> seeded factory.taskgraph/1) & Verified JSON Deliverables
  │   - User-facing sole downloadable deliverable: `graph.json`
  │   - Downstream runtime bundle: `task.json` -> `contract.json` + `plan.json`
  ▼
Downstream Factory Execution (untouched `controller.init_task` -> `scheduler` -> `node_check` -> `lab_manager`)
```

---

## 3. System Components & Exact File Map

### 3.1 CC Work Library (Preserved in Full)
- Catalog root: `jiuwenswarm/factory/ccs/` (`56` `*/cc.yaml` capsule directories; `64` entries in `jiuwenswarm/factory/ccs/atlas-names.json`, plus `jiuwenswarm/factory/ccs/migration.json`, including `expert_scale_wiring/`, `muse_nvfp4_reader/`, `weight_pack_compiler/`).
- Catalog loader & prompt serializer: `jiuwenswarm/factory/plan_catalog.py` (`load()`, `capability()`, `is_verifier()`, `prompt_view()`).
- Associated contracts/prompts: `jiuwenswarm/factory/contracts/muse-q2-ttft-v2.json`, `jiuwenswarm/factory/tasks/muse-q2-ttft.json`, `jiuwenswarm/factory/tasks/muse-q2-ttft.plan.json`, `ops/spark/prompts/muse/`.
- Capsule UI browser & model: `jiuwenswarm/channels/web/frontend/src/features/factoryRuns/cc/` (`CapsulesPage.tsx`, `capsuleApi.ts`, `capsuleModel.ts`, `CapsuleChips.tsx`, `CapsuleEvidence.tsx`, `CapsuleMaterial.tsx`, `AnalysisData.tsx`, `atlasNames.ts`, `navigation.ts`).

### 3.2 Planner Core & Internal TLA+/TLC Prover
- Schema & Requirements: `jiuwenswarm/factory/schemas/requirements-1.schema.json`, `jiuwenswarm/factory/requirements.py`, `jiuwenswarm/factory/requirements/star-deepseek-v2.json`, `jiuwenswarm/factory/requirements/muse-q2-ttft-v2.json`.
- Selection & IR: `jiuwenswarm/factory/plan_select.py` (`context()`), `jiuwenswarm/factory/plan_ir.py` (`FORMAT = 'factory.plan-ir/1'`, `problems()`).
- Compiler & Static Checks: `jiuwenswarm/factory/plan_compile.py` (`compile_plan()`), `jiuwenswarm/factory/plan_checks.py` (`run()`, `run_detailed()`), `jiuwenswarm/factory/m1_verifier_bridge.py` (`run_m1_plan_checks()`).
- Internal TLA+/TLC Prover: `jiuwenswarm/factory/tla/TaskGraphExec.tla`, `jiuwenswarm/factory/tla_check.py` (`tools()`, `execution_model()`, `check()`, `check_graph_tla()`, `parse_trace()`), `jiuwenswarm/factory/tla_graph.py` (`render_graph_tla()`, `parse_taskgraph_tla()`, `load_taskgraph()`).
- Orchestrator: `jiuwenswarm/factory/ai_planner.py` (`build_prompt()`, `parse_reply()`, `evaluate()`, `synthesize()`, `replay()`, `graph_preview()`).

### 3.3 HTTP API Gateway
- `jiuwenswarm/gateway/channel_manager/web/factory_planner_http.py` (`FactoryPlannerService`, `attach_planner_routes()`), mounted inside `jiuwenswarm/gateway/channel_manager/web/web_channel_app.py` (`register_http_routes()`) under `/api/factory/planner/*`.
- Note: `jiuwenswarm/gateway/channel_manager/web/factory_http.py` also allows loopback dev-proxy origins on `/api/factory/launch`.

### 3.4 Web Frontend
- Entry routing: `jiuwenswarm/channels/web/frontend/src/features/factoryRuns/cc/navigation.ts` (`readFactoryEntry`, `plannerHref`, `capsuleHref`, `runHref`) and `jiuwenswarm/channels/web/frontend/src/features/factoryRuns/FactoryRunsPage.tsx`.
- Planner feature UI: `jiuwenswarm/channels/web/frontend/src/features/factoryRuns/planner/`:
  - `PlannerPage.tsx` (`live` tab: TaskInput picker / custom JSON + Muse-Spark preset, 7-stage `PipelineStepper`, `graph.json` download banner & sole output panel, autonomous `steps` & CC `Decisions` table, `GraphViewer`, TLC `Proof`, `ExecutionContract`, round inspector; `ablation` tab: `<AblationTab />`).
  - `plannerApi.ts` (`plannerApi.*` typed HTTP client).
  - `AblationTab.tsx`, `GraphTlaInspector.tsx`, `planner.css`.
- Localization: `jiuwenswarm/channels/web/frontend/src/i18n/locales/{en,zh}.json` under `factoryPlanner.*`.

### 3.5 CLI & Ablation Benchmark
- CLI (`jiuwenswarm/factory/cli.py`): `jiuwenswarm-factory synthesize <requirements.json> [--out DIR] [--replay RUN_DIR]`, `jiuwenswarm-factory verify-plan <contract> [--requirements TASK_INPUT]`.
- Ablation suite: `benchmarks/planner_tlc_ablation/` (`run_ablation.py`, `simulator.py`, `report_gen.py`, `build_onepager_zh.py`, `results.json`, `report.html`, `tlc_architecture_onepager_zh.pdf`).

---

## 4. How the Parts Communicate

### 4.1 Frontend Hash Routes
- `#planner` or `#planner/<plan_id>` (Live Planner tab; also accepts legacy `#factory-planner`)
- `#planner?tab=ablation` (3-way Old M1 vs M2 Static vs TLC-Verified Benchmark tab)
- `#capsules` / `#capsules/<capsule_dir>` (CC Work Library browser)
- `#factory-run` / `#factory-run/<task_id>` (Downstream Factory Runs monitor)

### 4.2 HTTP API Endpoints (`/api/factory/planner/*`)
All mutating `POST` routes enforce same-origin checks (`check_origin`, permitting local loopback dev proxies on `127.0.0.1` / `localhost` / `::1`).

| Method & Path | Purpose / Payload / Response |
| --- | --- |
| `GET /api/factory/planner/requirements` | Returns `{requirements: [{id, objective, contract_id, notes, document, problems}], environment: {tlc, java, tla2tools} \| {tlc: false, reason}}`. |
| `GET /api/factory/planner/runs` | Returns `{runs: [...status.json + id...], busy: [active_plan_id]}` (marks orphaned `pending`/`running` runs as `interrupted`). |
| `POST /api/factory/planner/runs` | Starts async planning (`202 Accepted` -> `{id: plan_id}`). Body must be exactly `{"requirements_id": "<id>"}` OR `{"requirements": <TaskInput JSON>}`. Returns `409` if a run is active, `422` on invalid `TaskInput`, `503` if TLC is unavailable. |
| `GET /api/factory/planner/runs/{plan_id}` | Returns full `PlanDetail`: `{id, status, requirements, rounds, graph, plan, node_contracts, comparison, record, verification, selection, ir, derivation, graph_tla_info, outputs}`. Poll while `status.state` is `'pending'` or `'running'` until `'succeeded'`, `'failed'`, or `'rejected'`. |
| `GET /api/factory/planner/runs/{plan_id}/graph.json` | **Sole deliverable download**: returns `application/json` with `Content-Disposition: attachment; filename="graph.json"`. Strictly returns `404` unless `status.state == 'succeeded'` and `verification.passed == True`. |
| `GET /api/factory/planner/runs/{plan_id}/rounds/{number}/{name}` | Inspect round logs (`name` in `'prompt' \| 'reply'`) returning `{text, truncated, size}`. |
| `GET /api/factory/planner/codex/status` | Codex subscription state (`{state, plan, ...}`). |
| `POST /api/factory/planner/codex/login` | Starts OAuth login (`{device_code?: boolean}`). |
| `POST /api/factory/planner/codex/cancel` | Cancels pending login (`{login_attempt_id}`). |
| `POST /api/factory/planner/codex/logout` | Signs out Codex session. |
| `GET /api/factory/planner/ablation` | Returns `{available, report_available, running, run_state, environment, results}`. |
| `GET /api/factory/planner/ablation/report.html` | Serves full standalone ablation HTML report. |
| `POST /api/factory/planner/ablation/run` | Starts live background re-run of `run_ablation.py` + `report_gen.py` (`202 Accepted`). |

### 4.3 Internal Codex + TLC Execution Flow
1. `ai_planner.synthesize` checks `tla_check.tools()` (`FACTORY_JAVA` / `java` and `FACTORY_TLA2TOOLS` / `third_party/tlaplus/tla2tools.jar`) *before* invoking any LLM.
2. Each round (up to `ROUNDS = 3`) calls `ai_planner.codex_invoke` -> `jiuwenswarm.server.runtime.codex_subscription.service.get_service().invoke_governed(prompt, system=SYSTEM, timeout_s=600)` (tool-free, single-turn).
3. Reply JSON (`factory.plan-ir/1`) is validated by `plan_ir.problems`, compiled by `plan_compile.compile_plan`, checked by `plan_checks.run` (bridged M1 + M2), rendered via `tla_graph.render_graph_tla`, and model-checked in two runs (`safety` + `delivery`) by `tla_check.check_graph_tla`. Failures feed back to the next round.
4. On pass, `_accept` runs `graph_preview` (`planner.plan_for_task`), writes `contract.json`, `plan.json`, `graph.json` (with `execution_model` and `verification`), `verification.json`, `task.json`, `ir.json`, `derivation.json`, and `plan-record.json`. Downstream execution seeds from `task.json` (`contract.json` + `plan.json`) using standard `controller.init_task` without any `.tla` dependency.

---

## 5. Real Synthesized Examples (Verbatim JSON)

### 5.1 Real Input Example (`jiuwenswarm/factory/requirements/star-deepseek-v2.json`)
```json
{
  "format": "factory.task-input/1",
  "requirements_id": "star-deepseek-v2",
  "objective": "Optimize DeepSeek V4.1 Flash TTFT on DGX Spark over stock llama.cpp 9048bad by selecting and integrating the compatible performance and observability capsules (runtime event recorder, weight placement planner, expert weight cache, expert demand predictor, batch layout mapper) into a single combined candidate build, with every gate off by default and byte-identical output when unset.",
  "subject": {
    "engine": {
      "name": "llama.cpp",
      "source": "https://github.com/ggml-org/llama.cpp",
      "revision": "9048bad8d6e3a0f9f1726e238e451181c7e02613"
    },
    "model": {
      "name": "DeepSeek V4.1 Flash, IQ2_XXS six-shard GGUF conversion",
      "format": "gguf"
    }
  },
  "target": {
    "profile": "spark-gb10",
    "machine": "DGX Spark GB10",
    "arch": "arm64",
    "cuda": "13",
    "sm": "121",
    "node_count": 1
  },
  "acceptance_criteria": [
    {"id": "gate_unset_parity", "kind": "correctness", "description": "With every capsule gate unset, greedy output matches stock llama.cpp byte for byte."},
    {"id": "gate_set_activation", "kind": "correctness", "description": "With each gate set, the engine prints its capsule activation marker."},
    {"id": "server_token_count", "kind": "correctness", "description": "Server prompt token count equals the rendered prompt token count (512 / 2048)."},
    {"id": "client_ttft_ms", "kind": "metric", "description": "Client time to first token (ms, lower is better) at 512 and 2048 prompt tokens."},
    {"id": "decode_tokens_per_second", "kind": "metric", "description": "Decode rate (tokens/s, higher is better)."},
    {"id": "sampled_peak_memory_bytes", "kind": "metric", "description": "Highest sampled resident memory under the cap (bytes, lower is better)."},
    {"id": "load_seconds", "kind": "metric", "description": "Cold load time from start to ready (s, lower is better)."}
  ],
  "constraints": {
    "allowed_effects": ["workspace.read", "workspace.write", "process.exec"],
    "budget": {"max_turns": 300, "wall_clock_s": 21600}
  },
  "notes": [
    "Each component stays off by default behind its own switch; any one can be enabled alone.",
    "The factory never starts a model: the lab agent runs every engine and every measurement.",
    "Work only in the task-owned checkout; no remotes or pushes."
  ]
}
```

### 5.2 Real Output Example (`graph.json` emitted by `ai_planner.synthesize`)
```json
{
  "schema": "factory.taskgraph/1",
  "task_id": "planner-ex-yuwrrs8_",
  "rev": 0,
  "nodes": [
    {
      "capability": null,
      "inputs": [
        "planner-ex-yuwrrs8_",
        "contract:/private/var/folders/02/m38l_wps4r7c71crch_jkp3c0000gn/T/planner-ex-yuwrrs8_/contract.json"
      ],
      "depends_on": [],
      "state": "proposed",
      "attempt_ids": [],
      "evidence_ids": [],
      "reason": "Planned by factory.ai_planner from node contract inspect_engine.",
      "node_id": "inspect_engine",
      "kind": "inspect",
      "title": "Inspect pinned engine checkout and record CC Library capsule anchors.",
      "node_contract": "inspect_engine",
      "check": {
        "outputs": [
          {
            "name": "engine_map",
            "kind": "evidence",
            "required": true,
            "criteria": [
              "Names engine revision 9048bad8d, target spark-gb10, and source anchors for cache."
            ]
          }
        ]
      },
      "created_by_decision_rev": 0
    },
    {
      "capability": null,
      "inputs": [
        "planner-ex-yuwrrs8_",
        "contract:/private/var/folders/02/m38l_wps4r7c71crch_jkp3c0000gn/T/planner-ex-yuwrrs8_/contract.json"
      ],
      "depends_on": [
        "inspect_engine"
      ],
      "state": "proposed",
      "attempt_ids": [],
      "evidence_ids": [],
      "reason": "Planned by factory.ai_planner from node contract preflight_cache.",
      "node_id": "preflight_cache",
      "kind": "inspect",
      "title": "Verify engine.build_expert_weight_cache applicability on target hardware before editing.",
      "node_contract": "preflight_cache",
      "check": {
        "outputs": [
          {
            "name": "applicability",
            "kind": "evidence",
            "required": true,
            "review": true,
            "criteria": [
              "States whether the capsule method, source anchors and build settings apply to spark-gb10 (declared for jetson-orin sm_87; the task targets spark-gb10 sm_121), citing the files read.",
              "Names every target adaptation needed beyond the capsule method, or states that none is needed."
            ]
          }
        ]
      },
      "created_by_decision_rev": 0
    },
    {
      "capability": "engine.build_expert_weight_cache.verify",
      "inputs": [
        "planner-ex-yuwrrs8_",
        "contract:/private/var/folders/02/m38l_wps4r7c71crch_jkp3c0000gn/T/planner-ex-yuwrrs8_/contract.json"
      ],
      "depends_on": [
        "preflight_cache"
      ],
      "state": "proposed",
      "attempt_ids": [],
      "evidence_ids": [],
      "reason": "Planned by factory.ai_planner from node contract integrate_cache.",
      "node_id": "integrate_cache",
      "kind": "integrate",
      "title": "Integrate engine.build_expert_weight_cache behind its runtime toggle in an owned checkout.",
      "node_contract": "integrate_cache",
      "check": {
        "outputs": [
          {
            "name": "change",
            "kind": "diff",
            "required": true,
            "verifier": "engine.build_expert_weight_cache.verify",
            "stage": "native CC execution",
            "review": true,
            "criteria": [
              "Implements the expert weight cache as engine.build_expert_weight_cache describes, touching only the files its source map allows.",
              "With every capsule gate unset, greedy output matches stock llama.cpp byte for byte.",
              "With each gate set, the engine prints its capsule activation marker.",
              "Server prompt token count equals the rendered prompt token count (512 / 2048).",
              "With LLAMA_EXPERT_CACHE unset, take the stock path and do no component work beyond one cached getenv check. Emit zero log lines with the expert_weight_cache: prefix. Active, inactive (<reason>) and stats markers require a set gate.",
              "Preserve native --moe-cache-mib precedence and the stock copy when disabled or when a lease fails.",
              "Deliver the exact stock weight bytes and padding with identical greedy stdout.",
              "Share one lease per expert per operation and retain backing allocations through the last reader.",
              "Each component stays off by default behind its own switch; any one can be enabled alone.",
              "The factory never starts a model: the lab agent runs every engine and every measurement.",
              "Work only in the task-owned checkout; no remotes or pushes."
            ]
          }
        ]
      },
      "created_by_decision_rev": 0
    },
    {
      "capability": null,
      "inputs": [
        "planner-ex-yuwrrs8_",
        "contract:/private/var/folders/02/m38l_wps4r7c71crch_jkp3c0000gn/T/planner-ex-yuwrrs8_/contract.json"
      ],
      "depends_on": [
        "integrate_cache"
      ],
      "state": "proposed",
      "attempt_ids": [],
      "evidence_ids": [],
      "reason": "Planned by factory.ai_planner from node contract build_candidate.",
      "node_id": "build_candidate",
      "kind": "build",
      "title": "Build and package final verified engine artifact.",
      "node_contract": "build_candidate",
      "check": {
        "outputs": [
          {
            "name": "sources",
            "kind": "source_bundle",
            "required": true,
            "criteria": [
              "One final source bundle for DeepSeek V4.1 Flash, IQ2_XXS six-shard GGUF conversion against pinned commit 9048bad8d (spark-gb10)."
            ]
          },
          {
            "name": "image",
            "kind": "image",
            "required": false,
            "criteria": [
              "Optional: a factory-built image of the final build with its build receipt."
            ]
          }
        ]
      },
      "resources": {
        "class": "build"
      },
      "created_by_decision_rev": 0
    },
    {
      "capability": null,
      "inputs": [
        "planner-ex-yuwrrs8_",
        "contract:/private/var/folders/02/m38l_wps4r7c71crch_jkp3c0000gn/T/planner-ex-yuwrrs8_/contract.json"
      ],
      "depends_on": [
        "build_candidate"
      ],
      "state": "proposed",
      "attempt_ids": [],
      "evidence_ids": [],
      "reason": "Planned by factory.ai_planner from node contract deliver_to_lab.",
      "node_id": "deliver_to_lab",
      "kind": "deliver",
      "title": "Deliver verified engine artifact and acceptance suite to lab.",
      "node_contract": "deliver_to_lab",
      "check": {
        "outputs": [
          {
            "name": "lab_request",
            "kind": "lab_request",
            "required": true,
            "criteria": [
              "Delivers the verified artifact against pinned commit 9048bad8d on spark-gb10.",
              "Verifies every correctness check, metric and constraint in acceptance_criteria.",
              "[gate_unset_parity] With every capsule gate unset, greedy output matches stock llama.cpp byte for byte.",
              "[gate_set_activation] With each gate set, the engine prints its capsule activation marker.",
              "[server_token_count] Server prompt token count equals the rendered prompt token count (512 / 2048).",
              "[client_ttft_ms] Client time to first token (ms, lower is better) at 512 and 2048 prompt tokens.",
              "[decode_tokens_per_second] Decode rate (tokens/s, higher is better).",
              "[sampled_peak_memory_bytes] Highest sampled resident memory under the cap (bytes, lower is better).",
              "[load_seconds] Cold load time from start to ready (s, lower is better)."
            ]
          }
        ]
      },
      "created_by_decision_rev": 0
    }
  ],
  "ready_frontier": [
    "inspect_engine"
  ],
  "blocked_reasons": {
    "preflight_cache": [
      "dependency inspect_engine is proposed"
    ],
    "integrate_cache": [
      "dependency preflight_cache is proposed"
    ],
    "build_candidate": [
      "dependency integrate_cache is proposed"
    ],
    "deliver_to_lab": [
      "dependency build_candidate is proposed"
    ]
  },
  "history": [],
  "planner": "factory.ai_planner",
  "execution_model": {
    "nodes": [
      "inspect_engine",
      "preflight_cache",
      "integrate_cache",
      "build_candidate",
      "deliver_to_lab"
    ],
    "preds": {
      "inspect_engine": [],
      "preflight_cache": [
        "inspect_engine"
      ],
      "integrate_cache": [
        "preflight_cache"
      ],
      "build_candidate": [
        "integrate_cache"
      ],
      "deliver_to_lab": [
        "build_candidate"
      ]
    },
    "deliver": "deliver_to_lab",
    "limits": {
      "inspect_engine": 2,
      "preflight_cache": 2,
      "integrate_cache": 2,
      "build_candidate": 3,
      "deliver_to_lab": 2
    },
    "exclusive": {
      "inspect_engine": [],
      "preflight_cache": [],
      "integrate_cache": [
        "checkout"
      ],
      "build_candidate": [
        "builder"
      ],
      "deliver_to_lab": []
    },
    "max_parallel": 4,
    "default_attempts": 3,
    "proven": [
      {
        "run": "safety",
        "checked": [
          "TypeOK",
          "DependencyOrder",
          "ExclusiveResources",
          "ParallelBound",
          "AttemptBound",
          "NoStuck",
          "DeliveredMeansAllDone",
          "Termination"
        ],
        "distinct_states": 259
      },
      {
        "run": "delivery",
        "checked": [
          "TypeOK",
          "DependencyOrder",
          "ExclusiveResources",
          "ParallelBound",
          "AttemptBound",
          "NoStuck",
          "DeliveredMeansAllDone",
          "HaltsDelivered",
          "Termination"
        ],
        "distinct_states": 220
      }
    ],
    "spec_sha256": "0f44fec848dc13d7712a69620e5e073e22150bae31897764bbfe73aa719c7990"
  },
  "verification": {
    "static_checks": {
      "passed": true,
      "warnings": []
    },
    "tlc": {
      "passed": true,
      "runs": [
        {
          "run": "safety",
          "checked": [
            "TypeOK",
            "DependencyOrder",
            "ExclusiveResources",
            "ParallelBound",
            "AttemptBound",
            "NoStuck",
            "DeliveredMeansAllDone",
            "Termination"
          ],
          "distinct_states": 259
        },
        {
          "run": "delivery",
          "checked": [
            "TypeOK",
            "DependencyOrder",
            "ExclusiveResources",
            "ParallelBound",
            "AttemptBound",
            "NoStuck",
            "DeliveredMeansAllDone",
            "HaltsDelivered",
            "Termination"
          ],
          "distinct_states": 220
        }
      ],
      "spec_sha256": "0f44fec848dc13d7712a69620e5e073e22150bae31897764bbfe73aa719c7990"
    }
  }
}
```
