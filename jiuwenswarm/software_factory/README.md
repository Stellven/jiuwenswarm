# Executable STRATA Software Factory

JiuwenSwarm serves the live Workflow Factory from its existing WebChannel. The
host account owns the task, execution events and generated Product. The Sidebar
→ Workflow page submits requests to the same-origin Factory API.

## Start the M1 host

Use the [M1 Docker setup](../../deploy/m1/OPERATIONS.md) from this checkout. To
build and start the app service for Workflow development:

```sh
docker compose -p ai4r-workflow -f deploy/m1/compose.benchmark-runner.yaml build ai4r
docker compose -p ai4r-workflow -f deploy/m1/compose.benchmark-runner.yaml up -d ai4r
```

Open the private host bootstrap URL from the M1 launcher and enter **Workflow**
in the host sidebar. Select **STRATA build** to submit a fresh build, or **Workflow
Library** to submit a task over registered contracts. A signed-in host session
with submission permission is required. Agent-mode operations additionally use
the configured model runtime.

**STRATA build** submits a new task with requested output types and numeric inputs.
The service prepares the pinned STRATA and GoogleTest library, admits a new graph,
and runs its build actions and selected subworkflows. The generated Ascend source,
compiled CPU executable, and component outputs are recorded independently.
Open **Product** from a verified run to inspect its source tree or download its ZIP.
**Guided example** opens the packaged recording through the same host.
Open **Compose** to see how the Planner chose the steps. Then open **Scheduling**
to inspect the same Task Graph JSON and see the selected Builder for each step.
**Construction** plays the real execution that followed those assignments.

In **Workflow Library**, choose **Match required outputs** to plan a task over
the registered Library. Set `required_outputs` to the desired artifact kinds.
Use `step_parameters` to supply values to a selected part by its
`<workflow>.<subworkflow>` ID. **Agent planning** uses the configured model.
Both methods admit the same versioned graph format and use the same executor.

To extract source candidates from another pinned Python project, pass its Git
checkout, commit and package directory to the source extractor:

```sh
python -m jiuwenswarm.software_factory.python_source_extraction \
  --checkout path/to/skydiscover \
  --revision 0d932b690670a7e544388ad362e9876c8bd256a0 \
  --package skydiscover --output catalog.json
```

The catalog contains original definitions, their parameters and references to
statically resolved call sites. A candidate needs a registered contract and
executable entry point before the Planner can schedule it.

The live runner can reuse clean checkouts of the exact pinned upstream revisions
when operators set `JIUWENSWARM_FACTORY_STRATA_CHECKOUT` and
`JIUWENSWARM_FACTORY_GOOGLETEST_CHECKOUT`. Otherwise it acquires the pinned sources.
CMake and a C++ compiler must be available to the service.

## Local frontend and Factory checks

For isolated development on a machine with Python 3.11+, Node/npm, Git and a C++
toolchain, the auxiliary `python -m jiuwenswarm.software_factory.demo --build
--port 5175` command serves the same built frontend and Factory API on loopback.
The M1 startup above supplies the normal host account and service lifecycle.

## Workflow Library, Composer and executable graph

The Workflow Library view imports two reviewed open-source projects: STRATA and
GoogleTest. The importer really clones/fetches, fixes a clean commit, reads source,
writes decomposition evidence and factory-owned wrappers, then registers a version.
These wrappers are our reusable capabilities; they are not upstream workflow
declarations. Select a part to inspect its identity, actual Python implementation,
Agent Markdown instruction or upstream source.

The Library is a persistent JSON definition store under
`<root>/workflow-library/definitions/<workflow>/<version>/workflow.json`.
Agent instructions are copied alongside the immutable definition. Each part
declares its named input/output content contracts, executable entrypoint or MD,
requirements, pinned source defaults and verification scope. Python implementation
and dependency bytes are hashed; changing them invalidates the executable version.

The Composer is an actual Codex Agent, governed by
`workflow_prompts/composer_policy.md`. It receives Task Contract and published
artifact identities, requests actual Library reads, explains selections and
proposes references and port bindings. Python admission checks the proposal using
`schemas/task-graph-proposal.schema.json`, exact definitions, compatible ports,
acyclic dependencies and required deliverables. It constructs the Task Graph;
the model cannot invent commands or file-path bindings. There is no static-graph
fallback when model authentication fails.

A Task Graph is a separate per-plan JSON document. Each node has an instance ID,
fixed Workflow ID/version, selected part, declared parameters and input bindings.
A binding points to another node's named output, or to an existing published
artifact. Dependencies are derived from those bindings. Runtime status never
changes the Library definition.

The Scheduler reads the admitted Task Graph JSON and chooses the registered
Builder for each node before execution starts. It records the graph receipt and
the execution reason for each assignment. The Factory uses M1's topological
check and shares the predecessor gate with the M1 research Scheduler. A node
waits for verified dependencies, and a failed producer blocks its consumers.
Python/tool Builders call
their registered code. Agent Builders launch a restricted Codex process with the
pinned MD and input manifests. The Agent must create the declared files. STRATA
construction currently uses Python/tool Builders. Every file is hash/content
checked, copied into its consumer's
workspace and receipted. Missing output, failed command or model failure blocks
dependent work. Logs, PIDs, exit status, stdout/stderr and artifact hashes persist.

The source and test-generation graph may combine STRATA extraction/generation
with GoogleTest framework preparation, Agent test design and actual compilation.
Optional report/package parts are selected only when required. Available receipts
allow another plan to consume an existing result. Composing after a settled run
also supplies its actual failures and artifacts to the Agent and increments the
graph revision; this is a new model decision, not a scripted repair or a timer.

Agent execution requires an installed `codex` CLI and working authenticated model
access. A successful `codex login status` alone does not verify the provider.
Authentication errors remain blocked with real invocation logs. CMake must be
on PATH or configured with `STRATA_FACTORY_CMAKE`; generated CPU reference tests
remain distinct from CANN compilation, device execution and full-model inference.

Library API: `GET /api/v1/factory/library`, `POST /library/import`,
`GET /library/policy`, `POST /library/plan`, `POST /library/execute`, owned
`GET /library/{imports|plans|executions}/{id}` and `/events`, and
`GET /library/artifacts/{execution}/{artifact}` (all under the factory prefix).
Use `?view=workflow&lng=en&libraryPlan=<id>` or `&libraryExecution=<id>` to reopen
saved real observations without dispatching work. Historical Run Replay remains
available separately.

Open **Import History** to see the original GitHub source, the recorded checkout
version and the workflow files written during registration. **Projects & Steps**
shows the current versions and the declared connections between their reusable
parts. Open **Component Checks** to inspect the saved developer-selected execution
and its published source. For the STRATA routing check, the input handoff is
`core_ir.json`, the generated Ascend source is `src/ascend/router.cpp`, and the
later CPU comparison has its own command receipts. GoogleTest was built in a
separate branch of this check. Tests consuming that build still require the
Agent execution. Older Run Replay examples have their own source, graph and
selection records.

This route reuses the host Workflow page and session authority, and invokes the
existing factory's STRATA source extraction and C++ generator. The current Library
planner and executor are new modules. M1's protected Research Planner, native
Scheduler, execution gate and model path still need an actual adapter before
their use in this route can be verified. The shared CC schema preserves donor
definitions. Dispatching those definitions in this route requires a CC adapter.

## Real construction entry

```sh
python -m jiuwenswarm.software_factory.cli --root /workspace/factory-runs \
  --revision 13eedf552417a6a791a7d13c6597e24300ee3a09 \
  --backend cpu --goal construction.package
```

The requested output contract selects stages across source acquisition,
construction, transformation, verification and delivery workflows. This path:

1. Clones only `https://github.com/niko1221/strata`, records the exact SHA and clean source.
2. Executes `scripts/analyze_cuda.py`, reading real C++/CUDA files and writing
   `workspace/analysis/cuda_ops.json`. This is a regex declaration inventory,
   not a compiler AST or a proven migration.
3. Selects `adapters/ast_to_ascend.py` by its declared native-inventory output
   contract. The adapter extracts actual production router, SwiGLU and expert
   aggregation functions, preserving exact source slices, hashes and arithmetic
   expressions in a checked semantic IR. Unsupported semantics stop construction.
4. CodeGen consumes that IR in a real Python subprocess and writes a standalone
   project: `src/strata_core.cpp`, `include/strata_core.h`, `src/main.cpp`, tests,
   original reference excerpts, licenses, and `CMakeLists.txt`.
5. Builds the generated production library, file-input executable and a separate
   arithmetic test executable using CMake/Make. CPU validation is explicit;
   optional Ascend calls require the real SDK and do not imply a full native model.
6. Runs the separate tests against the extracted upstream reference and boundary
   cases, retaining actual stdout/stderr and exit status. These numerical tests
   use test inputs and do not claim real model-weight inference.
7. Packages the built and tested source project as `huawei_native_strata.zip`.
   The frontend displays real original CUDA and generated C++ in Code Diff, and
   downloads the ZIP through the owner-checked artifact endpoint.
8. The `construction.portability` goal unpacks that exact ZIP into another source
   tree, rebuilds it, reruns numerical tests, and runs the generated CLI against
   an external numeric test-input file. This is an explicit isolated arithmetic
   verification, never a model-inference result.

Use `--core router` to construct only the supported routing core. Omitting this
option constructs routing, SwiGLU and weighted expert-output aggregation together.
The generated CLI reads external numeric input files; its README gives the format.
Both projects build independently of the factory and the original STRATA checkout.

## Value Agent

Add `--goal value.report` to assess the actual generated source project. This
artifact goal composes source construction, build, separate numerical validation,
packaging, independent ZIP rebuild and assessment stages. Assessments run after the other requested goals
settle, so unavailable model/native goals are included honestly.

The report inspects the source ZIP bytes and actual graph, consumed artifacts,
commands and outcomes. It records cross-workflow composition and dependency reuse;
it does not invent a speedup or cost saving without a measured comparison.
An optional model interpretation uses the existing configured
`jiuwenswarm.research.providers.native_client` seam with bounded, cited output.
When its runtime/provider is unavailable, the report explicitly identifies its
deterministic provenance and records that no AI model was invoked. Source ZIP
delivery is independent of model availability. The frontend displays the actual
`value.report` file alongside the actual Code Diff and artifact downloads.

Missing build tools select a real toolchain stage; their checked executable paths
are actual inputs on retry. No timers, preset successful traces or fabricated
subprocess results are used. Independent requested goals continue when one branch
fails or is blocked. Unknown capabilities fail rather than becoming success.

## Candidate package and required full inference

```sh
python -m jiuwenswarm.software_factory.cli --root /workspace/factory-runs \
  --revision 13eedf552417a6a791a7d13c6597e24300ee3a09 --backend ascend \
  --goal construction.package --goal inference.result --goal verification.comparison
```

The source ZIP contains the generated core project. The independent legacy
`candidate.package` goal retains the modified upstream expert candidate archive.
Neither package is a complete Ascend model implementation. Core validation records
`full_inference_validated: false`; full-model goals retain their actual blocked
states when implementation, devices, SDK or model prerequisites are absent.

The current native source implements canonical Q2_0 expert projections/SwiGLU via
CANN calls with STRATA quantization boundaries. It does not yet implement the full
Ascend embedding/dense/router/QSA/GDN/cache/decoding graph, native IQ/K-quant packs,
or a complete Ascend generation engine. Missing SDK/device/model and unimplemented
full-model operations remain BLOCKED. CPU mathematical parity is not device parity.

Native acceptance requires the actual CANN build, device loading, native operator
execution, supported complete model pack, model generation and same-input original
backend comparison. Keep these layers separate; never replace them with component
checks, initialization, a report, an API response or a fixed answer.

## API and events

- `GET /api/v1/factory/catalog`: executable stage declarations, lineage, ports, tools and validators.
- `POST /api/v1/factory/runs`: goals, fixed upstream, optional SHA/model path and backend.
- `GET /api/v1/factory/runs/{id}`: actual graph, attempts, commands, artifacts and per-goal results.
- `GET /api/v1/factory/runs/{id}/stream?after=N`: authenticated SSE snapshot and ordered factory events.
- `GET /api/v1/factory/runs/{id}/artifacts/{artifact_id}`: verified published file bytes.

Events include `stage.started`, `command.output` (real stdout/stderr pipe chunks),
`schema.mismatch`, `adapter.injected`, `graph.updated`, `stage.verified` and real
failed/blocked/terminal decisions. The frontend refreshes only on actual server
events, not polling timers. It exposes graph history, all stage attempts, terminal
output and authenticated artifact downloads. Run/event records are in each run's
`run.json` and `events.jsonl`; commands and full logs live below its stage directory.

## Checks

```sh
python -m unittest discover -s tests/software_factory -v
```

From the frontend directory:

```sh
npm run test:workflow-demo
npm run build
FACTORY_RUN_ID=<actual-construction-and-value-run-id> python tests/workflow-demo-browser.py
```

The browser check uses the real local factory, real git/process execution and
actual artifact downloads. Backend unit tests isolate stages only inside tests.
