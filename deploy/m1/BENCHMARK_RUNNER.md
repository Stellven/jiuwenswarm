# Sequential benchmark runner

Use [OPERATIONS.md](OPERATIONS.md) for the current integrated setup, local/SSH
workflow, scoped credential provisioning, persistent mounts and result return.
All required source is in the repository. The common entry point is
`python deploy/m1/ai4r.py`; `runner.py` is a compatibility wrapper.

The app and runner remain two separate images/containers. The runner uses the
[supported research interface](research-client-interface.md), executes one task
at a time and retains real artifact bytes for human review. It does not judge
research correctness. Neither runtime container has the Docker socket.

## Historical connected evidence from the previous workstation

The following records describe the prior implementation's checks. They have not
been reproduced on this workstation and do not validate the new host tooling.


`smoke-20261022-02` completed two supplied synthetic PDF tasks in sequence on the
pinned app build `789e4745...`. Interrupting the observer and resuming kept the
same first request/run IDs; the second task started after collection confirmation.
Both archives and actual summary bytes were collected on the host. All 122 host
files and the pre-existing sentinel retained their hashes after both containers
were removed and recreated. These checks assess execution and persistence;
humans assess the summaries.

The final running app build is `db45a807...` (stable export filenames) with runner
image `193c0ae0...` (bounded archives and portable readable-copy paths). The old
execution image remains pinned for traceability. Final readiness, repeated stable
artifact manifests, and a matching summary download were verified after recreation.
The fixed privileged supervisor exception above remains; optional telemetry is
reported only when exposed, and no GPU or unavailable usage is inferred as zero.

## Reusing retained input uploads

When a later campaign references an input already uploaded to the same workspace,
the runner reuses it only when scope, kind, filename, byte size and SHA-256 all
match. Reusing the upload preserves its existing ID for intake and avoids sending
the same bytes again.

If that filename is already occupied by different bytes, or the server reports a
concurrent upload and no single exact match can be confirmed, preparation fails
with a conflict. The runner never overwrites or deletes retained inputs. Use a
different filename when the intended input bytes change.
