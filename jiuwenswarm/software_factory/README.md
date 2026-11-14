# Executable STRATA Software Factory

This module executes source-bound engineering stages in the existing JiuwenSwarm
project. It is mounted in the host WebChannel by `factory_http.py`; the CLI serves
the identical API for local construction without starting the chat/model gateway.
The existing Sidebar → Workflow page consumes this API and SSE.

## Start

From the repository root, with Python 3.11+ and FastAPI/Uvicorn installed:

```sh
python -m jiuwenswarm.software_factory.cli --root /workspace/factory-runs --serve --host 127.0.0.1 --port 19000
```

From `jiuwenswarm/channels/web/frontend`, in another terminal:

```sh
npm ci
FRONTEND_PORT=5175 npm run dev
```

Open the main application at port 5175 and select Workflow. The factory view uses
HTTP/SSE; its errors are independent of the chat gateway's WebSocket connection.
In a full protected host, HTTP mounts reuse its session authority and run owners.

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
