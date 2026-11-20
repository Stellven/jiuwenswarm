# Factory runs web API

The web channel mounts `/api/factory`. Reads reuse the factory's story, graph,
monitor, telemetry and redaction helpers. They do not initialize a controller.
Live SQLite and WAL are copied with stable size/mtime checks; the story reads the
same validated snapshot. No source database is opened for writes.

Operator configuration:

- `FACTORY_RUN_ROOTS`: OS path separator delimited allowed roots. Defaults to
  `~/predemo-spark/factory-runs` and the existing `factory-loop-v1` export root.
  Discovery descends at most four directories and stops at each bundle/home.
  Include any external live contract directory among these roots.
- `FACTORY_LAUNCH_ROOT`: directory of reviewed task JSON templates (opt-in).
- `FACTORY_LAUNCH_HOME_ROOT`: dedicated new-home directory beneath a run root.

Endpoints:

- `GET /runs`: runs with opaque IDs, kind, objective and task ID; available
  template IDs and launch configuration status.
- `GET /runs/{id}`: sanitized records, contract, native graph, component stack,
  telemetry, complete story projection, metadata and file digest inventory.
- `GET /runs/{id}/story?since=N`: story projection with numeric cursor/total.
  `reset: true` for subsequent polls means replace the prior projection, since
  later decisions can revise earlier story summaries. Never append a reset page.
- `GET /runs/{id}/file?path=...`: sanitized text, raw file SHA256, expected SHA256,
  integrity and size. Text truncates at 16 MiB; the hash covers the entire file.
- `POST /launch` with exactly `{"template_id":"reviewed-template"}`: initialize
  that operator-prepared task in a unique new home and start a detached
  `jiuwenswarm-factory run`. The template's allowed effects become the explicit
  CLI grants; the HTTP request cannot choose commands, effects or paths. Launch
  returns the new run ID, task ID and PID. Logs survive gateway/browser restarts.

Missing/mismatched manifest files remain visible. `MANIFEST.json` itself and
unlisted files have `untracked` status; that status does not assert provenance.
Digests describe original bytes, while displayed content is sanitized. Symlink
bundles and paths outside the evidence root are rejected. Live file browsing is
limited to recorded artifacts and that task's session/launch log.

Launching does not provision credentials. The operator must prepare authentication
and review template resource/GPU policy before enabling launch. HTTP reads never
launch jobs. Browser POST requests require same-origin Host/Origin. The gateway
must remain on localhost behind the demo frontend proxy.
