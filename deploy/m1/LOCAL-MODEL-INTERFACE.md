# Local model interface and deployment

This is the Dockerless **inference** path. AI4R, its existing authenticated
benchmark runner and Harbor run on a Docker-enabled application host. The GPU
host needs SSH, Python 3 and an existing OpenAI-compatible loopback endpoint;
it does not need Docker. Harbor continues to use the same protected app bridge
and original runner exports.

## Components and boundaries

The account model menu selects an operator-installed `local-*` ID without an
API key. It cannot install a URL, SSH command, credential or model policy.
Published cloud presets retain their existing endpoint and credential rules.

The app model owner reads a root-owned catalog and freezes its complete policy
hash, model revision and account binding into the run. Removing that account
binding, disabling the catalog entry or changing its policy prevents further
calls under the old selection. Continuations retain the original selection;
there is no automatic model fallback. Policy changes require an idle deployment
and reconfiguration; the app's mounted catalog is a pinned snapshot.

The private relay runs **on the application host**, under its operator's normal
UID and SSH identity. Its authenticated Unix socket permits the app UID 10001;
the client also checks the relay's peer UID and socket custody. The relay
invokes a fixed Python helper over SSH. Only that helper reaches the GPU host's
literal `127.0.0.1` or `::1` HTTP endpoint. There is no TCP relay listener, extra
localhost app port or model service restart. The UI remains on port **5175**.

Only the app receives the read-only config volume and dedicated socket export.
The benchmark runner and scientific execution sandboxes receive neither.
SSH private keys remain with the host operator; capabilities never enter public
model records, command arguments or exported request traces.

## Portable catalog

Copy [local-models.example.json](local-models.example.json) into an operator
control directory on the application host. The checked-in example is disabled.
Set the SSH target, exact served model name, checkpoint revision, display name,
context/output/prompt limits and generation budget for the selected hardware.
Enable only the intended entry. The upstream path must be `/v1` on a literal
loopback HTTP address; arbitrary network URLs are rejected.

For Docker deployments keep the transport paths exactly:

```json
{
  "socket_path": "/run/ai4r-local-model/model.sock",
  "session_file": "/run/ai4r-local-model-config/session.json",
  "peer_uid": 1000,
  "socket_mode": 432
}
```

`peer_uid` is the actual relay UID on the **application host**, not the GPU SSH
account UID. `432` is octal `0660`. This deployment option requires a local
standard rootful Linux Docker daemon at `unix:///var/run/docker.sock`.
Remote Docker endpoints, rootless daemons and user-namespace remapping are
rejected because host paths and peer UIDs must describe the same Linux host.

The host catalog must be root-owned, regular, single-linked, without symlink
components, and mode `0444`, `0644`, `0600` or `0400`. It must also be readable by
the relay operator. Keep the relay's private runtime directory owner-only mode
`0700`; its session and durable request ledger remain mode `0600`.

Provision a separate, initially empty socket export directory, owned by the
relay UID, group **10001**, mode **02710**. The setgid bit makes new sockets
inherit the app group. This requires authorized host administration; configure
does not change host users, groups or directory ownership. Export only this
directory, never the private runtime or SSH directory. The relay creates
`model.sock` there with mode `0660`; no other entry is permitted.

## Explicit activation, after the model is reserved

These are deployment instructions, not actions performed by creating the
interface. Use absolute application-host paths. First ensure that the relay
operator's existing SSH identity and known-hosts entry are ready. The relay uses
batch mode and strict host-key checking; it will not open an interactive login.

Run the new relay from the matching source/runtime on the application host:

```sh
python -m jiuwenswarm.research.local_model_relay \
  --catalog /operator/local-models.json \
  --runtime /operator/private/model-relay \
  --socket-directory /operator/model-export \
  --allowed-uid 10001
```

Starting the relay creates its private session and socket; it does not probe or
generate against the upstream model. Supervise this process using the host's
normal process manager. A stale socket after an unclean exit causes startup to
refuse; verify the original process is gone before explicitly removing that
socket. Preserve the ledger and session.

Record the local transport in the existing operator profile:

```sh
python deploy/m1/ai4r.py --profile /operator/app.json local-model configure \
  --catalog /operator/local-models.json \
  --session-file /operator/private/model-relay/session.json \
  --socket-directory /operator/model-export
```

This command checks idle state, source custody and SHA-256 pins. It records
paths and hashes only; it does not start containers, SSH or inference. Paths
refer to the operator profile's application execution host.

Build a new image containing this interface and use the normal deployment
workflow in [HARBOR-INTEGRATION.md](HARBOR-INTEGRATION.md). Use a separate
deployment for a changed app image; preserve the old pilot and its results.
On explicit `start`, the operator rechecks the pinned files and live socket,
then uses a network-disabled Docker helper to populate a labeled private volume.
The catalog is mounted root-owned `0444`; the session is app-owned `0400`.
Only secret stdin carries capability bytes. Repeated starts verify an active
volume rather than rewriting it; changed files require idle reconfiguration and
a stopped app before replacement.

In the English UI, select the approved local endpoint under Settings → Models.
Then perform one controlled live qualification through the real AI4R bridge,
inspect its actual model identity and original evidence, and run the supported
Harbor pipeline case sequentially. Bundle `--expected-model` remains an
attribution expectation; it does not select the app model.

## Effects, evidence and recovery

The relay commits a request claim before invoking SSH and stores the original
bounded provider reply. Reusing the same request ID and payload returns its
saved receipt; changed payloads are rejected. Concurrent new requests receive
a durable busy refusal instead of waiting in a queue. No automatic retries or
output repair occur. Text must be nonempty, finish with `stop`, and contain no
tool calls; truncated output remains a failure with its observed usage.

The app retains original request/response packets under the existing native
trace records and attaches them to the protected model call. Effective identity
comes from `response.model`; token usage comes from the original provider
response. Missing observations remain unavailable. Requested identity is never
substituted for the actual served model.

A lost reply, cancellation, timeout or unresolved crash claim blocks subsequent
relay effects, including after restart. Killing SSH proves only local observer
termination; the bridge does not report the GPU work as contained. Preserve the
ledger and original run evidence. Reconcile on the inference host before an
explicit operator recovery; there is deliberately no automatic reset command.

## Qualification status

October 25, 2026: implemented and tested offline with fixture providers and a
real Linux Unix-socket RPC connection. All 36 focused Linux fixtures pass,
including actual socket group inheritance. A broader Windows regression passed
147 tests (four environment-dependent checks skipped); the final deployment and
Harbor policy-pin checks also pass. The model owner's existing cloud and
subscription behavior remains covered. The English UI passes its network-disabled
production build. No Qwen request, Spark connection or service activation
was performed while the model was reserved by another agent.

This interface still needs live qualification with reserved GPU access. It does
not supply the separate protected CC/MR/RSI/verifier fault bindings described in
the Harbor guide, and does not establish a passing ten-case live benchmark.

### Subsequent authorized live checkpoint

Later on October 25 the user reserved Qwen and authorized activation, with all
RSI files to remain unchanged. Workstation Docker now has the English app and
the separate runner; Spark's existing service and checkpoint were unchanged.
One bounded request through the authenticated container-to-host relay returned
`{"value":4}`, effective model `Qwen3.8-27B-NVFP4`, 28 prompt tokens and six output
tokens. This qualifies the transport, not a scientific benchmark.

The initial Harbor attempt found unsupported JSON document and loose-source
uploads before model dispatch. Strict JSON document extraction and deterministic
repository ZIP transport were then implemented; eight actual public uploads
passed exact-byte/hash checks. A fresh three-variant pipeline attempt submitted
real app runs and completed with zero Harbor orchestration exceptions. Its first
Intention Compiler inference exceeded 120 seconds and became `outcome_unknown`;
the relay's durable latch blocked later inference. None of the variants passed.
All original results remain retained and unmodified.

The original exported subnode contract and its binding both impose **120 seconds**
for the intent call. The parent node allows 600 seconds across four model calls.
Increasing only the endpoint timeout cannot override these protected limits.
No capsule, template, benchmark budget or grading criterion was changed to
accommodate this hardware's observed inference time.

Small individually downloaded collections also lacked the original Ref inventory
required by Harbor normalization. Generated cases now request the runner's
optional `collection_mode: "archive"`; legacy cases retain `auto`. The corrected
runner image is deployed. The existing authenticated archive collector validated
all 44 members of the actual halted run; the unchanged normalizer joined 13 typed
records using the actual inventory in a separate diagnostic view. Original
records and assessments were not rewritten. A final model-free Harbor job
completed three expected unavailable assessments with zero exceptions.

Complete trace publication for a late interrupted call remains a limitation.
Input and observation wrappers are excluded by the current public export
representation; a late native trace can miss its publication-index phase.
Unavailable through this export does not mean never captured. No Refs were
invented and no export allowlist or disclosure restriction was broadened.

Final regression: **217 tests passed, five environment-dependent checks skipped,
20 subtests passed**. SHA-256 comparison confirmed **349 RSI-related files** in
this checkout unchanged, with none added or removed. After separate host/helper
and queue-drain checks, the local relay was stopped and its original uncertain
ledger retained unchanged. Spark showed zero running/waiting requests at
19:29 America/Toronto. The app remains on port 5175 with Qwen selected; model
readiness is unavailable while this relay is stopped. A reviewed fresh transport
generation and resolution of the protected compiler-time limit are required
before further live qualification; do not clear the old ledger or replay its call.

The active local profile is
`D:\Codex Development Runs\harbor-deployment-20261025\qwen-activation\operator-v2.json`.
The installed app build is
`3bd67a98c5779b68399f89c74ad84d9d19b07fe404c49b7dd7251507783e0b62`.
Original outcomes, proof files and the local run report are retained alongside
that profile. These are checkpoint-specific paths; use new dedicated paths on
other hardware.
