# 20261113 CC Catalog and Lab Integration postpresentation

This catalog is generated from the actual declarations in local revision `fe88a206` (published factory implementation `532d56c7`). It includes every factory CC and the separate runtime demonstration CCs. Archived evidence copies and test fixtures are not additional catalog entries. A declaration is an interface, not proof of invocation, deployment or performance. See the [Jetson branch record](20261113%20Jetson%20Software%20Factory%20Branch%20Record%20postpresentation.md) for results and limitations.

## Where lab developers should start

Reuse the existing separation: the factory records intent, authority and evidence; the lab executes bounded jobs and returns identified results. Start with `factory.builder`, `factory.lab_client`, `factory.evidence` and `factory.engine_inspector`. Read method/component materials before adapting a candidate. Do not treat material-only CCs as executable lab services.

```text
CC declaration -> native run.py -> factory API -> durable attempt / job
                                                  |
                                       Siminfeng queue and tools
                                                  |
                          build receipt / image / logs / lab results
                                                  |
                       admission -> contract evaluation -> evidence
```

## Lab implementation boundary

| Lab responsibility | Existing reference | What a compatible lab must preserve |
|---|---|---|
| Queue and lifecycle | [jobs.py](../../../jiuwenswarm/factory/jobs.py); Siminfeng `bin/jobq` | Durable job identity, same-input retry recovery, status, finite timeout, owned cancellation and complete logs. Do not start a competing worker. |
| Builds | [builder.py](../../../jiuwenswarm/factory/builder.py), [build_job.py](../../../jiuwenswarm/factory/build_job.py) | Pinned source/configuration; successful receipt and exact image identity; submission is not completion. |
| Admission | [manager.py](../../../jiuwenswarm/factory/manager.py) | Verify successful build, inspected immutable image and target/profile compatibility. |
| Single-run evaluation | [lab_runner.py](../../../jiuwenswarm/factory/lab_runner.py), [contract.py](../../../jiuwenswarm/factory/contract.py) | Frozen workload, raw output, exit status, correctness/engagement fields and evidence references. Missing instrumentation remains missing. |
| Comparison | [ab.py](../../../jiuwenswarm/factory/ab.py), [ab_runner.py](../../../jiuwenswarm/factory/ab_runner.py) | Comparable arms/settings, component acceptance, noise/null handling and contention records. Profiled runs are not speed evidence. |
| Evidence | [store.py](../../../jiuwenswarm/factory/store.py), [taskgraph.py](../../../jiuwenswarm/factory/taskgraph.py) | Public interfaces, immutable referenced records and revisions; do not synthesize success or edit the database directly. |

The declarations below often type a payload as `json`; that is not a complete nested schema. Follow the implementation and the [factory schemas](../../../jiuwenswarm/factory/schemas), [task inputs](../../../jiuwenswarm/factory/tasks) and [frozen contracts](../../../jiuwenswarm/factory/contracts) for the actual fields and checks. `run.py` bindings dispatch into factory interfaces; they are not standalone lab installers.

### Configuration is host-specific

Inspect [config.py](../../../jiuwenswarm/factory/config.py) and [RUNBOOK.md](RUNBOOK.md) before adapting a lab. Overrides include `SIMINFENG_ROOT`, `FACTORY_JOBQ_BIN`, `FACTORY_BUILD_ENGINE`, `FACTORY_BUILD_RECIPE`, `FACTORY_OM_RUN`, `FACTORY_PROBE_MODEL`, `FACTORY_BASELINE_RECORD` and `FACTORY_BASELINE_IMAGE`. The defaults include Jetson recipes, model paths and timeouts. Record actual lab revision, recipe, models, image, environment, queue and resources; an environment-variable override alone does not qualify a new target.

A lab smoke test should cover read-only inspection, one harmless queued job, reconnect without duplicate submission, owned cancellation/timeout cleanup, a completed build with matching identity and one fixed-workload correctness run. Only then run a bounded matched comparison. Keep failures and distinguish orchestration tests from engine performance. These are recommended qualification steps, not a claim that every lab adapter has passed them.

## Factory and Jetson components

| CC | Version | Binding | Capabilities |
|---|---|---|---|
| [factory.builder](../../../jiuwenswarm/factory/ccs/builder/cc.yaml) | 1.0.0 | native | `submit`, `status`, `cancel`, `result` |
| [factory.engine_component](../../../jiuwenswarm/factory/ccs/engine_component/cc.yaml) | 1.0.0 | material-only | None |
| [factory.engine_inspector](../../../jiuwenswarm/factory/ccs/engine_inspector/cc.yaml) | 1.0.0 | native | `inspect`, `preflight`, `verify_effective_config` |
| [factory.evidence](../../../jiuwenswarm/factory/ccs/evidence/cc.yaml) | 1.0.0 | native | `plan_get`, `plan_patch`, `query`, `read`, `publish` |
| [engine.expert_streaming](../../../jiuwenswarm/factory/ccs/expert_streaming/cc.yaml) | 2.0.1 | native | `applicability`, `engagement` |
| [factory.components.expert_fill](../../../jiuwenswarm/factory/ccs/expert_streaming/components/expert_fill/cc.yaml) | 1.1.0 | material-only | None |
| [factory.components.expert_pregate](../../../jiuwenswarm/factory/ccs/expert_streaming/components/expert_pregate/cc.yaml) | 1.1.0 | material-only | None |
| [factory.components.expert_readiness](../../../jiuwenswarm/factory/ccs/expert_streaming/components/expert_readiness/cc.yaml) | 1.0.0 | material-only | None |
| [factory.components.inflight_join](../../../jiuwenswarm/factory/ccs/expert_streaming/components/inflight_join/cc.yaml) | 1.0.0 | material-only | None |
| [factory.components.mmap_advice](../../../jiuwenswarm/factory/ccs/expert_streaming/components/mmap_advice/cc.yaml) | 1.1.0 | material-only | None |
| [factory.components.phase_stats](../../../jiuwenswarm/factory/ccs/expert_streaming/components/phase_stats/cc.yaml) | 1.0.0 | material-only | None |
| [factory.components.router_prefetch](../../../jiuwenswarm/factory/ccs/expert_streaming/components/router_prefetch/cc.yaml) | 1.1.0 | material-only | None |
| [factory.components.thread_names](../../../jiuwenswarm/factory/ccs/expert_streaming/components/thread_names/cc.yaml) | 1.1.0 | material-only | None |
| [factory.integration_skill](../../../jiuwenswarm/factory/ccs/integration_skill/cc.yaml) | 1.0.0 | material-only | None |
| [factory.lab_client](../../../jiuwenswarm/factory/ccs/lab_client/cc.yaml) | 1.0.0 | native | `submit`, `status`, `cancel`, `result`, `ab_submit`, `ab_status`, `ab_result` |
| [factory.methodology_ab](../../../jiuwenswarm/factory/ccs/methodology_ab/cc.yaml) | 1.0.0 | material-only | None |

### factory.builder

Version **1.0.0**. [Canonical declaration](../../../jiuwenswarm/factory/ccs/builder/cc.yaml). SHA-256: `e370aa97dedd1772cbbb8cbbf659035bd0b804a2432d0a24d40e476f99ca3909`.

Native entry point: [run.py](../../../jiuwenswarm/factory/ccs/builder/run.py).

**`submit`**: Submit a durable build job. This acknowledges submission, not success; inspect status and result separately.

Inputs: `request`, `idem_key`, `node_id`. Outputs: `attempt_id`, `state`, `jobq_id`.

**`status`**: Read and reconcile the owned build attempt.

Inputs: `attempt_id`. Outputs: `attempt_id`, `task_id`, `kind`, `idem_key`, `fingerprint`, `request`, `state`, `jobq_id`, `owner`, `started`, `ended`, `resources`, `result_refs`, `cleanup_state`, `history`.

**`cancel`**: Request cancellation of the owned build attempt.

Inputs: `attempt_id`. Outputs: `attempt_id`, `task_id`, `kind`, `idem_key`, `fingerprint`, `request`, `state`, `jobq_id`, `owner`, `started`, `ended`, `resources`, `result_refs`, `cleanup_state`, `history`.

**`result`**: Read build result references; submission alone is not success.

Inputs: `attempt_id`. Outputs: `attempt_id`, `state`, `result_refs`.

<details>
<summary>Full declaration: inputs, outputs, bindings, needs and effects</summary>

```yaml
cc: '2'
id: factory.builder
version: 1.0.0
bindings:
  default:
    kind: native
    command:
    - '{python}'
    - '{bundle}/run.py'
capabilities:
  submit:
    kind: tool
    does: Submit a durable build job. This acknowledges submission, not success; inspect
      status and result separately.
    takes:
      request: json
      idem_key: text
      node_id:
        kind: text
        optional: true
    gives:
      attempt_id: text
      state: text
      jobq_id: json
    needs:
    - python
    changes:
    - process.exec
  status:
    kind: tool
    does: Read and reconcile the owned build attempt.
    takes:
      attempt_id: text
    gives:
      attempt_id: text
      task_id: text
      kind: text
      idem_key: text
      fingerprint: text
      request: json
      state: text
      jobq_id: json
      owner: json
      started: json
      ended: json
      resources: json
      result_refs: json
      cleanup_state: text
      history: json
    needs:
    - python
    changes:
    - process.exec
  cancel:
    kind: tool
    does: Request cancellation of the owned build attempt.
    takes:
      attempt_id: text
    gives:
      attempt_id: text
      task_id: text
      kind: text
      idem_key: text
      fingerprint: text
      request: json
      state: text
      jobq_id: json
      owner: json
      started: json
      ended: json
      resources: json
      result_refs: json
      cleanup_state: text
      history: json
    needs:
    - python
    changes:
    - process.exec
  result:
    kind: tool
    does: Read build result references; submission alone is not success.
    takes:
      attempt_id: text
    gives:
      attempt_id: text
      state: text
      result_refs: json
    needs:
    - python
    changes:
    - process.exec
```

</details>

### factory.engine_component

Version **1.0.0**. [Canonical declaration](../../../jiuwenswarm/factory/ccs/engine_component/cc.yaml). SHA-256: `6c41a078206afd209b71dead67a1948d011cb7a3d6b34897bbe8daaf2d576aaf`.

| Material | Kind | Full content |
|---|---|---|
| `component` | component | [component.yaml](../../../jiuwenswarm/factory/ccs/engine_component/component.yaml) |
| `patch` | component | [09-thread-names.patch](../../../jiuwenswarm/factory/ccs/engine_component/09-thread-names.patch) |
| `pre_integration_patch` | component | [combined-01-02-03-04-05-06-07-08.patch](../../../jiuwenswarm/factory/ccs/engine_component/combined-01-02-03-04-05-06-07-08.patch) |
| `readme` | reference | [README.md](../../../jiuwenswarm/factory/ccs/engine_component/README.md) |

<details>
<summary>Full declaration: inputs, outputs, bindings, needs and effects</summary>

```yaml
cc: '2'
id: factory.engine_component
version: 1.0.0
materials:
  component:
    kind: component
    path: component.yaml
  patch:
    kind: component
    path: 09-thread-names.patch
  pre_integration_patch:
    kind: component
    path: combined-01-02-03-04-05-06-07-08.patch
  readme:
    kind: reference
    path: README.md
```

</details>

### factory.engine_inspector

Version **1.0.0**. [Canonical declaration](../../../jiuwenswarm/factory/ccs/engine_inspector/cc.yaml). SHA-256: `aac280bc945d2dd239446a1a0770675f2298f90b7f647c23763fb16d9a38c0aa`.

Native entry point: [run.py](../../../jiuwenswarm/factory/ccs/engine_inspector/run.py).

**`inspect`**: Inspect an authorized source checkout, host and optional local image; publish evidence.

Inputs: `source`, `subpath`, `image`. Outputs: `source`, `host`, `image`, `evidence`.

**`preflight`**: Resolve local image Id and reject unsupported flags using help cached by immutable Id.

Inputs: `image`, `tool`, `argv`. Outputs: `ok`, `unsupported_flags`, `help_sha256`, `image`, `evidence`.

**`verify_effective_config`**: Run one bounded CPU-only model config probe in an NVIDIA-runtime container and publish actual stderr evidence.

Inputs: `image`, `env`. Outputs: `requested`, `effective`, `mismatches`, `image`, `exit_status`, `aborted`, `invalid_line`, `engine_lines`, `evidence`.

<details>
<summary>Full declaration: inputs, outputs, bindings, needs and effects</summary>

```yaml
cc: '2'
id: factory.engine_inspector
version: 1.0.0
bindings:
  default:
    kind: native
    command:
    - '{python}'
    - '{bundle}/run.py'
capabilities:
  inspect:
    kind: tool
    does: Inspect an authorized source checkout, host and optional local image; publish
      evidence.
    takes:
      source:
        kind: handle
        description: Host-bound workspace handle; subpath selects its repository root.
      subpath:
        kind: text
        optional: true
      image:
        kind: json
        optional: true
    gives:
      source: json
      host: json
      image:
        kind: json
        optional: true
      evidence: json
    needs:
    - python
    - workspace
    changes:
    - workspace.read
    - process.exec
  preflight:
    kind: tool
    does: Resolve local image Id and reject unsupported flags using help cached by
      immutable Id.
    takes:
      image: json
      tool: text
      argv:
        kind: json
        schema:
          type: array
          items:
            type: string
    gives:
      ok: json
      unsupported_flags: json
      help_sha256: text
      image: json
      evidence: json
    needs:
    - python
    changes:
    - process.exec
    - gpu.use
  verify_effective_config:
    kind: tool
    does: Run one bounded CPU-only model config probe in an NVIDIA-runtime container
      and publish actual stderr evidence.
    takes:
      image: json
      env: json
    gives:
      requested: json
      effective: json
      mismatches: json
      image: json
      exit_status: json
      aborted: json
      invalid_line:
        kind: text
        optional: true
      engine_lines:
        kind: json
        optional: true
      evidence: json
    needs:
    - python
    changes:
    - process.exec
    - gpu.use
```

</details>

### factory.evidence

Version **1.0.0**. [Canonical declaration](../../../jiuwenswarm/factory/ccs/evidence/cc.yaml). SHA-256: `eaf79c7b87f4acd83060d99715fa6dcd53ed39f19093d97e06cb1c76dc144d22`.

Native entry point: [run.py](../../../jiuwenswarm/factory/ccs/evidence/run.py).

**`plan_get`**: Read a replayable work graph, ready frontier, blocked reasons and revision history. Proposed work is a suggestion.

Inputs: `rev`. Outputs: `plan`.

**`plan_patch`**: Apply a task-scoped work graph patch by CAS, citing a published decision. Does not start jobs or grant authority.

Inputs: `patch`, `expected_graph_rev`, `decision_rev`. Outputs: `plan`.

**`query`**: Query bounded task-scoped evidence summaries and cursor.

Inputs: `kinds`, `text`, `since`, `limit`, `task_id`. Outputs: `items`, `cursor`.

**`read`**: Read a task-scoped evidence record, with bounded artifact preview.

Inputs: `id`, `task_id`. Outputs: `record`.

**`publish`**: Publish an immutable observation/artifact or compare-and-swap decision revision.

Inputs: `type`, `record`, `expected_rev`. Outputs: `record`.

<details>
<summary>Full declaration: inputs, outputs, bindings, needs and effects</summary>

```yaml
cc: '2'
id: factory.evidence
version: 1.0.0
bindings:
  default:
    kind: native
    command:
    - '{python}'
    - '{bundle}/run.py'
capabilities:
  plan_get:
    kind: tool
    does: Read a replayable work graph, ready frontier, blocked reasons and revision history. Proposed work is a suggestion.
    takes:
      rev:
        kind: json
        optional: true
    gives:
      plan: json
    needs:
    - python
    changes:
    - process.exec
  plan_patch:
    kind: tool
    does: Apply a task-scoped work graph patch by CAS, citing a published decision. Does not start jobs or grant authority.
    takes:
      patch: json
      expected_graph_rev: json
      decision_rev: json
    gives:
      plan: json
    needs:
    - python
    changes:
    - process.exec
  query:
    kind: tool
    does: Query bounded task-scoped evidence summaries and cursor.
    takes:
      kinds:
        kind: json
        optional: true
      text:
        kind: text
        optional: true
      since:
        kind: json
        optional: true
      limit:
        kind: json
        optional: true
      task_id:
        kind: text
        optional: true
    gives:
      items: json
      cursor: json
    needs:
    - python
    changes:
    - process.exec
  read:
    kind: tool
    does: Read a task-scoped evidence record, with bounded artifact preview.
    takes:
      id: text
      task_id:
        kind: text
        optional: true
    gives:
      record: json
    needs:
    - python
    changes:
    - process.exec
  publish:
    kind: tool
    does: Publish an immutable observation/artifact or compare-and-swap decision revision.
    takes:
      type: text
      record: json
      expected_rev:
        kind: json
        optional: true
    gives:
      record: json
    needs:
    - python
    changes:
    - process.exec
```

</details>

### engine.expert_streaming

Version **2.0.1**. [Canonical declaration](../../../jiuwenswarm/factory/ccs/expert_streaming/cc.yaml). SHA-256: `1b45b42a5b1147f9a16c8d475abf9298b4b4089d228f438c09b14ead4ca92851`.

Native entry point: [run.py](../../../jiuwenswarm/factory/ccs/expert_streaming/run.py).

| Material | Kind | Full content |
|---|---|---|
| `guide` | skill | [STREAMING.md](../../../jiuwenswarm/factory/ccs/expert_streaming/STREAMING.md) |
| `method` | method | [EVIDENCE.md](../../../jiuwenswarm/factory/ccs/expert_streaming/EVIDENCE.md) |
| `source_map` | reference | [SOURCE-MAP.md](../../../jiuwenswarm/factory/ccs/expert_streaming/SOURCE-MAP.md) |
| `ontology` | reference | [ONTOLOGY.yaml](../../../jiuwenswarm/factory/ccs/expert_streaming/ONTOLOGY.yaml) |
| `expert_fill` | component | [component.yaml](../../../jiuwenswarm/factory/ccs/expert_streaming/components/expert_fill/component.yaml) |
| `expert_pregate` | component | [component.yaml](../../../jiuwenswarm/factory/ccs/expert_streaming/components/expert_pregate/component.yaml) |
| `mmap_advice` | component | [component.yaml](../../../jiuwenswarm/factory/ccs/expert_streaming/components/mmap_advice/component.yaml) |
| `router_prefetch` | component | [component.yaml](../../../jiuwenswarm/factory/ccs/expert_streaming/components/router_prefetch/component.yaml) |
| `thread_names` | component | [component.yaml](../../../jiuwenswarm/factory/ccs/expert_streaming/components/thread_names/component.yaml) |
| `expert_readiness` | component | [component.yaml](../../../jiuwenswarm/factory/ccs/expert_streaming/components/expert_readiness/component.yaml) |
| `inflight_join` | component | [component.yaml](../../../jiuwenswarm/factory/ccs/expert_streaming/components/inflight_join/component.yaml) |
| `phase_stats` | component | [component.yaml](../../../jiuwenswarm/factory/ccs/expert_streaming/components/phase_stats/component.yaml) |

**`applicability`**: Inspect applicability and publish a task-scoped observation; no engine execution.

Inputs: `model_path`, `argv`, `observed`. Outputs: `expert_bytes`, `other_bytes`, `mem_total`, `mem_available`, `experts_cpu_side`, `mmap`, `verdict`, `reasons`, `candidates`, `evidence`.

**`engagement`**: Inspect engagement and publish a task-scoped observation; no engine execution.

Inputs: `attempt_id`, `evaluation_id`, `requires_evidence`. Outputs: `runs`, `status`, `missing_required`, `evidence`.

<details>
<summary>Full declaration: inputs, outputs, bindings, needs and effects</summary>

```yaml
cc: '2'
id: engine.expert_streaming
version: 2.0.1
materials:
  guide:
    kind: skill
    path: STREAMING.md
  method:
    kind: method
    path: EVIDENCE.md
  source_map:
    kind: reference
    path: SOURCE-MAP.md
  ontology:
    kind: reference
    path: ONTOLOGY.yaml
  expert_fill:
    kind: component
    path: components/expert_fill/component.yaml
  expert_pregate:
    kind: component
    path: components/expert_pregate/component.yaml
  mmap_advice:
    kind: component
    path: components/mmap_advice/component.yaml
  router_prefetch:
    kind: component
    path: components/router_prefetch/component.yaml
  thread_names:
    kind: component
    path: components/thread_names/component.yaml
  expert_readiness:
    kind: component
    path: components/expert_readiness/component.yaml
  inflight_join:
    kind: component
    path: components/inflight_join/component.yaml
  phase_stats:
    kind: component
    path: components/phase_stats/component.yaml
bindings:
  default:
    kind: native
    command:
    - '{python}'
    - '{bundle}/run.py'
capabilities:
  applicability:
    kind: tool
    does: Inspect applicability and publish a task-scoped observation; no engine execution.
    takes:
      model_path:
        kind: text
        optional: true
      argv:
        kind: json
        optional: true
      observed:
        kind: json
        optional: true
    gives:
      expert_bytes: json
      other_bytes: json
      mem_total: json
      mem_available: json
      experts_cpu_side: json
      mmap: json
      verdict: json
      reasons: json
      candidates: json
      evidence: json
    needs:
    - python
    changes:
    - process.exec
  engagement:
    kind: tool
    does: Inspect engagement and publish a task-scoped observation; no engine execution.
    takes:
      attempt_id:
        kind: text
        optional: true
      evaluation_id:
        kind: text
        optional: true
      requires_evidence:
        kind: json
        optional: true
    gives:
      runs: json
      status: json
      missing_required: json
      evidence: json
    needs:
    - python
    changes:
    - process.exec
```

</details>

### factory.components.expert_fill

Version **1.1.0**. [Canonical declaration](../../../jiuwenswarm/factory/ccs/expert_streaming/components/expert_fill/cc.yaml). SHA-256: `06dedd06f6ef4ef53877c562a34ffafd19f3e9681d9be443b85d4abe54c59f84`.

| Material | Kind | Full content |
|---|---|---|
| `component` | component | [component.yaml](../../../jiuwenswarm/factory/ccs/expert_streaming/components/expert_fill/component.yaml) |
| `patch_03` | component | [03-expert-fill.patch](../../../jiuwenswarm/factory/ccs/expert_streaming/components/expert_fill/03-expert-fill.patch) |
| `patch_04` | component | [04-fill-phase.patch](../../../jiuwenswarm/factory/ccs/expert_streaming/components/expert_fill/04-fill-phase.patch) |
| `patch_05` | component | [05-fill-diag.patch](../../../jiuwenswarm/factory/ccs/expert_streaming/components/expert_fill/05-fill-diag.patch) |

<details>
<summary>Full declaration: inputs, outputs, bindings, needs and effects</summary>

```yaml
cc: '2'
id: factory.components.expert_fill
version: 1.1.0
materials:
  component:
    kind: component
    path: component.yaml
  patch_03:
    kind: component
    path: 03-expert-fill.patch
  patch_04:
    kind: component
    path: 04-fill-phase.patch
  patch_05:
    kind: component
    path: 05-fill-diag.patch
```

</details>

### factory.components.expert_pregate

Version **1.1.0**. [Canonical declaration](../../../jiuwenswarm/factory/ccs/expert_streaming/components/expert_pregate/cc.yaml). SHA-256: `39e87f3a64ee9d3d617c9696110cf1c9b3428e50c55aceb956d6e68435fa8495`.

| Material | Kind | Full content |
|---|---|---|
| `component` | component | [component.yaml](../../../jiuwenswarm/factory/ccs/expert_streaming/components/expert_pregate/component.yaml) |
| `patch_06` | component | [06-pregate.patch](../../../jiuwenswarm/factory/ccs/expert_streaming/components/expert_pregate/06-pregate.patch) |
| `patch_07` | component | [07-pregate-sched.patch](../../../jiuwenswarm/factory/ccs/expert_streaming/components/expert_pregate/07-pregate-sched.patch) |
| `patch_08` | component | [08-pregate-observe.patch](../../../jiuwenswarm/factory/ccs/expert_streaming/components/expert_pregate/08-pregate-observe.patch) |

<details>
<summary>Full declaration: inputs, outputs, bindings, needs and effects</summary>

```yaml
cc: '2'
id: factory.components.expert_pregate
version: 1.1.0
materials:
  component:
    kind: component
    path: component.yaml
  patch_06:
    kind: component
    path: 06-pregate.patch
  patch_07:
    kind: component
    path: 07-pregate-sched.patch
  patch_08:
    kind: component
    path: 08-pregate-observe.patch
```

</details>

### factory.components.expert_readiness

Version **1.0.0**. [Canonical declaration](../../../jiuwenswarm/factory/ccs/expert_streaming/components/expert_readiness/cc.yaml). SHA-256: `5d833e374466cc8e11358bcef9248d9a4f11fc73c27bcef8478f35589314d3e3`.

| Material | Kind | Full content |
|---|---|---|
| `component` | component | [component.yaml](../../../jiuwenswarm/factory/ccs/expert_streaming/components/expert_readiness/component.yaml) |
| `patch_10` | component | [10-expert-readiness.patch](../../../jiuwenswarm/factory/ccs/expert_streaming/components/expert_readiness/10-expert-readiness.patch) |

<details>
<summary>Full declaration: inputs, outputs, bindings, needs and effects</summary>

```yaml
cc: '2'
id: factory.components.expert_readiness
version: 1.0.0
materials:
  component:
    kind: component
    path: component.yaml
  patch_10:
    kind: component
    path: 10-expert-readiness.patch
```

</details>

### factory.components.inflight_join

Version **1.0.0**. [Canonical declaration](../../../jiuwenswarm/factory/ccs/expert_streaming/components/inflight_join/cc.yaml). SHA-256: `f33942ae254d9223b4e20a81c8ca1c274c1a3447559d734cb66e7da6279cf4c1`.

| Material | Kind | Full content |
|---|---|---|
| `component` | component | [component.yaml](../../../jiuwenswarm/factory/ccs/expert_streaming/components/inflight_join/component.yaml) |
| `patch_11` | component | [11-inflight-join.patch](../../../jiuwenswarm/factory/ccs/expert_streaming/components/inflight_join/11-inflight-join.patch) |

<details>
<summary>Full declaration: inputs, outputs, bindings, needs and effects</summary>

```yaml
cc: '2'
id: factory.components.inflight_join
version: 1.0.0
materials:
  component:
    kind: component
    path: component.yaml
  patch_11:
    kind: component
    path: 11-inflight-join.patch
```

</details>

### factory.components.mmap_advice

Version **1.1.0**. [Canonical declaration](../../../jiuwenswarm/factory/ccs/expert_streaming/components/mmap_advice/cc.yaml). SHA-256: `07679d78211ba5384340abfb55381f660e96428201c411d959539622dac45647`.

| Material | Kind | Full content |
|---|---|---|
| `component` | component | [component.yaml](../../../jiuwenswarm/factory/ccs/expert_streaming/components/mmap_advice/component.yaml) |
| `patch_01` | component | [01-mmap-advice-random.patch](../../../jiuwenswarm/factory/ccs/expert_streaming/components/mmap_advice/01-mmap-advice-random.patch) |

<details>
<summary>Full declaration: inputs, outputs, bindings, needs and effects</summary>

```yaml
cc: '2'
id: factory.components.mmap_advice
version: 1.1.0
materials:
  component:
    kind: component
    path: component.yaml
  patch_01:
    kind: component
    path: 01-mmap-advice-random.patch
```

</details>

### factory.components.phase_stats

Version **1.0.0**. [Canonical declaration](../../../jiuwenswarm/factory/ccs/expert_streaming/components/phase_stats/cc.yaml). SHA-256: `4c2f774b7ecb3a94b07ef1d2409f68ce910c6594ce2cca75b81d10e95789b469`.

| Material | Kind | Full content |
|---|---|---|
| `component` | component | [component.yaml](../../../jiuwenswarm/factory/ccs/expert_streaming/components/phase_stats/component.yaml) |
| `patch_16` | component | [16-phase-rusage.patch](../../../jiuwenswarm/factory/ccs/expert_streaming/components/phase_stats/16-phase-rusage.patch) |

<details>
<summary>Full declaration: inputs, outputs, bindings, needs and effects</summary>

```yaml
cc: '2'
id: factory.components.phase_stats
version: 1.0.0
materials:
  component:
    kind: component
    path: component.yaml
  patch_16:
    kind: component
    path: 16-phase-rusage.patch
```

</details>

### factory.components.router_prefetch

Version **1.1.0**. [Canonical declaration](../../../jiuwenswarm/factory/ccs/expert_streaming/components/router_prefetch/cc.yaml). SHA-256: `e96980a425cbe5d455e4d5520d85b90f1a06619cb88e6dfbbb84b392cf044913`.

| Material | Kind | Full content |
|---|---|---|
| `component` | component | [component.yaml](../../../jiuwenswarm/factory/ccs/expert_streaming/components/router_prefetch/component.yaml) |
| `patch_02` | component | [02-router-prefetch.patch](../../../jiuwenswarm/factory/ccs/expert_streaming/components/router_prefetch/02-router-prefetch.patch) |

<details>
<summary>Full declaration: inputs, outputs, bindings, needs and effects</summary>

```yaml
cc: '2'
id: factory.components.router_prefetch
version: 1.1.0
materials:
  component:
    kind: component
    path: component.yaml
  patch_02:
    kind: component
    path: 02-router-prefetch.patch
```

</details>

### factory.components.thread_names

Version **1.1.0**. [Canonical declaration](../../../jiuwenswarm/factory/ccs/expert_streaming/components/thread_names/cc.yaml). SHA-256: `d1a7859f21583659a710ce619f2b0fffcf5b7df9ce3bd100711380e40bb9b40c`.

| Material | Kind | Full content |
|---|---|---|
| `component` | component | [component.yaml](../../../jiuwenswarm/factory/ccs/expert_streaming/components/thread_names/component.yaml) |
| `patch_09` | component | [09-thread-names.patch](../../../jiuwenswarm/factory/ccs/expert_streaming/components/thread_names/09-thread-names.patch) |

<details>
<summary>Full declaration: inputs, outputs, bindings, needs and effects</summary>

```yaml
cc: '2'
id: factory.components.thread_names
version: 1.1.0
materials:
  component:
    kind: component
    path: component.yaml
  patch_09:
    kind: component
    path: 09-thread-names.patch
```

</details>

### factory.integration_skill

Version **1.0.0**. [Canonical declaration](../../../jiuwenswarm/factory/ccs/integration_skill/cc.yaml). SHA-256: `1380d5afae34b437e036bf01228527b164f69ed9ce303f7c819605de3757e559`.

| Material | Kind | Full content |
|---|---|---|
| `integrate` | skill | [INTEGRATE.md](../../../jiuwenswarm/factory/ccs/integration_skill/INTEGRATE.md) |
| `repair` | skill | [REPAIR.md](../../../jiuwenswarm/factory/ccs/integration_skill/REPAIR.md) |
| `preflight` | skill | [PREFLIGHT.md](../../../jiuwenswarm/factory/ccs/integration_skill/PREFLIGHT.md) |

<details>
<summary>Full declaration: inputs, outputs, bindings, needs and effects</summary>

```yaml
cc: '2'
id: factory.integration_skill
version: 1.0.0
materials:
  integrate:
    kind: skill
    path: INTEGRATE.md
  repair:
    kind: skill
    path: REPAIR.md
  preflight:
    kind: skill
    path: PREFLIGHT.md
```

</details>

### factory.lab_client

Version **1.0.0**. [Canonical declaration](../../../jiuwenswarm/factory/ccs/lab_client/cc.yaml). SHA-256: `9b65cd64065f463eb46cde3825e3a589773fb4246582d6a2c3e1cf7a38a5bebc`.

Native entry point: [run.py](../../../jiuwenswarm/factory/ccs/lab_client/run.py).

**`submit`**: Admit a local image and submit a fixed lab evaluation through the GPU queue. run_config may include profile nsys to trace the run with Nsight Systems; the result then carries a kernel, CUDA API and OS-runtime breakdown. Traced timing is perturbed and is never speed evidence.

Inputs: `image`, `build_attempt_id`, `contract_id`, `run_config`, `idem_key`, `node_id`. Outputs: `admission`, `attempt_id`, `state`, `jobq_id`.

**`status`**: Read the owned lab attempt from the durable queue.

Inputs: `attempt_id`. Outputs: `attempt_id`, `task_id`, `kind`, `idem_key`, `fingerprint`, `request`, `state`, `jobq_id`, `owner`, `started`, `ended`, `resources`, `result_refs`, `cleanup_state`, `history`.

**`cancel`**: Cancel the owned lab attempt and reap its container.

Inputs: `attempt_id`. Outputs: `attempt_id`, `task_id`, `kind`, `idem_key`, `fingerprint`, `request`, `state`, `jobq_id`, `owner`, `started`, `ended`, `resources`, `result_refs`, `cleanup_state`, `history`.

**`result`**: Read evaluation and evidence references for the owned lab attempt.

Inputs: `attempt_id`. Outputs: `attempt_id`, `state`, `result_refs`, `execution_outcome`, `evaluation`, `evidence_refs`.

**`ab_submit`**: Admit both images and queue one contract-bound ABBA experiment; checks come from component materials.

Inputs: `base_image`, `candidate_image`, `base_env`, `candidate_env`, `rounds`, `component`, `idem_key`, `node_id`. Outputs: `attempt_id`, `task_id`, `kind`, `idem_key`, `fingerprint`, `request`, `state`, `jobq_id`, `owner`, `started`, `ended`, `resources`, `result_refs`, `cleanup_state`, `history`.

**`ab_status`**: Read the owned durable A/B job status.

Inputs: `attempt_id`. Outputs: `attempt_id`, `task_id`, `kind`, `idem_key`, `fingerprint`, `request`, `state`, `jobq_id`, `owner`, `started`, `ended`, `resources`, `result_refs`, `cleanup_state`, `history`.

**`ab_result`**: Ingest and read verified A/B verdict, correctness and evidence.

Inputs: `attempt_id`. Outputs: `attempt_id`, `state`, `result_refs`, `execution_outcome`, `evaluation`, `evidence_refs`, `ab_result`.

<details>
<summary>Full declaration: inputs, outputs, bindings, needs and effects</summary>

```yaml
cc: '2'
id: factory.lab_client
version: 1.0.0
bindings:
  default:
    kind: native
    command:
    - '{python}'
    - '{bundle}/run.py'
capabilities:
  submit:
    kind: tool
    does: Admit a local image and submit a fixed lab evaluation through the GPU queue.
      run_config may include profile nsys to trace the run with Nsight Systems; the
      result then carries a kernel, CUDA API and OS-runtime breakdown. Traced timing
      is perturbed and is never speed evidence.
    takes:
      image: json
      build_attempt_id: text
      contract_id: text
      run_config: json
      idem_key: text
      node_id:
        kind: text
        optional: true
    gives:
      admission: json
      attempt_id: text
      state: text
      jobq_id: json
    needs:
    - python
    changes:
    - process.exec
  status:
    kind: tool
    does: Read the owned lab attempt from the durable queue.
    takes:
      attempt_id: text
    gives:
      attempt_id: text
      task_id: text
      kind: text
      idem_key: text
      fingerprint: text
      request: json
      state: text
      jobq_id: json
      owner: json
      started: json
      ended: json
      resources: json
      result_refs: json
      cleanup_state: text
      history: json
    needs:
    - python
    changes:
    - process.exec
  cancel:
    kind: tool
    does: Cancel the owned lab attempt and reap its container.
    takes:
      attempt_id: text
    gives:
      attempt_id: text
      task_id: text
      kind: text
      idem_key: text
      fingerprint: text
      request: json
      state: text
      jobq_id: json
      owner: json
      started: json
      ended: json
      resources: json
      result_refs: json
      cleanup_state: text
      history: json
    needs:
    - python
    changes:
    - process.exec
  result:
    kind: tool
    does: Read evaluation and evidence references for the owned lab attempt.
    takes:
      attempt_id: text
    gives:
      attempt_id: text
      state: text
      result_refs: json
      execution_outcome: text
      evaluation: json
      evidence_refs: json
    needs:
    - python
    changes:
    - process.exec
  ab_submit:
    kind: tool
    does: Admit both images and queue one contract-bound ABBA experiment; checks come
      from component materials.
    takes:
      base_image: json
      candidate_image: json
      base_env: json
      candidate_env: json
      rounds: json
      component: text
      idem_key: text
      node_id:
        kind: text
        optional: true
    gives:
      attempt_id: text
      task_id: text
      kind: text
      idem_key: text
      fingerprint: text
      request: json
      state: text
      jobq_id: json
      owner: json
      started: json
      ended: json
      resources: json
      result_refs: json
      cleanup_state: text
      history: json
    needs:
    - python
    changes:
    - process.exec
  ab_status:
    kind: tool
    does: Read the owned durable A/B job status.
    takes:
      attempt_id: text
    gives:
      attempt_id: text
      task_id: text
      kind: text
      idem_key: text
      fingerprint: text
      request: json
      state: text
      jobq_id: json
      owner: json
      started: json
      ended: json
      resources: json
      result_refs: json
      cleanup_state: text
      history: json
    needs:
    - python
    changes:
    - process.exec
  ab_result:
    kind: tool
    does: Ingest and read verified A/B verdict, correctness and evidence.
    takes:
      attempt_id: text
    gives:
      attempt_id: text
      state: text
      result_refs: json
      execution_outcome: text
      evaluation: json
      evidence_refs: json
      ab_result: json
    needs:
    - python
    changes:
    - process.exec
```

</details>

### factory.methodology_ab

Version **1.0.0**. [Canonical declaration](../../../jiuwenswarm/factory/ccs/methodology_ab/cc.yaml). SHA-256: `c6c88e675295e4931c730f5271e5439fc9cac7b08451faa4989d1b1e3c19b88d`.

| Material | Kind | Full content |
|---|---|---|
| `methodology` | method | [AB.md](../../../jiuwenswarm/factory/ccs/methodology_ab/AB.md) |

<details>
<summary>Full declaration: inputs, outputs, bindings, needs and effects</summary>

```yaml
cc: '2'
id: factory.methodology_ab
version: 1.0.0
materials:
  methodology:
    kind: method
    path: AB.md
```

</details>

## CC runtime examples, not Jetson campaign components

| CC | Version | Binding | Capabilities |
|---|---|---|---|
| [demo.compute_service](../../../demo/ccs/compute_service/cc.yaml) | 1.0.0 | image | `api` |
| [demo.methodology](../../../demo/ccs/methodology/cc.yaml) | 1.0.0 | material-only | None |
| [demo.service_client](../../../demo/ccs/service_client/cc.yaml) | 1.0.0 | native | `benchmark` |
| [demo.workspace_inspect](../../../demo/ccs/workspace_inspect/cc.yaml) | 1.0.0 | native | `inspect` |

### demo.compute_service

Version **1.0.0**. [Canonical declaration](../../../demo/ccs/compute_service/cc.yaml). SHA-256: `178eb98ab566edec91d0c483601caf379fd1f686e467b3891512183673c319dc`.

**`api`**: Serve synthetic multiplication with its own pinned OS and Python independent of the host. A published Docker bridge port cannot enforce no-egress, so network.request is required.

Inputs: none declared. Outputs: none declared.

<details>
<summary>Full declaration: inputs, outputs, bindings, needs and effects</summary>

```yaml
cc: '2'
id: demo.compute_service
version: 1.0.0
bindings:
  default:
    kind: image
    image: sha256:ec5b1df28d09604bf8895fbd83a423165d4970c90a7fed72a57e3bd5142f6551
    command: []
capabilities:
  api:
    does: Serve synthetic multiplication with its own pinned OS and Python independent of the host. A published Docker bridge port cannot enforce no-egress, so network.request is required.
    changes: [process.exec, network.listen, network.request]
    serves:
      interfaces:
        api: {protocol: http, port: 8080, path: '/', contract: api.json}
      ready: {interface: api, path: /health}
```

</details>

### demo.methodology

Version **1.0.0**. [Canonical declaration](../../../demo/ccs/methodology/cc.yaml). SHA-256: `ed8acf03f1048c8b019bb919c8d622988566973b2e79530422a8d5dbdebd0ef2`.

| Material | Kind | Full content |
|---|---|---|
| `method` |  | [METHOD.md](../../../demo/ccs/methodology/METHOD.md) |
| `limits` |  | [LIMITS.md](../../../demo/ccs/methodology/LIMITS.md) |

<details>
<summary>Full declaration: inputs, outputs, bindings, needs and effects</summary>

```yaml
cc: '2'
id: demo.methodology
version: 1.0.0
materials:
  method:
    path: METHOD.md
    media_type: text/markdown
    description: Agent workflow for evaluating the synthetic served compute demo.
  limits:
    path: LIMITS.md
    media_type: text/markdown
    description: Interpretation and evidence limits.
```

</details>

### demo.service_client

Version **1.0.0**. [Canonical declaration](../../../demo/ccs/service_client/cc.yaml). SHA-256: `0b4fba7f950f5ffaa5cf30c1892e3af47b9947ff39c1537a87dcb98c74a39ae7`.

**`benchmark`**: Record synthetic loopback client timings, NOT inference-engine TTFT or token-rate evidence; retain successful rows even on request failure.

Inputs: `engine`, `workload`. Outputs: `metrics`, `series`.

<details>
<summary>Full declaration: inputs, outputs, bindings, needs and effects</summary>

```yaml
cc: '2'
id: demo.service_client
version: 1.0.0
bindings:
  default:
    kind: native
    command: ['{python}', '{bundle}/client.py']
capabilities:
  benchmark:
    does: Record synthetic loopback client timings, NOT inference-engine TTFT or token-rate evidence; retain successful rows even on request failure.
    takes:
      engine: handle
      workload:
        kind: json
        schema:
          type: object
          required: [points]
          properties:
            points: {type: array, items: {type: number}}
          additionalProperties: false
    gives: {metrics: json, series: artifact}
    needs: [environment]
    changes: [network.request]
```

</details>

### demo.workspace_inspect

Version **1.0.0**. [Canonical declaration](../../../demo/ccs/workspace_inspect/cc.yaml). SHA-256: `d0715aceebfaaedb6a3242b34d70ec95b81e6b9ecd939aa1901f14884d879b7a`.

**`inspect`**: Read a bounded workspace inventory and retain its full summary without modifying the workspace.

Inputs: `workspace`, `max_files`. Outputs: `report`, `summary`.

<details>
<summary>Full declaration: inputs, outputs, bindings, needs and effects</summary>

```yaml
cc: '2'
id: demo.workspace_inspect
version: 1.0.0
bindings:
  default:
    kind: native
    command: ['{python}', '{bundle}/inspect.py']
capabilities:
  inspect:
    does: Read a bounded workspace inventory and retain its full summary without modifying the workspace.
    takes:
      workspace: handle
      max_files:
        kind: json
        optional: true
        description: Maximum ordinary files to inspect; defaults to 2000.
        schema: {type: integer, minimum: 0}
    gives: {report: json, summary: artifact}
    needs: [workspace]
    changes: [workspace.read]
```

</details>

## Limits and provenance

Material links and full declarations are the source reference, not a promise that every dependency is available on a new machine. Component defaults are historical configurations, not universal tuning recommendations. `factory.engine_component` is the earlier thread-naming component bundle; the nested expert-streaming entries are distinct declarations. Runtime demo service examples are learning aids, not inference-lab qualification.

The catalog reproduces declaration bytes for review; update it when declarations change. The hashes identify this snapshot. Raw experimental outputs remain in the historical evidence packages and Siminfeng records; they are not recreated here. New Spark CC candidates live outside this branch and are deliberately excluded from its implemented catalog.
