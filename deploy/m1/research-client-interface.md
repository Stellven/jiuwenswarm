# Supported research HTTP interface v1

All routes use `Authorization: Bearer <token>` from an operator-provided private
credential file. The runner uses `ResearchClient`; it imports only HTTP and
neutral `research_records` contracts. Credentials never appear in case files or
exports. The endpoint is configurable; the local app uses port **5175**.

For a virtual-hosted API, the network endpoint and HTTP authority can differ.
Set optional `AI4R_HTTP_AUTHORITY=127.0.0.1:5175` (or CLI `--http-authority`) when
the runner connects through the private Compose endpoint `http://ai4r:5173`.
`ResearchClient(..., http_authority=...)` sends that exact `Host` header while
connecting to the configured endpoint; values must be a hostname/IP with an
optional port, without a scheme, path, userinfo or whitespace. The campaign
persists this authority alongside the endpoint and build identity. Resume
retains it and refuses a conflicting configured authority. This preserves the
app's existing exact browser-origin and scoped bearer checks.

After the final app startup, the OS operator provisions a separate finite
ordinary runner grant using the app image. Mount the existing account volume at
`/var/lib/ai4r-accounts` and a dedicated root-owned credential directory at
`/operator`; run the issuer as UID 0 with the app entrypoint overridden:

```sh
/opt/venv/bin/python -m jiuwenswarm.research.runner_grants issue \
  --binding-file /operator/binding.json --output /operator/runner-token
```

The root-owned mode-0600 binding file contains exactly
`{"schema":"ai4r-runner-grant:1","account_id":"<actual account>","workspace_id":"<actual workspace>","expires_in_s":86400}`.
The directory must not be group/world writable. The issuer derives authority
from the current native startup, requires its exact account/workspace, and
writes an exclusive mode-0600 token file owned by runner UID 11001. Its stdout
contains only grant metadata; never copy the ordinary browser session token.
Bind the individual issued token read-only into the runner, outside results.
Keep its `grant_id` to revoke explicitly:

```sh
/opt/venv/bin/python -m jiuwenswarm.research.runner_grants revoke --grant-id '<grant_id>'
```

Runner grants expire in at most seven days and become invalid if their native
startup is revoked or restarted. They permit only the ordinary research HTTP
operations below, one initialized workspace and the researcher audience; they
cannot authorize native WebSocket sessions, Settings, Capsule activation,
evaluation profiles or private campaign execution. Issuance leaves the existing
browser session grant in place. Issue again after a planned app restart, before
starting a new campaign; do not modify a campaign's running target.

The account, permitted initialized workspace, operations and export audiences
come from the credential grant. A workspace ID supplied by a case cannot grant
access or create a new app workspace. Ordinary runs capture their own isolated
run input inventory. HTTP intake does not create or alter conversation sessions.

| Operation | Request | Response |
| --- | --- | --- |
| Readiness/build | `GET /api/v1/readiness` | Existing `client-readiness`; includes `build_id`, `instance_id`, pins, prerequisites and supported operation names |
| Scoped defaults | `GET /api/v1/context` | `{schema_version:"1.0.0", defaults:{account_id,workspace_id,configuration_ref,plan_source,profile_id,inputs_ready,...}}` |
| Upload original input | `POST /api/v1/inputs/{docs\|repo\|datasets}` multipart `scope_id`, `file` | Existing `client-upload`; use its `id` in intake |
| Prepare original task | `POST /api/v1/intakes` JSON `{task,upload_refs:[upload_id],workspace_id:null\|string}` | `{schema_version:"1.0.0",intake_ref,qualified:true,workspace_id,submission_defaults}` |
| Submit | `POST /api/v1/runs` | Existing `client-status` |
| Reconcile request | `GET /api/v1/runs?client_request_id=...` | Existing `client-status`, or 404 when no delivered request exists |
| Status | `GET /api/v1/runs/{run_id}` | Existing `client-status` |
| Events | `GET /api/v1/runs/{run_id}/events?after=0` | `{schema_version:"1.0.0",run_id,revision,events,next_after,sampling,metrics,unavailable_metrics}` |
| Cancel | `POST /api/v1/runs/{run_id}/cancel` JSON `{request_id}` | Existing `client-cancellation`; pending containment is not terminal |
| Freeze collection inventory | `GET /api/v1/runs/{run_id}/artifacts?audience=researcher` | Collection manifest below |
| Download original bytes | `GET /api/v1/runs/{run_id}/artifacts/{artifact_id}?audience=researcher` | Streamed octets, `Content-Length`, `X-Content-SHA256` |
| Confirm durable collection | `POST /api/v1/runs/{run_id}/collection-confirmation` JSON `{manifest_sha256,artifacts,audience}` | Idempotent receipt `{schema_version:"1.0.0",run_id,manifest_sha256,audience,status:"confirmed",confirmed_at,retention}` |
| Legacy aggregate export | `GET /api/v1/runs/{run_id}/export?audience=researcher` | Existing `client-retrieval`; request `Accept: application/zip` for original bytes archive |

Prepare intake validates and captures exactly the supplied task and permitted
uploads through the same qualification path as browser submission. It performs
no model request. Build the submission by extending `submission_defaults` with
the returned `intake_ref` and a persisted, stable `client_request_id`; defaults
include the required submission `id` and `interaction_mode:"headless"`.
Do not regenerate a submission or resend it after an uncertain delivery: first
reconcile the persisted client request ID. Reusing that ID with changed content
is a conflict. Headless research that requires a person returns its existing
blocked/halted status; it does not open an interactive prompt in the runner.

The collection manifest contains `schema_version:"1.0.0"`, `run_id`, `audience`,
`artifacts`, `redactions`, `execution_terminal`, `retention`, and
`manifest_sha256`. Each artifact has `artifact_id`, safe relative `path`, `size`
in bytes, lowercase `sha256`, and `media_type`. The manifest hash is SHA256 of
UTF8 JSON excluding `manifest_sha256`, with sorted keys, compact separators,
finite JSON numbers and literal Unicode. The app durably stores the snapshot;
IDs authorize retrieval only within its original owned run and audience.

`ResearchClient.download_artifact(run_id, artifact_id, destination, *, sha256,
size, max_bytes=1073741824, audience="researcher")` streams bounded chunks,
checks size/hash, fsyncs temporary bytes, and atomically publishes without
overwriting existing evidence. Destination parent directories must already
exist and contain no symlinks. Matching existing bytes are reusable after
verification. Failed downloads leave no final file. The runner persists its own
collection manifest before calling `confirm_collection(run_id,
manifest_sha256, artifacts, audience="researcher")` with the exact unchanged
artifact list. Partial, failed and cancelled run artifacts remain collectible.

Large trace inventories can use the existing aggregate ZIP endpoint while
preserving the pinned app build. The runner retains the archive as one physical
file and verifies every member against the authorized manifest: original Ref
identity, SHA256, size, media type and multiplicity must all match. The actual
archive `client_retrieval.json` mapping is saved in a separate inventory record.
Descriptive ordinal evidence paths from older builds may move between exports;
matching bytes alone do not authorize a different original Ref. Central-directory
size/member counts, expanded bytes and individual sizes remain bounded. Unsafe
paths, symlinks, duplicates, encryption, extra/missing identities and malformed
bytes are refused. Trace members remain inside the verified archive. Only
bounded readable text/Markdown copies are extracted; nothing is executed.
Physical file limits cover the archive, inventory and readable copies; a
separate finite archive-member limit covers retained originals. Confirmation
still names the exact original app snapshot after durable verification.

Retention has no automatic expiry or deletion: uncollected snapshots and bytes
remain in the app store, including across app restart, until an explicit future
owned cleanup policy removes them. A confirmation acknowledges one exact
snapshot; it does not delete evidence or acknowledge artifacts produced later.
Current receipts also retain confirmed bytes. Disk/storage errors remain
execution or collection errors, never scientific judgments.

Events project the existing owned run timeline, up to 1000 rows per request;
`next_after` is an observation cursor. The scope is captured workflow activity,
not complete host tracing. CPU/memory/disk/GPU and model usage values unsupported
by this projection are `null` with explicit unavailable names; they are not
zero. Original exposed invocation/model/check evidence is also collected as
artifacts under the existing audience/redaction rules. Consumers must treat
events as observations and use status/cancellation acknowledgments for execution
termination. Error replies retain the existing credential-free `client-error`
contract and 401/403/404/409/422/503/500 status semantics.
