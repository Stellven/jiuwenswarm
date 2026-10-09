# Standalone Intent Compiler

This isolated component captures local intake, runs the four bounded work/review assignments, and releases Research Brief 2.0.0 only after durable node acceptance. It imports no existing application implementation. The browser, headless client and benchmark API use the same server-owned workflow. Current verification status and live/container limitations are recorded in [native tasks](../../docs/code/Missions/M0/M0-001/tasks.md).

## Prepare and start locally

From the repository root, install the pinned Python lock in a virtual environment and build the browser assets:

```powershell
python -m venv .venv-intent
.venv-intent/Scripts/python.exe -m pip install -r standalone/intent_compiler/requirements.lock
npm --prefix standalone/intent_compiler/frontend ci
npm --prefix standalone/intent_compiler/frontend run build
$env:PYTHONPATH = 'standalone/intent_compiler'
$env:INTENT_STATE_DIR = 'D:/permitted/intent-state'
$env:INTENT_INPUT_ROOT = 'D:/permitted/intent-input'
$env:INTENT_INPUT_DIRECTORY = 'D:/permitted/intent-input/docs'
$env:INTENT_AUTH_TOKEN_FILE = 'D:/protected/intent-control-token.txt'
$env:INTENT_CODEX_PATH = 'D:/approved/codex.exe'
.venv-intent/Scripts/python.exe -m intent_compiler serve
```

Prepare the input directory and a protected random operator-token file before launch. Use the approved authenticated Codex executable; preserve the configured model identity with `INTENT_MODEL_NAME` only when explicitly selected. The local default URL is `http://127.0.0.1:5173`. Enter the operator token in the browser; it stays in tab memory, outside URLs, browser storage and evidence. Authentication success is distinct from mandatory model/enforcement readiness. An unavailable mandatory boundary blocks production execution.

For a labelled fixture smoke journey, the operator may set `INTENT_MODEL_MODE=smoke` and `INTENT_PROFILE_ID=compiler-smoke` before starting. The UI and exports mark it invalid for product acceptance. Clients cannot enable smoke, inject outputs or change checks. Switch back to `codex` / `compiler-only` for actual-model verification. Fixture completion does not establish semantic model quality.

## Finite headless client

The client uses `INTENT_AUTH_TOKEN_FILE` or `INTENT_AUTH_TOKEN`, with the same account/workspace scope as the server:

```powershell
.venv-intent/Scripts/python.exe -m intent_compiler readiness
.venv-intent/Scripts/python.exe -m intent_compiler run --request-file 'D:/permitted/request.txt' --client-request-id case-001 --profile compiler-only --timeout 600 --export 'D:/permitted/exports/case-001.zip'
.venv-intent/Scripts/python.exe -m intent_compiler reconcile case-001
.venv-intent/Scripts/python.exe -m intent_compiler status RUN_ID
.venv-intent/Scripts/python.exe -m intent_compiler cancel RUN_ID
.venv-intent/Scripts/python.exe -m intent_compiler export RUN_ID 'D:/permitted/exports/run.zip'
.venv-intent/Scripts/python.exe -m intent_compiler result RUN_ID
```

Pass reference documents with `--documents-json '[{"path":"paper.md","required":true}]'`; paths are confined to the operator's authorized input root. Resources use `--resources-json '[{"path":"validation.csv","role":"validation_data","required":true}]'`. Valid resource roles are `reference_document`, `project_asset` and `validation_data`. `--seed` records requested seed; unsupported effective seed remains null. `--previous-run-id` links corrected input to a failed/cancelled/paused prior run without changing history.

Reference documents supplied through either input field support `.txt`, `.md` and readable, unencrypted `.pdf` files. The host preserves their original bytes and extracts bounded reasoning text; required unsupported or unreadable documents reject before model dispatch, while optional failures remain disclosed. Supplied license metadata stays in the resource snapshot. Project assets and validation data are captured separately for resource binding and do not enter the compiler's reasoning text.

Exit codes: `0` successful operation/released run; `2` terminal run halt/cancel/pause; `3` compatibility/authentication/profile/readiness or submission rejection; `4` finite monitoring timeout; `5` transport/local-input failure. On halt, the client retrieves available evidence and exits without human input. Ambiguous submission transport is reconciled once by request ID, never automatically resubmitted. A client timeout or closed browser does not cancel server work.

## Authenticated API and benchmark contract

All `/api/v1/*` routes require `Authorization: Bearer TOKEN`. Optional `X-Account-ID` and `X-Workspace-ID` must match the credential scope. Browser requests require same origin; no CORS route is enabled. Readiness and status implement the supplied closed field contracts. Additional compiler fields live under `ext["m0.intent"]`.

| Route | Operation |
| --- | --- |
| `GET /api/v1/readiness` | Instance/build/interface/payload versions, approved profile and authentication/storage/model/enforcement states |
| `POST /api/v1/runs` | Protected raw intake wrapper; uniquely identified submission, qualification and one server-owned run |
| `GET /api/v1/requests/{client_request_id}` | Reconcile uncertain delivery without dispatch |
| `GET /api/v1/runs/{run_id}` | Monotonic correlated lifecycle, candidate/accepted refs and gate reasons |
| `POST /api/v1/runs/{run_id}/cancel` | Explicit scoped cancellation; body has `schema_version`, `id`, `request_id`, `run_id` |
| `GET /api/v1/runs/{run_id}/manifest` | Catalog client-retrieval manifest, exact named files, redactions and missing evidence |
| `GET /api/v1/runs/{run_id}/bundle` | ZIP containing manifest and exact immutable file bytes |
| `GET /api/v1/runs/{run_id}/artifacts/{artifact_id}` | Audience-authorized exact captured bytes; IDs may include confined path segments |
| `GET /api/v1/runs/{run_id}/result` | Bounded consumer: exact node-released Brief2 only; candidates/unsupported versions reject |

The HTTP submission body is a transport wrapper for original intake, rather than the catalog's canonical `client-submission` record. The host qualifies inputs and captures complete `Client_Submission.json` with required `intake_ref` and protected `configuration_ref`. The client cannot author those references or release state. The response's `ext["m0.intent"]["submission_ref"]` points to this normative record.

A concrete Python API call, independent of the headless client:

```python
import os, pathlib, httpx
token = pathlib.Path(os.environ['INTENT_AUTH_TOKEN_FILE']).read_text().strip()
with httpx.Client(base_url='http://127.0.0.1:5173', headers={'Authorization': 'Bearer ' + token}) as client:
    ready = client.get('/api/v1/readiness').json()
    assert ready['ready'], ready['prerequisites']
    profile = ready['ext']['m0.intent']
    response = client.post('/api/v1/runs', json={
        'schema_version': '1.0.0', 'id': 'submission:case-001', 'client_request_id': 'case-001',
        'account_id': profile['account_id'], 'workspace_id': profile['workspace_id'],
        'profile_id': profile['profile_id'], 'expected_instance_id': ready['instance_id'],
        'expected_build_id': ready['build_id'], 'client_contract_version': '1.0.0',
        'request': 'Compare method A against baseline B on the supplied validation data.',
        'documents': [], 'resources': [{'path': 'validation.csv', 'role': 'validation_data', 'required': True}],
    })
    response.raise_for_status()
    run_id = response.json()['run_id']
    print(client.get('/api/v1/requests/case-001').json())
    # Observe status until terminal, then retrieve manifest/bundle/result.
```

Exports retain qualified/original inputs, candidates, assessments/checks, contracts/admission/implementation/dependency pins, actual observations/settings and protected decisions/acceptance. Immutable derived `Run_Bundle.json` snapshots use catalog fields and state their actual lifecycle/missing evidence; generating an export does not alter authoritative gate state. A valid schema or a candidate file never grants external consumption. Default `single_gpu` describes an assumption, not observed GPU readiness. Unknown usage/cost remains unavailable.

## Single-image deployment

The Dockerfile builds TypeScript and installs Python/Codex dependencies before runtime startup. The native CLI version is pinned to the locally observed and registry-verified `0.162.0-alpha.2`; base images are explicit versions. The build selects the package's Linux x64/arm64 ELF executable and checks `--version`. Runtime calls that executable directly, so the bounded model process does not start the npm Node wrapper. Image build/start/recreation require actual Docker verification and are not established by the local frontend build.

Prepare a readable input root containing `docs/`, an operator token file, and approved native CLI `auth.json`; set `INTENT_INPUT_ROOT`, `INTENT_AUTH_TOKEN_FILE`, and `INTENT_CODEX_AUTH_FILE` in the launching environment. Then:

```powershell
docker compose -f standalone/intent_compiler/compose.yaml build
docker compose -f standalone/intent_compiler/compose.yaml up -d
docker compose -f standalone/intent_compiler/compose.yaml restart
```

The image entrypoint starts browser/API/runtime together. Compose publishes `127.0.0.1:5173:5173`, persists private state and model-home volumes, mounts permitted inputs read-only, and supplies secrets outside exports. The model uses owned stdin/stdout IPC; no public model-adapter endpoint or Docker socket is exposed. Runtime startup performs no downloads. Ensure secret files are readable by container UID 10001; local Compose secret ownership depends on the host runtime. Missing authentication/enforcement/storage is visible through readiness. Restart pauses interrupted runs with no automatic replay. Replaceable container cleanup must retain named evidence volumes.

## Verification

```powershell
$env:PYTHONPATH = 'standalone/intent_compiler'
.venv-intent/Scripts/python.exe -m pytest -c standalone/intent_compiler/pytest.ini standalone/intent_compiler/tests -q
npm --prefix standalone/intent_compiler/frontend ci
npm --prefix standalone/intent_compiler/frontend run build
```

API tests exercise real store/runtime/check connections with explicitly labelled model fixtures. Browser and actual-model/container evidence remain separate required checks in the native task.
