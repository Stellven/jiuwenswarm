# Factory runs web API

The web channel mounts `/api/factory`. Reads reuse the factory's story, graph,
monitor, telemetry and redaction helpers. They do not initialize a controller.
Live SQLite and WAL are copied with stable size/mtime checks; the story reads the
same validated snapshot. No read opens a source database for writes; only the
operator POSTs below write, through the controller.

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
- `POST /runs/{id}/nodes/{node}/hold|release|reopen` with exactly
  `{"reason": "..."}` (nonempty, at most 500 characters): calls
  `Controller(home).operator(task_id, op, node, reason)`, which records an
  operator graph revision (`taskgraph.operator_patch`) and queues an operator note
  for the agent's next turn. Graph refusals (node not held, node done, running
  descendants) return 422 with the controller's reason. Returns the new graph
  revision and the held node IDs.
- `POST /runs/{id}/resume` with no body or `{}`: starts a detached
  `jiuwenswarm-factory resume <task>` with the task's recorded allowed effects
  as grants, the way launch starts a run (systemd scope under
  `FACTORY_LAUNCH_SYSTEMD=1`), appending to `launch.log` and writing
  `resume.json`. Refused with 409 while a controller holds the home lock or when
  the controller outcome is not `paused` or `partial`.

Operator controls apply to live factory homes only. Exported bundles and
curated replays answer 403 and carry `controls: null`. All three use the same
same-origin guard as launch.

`GET /runs/{id}` also carries:

- `node_checks`: per plan node, the node contract's `helpful_ccs`, capability,
  requirement IDs and, per checked output (`node_check.effective_spec`, else the
  node contract's `check_spec`), its verifier capability, required stage,
  review flag, pinned verifier inputs, criteria and up to eight latest
  `node_check` observations in compact form (state, passed, reason, verifier
  checks `{name,status,stage,detail}` and `stage_reached`, reviewer verdict,
  summary and findings, whether the node cites it, whether the check used the
  node's current settings, and `superseded` when an operator reopened the node
  or an ancestor after it). The full records stay in `records.observations`.
  Empty for curated replays.
- `controls` (live homes): `operator`, `running` (controller lock held),
  `outcome`, `stop_reason` and `resume` (allowed now).

The UI derives the gate statement from these records with the host's done rule
(`node_check.pending`): closed when every required output's latest check passed;
open with the first output that has no check, a running or failed check, a
check under other settings, a check from before a reopen, or an uncited pass;
held when the node carries an operator hold. Lab results for `factory.contract/2`
runs come from `lab_report` observations recorded by the lab manager; arms,
metrics, metric direction (`measurement.metrics.*.better`) and the reference arm
(`comparison`, else `correctness.reference.arm`, else the `baseline` role, else
the first arm) are read from the contract. factory.lab-report/1 has no cold/warm
field, so the lab names it in the test or request ID (`speed-cold`,
`p512:warm`); without either token the test ID is the condition.

Missing/mismatched manifest files remain visible. `MANIFEST.json` itself and
unlisted files have `untracked` status; that status does not assert provenance.
Digests describe original bytes, while displayed content is sanitized. Symlink
bundles and paths outside the evidence root are rejected. Live file browsing is
limited to recorded artifacts and that task's session/launch log.

Launching does not provision credentials. The operator must prepare authentication
and review template resource/GPU policy before enabling launch. HTTP reads never
launch jobs. Browser POST requests require same-origin Host/Origin. The gateway
must remain on localhost behind the demo frontend proxy.

The Spark demo's `star-capsule-inspection` launch template has a fixed preparation
helper: copies the existing operator login into the new isolated home using the
reviewed `copy_auth_for_home` helper, then attaches contract/capsule/ontology
materials as native artifacts. It requires exactly the reviewed read grants and
an explicit inspection-only label. It does not provision source checkouts or
launch any builds/models. Other template IDs do not invoke this helper.

`FACTORY_LAUNCH_SYSTEMD=1` (set by the Spark demo service) places detached runs in
separate user systemd scopes, so gateway restarts do not kill their sessions.
The generic backend default remains a detached local subprocess. Content-addressed
artifact files include a human `display_path` from native artifact identities;
HTTP reads still use the confined original `path`, never a display label.

## Step-through correction history

`GET /runs/{id}` carries `correction_overview`, keyed by node ID, with counts of
findings, corrective notes and evidence-backed repairs. `GET /runs/{id}/nodes/{node}`
returns those counts and ordered `corrections.events`. The native story and
curated replay also carry each correction under `correction`. Each event identifies
its original check, operator inbox note, or cited repair observation or artifact.
The host, capsule verifier and independent reviewer retain separate verdicts.

For a new corrective `jiuwenswarm-factory note`, name the exact check observation
ID, the reported problem and the specific fix. Include the finding ID shown in the
story when the check reported several findings. A new repair observation can carry
`addresses_findings` with those exact finding IDs. The passing check must cite
that observation as evidence for the same output. A subsequent pass without
specific repair evidence leaves earlier findings visible and unresolved.
