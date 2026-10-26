# Acknowledging a historical unknown model call

The protected private relay RPC also supports `probe` with exactly
`endpoint_id` and `binding_sha256`. It resolves the installed host-Codex binding,
copies it with a deliberately invalid binary pin, and sends a fixed small input
to the same helper transport. Successful readiness requires the original
expected validation rejection before native account access or App Server launch.
No provider request is sent and no request-ledger row is written. The probe may
run while a historical unknown exists, but refuses while inference is active.
Its response contains only closed readiness/transport diagnostics; it does not
establish model entitlement or scientific execution. Use the existing private
RPC capability and app UID boundary; there is no public HTTP probe route.

An unknown result remains unknown permanently unless original correlated
provider terminal evidence is available. Restarting the relay never clears its
durable admission guard. The offline operator command below records an explicit
authorization for distinct new work after investigation and local containment.
It does not replay, retry, repair or reclassify the original request.

Stop the relay and app work first. Investigate the call-owned helper and native
App Server processes and retain bounded, nonsecret observations. Verify the app
has no active run, unfinished claim or unreleased lease. A stopped local process
does not prove provider completion: acknowledge that provider status is unknown.
Do not inspect or copy authentication caches. For an old relay version without
the singleton lock, independently confirm that its process exited before using
this command.

Use the matching source checkout and Linux interpreter as the private runtime's
owner. Copy the containment observations to an absolute, owner-only mode-0600
file outside app/runner mounts. Obtain the exact existing request ID and payload
digest from a read-only inspection of `requests.sqlite3`.

```sh
python -m jiuwenswarm.research.local_model_recovery \
  --runtime /operator/private/host-codex-relay \
  --request-id ORIGINAL_REQUEST_ID \
  --payload-sha256 ORIGINAL_PAYLOAD_DIGEST \
  --evidence-file /operator/private/containment-observation.json \
  --operator-note 'Investigated observer loss; authorize distinct new work after local containment.' \
  --authorize-new-work \
  --confirm-local-process-containment \
  --acknowledge-provider-status-unknown
```

This is a privileged operator operation, absent from the authenticated app RPC.
The relay and recovery command hold the same exclusive runtime lock. The command
opens the existing SQLite ledger read-only, retains an immutable logical snapshot
of all committed rows, records the physical database file hash, and copies the
observations into the private acknowledgement directory. Its acknowledgement
binds the exact request ID, payload digest, original result hash, snapshot hash
and evidence hash. Authority is published last with exclusive creation and fsync.
Do not delete or edit any of these retained files.

After successful acknowledgement, start the matching relay normally with the
same runtime, session, catalog and ledger. A new request can proceed only when
every historical unknown has its own valid acknowledgement. A NULL/incomplete
claim always blocks, and a later unknown blocks again. Reusing the acknowledged
request ID returns its original unknown response; different payload bytes with
that ID remain invalid. An acknowledgement never adds scientific success or
provider terminal evidence to the historical benchmark.

Preserve `unknown-acknowledgements/` with the ledger across deployment restarts.
Its files are private operator authority: app and benchmark users must never
have write access. Missing or corrupted acknowledgements fail closed. If the
command fails while publishing files, keep the partial evidence for inspection;
do not bypass the guard or start a different ledger.
